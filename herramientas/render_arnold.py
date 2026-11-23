"""Render de prueba con Arnold de la ruina (herramienta de desarrollo).

No forma parte del plugin. Crea la ruina con hiedra, pone un cielo (aiSkyDomeLight)
y un sol con sombra suave, y renderiza con Arnold las vistas de la ruina de
capturas_maya.py, más una a contraluz. Guarda también la escena, por si se
quiere renderizar a mano.

Uso desde la terminal, con mayapy (no hace falta abrir Maya)::

    TREPADORA_RAIZ=/ruta/Trepadora mayapy /ruta/Trepadora/herramientas/render_arnold.py \\
        /ruta/de/salida prefijo [vista ...]

Vistas: general, ventana, columna y contraluz; sin vistas, renderiza
«general». Si Arnold no tiene licencia, la imagen sale
con marca de agua, que para comparar versiones no molesta.
"""

import glob
import os
import sys
import time

_RAIZ = os.environ.get("TREPADORA_RAIZ") or os.path.dirname(
    os.path.dirname(os.path.abspath(globals().get("__file__", "."))))
for _ruta in (os.path.join(_RAIZ, "scripts"), os.path.join(_RAIZ, "herramientas")):
    if _ruta not in sys.path:
        sys.path.insert(0, _ruta)

ANCHO, ALTO = 1280, 720
# Cielo azulado y sol cálido, desde la misma dirección que la luz de las
# capturas del visor.
CIELO = dict(color=(0.75, 0.85, 1.0), intensidad=1.0)
SOL = dict(color=(1.0, 0.92, 0.8), intensidad=2.5, giro=(-50, -35, 0), angulo=2.0)
# Vistas propias del render. «contraluz» mira la ventana con el sol bajo detrás
# del muro: se ve la luz que atraviesa las hojas que cuelgan en el hueco.
CONTRALUZ = dict(ojo=(-40, 140, 260), mira=(-20, 110, 0), fov=40, sol=(-28, 160, 0))
PIEDRA = (0.55, 0.52, 0.47)
# Manchas de la piedra: ruido en el espacio de la escena (rasgos de unas 15
# unidades), entre un tono más oscuro y otro más claro que PIEDRA.
DESGASTE = dict(escala=(0.07, 0.07, 0.07), oscuro=0.7, claro=1.15, relieve=0.4)
SUELO = (0.32, 0.31, 0.28)


def _iniciar():
    """En mayapy arranca Maya sin interfaz; dentro de Maya no hace nada."""
    try:
        from maya import cmds
        cmds.about(version=True)
    except (ImportError, AttributeError):
        import maya.standalone
        maya.standalone.initialize(name="python")
    from maya import cmds
    if not cmds.pluginInfo("mtoa", query=True, loaded=True):
        cmds.loadPlugin("mtoa")
    return cmds


def _material_piedra(cmds, nombre, color, rugosidad=0.85):
    shader = cmds.shadingNode("aiStandardSurface", asShader=True, name=nombre)
    cmds.setAttr(shader + ".baseColor", *color, type="double3")
    cmds.setAttr(shader + ".specular", 0.15)
    cmds.setAttr(shader + ".specularRoughness", rugosidad)
    _desgaste(cmds, nombre, shader, color)
    grupo = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=nombre + "SG")
    cmds.connectAttr(shader + ".outColor", grupo + ".surfaceShader", force=True)
    return grupo


def _desgaste(cmds, nombre, shader, color):
    """Manchas y relieve de ruido en la piedra, para que no parezca plástico.

    Solo decora el render de prueba. Si algún nodo o atributo no existe en
    esta versión de Arnold, la piedra se queda lisa y el render sigue.
    """
    try:
        ruido = cmds.shadingNode("aiNoise", asTexture=True, name=nombre + "_manchas")
        cmds.setAttr(ruido + ".octaves", 4)
        cmds.setAttr(ruido + ".scale", *DESGASTE["escala"], type="double3")
        cmds.setAttr(ruido + ".coordSpace", 0)  # mundo
        oscuro = tuple(c * DESGASTE["oscuro"] for c in color)
        claro = tuple(min(1.0, c * DESGASTE["claro"]) for c in color)
        cmds.setAttr(ruido + ".color1", *oscuro, type="double3")
        cmds.setAttr(ruido + ".color2", *claro, type="double3")
        cmds.connectAttr(ruido + ".outColor", shader + ".baseColor", force=True)
        relieve = cmds.shadingNode("bump2d", asUtility=True, name=nombre + "_relieve")
        cmds.setAttr(relieve + ".bumpDepth", DESGASTE["relieve"])
        cmds.connectAttr(ruido + ".outColorR", relieve + ".bumpValue", force=True)
        cmds.connectAttr(relieve + ".outNormal", shader + ".normalCamera", force=True)
    except RuntimeError as error:
        print("render_arnold: piedra sin desgaste ({})".format(error))


def _luces(cmds):
    cmds.shadingNode("aiSkyDomeLight", asLight=True, name="render_cielo")
    forma_cielo = cmds.ls(type="aiSkyDomeLight")[0]
    cmds.setAttr(forma_cielo + ".color", *CIELO["color"], type="double3")
    cmds.setAttr(forma_cielo + ".intensity", CIELO["intensidad"])
    forma_sol = cmds.directionalLight(name="render_solShape", intensity=SOL["intensidad"])
    sol = cmds.listRelatives(forma_sol, parent=True)[0]
    cmds.setAttr(sol + ".rotate", *SOL["giro"], type="double3")
    cmds.setAttr(forma_sol + ".color", *SOL["color"], type="double3")
    if cmds.attributeQuery("aiAngle", node=forma_sol, exists=True):
        cmds.setAttr(forma_sol + ".aiAngle", SOL["angulo"])
    return sol


