"""Ensayo de la ventana y de la sesión reales con un Maya falso en memoria.

Recorre lo que haría un estudiante (elegir superficie, poner orígenes, crecer,
crecer más, preajustes, crear la malla, reabrir la escena, hoja propia...) y
comprueba cada paso. Sirve para encontrar fallos de la ventana antes de
probarla en Maya; no sustituye a ``herramientas/prueba_ventana.py``, que se
ejecuta dentro de Maya.

El Maya falso (carpeta ``maya`` de aquí al lado) solo guarda nodos, atributos
y cajas; la superficie se simula con cajas y ``crear_planta`` solo coloca las
hojas, sin crear mallas.

Necesita PySide6. Desde la raíz del repositorio:

    QT_QPA_PLATFORM=offscreen python herramientas/ensayo_sin_maya/ensayo.py
"""
import json
import os
import shutil
import sys
import tempfile
import time
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(AQUI, "..", ".."))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "tests"))
CARPETA = tempfile.mkdtemp()
os.environ["TREPADORA_PREAJUSTES"] = CARPETA
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

app = QtWidgets.QApplication([])

from maya import cmds  # noqa: E402
from superficies import Cajas  # noqa: E402
from trepadora import prototipo, sesion as ses, superficie_maya  # noqa: E402
from trepadora import ajustes as aj  # noqa: E402
from trepadora.hojas import ParametrosHojas, colocar_hojas  # noqa: E402
from trepadora.ui import ventana  # noqa: E402


def _cajas(nombres):
    return Cajas([cmds._caja(cmds._corto(n)) for n in nombres])


superficie_maya.SuperficieMaya = _cajas


def _punto(self, x, y, panel=None):
    # x, y = coordenadas de mundo frente al muro (z grande); fuera de todo -> None
    self._exigir_superficie()
    if y < 0 or abs(x) > 1000:
        return None
    return _cajas(self.superficies_validas()).mas_cercano((x, y, 6.0))[0]


ses.Sesion.punto_en_superficie = _punto


def _planta(crecimiento, paso, ajustes_hojas, grosor=1.0, semilla=1, instancias=True,
            forma_hoja="hiedra", tipo_tallo="lenoso", hoja_propia=None, lados=None,
            resumen=None):
    datos = dict(ajustes_hojas)
    datos["tamano"] = paso * 2.4 * datos.get("tamano", 1.0)
    hojas = colocar_hojas(crecimiento, ParametrosHojas(**datos))
    grupo = cmds.group(empty=True, name=prototipo.GRUPO_PLANTA)
    LLAMADAS.append(dict(lados=lados, forma=forma_hoja, tallo=tipo_tallo, propia=hoja_propia,
                         instancias=instancias, semilla=semilla, grosor=grosor))
    if resumen is not None:
        resumen.update(hojas=len(hojas), modelos=49 if instancias else 0)
    return grupo


LLAMADAS = []
prototipo.crear_planta = _planta

fallos = []


def comprobar(cond, texto):
    print(("  ok  " if cond else "  MAL ") + texto)
    if not cond:
        fallos.append(texto)


def textos_crudos(v):
    import re
    textos = []
    for w in v.findChildren(QtWidgets.QLabel):
        textos.append(w.text())
    for w in v.findChildren(QtWidgets.QAbstractButton):
        textos.append(w.text())
    return [x for x in textos if re.fullmatch(r"[a-z]+(_[a-z0-9]+)+", x or "")]


def paso(nombre, f):
    print("==", nombre)
    t0 = time.time()
    try:
        f()
    except Exception:
        traceback.print_exc()
        fallos.append(nombre + ": excepción")
    print("   ({:.2f} s)".format(time.time() - t0))


v = None


def p_abrir():
    global v
    v = ventana.Ventana()
    v.show()
    comprobar(not v.boton_crecer.isEnabled(), "Crecer desactivado sin superficie")
    comprobar(v.estado_superficie.text() != "", "texto de superficie: " + v.estado_superficie.text())
    comprobar(not textos_crudos(v), "sin claves sin traducir")


