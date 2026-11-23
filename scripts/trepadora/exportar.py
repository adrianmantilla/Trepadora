"""Exportar una planta a FBX (motores de juego) o a Alembic (otros programas).

Las hojas de una planta son instancias, y ni FBX ni Alembic las guardan bien.
Al exportar se hace una copia «horneada» con dos objetos limpios:

* ``tallos``: tallos y rabillos en una malla, con la corteza;
* ``hojas``: todas las hojas en una malla, con sus UVs y el color de cada hoja
  en los colores de vértice.

Se exporta la copia y se borra: la escena queda como estaba.

Para juegos se pueden exportar las hojas ligeras: cada hoja es una tarjeta
de seis vértices doblada por el nervio, y la silueta la pone la transparencia
del mapa de color (``<juego>_color.png``). Pesa unas doce veces menos.

Junto al archivo se copian las texturas de la resolución elegida, en la carpeta
``<nombre>_texturas``: los mapas de Trepadora y además un mapa de color
(``<juego>_color.jpg``) que ya lleva el tono medio de la planta, para los
programas que no multiplican el detalle por los colores de vértice (lo normal
al importar en Unity o Unreal). El material de cada objeto usa ese color y el
mapa de normales, que FBX sí guarda.

La primera parte no depende de Maya (se prueba sin él); lo de Maya va al final.
"""

import json
import os
import re
import shutil
import tempfile

from . import geometria, texturas, vectores

FORMATOS = ("fbx", "abc")
ATR_PLANTA = "trepadoraAjustes"
PREFIJO = "trepadora_exportar"


# ------------------------------------------------------------- matrices
# Matrices 4×4 como 16 números por filas, con vectores fila, como las de Maya
# (``cmds.xform(..., query=True, matrix=True)``): la traslación va al final.
IDENTIDAD = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)


def multiplicar(a, b):
    """``a·b``: primero se aplica ``a`` y después ``b``."""
    return tuple(sum(a[4 * i + k] * b[4 * k + j] for k in range(4))
                 for i in range(4) for j in range(4))


def matriz_instancia(posicion, giro, escala):
    """Escala, giro (grados, orden XYZ) y posición, como el instanciador de Maya."""
    from .instancias import matriz_euler

    filas = matriz_euler(giro)
    m = []
    for s, fila in zip(escala, filas):
        m.extend([s * fila[0], s * fila[1], s * fila[2], 0.0])
    m.extend([posicion[0], posicion[1], posicion[2], 1.0])
    return tuple(m)


def transformar(p, m):
    x, y, z = p
    return (x * m[0] + y * m[4] + z * m[8] + m[12],
            x * m[1] + y * m[5] + z * m[9] + m[13],
            x * m[2] + y * m[6] + z * m[10] + m[14])


# -------------------------------------------------------------- mallas
def anadir(destino, origen, matriz=None, color=None):
    """Añade ``origen`` a ``destino`` (las dos ``geometria.Malla``).

    ``matriz`` mueve los vértices; ``color`` multiplica sus colores. Las UVs
    van siempre aparte (``uv_indices``); una pieza sin UVs las tiene en 0,0.
    """
    base = len(destino.vertices)
    base_uv = len(destino.uvs)
    for p in origen.vertices:
        destino.vertices.append(transformar(p, matriz) if matriz else tuple(p))
    for c in origen.colores:
        destino.colores.append(tuple(a * b for a, b in zip(c, color)) if color else tuple(c))
    destino.conteos.extend(origen.conteos)
    destino.indices.extend(base + i for i in origen.indices)
    if origen.uvs and len(origen.uv_indices) == len(origen.indices):
        destino.uvs.extend(origen.uvs)
        destino.uv_indices.extend(base_uv + i for i in origen.uv_indices)
    else:
        destino.uvs.append((0.0, 0.0))
        destino.uv_indices.extend([base_uv] * len(origen.indices))
    return destino


def hornear_hojas(modelos, matrices_modelo, posiciones, giros, escalas, indices,
                  colores=None, matriz_instanciador=None):
    """Una malla con todas las hojas que dibuja un instanciador.

    Cada hoja es su modelo movido por la matriz propia del modelo, la de su
    partícula (escala, giro y posición) y la del instanciador en el mundo, en
    ese orden: así las hojas se mueven con la planta igual que los tallos.
    ``colores`` (el rgbPP) multiplica los del modelo, como hace Arnold.
    """
    malla = geometria.Malla()
    for i, (p, g, s) in enumerate(zip(posiciones, giros, escalas)):
        k = int(round(indices[i])) if indices else 0
        if not 0 <= k < len(modelos):
            continue
        m = multiplicar(matrices_modelo[k], matriz_instancia(p, g, s))
        if matriz_instanciador:
            m = multiplicar(m, matriz_instanciador)
        anadir(malla, modelos[k], m, colores[i] if colores else None)
    return malla


