"""Pruebas del algoritmo de crecimiento sin Maya.

Ejecutar desde la raíz del repositorio:  python -m unittest discover tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.dirname(__file__))

from trepadora.crecimiento import Crecimiento, Parametros  # noqa: E402
from trepadora import vectores as v  # noqa: E402
from superficies import Muro, escena_de_prueba  # noqa: E402


def crecer(superficie, origen=(0.0, 0.0, 0.5), **ajustes):
    c = Crecimiento(superficie, Parametros(**ajustes))
    c.anadir_origen(origen)
    c.crecer()
    return c


def todos(c):
    return [q for r in c.ramas for q in r.puntos]


def escena(**ajustes):
    # Mismas escalas que calcula prototipo._parametros_para para esta escena.
    paso = (400.0 ** 2 + 151.0 ** 2 + 400.0 ** 2) ** 0.5 / 150.0
    base = dict(longitud_paso=paso, distancia_adherencia=paso * 3, separacion=paso * 0.05,
                radio_espacio=paso * 2)
    base.update(ajustes)
    return crecer(escena_de_prueba(), origen=(-20.0, 2.0, 5.5), **base)


class PruebasVectores(unittest.TestCase):
    def test_limitar_giro(self):
        d = v.limitar_giro((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), 0.5, (0.0, 0.0, 1.0))
        self.assertAlmostEqual(v.angulo_entre((1.0, 0.0, 0.0), d), 0.5, places=6)


class PruebasCrecimiento(unittest.TestCase):
    def test_misma_semilla_mismo_resultado(self):
        a = crecer(Muro(), semilla=7, pasos=80)
        b = crecer(Muro(), semilla=7, pasos=80)
        self.assertEqual([r.puntos for r in a.ramas], [r.puntos for r in b.ramas])

    def test_semilla_distinta_resultado_distinto(self):
        a = crecer(Muro(), semilla=1, pasos=80)
        b = crecer(Muro(), semilla=2, pasos=80)
        self.assertNotEqual(a.ramas[0].puntos[-1], b.ramas[0].puntos[-1])

    def test_se_pega_al_muro_y_no_lo_atraviesa(self):
        c = crecer(Muro(), semilla=3, pasos=150)
        zs = [q[2] for q in todos(c)]
        self.assertGreaterEqual(min(zs), c.p.separacion - 1e-6)
        self.assertLessEqual(max(zs), c.p.distancia_adherencia)

    def test_trepa_hacia_la_luz(self):
        c = crecer(Muro(), semilla=3, pasos=150)
        principal = c.ramas[0].puntos
        self.assertGreater(principal[-1][1] - principal[0][1], 40.0)

    def test_giro_limitado(self):
        c = crecer(Muro(), semilla=4, pasos=150, giro_max=30.0)
        limite = v.math.radians(30.0 + 3.0)  # margen por el ajuste a la superficie
        for r in c.ramas:
            for a, b, d in zip(r.puntos, r.puntos[1:], r.puntos[2:]):
                u1, u2 = v.unitario(v.resta(b, a)), v.unitario(v.resta(d, b))
                if u1 and u2:
                    self.assertLessEqual(v.angulo_entre(u1, u2), limite)

    def test_ramifica_desde_cualquier_punto(self):
        c = crecer(Muro(), semilla=5, pasos=150, prob_rama=0.1)
        hijas = [r for r in c.ramas if r.generacion > 0]
        self.assertTrue(hijas)
        self.assertTrue(all(r.generacion <= c.p.generaciones_max for r in c.ramas))
        for h in hijas:
            madre = c.ramas[h.madre]
            self.assertIn(h.puntos[0], madre.puntos)
        # No todas nacen en la punta de la madre.
        self.assertTrue(any(h.puntos[0] != c.ramas[h.madre].puntos[-1] for h in hijas))

    def test_cuelga_y_muere_al_perder_apoyo(self):
        c = Crecimiento(Muro(), Parametros(semilla=2, prob_rama=0.0, gravedad=1.0, adherencia=0.0))
        rama = c.anadir_origen((0.0, 0.0, 0.5))
        rama.puntos[0] = (0.0, 0.0, 20.0)
        c.crecer(pasos=100)
        self.assertFalse(rama.viva)
        self.assertLessEqual(len(rama.puntos), c.p.pasos_sueltos_max + 2)
        self.assertLess(rama.puntos[-1][1], rama.puntos[0][1])

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


class PruebasEscena(unittest.TestCase):
    """Comportamiento en la escena de prueba (suelo, muro y caja)."""

    def test_no_se_amontona_en_el_borde_superior(self):
        c = escena(semilla=1)
        puntos = todos(c)
        arriba = [q for q in puntos if q[1] > 140.0]
        self.assertLess(len(arriba) / len(puntos), 0.35)

    def test_pocas_ramas_en_el_aire(self):
        c = escena(semilla=4, gravedad=1.0, prob_rama=0.08)
        sup = escena_de_prueba()
        lejos = [q for q in todos(c) if v.distancia(q, sup.mas_cercano(q)[0]) > c.p.distancia_adherencia]
        self.assertLess(len(lejos) / c.total_puntos, 0.1)


if __name__ == "__main__":
    unittest.main()
