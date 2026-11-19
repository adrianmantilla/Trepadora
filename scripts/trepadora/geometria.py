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
        (0.00, 0.00), (0.06, 0.22), (0.16, 0.42), (0.26, 0.50), (0.36, 0.30),
        (0.46, 0.27), (0.58, 0.30), (0.72, 0.22), (0.86, 0.10), (1.00, 0.00),
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
        joven = (0.36, 0.42, 0.18)
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
            mezcla = min(1.0, (n - 1 - k) / 25.0)
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
def malla_hojas(hojas, curvatura: float = 0.18, plegado: float = 0.22,
                semilla: int = 1, forma: str = "hiedra") -> Malla:
    """Una lámina por hoja, ligeramente plegada por el nervio y curvada."""
    rng = random.Random(semilla * 97 + 3)
    perfil = PERFILES_HOJA.get(forma, PERFIL_HOJA)
    malla = Malla()
    for hoja in hojas:
        f = hoja.adelante
        z = hoja.normal
        x = v.cruz(f, z)
        s = hoja.tamano
        # Hojas jóvenes, verde claro; adultas, verde oscuro, con variación.
        color = _mezclar((0.42, 0.62, 0.16), (0.10, 0.30, 0.07), hoja.edad)
        color = _variar(color, rng, 0.18)
        curva = curvatura * (0.6 + 0.8 * rng.random())

        def colocar(cx, cy, cz):
            return v.suma(hoja.base, v.suma(v.escala(x, cx * s),
                                            v.suma(v.escala(f, cy * s), v.escala(z, cz * s))))

        filas = []
        for y, ancho in perfil:
            # La punta se curva hacia la pared y los bordes caen respecto al nervio.
            caida = -curva * y * y
            if ancho == 0.0:
                filas.append([malla.vertice(colocar(0.0, y, caida), color)])
            else:
                borde = caida - plegado * ancho
                oscuro = _mezclar(color, (0.0, 0.0, 0.0), 0.12)
                filas.append([
                    malla.vertice(colocar(-ancho, y, borde), oscuro),
                    malla.vertice(colocar(0.0, y, caida), color),
                    malla.vertice(colocar(ancho, y, borde), oscuro),
                ])
        for a, b in zip(filas, filas[1:]):
            if len(a) == 1 and len(b) == 3:
                malla.cara(a[0], b[1], b[0])
                malla.cara(a[0], b[2], b[1])
            elif len(a) == 3 and len(b) == 3:
                malla.cara(a[0], a[1], b[1], b[0])
                malla.cara(a[1], a[2], b[2], b[1])
            elif len(a) == 3 and len(b) == 1:
                malla.cara(a[0], a[1], b[0])
                malla.cara(a[1], a[2], b[0])
    return malla


def malla_peciolos(hojas, grosor: float = 0.04) -> Malla:
    """Rabillos finos que unen cada hoja con su tallo (una tira plana)."""
    malla = Malla()
    color = (0.25, 0.33, 0.12)
    for hoja in hojas:
        eje = v.resta(hoja.base, hoja.tallo)
        lado = v.unitario(v.cruz(eje, hoja.normal))
        if lado is None:
            continue
        ancho = v.escala(lado, grosor * hoja.tamano)
        a = malla.vertice(v.resta(hoja.tallo, ancho), color)
        b = malla.vertice(v.suma(hoja.tallo, ancho), color)
        c = malla.vertice(v.suma(hoja.base, ancho), color)
        d = malla.vertice(v.resta(hoja.base, ancho), color)
        malla.cara(a, b, c, d)
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