# ------------------------------------------------------------ hojas ligeras
# Cuánto se levantan los bordes de la tarjeta sobre el nervio (por cada unidad
# de semiancho): la hoja ligera se dobla en V como las de verdad.
PLIEGUE_TARJETA = 0.3
# Margen alrededor de la silueta en la tarjeta (en UV), para el borde suavizado.
MARGEN_TARJETA = 0.01


def _resolver3(m, b):
    """Solución de ``m·x = b`` (3×3), o None si ``m`` no tiene inversa."""
    (a, b_, c), (d, e, f), (g, h, i) = m
    det = a * (e * i - f * h) - b_ * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-12:
        return None
    inv = ((e * i - f * h, c * h - b_ * i, b_ * f - c * e),
           (f * g - d * i, a * i - c * g, c * d - a * f),
           (d * h - e * g, b_ * g - a * h, a * e - b_ * d))
    return [sum(inv[r][k] * b[k] for k in range(3)) / det for r in range(3)]


def plano_de_uv(puntos, uvs):
    """``(origen, eje_u, eje_v)``: la posición como función de la UV, ``p = o + u·eu + v·ev``.

    Se ajusta por mínimos cuadrados a los vértices de una hoja: es el plano en
    el que la textura se ve como en la hoja. None si las UVs no lo permiten.
    """
    s = [[0.0] * 3 for _ in range(3)]
    for u, w in uvs:
        fila = (1.0, u, w)
        for r in range(3):
            for c in range(3):
                s[r][c] += fila[r] * fila[c]
    ejes = []
    for e in range(3):
        b = [0.0, 0.0, 0.0]
        for p, (u, w) in zip(puntos, uvs):
            b[0] += p[e]
            b[1] += p[e] * u
            b[2] += p[e] * w
        x = _resolver3(s, b)
        if x is None:
            return None
        ejes.append(x)
    origen = tuple(x[0] for x in ejes)
    eje_u = tuple(x[1] for x in ejes)
    eje_v = tuple(x[2] for x in ejes)
    return origen, eje_u, eje_v


def tarjeta(puntos, uvs, colores=None, nervio=0.5):
    """La hoja ligera de una hoja: seis vértices, dos caras dobladas por el nervio.

    ``puntos`` y ``uvs`` son los de cada esquina de cara de la hoja (o de cada
    vértice); la tarjeta cubre su rectángulo de UV, con el nervio en
    ``u = nervio``, y lleva el color medio de ``colores``. None si no se puede.
    """
    plano = plano_de_uv(puntos, uvs)
    if plano is None:
        return None
    origen, eu, ev = plano
    m = MARGEN_TARJETA
    u0 = max(0.0, min(u for u, _ in uvs) - m)
    u1 = min(1.0, max(u for u, _ in uvs) + m)
    v0 = max(0.0, min(w for _, w in uvs) - m)
    v1 = min(1.0, max(w for _, w in uvs) + m)
    um = nervio if u0 < nervio < u1 else 0.5 * (u0 + u1)
    cara = vectores.cruz(eu, ev)
    cara = vectores.unitario(cara)
    if cara is None:
        return None
    color = color_medio(_con_colores(colores)) if colores else (0.5, 0.5, 0.5)
    malla = geometria.Malla()
    for w in (v0, v1):
        for u in (u0, um, u1):
            p = tuple(origen[e] + u * eu[e] + w * ev[e] for e in range(3))
            alto = PLIEGUE_TARJETA * abs(u - um) * vectores.largo(eu)
            p = tuple(p[e] + cara[e] * alto for e in range(3))
            malla.vertice(p, color)
            malla.uv(u, w)
    malla.cara(0, 1, 4, 3, uvs=(0, 1, 4, 3))
    malla.cara(1, 2, 5, 4, uvs=(1, 2, 5, 4))
    return malla


def _con_colores(colores):
    malla = geometria.Malla()
    malla.colores = list(colores)
    return malla


def esquinas(malla):
    """Puntos, UVs y colores de cada esquina de cara de ``malla`` (para ``tarjeta``)."""
    puntos = [malla.vertices[i] for i in malla.indices]
    if malla.uvs and len(malla.uv_indices) == len(malla.indices):
        uvs = [malla.uvs[i] for i in malla.uv_indices]
    elif malla.uvs and len(malla.uvs) == len(malla.vertices):
        uvs = [malla.uvs[i] for i in malla.indices]
    else:
        return None
    colores = [malla.colores[i] for i in malla.indices] if malla.colores else None
    return puntos, uvs, colores


