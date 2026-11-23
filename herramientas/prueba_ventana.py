"""Prueba de la ventana dentro de Maya con interfaz (herramienta de desarrollo).

No forma parte del plugin. Instala Trepadora en una carpeta de módulos de
prueba, pulsa los botones de la ventana como lo haría un estudiante, guarda y
reabre la escena, y deja capturas de la ventana y del visor y un informe JSON.

Conviene lanzarla con una carpeta de preferencias de Maya aparte, para no
tocar las tuyas (estante, plug-ins cargados...)::

    MAYA_APP_DIR=/ruta/maya_prueba TREPADORA_RAIZ=/ruta/Trepadora TREPADORA_SALIDA=/ruta/salida \\
        maya -command "python(\\"exec(open('/ruta/Trepadora/herramientas/prueba_ventana.py').read()); probar_y_salir()\\")"

Después, con la misma MAYA_APP_DIR, ``comprobar_arranque_y_salir()`` mira si
al abrir Maya otra vez el plug-in se carga solo y aparecen el menú y el estante.
"""

import json
import os
import sys
import time
import traceback

from maya import cmds

_RAIZ = os.environ.get("TREPADORA_RAIZ") or os.path.dirname(
    os.path.dirname(os.path.abspath(globals().get("__file__", "."))))
for _carpeta in (_RAIZ, os.path.join(_RAIZ, "herramientas")):
    if _carpeta not in sys.path:
        sys.path.insert(0, _carpeta)

_SALIDA = os.environ.get("TREPADORA_SALIDA", os.path.join(_RAIZ, "capturas", "ventana"))
_informe = {"pasos": {}, "errores": {}}


def _paso(nombre, funcion, *args, **kwargs):
    """Ejecuta un paso; apunta su resultado o el error y sigue."""
    inicio = time.time()
    try:
        resultado = funcion(*args, **kwargs)
        _informe["pasos"][nombre] = {"ok": True, "segundos": round(time.time() - inicio, 2),
                                     "datos": resultado}
        return resultado
    except Exception:
        _informe["pasos"][nombre] = {"ok": False, "segundos": round(time.time() - inicio, 2)}
        _informe["errores"][nombre] = traceback.format_exc()
        return None


def _procesar():
    from PySide6 import QtWidgets

    QtWidgets.QApplication.processEvents()
    cmds.refresh(force=True)


def _captura_ventana(v, nombre):
    _procesar()
    ruta = os.path.join(_SALIDA, "ventana_{}.png".format(nombre))
    v.grab().save(ruta)
    return ruta


def _vista(ojo, mira, fov=40):
    import capturas_maya as cm

    cm.configurar_visor()
    panel = cm._panel_con_camara("persp")
    cmds.viewPlace("persp", eye=ojo, lookAt=mira, perspective=True)
    cmds.camera("persp", edit=True, horizontalFieldOfView=fov)
    cmds.modelEditor(panel, edit=True, locators=True, nurbsCurves=True)
    _procesar()
    return panel


def _captura_visor(nombre, ancho=1280, alto=760):
    ruta = os.path.join(_SALIDA, "visor_{}.png".format(nombre))
    cmds.select(clear=True)
    _procesar()
    cmds.playblast(frame=[1], format="image", compression="png", viewer=False,
                   showOrnaments=False, widthHeight=(ancho, alto), percent=100,
                   completeFilename=ruta, forceOverwrite=True, offScreen=True)
    return ruta


def _resumen_sesion(v):
    s = v.sesion
    return {"superficies": [x.split("|")[-1] for x in s.superficies_validas()],
            "origenes": [[round(c, 2) for c in cmds.xform(o, q=True, ws=True, t=True)]
                         for o in s.origenes()],
            "estado": s.estado(), "pasos": s.ajustes["pasos"], "semilla": s.ajustes["semilla"],
            "largo_ramas": s.ajustes["longitud_max"], "motivo_parada": s.motivo_parada(),
            "mensaje": v.mensaje.text(), "pie": v.estado_pie.text()}


def _curvas_vista_previa(v):
    grupo = v.sesion.vista_previa
    if not grupo or not cmds.objExists(grupo):
        return 0
    return len(cmds.listRelatives(grupo, children=True) or [])


