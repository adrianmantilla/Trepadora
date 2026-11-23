"""Instalador de Trepadora: arrastra este archivo a la ventana de Maya.

Funciona igual en Windows y en macOS, con Maya 2026 y 2027:

1. Escribe ``trepadora.mod`` en la carpeta de módulos del usuario de Maya
   (``Documentos/maya/modules`` en Windows, ``~/Library/Preferences/Autodesk/maya/modules``
   en macOS), apuntando a esta carpeta. Así Maya encuentra los scripts, el
   plug-in y el icono cada vez que arranca.
2. Carga el plug-in (que añade el menú «Trepadora») y lo marca para que se
   cargue solo.
3. Crea un estante «Trepadora» con un botón que abre la ventana.
4. Abre la ventana.

No copia nada: si mueves la carpeta de Trepadora, vuelve a arrastrar este
archivo. Para desinstalar, ejecuta ``desinstalar()`` de este archivo (o borra
``trepadora.mod`` de la carpeta de módulos y el estante «Trepadora»).
"""

import io
import os
import re
import sys
import time

RAIZ = os.path.dirname(os.path.abspath(__file__))
NOMBRE_MOD = "trepadora.mod"
PLUGIN = "trepadora_plugin"
ESTANTE = "Trepadora"
ORDEN_BOTON = "import trepadora.ui.ventana as v\nv.mostrar()"


def version(raiz=RAIZ):
    """La versión escrita en ``scripts/trepadora/__init__.py``."""
    with io.open(os.path.join(raiz, "scripts", "trepadora", "__init__.py"), encoding="utf-8") as f:
        encontrada = re.search(r'__version__\s*=\s*"([^"]+)"', f.read())
    return encontrada.group(1) if encontrada else "0.0.0"


def texto_mod(raiz=RAIZ):
    """Contenido del archivo .mod: una línea con el nombre, la versión y la carpeta.

    Maya añade por su cuenta ``scripts`` al PYTHONPATH, ``plug-ins`` a la ruta
    de plug-ins e ``icons`` a la de iconos.
    """
    return "+ Trepadora {} {}\n".format(version(), raiz.replace("\\", "/"))


def escribir_mod(carpeta_modulos, raiz=RAIZ):
    if not os.path.isdir(carpeta_modulos):
        os.makedirs(carpeta_modulos)
    ruta = os.path.join(carpeta_modulos, NOMBRE_MOD)
    with io.open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto_mod(raiz))
    return ruta


def _carpeta_modulos():
    from maya import cmds

    return os.path.join(cmds.internalVar(userAppDir=True), "modules")


def _olvidar_modulos_viejos():
    """Para reinstalar sin reiniciar Maya: que se lea el código nuevo."""
    for nombre in list(sys.modules):
        if nombre == "trepadora" or nombre.startswith("trepadora."):
            del sys.modules[nombre]


def _crear_estante(cmds, mel, t):
    padre = mel.eval("$tmp = $gShelfTopLevel")
    if cmds.shelfLayout(ESTANTE, exists=True):
        for boton in cmds.shelfLayout(ESTANTE, query=True, childArray=True) or []:
            cmds.deleteUI(boton)
    else:
        mel.eval('addNewShelfTab "{}"'.format(ESTANTE))
    icono = os.path.join(RAIZ, "icons", "trepadora.png").replace("\\", "/")
    cmds.shelfButton(parent=ESTANTE, label=t("ventana_titulo"), annotation=t("ayuda_estante"),
                     image=icono, image1=icono, imageOverlayLabel="",
                     command=ORDEN_BOTON, sourceType="python")
    cmds.tabLayout(padre, edit=True, selectTab=ESTANTE)
    mel.eval("saveAllShelves $gShelfTopLevel")


