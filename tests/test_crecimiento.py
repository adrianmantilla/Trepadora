"""Pruebas del algoritmo de crecimiento sin Maya.

Ejecutar desde la raíz del repositorio:  python -m unittest discover tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.dirname(__file__))

from trepadora.crecimiento import Crecimiento, Parametros, consultar  # noqa: E402
from trepadora import vectores as v  # noqa: E402
from trepadora import geometria  # noqa: E402
from trepadora.hojas import ParametrosHojas, colocar_hojas, _recorrido  # noqa: E402
from superficies import Muro, escena_de_prueba, escena_ruina  # noqa: E402
from trepadora import escenas  # noqa: E402
from trepadora.zonas import Zona, Zonas  # noqa: E402
from trepadora.guias import Guias  # noqa: E402


def crecer(superficie, origen=(0.0, 0.0, 0.5), zonas=None, guias=None, **ajustes):
    c = Crecimiento(superficie, Parametros(**ajustes), zonas=zonas, guias=guias)
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


class PruebasSuperficie(unittest.TestCase):
    class _Fija:
        """Devuelve siempre el mismo punto y la normal indicada."""

        def __init__(self, cercano, normal):
            self.r = (cercano, normal)

        def mas_cercano(self, punto):
            return self.r

    def test_en_una_arista_la_normal_no_depende_de_la_cara(self):
        # Punto por delante y por encima de la arista superior de un muro: el
        # más cercano es la arista, y una superficie puede dar la normal del
        # frente y otra la de arriba (Maya da la de la primera cara que mira).
        punto, arista = (0.0, 101.0, 11.0), (0.0, 100.0, 10.0)
        frente = consultar(self._Fija(arista, (0.0, 0.0, 1.0)), punto)[1]
        arriba = consultar(self._Fija(arista, (0.0, 1.0, 0.0)), punto)[1]
        for a, b in zip(frente, arriba):
            self.assertAlmostEqual(a, b, places=9)
        self.assertAlmostEqual(frente[1], frente[2], places=9)

    def test_delante_de_una_cara_se_queda_su_normal(self):
        n = consultar(self._Fija((3.0, 50.0, 10.0), (0.0, 0.0, 1.0)), (3.0, 50.0, 10.2))[1]
        self.assertEqual(n, (0.0, 0.0, 1.0))


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
        self.assertLessEqual(len(rama.puntos), c._sueltos_max + 2)
        self.assertLess(rama.puntos[-1][1], rama.puntos[0][1])

    def test_limite_de_seguridad(self):
        c = crecer(Muro(), semilla=1, pasos=500, prob_rama=0.5, limite_puntos=400,
                   generaciones_max=6, reduccion_por_generacion=0.95)
        self.assertTrue(c.limite_alcanzado)
        self.assertLessEqual(c.total_puntos, 400 + len(c.ramas))

    def test_cada_rama_parada_dice_por_que(self):
        c = escena(semilla=3, pasos=900)
        self.assertFalse(any(r.viva for r in c.ramas))
        motivos = c.motivos_de_parada()
        self.assertTrue(set(motivos) <= {"largo", "aire", "suelo", "espacio"}, motivos)
        self.assertEqual(sum(motivos.values()), c.total_puntos)
        corta = escena(semilla=3, pasos=900, longitud_max=30, generaciones_max=1)
        self.assertEqual(max(corta.motivos_de_parada(), key=corta.motivos_de_parada().get),
                         "largo")
        limite = crecer(Muro(), semilla=1, pasos=500, prob_rama=0.5, limite_puntos=400,
                        generaciones_max=6, reduccion_por_generacion=0.95)
        self.assertIn("limite", limite.motivos_de_parada())

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
        # Los tallos colgantes están en el aire a propósito: no cuentan.
        puntos = [q for r in c.ramas if not r.colgante for q in r.puntos]
        lejos = [q for q in puntos if v.distancia(q, sup.mas_cercano(q)[0]) > c.p.distancia_adherencia]
        self.assertLess(len(lejos) / len(puntos), 0.1)

    def test_matas_y_claros_repartidos_en_escena_pequena(self):
        # En una escena pequeña, una sola mancha de ruido de matas puede
        # cubrir todo el muro. El campo de matas va por percentiles: cada
        # planta tiene la misma proporción de matas y de claros.
        from trepadora import hojas
        c = escena(semilla=4, gravedad=1.0, prob_rama=0.08)
        escala = c.p.longitud_paso * 2.4 * ParametrosHojas().escala_manchas
        valores = [x for fila in hojas._campo_de_matas(c, escala, 4) for x in fila]
        self.assertAlmostEqual(sum(valores) / len(valores), 0.5, delta=0.02)
        claros = sum(1 for x in valores if x < 0.3) / len(valores)
        self.assertGreater(claros, 0.25)
        self.assertLess(claros, 0.35)

    def test_ramillas_cortas_que_no_se_ramifican(self):
        c = escena(semilla=2, ramillas=0.1)
        ramillas = [r for r in c.ramas if r.ramilla]
        self.assertGreater(len(ramillas), 10)
        for r in ramillas:
            self.assertLessEqual(len(r.puntos), c.p.largo_ramilla)
            self.assertFalse(r.hijas)
        # Sin ramillas no sale ninguna.
        self.assertFalse(any(r.ramilla for r in escena(semilla=2).ramas))


def ruina(**cambios):
    ajustes = dict(escenas.RUINA["ajustes"])
    ajustes.update(cambios)
    paso = ajustes.pop("paso")
    ajustes.pop("hojas", None)
    base = dict(longitud_paso=paso, distancia_adherencia=paso * 3, separacion=paso * 0.05,
                radio_espacio=paso * 2)
    base.update(ajustes)
    c = Crecimiento(escena_ruina(), Parametros(**base))
    for o in escenas.RUINA["origenes"]:
        c.anadir_origen(o)
    c.crecer()
    return c


_RUINAS = {}


def ruina_de_semilla(semilla):
    """La ruina con los ajustes de escenas.py, creciendo una sola vez por semilla."""
    if semilla not in _RUINAS:
        _RUINAS[semilla] = ruina(semilla=semilla)
    return _RUINAS[semilla]


def calvas_frente(hojas, celda=10.0):
    """Calvas del frente del muro de la ruina (z = 10), sin contar la ventana.

    Devuelve la fracción de celdas sin ninguna hoja y el tamaño (en celdas)
    de la mayor mancha de celdas vacías contiguas.
    """
    x0, x1, y0, y1 = -150.0, 150.0, 0.0, 230.0
    nx, ny = int((x1 - x0) // celda), int((y1 - y0) // celda)
    llenas = set()
    for h in hojas:
        centro = [h.base[i] + h.adelante[i] * h.tamano * 0.5 for i in range(3)]
        if -1.0 <= centro[2] - 10.0 <= 14.0:
            llenas.add((int((centro[0] - x0) // celda), int((centro[1] - y0) // celda)))
    validas = {(i, j) for i in range(nx) for j in range(ny)
               if not (-40.0 <= x0 + (i + 0.5) * celda <= 40.0
                       and 80.0 <= y0 + (j + 0.5) * celda <= 180.0)}
    vacias = validas - llenas
    mayor, vistas = 0, set()
    for celda_vacia in vacias:
        if celda_vacia in vistas:
            continue
        pila, n = [celda_vacia], 0
        vistas.add(celda_vacia)
        while pila:
            i, j = pila.pop()
            n += 1
            for q in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if q in vacias and q not in vistas:
                    vistas.add(q)
                    pila.append(q)
        mayor = max(mayor, n)
    return len(vacias) / float(len(validas)), mayor


class PruebasRuina(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = ruina_de_semilla(1)

    def test_busca_las_paredes_en_vez_de_reptar_por_el_suelo(self):
        puntos = todos(self.c)
        en_suelo = [q for q in puntos if q[1] < 3.0]
        self.assertLess(len(en_suelo) / len(puntos), 0.15)
        # Cada planta sube por su pared o su columna.
        for rama in self.c.ramas[:len(escenas.RUINA["origenes"])]:
            self.assertGreater(max(q[1] for q in rama.puntos), 40.0)

    def test_el_frente_del_muro_no_tiene_grandes_calvas(self):
        # Las hojas cubren el frente del muro sin dejar grandes manchas de
        # piedra desnuda (celdas de 10 cm: 40 celdas son 0,4 m²).
        tamano = escenas.RUINA["ajustes"]["paso"] * 2.4 * escenas.RUINA["ajustes"]["hojas"]["tamano"]
        for semilla in (1, 2, 3):
            c = ruina_de_semilla(semilla)
            hojas = colocar_hojas(c, ParametrosHojas(semilla=semilla, tamano=tamano))
            vacias, mayor = calvas_frente(hojas)
            self.assertLess(vacias, 0.12, "semilla %d" % semilla)
            self.assertLess(mayor, 40, "semilla %d" % semilla)

    def test_las_hojas_de_los_colgantes_no_quedan_de_canto(self):
        # Un tallo que cuelga bajo un saliente (el dintel de la ventana) tiene
        # por superficie más cercana un techo: sus hojas no deben quedar
        # tumbadas mirando arriba o abajo, que de frente no se ven.
        tamano = escenas.RUINA["ajustes"]["paso"] * 2.4 * escenas.RUINA["ajustes"]["hojas"]["tamano"]
        hojas = colocar_hojas(self.c, ParametrosHojas(semilla=1, tamano=tamano))
        colgantes = {tuple(round(x, 4) for x in q)
                     for r in self.c.ramas if r.colgante for q in r.puntos[1:]}
        suyas = [h for h in hojas if tuple(round(x, 4) for x in h.tallo) in colgantes]
        tumbadas = [h for h in suyas if abs(h.normal[1]) > 0.8]
        self.assertGreater(len(suyas), 100)
        self.assertLess(len(tumbadas), 0.04 * len(suyas))

    def hojas(self, **ajustes):
        tamano = escenas.RUINA["ajustes"]["paso"] * 2.4 * escenas.RUINA["ajustes"]["hojas"]["tamano"]
        return colocar_hojas(self.c, ParametrosHojas(semilla=1, tamano=tamano, **ajustes))

    def test_sin_hojas_de_pie_sobre_los_remates(self):
        # En lo alto de los muros, del murete y del alféizar, las hojas no
        # asoman de pie como banderas: se tumban sobre el remate o caen por
        # la pared.
        sup = escena_ruina()
        encima = de_pie = 0
        for h in self.hojas():
            punta = v.suma(h.base, v.escala(h.adelante, h.tamano * 0.6))
            cercano, normal = sup.mas_cercano(punta)
            if (normal[1] > 0.9 and cercano[1] > 5.0
                    and v.punto(v.resta(punta, cercano), normal) < h.tamano * 1.2):
                encima += 1
                de_pie += abs(h.normal[1]) < 0.5
        self.assertGreater(encima, 200)
        self.assertLess(de_pie, 0.05 * encima)

    def test_en_las_paredes_las_hojas_cuelgan_o_salen_de_lado(self):
        # En una pared, la hiedra no pone hojas de pie como banderas ni
        # derechas hacia fuera como aletas: la lámina queda de lado o colgando.
        # Las de los tallos que cuelgan junto a una jamba no cuentan: miran al
        # hueco a propósito.
        sup = escena_ruina()
        colgantes = {q for r in self.c.ramas if r.colgante for q in r.puntos}
        en_pared = arriba = aletas = 0
        for h in self.hojas():
            _, normal = sup.mas_cercano(h.tallo)
            if normal is None or abs(normal[1]) > 0.3 or h.tallo in colgantes:
                continue
            en_pared += 1
            arriba += h.adelante[1] > 0.5
            aletas += v.punto(h.adelante, normal) > 0.7
        self.assertGreater(en_pared, 3000)
        self.assertLess(arriba, 0.005 * en_pared)
        self.assertLess(aletas, 0.015 * en_pared)

    def test_hojas_bronce_sueltas_entre_las_verdes(self):
        # Alrededor de una de cada cien hojas tira a bronce, sueltas entre las
        # verdes: dos o tres juntas ya se leen como una mancha rojiza, y una
        # mancha llama la atención como un fallo.
        hojas = self.hojas()
        bronce = [h for h in hojas if h.tinte > 0.0]
        self.assertGreater(len(bronce), 0.004 * len(hojas))
        self.assertLess(len(bronce), 0.025 * len(hojas))
        for i, h in enumerate(bronce):
            for o in bronce[:i]:
                self.assertGreater(v.distancia(o.base, h.base), 10.0)

    def test_hojas_mayores_cerca_de_la_raiz(self):
        # La planta no es una alfombra uniforme: las hojas adultas de la parte
        # vieja, cerca de la raíz, son mayores que las del crecimiento nuevo.
        # Se juntan tres semillas: en una sola, las hojas lejanas salen de
        # pocas ramas y el vigor de cada una pesa demasiado.
        tamano = escenas.RUINA["ajustes"]["paso"] * 2.4 * escenas.RUINA["ajustes"]["hojas"]["tamano"]
        cerca, lejos = [], []
        for semilla in (1, 2, 3):
            c = ruina_de_semilla(semilla)
            recorrido = _recorrido(c)
            donde = {q: recorrido[i][k] for i, r in enumerate(c.ramas)
                     for k, q in enumerate(r.puntos)}
            for h in colocar_hojas(c, ParametrosHojas(semilla=semilla, tamano=tamano,
                                                      variacion=0.0)):
                if h.edad >= 1.0:
                    d = donde[h.tallo]
                    if d < 0.3:
                        cerca.append(h.tamano)
                    elif d > 0.7:
                        lejos.append(h.tamano)
        self.assertGreater(len(lejos), 300)
        self.assertGreater(sum(cerca) / len(cerca), 1.25 * sum(lejos) / len(lejos))

    def test_el_tronco_se_ve_entre_las_hojas(self):
        # Los tallos gruesos de la base dan menos hojas que las ramas finas.
        grosor = self.c.grosores(1.0, 0.0)
        donde = {q: grosor[i][k] for i, r in enumerate(self.c.ramas)
                 for k, q in enumerate(r.puntos)}
        puntos = {"grueso": 0, "fino": 0}
        hojas = {"grueso": 0, "fino": 0}
        for g in donde.values():
            if g > 0.6 or g < 0.3:
                puntos["grueso" if g > 0.6 else "fino"] += 1
        for h in self.hojas():
            g = donde[h.tallo]
            if g > 0.6 or g < 0.3:
                hojas["grueso" if g > 0.6 else "fino"] += 1
        self.assertLess(hojas["grueso"] / puntos["grueso"], 0.5 * hojas["fino"] / puntos["fino"])

    def test_pocas_hojas_sueltas_por_el_suelo(self):
        # Los tallos que reptan por el suelo dan pocas hojas: si no, el pie de
        # los muros queda rodeado de una falda de hojas sueltas.
        suelo = {q for r in self.c.ramas for q, n in zip(r.puntos, r.normales)
                 if n[1] > 0.8 and q[1] < 4.0}
        hojas = self.hojas()
        self.assertLess(sum(h.tallo in suelo for h in hojas), 0.03 * len(hojas))

    def test_nada_bajo_el_suelo(self):
        # El suelo de la escena es una caja fina: ningún paso debe atravesarla.
        self.assertGreaterEqual(min(q[1] for q in todos(self.c)), -1e-6)

    def test_cuelgan_tallos_de_los_bordes(self):
        colgantes = [r for r in self.c.ramas if r.colgante]
        self.assertGreater(len(colgantes), 5)
        # Cuelgan: todos bajan, y en conjunto bajan bastante más de lo que se
        # desplazan de lado (los que se arrastran por una pared serpentean).
        total_caida = total_lado = 0.0
        for r in colgantes:
            if len(r.puntos) < 10:
                continue
            caida = r.puntos[0][1] - r.puntos[-1][1]
            lado = v.distancia((r.puntos[0][0], 0.0, r.puntos[0][2]),
                               (r.puntos[-1][0], 0.0, r.puntos[-1][2]))
            self.assertGreater(caida, 0.0)
            total_caida += caida
            total_lado += lado
        self.assertGreater(total_caida, 1.5 * total_lado)

    def test_los_colgantes_libres_caen_mas_rectos(self):
        # Un tallo que cuelga en el aire (en la ventana) cae casi a plomo; uno
        # que se arrastra por la pared serpentea.
        libres = [r for r in self.c.ramas if r.colgante and r.roce == 0 and len(r.puntos) >= 10]
        self.assertTrue(libres)
        for r in libres:
            caida = r.puntos[0][1] - r.puntos[-1][1]
            lado = v.distancia((r.puntos[0][0], 0.0, r.puntos[0][2]),
                               (r.puntos[-1][0], 0.0, r.puntos[-1][2]))
            self.assertGreater(caida, 2.0 * lado)

    def test_sin_buscar_paredes_reptan_por_el_suelo(self):
        c = ruina(semilla=1, buscar_paredes=0.0, pasos=120)
        puntos = todos(c)
        en_suelo = [q for q in puntos if q[1] < 3.0]
        self.assertGreater(len(en_suelo) / len(puntos), 0.3)


class PruebasGrosorHojasMallas(unittest.TestCase):
    def setUp(self):
        self.c = escena(semilla=2)
        self.radios = self.c.grosores(1.0, 0.1)

    def test_grosor_se_afina_hacia_las_puntas(self):
        principal = self.radios[0]
        self.assertAlmostEqual(principal[0], 1.0)
        self.assertTrue(all(a >= b - 1e-9 for a, b in zip(principal, principal[1:])))
        for i, rama in enumerate(self.c.ramas):
            if rama.madre is not None:
                madre = self.radios[rama.madre][rama.indice_en_madre]
                self.assertLessEqual(self.radios[i][0], madre + 1e-9)

    def test_hojas_mas_pequenas_en_las_puntas(self):
        hojas = colocar_hojas(self.c, ParametrosHojas(tamano=2.0, variacion=0.0))
        self.assertGreater(len(hojas), 100)
        jovenes = [h.tamano for h in hojas if h.edad < 0.5]
        adultas = [h.tamano for h in hojas if h.edad >= 1.0]
        self.assertLess(sum(jovenes) / len(jovenes), sum(adultas) / len(adultas))
        for h in hojas:
            self.assertAlmostEqual(v.punto(h.adelante, h.normal), 0.0, places=6)

    def test_hojas_no_atraviesan_la_superficie(self):
        sup = escena_de_prueba()
        hojas = colocar_hojas(self.c, ParametrosHojas(tamano=4.0))
        dentro = 0
        for h in hojas:
            punta = v.suma(h.base, v.escala(h.adelante, h.tamano))
            cercano, normal = sup.mas_cercano(punta)
            if v.punto(v.resta(punta, cercano), normal) < -0.5:
                dentro += 1
        self.assertLess(dentro / len(hojas), 0.01)

    def test_hojas_no_se_meten_en_el_suelo_al_pie_del_muro(self):
        # En Maya el suelo es un plano: todo lo que queda por debajo está
        # "dentro". Se simula con un suelo muy grueso. Las hojas de los tallos
        # que suben por el pie del muro no deben hundirse en él.
        from superficies import Cajas
        cajas = escenas.cajas_min_max(escenas.SENCILLA)
        lo, hi = cajas[0]
        cajas[0] = ((lo[0], -300.0, lo[2]), hi)
        sup = Cajas(cajas)
        paso = (400.0 ** 2 + 151.0 ** 2 + 400.0 ** 2) ** 0.5 / 150.0
        c = crecer(sup, origen=(-20.0, 2.0, 5.5), longitud_paso=paso,
                   distancia_adherencia=paso * 3, separacion=paso * 0.05,
                   radio_espacio=paso * 2, semilla=4, gravedad=1.0, prob_rama=0.08)
        hojas = colocar_hojas(c, ParametrosHojas(semilla=4, tamano=paso * 2.4))
        malla = geometria.malla_hojas(hojas)
        hundidos = [p for p in malla.vertices if p[1] < -0.1 * paso]
        self.assertLess(len(hundidos), 0.001 * len(malla.vertices))

    def test_mallas_validas(self):
        hojas = colocar_hojas(self.c, ParametrosHojas(tamano=2.0))
        for malla in (geometria.malla_tallos(self.c, self.radios), geometria.malla_hojas(hojas),
                      geometria.malla_peciolos(hojas)):
            self.assertEqual(sum(malla.conteos), len(malla.indices))
            self.assertEqual(len(malla.vertices), len(malla.colores))
            self.assertTrue(all(0 <= i < len(malla.vertices) for i in malla.indices))
            self.assertTrue(all(n in (3, 4) for n in malla.conteos))

    def _mallas(self, forma="hiedra"):
        hojas = colocar_hojas(self.c, ParametrosHojas(tamano=2.0))
        return {"tallos": geometria.malla_tallos(self.c, self.radios, tipo="nudoso"),
                "hojas": geometria.malla_hojas(hojas, forma=forma),
                "rabillos": geometria.malla_peciolos(hojas)}

    def test_uvs_validas(self):
        for forma in geometria.FORMAS_HOJA:
            for nombre, malla in self._mallas(forma).items():
                with self.subTest(forma=forma, malla=nombre):
                    self.assertEqual(len(malla.uv_indices), len(malla.indices))
                    self.assertTrue(all(0 <= i < len(malla.uvs) for i in malla.uv_indices))
                    if nombre != "tallos":   # una UV por vértice
                        self.assertEqual(len(malla.uvs), len(malla.vertices))
                        self.assertEqual(malla.uv_indices, malla.indices)

    def test_uvs_de_hoja_dentro_del_cuadrado(self):
        """Cada forma cabe en su textura, con el nervio en u = 0,5 y la base abajo."""
        for forma in geometria.FORMAS_HOJA:
            uvs = self._mallas(forma)["hojas"].uvs
            us, vs = [u for u, _ in uvs], [v_ for _, v_ in uvs]
            with self.subTest(forma=forma):
                self.assertGreater(min(us), 0.0)
                self.assertLess(max(us), 1.0)
                self.assertGreater(min(vs), 0.0)
                self.assertLess(max(vs), 1.0)
                self.assertAlmostEqual(min(vs) + max(vs), 1.0, places=6)
                # La hoja más ancha llena la textura (sin desperdiciar más de un 15 %).
                if geometria.ESCALA_UV[forma] > 1.1:
                    self.assertGreater(max(us) - min(us), 0.85)
        modelo = geometria.Malla()
        geometria._lamina(modelo, geometria.perfil_hoja("hiedra"), (0.3, 0.4, 0.1, 0.1),
                          __import__("random").Random(1), (0.1, 0.3, 0.1),
                          lambda cx, cy, cz: (cx, cy, cz), geometria.ESCALA_UV["hiedra"])
        # Mismas UVs aunque la hoja se curve, se pliegue y se tuerza: el nervio
        # central (u = 0,5) va de la base a la punta.
        nervio = [i for i, (u, _) in enumerate(modelo.uvs) if abs(u - 0.5) < 1e-9]
        self.assertEqual(len(nervio), len(geometria.perfil_hoja("hiedra")))

    def test_uvs_de_tallo_con_costura_y_avance(self):
        """La textura da una vuelta al tubo y avanza a lo largo de la rama."""
        malla = self._mallas()["tallos"]
        lados = geometria.TIPOS_TALLO["nudoso"]["lados"]
        us = [u for u, _ in malla.uvs]
        self.assertAlmostEqual(min(us), 0.0)
        self.assertAlmostEqual(max(us), 1.0)
        # Cada cara de un anillo al siguiente abarca un lado (1/lados de vuelta),
        # también la de la costura, que va de u = (lados-1)/lados a u = 1.
        k = 0
        for n in malla.conteos:
            caras = [malla.uvs[i] for i in malla.uv_indices[k:k + n]]
            k += n
            ancho = max(u for u, _ in caras) - min(u for u, _ in caras)
            self.assertLessEqual(ancho, 1.0 / lados + 1e-9)
            if n == 4:
                self.assertLess(caras[0][1], caras[3][1])   # v avanza hacia la punta
        # A lo largo, la textura no se estira: en el tronco, un lado de un
        # anillo y un tramo de rama de la misma medida tienen la misma v.
        rama, radios = self.c.ramas[0], self.radios[0]
        largo = sum(v.largo(v.resta(b, a)) for a, b in zip(rama.puntos, rama.puntos[1:4]))
        vueltas = largo / (2.0 * 3.141592653589793 * radios[1])
        v3 = malla.uvs[(lados + 1) * 3][1]
        self.assertAlmostEqual(v3, vueltas, delta=0.15 * vueltas)



class PruebasZonas(unittest.TestCase):
    def test_caja_girada_escalada_y_movida(self):
        # Caja de 1 x 1 x 1 girada 90 grados en Y, con su X local escalada x2
        # y llevada a (10, 0, 0). Matriz por filas, como cmds.xform: cada fila
        # es un eje local en el mundo y la traslación va al final.
        matriz = [0, 0, -2, 0, 0, 1, 0, 0, 1, 0, 0, 0, 10, 0, 0, 1]
        z = Zona.desde_caja((-0.5, -0.5, -0.5), (0.5, 0.5, 0.5), matriz)
        self.assertTrue(z.dentro((10.0, 0.0, 0.9)))     # X local (x2) -> Z del mundo
        self.assertFalse(z.dentro((10.0, 0.0, 1.1)))
        self.assertTrue(z.dentro((10.4, 0.0, 0.0)))     # Z local -> X del mundo
        self.assertFalse(z.dentro((10.6, 0.0, 0.0)))

    def test_distancia_y_empuje(self):
        z = Zona.desde_caja((0, 0, 0), (10, 10, 10))
        d, fuera = z.distancia((15, 5, 5))
        self.assertAlmostEqual(d, 5.0)
        self.assertEqual(fuera, (1.0, 0.0, 0.0))
        d, fuera = z.distancia((5, 9, 5))
        self.assertAlmostEqual(d, -1.0)                 # dentro: sale por arriba
        self.assertEqual(fuera, (0.0, 1.0, 0.0))
        zonas = Zonas([z])
        self.assertIsNone(zonas.empuje((30, 5, 5), 10.0))
        fuera, fuerza, centro = zonas.empuje((15, 5, 5), 10.0)
        self.assertAlmostEqual(fuerza, 0.5)
        self.assertEqual(centro, (5.0, 5.0, 5.0))

    # Una ventana: caja delante del muro de la escena sencilla, con el origen
    # justo debajo de ella.
    VENTANA = Zona.desde_caja((-50, 40, -1), (10, 100, 12))

    def test_no_crece_ni_pone_hojas_dentro_y_la_rodea(self):
        for semilla in (1, 2, 3):
            c = escena(semilla=semilla, zonas=[self.VENTANA])
            puntos = todos(c)
            self.assertFalse([q for q in puntos if self.VENTANA.dentro(q)])
            # Sube igualmente por encima de la ventana: la rodea.
            encima = [q for q in puntos if q[1] > 100 and -50 < q[0] < 10]
            self.assertGreater(len(encima), 50, semilla)
            hojas = colocar_hojas(c, ParametrosHojas(tamano=4.0))
            for h in hojas:
                for f in (0.0, 0.5, 1.0):
                    self.assertFalse(self.VENTANA.dentro(v.suma(h.base, v.escala(h.adelante,
                                                                                h.tamano * f))))
        # Sin la zona, sí crece por donde está la ventana.
        self.assertTrue([q for q in todos(escena(semilla=1)) if self.VENTANA.dentro(q)])


class PruebasGuias(unittest.TestCase):
    # Curva horizontal sobre el muro, de x = -20 a x = 80, a 30 de altura.
    GUIA = [(-20.0 + 4.0 * k, 30.0, 5.0) for k in range(26)]

    def test_punto_mas_cercano_y_tiron(self):
        g = Guias([self.GUIA], alcance=10.0)
        q, rumbo, d, final = g.mas_cercano((10.0, 36.0, 5.0))
        self.assertAlmostEqual(q[1], 30.0)
        self.assertAlmostEqual(d, 6.0)
        self.assertEqual(rumbo, (1.0, 0.0, 0.0))
        self.assertFalse(final)
        direccion, fuerza = g.tiron((10.0, 36.0, 5.0))
        self.assertGreater(direccion[0], 0.5)           # a lo largo de la curva
        self.assertLess(direccion[1], 0.0)              # y de vuelta hacia ella
        self.assertGreater(g.tiron((10.0, 30.5, 5.0))[1], fuerza)
        # Pasada la punta, ya no tira hacia atrás y se apaga.
        direccion, _ = g.tiron((85.0, 30.0, 5.0))
        self.assertEqual(direccion, (1.0, 0.0, 0.0))
        self.assertIsNone(g.tiron((95.0, 30.0, 5.0)))
        self.assertEqual(g.inicios(), [((-20.0, 30.0, 5.0), (1.0, 0.0, 0.0))])

    def test_el_tallo_sigue_la_curva(self):
        for semilla in (1, 2, 3):
            c = escena(semilla=semilla, guias=[self.GUIA])
            puntos = todos(c)
            cubiertos = [q for q in self.GUIA if any(v.distancia(q, p) < 6.0 for p in puntos)]
            self.assertGreaterEqual(len(cubiertos), 0.9 * len(self.GUIA), semilla)
            # El tallo principal llega al final del muro, siguiendo la curva.
            self.assertGreater(max(q[0] for q in c.ramas[0].puntos), 90.0, semilla)
        # Sin guía, el tallo principal sube en vez de ir de lado.
        sin_guia = [max(q[0] for q in escena(semilla=s).ramas[0].puntos) for s in (1, 2, 3)]
        self.assertLess(min(sin_guia), 60.0)


if __name__ == "__main__":
    unittest.main()
