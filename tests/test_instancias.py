"""Pruebas de las hojas como instancias, sin Maya.

Ejecutar desde la raíz del repositorio:  python -m unittest discover tests
"""

import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.dirname(__file__))

from trepadora import geometria, instancias  # noqa: E402
from trepadora import vectores as v  # noqa: E402
from trepadora.hojas import ParametrosHojas, colocar_hojas  # noqa: E402
from test_crecimiento import escena  # noqa: E402


def aplicar(datos, i, p):
    """Lleva el punto ``p`` de un modelo a la escena, como el instanciador de Maya."""
    filas = instancias.matriz_euler(datos.giros[i])
    s = datos.escalas[i]
    q = datos.posiciones[i]
    for k in range(3):
        q = v.suma(q, v.escala(filas[k], p[k] * s[k]))
    return q


class PruebasGiros(unittest.TestCase):
    def comprobar(self, x, y, z):
        filas = instancias.matriz_euler(instancias.euler_xyz(x, y, z))
        for fila, eje in zip(filas, (x, y, z)):
            for a, b in zip(fila, eje):
                self.assertAlmostEqual(a, b, places=6)

    def test_ida_y_vuelta(self):
        rng = random.Random(4)
        for _ in range(300):
            z = v.unitario((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)))
            x = v.unitario(v.cruz((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)), z))
            self.comprobar(x, v.cruz(z, x), z)

    def test_bloqueo_del_cardan(self):
        for x in ((0.0, 0.0, 1.0), (0.0, 0.0, -1.0)):
            for z in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.6, 0.8, 0.0)):
                self.comprobar(x, v.cruz(z, x), z)


class PruebasHojasInstanciadas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c = escena(semilla=2)
        cls.hojas = colocar_hojas(c, ParametrosHojas(tamano=2.0))
        cls.datos = instancias.hojas_instanciadas(cls.hojas, semilla=3)

    def test_una_instancia_por_hoja_y_pocos_modelos(self):
        d = self.datos
        self.assertEqual(len(d), len(self.hojas))
        for lista in (d.giros, d.escalas, d.indices, d.colores):
            self.assertEqual(len(lista), len(self.hojas))
        self.assertLessEqual(len(d.modelos), 6 * 4 * 2)
        self.assertTrue(all(0 <= i < len(d.modelos) for i in d.indices))
        # Se usan modelos de varias formas y tonos, no siempre el mismo.
        self.assertGreater(len(set(d.indices)), 10)

    def test_modelos_validos(self):
        for modelo in self.datos.modelos:
            m = modelo.malla
            self.assertEqual(sum(m.conteos), len(m.indices))
            self.assertEqual(len(m.vertices), len(m.colores))
            self.assertTrue(all(0 <= i < len(m.vertices) for i in m.indices))
            # Hoja de largo 1 desde el origen hacia +Y.
            ys = [p[1] for p in m.vertices]
            self.assertAlmostEqual(min(ys), 0.0)
            self.assertAlmostEqual(max(ys), 1.0)

    def test_cada_hoja_queda_donde_la_malla(self):
        d = self.datos
        for i, hoja in enumerate(self.hojas):
            self.assertLess(v.distancia(aplicar(d, i, (0.0, 0.0, 0.0)), hoja.base), 1e-6)
            punta = v.suma(hoja.base, v.escala(hoja.adelante, hoja.tamano))
            self.assertLess(v.distancia(aplicar(d, i, (0.0, 1.0, 0.0)), punta), 1e-3 * hoja.tamano)
            cara = v.resta(aplicar(d, i, (0.0, 0.0, 1.0)), hoja.base)
            self.assertGreater(v.punto(v.unitario(cara), hoja.normal), 0.999)

    def test_color_de_cada_hoja(self):
        d = self.datos
        rng = random.Random(3 * 97 + 3)
        cerca = 0
        for i, hoja in enumerate(self.hojas):
            color = geometria.color_hoja(hoja, rng)
            self.assertEqual(d.colores[i], color)
            modelo = d.modelos[d.indices[i]]
            k = instancias.proporcion(color, modelo.color)
            for a, b, c in zip(modelo.color, k, color):
                self.assertAlmostEqual(a * b, c, places=9)
            if math.sqrt(instancias._distancia2(color, modelo.color)) < 0.04:
                cerca += 1
        # El tono del grupo, que es lo que se ve en el visor, se parece al de la hoja.
        self.assertGreater(cerca / len(self.hojas), 0.9)

    def test_pesa_mucho_menos_que_la_malla(self):
        malla = geometria.malla_hojas(self.hojas, semilla=3)
        en_modelos = sum(len(m.malla.vertices) for m in self.datos.modelos)
        self.assertLess(en_modelos, 0.05 * len(malla.vertices))

    def test_otras_formas_de_hoja(self):
        for forma in ("corazon", "alargada", "redonda"):
            d = instancias.hojas_instanciadas(self.hojas[:200], forma=forma, semilla=1)
            self.assertEqual(len(d), 200)
            self.assertTrue(all(m.lobulado == 1.0 for m in d.modelos))


class PruebasTiposDeTallo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = escena(semilla=2)
        cls.radios = cls.c.grosores(1.0, 0.1)

    def test_todos_los_tipos_dan_mallas_validas(self):
        hojas = colocar_hojas(self.c, ParametrosHojas(tamano=2.0))
        for tipo in geometria.TIPOS_TALLO:
            for malla in (geometria.malla_tallos(self.c, self.radios, tipo=tipo),
                          geometria.malla_peciolos(hojas, tipo=tipo)):
                self.assertEqual(sum(malla.conteos), len(malla.indices))
                self.assertEqual(len(malla.vertices), len(malla.colores))
                self.assertTrue(all(0 <= i < len(malla.vertices) for i in malla.indices))

    def test_la_corteza_nudosa_arruga_el_tubo(self):
        def radios_de_anillo(tipo):
            malla = geometria.malla_tallos(self.c, self.radios, tipo=tipo, lados=8)
            rama = self.c.ramas[0]
            centro = rama.puntos[0]
            return [v.distancia(p, centro) for p in malla.vertices[:8]]
        liso = radios_de_anillo("lenoso")
        nudoso = radios_de_anillo("nudoso")
        self.assertLess(max(liso) - min(liso), 1e-9)
        self.assertGreater(max(nudoso) - min(nudoso), 0.02)

    def test_los_tipos_cambian_el_color(self):
        colores = {tipo: geometria.malla_tallos(self.c, self.radios, tipo=tipo).colores[0]
                   for tipo in geometria.TIPOS_TALLO}
        self.assertEqual(len(set(colores.values())), len(colores))


if __name__ == "__main__":
    unittest.main()
