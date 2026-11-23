"""Prototipo de la fase 0: crecimiento con tallos y hojas, sin interfaz.

Uso en el Script Editor de Maya (pestaña Python)::

    import trepadora.prototipo as tp
    tp.escena_de_prueba()               # opcional: crea un muro y una caja y hace crecer
    tp.ejecutar(semilla=3)              # usa la seleccion actual
    tp.ejecutar(semilla=3, modo="curvas")   # solo lineas, muy rapido

Selecciona una o varias mallas y, si quieres, uno o varios localizadores para
marcar donde nace cada planta. Sin localizadores, la planta nace en la base del
primer objeto seleccionado.
"""

import math

from maya import cmds

from . import geometria
from .crecimiento import Crecimiento, Parametros
from .hojas import ParametrosHojas, colocar_hojas
from .i18n import t

GRUPO_VISTA_PREVIA = "trepadora_vista_previa_grp"
GRUPO_PLANTA = "trepadora_planta_grp"
# Colores de Maya por generacion: verde oscuro, verde, verde claro, amarillo verdoso.
_COLORES = [7, 23, 14, 26]
# Aclara los colores de hojas y rabillos una vez pasados a lineal (ver
# _a_lineal): con la vista ACES de Maya, la hiedra sale casi negra si no.
_BRILLO_HOJAS = 1.3


def _es_malla(nodo):
    if cmds.nodeType(nodo) == "mesh":
        return True
    formas = cmds.listRelatives(nodo, shapes=True, fullPath=True, noIntermediate=True) or []
    return any(cmds.nodeType(f) == "mesh" for f in formas)


def _es_localizador(nodo):
    formas = cmds.listRelatives(nodo, shapes=True, fullPath=True) or []
    return any(cmds.nodeType(f) == "locator" for f in formas)


def _parametros_para(mallas, ajustes, paso=None):
    """Escala las distancias al tamaño de la escena para que los valores por defecto funcionen.

    ``paso`` es la longitud de cada paso de crecimiento; si no se indica, es
    1/150 de la diagonal de los objetos seleccionados.
    """
    xmin, ymin, zmin, xmax, ymax, zmax = cmds.exactWorldBoundingBox(mallas)
    if paso is None:
        diagonal = math.sqrt((xmax - xmin) ** 2 + (ymax - ymin) ** 2 + (zmax - zmin) ** 2)
        paso = max(diagonal / 150.0, 1e-3)
    base = {
        "longitud_paso": paso,
        "distancia_adherencia": paso * 3.0,
        "separacion": paso * 0.05,
        "radio_espacio": paso * 2.0,
    }
    base.update(ajustes)
    return Parametros(**base), (xmin, ymin, zmin, xmax, ymax, zmax), paso


def ejecutar(semilla=1, pasos=None, modo="malla", hojas=None, grosor=1.0, paso=None, **ajustes):
    """Hace crecer la planta sobre la seleccion.

    * ``modo="malla"`` crea tallos con grosor y hojas; ``modo="curvas"`` solo lineas.
    * ``hojas``: diccionario con ajustes de ``ParametrosHojas`` (densidad, tamano...).
      El tamano es relativo: 1.0 = tamano por defecto para la escena.
    * ``grosor``: multiplica el grosor de los tallos.
    * ``paso``: longitud de cada paso en unidades de la escena (por defecto, automática).
    * Cualquier campo de ``Parametros`` se puede pasar por nombre, por ejemplo
      ``ejecutar(semilla=4, gravedad=1.0, prob_rama=0.08)``.

    Devuelve el grupo creado, o None si no se pudo crecer.
    """
    from .superficie_maya import SuperficieMaya

    seleccion = cmds.ls(selection=True, long=True) or []
    mallas = [n for n in seleccion if _es_malla(n)]
    localizadores = [n for n in seleccion if _es_localizador(n)]
    if not mallas:
        cmds.warning(t("falta_malla"))
        return None

    ajustes["semilla"] = semilla
    if pasos is not None:
        ajustes["pasos"] = pasos
    parametros, caja, paso_escena = _parametros_para(mallas, ajustes, paso)
    pasos = parametros.pasos
    superficie = SuperficieMaya(mallas)
    crecimiento = Crecimiento(superficie, parametros)

    if localizadores:
        for loc in localizadores:
            crecimiento.anadir_origen(cmds.xform(loc, query=True, worldSpace=True, translation=True))
    else:
        xmin, ymin, zmin, xmax, ymax, zmax = caja
        crecimiento.anadir_origen(((xmin + xmax) / 2.0, ymin, (zmin + zmax) / 2.0))

    cancelado = {"valor": False}

    def al_progresar(paso, total):
        if cmds.progressWindow(query=True, isCancelled=True):
            cancelado["valor"] = True
            return False
        if paso % 5 == 0 or paso == total:
            cmds.progressWindow(edit=True, progress=int(100 * paso / total),
                                status=t("progreso_estado", paso=paso, total=total))
        return True

    cmds.undoInfo(openChunk=True, chunkName="Trepadora")
    cmds.progressWindow(title=t("progreso_titulo"), progress=0, isInterruptable=True,
                        status=t("progreso_estado", paso=0, total=pasos))
    try:
        hechos = crecimiento.crecer(al_progresar=al_progresar)
        if modo == "curvas":
            grupo = crear_vista_previa(crecimiento.curvas())
        else:
            grupo = crear_planta(crecimiento, paso_escena, hojas or {}, grosor, semilla)
    finally:
        cmds.progressWindow(endProgress=True)
        cmds.undoInfo(closeChunk=True)

    if cancelado["valor"]:
        cmds.warning(t("cancelado"))
    if crecimiento.limite_alcanzado:
        cmds.warning(t("limite", limite=parametros.limite_puntos))
    print(t("resumen", ramas=len(crecimiento.ramas), puntos=crecimiento.total_puntos,
            pasos=hechos, semilla=semilla))
    cmds.select(grupo, replace=True)
    return grupo


