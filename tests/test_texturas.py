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

_MODULOS_CON_MAYA = ("trepadora.prototipo", "trepadora.deshacer", "trepadora.openpbr", "trepadora.menu")


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
            if hasattr(trepadora, nombre.split(".")[1]):   # «from . import x» lo tomaría de aquí
                delattr(trepadora, nombre.split(".")[1])
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
        self.assertEqual(self.cmds.nodeType(hojas), "openPBRSurface")
        self.assertEqual(self._entra(hojas, "subsurfaceWeight"),
                         "trepadora_tex_hoja_corazon_traslucidez_ai")
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

    def test_escena_de_otro_ordenador(self):
        """Las rutas que no existen aquí se apuntan a esta carpeta, con su resolución."""
        self._planta(1, resolucion_texturas="2k")
        texturas.recordar_resolucion("1k")
        rutas = self._rutas()
        otra = {"C:\\Users\\alumno\\Trepadora\\texturas\\2k\\x.jpg": "2k",
                "/Users/profe/Trepadora/texturas/512/x.jpg": "512",
                "/ruta/rara/x.jpg": "1k"}
        nodos = sorted(texturas.nodos_de_textura())
        viejas = [sorted(otra)[i % len(otra)] for i in range(len(nodos))]
        for (nodo, atributo, _j, _m), vieja in zip(nodos, viejas):
            self.cmds.setAttr(nodo + "." + atributo, vieja, type="string")
        self.assertEqual(texturas.reparar_rutas(), len(rutas))
        for (nodo, atributo, juego, mapa), vieja in zip(nodos, viejas):
            esperada = texturas.ruta(juego, mapa, otra[vieja], self.carpeta)
            self.assertEqual(self.cmds.getAttr(nodo + "." + atributo), esperada)
        # Las que ya existen no se tocan, y el historial de deshacer queda como estaba.
        self.assertEqual(texturas.reparar_rutas(), 0)
        self.assertTrue(self.escena.deshacer)
        self.assertEqual(texturas.resolucion_de("a/b/4k/c.jpg"), "4k")
        self.assertIsNone(texturas.resolucion_de("c.jpg"))

    def test_sin_arnold_no_avisa(self):
        """Sin MtoA, buscar las texturas no pregunta por aiImage (Maya avisaría al abrir escenas)."""
        self.escena.arnold = False
        self._planta(1, resolucion_texturas="1k")
        self.assertTrue(self._rutas())
        texturas.reparar_rutas()
        self.assertTrue(texturas.cambiar_resolucion("2k"))
        self.assertFalse([a for a in self.escena.avisos if "Unknown object type" in a])

    def test_planta_para_exportar(self):
        """La seleccionada (o la de una pieza suya); sin selección, la única que haya."""
        from trepadora import exportar

        primera = self.cmds.ls(self._planta(1), long=True)[0]
        self.assertEqual(exportar.planta_de(), primera)
        self.assertTrue(exportar.instanciador_de(primera).startswith(primera + "|"))
        segunda = self.cmds.ls(self._planta(2, instancias=False), long=True)[0]
        self.assertIsNone(exportar.planta_de())
        self.assertIsNone(exportar.instanciador_de(segunda))
        self.assertEqual(exportar.planta_de(segunda + "|trepadora_tallos"), segunda)
        self.assertEqual(sorted(exportar.plantas_en_escena()), sorted([primera, segunda]))

    def test_convertir_escena_vieja_a_openpbr(self):
        """Una planta con aiStandardSurface (como las de antes) pasa a OpenPBR sin perder nada."""
        sin_openpbr = mock.patch.object(self.cmds, "allNodeTypes",
                                        lambda **_: ["aiStandardSurface", "aiImage", "lambert"])
        with sin_openpbr:
            self._planta(1, forma_hoja="corazon", resolucion_texturas="1k")
        hojas = "trepadora_hoja_corazon_inst_ai"
        self.assertEqual(self.cmds.nodeType(hojas), "aiStandardSurface")
        self.assertEqual(self.cmds.getAttr(hojas + ".specular"), 0.5)
        grupos = sorted(d.nombre for o, a, d, b in self.escena.conexiones
                        if o.nombre == hojas and b == "aiSurfaceShader")
        self.assertTrue(grupos)

        from trepadora import menu
        hechos = menu.convertir_a_openpbr()
        self.assertIn(hojas, hechos)
        self.assertIn("trepadora_tallos_ai", hechos)
        self.assertEqual(self.cmds.nodeType(hojas), "openPBRSurface")
        self.assertEqual(self.cmds.getAttr(hojas + ".specularWeight"), 0.5)
        self.assertEqual(self.cmds.getAttr(hojas + ".geometryThinWalled"), 1)
        self.assertEqual(self._entra(hojas, "baseColor"), "trepadora_hoja_corazon_inst_detalle_ai")
        self.assertEqual(self._entra(hojas, "subsurfaceWeight"),
                         "trepadora_tex_hoja_corazon_traslucidez_ai")
        self.assertEqual(self._entra(hojas, "normalCamera"), "trepadora_hoja_corazon_inst_relieve_ai")
        self.assertEqual(sorted(d.nombre for o, a, d, b in self.escena.conexiones
                                if o.nombre == hojas and b == "aiSurfaceShader"), grupos)
        self.assertFalse(self.cmds.ls(type="aiStandardSurface"))
        # Una segunda vez no hay nada que convertir.
        self.assertEqual(menu.convertir_a_openpbr(), [])

    def test_sin_texturas_la_planta_sale_igual(self):
        shutil.rmtree(self.carpeta)
        os.makedirs(self.carpeta)
        self._planta(1)
        self.assertEqual(self._rutas(), {})
        self.assertEqual(self._entra("trepadora_tallos_ai", "baseColor"), "trepadora_tallos_color_ai")
        self.assertEqual(self.escena.avisos, [])


if __name__ == "__main__":
    unittest.main()
