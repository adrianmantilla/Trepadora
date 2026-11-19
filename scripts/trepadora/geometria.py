"""Construcción de mallas (vértices y caras) en Python puro.

Las funciones devuelven listas sencillas para que Maya (``MFnMesh.create``)
u otro programa puedan crear la malla:

* ``vertices``: lista de (x, y, z)
* ``conteos``: número de vértices de cada cara
* ``indices``: índices de vértices de todas las caras, seguidos
* ``colores``: un color (r, g, b) por vértice
"""

import math
import random
from typing import List, Tuple

from . import vectores as v

Vector = Tuple[float, float, float]

# Perfiles de hoja: (posición a lo largo 0..1, semiancho). La base y la punta
# tienen ancho cero. "hiedra" tiene dos lóbulos laterales y uno central.
PERFILES_HOJA = {
    "hiedra": [
        (0.00, 0.00), (0.04, 0.24), (0.12, 0.44), (0.22, 0.54), (0.30, 0.40),
        (0.36, 0.24), (0.46, 0.25), (0.56, 0.30), (0.66, 0.24), (0.78, 0.15),
        (0.90, 0.07), (1.00, 0.00),
    ],
    "corazon": [
        (0.00, 0.00), (0.08, 0.26), (0.22, 0.40), (0.40, 0.42), (0.58, 0.34),
        (0.76, 0.21), (0.90, 0.09), (1.00, 0.00),
    ],
    "alargada": [
        (0.00, 0.00), (0.10, 0.10), (0.30, 0.18), (0.55, 0.19), (0.80, 0.12), (1.00, 0.00),
    ],
}
PERFIL_HOJA = PERFILES_HOJA["hiedra"]


class Malla:
    def __init__(self):
        self.vertices: List[Vector] = []
        self.conteos: List[int] = []
        self.indices: List[int] = []
        self.colores: List[Vector] = []

    def vertice(self, p: Vector, color: Vector) -> int:
        self.vertices.append(p)
        self.colores.append(color)
        return len(self.vertices) - 1

    def cara(self, *ids: int) -> None:
        self.conteos.append(len(ids))
        self.indices.extend(ids)


# ------------------------------------------------------------------- tallos
def malla_tallos(crecimiento, radios: List[List[float]], lados: int = 6,
                 semilla: int = 1) -> Malla:
    """Un tubo por rama, con el radio de cada punto, cerrado en punta."""
    rng = random.Random(semilla * 31 + 5)
    malla = Malla()
    for rama, radios_rama in zip(crecimiento.ramas, radios):
        puntos = rama.puntos
        n = len(puntos)
        if n < 2:
            continue
        base_color = _variar((0.27, 0.19, 0.12), rng, 0.15)
        joven = (0.33, 0.30, 0.15)
        normal_ref = rama.normales[0]
        anillos = []
        for k in range(n):
            if k == 0:
                t = v.resta(puntos[1], puntos[0])
            elif k == n - 1:
                t = v.resta(puntos[k], puntos[k - 1])
            else:
                t = v.resta(puntos[k + 1], puntos[k - 1])
            t = v.unitario(t) or (0.0, 1.0, 0.0)
            # Marco que se transporta a lo largo de la rama (sin giros bruscos).
            u = v.unitario(v.tangente(normal_ref, t)) or v.perpendicular(t)
            normal_ref = u
            w = v.cruz(t, u)
            r = radios_rama[k]
            # Las puntas son verdes y la madera, marrón.
            mezcla = min(1.0, (n - 1 - k) / 40.0)
            color = _mezclar(joven, base_color, mezcla)
            if k == n - 1:
                anillos.append([malla.vertice(puntos[k], color)])
                continue
            anillo = []
            for j in range(lados):
                a = 2.0 * math.pi * j / lados
                desplazado = v.suma(v.escala(u, math.cos(a) * r), v.escala(w, math.sin(a) * r))
                anillo.append(malla.vertice(v.suma(puntos[k], desplazado), color))
            anillos.append(anillo)
        for k in range(n - 1):
            a, b = anillos[k], anillos[k + 1]
            for j in range(lados):
                j2 = (j + 1) % lados
                if len(b) == 1:
                    malla.cara(a[j], a[j2], b[0])
                else:
                    malla.cara(a[j], a[j2], b[j2], b[j])
    return malla


# -------------------------------------------------------------------- hojas
def _perfil_mezclado(a, b, t):
    """Perfil intermedio entre dos perfiles (t = 0 -> a, t = 1 -> b)."""
    def ancho(perfil, y):
        for (y0, w0), (y1, w1) in zip(perfil, perfil[1:]):
            if y0 <= y <= y1:
                k = (y - y0) / (y1 - y0) if y1 > y0 else 0.0
                return w0 + (w1 - w0) * k
        return 0.0
    ys = sorted(set(round(y, 3) for y, _ in a) | set(round(y, 3) for y, _ in b))
    return [(y, ancho(a, y) * (1.0 - t) + ancho(b, y) * t) for y in ys]


# Matices de verde de una hiedra: oscuro, medio, amarillento y azulado.
_VERDES = [(0.07, 0.20, 0.05), (0.11, 0.28, 0.07), (0.20, 0.31, 0.07), (0.06, 0.22, 0.11)]
_VERDE_JOVEN = (0.24, 0.40, 0.11)


