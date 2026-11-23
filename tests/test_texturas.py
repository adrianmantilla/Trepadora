"""Texturas: rutas por resolución, materiales con texturas y cambio de resolución.

Usa el Maya falso de maya_nombres.py con Arnold «cargado» y una carpeta de
texturas de mentira (archivos vacíos), para no depender de las imágenes.

Ejecutar desde la raíz del repositorio:  python -m unittest discover tests
"""

import importlib
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))
sys.path.insert(0, AQUI)

import maya_nombres  # noqa: E402
from superficies import Muro  # noqa: E402
from trepadora import geometria, texturas  # noqa: E402
from trepadora.crecimiento import Crecimiento, Parametros  # noqa: E402

_MODULOS_CON_MAYA = ("trepadora.prototipo", "trepadora.deshacer")


def _carpeta_falsa(resoluciones, juegos=None):
    carpeta = tempfile.mkdtemp()
    for res in resoluciones:
        os.makedirs(os.path.join(carpeta, res))
        for juego in juegos or texturas.juegos(geometria.FORMAS_HOJA):
            for mapa in texturas.mapas_de(juego):
                open(os.path.join(carpeta, res, texturas.archivo(juego, mapa)), "w").close()
    return carpeta


class PruebasRutas(unittest.TestCase):
    def setUp(self):
        self.carpeta = _carpeta_falsa(("512", "1k", "2k"))
        self.addCleanup(shutil.rmtree, self.carpeta)

    def test_ruta_y_respaldo(self):
        r = texturas.ruta("corteza", "normal", "2k", self.carpeta)
        self.assertEqual(r, os.path.join(self.carpeta, "2k", "corteza_normal.jpg"))
        # Sin 4K, la más parecida por debajo.
        self.assertIn(os.sep + "2k" + os.sep, texturas.ruta("corteza", "normal", "4k", self.carpeta))
        shutil.rmtree(os.path.join(self.carpeta, "512"))
        self.assertIn(os.sep + "1k" + os.sep, texturas.ruta("corteza", "normal", "512", self.carpeta))
        self.assertIsNone(texturas.ruta("corteza", "traslucidez", "1k", self.carpeta))
        self.assertEqual(texturas.disponibles(self.carpeta), ["1k", "2k"])

    def test_juegos_y_mapas(self):
        self.assertEqual(texturas.juegos(("hiedra",)), ["hoja_hiedra", "corteza"])
        self.assertIn("traslucidez", texturas.mapas_de("hoja_redonda"))
        self.assertNotIn("traslucidez", texturas.mapas_de("corteza"))
        self.assertEqual(texturas.de_clave(texturas.clave("hoja_hiedra", "normal")),
                         ("hoja_hiedra", "normal"))

    def test_las_texturas_del_plugin_estan_completas(self):
        """Si el plugin trae texturas, trae todos los mapas en todas las resoluciones."""
        carpeta = texturas.carpeta()
        if not os.path.isdir(carpeta):
            self.skipTest("sin carpeta de texturas")
        for res in texturas.RESOLUCIONES:
            for juego in texturas.juegos(geometria.FORMAS_HOJA):
                for mapa in texturas.mapas_de(juego):
                    ruta = os.path.join(carpeta, res, texturas.archivo(juego, mapa))
                    self.assertTrue(os.path.isfile(ruta), ruta)