def instalar(carpeta_modulos=None, estante=True, abrir=True, dialogo=True):
    """Instala Trepadora para el usuario actual de Maya. Devuelve un resumen."""
    from maya import cmds, mel

    tiempos = {}
    inicio = time.time()

    def apuntar(paso):
        nonlocal inicio
        tiempos[paso] = round(time.time() - inicio, 2)
        inicio = time.time()

    carpeta_modulos = carpeta_modulos or _carpeta_modulos()
    ruta_mod = escribir_mod(carpeta_modulos)

    # Para esta sesión (en las siguientes lo hace el .mod).
    scripts = os.path.join(RAIZ, "scripts")
    if ventana_abierta():
        from trepadora.ui import ventana

        ventana.cerrar()
    _olvidar_modulos_viejos()
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from trepadora.i18n import t

    apuntar("modulo")
    plugin = os.path.join(RAIZ, "plug-ins", PLUGIN + ".py")
    _descargar_plugin(cmds)
    cmds.loadPlugin(plugin)
    cmds.pluginInfo(plugin, edit=True, autoload=True)
    apuntar("plugin")
    if not cmds.about(batch=True):
        from trepadora import menu

        menu.crear()
        apuntar("menu")
        if estante:
            _crear_estante(cmds, mel, t)
            apuntar("estante")
        if abrir:
            menu.abrir()
            apuntar("ventana")
    _guardar_preferencias(cmds)
    apuntar("preferencias")
    if dialogo and not cmds.about(batch=True):
        cmds.confirmDialog(title=t("ventana_titulo"),
                           message=t("instalado", carpeta=RAIZ, mod=ruta_mod),
                           button=[t("boton_aceptar")])
    return {"mod": ruta_mod, "plugin": plugin, "version": version(), "segundos": tiempos}


def _descargar_plugin(cmds):
    """Descarga el plug-in si está cargado (para reinstalar o desinstalar).

    Antes vacía el historial de deshacer: puede guardar pasos del plug-in
    (Crear malla) que ya no se podrían deshacer sin él.
    """
    if cmds.pluginInfo(PLUGIN, query=True, loaded=True):
        cmds.flushUndo()
        cmds.unloadPlugin(PLUGIN + ".py", force=True)


def _guardar_preferencias(cmds):
    """Guarda ya la carga automática del plug-in y el estante.

    Maya solo guarda sus preferencias al salir bien; si se cuelga o se fuerza
    el cierre justo después de instalar, sin esto Trepadora no se cargaría sola.
    """
    try:
        cmds.savePrefs(general=True, plugins=True)
    except (RuntimeError, TypeError):
        import traceback

        traceback.print_exc()


def ventana_abierta():
    modulo = sys.modules.get("trepadora.ui.ventana")
    return bool(modulo and getattr(modulo, "_ventana", None) is not None)


def desinstalar(carpeta_modulos=None):
    """Quita el .mod, el estante y el plug-in. No borra esta carpeta ni tus preajustes."""
    from maya import cmds

    if ventana_abierta():
        from trepadora.ui import ventana

        ventana.cerrar()
    if cmds.pluginInfo(PLUGIN, query=True, loaded=True):
        cmds.pluginInfo(PLUGIN, edit=True, autoload=False)
        _descargar_plugin(cmds)
    ruta = os.path.join(carpeta_modulos or _carpeta_modulos(), NOMBRE_MOD)
    if os.path.exists(ruta):
        os.remove(ruta)
    if not cmds.about(batch=True) and cmds.shelfLayout(ESTANTE, exists=True):
        cmds.deleteUI(ESTANTE, layout=True)
    archivo_estante = os.path.join(cmds.internalVar(userShelfDir=True),
                                   "shelf_{}.mel".format(ESTANTE))
    if os.path.exists(archivo_estante):
        os.remove(archivo_estante)
    _guardar_preferencias(cmds)
    return ruta


def onMayaDroppedPythonFile(*_):
    """Maya llama a esta función al soltar el archivo sobre el visor."""
    instalar()
