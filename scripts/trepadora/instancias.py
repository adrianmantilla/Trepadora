"""Hojas como instancias (sin Maya).

En lugar de una malla con todas las hojas, unas pocas hojas modelo y, por cada
hoja de la planta, dónde va, cómo gira, su tamaño, qué modelo usa y su color.
Maya las dibuja con un instanciador: la escena pesa mucho menos y el visor va
más suelto con miles de hojas.

Los modelos combinan:

* la forma: varios grados de lobulado (en la hiedra) y unas pocas variantes de
  curva, pliegue y torsión;
* el color: los colores de todas las hojas se agrupan en unos pocos tonos
  (verde oscuro, claro, amarillento...), más uno propio para las hojas de un
  color muy distinto, como las bronce. El visor enseña el tono del grupo;
  para el render, cada hoja lleva además la proporción entre su color y el de
  su grupo, y Arnold multiplica una cosa por la otra.
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple

from . import geometria
from . import vectores as v

Vector = Tuple[float, float, float]


@dataclass
class Modelo:
    """Una hoja modelo de largo 1: x a lo ancho, y de la base a la punta, z hacia su cara."""
    malla: geometria.Malla
    lobulado: float
    grupo: int
    color: Vector


@dataclass
class HojasInstanciadas:
    modelos: List[Modelo] = field(default_factory=list)
    posiciones: List[Vector] = field(default_factory=list)
    # Giros en grados, en orden XYZ (el de Maya por defecto).
    giros: List[Vector] = field(default_factory=list)
    escalas: List[Vector] = field(default_factory=list)
    indices: List[int] = field(default_factory=list)
    # Color de cada hoja, en sRGB como los de geometria.
    colores: List[Vector] = field(default_factory=list)

    def __len__(self):
        return len(self.posiciones)


def euler_xyz(x: Vector, y: Vector, z: Vector) -> Vector:
    """Giros en grados (orden XYZ de Maya) que llevan los ejes X, Y, Z a ``x``, ``y``, ``z``.

    Maya usa vectores fila: la fila i de la matriz es el eje i ya girado, y
    con el orden XYZ la matriz es Rx·Ry·Rz.
    """
    m = (x, y, z)
    sy = max(-1.0, min(1.0, -m[0][2]))
    ry = math.asin(sy)
    if abs(math.cos(ry)) > 1e-6:
        rx = math.atan2(m[1][2], m[2][2])
        rz = math.atan2(m[0][1], m[0][0])
    else:
        # Bloqueo del cardán: el giro en Z se suma al de X.
        rx = math.atan2(-m[2][1], m[1][1])
        rz = 0.0
    return (math.degrees(rx), math.degrees(ry), math.degrees(rz))


def matriz_euler(giro: Vector):
    """Filas de la matriz de giro de unos ángulos XYZ en grados (la inversa de ``euler_xyz``)."""
    rx, ry, rz = (math.radians(a) for a in giro)
    cx, sx, cy, sy, cz, sz = (math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry),
                              math.cos(rz), math.sin(rz))
    return ((cy * cz, cy * sz, -sy),
            (-cx * sz + sx * sy * cz, cx * cz + sx * sy * sz, sx * cy),
            (sx * sz + cx * sy * cz, -sx * cz + cx * sy * sz, cx * cy))


def ejes_hoja(hoja):
    """Ejes de la hoja en la escena: a lo ancho, a lo largo y hacia su cara (ortonormales)."""
    z = v.unitario(hoja.normal) or (0.0, 0.0, 1.0)
    x = v.unitario(v.cruz(hoja.adelante, z)) or v.perpendicular(z)
    return x, v.cruz(z, x), z


def agrupar_colores(colores: List[Vector], grupos: int, vueltas: int = 10, aparte: int = 1,
                    umbral: float = 0.01):
    """Reparte los colores en ``grupos`` tonos (k-medias, sin azar).

    Los tonos salen ordenados de oscuro a claro. Después, hasta ``aparte``
    veces, el color que más se aleja de todos los tonos (más de ``umbral``,
    en distancia al cuadrado) abre un tono propio: así unas pocas hojas de
    otro color, como las bronce entre las verdes, no se pierden dentro de un
    verde. Devuelve el grupo de cada color y el color medio de cada grupo; los
    grupos vacíos se quitan.
    """
    if not colores:
        return [], []
    orden = sorted(range(len(colores)), key=lambda i: _luz(colores[i]))
    grupos = max(1, min(grupos, len(colores)))
    centros = [colores[orden[(2 * k + 1) * len(orden) // (2 * grupos)]] for k in range(grupos)]
    asignado, centros = _k_medias(colores, centros, vueltas)
    for _ in range(aparte):
        lejos = max(colores, key=lambda c: min(_distancia2(c, k) for k in centros))
        if min(_distancia2(lejos, k) for k in centros) <= umbral:
            break
        asignado, centros = _k_medias(colores, centros + [lejos], vueltas)
    usados = sorted(set(asignado))
    nuevo = {k: n for n, k in enumerate(usados)}
    return [nuevo[k] for k in asignado], [centros[k] for k in usados]


def _k_medias(colores, centros, vueltas):
    asignado = [0] * len(colores)
    for _ in range(vueltas):
        for i, c in enumerate(colores):
            asignado[i] = min(range(len(centros)), key=lambda k: _distancia2(c, centros[k]))
        sumas = [[0.0, 0.0, 0.0, 0] for _ in centros]
        for i, c in enumerate(colores):
            s = sumas[asignado[i]]
            s[0] += c[0]
            s[1] += c[1]
            s[2] += c[2]
            s[3] += 1
        centros = [(s[0] / s[3], s[1] / s[3], s[2] / s[3]) if s[3] else centros[k]
                   for k, s in enumerate(sumas)]
    return asignado, centros


def hojas_instanciadas(hojas, forma: str = "hiedra", semilla: int = 1,
                       curvatura: float = 0.22, plegado: float = 0.38,
                       niveles_lobulado: int = 4, variantes: int = 2,
                       tonos: int = 6, ancho_al_azar: float = 0.08) -> HojasInstanciadas:
    """Modelos y colocación de las hojas, para un instanciador.

    Usa el mismo color por hoja y las mismas formas que ``geometria.malla_hojas``.
    ``ancho_al_azar`` estira o encoge un poco cada hoja a lo ancho, para que
    las que comparten modelo no salgan iguales.
    """
    rng = random.Random(semilla * 97 + 3)
    colores = [geometria.color_hoja(h, rng) for h in hojas]
    grupo_de, centros = agrupar_colores(colores, tonos)

    lobulados = [1.0] if forma != "hiedra" or niveles_lobulado < 2 else [
        k / float(niveles_lobulado - 1) for k in range(niveles_lobulado)]
    rng_formas = random.Random(semilla * 131 + 7)
    formas = [(geometria._forma_al_azar(rng_formas, curvatura, plegado), rng_formas.random())
              for _ in range(max(1, variantes))]

    resultado = HojasInstanciadas()
    indice_modelo = {}
    for g, color in enumerate(centros):
        for lob in lobulados:
            for n, (al_azar, sub) in enumerate(formas):
                malla = geometria.Malla()
                geometria._lamina(malla, geometria.perfil_hoja(forma, lob), al_azar,
                                  random.Random(int(sub * 1e9)), color,
                                  lambda cx, cy, cz: (cx, cy, cz),
                                  geometria.ESCALA_UV.get(forma))
                indice_modelo[(g, lob, n)] = len(resultado.modelos)
                resultado.modelos.append(Modelo(malla, lob, g, color))

    rng_hojas = random.Random(semilla * 53 + 11)
    for hoja, color, g in zip(hojas, colores, grupo_de):
        lob = min(lobulados, key=lambda k: abs(k - getattr(hoja, "lobulado", 1.0)))
        n = rng_hojas.randrange(len(formas))
        x, y, z = ejes_hoja(hoja)
        s = hoja.tamano
        ancho = 1.0 + ancho_al_azar * (2.0 * rng_hojas.random() - 1.0)
        resultado.posiciones.append(hoja.base)
        resultado.giros.append(euler_xyz(x, y, z))
        resultado.escalas.append((s * ancho, s, s))
        resultado.indices.append(indice_modelo[(g, lob, n)])
        resultado.colores.append(color)
    return resultado


def proporcion(color: Vector, del_modelo: Vector, convertir=None) -> Vector:
    """Por cuánto hay que multiplicar el color del modelo para llegar al de la hoja.

    ``convertir`` pasa los colores al espacio en el que multiplica el render
    (en Maya, el lineal) antes de dividir.
    """
    if convertir is not None:
        color, del_modelo = convertir(color), convertir(del_modelo)
    return tuple(c / m if m > 1e-6 else 1.0 for c, m in zip(color, del_modelo))


def _luz(c: Vector) -> float:
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _distancia2(a: Vector, b: Vector) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