def p_superficie():
    v.boton_superficie.click()
    comprobar(v.mensaje.text() != "", "aviso sin selección: " + v.mensaje.text())
    mallas, locs = prototipo.crear_escena("sencilla")
    cmds.select(mallas + locs)
    v.boton_superficie.click()
    comprobar(len(v.sesion.superficies) == 3, "3 superficies: {}".format(v.sesion.superficies))
    comprobar(len(v.sesion.origenes()) == len(locs), "localizadores -> orígenes: {}".format(
        v.sesion.origenes()))
    comprobar(v.boton_crecer.isEnabled() and v.caja_origen.isEnabled(), "pasos 2 y 3 activos")
    print("   superficie:", v.estado_superficie.text(), "| origen:", v.estado_origen.text())
    print("   mensaje:", v.mensaje.text())
    cmds.delete(locs)


def p_origenes():
    v.boton_quitar.click()
    comprobar(v.sesion.origenes() == [], "Quitar borra orígenes")
    v._al_clic(5000, 5000)
    comprobar("fuera" in v.mensaje.text().lower() or v.mensaje.text() != "",
              "clic fuera avisa: " + v.mensaje.text())
    v._al_clic(40, 90)
    o = v.sesion.origenes()
    comprobar(len(o) == 1, "clic coloca un origen")
    print("   origen en", cmds.xform(o[0], query=True, worldSpace=True, translation=True),
          "| mensaje:", v.mensaje.text(), "| estado:", v.estado_origen.text())
    comprobar(o[0].startswith("|" + ses.GRUPO_DATOS), "origen dentro del grupo de datos")


def p_crecer():
    v.controles["pasos"].casilla.setValue(80)
    v.boton_crecer.click()
    e = v.sesion.estado()
    print("   estado:", e)
    print("   mensaje:", v.mensaje.text())
    print("   pie:", v.estado_pie.text().replace("\n", " / "))
    comprobar(e["crecido"] and e["puntos"] > 100, "crece")
    comprobar(e["al_dia"], "al día tras crecer")
    comprobar(cmds.objExists(prototipo.GRUPO_VISTA_PREVIA), "hay vista previa")
    comprobar(v.boton_mas.isEnabled() and v.boton_reiniciar.isEnabled(), "Crecer más y Reiniciar")


def p_mas():
    antes = v.sesion.estado()["puntos"]
    crec = v.sesion._crecimiento
    v.boton_mas.click()
    e = v.sesion.estado()
    print("   pasos:", v.controles["pasos"].valor(), "puntos:", antes, "->", e["puntos"])
    print("   mensaje:", v.mensaje.text())
    comprobar(v.sesion._crecimiento is crec, "sigue el mismo crecimiento")
    comprobar(v.controles["pasos"].valor() == 120, "Tamaño sube de 80 a 120")
    comprobar(e["al_dia"] and e["puntos"] > antes, "al día y más grande")
    otro = ses.Sesion()
    otro.superficies = list(v.sesion.superficies)
    otro.ajustes = dict(v.sesion.ajustes)
    otro.extra = dict(v.sesion.extra)
    otro._nuevo_crecimiento()
    otro._hacer_crecer(otro.ajustes["pasos"])
    comprobar(otro._crecimiento.total_puntos == e["puntos"],
              "crecer más == crecer desde cero ({} / {})".format(otro._crecimiento.total_puntos,
                                                                e["puntos"]))


def p_llena():
    v.controles["pasos"].casilla.setValue(900)
    comprobar(not v.sesion.al_dia(), "subir el Tamaño pide crecer")
    v.boton_crecer.click()
    e = v.sesion.estado()
    print("   estado:", e, "motivo:", v.sesion.motivo_parada())
    print("   mensaje:", v.mensaje.text())
    v.controles["pasos"].casilla.setValue(600)
    comprobar(v.sesion.al_dia(), "bajar el Tamaño por encima de donde paró no pide crecer")
    v.controles["pasos"].casilla.setValue(900)
    for i in range(8):
        antes = v.sesion.estado()["puntos"]
        v.boton_mas.click()
        print("   crecer más {}: {} -> {} | largo {} | {}".format(
            i + 1, antes, v.sesion.estado()["puntos"], v.controles["longitud_max"].valor(),
            v.mensaje.text()))
        if v.sesion.estado()["puntos"] == antes:
            break
    comprobar(v.sesion.motivo_parada() in ("espacio", "superficie", "largo"),
              "acaba explicando por qué no crece más")
    comprobar(v.sesion.al_dia(), "al día")


