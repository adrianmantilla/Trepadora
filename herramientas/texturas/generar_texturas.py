"""Genera las texturas de Trepadora por procedimiento (sin Substance Painter).

Dibuja en el espacio UV de cada forma de hoja (ver ``geometria.ESCALA_UV`` y
``geometria.uv_hoja``) sus nervios principales, los secundarios y una red fina
de nervillos, y de ahí saca los mapas de ``trepadora.texturas.MAPAS``.

La corteza del plugin sale de Substance 3D Painter
(``herramientas/painter/corteza_painter.py``), así que este script no la toca
salvo con ``--con-corteza``: entonces dibuja una corteza procedural que se
repite sin costuras (ruido filtrado con la transformada de Fourier, que es
periódico por construcción), con surcos a lo largo del tallo. Sirve para
quien no tenga Painter.

Se dibuja a 4K y se reduce al resto de resoluciones. Necesita NumPy y Pillow
(no Maya). Desde la raíz del repositorio:

    python herramientas/texturas/generar_texturas.py [carpeta] [--solo 512,1k] [--con-corteza]

Por defecto escribe en ``texturas/``.
"""

import argparse
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(AQUI, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from trepadora import geometria, texturas  # noqa: E402

N = 4096   # resolución de trabajo


# ------------------------------------------------------------------ utilidades
def _ruido_periodico(n, semilla, escala, alargado=1.0, potencia=2.0):
    """Ruido suave que se repite en los bordes, de media 0 y desviación 1.

    ``escala``: tamaño de los detalles en fracción de la imagen. ``alargado``
    > 1 estira las formas a lo largo de v (las filas de la imagen).
    """
    rng = np.random.default_rng(semilla)
    blanco = rng.standard_normal((n, n)).astype(np.float32)
    fu = np.fft.fftfreq(n)[None, :].astype(np.float32)
    fv = np.fft.fftfreq(n)[:, None].astype(np.float32)
    f = np.sqrt((fu * n * escala) ** 2 + (fv * n * escala * alargado) ** 2)
    filtro = 1.0 / (1.0 + f ** potencia)
    filtro[0, 0] = 0.0
    r = np.real(np.fft.ifft2(np.fft.fft2(blanco) * filtro)).astype(np.float32)
    return (r - r.mean()) / (r.std() + 1e-8)


def _fbm(n, semilla, escalas, alargado=1.0):
    total = np.zeros((n, n), np.float32)
    peso_total = 0.0
    for k, escala in enumerate(escalas):
        peso = 0.55 ** k
        total += peso * _ruido_periodico(n, semilla + 17 * k, escala, alargado)
        peso_total += peso
    return total / peso_total


def _desenfocar(a, radio):
    img = Image.fromarray(np.clip(a * 255.0, 0, 255).astype(np.uint8), "L")
    return np.asarray(img.filter(ImageFilter.GaussianBlur(radio)), np.float32) / 255.0


def _desenfocar_real(a, radio):
    """Desenfoque de un mapa con valores cualesquiera (no solo 0..1)."""
    lo, hi = float(a.min()), float(a.max())
    return _desenfocar((a - lo) / (hi - lo + 1e-8), radio) * (hi - lo) + lo


def _normal(altura, fuerza):
    """Mapa de normales (espacio tangente, Y arriba = v creciente) desde una altura."""
    # Las filas de la imagen bajan cuando v sube.
    dh_du = (np.roll(altura, -1, axis=1) - np.roll(altura, 1, axis=1)) * 0.5
    dh_dv = -(np.roll(altura, -1, axis=0) - np.roll(altura, 1, axis=0)) * 0.5
    nx, ny = -dh_du * fuerza, -dh_dv * fuerza
    nz = np.ones_like(nx)
    largo = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx / largo, ny / largo, nz / largo], axis=-1) * 0.5 + 0.5


