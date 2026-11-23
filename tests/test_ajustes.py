"""Pruebas de los ajustes de la ventana, los preajustes, los textos y el instalador, sin Maya.

Ejecutar desde la raíz del repositorio:  python -m unittest discover tests
"""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import instalar  # noqa: E402
from trepadora import __version__, geometria  # noqa: E402
from trepadora import ajustes as aj  # noqa: E402
from trepadora.crecimiento import Crecimiento, Parametros  # noqa: E402
from trepadora.hojas import ParametrosHojas, colocar_hojas  # noqa: E402

ES = os.path.join(RAIZ, "scripts", "trepadora", "i18n", "es.json")


def textos():
    with open(ES, encoding="utf-8") as f:
        return json.load(f)


class PruebasControles(unittest.TestCase):
    def test_valores_por_defecto_en_su_rango(self):
        for c in aj.CONTROLES:
            if c.tipo in ("real", "entero"):
                self.assertLessEqual(c.minimo, c.defecto, c.clave)
                self.assertLessEqual(c.defecto, c.maximo, c.clave)
            elif c.tipo == "opcion":
                self.assertIn(c.defecto, c.opciones, c.clave)

    def test_por_defecto_son_los_del_algoritmo(self):
        crecimiento, hojas, planta = aj.repartir(aj.valores_por_defecto())
        p, ph = Parametros(), ParametrosHojas()
        for clave, valor in crecimiento.items():
            self.assertEqual(valor, getattr(p, clave), clave)
        for clave, valor in hojas.items():
            self.assertEqual(valor, getattr(ph, clave), clave)
        self.assertEqual(planta["lados"], geometria.TIPOS_TALLO["lenoso"]["lados"])

    def test_repartir_da_argumentos_validos(self):
        crecimiento, hojas, planta = aj.repartir({"semilla": 7, "gravedad": 1.2})
        Parametros(**crecimiento)
        ParametrosHojas(**hojas)
        self.assertEqual(hojas["semilla"], 7)
        self.assertEqual(crecimiento["gravedad"], 1.2)
        self.assertEqual(set(planta), {"grosor", "escala", "forma_hoja", "tipo_tallo",
                                       "instancias", "lados"})

    def test_ajustar_recorta_y_convierte(self):
        pasos = aj.POR_CLAVE["pasos"]
        self.assertEqual(aj.ajustar(pasos, 5000), pasos.maximo)
        self.assertEqual(aj.ajustar(pasos, "120.4"), 120)
        self.assertEqual(aj.ajustar(aj.POR_CLAVE["gravedad"], -3), 0.0)
        self.assertIs(aj.ajustar(aj.POR_CLAVE["instancias"], "false"), False)
        with self.assertRaises(ValueError):
            aj.ajustar(aj.POR_CLAVE["forma_hoja"], "palmera")
        with self.assertRaises(ValueError):
            aj.ajustar(aj.POR_CLAVE["gravedad"], float("nan"))

    def test_limpiar_ignora_lo_desconocido(self):
        ajustes, ignorados = aj.limpiar({"gravedad": "mucha", "color": "rojo", "luz": 0.2})
        self.assertEqual(sorted(ignorados), ["color", "gravedad"])
        self.assertEqual(ajustes["gravedad"], aj.POR_CLAVE["gravedad"].defecto)
        self.assertEqual(ajustes["luz"], 0.2)

    def test_lados_por_resolucion(self):
        for tipo in geometria.TIPOS_TALLO:
            baja, media, alta = (aj.lados_tallo(tipo, r) for r in aj.RESOLUCIONES)
            self.assertGreaterEqual(baja, 3)
            self.assertLess(baja, media)
            self.assertLess(media, alta)

    def test_carga(self):
        self.assertEqual(aj.carga(0), "baja")
        self.assertEqual(aj.carga(aj.UMBRAL_MEDIA), "media")
        self.assertEqual(aj.carga(aj.UMBRAL_ALTA + 1), "alta")


