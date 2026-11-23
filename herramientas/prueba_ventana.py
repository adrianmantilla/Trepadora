"""Prueba de la ventana dentro de Maya con interfaz (herramienta de desarrollo).

No forma parte del plugin. Instala Trepadora en una carpeta de módulos de
prueba, pulsa los botones de la ventana como lo haría un estudiante, guarda y
reabre la escena, y deja capturas de la ventana y del visor y un informe JSON.

Conviene lanzarla con una carpeta de preferencias de Maya aparte, para no
tocar las tuyas (estante, plug-ins cargados...)::

    MAYA_APP_DIR=/ruta/maya_prueba TREPADORA_RAIZ=/ruta/Trepadora TREPADORA_SALIDA=/ruta/salida \\
        maya -command "python(\\"exec(open('/ruta/Trepadora/herramientas/prueba_ventana.py').read()); probar_y_salir()\\")"

Con MAYA_APP_DIR instala soltando ``instalar.py`` sobre el visor, como un
estudiante (``TREPADORA_SOLTAR=0`` para importarlo sin más). Apunta además
cada ventana que abre Maya, como el aviso de seguridad de Maya 2027 al cargar
el plug-in, y los ajustes y registros de seguridad.

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
    _informe["paso_actual"] = nombre
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


def _seguridad():
    """Ajustes de seguridad de Maya 2027 y lo que dicen sus registros de Trepadora."""
    variables = {}
    for nombre in cmds.optionVar(list=True) or []:
        if any(c in nombre.lower() for c in ("secur", "trust", "safe")):
            try:
                variables[nombre] = cmds.optionVar(query=nombre)
            except Exception:
                variables[nombre] = "?"
    registros = {}
    raiz = os.environ.get("MAYA_APP_DIR", "")
    for carpeta, _, archivos in os.walk(raiz) if raiz else ():
        for nombre in archivos:
            if "secur" not in nombre.lower():
                continue
            ruta = os.path.join(carpeta, nombre)
            try:
                with open(ruta, encoding="utf-8", errors="replace") as f:
                    lineas = [x.strip()[:300] for x in f if "trepadora" in x.lower()]
            except OSError:
                lineas = ["(no se pudo leer)"]
            registros[os.path.relpath(ruta, raiz)] = lineas[-20:]
    return {"optionVars": variables, "registros": registros}


_vistos = set()
_inicio = time.time()
_vigia = None


def _vigilar():
    """Apunta cada ventana nueva que abre Maya (avisos de seguridad, errores...).

    Sigue funcionando mientras Maya espera en un diálogo.
    """
    from PySide6 import QtWidgets

    try:
        principal = cmds.about(application=True)
    except Exception:
        principal = ""
    for w in QtWidgets.QApplication.topLevelWidgets():
        titulo = w.windowTitle()
        if not w.isVisible() or not titulo or titulo.startswith("Autodesk Maya") \
                or principal and titulo.startswith(principal):
            continue
        clave = (type(w).__name__, titulo, w.objectName())
        if clave in _vistos:
            continue
        _vistos.add(clave)
        dialogos = _informe.setdefault("dialogos", [])
        captura = os.path.join(_SALIDA, "dialogo_{}.png".format(len(dialogos) + 1))
        try:
            w.grab().save(captura)
        except Exception:
            captura = None
        dialogos.append({
            "t": round(time.time() - _inicio, 1), "paso": _informe.get("paso_actual"),
            "clase": clave[0], "titulo": titulo, "nombre": clave[2],
            "textos": [x.text()[:600] for x in w.findChildren(QtWidgets.QLabel) if x.text()][:12],
            "botones": [x.text() for x in w.findChildren(QtWidgets.QAbstractButton)
                        if x.text()][:12], "captura": captura})


def _empezar_vigia():
    global _vigia
    from PySide6 import QtCore

    _vigia = QtCore.QTimer()
    _vigia.timeout.connect(_vigilar)
    _vigia.start(500)


# ------------------------------------------------------------------- pasos
def _soltar_instalador():
    """Instala como un estudiante: suelta ``instalar.py`` sobre el visor.

    Lo hace la misma función de Maya que atiende el arrastrar y soltar. El
    diálogo final del instalador se apunta en vez de mostrarse (esperaría a
    que alguien pulse Aceptar). Devuelve lo que se pudo saber, o None si esta
    Maya no tiene esa función.
    """
    try:
        from maya.app.general import executeDroppedPythonFile as soltar
    except ImportError:
        return None
    dialogos = []
    original = cmds.confirmDialog

    def dialogo(*_a, **k):
        dialogos.append({"titulo": k.get("title"), "mensaje": k.get("message")})
        return k.get("button", [""])[0] if isinstance(k.get("button"), list) else ""

    import maya.api.OpenMaya as om

    mensajes = []
    escucha = om.MCommandMessage.addCommandOutputCallback(
        lambda texto, tipo, *_: mensajes.append(texto.strip()[:400]) if texto.strip() else None)
    sys.modules.pop("instalar", None)  # que lo cargue Maya, no el que ya importó esta prueba
    cmds.confirmDialog = dialogo
    try:
        soltar.executeDroppedPythonFile(os.path.join(_RAIZ, "instalar.py"), "")
    finally:
        cmds.confirmDialog = original
        om.MMessage.removeCallback(escucha)
    return {"como": "soltado", "dialogos": dialogos, "mensajes": mensajes[-30:]}


def instalar_prueba():
    # Con una carpeta de preferencias aparte (MAYA_APP_DIR), en su carpeta de módulos,
    # soltando instalar.py como un estudiante; si no, en la carpeta de salida, para no
    # tocar nada.
    datos = None
    if os.environ.get("MAYA_APP_DIR") and os.environ.get("TREPADORA_SOLTAR", "1") != "0":
        try:
            datos = _soltar_instalador()
        except Exception:
            _informe["errores"]["soltar_instalador"] = traceback.format_exc()
    import instalar

    if datos is None:
        modulos = None if os.environ.get("MAYA_APP_DIR") else os.path.join(_SALIDA, "modules")
        datos = instalar.instalar(carpeta_modulos=modulos, estante=True, abrir=False,
                                  dialogo=False)
        datos["como"] = "importado"
    else:
        datos["mod"] = os.path.join(instalar._carpeta_modulos(), instalar.NOMBRE_MOD)
    from trepadora import menu

    items = cmds.menu(menu.MENU, query=True, itemArray=True) or []
    datos.update(
        plugin_cargado=cmds.pluginInfo(instalar.PLUGIN, query=True, loaded=True),
        autoload=cmds.pluginInfo(instalar.PLUGIN, query=True, autoload=True),
        comando_deshacer=_hay_comando_deshacer(),
        menu=cmds.menu(menu.MENU, exists=True),
        menu_items=[cmds.menuItem(i, query=True, label=True) for i in items
                    if not cmds.menuItem(i, query=True, divider=True)],
        estante=cmds.shelfLayout(instalar.ESTANTE, exists=True),
        botones_estante=len(cmds.shelfLayout(instalar.ESTANTE, query=True, childArray=True)
                            or []) if cmds.shelfLayout(instalar.ESTANTE, exists=True) else 0,
        contenido_mod=open(datos["mod"], encoding="utf-8").read()
        if os.path.exists(datos["mod"]) else None,
        seguridad=_seguridad())
    return datos


def _hay_comando_deshacer():
    from maya import mel

    return bool(mel.eval('exists "trepadoraDeshacer"'))


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


def _clic_qt(widget, x, y):
    """Clic de ratón de verdad (eventos de Qt) en el píxel (x, y) del visor, origen abajo."""
    from PySide6 import QtCore, QtGui, QtWidgets

    proporcion = widget.devicePixelRatioF()
    local = QtCore.QPoint(int(round(x / proporcion)), int(round(widget.height() - y / proporcion)))
    destino = widget.childAt(local) or widget
    punto = destino.mapFrom(widget, local) if destino is not widget else local
    global_ = destino.mapToGlobal(punto)
    for tipo, botones in ((QtCore.QEvent.MouseButtonPress, QtCore.Qt.LeftButton),
                          (QtCore.QEvent.MouseButtonRelease, QtCore.Qt.NoButton)):
        evento = QtGui.QMouseEvent(tipo, QtCore.QPointF(punto), QtCore.QPointF(global_),
                                   QtCore.Qt.LeftButton, botones, QtCore.Qt.NoModifier)
        QtWidgets.QApplication.sendEvent(destino, evento)
        _procesar()
    return {"proporcion_pixeles": proporcion, "widget": [widget.width(), widget.height()],
            "destino": destino.metaObject().className(), "punto_qt": [punto.x(), punto.y()]}


def origen_por_clic(v):
    """Coloca un origen en el muro como si se hiciera clic: primero llamando a la
    función del clic con las coordenadas del visor, después con un clic de verdad."""
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaUI as omui
    from trepadora.ui import herramienta

    panel = _vista((0, 80, 330), (0, 70, 0))
    datos = {"panel": panel, "visibles": cmds.getPanel(visiblePanels=True)}
    vista = omui.M3dView.getM3dViewFromModelPanel(panel)
    activa = omui.M3dView.active3dView()
    datos["visor"] = [vista.portWidth(), vista.portHeight()]
    datos["visor_activo"] = [activa.portWidth(), activa.portHeight()]
    objetivo = om.MPoint(40.0, 90.0, 5.0)
    x, y, dentro = vista.worldToView(objetivo)
    datos["pixel"] = [x, y, dentro]
    antes = len(v.sesion.origenes())
    v.boton_clic.click()
    datos["herramienta_activa"] = cmds.currentCtx()
    v._al_clic(x, y, panel)
    nuevos = v.sesion.origenes()[antes:]
    datos["por_funcion"] = [[round(c, 2) for c in cmds.xform(o, q=True, ws=True, t=True)]
                            for o in nuevos]
    datos["mensaje_funcion"] = v.mensaje.text()
    # Clic de verdad sobre el visor: ¿coinciden los píxeles que recibe la herramienta
    # con los del visor en pantallas Retina?
    recibidos = []
    original = herramienta._al_pulsar

    def espia(px, py, panel_clic=None):
        recibidos.append([px, py, panel_clic])
        original(px, py, panel_clic)

    try:
        from PySide6 import QtWidgets
        from shiboken6 import wrapInstance

        herramienta._al_pulsar = espia
        widget = wrapInstance(int(vista.widget()), QtWidgets.QWidget)
        antes = len(v.sesion.origenes())
        datos.update(_clic_qt(widget, x, y))
        nuevos = v.sesion.origenes()[antes:]
        datos["clic_recibido"] = recibidos
        datos["por_clic"] = [[round(c, 2) for c in cmds.xform(o, q=True, ws=True, t=True)]
                             for o in nuevos]
        datos["mensaje_clic"] = v.mensaje.text()
    except Exception:
        datos["clic_error"] = traceback.format_exc()
    finally:
        herramienta._al_pulsar = original
    # Un clic fuera de la superficie (al cielo) debe avisar sin crear nada.
    antes = len(v.sesion.origenes())
    v._al_clic(5, vista.portHeight() - 5, panel)
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


def _mallas():
    return len(cmds.ls(type="mesh") or [])


def _hojas_instanciadas():
    total = 0
    for p in cmds.ls(type="particle") or []:
        try:
            total += cmds.particle(p, query=True, count=True)
        except RuntimeError:
            pass
    return total


def deshacer(v):
    """Ctrl+Z tras Crear malla: la planta entera desaparece de una vez y rehacer la devuelve."""
    mallas_antes = _mallas()
    # Lo mismo que hace un estudiante: crear y deshacer enseguida.
    v.boton_malla.click()
    planta = v.sesion.ultima_planta
    mallas_con = _mallas()
    nombre_paso = cmds.undoInfo(query=True, undoName=True)
    cmds.undo()
    _procesar()
    datos = {"paso": nombre_paso, "mallas_antes": mallas_antes, "mallas_con_planta": mallas_con,
             "deshacer_quita_la_planta": not cmds.objExists(planta),
             "mallas_tras_deshacer": _mallas(),
             "vista_previa_vuelve": bool(v.sesion.vista_previa
                                         and cmds.objExists(v.sesion.vista_previa))}
    cmds.redo()
    _procesar()
    datos.update(rehacer_la_devuelve=cmds.objExists(planta), mallas_tras_rehacer=_mallas(),
                 instanciadores=len(cmds.ls(type="instancer") or []),
                 hojas_tras_rehacer=_hojas_instanciadas())
    datos["visor"] = _captura_visor("4b_rehecha")
    return datos


def guardar_y_nueva(v):
    ruta = os.path.join(_SALIDA, "prueba_ventana.ma")
    cmds.file(rename=ruta)
    cmds.file(save=True, type="mayaAscii", force=True)
    antes = _resumen_sesion(v)
    cmds.file(new=True, force=True)
    return {"antes": antes, "mb": round(os.path.getsize(ruta) / 1e6, 1)}


def reabrir(v):
    cmds.file(os.path.join(_SALIDA, "prueba_ventana.ma"), open=True, force=True)
    return {"escena": cmds.file(query=True, sceneName=True)}


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
    from trepadora.ui import ventana

    datos = {"comando_deshacer": _hay_comando_deshacer()}
    llamadas = []

    def espiar(modulo, nombre):
        original = getattr(modulo, nombre)

        def espia(*a, **k):
            try:
                resultado = original(*a, **k)
                llamadas.append([nombre, "ok"])
                return resultado
            except Exception:
                llamadas.append([nombre, traceback.format_exc().strip().splitlines()[-1]])
                raise
        setattr(modulo, nombre, espia)
        return original

    originales = {"borrar": espiar(menu, "borrar"), "cerrar": espiar(ventana, "cerrar")}
    try:
        try:
            cmds.unloadPlugin(instalar.PLUGIN + ".py")
        except RuntimeError:
            datos["error_descargar"] = traceback.format_exc().strip().splitlines()[-1]
        datos["llamadas"] = llamadas
        datos["cargado_tras_descargar"] = cmds.pluginInfo(instalar.PLUGIN, query=True,
                                                          loaded=True)
        datos["menu_tras_descargar"] = cmds.menu(menu.MENU, exists=True)
    finally:
        menu.borrar, ventana.cerrar = originales["borrar"], originales["cerrar"]
    cmds.loadPlugin(os.path.join(_RAIZ, "plug-ins", instalar.PLUGIN + ".py"))
    from trepadora import menu as menu2

    menu2.crear()
    datos["menu_tras_cargar"] = cmds.menu(menu2.MENU, exists=True)
    datos["comando_tras_cargar"] = _hay_comando_deshacer()
    return datos


def _v():
    from trepadora.ui import ventana

    if ventana._ventana is None:
        raise RuntimeError("La ventana no está abierta")
    return ventana._ventana


_RECORDADOS = ("pasos", "semilla", "escala", "longitud_max", "forma_hoja", "tipo_tallo")


def _ajustes_al_salir():
    """Lo que la siguiente vez que se abra Maya debería recordar la ventana."""
    datos = {c: _v().sesion.ajustes[c] for c in _RECORDADOS}
    with open(os.path.join(_SALIDA, "ajustes_al_salir.json"), "w", encoding="utf-8") as f:
        json.dump(datos, f)
    return datos


def _pasos():
    """Los pasos de la prueba, en orden."""
    return [
        ("instalar", instalar_prueba),
        ("abrir_ventana", lambda: abrir_ventana()[1]),
        ("escena_sencilla", lambda: escena_sencilla(_v())),
        ("origen_por_clic", lambda: origen_por_clic(_v())),
        ("crecer", lambda: crecer(_v())),
        ("crecer_mas", lambda: crecer_mas(_v())),
        ("preajuste_colgante", lambda: preajuste(_v(), "Enredadera colgante")),
        ("preajuste_fachada", lambda: preajuste(_v(), "Hiedra de fachada")),
        ("crear_malla", lambda: crear_malla(_v())),
        ("deshacer", lambda: deshacer(_v())),
        ("guardar_y_nueva", lambda: guardar_y_nueva(_v())),
        ("escena_nueva", lambda: _resumen_sesion(_v())),
        ("reabrir", lambda: reabrir(_v())),
        ("reabierta", lambda: _resumen_sesion(_v())),
        ("ajustes_de_planta", lambda: ajustes_de_planta(_v())),
        ("guardar_preajuste", lambda: guardar_preajuste(_v())),
        ("hoja_propia", lambda: hoja_propia(_v())),
        ("ruina", lambda: ruina(_v())),
        ("recargar_plugin", recargar_plugin),
        ("ajustes_al_salir", _ajustes_al_salir),
    ]


def _datos_generales():
    if not os.path.isdir(_SALIDA):
        os.makedirs(_SALIDA)
    _informe["maya"] = cmds.about(version=True)
    _informe["so"] = cmds.about(operatingSystem=True)
    _informe["app_dir"] = cmds.internalVar(userAppDir=True)


def probar():
    """Todos los pasos seguidos, sin dejar a Maya atender lo pendiente entre ellos."""
    _datos_generales()
    for nombre, funcion in _pasos():
        _paso(nombre, funcion)
    return _informe


def _escribir(nombre):
    with open(os.path.join(_SALIDA, nombre), "w", encoding="utf-8") as f:
        json.dump(_informe, f, ensure_ascii=False, indent=1, default=str)


def _como_un_clic(funcion):
    """Ejecuta ``funcion`` desde Qt, como un clic de verdad en la ventana.

    Lo que se ejecuta con evalDeferred queda en el historial como un solo paso
    (con el nombre de la función), y un Ctrl+Z dentro desharía el paso anterior
    entero; desde Qt cada orden de Maya va a su sitio, igual que al pulsar botones.
    """
    from PySide6 import QtCore

    QtCore.QTimer.singleShot(0, funcion)


def probar_y_salir():
    """Cada paso se ejecuta cuando Maya ha atendido lo que dejó pendiente el anterior
    (avisos de escena nueva, de deshacer...), como cuando un estudiante pulsa botones."""
    pasos = _pasos()

    def salir():
        try:
            # Como al salir de Maya normalmente: guarda las preferencias generales (no
            # las de plug-ins, para comprobar que las guardó el instalador).
            cmds.savePrefs(general=True)
            _informe["seguridad_al_salir"] = _seguridad()
        except Exception:
            _informe["errores"]["salir"] = traceback.format_exc()
        _escribir("prueba_ventana.json")
        sys.stdout.flush()
        os._exit(0)

    def siguiente(i):
        try:
            if i >= len(pasos):
                salir()
                return
            _paso(*pasos[i])
            _escribir("prueba_ventana.json")
        except Exception:
            _informe["errores"]["general"] = traceback.format_exc()
            salir()
            return
        cmds.evalDeferred(lambda: _como_un_clic(lambda: siguiente(i + 1)), lowestPriority=True)

    _datos_generales()
    _empezar_vigia()
    # Cuando Maya haya terminado de arrancar y de dibujar su ventana.
    cmds.evalDeferred(lambda: cmds.evalDeferred(lambda: _como_un_clic(lambda: siguiente(0)),
                                                lowestPriority=True),
                      lowestPriority=True)


def comprobar_arranque():
    """Segunda vez que se abre Maya con las mismas preferencias: ¿está todo sin reinstalar?"""
    from trepadora import menu

    return {"plugin_cargado": cmds.pluginInfo("trepadora_plugin", query=True, loaded=True),
            "comando_deshacer": _hay_comando_deshacer(),
            "menu": cmds.menu(menu.MENU, exists=True),
            "estante": cmds.shelfLayout("Trepadora", exists=True),
            "modulo": cmds.moduleInfo(path=True, moduleName="Trepadora")
            if "Trepadora" in (cmds.moduleInfo(listModules=True) or []) else None,
            "seguridad": _seguridad(),
            "ventana": _abrir_y_capturar()}


def _abrir_y_capturar():
    from trepadora import menu

    v = menu.abrir()
    recordados = {c: v.sesion.ajustes[c] for c in _RECORDADOS}
    ruta = os.path.join(_SALIDA, "ajustes_al_salir.json")
    esperados = None
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            esperados = json.load(f)
    return {"ajustes_recordados": recordados, "ajustes_al_salir": esperados,
            "coinciden": recordados == esperados, "captura": _captura_ventana(v, "6_arranque")}


def comprobar_arranque_y_salir():
    def hacer():
        _informe["paso_actual"] = "arranque"
        try:
            _informe["arranque"] = comprobar_arranque()
        except Exception:
            _informe["errores"]["arranque"] = traceback.format_exc()
        finally:
            _vigilar()
            _escribir("prueba_arranque.json")
            sys.stdout.flush()
            os._exit(0)

    _empezar_vigia()
    # Después de que el plug-in haya creado el menú (también va diferido).
    cmds.evalDeferred(lambda: cmds.evalDeferred(hacer, lowestPriority=True), lowestPriority=True)
