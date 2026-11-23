"""Plug-in de Maya de Trepadora: al cargarse añade el menú «Trepadora».

Lo carga el instalador (``instalar.py``) y queda marcado para cargarse solo
cada vez que se abre Maya. También se puede cargar a mano desde
Windows > Settings/Preferences > Plug-in Manager.
"""

import os
import sys

import maya.api.OpenMaya as om
from maya import cmds

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if os.path.isdir(_SCRIPTS) and _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


def maya_useNewAPI():
    """Le dice a Maya que este plug-in usa la API 2.0."""


def initializePlugin(objeto):
    from trepadora import __version__

    om.MFnPlugin(objeto, "Trepadora", __version__)
    if not cmds.about(batch=True):
        from trepadora import menu

        # Al arrancar Maya la barra de menús puede no existir todavía.
        cmds.evalDeferred(menu.crear)


def uninitializePlugin(objeto):
    om.MFnPlugin(objeto)
    if not cmds.about(batch=True):
        from trepadora import menu
        from trepadora.ui import ventana

        ventana.cerrar()
        menu.borrar()
