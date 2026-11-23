"""Pruebas de la ventana con una sesión simulada, sin Maya.

Necesitan PySide6 (``pip install PySide6``); si no está, se saltan. En Linux
sin pantalla, con ``QT_QPA_PLATFORM=offscreen``.
"""

import os
import re
import shutil
import sys
import tempfile
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RAIZ, "scripts"))

try:
    from PySide6 import QtWidgets
except ImportError:
    QtWidgets = None

try:
    import maya  # noqa: F401

    EN_MAYA = True
except ImportError:
    EN_MAYA = False

from trepadora import ajustes as aj  # noqa: E402
from trepadora.ajustes import Aviso  # noqa: E402


class SesionFalsa:
    """Hace lo mínimo para que la ventana funcione y apunta lo que se le pide."""

    def __init__(self):
        self.superficies = []
        self.hoja_propia = None
        self.ajustes = aj.valores_por_defecto()
        self.extra = {}
        self.llamadas = []
        self._origenes = []
        self._crecido = False
        self.fallar_seleccion = False
        self.resolucion = "1k"
        self.hay_resoluciones = ("512", "1k", "2k", "4k")

    def superficies_validas(self):
        return self.superficies

    def origenes(self):
        return list(self._origenes)

    def hay_crecimiento(self):
        return self._crecido

    def estado(self):
        if not self._crecido:
            return {"crecido": False}
        hojas = 12345
        return {"crecido": True, "ramas": 80, "puntos": 20000, "pasos": self.ajustes["pasos"],
                "hojas": hojas, "carga": aj.carga(hojas), "al_dia": True}

    def hojas_previstas(self):
        return self.estado().get("hojas", 0)

    def usar_seleccion(self):
        self.llamadas.append("usar_seleccion")
        if self.fallar_seleccion:
            raise Aviso("elige una malla")
        self.superficies = ["|muro", "|suelo"]
        return self.superficies

    def anadir_origen_en(self, x, y, panel=None):
        self._origenes.append((x, y))
        return "|trepadora_origenes_grp|trepadora_origen1"

    def borrar_origenes(self):
        self._origenes = []

    def usar_hoja_propia(self):
        self.hoja_propia = "|hoja"
        return self.hoja_propia

    def quitar_hoja_propia(self):
        self.hoja_propia = None

    def crecer(self):
        self.llamadas.append(("crecer", dict(self.ajustes)))
        self._crecido = True
        return {"cancelado": False, "hechos": self.ajustes["pasos"],
                "pedidos": self.ajustes["pasos"], "limite": False, "segundos": 1.25}

    def crecer_mas(self):
        self.llamadas.append("crecer_mas")
        self.ajustes["pasos"] += 91
        return {"cancelado": False, "hechos": 91, "pedidos": 91, "limite": False,
                "segundos": 0.5}

    def reiniciar(self):
        self._crecido = False

    def crear_malla(self):
        self.llamadas.append("crear_malla")
        return {"planta": "|trepadora_planta_grp", "hojas": 12001, "modelos": 49,
                "segundos": 2.0, "limite": False, "cancelado": False}

    def ajustes_de_planta(self):
        return dict(aj.valores_por_defecto(), semilla=77), {}

    def resolucion_texturas(self):
        return self.resolucion

    def cambiar_texturas(self, resolucion):
        self.llamadas.append(("texturas", resolucion))
        self.resolucion = resolucion
        usada = resolucion if resolucion in self.hay_resoluciones else self.hay_resoluciones[-1]
        return (7 if usada != "1k" else 0), usada


