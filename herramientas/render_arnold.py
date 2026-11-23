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
# «intensidad» es la luz que da el cielo; el cielo que se ve de fondo se
# queda en los colores de DEGRADADO (la visibilidad para la cámara compensa).
# Con el cielo azul, a 1.0 las sombras salían casi negras a contraluz.
CIELO = dict(color=(0.75, 0.85, 1.0), intensidad=1.3)
# Bruma del horizonte: un gris azulado pálido. El cielo la tiene justo en el
# horizonte y por debajo, y el suelo se funde con ella a lo lejos (LEJANIA).
BRUMA = (0.66, 0.74, 0.86)
# Degradado del cielo (posición de abajo a arriba, color lineal; 0.5 es el
# horizonte). Las vistas miran casi en horizontal y solo ven unos grados de
# cielo: el azul tiene que empezar muy cerca del horizonte o el cielo sale
# blanco. Si no se puede montar, queda el color liso de CIELO.
DEGRADADO = ((0.0, BRUMA), (0.5, BRUMA), (0.515, (0.60, 0.70, 0.88)),
             (0.56, (0.42, 0.58, 0.90)), (0.7, (0.30, 0.48, 0.88)), (1.0, (0.22, 0.40, 0.84)))
AMPLIAR_SUELO = 25.0
# Cuánta bruma lleva el suelo según la distancia al centro de la ruina, como
# (distancia en unidades de la escena, bruma). Sin esto el suelo acaba en una
# línea dura contra el cielo y parece un plano infinito. Es un término medio:
# desde una cámara baja todo lo que queda más allá de unas 2000 unidades se
# aprieta en una franja de pocos píxeles bajo el horizonte, pero en la vista
# general ese mismo tramo ocupa media imagen y, con mucha bruma, la hierba
# detrás de la ruina salía gris y plana.
LEJANIA = ((300, 0.0), (1200, 0.1), (2400, 0.35), (4500, 0.75), (8000, 1.0))
# Media anchura del suelo ya agrandado (700 × AMPLIAR_SUELO / 2): ahí está la
# posición 1 de la rampa circular.
RADIO_SUELO = 350.0 * AMPLIAR_SUELO
# Con el cielo azul y la bruma, un sol de 0.92 de verde dejaba la escena fría:
# más anaranjado y algo más fuerte, para que la piedra y la hierba se calienten.
SOL = dict(color=(1.0, 0.86, 0.68), intensidad=2.8, giro=(-50, -35, 0), angulo=2.0)
# Vistas propias del render. «contraluz» mira la ventana con el sol bajo detrás
# del muro: se ve la luz que atraviesa las hojas que cuelgan en el hueco.
# El sol, más fuerte: a contraluz es lo que hace brillar las hojas.
# A contraluz la cara de la pared que ve la cámara queda en sombra: se abre medio
# paso de exposición, como haría un fotógrafo midiendo en la hiedra.
CONTRALUZ = dict(ojo=(-40, 140, 260), mira=(-20, 110, 0), fov=40, sol=(-28, 160, 0),
                 intensidad_sol=4.0, exposicion=0.5)
PIEDRA = (0.55, 0.52, 0.47)
# Manchas de la piedra: ruido en el espacio de la escena (rasgos de unas 15
# unidades), entre un tono más oscuro y otro más claro que PIEDRA. El relieve,
# de otro ruido más fino, con más octavas y algo retorcido, para que no salga
# un grano uniforme como de gotelé ni una piedra lisa.
DESGASTE = dict(escala=0.07, oscuro=0.7, claro=1.15, escala_relieve=0.15, relieve=0.9,
                retorcido=0.5)
SUELO = (0.32, 0.31, 0.28)
# En el suelo, manchas más pequeñas (grandes, se leen como nubes) y, por debajo,
# un campo de rodales de tierra y hierba seca de unas 150 unidades: el suelo
# llega hasta el horizonte y, gris y liso, parecía agua o asfalto. El ruido casi
# nunca llega a sus extremos (se queda entre 0.3 y 0.7), así que los dos colores
# del campo van más separados de lo que se quiere ver: tierra parda y hierba verde.
DESGASTE_SUELO = dict(DESGASTE, escala=0.14, relieve=0.4, oscuro=0.65, claro=1.25,
                      campo=(0.006, (0.40, 0.30, 0.16), (0.08, 0.19, 0.04)))


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