def hojas_sueltas(malla):
    """Cada hoja de una malla de hojas (sus caras unidas), como una ``geometria.Malla``."""
    padre = list(range(len(malla.vertices)))

    def raiz(a):
        while padre[a] != a:
            padre[a] = padre[padre[a]]
            a = padre[a]
        return a

    inicio = 0
    caras = []
    for n in malla.conteos:
        ids = malla.indices[inicio:inicio + n]
        caras.append((inicio, n))
        for i in ids[1:]:
            ra, rb = raiz(ids[0]), raiz(i)
            if ra != rb:
                padre[rb] = ra
        inicio += n
    grupos = {}
    for inicio, n in caras:
        grupos.setdefault(raiz(malla.indices[inicio]), []).append((inicio, n))
    con_uv = malla.uvs and len(malla.uv_indices) == len(malla.indices)
    hojas = []
    for lista in grupos.values():
        hoja = geometria.Malla()
        nuevo = {}
        for inicio, n in lista:
            ids = []
            for i in malla.indices[inicio:inicio + n]:
                if i not in nuevo:
                    nuevo[i] = hoja.vertice(malla.vertices[i],
                                            malla.colores[i] if malla.colores else (0.5,) * 3)
                ids.append(nuevo[i])
            uvs = None
            if con_uv:
                uvs = [hoja.uv(*malla.uvs[j]) for j in malla.uv_indices[inicio:inicio + n]]
            hoja.cara(*ids, uvs=uvs)
        hojas.append(hoja)
    return hojas


def hojas_ligeras(hojas):
    """Una malla con la tarjeta de cada hoja de ``hojas`` (una lista de mallas)."""
    malla = geometria.Malla()
    for hoja in hojas:
        datos = esquinas(hoja)
        carta = tarjeta(*datos) if datos else None
        if carta is not None:
            anadir(malla, carta)
    return malla


# Cuánto más ancha que su perfil es la silueta de una hoja ligera: cada hoja
# varía algo de ancho y es un poco asimétrica (ver ``geometria._lamina``).
HOLGURA_SILUETA = 1.1


def mascara_alfa(forma, lado, holgura=HOLGURA_SILUETA):
    """Bytes (``lado``×``lado``, de arriba abajo) con la silueta de la hoja ``forma``.

    255 dentro de la hoja y 0 fuera, con el borde suavizado un píxel. Las UVs
    de las hojas son las de ``geometria.uv_hoja``.
    """
    perfil = geometria.PERFILES_HOJA[forma]
    escala = geometria.ESCALA_UV[forma]

    def ancho(y):
        for (y0, w0), (y1, w1) in zip(perfil, perfil[1:]):
            if y0 <= y <= y1:
                return w0 + (w1 - w0) * ((y - y0) / (y1 - y0) if y1 > y0 else 0.0)
        return 0.0

    filas = []
    for j in range(lado):
        v = 1.0 - (j + 0.5) / lado
        semiancho = holgura * ancho((v - 0.5) * escala + 0.5) / escala * lado   # en píxeles
        centro = 0.5 * lado
        fila = bytearray(lado)
        if semiancho > 0.0:
            a, b = centro - semiancho, centro + semiancho
            for i in range(max(0, int(a)), min(lado, int(b) + 1)):
                cubre = max(0.0, min(i + 1.0, b) - max(float(i), a))
                fila[i] = int(round(255 * min(1.0, cubre)))
        filas.append(bytes(fila))
    return b"".join(filas)


def color_medio(malla, defecto=(0.5, 0.5, 0.5)):
    """Media de los colores de vértice que tienen color."""
    validos = [c for c in malla.colores if min(c[:3]) >= 0.0]
    if not validos:
        return tuple(defecto)
    return tuple(sum(c[i] for c in validos) / len(validos) for i in range(3))


# ------------------------------------------------------- mapa de color
def _a_srgb(c):
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1.0 / 2.4) - 0.055


def tablas_color(tinte, lineal=True):
    """Tres tablas de 256 bytes: del gris del mapa de detalle al color de cada canal.

    Como en el material de Arnold, color = 2 × detalle × tinte, en lineal; el
    mapa resultante se guarda en sRGB, que es lo que esperan los programas para
    un mapa de color. Con ``lineal=False`` el tinte ya está en sRGB y no se
    convierte.
    """
    tablas = []
    for c in tinte[:3]:
        valores = []
        for g in range(256):
            x = 2.0 * (g / 255.0) * c
            x = _a_srgb(x) if lineal else max(0.0, min(1.0, x))
            valores.append(int(round(255.0 * x)))
        tablas.append(bytes(valores))
    return tablas


