"""Exportar: hornear las hojas instanciadas, juntar mallas y el mapa de color.

Lo que depende de Maya (leer la escena, FBX, Alembic) se prueba dentro de Maya
con el paso «exportar» de ``herramientas/prueba_ventana.py``.

Ejecutar desde la raíz del repositorio:  python -m unittest discover tests
"""

import os
import random
import shutil
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))
sys.path.insert(0, AQUI)

from superficies import Muro  # noqa: E402
from trepadora import exportar, geometria, instancias, texturas  # noqa: E402
from trepadora import vectores as v  # noqa: E402
from trepadora.crecimiento import Crecimiento, Parametros  # noqa: E402
from trepadora.hojas import ParametrosHojas, colocar_hojas  # noqa: E402


def _cerca(a, b, tol=1e-6):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _hojas(semilla=1):
    c = Crecimiento(Muro(), Parametros(semilla=semilla, pasos=40))
    c.anadir_origen((0.0, 0.0, 0.5))
    c.crecer()
    return colocar_hojas(c, ParametrosHojas(semilla=semilla, tamano=0.3))


class PruebasMatrices(unittest.TestCase):
    def test_multiplicar_aplica_primero_la_primera(self):
        mover = exportar.IDENTIDAD[:12] + (1.0, 2.0, 3.0, 1.0)
        doble = (2.0, 0, 0, 0, 0, 2.0, 0, 0, 0, 0, 2.0, 0, 0, 0, 0, 1.0)
        p = (1.0, 1.0, 1.0)
        self.assertTrue(_cerca(exportar.transformar(p, exportar.multiplicar(mover, doble)),
                               (4.0, 6.0, 8.0)))
        self.assertTrue(_cerca(exportar.transformar(p, exportar.multiplicar(doble, mover)),
                               (3.0, 4.0, 5.0)))

    def test_la_instancia_pone_la_hoja_donde_va(self):
        """El eje y del modelo (de la base a la punta) acaba a lo largo de la hoja."""
        for hoja in _hojas()[:50]:
            x, y, z = instancias.ejes_hoja(hoja)
            giro = instancias.euler_xyz(x, y, z)
            s = hoja.tamano
            m = exportar.matriz_instancia(hoja.base, giro, (s, s, s))
            self.assertTrue(_cerca(exportar.transformar((0.0, 0.0, 0.0), m), hoja.base))
            punta = exportar.transformar((0.0, 1.0, 0.0), m)
            self.assertTrue(_cerca(punta, v.suma(hoja.base, v.escala(y, s)), 1e-6))
            cara = exportar.transformar((0.0, 0.0, 1.0), m)
            self.assertTrue(_cerca(cara, v.suma(hoja.base, v.escala(z, s)), 1e-6))


class PruebasMallas(unittest.TestCase):
    def _cuadrado(self, uvs_aparte=False):
        m = geometria.Malla()
        for p in ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)):
            if uvs_aparte:
                m.vertice(p, (0.5, 0.5, 0.5))
            else:
                m.vertice(p, (0.5, 0.5, 0.5), (p[0], p[1]))
        if uvs_aparte:
            ids = [m.uv(u, w) for u, w in ((0, 0), (1, 0), (1, 1), (0, 1))]
            m.cara(0, 1, 2, 3, uvs=ids)
        else:
            m.cara(0, 1, 2, 3)
        return m

    def test_anadir_junta_vertices_caras_uvs_y_colores(self):
        total = geometria.Malla()
        mover = exportar.IDENTIDAD[:12] + (10.0, 0.0, 0.0, 1.0)
        exportar.anadir(total, self._cuadrado())
        exportar.anadir(total, self._cuadrado(uvs_aparte=True), mover, (2.0, 1.0, 0.0))
        sin_uvs = self._cuadrado()
        sin_uvs.uvs, sin_uvs.uv_indices = [], []
        exportar.anadir(total, sin_uvs)
        self.assertEqual(len(total.vertices), 12)
        self.assertEqual(total.conteos, [4, 4, 4])
        self.assertEqual(total.indices[4:8], [4, 5, 6, 7])
        self.assertEqual(total.vertices[5], (11.0, 0.0, 0.0))
        self.assertEqual(total.colores[4], (1.0, 0.5, 0.0))
        self.assertEqual(len(total.uv_indices), len(total.indices))
        self.assertEqual(total.uvs[total.uv_indices[6]], (1, 1))
        # La pieza sin UVs las tiene todas en 0,0.
        self.assertEqual({total.uvs[i] for i in total.uv_indices[8:]}, {(0.0, 0.0)})

    def test_hornear_hojas_como_el_instanciador(self):
        hojas = _hojas(2)
        datos = instancias.hojas_instanciadas(hojas, semilla=2)
        modelos = [m.malla for m in datos.modelos]
        proporciones = [instancias.proporcion(c, datos.modelos[i].color)
                        for c, i in zip(datos.colores, datos.indices)]
        mover = exportar.IDENTIDAD[:12] + (0.0, 5.0, 0.0, 1.0)
        malla = exportar.hornear_hojas(modelos, [exportar.IDENTIDAD] * len(modelos),
                                       datos.posiciones, datos.giros, datos.escalas,
                                       datos.indices, proporciones, mover)
        esperados = sum(len(modelos[i].vertices) for i in datos.indices)
        self.assertEqual(len(malla.vertices), esperados)
        self.assertEqual(len(malla.colores), esperados)
        self.assertEqual(len(malla.uv_indices), len(malla.indices))
        # La primera hoja: su base, subida 5 por el instanciador.
        n0 = len(modelos[datos.indices[0]].vertices)
        bases = malla.vertices[:n0]
        base = min(bases, key=lambda p: v.distancia(p, v.suma(hojas[0].base, (0.0, 5.0, 0.0))))
        self.assertLess(v.distancia(base, v.suma(hojas[0].base, (0.0, 5.0, 0.0))),
                        0.05 * hojas[0].tamano + 1e-6)
        # Cada hoja sale de su color (el del modelo por la proporción).
        medio = exportar.color_medio(malla)
        self.assertTrue(all(0.0 < c < 1.0 for c in medio))
        # Un índice que no es de ningún modelo se salta.
        vacia = exportar.hornear_hojas(modelos, [exportar.IDENTIDAD] * len(modelos),
                                       datos.posiciones[:1], datos.giros[:1], datos.escalas[:1],
                                       [len(modelos) + 3])
        self.assertEqual(vacia.vertices, [])

    def test_caja(self):
        m = self._cuadrado()
        self.assertEqual(exportar.caja(m), ((0, 0, 0), (1, 1, 0)))
        self.assertIsNone(exportar.caja(geometria.Malla()))
        self.assertEqual(exportar.distancia_cajas(((0, 0, 0), (1, 1, 1)),
                                                  ((0, 0.5, 0), (1, 1, 1))), 0.5)


