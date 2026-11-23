"""Dos plantas en la misma escena, con las reglas de nombres de Maya.

La segunda planta tiene piezas con el mismo nombre que la primera
(``trepadora_tallos``, ``trepadora_hoja_modelo1``...), cada una en su grupo.
Maya lo permite, pero entonces el nombre corto ya no basta para encontrar la
pieza: ``crear_planta`` tiene que usar rutas completas. Ver maya_nombres.py.

Ejecutar desde la raíz del repositorio:  python -m unittest discover tests
"""

import importlib
import os
import sys
import unittest
from unittest import mock

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))
sys.path.insert(0, AQUI)

import maya_nombres  # noqa: E402
from superficies import Muro  # noqa: E402
from trepadora.crecimiento import Crecimiento, Parametros  # noqa: E402

_MODULOS_CON_MAYA = ("trepadora.prototipo", "trepadora.deshacer")


def _crecida(semilla):
    c = Crecimiento(Muro(), Parametros(semilla=semilla, pasos=40))
    c.anadir_origen((0.0, 0.0, 0.5))
    c.crecer()
    return c


class PruebasDosPlantas(unittest.TestCase):

    def setUp(self):
        import trepadora
        antes = {n: getattr(trepadora, n.split(".")[1], None) for n in _MODULOS_CON_MAYA}
        self.addCleanup(lambda: [setattr(trepadora, n.split(".")[1], m)
                                 for n, m in antes.items() if m is not None])
        self.escena, modulos = maya_nombres.instalar()
        for nombre in _MODULOS_CON_MAYA:
            modulos[nombre] = None   # se vuelven a importar con este Maya
        parche = mock.patch.dict(sys.modules, modulos)
        parche.start()
        self.addCleanup(parche.stop)
        for nombre in _MODULOS_CON_MAYA:
            del sys.modules[nombre]
        self.prototipo = importlib.import_module("trepadora.prototipo")
        self.cmds = sys.modules["maya.cmds"]

    def _planta(self, semilla=1, **opciones):
        resumen = {}
        grupo = self.prototipo.crear_planta(_crecida(semilla), 1.0, {}, semilla=semilla,
                                            resumen=resumen, **opciones)
        return grupo, resumen

    def _piezas(self, grupo):
        """Ruta de cada nodo de la planta, sin el grupo."""
        nodo = self.escena.buscar(grupo)
        piezas, pila = [], self.escena.hijos(nodo)
        while pila:
            n = pila.pop()
            piezas.append(n)
            pila += self.escena.hijos(n)
        return piezas

    def _comprobar_planta(self, grupo, modelos):
        nodo = self.escena.buscar(grupo)   # la ruta devuelta es única
        piezas = self._piezas(grupo)
        nombres = sorted(p.nombre for p in piezas if p.tipo == "transform")
        self.assertIn("trepadora_tallos", nombres)
        self.assertIn("trepadora_rabillos", nombres)
        instanciadores = [p for p in piezas if p.tipo == "instancer"]
        if modelos:
            self.assertEqual(len(instanciadores), 1)
            hojas = [p for p in instanciadores[0].objetos]
            self.assertEqual(len(hojas), modelos)
            # Las hojas que instancia son las de esta planta, no las de otra.
            for hoja in hojas:
                self.assertIn(hoja, piezas)
                self.assertEqual(hoja.padre.padre, nodo)
        else:
            self.assertEqual(instanciadores, [])
            self.assertIn("trepadora_hojas", nombres)

    def test_dos_plantas_con_instancias(self):
        primera, r1 = self._planta(1)
        segunda, r2 = self._planta(2)
        self.assertNotEqual(primera, segunda)
        self.assertGreater(r1["modelos"], 0)
        self.assertGreater(r2["modelos"], 0)
        self._comprobar_planta(primera, r1["modelos"])
        self._comprobar_planta(segunda, r2["modelos"])
        self.assertEqual(self.escena.avisos, [])

    def test_tres_plantas_mezcladas(self):
        """Con y sin instancias, y dos con la hoja del alumno, en la misma escena."""
        hoja = self.cmds.group(empty=True, name="miHoja")
        self.escena.crear("miHojaShape", "mesh", self.escena.buscar(hoja))
        plantas = [self._planta(1), self._planta(2, instancias=False),
                   self._planta(3, hoja_propia="|miHoja"), self._planta(4),
                   self._planta(5, hoja_propia="|miHoja")]
        for grupo, resumen in plantas:
            self._comprobar_planta(grupo, resumen["modelos"])
        self.assertEqual(len({g for g, _ in plantas}), 5)
        self.assertEqual(self.escena.avisos, [])

    def test_el_maya_falso_no_deja_buscar_nombres_repetidos(self):
        """Que la prueba sirve: con nombres cortos repetidos, Maya falla."""
        a = self.cmds.group(empty=True, name="a")
        b = self.cmds.group(empty=True, name="b")
        for padre in (a, b):
            hijo = self.cmds.group(empty=True, name="x")
            self.cmds.parent(hijo, padre)
            self.cmds.rename("|" + padre + "|" + hijo, "pieza")
        with self.assertRaises(ValueError):
            self.cmds.listRelatives("pieza", parent=True)
        self.assertEqual(len(self.cmds.ls("pieza", long=True)), 2)


if __name__ == "__main__":
    unittest.main()