def tenir(gris, tablas):
    """Bytes RGB entrelazados a partir de los bytes de un gris (uno por píxel)."""
    salida = bytearray(3 * len(gris))
    for canal, tabla in enumerate(tablas):
        salida[canal::3] = gris.translate(tabla)
    return bytes(salida)


# ---------------------------------------------------------- archivos
def carpeta_texturas(ruta):
    """``escena/planta.fbx`` -> ``escena/planta_texturas``."""
    base, _ = os.path.splitext(ruta)
    return base + "_texturas"


def formato_de(ruta):
    extension = os.path.splitext(ruta)[1].lower().lstrip(".")
    return extension if extension in FORMATOS else None


def mapas_a_copiar(juegos, resolucion, base=None):
    """``[(origen, nombre de destino)]`` de los mapas de los ``juegos`` (los que haya)."""
    lista = []
    for juego in juegos:
        for mapa in texturas.mapas_de(juego):
            origen = texturas.ruta(juego, mapa, resolucion, base)
            if origen:
                lista.append((origen, texturas.archivo(juego, mapa)))
    return lista


def nombre_color(juego, alfa=False):
    """El mapa de color: JPEG, o PNG con la silueta en la transparencia (hojas ligeras)."""
    return juego + ("_color.png" if alfa else "_color.jpg")


def guardar_color(detalle, destino, tinte, lineal=True, forma=None):
    """Escribe el mapa de color a partir del de detalle. Devuelve True si pudo.

    Con ``forma`` (de hoja), el mapa lleva su silueta en el canal alfa y se
    guarda en PNG. Usa Qt (el de Maya) solo para leer y guardar la imagen.
    """
    try:
        try:
            from PySide6 import QtGui
        except ImportError:
            from PySide2 import QtGui
    except ImportError:
        return False
    img = QtGui.QImage(detalle)
    if img.isNull():
        return False
    img = img.convertToFormat(QtGui.QImage.Format.Format_Grayscale8)
    ancho, alto, fila = img.width(), img.height(), img.bytesPerLine()
    datos = bytes(img.constBits())[:fila * alto]
    if fila != ancho:
        datos = b"".join(datos[y * fila:y * fila + ancho] for y in range(alto))
    rgb = tenir(datos, tablas_color(tinte, lineal))
    if forma is not None and ancho == alto:
        rgba = bytearray(4 * ancho * alto)
        for canal in range(3):
            rgba[canal::4] = rgb[canal::3]
        rgba[3::4] = mascara_alfa(forma, ancho)
        nueva = QtGui.QImage(bytes(rgba), ancho, alto, 4 * ancho,
                             QtGui.QImage.Format.Format_RGBA8888).copy()
        return bool(nueva.save(destino, "PNG"))
    nueva = QtGui.QImage(rgb, ancho, alto, 3 * ancho, QtGui.QImage.Format.Format_RGB888).copy()
    # Calidad 91 o más: Qt guarda entonces el color sin submuestrear (4:4:4).
    return bool(nueva.save(destino, "JPG", 92))


# ------------------------------------------------------------------ Maya
def _cmds():
    from maya import cmds

    return cmds


def _es_planta(nodo):
    from .prototipo import GRUPO_PLANTA

    cmds = _cmds()
    return (cmds.attributeQuery(ATR_PLANTA, node=nodo, exists=True)
            or nodo.split("|")[-1].startswith(GRUPO_PLANTA))


def plantas_en_escena():
    """Los grupos de plantas de Trepadora que hay en la escena."""
    from .prototipo import GRUPO_PLANTA

    cmds = _cmds()
    return [n for n in cmds.ls(GRUPO_PLANTA + "*", long=True, type="transform") or []
            if _es_planta(n)]


def planta_de(nodo=None, sola=True):
    """El grupo de la planta de Trepadora de ``nodo`` o de la selección (o None).

    Sin nada seleccionado, con ``sola`` y una sola planta en la escena, esa.
    """
    cmds = _cmds()
    candidatos = [nodo] if nodo else cmds.ls(selection=True, long=True) or []
    for c in candidatos:
        actual = (cmds.ls(c, long=True) or [None])[0]
        while actual:
            if _es_planta(actual):
                return actual
            padres = cmds.listRelatives(actual, parent=True, fullPath=True)
            actual = padres[0] if padres else None
    if not candidatos and sola:
        plantas = plantas_en_escena()
        if len(plantas) == 1:
            return plantas[0]
    return None