def p_largo():
    v.controles["longitud_max"].casilla.setValue(30)
    v.controles["pasos"].casilla.setValue(300)
    v.boton_crecer.click()
    e = v.sesion.estado()
    print("   estado:", e, "motivo:", v.sesion.motivo_parada(),
          v.sesion._crecimiento.motivos_de_parada())
    print("   mensaje:", v.mensaje.text())
    if v.sesion.motivo_parada() == "largo":
        v.boton_mas.click()
        print("   crecer más:", v.mensaje.text())
        comprobar(v.controles["longitud_max"].valor() == 40, "Crecer más alarga las ramas: {}"
                  .format(v.controles["longitud_max"].valor()))
        comprobar(v.sesion.estado()["puntos"] > e["puntos"], "y crece más")
        comprobar(v.sesion.al_dia(), "al día")
    else:
        comprobar(False, "esperaba parada por largo")
    v.controles["longitud_max"].casilla.setValue(aj.POR_CLAVE["longitud_max"].defecto)
    v.controles["pasos"].casilla.setValue(220)
    v.boton_crecer.click()


def p_cambios():
    v.controles["densidad"].casilla.setValue(0.3)
    comprobar(v.sesion.estado()["al_dia"], "cambiar densidad no obliga a recrecer")
    print("   pie:", v.estado_pie.text().replace("\n", " / "))
    v.controles["gravedad"].casilla.setValue(1.2)
    comprobar(not v.sesion.estado()["al_dia"], "cambiar gravedad sí")
    print("   pie:", v.estado_pie.text().replace("\n", " / "))
    v.controles["gravedad"].casilla.setValue(aj.POR_CLAVE["gravedad"].defecto)
    comprobar(v.sesion.estado()["al_dia"], "volver a la gravedad de antes, al día otra vez")


def p_preajuste():
    combo = v.combo_preajustes
    nombres = [combo.itemText(i) for i in range(combo.count())]
    print("   preajustes:", nombres)
    combo.setCurrentIndex(nombres.index("Enredadera colgante"))
    combo.activated.emit(nombres.index("Enredadera colgante"))
    print("   gravedad:", v.sesion.ajustes["gravedad"], "mensaje:", v.mensaje.text())
    comprobar(v.sesion.ajustes["gravedad"] == 0.95, "preajuste aplicado al cambiar el combo")
    comprobar(not v.sesion.estado()["al_dia"], "preajuste deja la planta sin actualizar")
    print("   pie:", v.estado_pie.text().replace("\n", " / "))


def p_malla():
    v.boton_malla.click()
    print("   mensaje:", v.mensaje.text())
    print("   llamada:", LLAMADAS[-1])
    planta = v.sesion.ultima_planta
    comprobar(planta and cmds.objExists(planta), "planta creada")
    comprobar(not cmds.objExists(prototipo.GRUPO_VISTA_PREVIA), "vista previa borrada")
    comprobar(cmds.ls(selection=True) == [cmds._corto(planta)], "planta seleccionada")
    datos = json.loads(cmds.getAttr(planta + "." + ses.ATR_PLANTA))
    comprobar(datos["gravedad"] == 0.95, "la planta guarda sus ajustes")
    comprobar(LLAMADAS[-1]["lados"] == aj.lados_tallo(datos["tipo_tallo"], datos["resolucion"]),
              "lados según la resolución")
    comprobar(not textos_crudos(v), "sin claves sin traducir")


def p_reabrir():
    nueva = ses.Sesion()
    comprobar(nueva.superficies == v.sesion.superficies, "reabrir: superficies")
    comprobar(nueva.ajustes == v.sesion.ajustes, "reabrir: ajustes")
    comprobar(len(nueva.origenes()) == 1, "reabrir: origen")
    v.cambiar_sesion(nueva)
    comprobar(v.leer_controles() == nueva.ajustes, "controles = ajustes guardados")
    print("   pie:", v.estado_pie.text().replace("\n", " / "))


def p_ajustes_planta():
    v._por_defecto()
    comprobar(v.sesion.ajustes["gravedad"] != 0.95, "por defecto")
    cmds.select(v.sesion.ultima_planta or prototipo.GRUPO_PLANTA)
    v._ajustes_de_planta()
    print("   mensaje:", v.mensaje.text())
    comprobar(v.sesion.ajustes["gravedad"] == 0.95, "recupera los ajustes de la planta")
    cmds.select(clear=True)
    v._ajustes_de_planta()
    print("   sin selección:", v.mensaje.text())


