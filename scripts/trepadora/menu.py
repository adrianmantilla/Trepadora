"""Menú «Trepadora» en la barra principal de Maya (lo crea el plug-in al cargarse)."""

import os

from maya import cmds, mel

from . import __version__
from .i18n import t, usar_idioma

MENU = "trepadoraMenu"
OPCION_IDIOMA = "trepadoraIdioma"
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def idioma_guardado():
    """Usa el idioma elegido en las preferencias de Maya, si hay uno."""
    if cmds.optionVar(exists=OPCION_IDIOMA):
        usar_idioma(cmds.optionVar(query=OPCION_IDIOMA))


def crear():
    if cmds.about(batch=True):
        return
    idioma_guardado()
    borrar()
    principal = mel.eval("$tmp = $gMainWindow")
    cmds.menu(MENU, label=t("menu_titulo"), parent=principal, tearOff=True)
    cmds.menuItem(label=t("menu_abrir"), annotation=t("ayuda_menu_abrir"),
                  command=lambda *_: abrir())
    cmds.menuItem(divider=True, dividerLabel=t("menu_escenas"))
    cmds.menuItem(label=t("menu_escena_sencilla"), annotation=t("ayuda_menu_escena"),
                  command=lambda *_: escena_de_prueba("sencilla"))
    cmds.menuItem(label=t("menu_escena_ruina"), annotation=t("ayuda_menu_escena"),
                  command=lambda *_: escena_de_prueba("ruina"))
    cmds.menuItem(divider=True)
    cmds.menuItem(label=t("menu_acerca"), command=lambda *_: acerca_de())


def borrar():
    if cmds.menu(MENU, exists=True):
        cmds.deleteUI(MENU)


def abrir():
    from .ui import ventana

    return ventana.mostrar()


def escena_de_prueba(nombre):
    """Escena nueva (pregunta si guardar la actual) con la escena de prueba lista para crecer."""
    if cmds.file(query=True, modified=True):
        respuesta = cmds.confirmDialog(
            title=t("ventana_titulo"), message=t("confirmar_escena_nueva"),
            button=[t("boton_guardar"), t("boton_no_guardar"), t("boton_cancelar")],
            defaultButton=t("boton_guardar"), cancelButton=t("boton_cancelar"),
            dismissString=t("boton_cancelar"))
        if respuesta == t("boton_cancelar"):
            return None
        if respuesta == t("boton_guardar"):
            if not cmds.file(query=True, sceneName=True):
                mel.eval("SaveSceneAs")
                if cmds.file(query=True, modified=True):
                    return None
            else:
                cmds.file(save=True)
    cmds.file(new=True, force=True)
    ventana = abrir()
    ventana.escena_de_prueba(nombre)
    return ventana


def acerca_de():
    cmds.confirmDialog(title=t("menu_acerca"),
                       message=t("acerca_texto", version=__version__, carpeta=RAIZ),
                       button=[t("boton_aceptar")])