def _hijo(padre, nombre, tipo=None):
    """Ruta completa del hijo de ``padre`` que se llama ``nombre`` (o ``nombre`` y un número)."""
    cmds = _cmds()
    patron = re.compile(re.escape(nombre) + r"\d*$")
    for h in cmds.listRelatives(padre, children=True, fullPath=True, type=tipo) or []:
        if patron.match(h.split("|")[-1]):
            return h
    return None


def _matriz(nodo, mundo=True):
    return tuple(_cmds().xform(nodo, query=True, matrix=True, worldSpace=mundo))


def leer_malla(transform, mundo=True):
    """La malla de ``transform`` como ``geometria.Malla`` (en el mundo o en el objeto)."""
    import maya.api.OpenMaya as om

    seleccion = om.MSelectionList()
    seleccion.add(transform)
    camino = seleccion.getDagPath(0)
    camino.extendToShape()
    fn = om.MFnMesh(camino)
    espacio = om.MSpace.kWorld if mundo else om.MSpace.kObject
    malla = geometria.Malla()
    malla.vertices = [(p.x, p.y, p.z) for p in fn.getPoints(espacio)]
    conteos, indices = fn.getVertices()
    malla.conteos, malla.indices = list(conteos), list(indices)
    try:
        colores = fn.getVertexColors()
        malla.colores = [(c.r, c.g, c.b) for c in colores]
    except RuntimeError:
        malla.colores = []
    if len(malla.colores) != len(malla.vertices):
        malla.colores = [(-1.0, -1.0, -1.0)] * len(malla.vertices)
    try:
        us, vs = fn.getUVs()
        _, uv_ids = fn.getAssignedUVs()
        if len(uv_ids) == len(malla.indices):
            malla.uvs = list(zip(us, vs))
            malla.uv_indices = list(uv_ids)
    except RuntimeError:
        pass
    return malla


def _arrays(forma, atributo):
    """Valores por partícula: los del estado inicial (los que guarda Trepadora) o los actuales.

    Leer los actuales de unas partículas fuera de su fotograma inicial hace que
    Maya avise de que hay que rebobinar; los iniciales se leen sin más.
    """
    cmds = _cmds()
    for nombre in (atributo + "0", atributo):
        if cmds.attributeQuery(nombre, node=forma, exists=True):
            valores = cmds.getAttr(forma + "." + nombre)
            if valores:
                return list(valores)
    return []


def instanciador_de(planta):
    """El instanciador de las hojas de la planta (o None)."""
    cmds = _cmds()
    for h in cmds.listRelatives(planta, children=True, fullPath=True) or []:
        if cmds.nodeType(h) == "instancer":
            return h
    # Por si alguna versión de Maya no lo da entre los hijos.
    for h in cmds.ls(type="instancer", long=True) or []:
        if h.startswith(planta + "|"):
            return h
    return None


def _ligera(malla):
    """La tarjeta de una hoja modelo (o la hoja tal cual si no se puede)."""
    datos = esquinas(malla)
    carta = tarjeta(*datos) if datos else None
    return carta if carta is not None else malla


def hojas_de(planta, ligeras=False):
    """Las hojas de la planta en una malla (de sus instancias o de su malla de hojas).

    Con ``ligeras``, cada hoja es una tarjeta (ver ``tarjeta``), salvo si las
    hojas no son de Trepadora (una hoja propia): sus UVs no siguen la silueta.
    """
    cmds = _cmds()
    malla_hojas = _hijo(planta, "trepadora_hojas", "transform")
    instanciador = instanciador_de(planta)
    if instanciador is None:
        if malla_hojas and cmds.listRelatives(malla_hojas, shapes=True, type="mesh"):
            malla = leer_malla(malla_hojas)
            if ligeras and _juego_de([malla_hojas]):
                malla = hojas_ligeras(hojas_sueltas(malla))
            return malla, [malla_hojas]
        return geometria.Malla(), []
    entradas = cmds.listConnections(instanciador + ".inputPoints", source=True,
                                    destination=False, shapes=True) or []
    forma = (cmds.ls(entradas[0], long=True) or [None])[0] if entradas else None
    indices_jerarquia = cmds.getAttr(instanciador + ".inputHierarchy", multiIndices=True) or []
    modelos = []
    for i in indices_jerarquia:
        origen = cmds.listConnections("{}.inputHierarchy[{}]".format(instanciador, i),
                                      source=True, destination=False) or []
        modelos.append((cmds.ls(origen[0], long=True) or [origen[0]])[0] if origen else None)
    if forma is None or not modelos:
        return geometria.Malla(), []
    mallas = [leer_malla(m, mundo=False) if m else geometria.Malla() for m in modelos]
    if ligeras and _juego_de([m for m in modelos if m]):
        mallas = [_ligera(m) for m in mallas]
    # La matriz propia de cada modelo, sin la de sus padres: la de la planta
    # ya llega con la del instanciador, que cuelga de ella.
    matrices = [_matriz(m, mundo=False) if m else IDENTIDAD for m in modelos]
    posiciones = _arrays(forma, "position")
    giros = _arrays(forma, "giroPP")
    escalas = _arrays(forma, "escalaPP")
    indices = _arrays(forma, "modeloPP")
    colores = _arrays(forma, "rgbPP")
    n = len(posiciones)
    giros = giros if len(giros) == n else [(0.0, 0.0, 0.0)] * n
    escalas = escalas if len(escalas) == n else [(1.0, 1.0, 1.0)] * n
    indices = indices if len(indices) == n else [0.0] * n
    colores = colores if len(colores) == n else None
    return (hornear_hojas(mallas, matrices, posiciones, giros, escalas, indices, colores,
                          _matriz(instanciador)),
            [m for m in modelos if m])