def p_hoja_propia():
    hoja = cmds.polyPlane(name="mi_hoja", width=1, height=2)[0]
    cmds.select(hoja)
    v.boton_hoja.click()
    comprobar(v.sesion.hoja_propia == "|mi_hoja", "hoja propia: {}".format(v.sesion.hoja_propia))
    print("   estado:", v.estado_hoja.text(), "| mensaje:", v.mensaje.text())
    v.boton_crecer.click()
    v.boton_malla.click()
    comprobar(LLAMADAS[-1]["propia"] == "|mi_hoja", "la planta usa la hoja propia")
    comprobar(ses.Sesion().hoja_propia == "|mi_hoja", "la escena recuerda la hoja propia")
    v.boton_quitar_hoja.click()
    comprobar(v.sesion.hoja_propia is None, "quitar hoja propia")


def p_reiniciar():
    v.boton_crecer.click()
    v.boton_reiniciar.click()
    comprobar(not cmds.objExists(prototipo.GRUPO_VISTA_PREVIA), "Reiniciar borra la vista previa")
    comprobar(not v.boton_mas.isEnabled(), "Crecer más desactivado")
    print("   mensaje:", v.mensaje.text(), "| pie:", v.estado_pie.text())


def p_sin_origen():
    v.boton_quitar.click()
    v.boton_crecer.click()
    e = v.sesion.estado()
    comprobar(e["crecido"] and e["puntos"] > 100, "crece sin orígenes desde la base")
    print("   mensaje:", v.mensaje.text())


def p_guardar_preajuste():
    original = QtWidgets.QInputDialog.getText
    QtWidgets.QInputDialog.getText = staticmethod(lambda *a, **k: ("Mi hiedra", True))
    try:
        v._guardar_preajuste()
    finally:
        QtWidgets.QInputDialog.getText = original
    print("   archivos:", os.listdir(CARPETA), "| combo:", v.combo_preajustes.currentText())
    comprobar(os.path.isfile(os.path.join(CARPETA, "Mi_hiedra.json")), "preajuste guardado")


def p_escena_prueba():
    for n in list(cmds.nodos):
        cmds.nodos.pop(n, None)
    v._escena_nueva()
    comprobar(not v.boton_crecer.isEnabled(), "escena nueva: vuelve al paso 1")
    v.escena_de_prueba("ruina")
    print("   mensaje:", v.mensaje.text(), "| superficies:", len(v.sesion.superficies))
    print("   ajustes:", {k: v.sesion.ajustes[k] for k in ("pasos", "escala", "densidad")},
          "extra:", v.sesion.extra)
    t0 = time.time()
    v.boton_crecer.click()
    print("   crecer ruina: {:.1f} s".format(time.time() - t0), v.sesion.estado())
    print("   pie:", v.estado_pie.text().replace("\n", " / "))
    t0 = time.time()
    v.boton_malla.click()
    print("   malla ruina: {:.1f} s".format(time.time() - t0), v.mensaje.text())


def p_carga_alta():
    llamado = []
    original = QtWidgets.QMessageBox.question
    QtWidgets.QMessageBox.question = staticmethod(
        lambda *a, **k: llamado.append(a) or QtWidgets.QMessageBox.No)
    try:
        v.controles["pasos"].casilla.setValue(900)
        v.controles["densidad"].casilla.setValue(1.0)
        v.boton_crecer.click()
        previstas = v.sesion.hojas_previstas()
        n = len(LLAMADAS)
        v.boton_malla.click()
    finally:
        QtWidgets.QMessageBox.question = original
    print("   previstas:", previstas, aj.carga(previstas), "| pie:",
          v.estado_pie.text().replace("\n", " / "))
    if aj.carga(previstas) == "alta":
        comprobar(llamado and len(LLAMADAS) == n, "carga alta pregunta y respeta el No")


for nombre, f in [("abrir", p_abrir), ("superficie", p_superficie), ("origenes", p_origenes),
                  ("crecer", p_crecer), ("crecer_mas", p_mas), ("llena", p_llena), ("largo", p_largo),
                  ("cambios", p_cambios),
                  ("preajuste", p_preajuste), ("malla", p_malla), ("reabrir", p_reabrir),
                  ("ajustes_planta", p_ajustes_planta), ("hoja_propia", p_hoja_propia),
                  ("reiniciar", p_reiniciar), ("sin_origen", p_sin_origen),
                  ("guardar_preajuste", p_guardar_preajuste), ("escena_prueba", p_escena_prueba),
                  ("carga_alta", p_carga_alta)]:
    paso(nombre, f)

print("\nAvisos de Maya:", cmds.avisos)
print("FALLOS:", fallos)
shutil.rmtree(CARPETA)
sys.exit(1 if fallos else 0)