def _material_piedra(cmds, nombre, color, rugosidad=0.85, desgaste=DESGASTE):
    shader = cmds.shadingNode("aiStandardSurface", asShader=True, name=nombre)
    cmds.setAttr(shader + ".baseColor", *color, type="double3")
    cmds.setAttr(shader + ".specular", 0.15)
    cmds.setAttr(shader + ".specularRoughness", rugosidad)
    _desgaste(cmds, nombre, shader, color, desgaste)
    grupo = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=nombre + "SG")
    cmds.connectAttr(shader + ".outColor", grupo + ".surfaceShader", force=True)
    return grupo


def _ruido(cmds, nombre, escala, color1, color2, octavas=4):
    ruido = cmds.shadingNode("aiNoise", asTexture=True, name=nombre)
    cmds.setAttr(ruido + ".octaves", octavas)
    cmds.setAttr(ruido + ".scale", escala, escala, escala, type="double3")
    cmds.setAttr(ruido + ".coordSpace", 0)  # mundo
    cmds.setAttr(ruido + ".color1", *color1, type="double3")
    cmds.setAttr(ruido + ".color2", *color2, type="double3")
    return ruido


def _desgaste(cmds, nombre, shader, color, desgaste):
    """Manchas y relieve de ruido en la piedra, para que no parezca plástico.

    Solo decora el render de prueba. Si algún nodo o atributo no existe en
    esta versión de Arnold, la piedra se queda lisa y el render sigue.
    """
    try:
        if "campo" in desgaste:
            # Rodales grandes de color, aclarados y oscurecidos por las manchas.
            escala, color_a, color_b = desgaste["campo"]
            campo = _ruido(cmds, nombre + "_campo", escala, color_a, color_b, octavas=5)
            manchas = _ruido(cmds, nombre + "_manchas", desgaste["escala"],
                             (desgaste["oscuro"],) * 3, (desgaste["claro"],) * 3)
            mezcla = cmds.shadingNode("aiMultiply", asUtility=True, name=nombre + "_mezcla")
            cmds.connectAttr(campo + ".outColor", mezcla + ".input1", force=True)
            cmds.connectAttr(manchas + ".outColor", mezcla + ".input2", force=True)
            cmds.connectAttr(mezcla + ".outColor", shader + ".baseColor", force=True)
        else:
            oscuro = tuple(c * desgaste["oscuro"] for c in color)
            claro = tuple(min(1.0, c * desgaste["claro"]) for c in color)
            manchas = _ruido(cmds, nombre + "_manchas", desgaste["escala"], oscuro, claro)
            cmds.connectAttr(manchas + ".outColor", shader + ".baseColor", force=True)
        granos = _ruido(cmds, nombre + "_granos", desgaste["escala_relieve"],
                        (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), octavas=6)
        if desgaste.get("retorcido"):
            cmds.setAttr(granos + ".distortion", desgaste["retorcido"])
        relieve = cmds.shadingNode("bump2d", asUtility=True, name=nombre + "_relieve")
        cmds.setAttr(relieve + ".bumpDepth", desgaste["relieve"])
        cmds.connectAttr(granos + ".outColorR", relieve + ".bumpValue", force=True)
        cmds.connectAttr(relieve + ".outNormal", shader + ".normalCamera", force=True)
    except RuntimeError as error:
        print("render_arnold: piedra sin desgaste ({})".format(error))


def _rampa(cmds, nombre, entradas, tipo, lugar=None):
    """Rampa de Maya con estas (posición, color); quita las que trae de serie."""
    rampa = cmds.shadingNode("ramp", asTexture=True, name=nombre)
    cmds.setAttr(rampa + ".type", tipo)
    if lugar:
        cmds.connectAttr(lugar + ".outUV", rampa + ".uvCoord", force=True)
        cmds.connectAttr(lugar + ".outUvFilterSize", rampa + ".uvFilterSize", force=True)
    for i in cmds.getAttr(rampa + ".colorEntryList", multiIndices=True) or []:
        cmds.removeMultiInstance("{}.colorEntryList[{}]".format(rampa, i), b=True)
    for i, (posicion, color) in enumerate(entradas):
        entrada = "{}.colorEntryList[{}]".format(rampa, i)
        cmds.setAttr(entrada + ".position", posicion)
        cmds.setAttr(entrada + ".color", *color, type="double3")
    return rampa


