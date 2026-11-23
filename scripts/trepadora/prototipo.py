"""Prototipo de la fase 0: crecimiento con tallos y hojas, sin interfaz.

Uso en el Script Editor de Maya (pestaña Python)::

    import trepadora.prototipo as tp
    tp.escena_de_prueba()               # opcional: crea un muro y una caja y hace crecer
    tp.ejecutar(semilla=3)              # usa la seleccion actual
    tp.ejecutar(semilla=3, modo="curvas")   # solo lineas, muy rapido
    tp.ejecutar(semilla=3, forma_hoja="corazon", tipo_tallo="verde")
    tp.ejecutar(semilla=3, hoja_propia="miHoja")   # una hoja modelada por ti
    tp.ejecutar(semilla=3, instancias=False)       # todas las hojas en una malla

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


def ejecutar(semilla=1, pasos=None, modo="malla", hojas=None, grosor=1.0, paso=None,
             instancias=True, forma_hoja="hiedra", tipo_tallo="lenoso", hoja_propia=None,
             **ajustes):
    """Hace crecer la planta sobre la seleccion.

    * ``modo="malla"`` crea tallos con grosor y hojas; ``modo="curvas"`` solo lineas.
    * ``instancias``: las hojas son instancias de unas pocas hojas modelo (la
      escena pesa mucho menos). Con False, todas las hojas van en una malla,
      por ejemplo para exportarla.
    * ``forma_hoja``: "hiedra", "corazon", "alargada" o "redonda".
    * ``tipo_tallo``: "lenoso", "nudoso", "verde" o "rojizo".
    * ``hoja_propia``: nombre de una malla de la escena que se usa como hoja
      (siempre con instancias). Modélala con la base en el origen, la punta
      hacia +Y y la cara hacia +Z; el tamaño se ajusta solo.
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

    cmds.undoInfo(openChunk=True, chunkName="Trepadora")
    try:
        hechos, cancelado = crecer_con_progreso(crecimiento, pasos)
        if modo == "curvas":
            grupo = crear_vista_previa(crecimiento.curvas())
        else:
            grupo = crear_planta(crecimiento, paso_escena, hojas or {}, grosor, semilla,
                                 instancias=instancias, forma_hoja=forma_hoja,
                                 tipo_tallo=tipo_tallo, hoja_propia=hoja_propia)
    finally:
        cmds.undoInfo(closeChunk=True)

    if cancelado:
        cmds.warning(t("cancelado"))
    if crecimiento.limite_alcanzado:
        cmds.warning(t("limite", limite=parametros.limite_puntos))
    print(t("resumen", ramas=len(crecimiento.ramas), puntos=crecimiento.total_puntos,
            pasos=hechos, semilla=semilla))
    cmds.select(grupo, replace=True)
    return grupo


def crecer_con_progreso(crecimiento, pasos):
    """Hace ``pasos`` pasos con una barra de progreso que se detiene con Esc.

    Devuelve ``(pasos_hechos, cancelado)``. Lo crecido hasta Esc se conserva.
    """
    cancelado = {"valor": False}

    def al_progresar(paso, total):
        if cmds.progressWindow(query=True, isCancelled=True):
            cancelado["valor"] = True
            return False
        if paso % 5 == 0 or paso == total:
            cmds.progressWindow(edit=True, progress=int(100 * paso / total),
                                status=t("progreso_estado", paso=paso, total=total))
        return True

    cmds.progressWindow(title=t("progreso_titulo"), progress=0, isInterruptable=True,
                        status=t("progreso_estado", paso=0, total=pasos))
    try:
        hechos = crecimiento.crecer(pasos, al_progresar=al_progresar)
    finally:
        cmds.progressWindow(endProgress=True)
    return hechos, cancelado["valor"]


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


def _elegir(valor, opciones, por_defecto, clave_aviso, **datos):
    """``valor`` si está entre ``opciones``; si no, avisa y devuelve ``por_defecto``."""
    if valor in opciones:
        return valor
    cmds.warning(t(clave_aviso, opciones=", ".join(opciones), **datos))
    return por_defecto


