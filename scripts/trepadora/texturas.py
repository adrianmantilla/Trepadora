"""Texturas de hojas y tallos, a varias resoluciones.

Las imágenes vienen con el plugin, en ``texturas/<resolución>/`` (junto a
``scripts``), así que los estudiantes no necesitan Substance Painter. Cada
juego de texturas tiene varios mapas:

* ``detalle``: el color de la hoja o de la corteza *relativo*, alrededor de
  un gris medio (0,5 en lineal). El render lo multiplica por 2 y por el color
  de cada hoja (o de cada punto del tallo), así se conservan los tonos que
  ya da Trepadora y la textura pone nervios, bordes y grietas.
* ``normal``: relieve, en espacio tangente (convención de Maya, Y hacia arriba).
* ``rugosidad``: rugosidad del brillo (0 = espejo, 1 = mate).
* ``traslucidez`` (solo hojas): cuánta luz deja pasar cada punto (los nervios,
  menos).

La resolución se elige en la ventana («Resolución de texturas»). Cambiarla
cambia también las plantas que ya están en la escena: cada nodo de imagen de
Trepadora lleva el atributo ``trepadoraTextura`` con su juego y su mapa.
"""

import os

RESOLUCIONES = ("512", "1k", "2k", "4k")
POR_DEFECTO = "1k"
PIXELES = {"512": 512, "1k": 1024, "2k": 2048, "4k": 4096}

MAPAS = {
    "hoja": ("detalle", "normal", "rugosidad", "traslucidez"),
    "corteza": ("detalle", "normal", "rugosidad"),
}
# Todo en JPEG (de calidad alta y sin submuestreo del color): en PNG, un mapa
# de relieve de 4K pesa unos 18 MB y en JPEG unos 4, sin que se note en el render.
EXTENSION = {"detalle": ".jpg", "normal": ".jpg", "rugosidad": ".jpg", "traslucidez": ".jpg"}

ATRIBUTO = "trepadoraTextura"
OPCION = "trepadoraResolucionTexturas"


def juego_hoja(forma):
    return "hoja_" + forma


def juegos(formas):
    """Todos los juegos de texturas: uno por forma de hoja y la corteza."""
    return [juego_hoja(f) for f in formas] + ["corteza"]


def mapas_de(juego):
    return MAPAS["hoja" if juego.startswith("hoja_") else juego]


def carpeta(raiz=None):
    """``<plugin>/texturas``. ``TREPADORA_TEXTURAS`` manda sobre ella."""
    if os.environ.get("TREPADORA_TEXTURAS"):
        return os.environ["TREPADORA_TEXTURAS"]
    if raiz is None:
        raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(raiz, "texturas")


def archivo(juego, mapa):
    return juego + "_" + mapa + EXTENSION[mapa]


def ruta(juego, mapa, resolucion, base=None):
    """Ruta de la imagen. Si falta en esa resolución, la de la más parecida que haya.

    Devuelve None si no hay ninguna.
    """
    base = base or carpeta()
    nombre = archivo(juego, mapa)
    i = RESOLUCIONES.index(resolucion) if resolucion in RESOLUCIONES else 1
    # La pedida, después las más bajas y por último las más altas.
    orden = [RESOLUCIONES[i]] + list(reversed(RESOLUCIONES[:i])) + list(RESOLUCIONES[i + 1:])
    for res in orden:
        candidata = os.path.join(base, res, nombre)
        if os.path.isfile(candidata):
            return candidata
    return None


def disponibles(base=None):
    """Resoluciones que tienen alguna imagen."""
    base = base or carpeta()
    return [r for r in RESOLUCIONES
            if os.path.isdir(os.path.join(base, r)) and os.listdir(os.path.join(base, r))]


def resolucion_de(ruta_imagen):
    """La resolución de una ruta ``.../<res>/<archivo>`` (de Windows o de macOS), o None."""
    partes = (ruta_imagen or "").replace("\\", "/").split("/")
    if len(partes) >= 2 and partes[-2] in RESOLUCIONES:
        return partes[-2]
    return None


def clave(juego, mapa):
    return juego + "/" + mapa