def _lejania(cmds, shader):
    """A lo lejos, el suelo deja de recibir luz y brilla con el color de la bruma.

    Con la bruma como emisión, y no como color, el suelo lejano sale igual que
    el cielo en el horizonte, haya sol o sombra, y no queda línea entre los dos.
    """
    try:
        lugar = cmds.shadingNode("place2dTexture", asUtility=True, name=shader + "_lugar")
        tramos = [(min(1.0, d / RADIO_SUELO), k) for d, k in LEJANIA]
        cerca = [(0.0, (1.0, 1.0, 1.0))] + [(pos, (1.0 - k,) * 3) for pos, k in tramos]
        lejos = [(0.0, (0.0, 0.0, 0.0))] + [(pos, tuple(k * c for c in BRUMA))
                                            for pos, k in tramos]
        # Tipo 4: rampa circular, por anillos desde el centro del suelo.
        mascara = _rampa(cmds, shader + "_cerca", cerca, 4, lugar)
        velo = _rampa(cmds, shader + "_lejos", lejos, 4, lugar)
        apagado = cmds.shadingNode("aiMultiply", asUtility=True, name=shader + "_apagado")
        fuente = cmds.listConnections(shader + ".baseColor", source=True, destination=False,
                                      plugs=True)
        if fuente:
            cmds.connectAttr(fuente[0], apagado + ".input1", force=True)
        else:
            cmds.setAttr(apagado + ".input1", *cmds.getAttr(shader + ".baseColor")[0],
                         type="double3")
        cmds.connectAttr(mascara + ".outColor", apagado + ".input2", force=True)
        cmds.connectAttr(apagado + ".outColor", shader + ".baseColor", force=True)
        cmds.setAttr(shader + ".emission", 1.0)
        cmds.connectAttr(velo + ".outColor", shader + ".emissionColor", force=True)
    except RuntimeError as error:
        print("render_arnold: suelo sin bruma ({})".format(error))


def _degradado_cielo(cmds, forma_cielo):
    """Pone en el cielo el DEGRADADO de abajo a arriba, con una rampa de Maya."""
    try:
        rampa = _rampa(cmds, "render_cielo_degradado", DEGRADADO, 0)  # en V: de abajo a arriba
        cmds.connectAttr(rampa + ".outColor", forma_cielo + ".color", force=True)
    except RuntimeError as error:
        print("render_arnold: cielo sin degradado ({})".format(error))


def _luces(cmds):
    cmds.shadingNode("aiSkyDomeLight", asLight=True, name="render_cielo")
    forma_cielo = cmds.ls(type="aiSkyDomeLight")[0]
    cmds.setAttr(forma_cielo + ".color", *CIELO["color"], type="double3")
    # En MtoA 5.6 el atributo se llama «camera»; se mira también «aiCamera».
    camara = [a for a in ("camera", "aiCamera")
              if cmds.attributeQuery(a, node=forma_cielo, exists=True)]
    if camara:
        cmds.setAttr(forma_cielo + ".intensity", CIELO["intensidad"])
        cmds.setAttr(forma_cielo + "." + camara[0], 1.0 / CIELO["intensidad"])
    else:
        # Sin esa visibilidad, más luz aclararía también el cielo de fondo
        # y dejaría de casar con la bruma del suelo.
        print("render_arnold: cielo sin visibilidad de cámara; intensidad 1")
    _degradado_cielo(cmds, forma_cielo)
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
    suelo = _material_piedra(cmds, "render_suelo", SUELO, 0.95, DESGASTE_SUELO)
    _lejania(cmds, "render_suelo")
    for nodo in cmds.ls("prueba_*", type="transform"):
        if cmds.listRelatives(nodo, shapes=True, type="mesh"):
            cmds.sets(nodo, edit=True, forceElement=suelo if nodo == "prueba_suelo" else piedra)
    if cmds.objExists("prueba_suelo"):
        # La planta ya ha crecido: agrandar el suelo solo cambia el fondo.
        cmds.scale(AMPLIAR_SUELO, 1, AMPLIAR_SUELO, "prueba_suelo", relative=True)
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
    forma = cmds.listRelatives("render_cam", shapes=True)[0]
    cmds.setAttr(forma + ".renderable", 1)
    if cmds.attributeQuery("aiExposure", node=forma, exists=True):
        cmds.setAttr(forma + ".aiExposure", vista.get("exposicion", 0.0))
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
    forma_sol = cmds.listRelatives(sol, shapes=True)[0]
    informe.append("crecimiento y mallas: {:.2f} s".format(segundos))
    todas = dict(capturas_maya.VISTAS_RUINA, contraluz=CONTRALUZ)
    for nombre in vistas:
        vista = todas[nombre]
        cmds.setAttr(sol + ".rotate", *vista.get("sol", SOL["giro"]), type="double3")
        cmds.setAttr(forma_sol + ".intensity", vista.get("intensidad_sol", SOL["intensidad"]))
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