def crear_planta(crecimiento, paso, ajustes_hojas, grosor=1.0, semilla=1, instancias=True,
                 forma_hoja="hiedra", tipo_tallo="lenoso", hoja_propia=None, lados=None,
                 resumen=None):
    """Crea tallos, hojas y rabillos dentro de un grupo nuevo (ver ``ejecutar``).

    ``lados``: lados del tubo de los tallos (por defecto, los del tipo de tallo).
    ``resumen``: si se da un diccionario, se rellena con ``hojas`` y ``modelos``.
    """
    forma_hoja = _elegir(forma_hoja, geometria.FORMAS_HOJA, "hiedra", "forma_desconocida",
                         forma=forma_hoja)
    tipo_tallo = _elegir(tipo_tallo, tuple(geometria.TIPOS_TALLO), "lenoso",
                         "tallo_desconocido", tipo=tipo_tallo)
    if hoja_propia and not instancias:
        cmds.warning(t("hoja_propia_sin_instancias"))
        instancias = True
    grosor *= geometria.TIPOS_TALLO[tipo_tallo]["grosor"]
    radios = crecimiento.grosores(paso * 0.45 * grosor, paso * 0.06 * grosor)
    datos_hojas = dict(ajustes_hojas)
    datos_hojas["tamano"] = paso * 2.4 * datos_hojas.get("tamano", 1.0)
    datos_hojas.setdefault("semilla", semilla)
    hojas = colocar_hojas(crecimiento, ParametrosHojas(**datos_hojas))

    grupo = cmds.group(empty=True, name=GRUPO_PLANTA)
    piezas = [
        ("trepadora_tallos",
         geometria.malla_tallos(crecimiento, radios, lados=lados, semilla=semilla,
                                tipo=tipo_tallo),
         (0.30, 0.21, 0.13)),
        ("trepadora_rabillos", geometria.malla_peciolos(hojas, tipo=tipo_tallo),
         (0.25, 0.33, 0.12)),
    ]
    modelos = 0
    if instancias and hojas:
        try:
            modelos = _crear_hojas_instanciadas(hojas, grupo, forma_hoja, semilla, hoja_propia)
        except RuntimeError as error:
            cmds.warning(t("sin_instancias", error=error))
    if not modelos:
        piezas.insert(1, ("trepadora_hojas",
                          geometria.malla_hojas(hojas, semilla=semilla, forma=forma_hoja),
                          (0.16, 0.38, 0.10)))
    for nombre, malla, color in piezas:
        if not malla.conteos:
            continue
        brillo = 1.0 if nombre == "trepadora_tallos" else _BRILLO_HOJAS
        transform = _crear_malla(nombre, malla, brillo)
        sombreado = _asignar_material(transform, nombre + "_mat", color, brillo)
        _material_arnold(transform, sombreado, nombre, color, brillo)
        cmds.parent(transform, grupo)
    if resumen is not None:
        resumen.update(hojas=len(hojas), modelos=modelos)
    if modelos:
        print(t("resumen_instancias", hojas=len(hojas), modelos=modelos))
    else:
        print(t("resumen_malla", hojas=len(hojas)))
    return grupo


# Color por defecto de las hojas en Arnold, si a una hoja le faltaran los
# colores de vértice (el de cada hoja va en ellos).
_COLOR_HOJAS = (0.16, 0.38, 0.10)


