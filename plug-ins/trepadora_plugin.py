"""Plug-in de Maya de Trepadora: al cargarse añade el menú «Trepadora».

Lo carga el instalador (``instalar.py``) y queda marcado para cargarse solo
cada vez que se abre Maya. También se puede cargar a mano desde
Windows > Settings/Preferences > Plug-in Manager.

Registra además el comando ``trepadoraDeshacer``, que hace que Ctrl+Z quite
de una vez la planta creada con «Crear malla» (ver ``trepadora/deshacer.py``).
"""

import os
import sys
import traceback

import maya.api.OpenMaya as om
from maya import cmds

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if os.path.isdir(_SCRIPTS) and _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

COMANDO_DESHACER = "trepadoraDeshacer"


def maya_useNewAPI():
    """Le dice a Maya que este plug-in usa la API 2.0."""


class _PasoDeshacer(om.MPxCommand):
    """Un paso del historial de deshacer para lo que Trepadora crea con la API."""

    def __init__(self):
        om.MPxCommand.__init__(self)
        self._rehacer = None
        self._deshacer = None

    def doIt(self, _argumentos):
        from trepadora import deshacer

        pendiente = deshacer.tomar_pendiente()
        if pendiente is None:
            raise RuntimeError("{} solo lo usa Trepadora por dentro.".format(COMANDO_DESHACER))
        # Lo creado ya está hecho: aquí solo se apunta cómo deshacerlo y rehacerlo.
        self._rehacer, self._deshacer = pendiente

    def undoIt(self):
        self._llamar(self._deshacer)

    def redoIt(self):
        self._llamar(self._rehacer)

    def isUndoable(self):
        return True

    @staticmethod
    def crear():
        """Lo llama Maya cada vez que se ejecuta el comando."""
        return _PasoDeshacer()

    @staticmethod
    def _llamar(funcion):
        try:
            funcion()
        except Exception:
            om.MGlobal.displayWarning("Trepadora: " + traceback.format_exc().strip().splitlines()[-1])


def initializePlugin(objeto):
    from trepadora import __version__

    plugin = om.MFnPlugin(objeto, "Trepadora", __version__)
    plugin.registerCommand(COMANDO_DESHACER, _PasoDeshacer.crear)
    if not cmds.about(batch=True):
        from trepadora import menu

        # Al arrancar Maya la barra de menús puede no existir todavía.
        cmds.evalDeferred(menu.crear)


def uninitializePlugin(objeto):
    plugin = om.MFnPlugin(objeto)
    if not cmds.about(batch=True):
        from trepadora import menu

        menu.borrar()
        try:
            from trepadora.ui import ventana

            ventana.cerrar()
        except Exception:
            om.MGlobal.displayWarning("Trepadora: " + traceback.format_exc().strip().splitlines()[-1])
    plugin.deregisterCommand(COMANDO_DESHACER)