def _guardar(datos, juego, mapa, salida, solo):
    """Guarda ``datos`` (0..1, gris o RGB) a cada resolución."""
    datos = np.clip(datos, 0.0, 1.0)
    modo = "RGB" if datos.ndim == 3 else "L"
    img = Image.fromarray((datos * 255.0 + 0.5).astype(np.uint8), modo)
    for res in texturas.RESOLUCIONES:
        if solo and res not in solo:
            continue
        lado = texturas.PIXELES[res]
        copia = img if lado == img.size[0] else img.resize((lado, lado), Image.LANCZOS)
        carpeta = os.path.join(salida, res)
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, texturas.archivo(juego, mapa))
        if ruta.endswith(".jpg"):
            calidad = 92 if mapa == "normal" else 90
            copia.save(ruta, quality=calidad, optimize=True, subsampling=0)
        else:
            copia.save(ruta, optimize=True)
        print("  ", os.path.relpath(ruta, salida), os.path.getsize(ruta) // 1024, "KB")


# ---------------------------------------------------------------------- hojas
def _ancho(perfil, y):
    for (y0, w0), (y1, w1) in zip(perfil, perfil[1:]):
        if y0 <= y <= y1:
            k = (y - y0) / (y1 - y0) if y1 > y0 else 0.0
            return w0 + (w1 - w0) * k
    return 0.0


def _perfil_envolvente(forma):
    """El perfil más ancho de los que usa la forma (la hiedra se mezcla con el corazón)."""
    perfiles = [geometria.PERFILES_HOJA[forma]]
    if forma == "hiedra":
        perfiles.append(geometria.PERFILES_HOJA["corazon"])
    ys = sorted({y for p in perfiles for y, _ in p})
    return [(y, max(_ancho(p, y) for p in perfiles)) for y in ys]


# Puntas de los nervios principales (cx, y), además del central, en la mitad
# derecha de la hoja (la izquierda es su reflejo). Hojas palmeadas: salen de la
# base. La alargada solo tiene el central (nervadura pinnada).
_NERVIOS = {
    "hiedra": [(0.47, 0.22), (0.26, 0.55), (0.30, 0.07)],
    "corazon": [(0.37, 0.40), (0.31, 0.15)],
    "redonda": [(0.43, 0.44), (0.33, 0.14)],
    "alargada": [],
}
_BASE = (0.0, 0.035)


def _curva(a, b, combar, pasos=24):
    """Curva suave de a a b, combada hacia fuera (``combar`` en fracción del largo)."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    largo = math.hypot(dx, dy) or 1e-6
    # Punto de control desplazado en perpendicular, hacia arriba (la punta).
    px, py = -dy / largo, dx / largo
    if py < 0:
        px, py = -px, -py
    cx, cy = ax + dx * 0.5 + px * combar * largo, ay + dy * 0.5 + py * combar * largo
    puntos = []
    for i in range(pasos + 1):
        t = i / pasos
        puntos.append(((1 - t) ** 2 * ax + 2 * (1 - t) * t * cx + t * t * bx,
                        (1 - t) ** 2 * ay + 2 * (1 - t) * t * cy + t * t * by))
    return puntos


def _dentro(perfil, cx, y, margen=0.92):
    return 0.0 <= y <= 1.0 and abs(cx) <= _ancho(perfil, y) * margen


_CELDA = 0.008


class _Ocupado(object):
    """Qué nervio pasa por cada celda de una rejilla fina (en coordenadas de la hoja)."""

    def __init__(self):
        self.celdas = {}

    def marcar(self, puntos, dueno):
        for (x0, y0), (x1, y1) in zip(puntos, puntos[1:]):
            pasos = max(1, int(math.hypot(x1 - x0, y1 - y0) / (_CELDA * 0.5)))
            for i in range(pasos + 1):
                t = i / pasos
                clave = (int(math.floor((x0 + (x1 - x0) * t) / _CELDA)),
                         int(math.floor((y0 + (y1 - y0) * t) / _CELDA)))
                self.celdas.setdefault(clave, dueno)

    def dueno(self, x, y):
        return self.celdas.get((int(math.floor(x / _CELDA)), int(math.floor(y / _CELDA))))


def _marchar(perfil, ocupado, x, y, dx, dy, padre, paso=0.004, curva=0.03, largo_max=0.4):
    """Un nervio secundario: avanza curvándose hacia la punta hasta el borde o
    hasta topar con otro nervio (y entonces se une a él, cerrando un lazo)."""
    puntos = [(x, y)]
    largo = 0.0
    while largo < largo_max:
        dy += curva
        n = math.hypot(dx, dy) or 1e-6
        dx, dy = dx / n, dy / n
        nx, ny = x + dx * paso, y + dy * paso
        if not _dentro(perfil, nx, ny, 0.93):
            break
        otro = ocupado.dueno(nx, ny)
        if otro is not None and otro != padre and largo > 0.015:
            puntos.append((nx, ny))
            break
        x, y = nx, ny
        puntos.append((x, y))
        largo += paso
    return puntos, largo


def _nervios(forma, rng):
    """Lista de (puntos, grosor inicial, grosor final, nivel) en coordenadas de la hoja."""
    perfil = _perfil_envolvente(forma)
    ocupado = _Ocupado()
    lineas = []
    central = _curva(_BASE, (0.0, 0.975), 0.0)
    principales = [(central, 0)]
    lineas.append((central, 0.016, 0.003, 0))
    ocupado.marcar(central, 0)
    for x, y in _NERVIOS[forma]:
        for lado in (1, -1):
            curva = _curva(_BASE, (lado * x, y), 0.10 + 0.04 * rng.random())
            principales.append((curva, len(principales)))
            lineas.append((curva, 0.010, 0.0025, 0))
            ocupado.marcar(curva, len(principales) - 1)
    # Secundarios: salen de los principales hacia el borde, se curvan hacia la
    # punta y se unen al siguiente nervio que encuentran.
    secundarios = []
    for curva, dueno in principales:
        n = len(curva)
        es_central = dueno == 0
        paradas = np.linspace(0.10 if es_central else 0.18, 0.92, 11 if es_central else 6)
        for t in paradas:
            t = min(0.97, t + rng.uniform(-0.025, 0.025))
            i = min(n - 2, int(t * (n - 1)))
            (x0, y0), (x1, y1) = curva[i], curva[i + 1]
            tx, ty = x1 - x0, y1 - y0
            largo = math.hypot(tx, ty) or 1e-6
            tx, ty = tx / largo, ty / largo
            for lado in (1, -1):
                giro = math.radians(rng.uniform(38, 55)) * lado
                dx = tx * math.cos(giro) - ty * math.sin(giro)
                dy = tx * math.sin(giro) + ty * math.cos(giro)
                puntos, recorrido = _marchar(perfil, ocupado, x0, y0, dx, dy, dueno,
                                             curva=rng.uniform(0.003, 0.009))
                if recorrido < 0.03:
                    continue
                secundarios.append(puntos)
                lineas.append((puntos, 0.0048, 0.0014, 1))
                ocupado.marcar(puntos[3:], 100 + len(secundarios))
    return perfil, lineas


def _a_imagen(cx, y, escala, n):
    u, v = geometria.uv_hoja(cx, y, escala)
    return u * n, (1.0 - v) * n


def _dibujar_nervios(forma, escala, n, rng):
    """Máscaras (0..1) de los nervios principales y de los secundarios."""
    perfil, lineas = _nervios(forma, rng)
    grande = n * 2   # se dibuja al doble y se reduce: bordes suaves
    capas = {0: Image.new("L", (grande, grande), 0), 1: Image.new("L", (grande, grande), 0)}
    for puntos, g0, g1, nivel in lineas:
        dibujo = ImageDraw.Draw(capas[nivel])
        total = len(puntos) - 1
        for i in range(total):
            g = (g0 + (g1 - g0) * i / total) / escala * grande
            a = _a_imagen(*puntos[i], escala, grande)
            b = _a_imagen(*puntos[i + 1], escala, grande)
            dibujo.line([a, b], fill=255, width=max(1, int(round(g))))
            r = g / 2.0
            dibujo.ellipse([b[0] - r, b[1] - r, b[0] + r, b[1] + r], fill=255)
    return perfil, {k: np.asarray(c.resize((n, n), Image.LANCZOS), np.float32) / 255.0
                    for k, c in capas.items()}


def _red_de_nervillos(n, semilla, celdas):
    """Red fina de nervillos: los bordes de unas celdas de Voronoi irregulares."""
    rng = np.random.default_rng(semilla)
    # Un punto al azar en cada celda de una rejilla de celdas × celdas.
    jitter_x = (np.arange(celdas)[:, None] + rng.random((celdas, celdas))).astype(np.float32)
    jitter_y = (np.arange(celdas)[None, :] + rng.random((celdas, celdas))).astype(np.float32)
    coord = (np.arange(n, dtype=np.float32) + 0.5) / n * celdas
    gx, gy = coord[None, :], coord[:, None]
    cx, cy = np.floor(gx).astype(int), np.floor(gy).astype(int)
    d1 = np.full((n, n), 9.0, np.float32)
    d2 = np.full((n, n), 9.0, np.float32)
    for ox in (-1, 0, 1):
        for oy in (-1, 0, 1):
            ix, iy = (cx + ox) % celdas, (cy + oy) % celdas
            px = jitter_x[ix, iy] + (cx + ox - ix)
            py = jitter_y[ix, iy] + (cy + oy - iy)
            d = np.sqrt((gx - px) ** 2 + (gy - py) ** 2)
            d2 = np.where(d < d1, d1, np.minimum(d2, d))
            d1 = np.minimum(d1, d)
    borde = d2 - d1
    return np.clip(1.0 - borde / 0.09, 0.0, 1.0) ** 1.5


def _mascara_hoja(perfil, escala, n, holgura=1.0):
    """1 dentro de la silueta de la hoja (ensanchada ``holgura`` veces), 0 fuera."""
    filas = (np.arange(n, dtype=np.float32) + 0.5) / n
    u = filas[None, :]
    v = 1.0 - filas[:, None]
    cx = (u - 0.5) * escala
    y = (v - 0.5) * escala + 0.5
    anchos = np.interp(y[:, 0], [p for p, _ in perfil], [w for _, w in perfil], 0.0, 0.0)
    return (np.abs(cx) <= anchos[:, None] * holgura).astype(np.float32)


def textura_hoja(forma, salida, solo, semilla=7):
    escala = geometria.ESCALA_UV[forma]
    rng = random.Random(semilla)
    print("hoja", forma, "escala UV", round(escala, 3))
    perfil, nervios = _dibujar_nervios(forma, escala, N, rng)
    principal = nervios[0]
    secundario = nervios[1]
    nervillos = _red_de_nervillos(N, semilla + 1, int(round(30 * escala)))
    nervillos = _desenfocar(nervillos, max(0.5, N / 2048.0)) * (1.0 - principal)
    manchas = _fbm(N, semilla + 2, (0.12, 0.05, 0.02))
    hoja = _mascara_hoja(perfil, escala, N)

    # Altura: los nervios, hundidos en el haz (la hiedra los tiene así), con
    # un leve abombado entre ellos.
    k = N / 1024.0   # los radios y la fuerza, en píxeles de una textura de 1K
    surco = _desenfocar(principal, 6 * k) * 0.9 + _desenfocar(secundario, 4 * k) * 0.6
    # Sin ruido fino: la hiedra es lisa y brillante, y el ruido haría pesar
    # mucho el mapa de relieve sin verse.
    ondas = _ruido_periodico(N, semilla + 4, 0.15)
    altura = -surco - 0.2 * _desenfocar(nervillos, 2 * k) + 0.03 * ondas
    normal = _normal(altura, fuerza=10.0 * k)

    # Color relativo: nervios más claros y amarillos, nervillos apenas, y
    # manchas suaves. Media 0,5 dentro de la hoja.
    luz = 1.0 + 0.55 * principal + 0.35 * secundario + 0.16 * nervillos + 0.05 * manchas
    detalle = np.stack([luz * (1.0 + 0.10 * (principal + secundario)),
                        luz,
                        luz * (1.0 - 0.35 * (principal + secundario))], axis=-1)
    dentro = hoja > 0.5
    for c in range(3):
        detalle[..., c] *= 0.5 / detalle[..., c][dentro].mean()

    rugosidad = 0.30 + 0.10 * np.maximum(principal, secundario) + 0.04 * nervillos
    rugosidad += 0.02 * manchas
    traslucidez = 1.0 - 0.6 * principal - 0.4 * secundario - 0.12 * nervillos + 0.04 * manchas

    juego = texturas.juego_hoja(forma)
    _guardar(detalle, juego, "detalle", salida, solo)
    _guardar(normal, juego, "normal", salida, solo)
    _guardar(rugosidad, juego, "rugosidad", salida, solo)
    _guardar(traslucidez, juego, "traslucidez", salida, solo)


# -------------------------------------------------------------------- corteza
def textura_corteza(salida, solo, semilla=11):
    """Corteza que se repite: u alrededor del tallo, v a lo largo.

    Surcos largos y estrechos a lo largo del tallo (unos diez por vuelta),
    con placas entre ellos y alguna mancha de musgo.
    """
    print("corteza")
    surcos = _fbm(N, semilla, (0.10, 0.05), alargado=4.0)
    grieta = (1.0 - np.abs(np.tanh(3.0 * surcos))) ** 2   # 1 en las grietas, estrechas
    placas = _fbm(N, semilla + 5, (0.08, 0.03), alargado=2.5)
    fino = _fbm(N, semilla + 7, (0.012, 0.006), alargado=3.0)
    musgo = np.clip((_fbm(N, semilla + 13, (0.1, 0.04)) - 1.0) * 1.2, 0.0, 1.0)
    altura = -0.9 * grieta + 0.15 * placas + 0.1 * musgo
    normal = _normal(_desenfocar_real(altura, max(0.5, N / 2048.0)), fuerza=N / 120.0)
    crestas = 1.0 - grieta
    luz = 1.0 - 0.55 * grieta + 0.10 * placas + 0.03 * fino
    detalle = np.stack([luz * (1.0 - 0.30 * musgo),
                        luz * (1.0 + 0.15 * musgo),
                        luz * (1.0 - 0.35 * musgo)], axis=-1)
    for c in range(3):
        detalle[..., c] *= 0.5 / detalle[..., c].mean()
    rugosidad = 0.80 - 0.10 * crestas + 0.03 * fino + 0.06 * musgo
    _guardar(detalle, "corteza", "detalle", salida, solo)
    _guardar(normal, "corteza", "normal", salida, solo)
    _guardar(rugosidad, "corteza", "rugosidad", salida, solo)


def main(argv=None):
    global N
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("salida", nargs="?", default=os.path.join(REPO, "texturas"))
    p.add_argument("--solo", default="", help="resoluciones separadas por comas (512,1k...)")
    p.add_argument("--formas", default=",".join(geometria.FORMAS_HOJA))
    p.add_argument("--con-corteza", action="store_true",
                   help="dibuja también la corteza procedural (sustituye a la de Painter)")
    p.add_argument("--lado", type=int, default=N, help="resolución de trabajo (4096)")
    a = p.parse_args(argv)
    N = a.lado
    solo = [s for s in a.solo.split(",") if s]
    for forma in [f for f in a.formas.split(",") if f]:
        textura_hoja(forma, a.salida, solo)
    if a.con_corteza:
        textura_corteza(a.salida, solo)


if __name__ == "__main__":
    main()
