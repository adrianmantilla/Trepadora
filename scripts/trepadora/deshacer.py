"""Ctrl+Z para lo que Trepadora crea con la API de Maya.

Las mallas de la planta se crean con la API (``MFnMesh``), mucho más rápida
que los comandos, pero Maya no apunta en su historial de deshacer lo que se
hace con la API fuera de un comando: Ctrl+Z dejaría tallos y hojas sueltos en
la escena. Por eso la planta se crea con el historial apagado y después se
ejecuta el comando ``trepadoraDeshacer`` (lo registra el plug-in), que sí
queda en el historial: al deshacerlo borra todo lo que se creó, y al rehacerlo
lo vuelve a crear.

Si el plug-in no está cargado, la planta se crea igual, sin este paso.
"""

import traceback

from maya import cmds

COMANDO = "trepadoraDeshacer"
PLUGIN = "trepadora_plugin"
_pendiente = None


def disponible():
    """True si el comando del plug-in existe (si no, intenta cargar el plug-in)."""
    if hasattr(cmds, COMANDO):
        return True
    try:
        cmds.loadPlugin(PLUGIN, quiet=True)
    except Exception:
        return False
    return hasattr(cmds, COMANDO)


def tomar_pendiente():
    """Lo usa el comando del plug-in: las funciones para deshacer y rehacer."""
    global _pendiente
    pendiente, _pendiente = _pendiente, None
    return pendiente


def ejecutar(hacer):
    """Ejecuta ``hacer()`` como un solo paso de Ctrl+Z y devuelve lo que devuelva.

    ``hacer`` tiene que poder repetirse (rehacer la vuelve a llamar) y solo
    debe crear nodos nuevos o cambiar los que crea.
    """
    global _pendiente
    if not disponible():
        return hacer()
    estado = {"creados": []}
    resultado = _crear(hacer, estado["creados"])

    def rehacer():
        estado["creados"] = []
        _crear(hacer, estado["creados"])

    def deshacer():
        _borrar(estado["creados"])

    _pendiente = (rehacer, deshacer)
    try:
        getattr(cmds, COMANDO)()
    except Exception:
        # Sin el paso en el historial lo creado se queda, pero Ctrl+Z no lo quita.
        _pendiente = None
        traceback.print_exc()
    return resultado


class _HistorialApagado(object):
    """Apaga el historial de deshacer sin vaciarlo, y lo deja como estaba."""

    def __enter__(self):
        self.estado = cmds.undoInfo(query=True, state=True)
        cmds.undoInfo(stateWithoutFlush=False)

    def __exit__(self, *_):
        cmds.undoInfo(stateWithoutFlush=self.estado)


def _crear(hacer, creados):
    """Llama a ``hacer()`` con el historial apagado y apunta cada nodo que se crea."""
    import maya.api.OpenMaya as om

    def al_crear(nodo, *_):
        creados.append(om.MObjectHandle(nodo))

    llamada = om.MDGMessage.addNodeAddedCallback(al_crear, "dependNode")
    try:
        with _HistorialApagado():
            try:
                return hacer()
            except BaseException:
                _borrar(creados)
                raise
    finally:
        om.MMessage.removeCallback(llamada)


def _borrar(creados):
    """Borra los nodos apuntados que sigan existiendo."""
    import maya.api.OpenMaya as om

    with _HistorialApagado():
        for asa in creados:
            if not asa.isValid():
                continue
            modificador = om.MDagModifier()
            try:
                modificador.deleteNode(asa.object())
                modificador.doIt()
            except RuntimeError:
                pass