class PruebasColor(unittest.TestCase):
    def test_tablas_color(self):
        verde = (0.05, 0.2, 0.02)
        r, g, b = exportar.tablas_color(verde)
        # El gris medio (0,5) da el tinte, en sRGB.
        medio = [t[128] / 255.0 for t in (r, g, b)]
        esperado = [exportar._a_srgb(c * 2 * 128 / 255.0) for c in verde]
        self.assertTrue(_cerca(medio, esperado, 1 / 255.0))
        self.assertEqual((r[0], g[0], b[0]), (0, 0, 0))
        self.assertEqual(list(r), sorted(r))
        sin = exportar.tablas_color((0.25, 0.5, 1.0), lineal=False)
        self.assertEqual((sin[0][255], sin[1][255], sin[2][255]), (128, 255, 255))

    def test_tenir(self):
        tablas = [bytes(range(256)), bytes(255 - i for i in range(256)), bytes([7] * 256)]
        self.assertEqual(exportar.tenir(bytes([0, 10]), tablas),
                         bytes([0, 255, 7, 10, 245, 7]))

    def test_guardar_color(self):
        try:
            from PySide6 import QtGui
        except ImportError:
            self.skipTest("sin PySide6")
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta)
        gris = QtGui.QImage(64, 32, QtGui.QImage.Format.Format_Grayscale8)
        gris.fill(QtGui.QColor(128, 128, 128))
        origen = os.path.join(carpeta, "detalle.jpg")
        self.assertTrue(gris.save(origen, "JPG", 95))
        destino = os.path.join(carpeta, "color.jpg")
        self.assertTrue(exportar.guardar_color(origen, destino, (0.05, 0.2, 0.02)))
        color = QtGui.QImage(destino)
        self.assertEqual((color.width(), color.height()), (64, 32))
        c = color.pixelColor(10, 10)
        esperado = [round(255 * exportar._a_srgb(x * 2 * 128 / 255.0)) for x in (0.05, 0.2, 0.02)]
        self.assertTrue(_cerca((c.red(), c.green(), c.blue()), esperado, 4))
        self.assertFalse(exportar.guardar_color(os.path.join(carpeta, "no.jpg"), destino,
                                                (1, 1, 1)))