def _ajustes(cmds):
    import mtoa.core
    mtoa.core.createOptions()
    cmds.setAttr("defaultRenderGlobals.currentRenderer", "arnold", type="string")
    opciones = "defaultArnoldRenderOptions"
    for atributo, valor in (("AASamples", 4), ("GIDiffuseSamples", 2), ("GISpecularSamples", 2),
                            ("GITransmissionSamples", 2), ("GISssSamples", 2),
                            ("GIDiffuseDepth", 2), ("GITransmissionDepth", 4),
                            ("abortOnLicenseFail", 0)):
        if cmds.attributeQuery(atributo, node=opciones, exists=True):
            cmds.setAttr(opciones + "." + atributo, valor)
    cmds.setAttr("defaultArnoldDriver.ai_translator", "png", type="string")
    # Que la imagen guardada lleve la misma transformación de vista que el
    # visor; si no, el PNG sale en lineal, oscuro y duro.
    for ajuste in (dict(outputTransformEnabled=True), dict(outputUseViewTransform=True)):
        try:
            cmds.colorManagementPrefs(edit=True, **ajuste)
        except (RuntimeError, TypeError):
            pass
    cmds.setAttr("defaultResolution.width", ANCHO)
    cmds.setAttr("defaultResolution.height", ALTO)
    cmds.setAttr("defaultResolution.deviceAspectRatio", ANCHO / float(ALTO))


def preparar(cmds, semilla=1):
    """Crea la ruina con hiedra, materiales de piedra, luces y ajustes de Arnold."""
    import capturas_maya
    tp = capturas_maya._recargar()
    cmds.file(new=True, force=True)
    inicio = time.time()
    tp.escena_ruina(semilla=semilla)
    segundos = time.time() - inicio
    piedra = _material_piedra(cmds, "render_piedra", PIEDRA)
    suelo = _material_piedra(cmds, "render_suelo", SUELO, 0.95)
    for nodo in cmds.ls("prueba_*", type="transform"):
        if cmds.listRelatives(nodo, shapes=True, type="mesh"):
            cmds.sets(nodo, edit=True, forceElement=suelo if nodo == "prueba_suelo" else piedra)
    sol = _luces(cmds)
    _ajustes(cmds)
    return segundos, sol


def _camara(cmds, vista):
    if not cmds.objExists("render_cam"):
        cmds.rename(cmds.camera()[0], "render_cam")
    cmds.viewPlace("render_cam", eye=vista["ojo"], lookAt=vista["mira"], perspective=True)
    cmds.camera("render_cam", edit=True, horizontalFieldOfView=vista.get("fov", 40))
    for camara in cmds.ls(type="camera"):
        cmds.setAttr(camara + ".renderable", 0)
    cmds.setAttr(cmds.listRelatives("render_cam", shapes=True)[0] + ".renderable", 1)
    return "render_cam"


def _recientes(cmds, desde):
    """PNG escritos desde ``desde`` en la carpeta de imágenes del proyecto, por
    si Arnold no respetó la ruta de salida."""
    raiz = cmds.workspace(query=True, rootDirectory=True) or ""
    imagenes = os.path.join(raiz, cmds.workspace(fileRuleEntry="images") or "images")
    return [r for r in glob.glob(os.path.join(imagenes, "**", "*.png"), recursive=True)
            if os.path.getmtime(r) >= desde]


def renderizar(carpeta, prefijo, vistas=("general",), semilla=1):
    cmds = _iniciar()
    import capturas_maya
    if not os.path.isdir(carpeta):
        os.makedirs(carpeta)
    informe = ["MtoA {}".format(cmds.pluginInfo("mtoa", query=True, version=True))]
    segundos, sol = preparar(cmds, semilla)
    informe.append("crecimiento y mallas: {:.2f} s".format(segundos))
    todas = dict(capturas_maya.VISTAS_RUINA, contraluz=CONTRALUZ)
    for nombre in vistas:
        vista = todas[nombre]
        cmds.setAttr(sol + ".rotate", *vista.get("sol", SOL["giro"]), type="double3")
        camara = _camara(cmds, vista)
        base = os.path.join(carpeta, "{}_arnold_{}".format(prefijo, nombre))
        cmds.setAttr("defaultRenderGlobals.imageFilePrefix", base, type="string")
        inicio = time.time()
        cmds.arnoldRender(width=ANCHO, height=ALTO, camera=camara, batch=True)
        hechas = sorted(glob.glob(base + "*.png") + _recientes(cmds, inicio), key=os.path.getmtime)
        informe.append("{}: {:.1f} s, {}".format(nombre, time.time() - inicio,
                                                 hechas[-1] if hechas else "SIN IMAGEN"))
    escena = os.path.join(carpeta, prefijo + "_arnold.ma")
    cmds.file(rename=escena)
    cmds.file(save=True, type="mayaAscii", force=True)
    informe.append("escena: " + escena)
    texto = "\n".join(informe)
    with open(os.path.join(carpeta, prefijo + "_arnold_informe.txt"), "w") as f:
        f.write(texto + "\n")
    print(texto)
    return texto


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    renderizar(sys.argv[1], sys.argv[2], tuple(sys.argv[3:]) or ("general",))