def _verde(tono):
    tono = max(0.0, min(0.999, tono)) * (len(_VERDES) - 1)
    i = int(tono)
    return _mezclar(_VERDES[i], _VERDES[i + 1], tono - i)


def malla_hojas(hojas, curvatura: float = 0.22, plegado: float = 0.38,
                semilla: int = 1, forma: str = "hiedra") -> Malla:
    """Una lámina por hoja, plegada por el nervio, curvada y un poco asimétrica.

    Cada hoja mezcla el perfil lobulado con el acorazonado según su
    ``lobulado`` y tiene su propio matiz de verde.
    """
    rng = random.Random(semilla * 97 + 3)
    perfil_base = PERFILES_HOJA.get(forma, PERFIL_HOJA)
    entero = PERFILES_HOJA["corazon"]
    malla = Malla()
    for hoja in hojas:
        f = hoja.adelante
        z = hoja.normal
        x = v.cruz(f, z)
        s = hoja.tamano
        lobulado = getattr(hoja, "lobulado", 1.0)
        perfil = perfil_base if forma != "hiedra" else _perfil_mezclado(entero, perfil_base, lobulado)
        color = _verde(getattr(hoja, "tono", 0.5))
        color = _mezclar(_VERDE_JOVEN, color, hoja.edad)
        color = _variar(color, rng, 0.12)
        curva = curvatura * (0.5 + 1.0 * rng.random())
        pliegue = plegado * (0.6 + 0.8 * rng.random())
        asimetria = rng.uniform(-0.1, 0.1)
        # La punta se tuerce un poco hacia un lado.
        torsion = rng.uniform(-0.12, 0.12)

        def colocar(cx, cy, cz):
            cx += torsion * cy * cy
            return v.suma(hoja.base, v.suma(v.escala(x, cx * s),
                                            v.suma(v.escala(f, cy * s), v.escala(z, cz * s))))

        filas = []
        for y, ancho in perfil:
            caida = -curva * y * y
            if ancho == 0.0:
                filas.append([malla.vertice(colocar(0.0, y, caida), color)])
            else:
                ancho *= 1.0 + rng.uniform(-0.06, 0.06)
                izq, der = ancho * (1.0 + asimetria), ancho * (1.0 - asimetria)
                oscuro = _mezclar(color, (0.0, 0.0, 0.0), 0.15)
                claro = _mezclar(color, (0.55, 0.65, 0.35), 0.18)
                fila = []
                # Sección en forma de cuenco suave (no una V): el nervio
                # central queda arriba y los bordes caen poco a poco.
                for r in (-1.0, -0.5, 0.0, 0.5, 1.0):
                    w = izq if r < 0 else der
                    cx = r * w
                    cz = caida - pliegue * w * (0.35 * abs(r) + 0.65 * r * r)
                    c = claro if r == 0.0 else (oscuro if abs(r) == 1.0 else color)
                    fila.append(malla.vertice(colocar(cx, y, cz), c))
                filas.append(fila)
        for a, b in zip(filas, filas[1:]):
            if len(a) == 1 and len(b) > 1:
                for j in range(len(b) - 1):
                    malla.cara(a[0], b[j + 1], b[j])
            elif len(a) > 1 and len(b) > 1:
                for j in range(len(a) - 1):
                    malla.cara(a[j], a[j + 1], b[j + 1], b[j])
            elif len(a) > 1 and len(b) == 1:
                for j in range(len(a) - 1):
                    malla.cara(a[j], a[j + 1], b[0])
    return malla


def malla_peciolos(hojas, grosor: float = 0.022) -> Malla:
    """Rabillos finos y algo arqueados que unen cada hoja con su tallo."""
    malla = Malla()
    for hoja in hojas:
        eje = v.resta(hoja.base, hoja.tallo)
        largo = v.largo(eje)
        lado = v.unitario(v.cruz(eje, hoja.normal))
        if lado is None or largo < v.EPS:
            continue
        color = _mezclar((0.30, 0.22, 0.12), (0.30, 0.40, 0.13), 1.0 - hoja.edad * 0.6)
        ancho = v.escala(lado, grosor * hoja.tamano)
        fino = v.escala(ancho, 0.6)
        # Punto medio levantado: el rabillo forma un arco, no una línea recta.
        medio = v.suma(v.suma(hoja.tallo, v.escala(eje, 0.5)), v.escala(hoja.normal, largo * 0.18))
        a = malla.vertice(v.resta(hoja.tallo, ancho), color)
        b = malla.vertice(v.suma(hoja.tallo, ancho), color)
        c = malla.vertice(v.suma(medio, fino), color)
        d = malla.vertice(v.resta(medio, fino), color)
        e = malla.vertice(v.suma(hoja.base, fino), color)
        g = malla.vertice(v.resta(hoja.base, fino), color)
        malla.cara(a, b, c, d)
        malla.cara(d, c, e, g)
    return malla


# --------------------------------------------------------------- utilidades
def _mezclar(a: Vector, b: Vector, t: float) -> Vector:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _variar(c: Vector, rng, cantidad: float) -> Vector:
    k = 1.0 + cantidad * (rng.random() * 2.0 - 1.0)
    tono = cantidad * 0.5 * (rng.random() * 2.0 - 1.0)
    return (max(0.0, min(1.0, c[0] * k + tono * 0.3)),
            max(0.0, min(1.0, c[1] * k)),
            max(0.0, min(1.0, c[2] * k - tono * 0.2)))
