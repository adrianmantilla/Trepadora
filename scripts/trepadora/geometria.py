"""Construcción de mallas (vértices y caras) en Python puro.

Las funciones devuelven listas sencillas para que Maya (``MFnMesh.create``)
u otro programa puedan crear la malla:

* ``vertices``: lista de (x, y, z)
* ``conteos``: número de vértices de cada cara
* ``indices``: índices de vértices de todas las caras, seguidos
* ``colores``: un color (r, g, b) por vértice
* ``uvs``: coordenadas de textura (u, v)
* ``uv_indices``: un índice de ``uvs`` por cada índice de ``indices``

Las UVs de las hojas van en coordenadas de la propia hoja (el nervio central
en u = 0,5), así que todas las hojas de una forma comparten textura. Las de
los tallos dan una vuelta de textura alrededor del tubo y avanzan a lo largo
de la rama, para una corteza que se repite.
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
    "redonda": [
        (0.00, 0.00), (0.05, 0.20), (0.16, 0.38), (0.32, 0.47), (0.50, 0.48), (0.68, 0.42),
        (0.84, 0.29), (0.95, 0.13), (1.00, 0.00),
    ],
}
PERFIL_HOJA = PERFILES_HOJA["hiedra"]
FORMAS_HOJA = tuple(PERFILES_HOJA)

# Tipos de tallo. «madera» es el color de lo viejo y «joven» el de las puntas
# (que se ven de ese color a lo largo de «verde» puntos); «grosor» multiplica
# el grosor de los tallos; «corteza» arruga el tubo con surcos a lo largo,
# como la madera vieja; «rabillo» son los colores del rabillo de una hoja
# vieja y de una nueva.
TIPOS_TALLO = {
    "lenoso": dict(madera=(0.27, 0.19, 0.12), joven=(0.33, 0.30, 0.15), verde=40.0,
                   lados=6, grosor=1.0, corteza=0.0,
                   rabillo=((0.30, 0.22, 0.12), (0.30, 0.40, 0.13))),
    "nudoso": dict(madera=(0.21, 0.15, 0.10), joven=(0.31, 0.28, 0.14), verde=25.0,
                   lados=8, grosor=1.3, corteza=0.22,
                   rabillo=((0.28, 0.20, 0.11), (0.30, 0.38, 0.13))),
    "verde": dict(madera=(0.17, 0.26, 0.09), joven=(0.30, 0.42, 0.15), verde=80.0,
                  lados=5, grosor=0.6, corteza=0.0,
                  rabillo=((0.20, 0.30, 0.10), (0.32, 0.44, 0.15))),
    "rojizo": dict(madera=(0.28, 0.12, 0.08), joven=(0.45, 0.20, 0.13), verde=60.0,
                   lados=6, grosor=0.8, corteza=0.0,
                   rabillo=((0.32, 0.13, 0.09), (0.46, 0.22, 0.13))),
}


class Malla:
    """Vértices, caras, colores y UVs.

    Hay dos maneras de dar las UVs: una por vértice (``vertice(p, color, uv)``
    y ``cara(*ids)``), o aparte con ``uv()`` y ``cara(*ids, uvs=...)`` cuando
    un vértice necesita más de una (la costura de un tubo). No se mezclan en
    la misma malla.
    """

    def __init__(self):
        self.vertices: List[Vector] = []
        self.conteos: List[int] = []
        self.indices: List[int] = []
        self.colores: List[Vector] = []
        self.uvs: List[Tuple[float, float]] = []
        self.uv_indices: List[int] = []

    def vertice(self, p: Vector, color: Vector, uv: Tuple[float, float] = None) -> int:
        self.vertices.append(p)
        self.colores.append(color)
        if uv is not None:
            self.uvs.append(uv)
        return len(self.vertices) - 1

    def uv(self, u: float, v: float) -> int:
        self.uvs.append((u, v))
        return len(self.uvs) - 1

    def cara(self, *ids: int, uvs: List[int] = None) -> None:
        self.conteos.append(len(ids))
        self.indices.extend(ids)
        self.uv_indices.extend(ids if uvs is None else uvs)


# ------------------------------------------------------------------- tallos
def malla_tallos(crecimiento, radios: List[List[float]], lados: int = None,
                 semilla: int = 1, tipo: str = "lenoso") -> Malla:
    """Un tubo por rama, con el radio de cada punto, cerrado en punta.

    ``tipo`` es uno de TIPOS_TALLO; ``lados``, si se da, manda sobre el del tipo.
    """
    datos = TIPOS_TALLO.get(tipo, TIPOS_TALLO["lenoso"])
    lados = lados or datos["lados"]
    rng = random.Random(semilla * 31 + 5)
    rng_corteza = random.Random(semilla * 37 + 2)
    malla = Malla()
    for rama, radios_rama in zip(crecimiento.ramas, radios):
        puntos = rama.puntos
        n = len(puntos)
        if n < 2:
            continue
        base_color = _variar(datos["madera"], rng, 0.15)
        joven = datos["joven"]
        surcos = _surcos(rng_corteza, lados, datos["corteza"])
        normal_ref = rama.normales[0]
        anillos, anillos_uv = [], []
        # La textura da una vuelta al tubo (u) y avanza con la rama (v) al
        # mismo ritmo que la vuelta, para que no se estire. En las puntas, muy
        # finas, no avanza más deprisa que en un tallo de un tercio del grueso.
        r_min = 0.3 * max(radios_rama[:n])
        recorrido = 0.0
        for k in range(n):
            if k > 0:
                r_medio = max(r_min, 0.5 * (radios_rama[k - 1] + radios_rama[k]), v.EPS)
                recorrido += v.largo(v.resta(puntos[k], puntos[k - 1])) / (2.0 * math.pi * r_medio)
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
            mezcla = min(1.0, (n - 1 - k) / datos["verde"])
            color = _mezclar(joven, base_color, mezcla)
            if k == n - 1:
                anillos.append([malla.vertice(puntos[k], color)])
                anillos_uv.append([malla.uv((j + 0.5) / lados, recorrido) for j in range(lados)])
                continue
            anillo = []
            # La corteza se arruga más en la madera vieja que en las puntas.
            arrugas = _arrugas(rng_corteza, surcos, datos["corteza"] * mezcla)
            for j in range(lados):
                a = 2.0 * math.pi * j / lados
                rj = r * arrugas[j]
                desplazado = v.suma(v.escala(u, math.cos(a) * rj), v.escala(w, math.sin(a) * rj))
                anillo.append(malla.vertice(v.suma(puntos[k], desplazado), color))
            anillos.append(anillo)
            # Un lado más en las UVs: la costura repite el primer vértice en u = 1.
            anillos_uv.append([malla.uv(j / lados, recorrido) for j in range(lados + 1)])
        for k in range(n - 1):
            a, b = anillos[k], anillos[k + 1]
            ua, ub = anillos_uv[k], anillos_uv[k + 1]
            for j in range(lados):
                j2 = (j + 1) % lados
                if len(b) == 1:
                    malla.cara(a[j], a[j2], b[0], uvs=(ua[j], ua[j + 1], ub[j]))
                else:
                    malla.cara(a[j], a[j2], b[j2], b[j], uvs=(ua[j], ua[j + 1], ub[j + 1], ub[j]))
    return malla


# ------------------------------------------------------------------- raíces
# Color de las raíces adhesivas: un pardo más claro que la madera del tallo.
_RAIZ = (0.36, 0.28, 0.19)
# Puntos del final de cada rama sin raíces: lo joven aún no se ha agarrado.
_RAICES_SIN_PUNTA = 6
# Probabilidad de un grupo de raíces en cada punto pegado, con «Raíces adhesivas» a 1
# (a 0,5, la mitad): un grupo cada dos o tres puntos, como una franja a los lados.
_RAICES_PROB = 0.7


def anadir_raices(malla: Malla, crecimiento, radios: List[List[float]], cantidad: float,
                  semilla: int = 1, tipo: str = "lenoso") -> int:
    """Añade a ``malla`` (la de los tallos) raicillas que agarran el tallo a la pared.

    Salen en grupos de dos a cuatro por los lados del tallo, allí donde va
    pegado a una superficie (no en lo que cuelga ni en las puntas), y llegan
    a la pared un poco más allá, algo hacia abajo. Cada una es un tubo fino
    de tres lados y dos tramos, arqueado, con la textura de la corteza.
    ``cantidad`` va de 0 (ninguna) a 1. Devuelve cuántas se añadieron.
    """
    if cantidad <= 0.0:
        return 0
    rng = random.Random(semilla * 53 + 11)
    madera = TIPOS_TALLO.get(tipo, TIPOS_TALLO["lenoso"])["madera"]
    paso = crecimiento.p.longitud_paso
    hechas = 0
    for rama, radios_rama in zip(crecimiento.ramas, radios):
        if rama.colgante:
            continue
        puntos = rama.puntos
        for k in range(1, len(puntos) - _RAICES_SIN_PUNTA):
            if rng.random() >= cantidad * _RAICES_PROB:
                continue
            p, r = puntos[k], radios_rama[k]
            cercano, normal = crecimiento.cercano(p)
            if v.distancia(p, cercano) > r + 0.25 * paso:
                continue        # aquí el tallo no toca la pared
            adelante = v.unitario(v.tangente(v.resta(puntos[k + 1], puntos[k - 1]), normal))
            if adelante is None:
                continue
            lado = v.cruz(normal, adelante)
            abajo = v.tangente(v.ABAJO, normal)
            color = _variar(_mezclar(madera, _RAIZ, 0.6), rng, 0.12)
            for _ in range(rng.randint(2, 4)):
                signo = 1.0 if rng.random() < 0.5 else -1.0
                # Sale del costado del tallo, del lado que da a la pared...
                salida = v.unitario(v.suma(v.escala(lado, signo), v.escala(normal, -0.4)))
                inicio = v.suma(p, v.escala(salida, r * 0.85))
                # ...y llega a la pared algo apartada del tallo y más abajo.
                fin = v.suma(cercano, v.escala(lado, signo * r * rng.uniform(1.6, 3.4)))
                fin = v.suma(fin, v.escala(adelante, r * rng.uniform(-1.0, 1.0)))
                fin = v.suma(fin, v.escala(abajo, r * rng.uniform(0.0, 1.2)))
                # Junto a una arista la pared se acaba: la raíz se agarra donde
                # siga habiendo superficie, o no sale si queda lejos del tallo.
                apoyo, normal_apoyo = crecimiento.cercano(fin)
                if v.distancia(apoyo, cercano) > 4.0 * r:
                    continue
                fin = v.suma(apoyo, v.escala(normal_apoyo, 0.02 * r))
                medio = v.escala(v.suma(inicio, fin), 0.5)
                medio = v.suma(medio, v.escala(normal, v.distancia(inicio, fin) * 0.25))
                _tubo_fino(malla, (inicio, medio, fin), r * rng.uniform(0.09, 0.14), color)
                hechas += 1
    return hechas


def _tubo_fino(malla: Malla, camino, radio: float, color: Vector, lados: int = 3) -> None:
    """Tubo de ``lados`` lados por los puntos de ``camino``, que adelgaza hacia el final."""
    n = len(camino)
    anillos, anillos_uv, recorrido = [], [], 0.0
    referencia = None
    for k, punto in enumerate(camino):
        if k > 0:
            recorrido += v.distancia(punto, camino[k - 1]) / (2.0 * math.pi * max(radio, v.EPS))
        t = v.unitario(v.resta(camino[min(k + 1, n - 1)], camino[max(k - 1, 0)])) or v.ARRIBA
        u = (v.unitario(v.tangente(referencia, t)) if referencia else None) or v.perpendicular(t)
        referencia = u
        w = v.cruz(t, u)
        rk = radio * (1.0 - 0.45 * k / (n - 1))
        anillo = []
        for j in range(lados):
            a = 2.0 * math.pi * j / lados
            desplazado = v.suma(v.escala(u, math.cos(a) * rk), v.escala(w, math.sin(a) * rk))
            anillo.append(malla.vertice(v.suma(punto, desplazado), color))
        anillos.append(anillo)
        anillos_uv.append([malla.uv(j / lados, recorrido) for j in range(lados + 1)])
    for k in range(n - 1):
        a, b = anillos[k], anillos[k + 1]
        ua, ub = anillos_uv[k], anillos_uv[k + 1]
        for j in range(lados):
            j2 = (j + 1) % lados
            malla.cara(a[j], a[j2], b[j2], b[j], uvs=(ua[j], ua[j + 1], ub[j + 1], ub[j]))


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
_VERDES = [(0.07, 0.20, 0.05), (0.11, 0.28, 0.07), (0.22, 0.31, 0.10), (0.05, 0.21, 0.12)]
# Claros y brotes de un verde oliva, no lima; lo viejo, oscuro pero no negro.
_VERDE_JOVEN = (0.27, 0.37, 0.14)
_VERDE_CLARO = (0.36, 0.41, 0.17)
_VERDE_VIEJO = (0.035, 0.09, 0.05)
_BRONCE = (0.24, 0.085, 0.07)


def _verde(tono):
    tono = max(0.0, min(0.999, tono)) * (len(_VERDES) - 1)
    i = int(tono)
    return _mezclar(_VERDES[i], _VERDES[i + 1], tono - i)


def color_hoja(hoja, rng) -> Vector:
    """Color de una hoja según su tono, edad, claridad y tinte, con algo de azar."""
    color = _verde(getattr(hoja, "tono", 0.5))
    # Los brotes aclaran, pero sin salir como motas de otro color.
    color = _mezclar(_VERDE_JOVEN, color, 0.35 + 0.65 * hoja.edad)
    claridad = getattr(hoja, "claridad", 0.0)
    if claridad > 0.0:
        color = _mezclar(color, _VERDE_CLARO, 0.85 * claridad)
    else:
        color = _mezclar(color, _VERDE_VIEJO, -0.55 * claridad)
    color = _mezclar(color, _BRONCE, getattr(hoja, "tinte", 0.0))
    # La hiedra de verdad es un verde apagado: sin esto, en el espacio
    # lineal de Maya todas las hojas salen del mismo verde chillón.
    color = _apagar(color, _APAGADO)
    return _variar(color, rng, 0.12)


def _forma_al_azar(rng, curvatura, plegado):
    """Curva, pliegue, asimetría y torsión de una hoja."""
    curva = curvatura * (0.5 + 1.0 * rng.random())
    pliegue = plegado * (0.6 + 0.8 * rng.random())
    asimetria = rng.uniform(-0.1, 0.1)
    # La punta se tuerce un poco hacia un lado.
    torsion = rng.uniform(-0.12, 0.12)
    return curva, pliegue, asimetria, torsion


# Cuánto se aclara el nervio central y se oscurece el borde de cada hoja.
_NERVIO = ((0.55, 0.65, 0.35), 0.18)
_BORDE = ((0.0, 0.0, 0.0), 0.15)


def _ancho_maximo(forma: str) -> float:
    perfiles = [PERFILES_HOJA.get(forma, PERFIL_HOJA)]
    if forma == "hiedra":
        perfiles.append(PERFILES_HOJA["corazon"])   # la hiedra se mezcla con él
    return max(w for perfil in perfiles for _, w in perfil)


# Cuánto mide de lado el cuadrado de textura de cada forma de hoja, con la
# hoja de largo 1: cabe la hoja más ancha (con su azar y su asimetría) y un
# margen. Igual en u y en v, para que la textura no se estire.
ESCALA_UV = {f: max(1.1, 2.0 * _ancho_maximo(f) * 1.17 + 0.04) for f in PERFILES_HOJA}


def uv_hoja(cx: float, y: float, escala: float) -> Tuple[float, float]:
    """UV de un punto de la hoja (cx a lo ancho, y a lo largo de 0 a 1)."""
    return 0.5 + cx / escala, 0.5 + (y - 0.5) / escala


def _lamina(malla, perfil, forma, rng, color, colocar, escala_uv=None):
    """Añade a ``malla`` la lámina de una hoja.

    ``forma`` es (curva, pliegue, asimetría, torsión). ``colocar(cx, cy, cz)``
    pasa un punto de la hoja (cx a lo ancho, cy a lo largo de 0 a 1, cz hacia
    su cara) a la escena. ``escala_uv`` es la de ESCALA_UV para la forma de la
    hoja; las UVs son las de la hoja plana, antes de curvarla y torcerla.
    """
    curva, pliegue, asimetria, torsion = forma
    if escala_uv is None:
        escala_uv = max(1.1, 2.0 * max(w for _, w in perfil) * 1.17 + 0.04)
    filas = []
    for y, ancho in perfil:
        caida = -curva * y * y
        if ancho == 0.0:
            filas.append([malla.vertice(colocar(0.0 + torsion * y * y, y, caida), color,
                                        uv_hoja(0.0, y, escala_uv))])
        else:
            ancho *= 1.0 + rng.uniform(-0.06, 0.06)
            izq, der = ancho * (1.0 + asimetria), ancho * (1.0 - asimetria)
            oscuro = _mezclar(color, _BORDE[0], _BORDE[1])
            claro = _mezclar(color, _NERVIO[0], _NERVIO[1])
            fila = []
            # Sección en forma de cuenco suave (no una V): el nervio
            # central queda arriba y los bordes caen poco a poco.
            for r in (-1.0, -0.5, 0.0, 0.5, 1.0):
                w = izq if r < 0 else der
                cx = r * w
                cz = caida - pliegue * w * (0.35 * abs(r) + 0.65 * r * r)
                c = claro if r == 0.0 else (oscuro if abs(r) == 1.0 else color)
                fila.append(malla.vertice(colocar(cx + torsion * y * y, y, cz), c,
                                          uv_hoja(cx, y, escala_uv)))
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


def perfil_hoja(forma: str, lobulado: float = 1.0):
    """Perfil de la hoja: la de hiedra mezcla el lobulado con el acorazonado."""
    perfil = PERFILES_HOJA.get(forma, PERFIL_HOJA)
    if forma != "hiedra":
        return perfil
    return _perfil_mezclado(PERFILES_HOJA["corazon"], perfil, lobulado)


def malla_hojas(hojas, curvatura: float = 0.22, plegado: float = 0.38,
                semilla: int = 1, forma: str = "hiedra") -> Malla:
    """Una lámina por hoja, plegada por el nervio, curvada y un poco asimétrica.

    Cada hoja mezcla el perfil lobulado con el acorazonado según su
    ``lobulado`` y tiene su propio matiz de verde.
    """
    rng = random.Random(semilla * 97 + 3)
    malla = Malla()
    for hoja in hojas:
        f = hoja.adelante
        z = hoja.normal
        x = v.cruz(f, z)
        s = hoja.tamano
        perfil = perfil_hoja(forma, getattr(hoja, "lobulado", 1.0))
        color = color_hoja(hoja, rng)
        al_azar = _forma_al_azar(rng, curvatura, plegado)

        def colocar(cx, cy, cz, base=hoja.base, x=x, f=f, z=z, s=s):
            return v.suma(base, v.suma(v.escala(x, cx * s),
                                       v.suma(v.escala(f, cy * s), v.escala(z, cz * s))))

        _lamina(malla, perfil, al_azar, rng, color, colocar, ESCALA_UV.get(forma))
    return malla


def _surcos(rng, lados, corteza):
    """Por cada lado del tubo, si va en un surco (negativo) o en una cresta (positivo)."""
    if corteza <= 0.0:
        return None
    return [rng.uniform(-1.0, 1.0) for _ in range(lados)]


def _arrugas(rng, surcos, corteza):
    """Cuánto se estira el radio en cada lado de un anillo: surcos que siguen la rama."""
    if surcos is None or corteza <= 0.0:
        return [1.0] * (len(surcos) if surcos else 64)
    return [1.0 + corteza * (0.7 * s + 0.3 * rng.uniform(-1.0, 1.0)) for s in surcos]


def malla_peciolos(hojas, grosor: float = 0.022, tipo: str = "lenoso") -> Malla:
    """Rabillos finos y algo arqueados que unen cada hoja con su tallo."""
    viejo, nuevo = TIPOS_TALLO.get(tipo, TIPOS_TALLO["lenoso"])["rabillo"]
    malla = Malla()
    for hoja in hojas:
        eje = v.resta(hoja.base, hoja.tallo)
        largo = v.largo(eje)
        lado = v.unitario(v.cruz(eje, hoja.normal))
        if lado is None or largo < v.EPS:
            continue
        color = _mezclar(viejo, nuevo, 1.0 - hoja.edad * 0.6)
        ancho = v.escala(lado, grosor * hoja.tamano)
        fino = v.escala(ancho, 0.6)
        # Punto medio levantado: el rabillo forma un arco, no una línea recta.
        medio = v.suma(v.suma(hoja.tallo, v.escala(eje, 0.5)), v.escala(hoja.normal, largo * 0.18))
        # UVs: una tira de la textura de los tallos, de ancho a ancho y del tallo a la hoja.
        a = malla.vertice(v.resta(hoja.tallo, ancho), color, (0.0, 0.0))
        b = malla.vertice(v.suma(hoja.tallo, ancho), color, (1.0, 0.0))
        c = malla.vertice(v.suma(medio, fino), color, (1.0, 0.5))
        d = malla.vertice(v.resta(medio, fino), color, (0.0, 0.5))
        e = malla.vertice(v.suma(hoja.base, fino), color, (1.0, 1.0))
        g = malla.vertice(v.resta(hoja.base, fino), color, (0.0, 1.0))
        malla.cara(a, b, c, d)
        malla.cara(d, c, e, g)
    return malla


# --------------------------------------------------------------- utilidades
def _mezclar(a: Vector, b: Vector, t: float) -> Vector:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


_APAGADO = 0.3


def _apagar(c: Vector, cantidad: float) -> Vector:
    """Acerca el color a un gris de su misma luminosidad (le quita saturación)."""
    gris = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    return _mezclar(c, (gris, gris, gris), cantidad)


def _variar(c: Vector, rng, cantidad: float) -> Vector:
    k = 1.0 + cantidad * (rng.random() * 2.0 - 1.0)
    tono = cantidad * 0.5 * (rng.random() * 2.0 - 1.0)
    return (max(0.0, min(1.0, c[0] * k + tono * 0.3)),
            max(0.0, min(1.0, c[1] * k)),
            max(0.0, min(1.0, c[2] * k - tono * 0.2)))
