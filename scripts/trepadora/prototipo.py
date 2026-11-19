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


def _es_malla(nodo):
    if cmds.nodeType(nodo) == "mesh":
        return True
    formas = cmds.listRelatives(nodo, shapes=True, fullPath=True, noIntermediate=True) or []
    return any(cmds.nodeType(f) == "mesh" for f in formas)


def _es_localizador(nodo):
    formas = cmds.listRelatives(nodo, shapes=True, fullPath=True) or []
    return any(cmds.nodeType(f) == "locator" for f in formas)


def _parametros_para(mallas, ajustes):
    """Escala las distancias al tamaño de la escena para que los valores por defecto funcionen."""
    xmin, ymin, zmin, xmax, ymax, zmax = cmds.exactWorldBoundingBox(mallas)
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


def ejecutar(semilla=1, pasos=None, modo="malla", hojas=None, grosor=1.0, **ajustes):
    """Hace crecer la planta sobre la seleccion.

    * ``modo="malla"`` crea tallos con grosor y hojas; ``modo="curvas"`` solo lineas.
    * ``hojas``: diccionario con ajustes de ``ParametrosHojas`` (densidad, tamano...).
      El tamano es relativo: 1.0 = tamano por defecto para la escena.
    * ``grosor``: multiplica el grosor de los tallos.
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
    parametros, caja, paso_escena = _parametros_para(mallas, ajustes)
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
        transform = _crear_malla(nombre, malla)
        _asignar_material(transform, nombre + "_mat", color)
        cmds.parent(transform, grupo)
    print("Trepadora: {} hojas.".format(len(hojas)))
    return grupo


def _crear_malla(nombre, malla):
    import maya.api.OpenMaya as om

    fn = om.MFnMesh()
    puntos = om.MPointArray([om.MPoint(*p) for p in malla.vertices])
    objeto = fn.create(puntos, malla.conteos, malla.indices)
    colores = om.MColorArray([om.MColor((c[0], c[1], c[2], 1.0)) for c in malla.colores])
    fn.setVertexColors(colores, list(range(len(malla.vertices))))
    transform = om.MFnDagNode(objeto).fullPathName()
    transform = cmds.rename(transform, nombre)
    forma = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
    cmds.setAttr(forma + ".displayColors", 1)
    return transform


def _asignar_material(transform, nombre, color):
    if cmds.objExists(nombre):
        material = nombre
        grupo = cmds.listConnections(material + ".outColor", type="shadingEngine")[0]
    else:
        material = cmds.shadingNode("lambert", asShader=True, name=nombre)
        cmds.setAttr(material + ".color", *color, type="double3")
        grupo = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=nombre + "SG")
        cmds.connectAttr(material + ".outColor", grupo + ".surfaceShader", force=True)
    cmds.sets(transform, edit=True, forceElement=grupo)


def escena_de_prueba(semilla=1, **ajustes):
    """Crea un suelo, un muro y una caja, y hace crecer una planta desde la base del muro."""
    suelo = cmds.polyPlane(name="prueba_suelo", width=400, height=400, subdivisionsX=1,
                           subdivisionsY=1)[0]
    muro = cmds.polyCube(name="prueba_muro", width=200, height=150, depth=10)[0]
    cmds.move(0, 75, 0, muro)
    caja = cmds.polyCube(name="prueba_caja", width=40, height=40, depth=40)[0]
    cmds.move(60, 20, 30, caja)
    origen = cmds.spaceLocator(name="prueba_origen")[0]
    cmds.move(-20, 2, 5.5, origen)
    cmds.select([suelo, muro, caja, origen], replace=True)
    return ejecutar(semilla=semilla, **ajustes)
