"""Herramienta del visor para colocar orígenes con un clic (paso 2 de la ventana)."""

from maya import cmds

CONTEXTO = "trepadoraOrigenCtx"
_al_pulsar = None


def activar(al_pulsar):
    """Activa la herramienta: cada clic en el visor llama a ``al_pulsar(x, y, panel)``.

    ``x`` e ``y`` son píxeles del visor (origen abajo a la izquierda), los que
    espera ``M3dView.viewToWorld``; ``panel`` es el visor donde se hizo clic.
    """
    global _al_pulsar
    _al_pulsar = al_pulsar
    if not cmds.draggerContext(CONTEXTO, exists=True):
        cmds.draggerContext(CONTEXTO, pressCommand=_pulsar, cursor="crossHair",
                            space="screen", undoMode="step")
    cmds.setToolTo(CONTEXTO)


def _pulsar(*_):
    x, y, _z = cmds.draggerContext(CONTEXTO, query=True, anchorPoint=True)
    if _al_pulsar is not None:
        _al_pulsar(x, y, panel_bajo_el_cursor())


def panel_bajo_el_cursor():
    """El visor 3D donde está el ratón, o None si no es un visor."""
    panel = cmds.getPanel(underPointer=True) or cmds.getPanel(withFocus=True)
    if panel and cmds.getPanel(typeOf=panel) == "modelPanel":
        return panel
    return None


def activa():
    return cmds.currentCtx() == CONTEXTO


def desactivar():
    """Vuelve a la herramienta de selección si la nuestra estaba activa."""
    if activa():
        cmds.setToolTo("selectSuperContext")