class PruebasPreajustes(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.carpeta)

    def test_incluidos_validos_y_con_nombre(self):
        incluidos = aj.preajustes_incluidos()
        self.assertGreaterEqual(len(incluidos), 4)
        es = textos()
        for p in incluidos:
            with open(p.ruta, encoding="utf-8") as f:
                datos = json.load(f)
            desconocidas = set(datos["ajustes"]) - set(aj.POR_CLAVE)
            self.assertFalse(desconocidas, p.ruta)
            _, ignorados = aj.limpiar(datos["ajustes"])
            self.assertFalse(ignorados, p.ruta)
            self.assertIn(p.clave_nombre, es)
            self.assertTrue(p.incluido)

    def test_guardar_y_leer(self):
        ruta = os.path.join(self.carpeta, "sub", aj.nombre_de_archivo("Mi hiedra: «roja»"))
        valores = dict(aj.valores_por_defecto(), semilla=42, forma_hoja="corazon")
        aj.guardar_preajuste(ruta, "Mi hiedra: «roja»", valores)
        leido = aj.leer_preajuste(ruta)
        self.assertEqual(leido.nombre, "Mi hiedra: «roja»")
        self.assertEqual(leido.ajustes, valores)
        self.assertFalse(leido.incluido)

    def test_nombre_de_archivo_seguro(self):
        for nombre in ("a/b\\c:d*e?f", "  ", "...", "Hiedra de  fachada"):
            archivo = aj.nombre_de_archivo(nombre)
            self.assertTrue(archivo.endswith(".json"))
            self.assertFalse(re.search(r'[\\/:*?"<>|\s]', archivo), archivo)
            self.assertGreater(len(archivo), len(".json"))

    def test_usuario_salta_archivos_rotos(self):
        aj.guardar_preajuste(os.path.join(self.carpeta, "b.json"), "Bueno", {})
        with open(os.path.join(self.carpeta, "roto.json"), "w") as f:
            f.write("{no es json")
        with open(os.path.join(self.carpeta, "otro.json"), "w") as f:
            json.dump([1, 2, 3], f)
        with open(os.path.join(self.carpeta, "nota.txt"), "w") as f:
            f.write("hola")
        nombres = [p.nombre for p in aj.preajustes_de_usuario(self.carpeta)]
        self.assertEqual(nombres, ["Bueno"])
        self.assertEqual(aj.preajustes_de_usuario(os.path.join(self.carpeta, "no")), [])

    def test_leer_preajuste_no_valido(self):
        ruta = os.path.join(self.carpeta, "x.json")
        with open(ruta, "w") as f:
            json.dump({"nombre": "sin ajustes"}, f)
        with self.assertRaises(ValueError):
            aj.leer_preajuste(ruta)
        with self.assertRaises(ValueError):
            aj.leer_preajuste(os.path.join(self.carpeta, "no_existe.json"))

    def test_carpeta_usuario(self):
        antes = os.environ.pop("TREPADORA_PREAJUSTES", None)
        try:
            self.assertEqual(aj.carpeta_usuario("/maya"),
                             os.path.join("/maya", "trepadora", "preajustes"))
            os.environ["TREPADORA_PREAJUSTES"] = self.carpeta
            self.assertEqual(aj.carpeta_usuario("/maya"), self.carpeta)
        finally:
            os.environ.pop("TREPADORA_PREAJUSTES", None)
            if antes is not None:
                os.environ["TREPADORA_PREAJUSTES"] = antes

    def test_preajustes_crecen_distinto_y_la_cuenta_de_hojas_se_acerca(self):
        from superficies import escena_de_prueba

        diagonal = (400.0 ** 2 + 151.0 ** 2 + 400.0 ** 2) ** 0.5
        firmas = set()
        for p in aj.preajustes_incluidos():
            crecimiento, hojas, planta = aj.repartir(p.ajustes)
            paso = diagonal / 150.0 * planta["escala"]
            base = dict(longitud_paso=paso, distancia_adherencia=paso * 3,
                        separacion=paso * 0.05, radio_espacio=paso * 2)
            base.update(crecimiento)
            c = Crecimiento(escena_de_prueba(), Parametros(**base))
            c.anadir_origen((-20.0, 2.0, 5.5))
            c.crecer()
            self.assertGreater(c.total_puntos, 500, p.nombre)
            hojas["tamano"] *= paso * 2.4
            reales = len(colocar_hojas(c, ParametrosHojas(**hojas)))
            estimadas = aj.hojas_estimadas(c.total_puntos, p.ajustes["densidad"])
            if reales == 0:
                self.assertEqual(estimadas, 0, p.nombre)
            else:
                self.assertLess(abs(estimadas - reales) / reales, 0.3, p.nombre)
            firmas.add((len(c.ramas), c.total_puntos, reales))
        self.assertEqual(len(firmas), len(aj.preajustes_incluidos()))