class PruebasHojasLigeras(unittest.TestCase):
    def setUp(self):
        self.hojas = _hojas(semilla=3)
        self.malla = geometria.malla_hojas(self.hojas, semilla=3, forma="hiedra")

    def test_cada_hoja_suelta_y_su_tarjeta(self):
        sueltas = exportar.hojas_sueltas(self.malla)
        self.assertEqual(len(sueltas), len(self.hojas))
        self.assertEqual(sum(len(h.vertices) for h in sueltas), len(self.malla.vertices))
        ligeras = exportar.hojas_ligeras(sueltas)
        self.assertEqual(len(ligeras.vertices), 6 * len(self.hojas))
        self.assertEqual(ligeras.conteos, [4] * (2 * len(self.hojas)))
        self.assertLess(len(ligeras.vertices) * 8, len(self.malla.vertices))
        self.assertTrue(all(0.0 <= u <= 1.0 and 0.0 <= w <= 1.0 for u, w in ligeras.uvs))

    def test_la_tarjeta_cubre_la_hoja_y_se_dobla_hacia_su_cara(self):
        hoja = exportar.hojas_sueltas(self.malla)[0]
        puntos, uvs, colores = exportar.esquinas(hoja)
        carta = exportar.tarjeta(puntos, uvs, colores)
        self.assertEqual(len(carta.vertices), 6)
        # Nervio en u = 0,5 y la silueta dentro del rectángulo de UV.
        self.assertEqual([round(u, 6) for u, _ in carta.uvs[:3]][1], 0.5)
        self.assertLessEqual(carta.uvs[0][0], min(u for u, _ in uvs))
        self.assertGreaterEqual(carta.uvs[5][1], max(w for _, w in uvs))
        # La cara de la tarjeta mira como la de la hoja, y los bordes se levantan hacia ella.
        h = self.hojas[0]
        a, b, c = carta.vertices[0], carta.vertices[1], carta.vertices[4]
        normal = v.unitario(v.cruz(v.resta(b, a), v.resta(c, b)))
        self.assertGreater(v.punto(normal, h.normal), 0.5)
        borde = v.resta(carta.vertices[0], carta.vertices[1])
        self.assertGreater(v.punto(borde, h.normal), 0.0)
        self.assertTrue(_cerca(carta.colores[0], exportar.color_medio(hoja), 0.03))

    def test_mascara_alfa(self):
        n = 64
        mascara = exportar.mascara_alfa("hiedra", n)
        self.assertEqual(len(mascara), n * n)
        self.assertEqual(mascara[(n // 2) * n + n // 2], 255)   # el centro, dentro
        self.assertEqual(mascara[0], 0)                          # la esquina, fuera
        for j in range(n):
            fila = mascara[j * n:(j + 1) * n]
            self.assertEqual(fila, fila[::-1])                   # simétrica por el nervio
        # Cubre lo mismo que las hojas: casi todos sus vértices, también los
        # del borde, caen dentro (las hojas varían algo de ancho).
        n = 256
        mascara = exportar.mascara_alfa("hiedra", n)
        dentro = 0
        for u, w in self.malla.uvs:
            i, j = min(n - 1, int(u * n)), min(n - 1, int((1.0 - w) * n))
            vecinos = [mascara[jj * n + ii] for jj in range(max(0, j - 1), min(n, j + 2))
                       for ii in range(max(0, i - 1), min(n, i + 2))]
            dentro += max(vecinos) > 0
        self.assertGreater(dentro / len(self.malla.uvs), 0.95)

    def test_mapa_de_color_con_silueta(self):
        try:
            from PySide6 import QtGui
        except ImportError:
            self.skipTest("sin PySide6")
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta)
        gris = QtGui.QImage(64, 64, QtGui.QImage.Format.Format_Grayscale8)
        gris.fill(QtGui.QColor(128, 128, 128))
        origen = os.path.join(carpeta, "detalle.jpg")
        self.assertTrue(gris.save(origen, "JPG", 95))
        self.assertEqual(exportar.nombre_color("hoja_hiedra", alfa=True), "hoja_hiedra_color.png")
        destino = os.path.join(carpeta, exportar.nombre_color("hoja_hiedra", alfa=True))
        self.assertTrue(exportar.guardar_color(origen, destino, (0.05, 0.2, 0.02), forma="hiedra"))
        color = QtGui.QImage(destino)
        self.assertTrue(color.hasAlphaChannel())
        self.assertEqual(color.pixelColor(32, 32).alpha(), 255)
        self.assertEqual(color.pixelColor(0, 0).alpha(), 0)


class PruebasArchivos(unittest.TestCase):
    def test_nombres(self):
        self.assertEqual(exportar.carpeta_texturas(os.path.join("a", "mi planta.fbx")),
                         os.path.join("a", "mi planta_texturas"))
        self.assertEqual(exportar.formato_de("x.FBX"), "fbx")
        self.assertEqual(exportar.formato_de("x.abc"), "abc")
        self.assertIsNone(exportar.formato_de("x.obj"))
        self.assertEqual(exportar.nombre_de_grupo("/a/mi planta ñ.fbx"), "mi_planta")
        self.assertEqual(exportar.nombre_de_grupo("3d.abc"), "planta_3d")
        self.assertEqual(exportar.nombre_de_grupo("ñ.fbx"), "trepadora_planta")

    def test_mapas_a_copiar(self):
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta)
        for res in ("1k", "2k"):
            os.makedirs(os.path.join(carpeta, res))
            for juego in ("hoja_hiedra", "corteza"):
                for mapa in texturas.mapas_de(juego):
                    open(os.path.join(carpeta, res, texturas.archivo(juego, mapa)), "w").close()
        lista = exportar.mapas_a_copiar(["hoja_hiedra", "corteza"], "4k", carpeta)
        self.assertEqual(len(lista), 7)
        self.assertTrue(all(os.sep + "2k" + os.sep in origen for origen, _ in lista))
        self.assertIn("hoja_hiedra_traslucidez.jpg", [n for _, n in lista])
        self.assertEqual(exportar.mapas_a_copiar(["hoja_redonda"], "1k", carpeta), [])


if __name__ == "__main__":
    random.seed(0)
    unittest.main()