def de_clave(valor):
    juego, _, mapa = (valor or "").partition("/")
    return juego, mapa


# ------------------------------------------------------------------ en Maya
def resolucion_actual():
    """La resolución elegida en la ventana (se recuerda entre sesiones de Maya)."""
    try:
        from maya import cmds

        if cmds.optionVar(exists=OPCION):
            valor = cmds.optionVar(query=OPCION)
            if valor in RESOLUCIONES:
                return valor
    except (ImportError, AttributeError, RuntimeError, TypeError):
        pass
    return POR_DEFECTO


def recordar_resolucion(resolucion):
    from maya import cmds

    cmds.optionVar(stringValue=(OPCION, resolucion))


TIPOS_DE_IMAGEN = (("file", "fileTextureName"), ("aiImage", "filename"))


def _arnold_cargado(cmds):
    try:
        return bool(cmds.pluginInfo("mtoa", query=True, loaded=True))
    except (AttributeError, RuntimeError):
        return False


def nodos_de_textura():
    """Nodos de imagen de Trepadora en la escena: ``[(nodo, atributo de ruta, juego, mapa)]``."""
    from maya import cmds

    resultado = []
    for tipo, atributo in TIPOS_DE_IMAGEN:
        # Sin Arnold cargado, Maya no conoce aiImage y ``ls(type="aiImage")``
        # avisa «Unknown object type» (y esto corre al abrir cada escena).
        if tipo.startswith("ai") and not _arnold_cargado(cmds):
            continue
        for nodo in cmds.ls(type=tipo) or []:
            if cmds.attributeQuery(ATRIBUTO, node=nodo, exists=True):
                juego, mapa = de_clave(cmds.getAttr(nodo + "." + ATRIBUTO))
                if juego and mapa:
                    resultado.append((nodo, atributo, juego, mapa))
    return resultado


def cambiar_resolucion(resolucion):
    """Pone todas las texturas de Trepadora de la escena a ``resolucion``.

    Devuelve cuántos nodos cambió. La resolución queda recordada para las
    plantas nuevas.
    """
    from maya import cmds

    recordar_resolucion(resolucion)
    cambiados = 0
    for nodo, atributo, juego, mapa in nodos_de_textura():
        nueva = ruta(juego, mapa, resolucion)
        if nueva and cmds.getAttr(nodo + "." + atributo) != nueva:
            cmds.setAttr(nodo + "." + atributo, nueva, type="string")
            cambiados += 1
    return cambiados


def marcar(nodo, juego, mapa):
    from maya import cmds

    if not cmds.attributeQuery(ATRIBUTO, node=nodo, exists=True):
        cmds.addAttr(nodo, longName=ATRIBUTO, dataType="string")
    cmds.setAttr(nodo + "." + ATRIBUTO, clave(juego, mapa), type="string")


def reparar_rutas():
    """Apunta a la carpeta de este ordenador las texturas que no se encuentran.

    Una escena hecha en otro ordenador (en casa con macOS y en clase con
    Windows, por ejemplo) guarda la ruta de la carpeta de Trepadora de allí.
    Cada imagen que no existe aquí se busca en la carpeta de este ordenador con
    la misma resolución que tenía. No entra en el historial de deshacer, para
    que Ctrl+Z no vuelva a dejar las rutas rotas. Devuelve cuántas cambió.
    """
    from maya import cmds

    deshacer = cmds.undoInfo(query=True, stateWithoutFlush=True)
    if deshacer:
        cmds.undoInfo(stateWithoutFlush=False)
    try:
        cambiados = 0
        for nodo, atributo, juego, mapa in nodos_de_textura():
            actual = cmds.getAttr(nodo + "." + atributo) or ""
            if actual and os.path.isfile(actual):
                continue
            nueva = ruta(juego, mapa, resolucion_de(actual) or resolucion_actual())
            if nueva and nueva != actual:
                cmds.setAttr(nodo + "." + atributo, nueva, type="string")
                cambiados += 1
        return cambiados
    finally:
        if deshacer:
            cmds.undoInfo(stateWithoutFlush=True)