def _crear_hojas_instanciadas(hojas, grupo, forma, semilla, hoja_propia=None):
    """Hojas modelo ocultas, una partícula por hoja y un instanciador.

    Cada partícula lleva el giro, la escala y el modelo de su hoja, y en rgbPP
    la proporción entre el color de la hoja y el de su modelo: Arnold la lee y
    multiplica, así cada hoja sale de su color aunque comparta modelo.
    Devuelve el número de modelos, o 0 si no se pudo.
    """
    from . import instancias

    datos = instancias.hojas_instanciadas(hojas, forma=forma, semilla=semilla)
    lineal = _con_gestion_de_color()

    def a_lineal(c):
        return _a_lineal(c, lineal, _BRILLO_HOJAS)

    modelos_grp = _largo(cmds.group(empty=True, name="trepadora_hojas_modelos", parent=grupo))
    try:
        return _crear_modelos_e_instancias(datos, grupo, modelos_grp, hoja_propia, a_lineal)
    except RuntimeError:
        # Sin restos a medias: se borra lo creado y crear_planta hace la malla.
        restos = [modelos_grp] + (cmds.listRelatives(grupo, children=True, fullPath=True,
                                                     type="transform") or [])
        cmds.delete([r for r in restos if cmds.objExists(r) and "trepadora_hojas" in r])
        raise


def _largo(nombre):
    """Ruta completa de un nodo recién creado o movido (Maya da la más corta que no se repite)."""
    return (cmds.ls(nombre, long=True) or [nombre])[0]


def _crear_modelos_e_instancias(datos, grupo, modelos_grp, hoja_propia, a_lineal):
    from . import instancias

    propia = _modelo_propio(hoja_propia, modelos_grp) if hoja_propia else None
    if propia:
        modelos, indices = [propia], [0.0] * len(datos)
        proporciones = [(1.0, 1.0, 1.0)] * len(datos)
    else:
        modelos = []
        for i, modelo in enumerate(datos.modelos):
            transform = _crear_malla("trepadora_hoja_modelo{}".format(i + 1), modelo.malla,
                                     _BRILLO_HOJAS)
            # El visor no enseña los colores de vértice de las instancias: cada
            # tono lleva su propio material, del color de su grupo. Arnold no
            # lo usa (toma los colores de vértice y el rgbPP de cada hoja).
            sombreado = _asignar_material(
                transform, "trepadora_hojas_tono{}_mat".format(modelo.grupo + 1), modelo.color,
                _BRILLO_HOJAS)
            _material_arnold(transform, sombreado, "trepadora_hojas_inst", _COLOR_HOJAS,
                             _BRILLO_HOJAS, clave="trepadora_hojas", por_instancia=True)
            modelos.append(_largo(cmds.parent(transform, modelos_grp)[0]))
        indices = [float(i) for i in datos.indices]
        proporciones = [instancias.proporcion(c, datos.modelos[i].color, a_lineal)
                        for c, i in zip(datos.colores, datos.indices)]
    cmds.setAttr(modelos_grp + ".visibility", 0)
    _instanciador("trepadora_hojas", grupo, modelos, datos, indices, proporciones)
    return len(modelos)


def _modelo_propio(nombre, padre):
    """Copia de la hoja del alumno, de largo 1, lista para instanciar (o None)."""
    if not cmds.objExists(nombre) or not _es_malla(nombre):
        cmds.warning(t("sin_hoja_propia", nombre=nombre))
        return None
    copia = cmds.duplicate(nombre, name="trepadora_hoja_propia")[0]
    copia = _largo(cmds.parent(copia, padre)[0])
    # Se queda con la forma tal como se modeló, sin la posición del objeto.
    cmds.xform(copia, matrix=[1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0])
    caja = cmds.exactWorldBoundingBox(copia)
    largo = caja[4]
    if largo <= 1e-6 or caja[1] < -0.5 * largo:
        cmds.warning(t("hoja_propia_eje", nombre=nombre))
        largo = max(caja[4] - caja[1], 1e-6)
    cmds.setAttr(copia + ".scale", 1.0 / largo, 1.0 / largo, 1.0 / largo, type="double3")
    return copia