def tallos_de(planta):
    """Tallos y rabillos de la planta en una malla (en el mundo)."""
    malla = geometria.Malla()
    for nombre in ("trepadora_tallos", "trepadora_rabillos"):
        pieza = _hijo(planta, nombre, "transform")
        if pieza and _cmds().listRelatives(pieza, shapes=True, type="mesh"):
            anadir(malla, leer_malla(pieza))
    return malla


def _juego_de(transforms):
    """El juego de texturas de hoja de los materiales de esas mallas (o None)."""
    cmds = _cmds()
    for transform in transforms:
        formas = cmds.listRelatives(transform, shapes=True, fullPath=True) or []
        for forma in formas:
            for grupo in cmds.listConnections(forma, type="shadingEngine") or []:
                for material in cmds.listConnections(grupo + ".surfaceShader") or []:
                    for nodo in cmds.listConnections(material, source=True,
                                                     destination=False) or []:
                        if cmds.attributeQuery(texturas.ATRIBUTO, node=nodo, exists=True):
                            juego, _ = texturas.de_clave(
                                cmds.getAttr(nodo + "." + texturas.ATRIBUTO))
                            if juego.startswith("hoja_"):
                                return juego
    return None


def _crear(nombre, malla, padre):
    import maya.api.OpenMaya as om

    from .prototipo import _bajo, _poner_uvs, _suavizar

    cmds = _cmds()
    fn = om.MFnMesh()
    objeto = fn.create(om.MPointArray([om.MPoint(*p) for p in malla.vertices]),
                       malla.conteos, malla.indices)
    if malla.colores and min(min(c) for c in malla.colores) >= 0.0:
        fn.setVertexColors(om.MColorArray([om.MColor(tuple(c) + (1.0,)) for c in malla.colores]),
                           list(range(len(malla.vertices))))
    _poner_uvs(fn, malla)
    _suavizar(fn)
    ruta = om.MFnDagNode(objeto).fullPathName()
    ruta = _bajo(None, cmds.rename(ruta, nombre))
    return _bajo(padre, cmds.parent(ruta, padre)[0])


def _material(nombre, transform, color, carpeta, archivo_color, archivo_normal, alfa=False):
    """Lambert con el mapa de color y el de normales (rutas dentro de ``carpeta``).

    Con ``alfa``, la transparencia del mapa de color recorta la silueta de las
    hojas ligeras.
    """
    cmds = _cmds()
    creados = []
    material = cmds.shadingNode("lambert", asShader=True, name=nombre)
    creados.append(material)
    cmds.setAttr(material + ".color", *color[:3], type="double3")
    if archivo_color and os.path.isfile(os.path.join(carpeta, archivo_color)):
        imagen = cmds.shadingNode("file", asTexture=True, name=nombre + "_color")
        creados.append(imagen)
        cmds.setAttr(imagen + ".fileTextureName", os.path.join(carpeta, archivo_color),
                     type="string")
        cmds.connectAttr(imagen + ".outColor", material + ".color", force=True)
        if alfa:
            cmds.connectAttr(imagen + ".outTransparency", material + ".transparency",
                             force=True)
    if archivo_normal and os.path.isfile(os.path.join(carpeta, archivo_normal)):
        imagen = cmds.shadingNode("file", asTexture=True, name=nombre + "_normal")
        relieve = cmds.shadingNode("bump2d", asUtility=True, name=nombre + "_relieve")
        creados += [imagen, relieve]
        cmds.setAttr(imagen + ".fileTextureName", os.path.join(carpeta, archivo_normal),
                     type="string")
        from .prototipo import _espacio_raw

        _espacio_raw(imagen)
        cmds.connectAttr(imagen + ".outAlpha", relieve + ".bumpValue", force=True)
        cmds.setAttr(relieve + ".bumpInterp", 1)    # Tangent Space Normals
        cmds.connectAttr(relieve + ".outNormal", material + ".normalCamera", force=True)
    grupo = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=nombre + "SG")
    creados.append(grupo)
    cmds.connectAttr(material + ".outColor", grupo + ".surfaceShader", force=True)
    cmds.sets(transform, edit=True, forceElement=grupo)
    return creados