def crear_vista_previa(curvas):
    """Crea una curva lineal por rama dentro de un grupo nuevo."""
    grupo = cmds.group(empty=True, name=GRUPO_VISTA_PREVIA)
    for generacion, puntos in curvas:
        curva = cmds.curve(degree=1, point=[tuple(map(float, p)) for p in puntos],
                           name="trepadora_rama_g{}_1".format(generacion))
        forma = cmds.listRelatives(curva, shapes=True, fullPath=True)[0]
        cmds.setAttr(forma + ".overrideEnabled", 1)
        cmds.setAttr(forma + ".overrideColor", _COLORES[min(generacion, len(_COLORES) - 1)])
        cmds.parent(curva, grupo)
    return grupo


def crear_planta(crecimiento, paso, ajustes_hojas, grosor=1.0, semilla=1):
    """Crea las mallas de tallos, hojas y rabillos dentro de un grupo nuevo."""
    radios = crecimiento.grosores(paso * 0.45 * grosor, paso * 0.06 * grosor)
    datos_hojas = dict(ajustes_hojas)
    datos_hojas["tamano"] = paso * 2.4 * datos_hojas.get("tamano", 1.0)
    datos_hojas.setdefault("semilla", semilla)
    hojas = colocar_hojas(crecimiento, ParametrosHojas(**datos_hojas))

    grupo = cmds.group(empty=True, name=GRUPO_PLANTA)
    piezas = [
        ("trepadora_tallos", geometria.malla_tallos(crecimiento, radios, semilla=semilla),
         (0.30, 0.21, 0.13)),
        ("trepadora_hojas", geometria.malla_hojas(hojas, semilla=semilla), (0.16, 0.38, 0.10)),
        ("trepadora_rabillos", geometria.malla_peciolos(hojas), (0.25, 0.33, 0.12)),
    ]
    for nombre, malla, color in piezas:
        if not malla.conteos:
            continue
        brillo = 1.0 if nombre == "trepadora_tallos" else _BRILLO_HOJAS
        transform = _crear_malla(nombre, malla, brillo)
        sombreado = _asignar_material(transform, nombre + "_mat", color, brillo)
        _material_arnold(transform, sombreado, nombre, color, brillo)
        cmds.parent(transform, grupo)
    print("Trepadora: {} hojas.".format(len(hojas)))
    return grupo


def _crear_malla(nombre, malla, brillo=1.0):
    import maya.api.OpenMaya as om

    fn = om.MFnMesh()
    puntos = om.MPointArray([om.MPoint(*p) for p in malla.vertices])
    objeto = fn.create(puntos, malla.conteos, malla.indices)
    lineal = _con_gestion_de_color()
    colores = om.MColorArray([om.MColor(_a_lineal(c, lineal, brillo) + (1.0,))
                              for c in malla.colores])
    fn.setVertexColors(colores, list(range(len(malla.vertices))))
    transform = om.MFnDagNode(objeto).fullPathName()
    transform = cmds.rename(transform, nombre)
    forma = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
    cmds.setAttr(forma + ".displayColors", 1)
    return transform


def _asignar_material(transform, nombre, color, brillo=1.0):
    if cmds.objExists(nombre):
        material = nombre
        grupo = cmds.listConnections(material + ".outColor", type="shadingEngine")[0]
    else:
        material = cmds.shadingNode("lambert", asShader=True, name=nombre)
        cmds.setAttr(material + ".color", *_a_lineal(color, _con_gestion_de_color(), brillo),
                     type="double3")
        grupo = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=nombre + "SG")
        cmds.connectAttr(material + ".outColor", grupo + ".surfaceShader", force=True)
    cmds.sets(transform, edit=True, forceElement=grupo)
    return grupo


# Ajustes del aiStandardSurface de cada pieza. Las hojas son finas: con
# thinWalled, «subsurface» es la luz que las atraviesa (a contraluz brillan).
_ARNOLD = {
    "trepadora_tallos": {"specular": 0.15, "specularRoughness": 0.6},
    "trepadora_hojas": {"specular": 0.45, "specularRoughness": 0.35, "thinWalled": 1,
                        "subsurface": 0.3},
    "trepadora_rabillos": {"specular": 0.25, "specularRoughness": 0.45},
}