# ------------------------------------------------------------------- pasos
def instalar_prueba():
    import instalar

    modulos = os.path.join(_SALIDA, "modules")
    datos = instalar.instalar(carpeta_modulos=modulos, estante=True, abrir=False, dialogo=False)
    from trepadora import menu

    items = cmds.menu(menu.MENU, query=True, itemArray=True) or []
    datos.update(
        plugin_cargado=cmds.pluginInfo(instalar.PLUGIN, query=True, loaded=True),
        autoload=cmds.pluginInfo(instalar.PLUGIN, query=True, autoload=True),
        menu=cmds.menu(menu.MENU, exists=True),
        menu_items=[cmds.menuItem(i, query=True, label=True) for i in items
                    if not cmds.menuItem(i, query=True, divider=True)],
        estante=cmds.shelfLayout(instalar.ESTANTE, exists=True),
        botones_estante=len(cmds.shelfLayout(instalar.ESTANTE, query=True, childArray=True)
                            or []) if cmds.shelfLayout(instalar.ESTANTE, exists=True) else 0,
        contenido_mod=open(datos["mod"], encoding="utf-8").read())
    return datos


def abrir_ventana():
    from trepadora import menu
    from trepadora.ui import ventana

    v = menu.abrir()
    _procesar()
    otra = ventana.mostrar()
    return v, {"misma_al_abrir_dos_veces": otra is v,
               "control": cmds.workspaceControl(ventana.CONTROL, exists=True),
               "captura": _captura_ventana(v, "1_inicio")}


def escena_sencilla(v):
    cmds.file(new=True, force=True)
    _procesar()
    v.escena_de_prueba("sencilla")
    return _resumen_sesion(v)


def origen_por_clic(v):
    """Coloca un origen en el muro como si se hiciera clic: primero llamando a la
    función del clic con las coordenadas del visor, después con un clic de verdad."""
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaUI as omui

    _vista((0, 80, 330), (0, 70, 0))
    datos = {}
    vista = omui.M3dView.active3dView()
    objetivo = om.MPoint(40.0, 90.0, 5.0)
    x, y, dentro = vista.worldToView(objetivo)
    datos["pixel"] = [x, y, dentro]
    datos["visor"] = [vista.portWidth(), vista.portHeight()]
    antes = len(v.sesion.origenes())
    v.boton_clic.click()
    datos["herramienta_activa"] = cmds.currentCtx()
    v._al_clic(x, y)
    nuevos = v.sesion.origenes()[antes:]
    datos["por_funcion"] = [[round(c, 2) for c in cmds.xform(o, q=True, ws=True, t=True)]
                            for o in nuevos]
    datos["mensaje_funcion"] = v.mensaje.text()
    # Clic de verdad sobre el visor (para ver si coinciden los píxeles en pantallas Retina).
    try:
        from PySide6 import QtCore, QtWidgets
        from PySide6.QtTest import QTest
        from shiboken6 import wrapInstance

        widget = wrapInstance(int(vista.widget()), QtWidgets.QWidget)
        proporcion = widget.devicePixelRatioF()
        datos["proporcion_pixeles"] = proporcion
        datos["widget"] = [widget.width(), widget.height()]
        antes = len(v.sesion.origenes())
        punto = QtCore.QPoint(int(round(x / proporcion)),
                              int(round(widget.height() - y / proporcion)))
        QTest.mouseClick(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, punto)
        _procesar()
        nuevos = v.sesion.origenes()[antes:]
        datos["por_clic"] = [[round(c, 2) for c in cmds.xform(o, q=True, ws=True, t=True)]
                             for o in nuevos]
        datos["mensaje_clic"] = v.mensaje.text()
    except Exception:
        datos["clic_error"] = traceback.format_exc()
    # Un clic fuera de la superficie (al cielo) debe avisar sin crear nada.
    antes = len(v.sesion.origenes())
    v._al_clic(5, vista.portHeight() - 5)
    datos["fuera_crea"] = len(v.sesion.origenes()) - antes
    datos["mensaje_fuera"] = v.mensaje.text()
    v.boton_clic.click()
    datos["herramienta_despues"] = cmds.currentCtx()
    datos["captura"] = _captura_ventana(v, "2_origenes")
    return datos


def crecer(v):
    v.controles["pasos"].casilla.setValue(220)
    v.boton_crecer.click()
    datos = _resumen_sesion(v)
    datos["curvas"] = _curvas_vista_previa(v)
    _vista((-150, 120, 260), (0, 70, 0))
    datos["visor"] = _captura_visor("1_crecer")
    datos["captura"] = _captura_ventana(v, "3_crecer")
    return datos


def crecer_mas(v):
    puntos = v.sesion.estado().get("puntos", 0)
    v.boton_mas.click()
    datos = _resumen_sesion(v)
    datos["puntos_antes"] = puntos
    datos["curvas"] = _curvas_vista_previa(v)
    datos["control_pasos"] = v.controles["pasos"].valor()
    datos["visor"] = _captura_visor("2_crecer_mas")
    return datos