def _a_pantalla(color, lineal):
    """Color lineal de vértice a color de material (sRGB si la escena es lineal)."""
    return tuple(_a_srgb(c) for c in color) if lineal else tuple(color)


def nombre_de_grupo(ruta):
    """Nombre válido en Maya a partir del nombre del archivo (``mi planta.fbx`` -> ``mi_planta``)."""
    base = os.path.splitext(os.path.basename(ruta or ""))[0]
    limpio = re.sub(r"[^0-9A-Za-z_]", "_", base).strip("_")
    if not limpio:
        return "trepadora_planta"
    return limpio if not limpio[0].isdigit() else "planta_" + limpio


def hornear(planta, carpeta=None, resolucion=None, lineal=True, nombre=None, ligeras=False):
    """Crea la copia horneada de ``planta`` y, con ``carpeta``, copia allí las texturas.

    Con ``ligeras``, las hojas son tarjetas (para juegos) y su mapa de color
    lleva la silueta en la transparencia. Devuelve ``(grupo, creados,
    informe)``: el grupo nuevo, todos los nodos creados (para borrarlos) y un
    diccionario con lo que se hizo.
    """
    cmds = _cmds()
    resolucion = resolucion or texturas.resolucion_actual()
    hojas, modelos = hojas_de(planta, ligeras)
    tallos = tallos_de(planta)
    juego_hojas = _juego_de(modelos)
    ligeras = bool(ligeras and juego_hojas)
    grupo = cmds.group(empty=True, name=nombre or PREFIJO)
    grupo = (cmds.ls(grupo, long=True) or [grupo])[0]
    creados = [grupo]
    informe = {"hojas_vertices": len(hojas.vertices), "tallos_vertices": len(tallos.vertices),
               "juego_hojas": juego_hojas, "resolucion": resolucion, "texturas": [],
               "sin_color": [], "ligeras": ligeras}
    piezas = []
    if tallos.vertices:
        piezas.append(("tallos", tallos, "corteza"))
    if hojas.vertices:
        piezas.append(("hojas", hojas, juego_hojas))
    if carpeta:
        if not os.path.isdir(carpeta):
            os.makedirs(carpeta)
        juegos = [j for _n, _m, j in piezas if j]
        for origen, nombre in mapas_a_copiar(juegos, resolucion):
            shutil.copyfile(origen, os.path.join(carpeta, nombre))
            informe["texturas"].append(nombre)
    for nombre, malla, juego in piezas:
        transform = _crear(nombre, malla, grupo)
        tinte = color_medio(malla)
        archivo_color = archivo_normal = None
        # Con hojas ligeras, la silueta de la hoja va en el mapa de color.
        forma = juego[len("hoja_"):] if ligeras and juego and juego.startswith("hoja_") else None
        if forma not in geometria.PERFILES_HOJA:
            forma = None
        if carpeta and juego:
            detalle = os.path.join(carpeta, texturas.archivo(juego, "detalle"))
            archivo = nombre_color(juego, alfa=forma is not None)
            if os.path.isfile(detalle) and guardar_color(
                    detalle, os.path.join(carpeta, archivo), tinte, lineal, forma):
                archivo_color = archivo
                informe["texturas"].append(archivo_color)
            else:
                informe["sin_color"].append(juego)
            archivo_normal = texturas.archivo(juego, "normal")
        creados += _material("{}_{}_mat".format(PREFIJO, nombre), transform,
                             _a_pantalla(tinte, lineal), carpeta or "", archivo_color,
                             archivo_normal, alfa=forma is not None and archivo_color is not None)
    return grupo, creados, informe


def _cargar(plugin):
    cmds = _cmds()
    if not cmds.pluginInfo(plugin, query=True, loaded=True):
        cmds.loadPlugin(plugin, quiet=True)