@unittest.skipIf(QtWidgets is None or EN_MAYA, "sin PySide6, o dentro de Maya")
class PruebasVentana(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        from trepadora.ui import ventana

        self.carpeta = tempfile.mkdtemp()
        os.environ["TREPADORA_PREAJUSTES"] = self.carpeta
        self.modulo = ventana
        self.sesion = SesionFalsa()
        self.v = ventana.Ventana(sesion=self.sesion)
        self.v.show()

    def tearDown(self):
        self.v.close()
        self.v.deleteLater()
        os.environ.pop("TREPADORA_PREAJUSTES", None)
        shutil.rmtree(self.carpeta)

    def _textos(self):
        textos = []
        for w in self.v.findChildren(QtWidgets.QLabel):
            textos.append(w.text())
        for w in self.v.findChildren(QtWidgets.QAbstractButton):
            textos.append(w.text())
        for w in self.v.findChildren(QtWidgets.QGroupBox):
            textos.append(w.title())
        for w in self.v.findChildren(QtWidgets.QComboBox):
            textos += [w.itemText(i) for i in range(w.count())]
        return [x for x in textos if x]

    def test_ningun_texto_sin_traducir(self):
        sueltos = [x for x in self._textos() if re.fullmatch(r"[a-z]+(_[a-z0-9]+)+", x)]
        self.assertEqual(sueltos, [])

    def test_pasos_se_activan_en_orden(self):
        v = self.v
        self.assertFalse(v.boton_crecer.isEnabled())
        self.assertFalse(v.caja_origen.isEnabled())
        self.assertFalse(v.boton_mas.isEnabled())
        v.boton_superficie.click()
        self.assertTrue(v.boton_crecer.isEnabled())
        self.assertTrue(v.caja_origen.isEnabled())
        self.assertTrue(v.boton_malla.isEnabled())
        self.assertFalse(v.boton_mas.isEnabled())
        self.assertIn("muro", v.estado_superficie.text())
        v.boton_crecer.click()
        self.assertTrue(v.boton_mas.isEnabled())
        self.assertIn("12.345", v.estado_pie.text())

    def test_resolucion_de_texturas(self):
        """El ajuste cambia las texturas de la escena y no entra en los preajustes."""
        combo = self.v.combo_texturas
        self.assertEqual(combo.valor(), "1k")
        combo.setCurrentIndex(combo.findData("2k"))
        self.assertEqual(self.sesion.llamadas[-1], ("texturas", "2k"))
        self.assertIn("7", self.v.mensaje.text())
        self.assertNotIn("texturas", self.sesion.ajustes)
        self.sesion.hay_resoluciones = ("512", "1k")
        combo.setCurrentIndex(combo.findData("4k"))
        self.assertIn("1K", self.v.mensaje.text())

    def test_aviso_que_ensena(self):
        self.sesion.fallar_seleccion = True
        self.v.boton_superficie.click()
        self.assertEqual(self.v.mensaje.text(), "elige una malla")

    def test_controles_cambian_los_ajustes(self):
        self.v.boton_superficie.click()
        self.v.controles["pasos"].casilla.setValue(500)
        self.v.controles["forma_hoja"].setCurrentIndex(
            self.v.controles["forma_hoja"].findData("corazon"))
        self.v.controles["instancias"].setChecked(False)
        self.v.controles["gravedad"].barra.setValue(1000)
        self.v.boton_crecer.click()
        _, usados = self.sesion.llamadas[-1]
        self.assertEqual(usados["pasos"], 500)
        self.assertEqual(usados["forma_hoja"], "corazon")
        self.assertIs(usados["instancias"], False)
        self.assertEqual(usados["gravedad"], aj.POR_CLAVE["gravedad"].maximo)

    def test_crecer_mas_actualiza_el_tamano(self):
        self.v.boton_superficie.click()
        self.v.boton_crecer.click()
        antes = self.v.controles["pasos"].valor()
        self.v.boton_mas.click()
        self.assertEqual(self.v.controles["pasos"].valor(), antes + 91)

    def test_preajuste_cambia_los_controles(self):
        combo = self.v.combo_preajustes
        nombres = [combo.itemText(i) for i in range(combo.count())]
        self.assertIn("Ramas secas", nombres)
        combo.setCurrentIndex(nombres.index("Ramas secas"))
        self.v._elegir_preajuste()
        self.assertEqual(self.v.controles["densidad"].valor(), 0.0)
        self.assertEqual(self.sesion.ajustes["tipo_tallo"], "nudoso")

    def test_guardar_preajuste(self):
        original = QtWidgets.QInputDialog.getText
        QtWidgets.QInputDialog.getText = staticmethod(lambda *a, **k: ("Mi hiedra", True))
        try:
            self.v.controles["semilla"].casilla.setValue(321)
            self.v._guardar_preajuste()
        finally:
            QtWidgets.QInputDialog.getText = original
        self.assertTrue(os.path.isfile(os.path.join(self.carpeta, "Mi_hiedra.json")))
        combo = self.v.combo_preajustes
        self.assertEqual(combo.currentText(), "Mi hiedra")
        self.assertEqual(aj.leer_preajuste(os.path.join(self.carpeta, "Mi_hiedra.json"))
                         .ajustes["semilla"], 321)

    def test_crear_malla_y_ajustes_de_planta(self):
        self.v.boton_superficie.click()
        self.v.boton_malla.click()
        self.assertIn("crear_malla", self.sesion.llamadas)
        self.assertIn("12.001", self.v.mensaje.text())
        self.v._ajustes_de_planta()
        self.assertEqual(self.v.controles["semilla"].valor(), 77)

    def test_avanzados_plegados(self):
        self.assertFalse(self.v.plegable_avanzados.contenido.isVisible())
        self.v.plegable_avanzados.boton.click()
        self.assertTrue(self.v.plegable_avanzados.contenido.isVisible())


if __name__ == "__main__":
    unittest.main()