def _arnold_cargado():
    try:
        return bool(cmds.pluginInfo("mtoa", query=True, loaded=True))
    except RuntimeError:
        return False


def _material_arnold(transform, grupo, nombre, color, brillo=1.0):
    """Material de Arnold para la pieza, si Arnold (MtoA) está cargado.

    El lambert del grupo de sombreado queda para el visor; Arnold usa en su
    lugar un aiStandardSurface (conectado a aiSurfaceShader) que toma el color
    de cada hoja de los colores de vértice. Sin esto, en el render todas las
    hojas saldrían del mismo verde.
    """
    if not _arnold_cargado():
        return None
    forma = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
    try:
        if cmds.attributeQuery("aiExportColors", node=forma, exists=True):
            cmds.setAttr(forma + ".aiExportColors", 1)
        conjunto = (cmds.polyColorSet(forma, query=True, currentColorSet=True) or ["colorSet1"])[0]
        shader = nombre + "_ai"
        if not cmds.objExists(shader):
            shader = cmds.shadingNode("aiStandardSurface", asShader=True, name=shader)
            dato = cmds.shadingNode("aiUserDataColor", asUtility=True, name=nombre + "_color_ai")
            cmds.setAttr(dato + ".attribute", conjunto, type="string")
            cmds.setAttr(dato + ".default", *_a_lineal(color, _con_gestion_de_color(), brillo),
                         type="double3")
            cmds.connectAttr(dato + ".outColor", shader + ".baseColor", force=True)
            ajustes = _ARNOLD.get(nombre, {})
            if ajustes.get("subsurface"):
                cmds.connectAttr(dato + ".outColor", shader + ".subsurfaceColor", force=True)
            for atributo, valor in ajustes.items():
                cmds.setAttr(shader + "." + atributo, valor)
        if cmds.attributeQuery("aiSurfaceShader", node=grupo, exists=True):
            cmds.connectAttr(shader + ".outColor", grupo + ".aiSurfaceShader", force=True)
        return shader
    except RuntimeError as error:
        cmds.warning(t("sin_arnold", error=error))
        return None


def _con_gestion_de_color():
    try:
        return bool(cmds.colorManagementPrefs(query=True, cmEnabled=True))
    except (RuntimeError, TypeError):
        return False


def _a_lineal(color, lineal=True, brillo=1.0):
    """Pasa un color pensado para la pantalla (sRGB) al espacio lineal.

    Con la gestión de color activa, Maya trata los colores de vértice y de
    material como lineales: sin convertirlos, los verdes salen mucho más
    claros y chillones de lo previsto. ``brillo`` multiplica el resultado.
    """
    if not lineal:
        return tuple(color[:3])
    return tuple(min(1.0, brillo * (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4))
                 for c in color[:3])


def crear_escena(nombre="sencilla"):
    """Construye una de las escenas de ``escenas.py`` y devuelve (mallas, localizadores)."""
    from . import escenas

    datos = escenas.ESCENAS[nombre]
    centro, tam = datos["suelo"]
    suelo = cmds.polyPlane(name="prueba_suelo", width=tam[0], height=tam[2],
                           subdivisionsX=1, subdivisionsY=1)[0]
    cmds.move(centro[0], centro[1] + tam[1] / 2.0, centro[2], suelo)
    mallas = [suelo]
    for nombre_caja, c, t in datos["cajas"]:
        caja = cmds.polyCube(name="prueba_" + nombre_caja, width=t[0], height=t[1], depth=t[2])[0]
        cmds.move(c[0], c[1], c[2], caja)
        mallas.append(caja)
    localizadores = []
    for i, o in enumerate(datos["origenes"]):
        loc = cmds.spaceLocator(name="prueba_origen{}".format(i + 1))[0]
        cmds.move(o[0], o[1], o[2], loc)
        localizadores.append(loc)
    return mallas, localizadores


def escena_de_prueba(semilla=1, **ajustes):
    """Crea un suelo, un muro y una caja, y hace crecer una planta desde la base del muro."""
    mallas, localizadores = crear_escena("sencilla")
    cmds.select(mallas + localizadores, replace=True)
    return ejecutar(semilla=semilla, **ajustes)


def escena_ruina(semilla=1, **ajustes):
    """Crea una pequeña ruina (muro con ventana, columna, murete) y la cubre de hiedra."""
    mallas, localizadores = crear_escena("ruina")
    cmds.select(mallas + localizadores, replace=True)
    from . import escenas

    for clave, valor in escenas.RUINA["ajustes"].items():
        if clave == "hojas":
            ajustes["hojas"] = dict(valor, **(ajustes.get("hojas") or {}))
        else:
            ajustes.setdefault(clave, valor)
    return ejecutar(semilla=semilla, **ajustes)