def _exportar_fbx(grupo, ruta):
    from maya import mel

    _cargar("fbxmaya")
    cmds = _cmds()
    cmds.select(grupo, replace=True)
    for orden in ("FBXResetExport", "FBXExportSmoothingGroups -v true",
                  "FBXExportSmoothMesh -v false", "FBXExportEmbeddedTextures -v false",
                  "FBXExportShapes -v false",
                  "FBXExportSkins -v false", "FBXExportCameras -v false",
                  "FBXExportLights -v false"):
        mel.eval(orden)
    mel.eval('FBXExport -f "{}" -s'.format(ruta.replace("\\", "/")))


def _exportar_abc(grupo, ruta):
    _cargar("AbcExport")
    cmds = _cmds()
    cuadro = cmds.currentTime(query=True)
    trabajo = ("-frameRange {0} {0} -uvWrite -writeColorSets -writeFaceSets -writeUVSets "
               "-worldSpace -dataFormat ogawa -root {1} -file \"{2}\"").format(
                   cuadro, grupo, ruta.replace("\\", "/"))
    cmds.AbcExport(jobArg=trabajo)


def exportar(ruta, planta=None, resolucion=None, ligeras=False):
    """Exporta ``planta`` (o la seleccionada) a ``ruta`` (.fbx o .abc).

    Con ``ligeras``, las hojas van como tarjetas con transparencia (juegos).

    Devuelve el informe de ``hornear`` con ``ruta`` y ``carpeta`` añadidos.
    La escena queda como estaba (sin la copia ni sus materiales).
    """
    from .ajustes import Aviso
    from .i18n import t
    from .prototipo import _con_gestion_de_color

    cmds = _cmds()
    formato = formato_de(ruta)
    if formato is None:
        raise Aviso(t("exportar_formato", ruta=os.path.basename(ruta)))
    planta = planta_de(planta)
    if planta is None:
        raise Aviso(t("sin_planta_seleccionada"))
    seleccion = cmds.ls(selection=True, long=True) or []
    carpeta = carpeta_texturas(ruta)
    deshacer = cmds.undoInfo(query=True, stateWithoutFlush=True)
    if deshacer:
        cmds.undoInfo(stateWithoutFlush=False)
    creados = []
    temporal = None
    try:
        ruta = os.path.abspath(ruta)
        if not os.path.isdir(os.path.dirname(ruta)):
            os.makedirs(os.path.dirname(ruta))
        if os.path.isfile(ruta):
            os.remove(ruta)
        grupo, creados, informe = hornear(planta, carpeta, resolucion, _con_gestion_de_color(),
                                          nombre_de_grupo(ruta), ligeras)
        if not informe["hojas_vertices"] and not informe["tallos_vertices"]:
            raise Aviso(t("exportar_vacia"))
        if formato == "fbx":
            # Directo a su sitio: el FBX guarda las rutas de las texturas
            # también relativas a él.
            _exportar_fbx(grupo, ruta)
        else:
            try:
                _exportar_abc(grupo, ruta)
            except RuntimeError as error:
                informe["abc_error"] = str(error)
            if not os.path.isfile(ruta):
                # Por si esta versión de AbcExport no admite la ruta (espacios,
                # acentos): a una carpeta temporal y después a su sitio.
                temporal = tempfile.mkdtemp(prefix="trepadora_")
                provisional = os.path.join(temporal, "planta.abc")
                _exportar_abc(grupo, provisional)
                if os.path.isfile(provisional):
                    shutil.move(provisional, ruta)
                informe["abc_temporal"] = True
        if not os.path.isfile(ruta):
            raise Aviso(t("exportar_fallo", ruta=ruta))
        informe.update(ruta=ruta, carpeta=carpeta, formato=formato)
        with open(os.path.join(carpeta, "trepadora_exportar.json"), "w",
                  encoding="utf-8") as f:
            json.dump(informe, f, ensure_ascii=False, indent=2)
        return informe
    finally:
        restos = [n for n in creados if cmds.objExists(n)]
        if restos:
            cmds.delete(restos)
        if temporal:
            shutil.rmtree(temporal, ignore_errors=True)
        if deshacer:
            cmds.undoInfo(stateWithoutFlush=True)
        if seleccion:
            cmds.select([s for s in seleccion if cmds.objExists(s)], replace=True)
        else:
            cmds.select(clear=True)


def caja(malla):
    """Caja (mínimos, máximos) de los vértices, para comparar con la de Maya."""
    if not malla.vertices:
        return None
    return (tuple(min(p[i] for p in malla.vertices) for i in range(3)),
            tuple(max(p[i] for p in malla.vertices) for i in range(3)))


def distancia_cajas(a, b):
    """La mayor diferencia entre dos cajas, en unidades de la escena."""
    return max(abs(x - y) for pa, pb in zip(a, b) for x, y in zip(pa, pb))