class PruebasMateriales(unittest.TestCase):

    def setUp(self):
        import trepadora
        antes = {n: getattr(trepadora, n.split(".")[1], None) for n in _MODULOS_CON_MAYA}
        self.addCleanup(lambda: [setattr(trepadora, n.split(".")[1], m)
                                 for n, m in antes.items() if m is not None])
        self.carpeta = _carpeta_falsa(("512", "1k", "2k"))
        self.addCleanup(shutil.rmtree, self.carpeta)
        entorno = mock.patch.dict(os.environ, {"TREPADORA_TEXTURAS": self.carpeta})
        entorno.start()
        self.addCleanup(entorno.stop)
        self.escena, modulos = maya_nombres.instalar()
        self.escena.arnold = True
        for nombre in _MODULOS_CON_MAYA:
            modulos[nombre] = None
        parche = mock.patch.dict(sys.modules, modulos)
        parche.start()
        self.addCleanup(parche.stop)
        for nombre in _MODULOS_CON_MAYA:
            del sys.modules[nombre]
        self.prototipo = importlib.import_module("trepadora.prototipo")
        self.cmds = sys.modules["maya.cmds"]

    def _planta(self, semilla=1, **opciones):
        c = Crecimiento(Muro(), Parametros(semilla=semilla, pasos=40))
        c.anadir_origen((0.0, 0.0, 0.5))
        c.crecer()
        return self.prototipo.crear_planta(c, 1.0, {}, semilla=semilla, **opciones)

    def _rutas(self):
        return {n: self.cmds.getAttr(n + "." + a) for n, a, _j, _m in texturas.nodos_de_textura()}

    def _entra(self, nodo, atributo):
        """El nodo que llega a ``nodo.atributo``."""
        destino = self.escena.buscar(nodo)
        for o, _a, d, b in self.escena.conexiones:
            if d is destino and b == atributo:
                return o.nombre
        return None

    def test_shader_con_texturas(self):
        self._planta(1, forma_hoja="corazon", resolucion_texturas="1k")
        rutas = self._rutas()
        self.assertTrue(rutas)
        self.assertTrue(all(os.sep + "1k" + os.sep in r for r in rutas.values()))
        juegos = {texturas.de_clave(self.cmds.getAttr(n + "." + texturas.ATRIBUTO))[0]
                  for n in rutas}
        self.assertEqual(juegos, {"hoja_corazon", "corteza"})
        hojas = "trepadora_hoja_corazon_inst_ai"
        self.assertEqual(self._entra(hojas, "baseColor"), "trepadora_hoja_corazon_inst_detalle_ai")
        self.assertEqual(self._entra(hojas, "subsurface"), "trepadora_tex_hoja_corazon_traslucidez_ai")
        self.assertEqual(self._entra(hojas, "normalCamera"), "trepadora_hoja_corazon_inst_relieve_ai")
        self.assertEqual(self._entra("trepadora_tallos_ai", "specularRoughness"),
                         "trepadora_tex_corteza_rugosidad_ai")
        # El visor: el lambert de cada tono lleva el detalle de la hoja.
        self.assertTrue(any(self._entra(m.nombre, "color")
                            for m in self.escena.nodos if m.tipo == "lambert"
                            and m.nombre.startswith("trepadora_hoja_corazon_tono")))
        self.assertEqual(self.escena.avisos, [])

    def test_cambiar_resolucion_cambia_las_plantas_creadas(self):
        self._planta(1, resolucion_texturas="1k")
        self._planta(2, forma_hoja="redonda", instancias=False, resolucion_texturas="1k")
        antes = self._rutas()
        cambiados = texturas.cambiar_resolucion("2k")
        despues = self._rutas()
        self.assertEqual(cambiados, len(antes))
        self.assertTrue(all(os.sep + "2k" + os.sep in r for r in despues.values()))
        self.assertEqual(texturas.resolucion_actual(), "2k")
        # Las plantas nuevas salen ya con la nueva resolución.
        self._planta(3, forma_hoja="alargada")
        self.assertTrue(all(os.sep + "2k" + os.sep in r for r in self._rutas().values()))
        # 4K no está: se queda con la más parecida y no cambia nada.
        self.assertEqual(texturas.cambiar_resolucion("4k"), 0)

    def test_sin_texturas_la_planta_sale_igual(self):
        shutil.rmtree(self.carpeta)
        os.makedirs(self.carpeta)
        self._planta(1)
        self.assertEqual(self._rutas(), {})
        self.assertEqual(self._entra("trepadora_tallos_ai", "baseColor"), "trepadora_tallos_color_ai")
        self.assertEqual(self.escena.avisos, [])


if __name__ == "__main__":
    unittest.main()
