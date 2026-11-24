"""Menú «Trepadora» en la barra principal de Maya (lo crea el plug-in al cargarse)."""

import os

from maya import cmds, mel

from . import __version__
from .i18n import idioma, t, usar_idioma

MENU = "trepadoraMenu"
OPCION_IDIOMA = "trepadoraIdioma"
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Cada idioma se nombra en su propia lengua.
NOMBRES_IDIOMA = {"es": "Español", "en": "English"}


def idioma_guardado():
    """Usa el idioma elegido en las preferencias de Maya, si hay uno."""
    if cmds.optionVar(exists=OPCION_IDIOMA):
        usar_idioma(cmds.optionVar(query=OPCION_IDIOMA))


def crear():
    if cmds.about(batch=True):
        return
    idioma_guardado()
    borrar()
    from . import pack

    pack.crear_menu(MENU, t("menu_titulo"), padre=mel.eval("$tmp = $gMainWindow"))
    cmds.menuItem(label=t("menu_abrir"), annotation=t("ayuda_menu_abrir"),
                  command=lambda *_: abrir())
    cmds.menuItem(divider=True, dividerLabel=t("menu_escenas"))
    cmds.menuItem(label=t("menu_escena_sencilla"), annotation=t("ayuda_menu_escena"),
                  command=lambda *_: escena_de_prueba("sencilla"))
    cmds.menuItem(label=t("menu_escena_ruina"), annotation=t("ayuda_menu_escena"),
                  command=lambda *_: escena_de_prueba("ruina"))
    cmds.menuItem(divider=True)
    cmds.menuItem(label=t("menu_exportar"), annotation=t("ayuda_menu_exportar"),
                  command=lambda *_: exportar_seleccion())
    cmds.menuItem(label=t("menu_exportar_ligeras"), annotation=t("ayuda_menu_exportar_ligeras"),
                  command=lambda *_: exportar_seleccion(ligeras=True))
    cmds.menuItem(divider=True)
    cmds.menuItem(label=t("menu_idioma"), subMenu=True)
    cmds.radioMenuItemCollection()
    for codigo in idiomas_del_menu():
        cmds.menuItem(label=NOMBRES_IDIOMA.get(codigo, codigo), radioButton=codigo == idioma(),
                      command=lambda *_, c=codigo: cambiar_idioma(c))
    cmds.setParent("..", menu=True)
    cmds.menuItem(label=t("menu_acerca"), command=lambda *_: acerca_de())


def idiomas_del_menu():
    from .i18n import idiomas

    return idiomas()


def cambiar_idioma(codigo):
    """Cambia el idioma de Trepadora, lo recuerda y rehace el menú y la ventana."""
    cmds.optionVar(stringValue=(OPCION_IDIOMA, codigo))
    usar_idioma(codigo)
    from .ui import ventana

    anterior = ventana._ventana
    abierta = anterior is not None and ventana._valida(anterior)
    sesion = anterior.sesion if abierta else None
    if abierta:
        ventana.cerrar()
    # El menú no se puede borrar mientras se ejecuta una de sus órdenes.
    cmds.evalDeferred(crear)
    if abierta:
        cmds.evalDeferred(lambda: ventana.mostrar(sesion=sesion))
    print(t("idioma_cambiado"))


def borrar():
    from . import pack

    pack.quitar_menu(MENU)


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


def exportar_seleccion(ligeras=False):
    """Pide dónde guardar la planta seleccionada y la exporta (FBX o Alembic).

    Con ``ligeras``, las hojas van como tarjetas con transparencia (juegos).
    """
    from . import exportar, texturas
    from .ajustes import Aviso

    if exportar.planta_de() is None:
        cmds.warning(t("sin_planta_seleccionada"))
        return None
    rutas = cmds.fileDialog2(caption=t("exportar_titulo"), fileMode=0, dialogStyle=2,
                             fileFilter=t("exportar_filtro"))
    if not rutas:
        return None
    try:
        informe = exportar.exportar(rutas[0], resolucion=texturas.resolucion_actual(),
                                    ligeras=ligeras)
    except Aviso as aviso:
        cmds.warning(str(aviso))
        return None
    except (RuntimeError, OSError) as error:
        cmds.warning(t("exportar_error", error=str(error).strip()))
        return None
    print(t("exportado", archivo=os.path.basename(informe["ruta"]), n=len(informe["texturas"]),
            carpeta=os.path.basename(informe["carpeta"])))
    if ligeras:
        if informe.get("ligeras"):
            print(t("exportado_ligeras", n=informe["hojas_vertices"]))
        else:
            cmds.warning(t("exportado_sin_ligeras"))
    if informe["sin_color"]:
        cmds.warning(t("exportado_sin_color", juegos=", ".join(informe["sin_color"])))
    return informe


def acerca_de():
    cmds.confirmDialog(title=t("menu_acerca"),
                       message=t("acerca_texto", version=__version__, carpeta=RAIZ),
                       button=[t("boton_aceptar")])