class PruebasTextos(unittest.TestCase):
    def test_cada_texto_usado_existe(self):
        es = textos()
        claves = set()
        carpetas = [os.path.join(RAIZ, "scripts"), os.path.join(RAIZ, "plug-ins")]
        archivos = [os.path.join(RAIZ, "instalar.py")]
        for carpeta in carpetas:
            for raiz, _, nombres in os.walk(carpeta):
                archivos += [os.path.join(raiz, n) for n in nombres if n.endswith(".py")]
        for ruta in archivos:
            with open(ruta, encoding="utf-8") as f:
                claves.update(re.findall(r'\bt\("([a-z_0-9]+)"[,)]', f.read()))
        self.assertGreater(len(claves), 50)
        faltan = sorted(c for c in claves if c not in es)
        self.assertEqual(faltan, [])

    def test_cada_control_tiene_sus_textos(self):
        es = textos()
        faltan = []
        for c in aj.CONTROLES:
            faltan += [k for k in ("ajuste_" + c.clave, "ayuda_" + c.clave) if k not in es]
            faltan += ["opcion_{}_{}".format(c.clave, o) for o in c.opciones
                       if "opcion_{}_{}".format(c.clave, o) not in es]
        faltan += ["grupo_" + g for g in aj.GRUPOS_AVANZADOS if "grupo_" + g not in es]
        faltan += ["carga_" + n for n in ("baja", "media", "alta") if "carga_" + n not in es]
        faltan += [k for k in ("resultado_crecer", "resultado_malla", "forma_desconocida",
                               "tallo_desconocido") if k not in es]
        self.assertEqual(faltan, [])

    def test_textos_bien_formados(self):
        for clave, texto in textos().items():
            self.assertIsInstance(texto, str, clave)
            self.assertTrue(texto.strip(), clave)
            # Cada {campo} se puede sustituir.
            campos = re.findall(r"{(\w*)}", texto)
            texto.format(**{c: "x" for c in campos})


class PruebasInstalador(unittest.TestCase):
    def test_version_y_mod(self):
        self.assertEqual(instalar.version(), __version__)
        linea = instalar.texto_mod("C:\\Users\\Ana Pérez\\Trepadora")
        self.assertEqual(linea, "+ Trepadora {} C:/Users/Ana Pérez/Trepadora\n".format(__version__))

    def test_escribir_mod(self):
        carpeta = tempfile.mkdtemp()
        try:
            ruta = instalar.escribir_mod(os.path.join(carpeta, "modules"))
            with open(ruta, encoding="utf-8") as f:
                contenido = f.read()
            self.assertEqual(contenido, instalar.texto_mod())
            destino = contenido.split(" ", 3)[3].strip()
            for sub in ("scripts", "plug-ins", "icons"):
                self.assertTrue(os.path.isdir(os.path.join(destino, sub)), sub)
            self.assertTrue(os.path.isfile(os.path.join(destino, "plug-ins",
                                                        instalar.PLUGIN + ".py")))
            self.assertTrue(os.path.isfile(os.path.join(destino, "icons", "trepadora.png")))
        finally:
            shutil.rmtree(carpeta)


if __name__ == "__main__":
    unittest.main()
