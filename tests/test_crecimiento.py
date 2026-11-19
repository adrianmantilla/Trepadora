"""Pruebas del algoritmo de crecimiento sin Maya.

Ejecutar desde la raiz del repositorio:  python -m unittest discover tests
"""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from trepadora.crecimiento import Crecimiento, Parametros  # noqa: E402


class Muro:
    """Plano vertical infinito z = 0 con la cara hacia +z."""

    normal = np.array([0.0, 0.0, 1.0])

    def mas_cercano(self, punto):
        p = np.asarray(punto, dtype=float)
        return np.array([p[0], p[1], 0.0]), self.normal


def crecer(superficie, **ajustes):
    c = Crecimiento(superficie, Parametros(**ajustes))
    c.anadir_origen((0.0, 0.0, 0.5))
    c.crecer()
    return c


class PruebasCrecimiento(unittest.TestCase):
    def test_misma_semilla_mismo_resultado(self):
        a = crecer(Muro(), semilla=7, pasos=80)
        b = crecer(Muro(), semilla=7, pasos=80)
        self.assertEqual(len(a.ramas), len(b.ramas))
        for ra, rb in zip(a.ramas, b.ramas):
            np.testing.assert_allclose(ra.como_array(), rb.como_array())

    def test_semilla_distinta_resultado_distinto(self):
        a = crecer(Muro(), semilla=1, pasos=80)
        b = crecer(Muro(), semilla=2, pasos=80)
        self.assertFalse(np.allclose(a.ramas[0].como_array()[-1], b.ramas[0].como_array()[-1]))

    def test_se_pega_al_muro_y_no_lo_atraviesa(self):
        c = crecer(Muro(), semilla=3, pasos=150)
        todos = np.vstack([r.como_array() for r in c.ramas])
        self.assertTrue(np.all(todos[:, 2] >= c.p.separacion - 1e-6))
        self.assertTrue(np.all(todos[:, 2] <= c.p.distancia_adherencia))

    def test_trepa_hacia_la_luz(self):
        c = crecer(Muro(), semilla=3, pasos=150, aleatoriedad=0.2)
        principal = c.ramas[0].como_array()
        self.assertGreater(principal[-1, 1] - principal[0, 1], 50.0)

    def test_ramifica(self):
        c = crecer(Muro(), semilla=5, pasos=150, prob_rama=0.1)
        self.assertGreater(len(c.ramas), 1)
        self.assertTrue(all(r.generacion <= c.p.generaciones_max for r in c.ramas))
        hijas = [r for r in c.ramas if r.generacion > 0]
        self.assertTrue(all(r.madre is not None for r in hijas))

    def test_cuelga_y_muere_al_perder_apoyo(self):
        c = Crecimiento(Muro(), Parametros(semilla=2, prob_rama=0.0, gravedad=1.0))
        rama = c.anadir_origen((0.0, 0.0, 0.5))
        # Separamos la punta del muro, como si hubiera llegado al borde.
        rama.puntos[0] = np.array([0.0, 0.0, 20.0])
        c.crecer(pasos=100)
        puntos = rama.como_array()
        self.assertFalse(rama.viva)
        self.assertLessEqual(len(puntos), c.p.pasos_sueltos_max + 2)
        self.assertLess(puntos[-1, 1], puntos[0, 1])

    def test_limite_de_seguridad(self):
        c = crecer(Muro(), semilla=1, pasos=500, prob_rama=0.5, limite_puntos=400,
                   generaciones_max=6, reduccion_por_generacion=0.95)
        self.assertTrue(c.limite_alcanzado)
        self.assertLessEqual(c.total_puntos, 400 + len(c.ramas))

    def test_cancelar_conserva_lo_generado(self):
        c = Crecimiento(Muro(), Parametros(pasos=100))
        c.anadir_origen((0.0, 0.0, 0.5))
        hechos = c.crecer(al_progresar=lambda paso, total: paso < 10)
        self.assertEqual(hechos, 10)
        self.assertEqual(len(c.ramas[0].puntos), 11)


if __name__ == "__main__":
    unittest.main()