def preajuste(v, nombre):
    combo = v.combo_preajustes
    indice = [combo.itemText(i) for i in range(combo.count())].index(nombre)
    combo.setCurrentIndex(indice)
    v._elegir_preajuste()
    v.boton_crecer.click()
    datos = _resumen_sesion(v)
    datos["ajustes"] = dict(v.sesion.ajustes)
    datos["visor"] = _captura_visor("3_" + nombre.replace(" ", "_"))
    return datos


def crear_malla(v, nombre="4_malla"):
    v.boton_malla.click()
    datos = _resumen_sesion(v)
    planta = v.sesion.ultima_planta
    datos["planta"] = planta
    if planta and cmds.objExists(planta):
        datos["hijos"] = [h.split("|")[-1] for h in
                          cmds.listRelatives(planta, children=True, fullPath=True) or []]
        datos["ajustes_guardados"] = cmds.attributeQuery("trepadoraAjustes", node=planta,
                                                         exists=True)
        datos["instanciadores"] = len(cmds.ls(type="instancer") or [])
        datos["vista_previa_borrada"] = not cmds.objExists(v.sesion.vista_previa or "x")
    datos["visor"] = _captura_visor(nombre)
    datos["captura"] = _captura_ventana(v, nombre)
    return datos


def deshacer(v):
    planta = v.sesion.ultima_planta
    cmds.undo()
    _procesar()
    quitada = not cmds.objExists(planta)
    cmds.redo()
    _procesar()
    return {"deshacer_quita_la_planta": quitada, "rehacer_la_devuelve": cmds.objExists(planta)}


def guardar_y_reabrir(v):
    ruta = os.path.join(_SALIDA, "prueba_ventana.ma")
    cmds.file(rename=ruta)
    cmds.file(save=True, type="mayaAscii", force=True)
    antes = _resumen_sesion(v)
    cmds.file(new=True, force=True)
    _procesar()
    vacia = _resumen_sesion(v)
    cmds.file(ruta, open=True, force=True)
    _procesar()
    despues = _resumen_sesion(v)
    return {"antes": antes, "escena_nueva": vacia, "reabierta": despues,
            "mb": round(os.path.getsize(ruta) / 1e6, 1)}


def ajustes_de_planta(v):
    plantas = cmds.ls("trepadora_planta_grp*", type="transform", long=True) or []
    cmds.select(plantas[-1], replace=True)
    v.controles["semilla"].poner(999)
    v._ajustes_de_planta()
    return {"plantas": len(plantas), "semilla": v.controles["semilla"].valor(),
            "mensaje": v.mensaje.text()}


def guardar_preajuste(v):
    from PySide6 import QtWidgets

    original = QtWidgets.QInputDialog.getText
    QtWidgets.QInputDialog.getText = staticmethod(lambda *a, **k: ("Prueba del aula", True))
    try:
        v._guardar_preajuste()
    finally:
        QtWidgets.QInputDialog.getText = original
    carpeta = v.carpeta_preajustes()
    combo = v.combo_preajustes
    return {"carpeta": carpeta, "archivos": sorted(os.listdir(carpeta)),
            "elegido": combo.currentText(),
            "en_lista": [combo.itemText(i) for i in range(combo.count())]}


def hoja_propia(v):
    cmds.file(new=True, force=True)
    v.escena_de_prueba("sencilla")
    hoja = cmds.polyPlane(name="mi_hoja", width=0.6, height=1.0, subdivisionsX=1,
                          subdivisionsY=1, axis=(0, 0, 1))[0]
    cmds.move(0, 0.5, 0, hoja)
    cmds.makeIdentity(hoja, apply=True, translate=True)
    cmds.select(hoja, replace=True)
    v._usar_hoja_propia()
    v.controles["pasos"].casilla.setValue(150)
    v.boton_malla.click()
    datos = _resumen_sesion(v)
    datos["hoja"] = v.estado_hoja.text()
    datos["modelos"] = cmds.ls("trepadora_hoja_propia*", type="transform")
    return datos