def _instanciador(nombre, grupo, modelos, datos, indices, proporciones):
    """Partículas quietas, una por hoja, y el instanciador que pone en ellas los modelos."""
    n = len(datos)
    particula, forma = (_largo(x) for x in cmds.particle(
        position=[tuple(p) for p in datos.posiciones], name=nombre + "_puntos"))
    for atributo, tipo in (("giroPP", "vectorArray"), ("escalaPP", "vectorArray"),
                           ("rgbPP", "vectorArray"), ("modeloPP", "doubleArray")):
        for nombre_pp in (atributo, atributo + "0"):
            if not cmds.attributeQuery(nombre_pp, node=forma, exists=True):
                cmds.addAttr(forma, longName=nombre_pp, dataType=tipo)
            if tipo == "doubleArray":
                cmds.setAttr(forma + "." + nombre_pp, indices, type=tipo)
            else:
                valores = {"giroPP": datos.giros, "escalaPP": datos.escalas,
                           "rgbPP": proporciones}[atributo]
                cmds.setAttr(forma + "." + nombre_pp, n, *valores, type=tipo)
    # Quietas: no son una simulación, solo marcan dónde va cada hoja.
    cmds.setAttr(forma + ".isDynamic", 0)
    cmds.saveInitialState(forma)
    # Que no se rendericen como puntos ni ensucien el visor.
    for atributo in ("primaryVisibility", "castsShadows", "receiveShadows",
                     "visibleInReflections", "visibleInRefractions"):
        if cmds.attributeQuery(atributo, node=forma, exists=True):
            cmds.setAttr(forma + "." + atributo, 0)
    if cmds.attributeQuery("aiExportAttributes", node=forma, exists=True):
        cmds.setAttr(forma + ".aiExportAttributes", "rgbPP", type="string")
    instanciador = cmds.particleInstancer(
        forma, addObject=True, object=modelos, cycle="None", levelOfDetail="Geometry",
        rotationUnits="Degrees", rotationOrder="XYZ", position="position",
        rotation="giroPP", scale="escalaPP", objectIndex="modeloPP", name=nombre + "_instancias")
    particula = _largo(cmds.parent(particula, grupo)[0])
    instanciador = _largo(cmds.parent(instanciador, grupo)[0])
    if _OCULTAR_PUNTOS:
        cmds.setAttr(particula + ".visibility", 0)
    return instanciador


# Ocultar las partículas (no las hojas): si en alguna versión de Maya o de
# Arnold las instancias desaparecieran con ellas, poner False.
_OCULTAR_PUNTOS = True


def _crear_malla(nombre, malla, brillo=1.0):
    import maya.api.OpenMaya as om

    fn = om.MFnMesh()
    puntos = om.MPointArray([om.MPoint(*p) for p in malla.vertices])
    objeto = fn.create(puntos, malla.conteos, malla.indices)
    lineal = _con_gestion_de_color()
    colores = om.MColorArray([om.MColor(_a_lineal(c, lineal, brillo) + (1.0,))
                              for c in malla.colores])
    fn.setVertexColors(colores, list(range(len(malla.vertices))))
    _suavizar(fn)
    transform = om.MFnDagNode(objeto).fullPathName()
    transform = cmds.rename(transform, nombre)
    forma = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
    cmds.setAttr(forma + ".displayColors", 1)
    return transform


def _suavizar(fn):
    """Todas las aristas suaves: la hoja y el tallo se ven curvos, no hechos de caras planas."""
    try:
        aristas = fn.numEdges
        fn.setEdgeSmoothings(list(range(aristas)), [True] * aristas)
        fn.cleanupEdgeSmoothing()
        fn.updateSurface()
    except (AttributeError, RuntimeError, TypeError):
        pass


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


# Ajustes del aiStandardSurface de cada pieza. «base» a 1 (Arnold trae 0.8)
# para que el color sea el de los vértices, como en el visor. Las hojas son
# finas: con thinWalled, «subsurface» es la luz que las atraviesa (a contraluz
# brillan), pero lo que pasa al otro lado se le quita a la cara iluminada; la
# hiedra es gruesa y cerosa, deja pasar poca. La luz que atraviesa una hoja
# sale mucho más clara y amarilla que su cara: el color de cada hoja se
# multiplica por _TRASLUCIDO.
_ARNOLD = {
    "trepadora_tallos": {"base": 1.0, "specular": 0.15, "specularRoughness": 0.6},
    "trepadora_hojas": {"base": 1.0, "specular": 0.5, "specularRoughness": 0.32,
                        "thinWalled": 1, "subsurface": 0.3},
    "trepadora_rabillos": {"base": 1.0, "specular": 0.25, "specularRoughness": 0.45},
}
_TRASLUCIDO = (4.0, 4.5, 1.5)


