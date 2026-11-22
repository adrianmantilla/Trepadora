"""Capturas de prueba de Trepadora en Maya (herramienta de desarrollo).

No forma parte del plugin. Sirve para generar siempre las mismas imágenes y
comparar versiones del crecimiento.

Uso, con Maya abierto (no funciona con mayapy porque necesita el visor)::

    exec(open("/ruta/Trepadora/herramientas/capturas_maya.py").read())
    capturar_todo("/ruta/de/salida", prefijo="maya2027")

O desde la terminal, abriendo Maya y cerrándolo al terminar::

    TREPADORA_RAIZ=/ruta/Trepadora TREPADORA_SALIDA=/ruta/de/salida TREPADORA_PREFIJO=maya2027 \
        maya -command "python(\\"exec(open('/ruta/Trepadora/herramientas/capturas_maya.py').read()); capturar_y_salir()\\")"
"""

import os
import sys
import time

from maya import cmds

# Carpeta raíz del repositorio: la variable TREPADORA_RAIZ, o la de este archivo.
_RAIZ = os.environ.get("TREPADORA_RAIZ") or os.path.dirname(
    os.path.dirname(os.path.abspath(globals().get("__file__", "."))))
_SCRIPTS = os.path.join(_RAIZ, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

VISTAS = {
    "tres_cuartos": dict(ojo=(-150, 120, 260), mira=(0, 70, 0), fov=40),
    "frente": dict(ojo=(0, 80, 330), mira=(0, 70, 0), fov=40),
    "cerca": dict(ojo=(-60, 150, 120), mira=(-30, 110, 0), fov=45),
}

VISTAS_RUINA = {
    "general": dict(ojo=(-260, 220, 520), mira=(20, 110, 40), fov=42),
    "ventana": dict(ojo=(-40, 140, 260), mira=(-20, 110, 0), fov=40),
    # Desde delante a la izquierda y un poco abajo: el extremo del muro a un
    # lado y la columna entera, con su capitel, contra el cielo. Por delante
    # del bloque de piedra, que así no tapa el pie de la columna.
    "columna": dict(ojo=(-170, 60, 470), mira=(180, 146, 30), fov=58),
}

# Cada variante: (escena, ajustes, vistas). La escena es "sencilla" o "ruina".
VARIANTES = {
    "semilla1": ("sencilla", dict(semilla=1), VISTAS),
    "semilla4_colgante": ("sencilla", dict(semilla=4, gravedad=1.0, prob_rama=0.08), VISTAS),
    "ruina_semilla1": ("ruina", dict(semilla=1), VISTAS_RUINA),
    "ruina_semilla1_ramillas": ("ruina", dict(semilla=1, ramillas=0.08), VISTAS_RUINA),
}


def _recargar():
    import importlib
    for nombre in sorted([m for m in sys.modules if m.startswith("trepadora")], reverse=True):
        importlib.reload(sys.modules[nombre])
    import trepadora.prototipo as tp
    return importlib.reload(tp)


def configurar_visor():
    """Antialiasing, oclusión ambiental y una luz con sombras."""
    hrg = "hardwareRenderingGlobals"
    for atributo, valor in (("multiSampleEnable", 1), ("multiSampleCount", 8),
                            ("ssaoEnable", 1), ("ssaoAmount", 1.2), ("ssaoRadius", 8),
                            ("ssaoFilterRadius", 8), ("ssaoSamples", 16)):
        try:
            cmds.setAttr("{}.{}".format(hrg, atributo), valor)
        except RuntimeError:
            pass
    if not cmds.objExists("captura_sol"):
        sol = cmds.directionalLight(name="captura_solShape", intensity=1.1)
        transform = cmds.listRelatives(sol, parent=True)[0]
        transform = cmds.rename(transform, "captura_sol")
        cmds.setAttr(transform + ".rotate", -50, -35, 0, type="double3")
        forma = cmds.listRelatives(transform, shapes=True)[0]
        cmds.setAttr(forma + ".useDepthMapShadows", 1)
        cmds.setAttr(forma + ".dmapResolution", 4096)
        cmds.setAttr(forma + ".dmapFilterSize", 2)
    if not cmds.objExists("captura_relleno"):
        relleno = cmds.ambientLight(name="captura_rellenoShape", intensity=0.35)
        cmds.rename(cmds.listRelatives(relleno, parent=True)[0], "captura_relleno")


def _panel_con_camara(camara):
    panel = None
    for p in cmds.getPanel(type="modelPanel") or []:
        if cmds.modelPanel(p, query=True, camera=True):
            panel = p
            break
    if panel is None:
        raise RuntimeError("No hay ningún visor 3D abierto")
    cmds.lookThru(panel, camara)
    cmds.setFocus(panel)
    cmds.modelEditor(panel, edit=True, displayAppearance="smoothShaded", displayLights="all",
                     shadows=True, twoSidedLighting=True, grid=False, headsUpDisplay=False, manipulators=False,
                     locators=False, lights=False, cameras=False, nurbsCurves=True,
                     selectionHiliteDisplay=False, wireframeOnShaded=False)
    return panel


def capturar_vistas(carpeta, nombre_base, vistas=None, ancho=1600, alto=900):
    vistas = vistas or VISTAS
    if not cmds.objExists("captura_cam"):
        cmds.rename(cmds.camera()[0], "captura_cam")
    camara = "captura_cam"
    _panel_con_camara(camara)
    cmds.select(clear=True)
    rutas = []
    for nombre, vista in vistas.items():
        cmds.viewPlace(camara, eye=vista["ojo"], lookAt=vista["mira"], perspective=True)
        cmds.camera(camara, edit=True, horizontalFieldOfView=vista.get("fov", 40))
        ruta = os.path.join(carpeta, "{}_{}.png".format(nombre_base, nombre))
        cmds.refresh(force=True)
        cmds.playblast(frame=[1], format="image", compression="png", viewer=False,
                       showOrnaments=False, widthHeight=(ancho, alto), percent=100,
                       completeFilename=ruta, forceOverwrite=True, offScreen=True)
        rutas.append(ruta)
    return rutas


def capturar_todo(carpeta, prefijo="maya"):
    if not os.path.isdir(carpeta):
        os.makedirs(carpeta)
    tp = _recargar()
    informe = []
    for nombre, (escena, ajustes, vistas) in VARIANTES.items():
        cmds.file(new=True, force=True)
        inicio = time.time()
        if escena == "ruina":
            tp.escena_ruina(**ajustes)
        else:
            tp.escena_de_prueba(**ajustes)
        segundos = time.time() - inicio
        configurar_visor()
        rutas = capturar_vistas(carpeta, "{}_{}".format(prefijo, nombre), vistas)
        escena = os.path.join(carpeta, "{}_{}.ma".format(prefijo, nombre))
        cmds.file(rename=escena)
        cmds.file(save=True, type="mayaAscii", force=True)
        informe.append("{}: {:.2f} s, {}".format(nombre, segundos, ", ".join(rutas + [escena])))
    texto = "\n".join(informe)
    with open(os.path.join(carpeta, prefijo + "_informe.txt"), "w") as f:
        f.write(texto + "\n")
    print(texto)
    return texto


def capturar_y_salir():
    carpeta = os.environ.get("TREPADORA_SALIDA", os.path.join(_RAIZ, "capturas"))
    prefijo = os.environ.get("TREPADORA_PREFIJO", "maya")
    if not os.path.isdir(carpeta):
        os.makedirs(carpeta)
    try:
        capturar_todo(carpeta, prefijo)
    except Exception:
        import traceback
        with open(os.path.join(carpeta, prefijo + "_error.txt"), "w") as f:
            traceback.print_exc(file=f)
        raise
    finally:
        # cmds.quit no siempre funciona durante el arranque de Maya: se sale
        # del proceso directamente (las imágenes y escenas ya están guardadas).
        sys.stdout.flush()
        os._exit(0)