def ruina(v):
    cmds.file(new=True, force=True)
    v.escena_de_prueba("ruina")
    datos = {"preparada": _resumen_sesion(v), "escala": v.sesion.ajustes["escala"]}
    inicio = time.time()
    v.boton_crecer.click()
    datos["crecer_s"] = round(time.time() - inicio, 2)
    datos["crecida"] = _resumen_sesion(v)
    inicio = time.time()
    v.boton_malla.click()
    datos["malla_s"] = round(time.time() - inicio, 2)
    datos["malla"] = _resumen_sesion(v)
    datos["materiales_tono"] = sorted(cmds.ls("trepadora_hojas_tono*_mat") or [])
    datos["colores_tono"] = [[round(c, 3) for c in cmds.getAttr(m + ".color")[0]]
                             for m in datos["materiales_tono"]]
    _vista((-260, 220, 520), (20, 110, 40), 42)
    datos["visor"] = _captura_visor("5_ruina")
    datos["captura"] = _captura_ventana(v, "5_ruina")
    return datos


def recargar_plugin():
    import instalar
    from trepadora import menu

    cmds.unloadPlugin(instalar.PLUGIN + ".py")
    sin = cmds.menu(menu.MENU, exists=True)
    cmds.loadPlugin(os.path.join(_RAIZ, "plug-ins", instalar.PLUGIN + ".py"))
    cmds.evalDeferred("pass")
    _procesar()
    from trepadora import menu as menu2

    menu2.crear()
    return {"menu_tras_descargar": sin, "menu_tras_cargar": cmds.menu(menu2.MENU, exists=True)}


def probar():
    if not os.path.isdir(_SALIDA):
        os.makedirs(_SALIDA)
    _informe["maya"] = cmds.about(version=True)
    _informe["so"] = cmds.about(operatingSystem=True)
    _informe["app_dir"] = cmds.internalVar(userAppDir=True)
    _paso("instalar", instalar_prueba)
    abierta = _paso("abrir_ventana", abrir_ventana)
    if abierta:
        v, _informe["pasos"]["abrir_ventana"]["datos"] = abierta
        _paso("escena_sencilla", escena_sencilla, v)
        _paso("origen_por_clic", origen_por_clic, v)
        _paso("crecer", crecer, v)
        _paso("crecer_mas", crecer_mas, v)
        _paso("preajuste_colgante", preajuste, v, "Enredadera colgante")
        _paso("preajuste_fachada", preajuste, v, "Hiedra de fachada")
        _paso("crear_malla", crear_malla, v)
        _paso("deshacer", deshacer, v)
        _paso("guardar_y_reabrir", guardar_y_reabrir, v)
        from trepadora.ui import ventana

        v = ventana._ventana
        _paso("ajustes_de_planta", ajustes_de_planta, v)
        _paso("guardar_preajuste", guardar_preajuste, v)
        _paso("hoja_propia", hoja_propia, v)
        _paso("ruina", ruina, v)
    _paso("recargar_plugin", recargar_plugin)
    return _informe


def _escribir(nombre):
    with open(os.path.join(_SALIDA, nombre), "w", encoding="utf-8") as f:
        json.dump(_informe, f, ensure_ascii=False, indent=1, default=str)


def probar_y_salir():
    def hacer():
        try:
            probar()
        except Exception:
            _informe["errores"]["general"] = traceback.format_exc()
        finally:
            _escribir("prueba_ventana.json")
            sys.stdout.flush()
            os._exit(0)

    if not os.path.isdir(_SALIDA):
        os.makedirs(_SALIDA)
    # Cuando Maya haya terminado de arrancar y de dibujar su ventana.
    cmds.evalDeferred(lambda: cmds.evalDeferred(hacer, lowestPriority=True), lowestPriority=True)


def comprobar_arranque():
    """Segunda vez que se abre Maya con las mismas preferencias: ¿está todo sin reinstalar?"""
    from trepadora import menu

    return {"plugin_cargado": cmds.pluginInfo("trepadora_plugin", query=True, loaded=True),
            "menu": cmds.menu(menu.MENU, exists=True),
            "estante": cmds.shelfLayout("Trepadora", exists=True),
            "modulo": cmds.moduleInfo(path=True, moduleName="Trepadora")
            if "Trepadora" in (cmds.moduleInfo(listModules=True) or []) else None,
            "ventana": _abrir_y_capturar()}


def _abrir_y_capturar():
    from trepadora import menu

    v = menu.abrir()
    return {"ajustes_recordados": v.sesion.ajustes["semilla"],
            "captura": _captura_ventana(v, "6_arranque")}


def comprobar_arranque_y_salir():
    def hacer():
        try:
            _informe["arranque"] = comprobar_arranque()
        except Exception:
            _informe["errores"]["arranque"] = traceback.format_exc()
        finally:
            _escribir("prueba_arranque.json")
            sys.stdout.flush()
            os._exit(0)

    # Después de que el plug-in haya creado el menú (también va diferido).
    cmds.evalDeferred(lambda: cmds.evalDeferred(hacer, lowestPriority=True), lowestPriority=True)