def _arnold_cargado():
    try:
        return bool(cmds.pluginInfo("mtoa", query=True, loaded=True))
    except RuntimeError:
        return False


def _material_arnold(transform, grupo, nombre, color, brillo=1.0, clave=None,
                     por_instancia=False):
    """Material de Arnold para la pieza, si Arnold (MtoA) está cargado.

    El lambert del grupo de sombreado queda para el visor; Arnold usa en su
    lugar un aiStandardSurface (conectado a aiSurfaceShader) que toma el color
    de cada hoja de los colores de vértice. Sin esto, en el render todas las
    hojas saldrían del mismo verde. ``clave`` elige los ajustes de _ARNOLD
    (por defecto, los de ``nombre``). Con ``por_instancia``, el color de los
    vértices se multiplica por el rgbPP de cada instancia.
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
            if por_instancia:
                dato = _por_instancia(dato, nombre)
            cmds.connectAttr(dato + ".outColor", shader + ".baseColor", force=True)
            ajustes = _ARNOLD.get(clave or nombre, {})
            if ajustes.get("subsurface"):
                _color_traslucido(dato, shader, nombre)
            for atributo, valor in ajustes.items():
                cmds.setAttr(shader + "." + atributo, valor)
        if cmds.attributeQuery("aiSurfaceShader", node=grupo, exists=True):
            _conectar(shader + ".outColor", grupo + ".aiSurfaceShader")
        return shader
    except RuntimeError as error:
        cmds.warning(t("sin_arnold", error=error))
        return None


def _conectar(origen, destino):
    """Conecta si no lo estaba ya (varias piezas comparten material: sin avisos repetidos)."""
    if not cmds.isConnected(origen, destino):
        cmds.connectAttr(origen, destino, force=True)


def _por_instancia(dato, nombre):
    """Multiplica el color de ``dato`` por el rgbPP de la instancia (1 si no lo hay)."""
    instancia = cmds.shadingNode("aiUserDataColor", asUtility=True, name=nombre + "_rgbPP_ai")
    cmds.setAttr(instancia + ".attribute", "rgbPP", type="string")
    cmds.setAttr(instancia + ".default", 1.0, 1.0, 1.0, type="double3")
    producto = cmds.shadingNode("aiMultiply", asUtility=True, name=nombre + "_color_hoja_ai")
    cmds.connectAttr(dato + ".outColor", producto + ".input1", force=True)
    cmds.connectAttr(instancia + ".outColor", producto + ".input2", force=True)
    return producto


def _color_traslucido(dato, shader, nombre):
    """Conecta al color de la luz que atraviesa la hoja su color, aclarado."""
    try:
        claro = cmds.shadingNode("aiMultiply", asUtility=True, name=nombre + "_traslucido_ai")
        cmds.connectAttr(dato + ".outColor", claro + ".input1", force=True)
        cmds.setAttr(claro + ".input2", *_TRASLUCIDO, type="double3")
        cmds.connectAttr(claro + ".outColor", shader + ".subsurfaceColor", force=True)
    except RuntimeError:
        # Sin aiMultiply, el mismo color de la hoja: atraviesa menos luz.
        cmds.connectAttr(dato + ".outColor", shader + ".subsurfaceColor", force=True)


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
    for nombre_caja, c, medidas in datos["cajas"]:
        caja = cmds.polyCube(name="prueba_" + nombre_caja, width=medidas[0], height=medidas[1],
                             depth=medidas[2])[0]
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
