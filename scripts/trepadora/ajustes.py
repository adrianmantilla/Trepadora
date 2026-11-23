"""Los ajustes que ve el estudiante en la ventana, y los preajustes.

No usa Maya: la ventana se construye a partir de la lista ``CONTROLES`` y las
pruebas comprueban que cada ajuste existe, que su valor por defecto está dentro
de su rango y que cada texto está en el archivo de idioma.

Un juego de ajustes es un diccionario plano ``{clave: valor}`` con una entrada
por control. ``repartir()`` lo convierte en lo que necesitan el crecimiento
(``Parametros``), las hojas (``ParametrosHojas``) y la planta (grosor, tipos...).

Un preajuste es un archivo JSON con ``nombre`` y ``ajustes``. Los que trae el
plugin están en la carpeta ``preajustes``; los que guarda el estudiante, en su
carpeta de usuario de Maya (ver ``carpeta_usuario``).
"""

import json
import os
import re
from dataclasses import dataclass, fields
from typing import Optional, Tuple

from . import geometria
from .crecimiento import Parametros
from .hojas import ParametrosHojas

VERSION_PREAJUSTE = 1


class Aviso(Exception):
    """Un problema que el estudiante puede resolver; el texto (traducido) dice cómo."""


@dataclass(frozen=True)
class Control:
    """Un ajuste de la ventana.

    * ``destino``: a quién va el valor: ``crecimiento`` (``Parametros``),
      ``hojas`` (``ParametrosHojas``) o ``planta`` (cómo se construye la malla).
    * ``tipo``: ``real``, ``entero``, ``opcion`` o ``si_no``.
    * ``grupo``: ``aspecto`` (siempre a la vista) o uno de los grupos plegados
      de ajustes avanzados: ``crecimiento``, ``hojas`` o ``tallos``.

    Los textos salen del archivo de idioma: ``ajuste_<clave>`` (nombre),
    ``ayuda_<clave>`` (una línea de ayuda) y ``opcion_<clave>_<valor>``.
    """

    clave: str
    destino: str
    tipo: str
    grupo: str
    defecto: object
    minimo: Optional[float] = None
    maximo: Optional[float] = None
    opciones: Tuple[str, ...] = ()
    decimales: int = 2


def _por_defecto(clase, campo):
    return {f.name: f.default for f in fields(clase)}[campo]


def _c(clave, destino, tipo, grupo, minimo=None, maximo=None, defecto=None, opciones=(),
       decimales=2):
    if defecto is None:
        clase = {"crecimiento": Parametros, "hojas": ParametrosHojas}[destino]
        defecto = _por_defecto(clase, clave)
    return Control(clave, destino, tipo, grupo, defecto, minimo, maximo, tuple(opciones),
                   decimales)


RESOLUCIONES = ("baja", "media", "alta")

CONTROLES = (
    # Paso 3, Aspecto: lo que se ve siempre.
    _c("tipo_tallo", "planta", "opcion", "aspecto", defecto="lenoso",
       opciones=tuple(geometria.TIPOS_TALLO)),
    _c("forma_hoja", "planta", "opcion", "aspecto", defecto="hiedra",
       opciones=geometria.FORMAS_HOJA),
    _c("pasos", "crecimiento", "entero", "aspecto", 40, 900),
    _c("densidad", "hojas", "real", "aspecto", 0.0, 1.0),
    _c("grosor", "planta", "real", "aspecto", 0.2, 3.0, defecto=1.0),
    # Ajustes avanzados: crecimiento.
    _c("semilla", "crecimiento", "entero", "crecimiento", 1, 9999),
    _c("escala", "planta", "real", "crecimiento", 0.2, 5.0, defecto=1.0),
    _c("adherencia", "crecimiento", "real", "crecimiento", 0.0, 1.0),
    _c("gravedad", "crecimiento", "real", "crecimiento", 0.0, 1.5),
    _c("luz", "crecimiento", "real", "crecimiento", 0.0, 1.0),
    _c("aleatoriedad", "crecimiento", "real", "crecimiento", 0.0, 1.5),
    _c("prob_rama", "crecimiento", "real", "crecimiento", 0.0, 0.3, decimales=3),
    _c("generaciones_max", "crecimiento", "entero", "crecimiento", 0, 6),
    _c("longitud_max", "crecimiento", "entero", "crecimiento", 20, 600),
    _c("brotes_basales", "crecimiento", "entero", "crecimiento", 0, 8),
    _c("prob_colgar", "crecimiento", "real", "crecimiento", 0.0, 1.0),
    _c("guia", "crecimiento", "real", "crecimiento", 0.0, 2.0),
    # Ajustes avanzados: hojas.
    _c("tamano", "hojas", "real", "hojas", 0.2, 3.0),
    _c("variacion", "hojas", "real", "hojas", 0.0, 1.0),
    _c("caida", "hojas", "real", "hojas", 0.0, 1.0),
    _c("despegue", "hojas", "real", "hojas", 0.0, 1.0),
    _c("manchas", "hojas", "real", "hojas", 0.0, 1.0),
    _c("bronce", "hojas", "real", "hojas", 0.0, 0.2, decimales=3),
    _c("instancias", "planta", "si_no", "hojas", defecto=True),
    # Ajustes avanzados: tallos.
    _c("resolucion", "planta", "opcion", "tallos", defecto="media", opciones=RESOLUCIONES),
)

POR_CLAVE = {c.clave: c for c in CONTROLES}
GRUPOS_AVANZADOS = ("crecimiento", "hojas", "tallos")


def valores_por_defecto():
    return {c.clave: c.defecto for c in CONTROLES}


def controles_del_grupo(grupo):
    return [c for c in CONTROLES if c.grupo == grupo]


def ajustar(control, valor):
    """Devuelve ``valor`` convertido al tipo del control y dentro de su rango.

    Lanza ValueError si no se puede convertir (por ejemplo, una opción que no existe).
    """
    if control.tipo == "si_no":
        if isinstance(valor, str):
            return valor.strip().lower() in ("1", "true", "si", "sí", "yes")
        return bool(valor)
    if control.tipo == "opcion":
        if valor not in control.opciones:
            raise ValueError(valor)
        return valor
    if isinstance(valor, bool):
        raise ValueError(valor)
    numero = float(valor)
    if numero != numero:  # NaN
        raise ValueError(valor)
    numero = min(max(numero, control.minimo), control.maximo)
    if control.tipo == "entero":
        return int(round(numero))
    return round(numero, control.decimales)


def limpiar(valores):
    """Completa y corrige un juego de ajustes.

    Devuelve ``(ajustes, ignorados)``: los ajustes con todas las claves y cada
    valor en su rango, y la lista de claves desconocidas o con valores que no
    se pudieron usar (esas toman el valor por defecto).
    """
    resultado = valores_por_defecto()
    ignorados = []
    for clave, valor in (valores or {}).items():
        control = POR_CLAVE.get(clave)
        if control is None:
            ignorados.append(clave)
            continue
        try:
            resultado[clave] = ajustar(control, valor)
        except (TypeError, ValueError):
            ignorados.append(clave)
    return resultado, ignorados


def lados_tallo(tipo_tallo, resolucion):
    """Lados del tubo del tallo para un tipo y una resolución (baja, media o alta)."""
    lados = geometria.TIPOS_TALLO[tipo_tallo]["lados"]
    if resolucion == "baja":
        return max(3, lados - 2)
    if resolucion == "alta":
        return lados * 2
    return lados


def repartir(valores):
    """Separa un juego de ajustes en ``(crecimiento, hojas, planta)``.

    * ``crecimiento``: argumentos para ``Parametros`` (sin las distancias, que
      dependen del tamaño de la escena).
    * ``hojas``: argumentos para ``ParametrosHojas`` (``tamano`` relativo: 1 = automático).
    * ``planta``: ``grosor``, ``escala``, ``forma_hoja``, ``tipo_tallo``,
      ``instancias`` y ``lados``.
    """
    ajustes, _ = limpiar(valores)
    crecimiento, hojas, planta = {}, {}, {}
    destinos = {"crecimiento": crecimiento, "hojas": hojas, "planta": planta}
    for control in CONTROLES:
        destinos[control.destino][control.clave] = ajustes[control.clave]
    planta["lados"] = lados_tallo(planta["tipo_tallo"], planta.pop("resolucion"))
    hojas["semilla"] = crecimiento["semilla"]
    return crecimiento, hojas, planta


# --------------------------------------------------------------- preajustes
CARPETA_PREAJUSTES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preajustes")


@dataclass
class Preajuste:
    nombre: str
    ajustes: dict
    ruta: Optional[str] = None
    # True si viene con el plugin (no se puede borrar ni sobrescribir).
    incluido: bool = False
    # Clave del texto con el nombre, para los incluidos (se traduce).
    clave_nombre: Optional[str] = None


def leer_preajuste(ruta, incluido=False):
    """Lee un preajuste. Lanza ValueError si el archivo no es un preajuste válido."""
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(str(error))
    if not isinstance(datos, dict) or not isinstance(datos.get("ajustes"), dict):
        raise ValueError("sin ajustes")
    nombre = datos.get("nombre") or os.path.splitext(os.path.basename(ruta))[0]
    ajustes, _ = limpiar(datos["ajustes"])
    return Preajuste(str(nombre), ajustes, ruta, incluido, datos.get("clave_nombre"))


def preajustes_incluidos():
    """Los preajustes que trae el plugin, en el orden de su nombre de archivo."""
    resultado = []
    for archivo in sorted(os.listdir(CARPETA_PREAJUSTES)):
        if archivo.endswith(".json"):
            resultado.append(leer_preajuste(os.path.join(CARPETA_PREAJUSTES, archivo), True))
    return resultado


def preajustes_de_usuario(carpeta):
    """Los preajustes guardados en ``carpeta``, por nombre. Los archivos dañados se saltan."""
    resultado = []
    if not carpeta or not os.path.isdir(carpeta):
        return resultado
    for archivo in sorted(os.listdir(carpeta)):
        if not archivo.lower().endswith(".json"):
            continue
        try:
            resultado.append(leer_preajuste(os.path.join(carpeta, archivo)))
        except ValueError:
            continue
    return sorted(resultado, key=lambda p: p.nombre.lower())


def nombre_de_archivo(nombre):
    """Un nombre de archivo seguro en Windows y macOS para el preajuste ``nombre``."""
    limpio = re.sub(r'[\\/:*?"<>|\s]+', "_", nombre.strip()).strip("._")
    return (limpio or "preajuste")[:60] + ".json"


def guardar_preajuste(ruta, nombre, valores):
    """Guarda ``valores`` como preajuste en ``ruta`` (crea la carpeta si hace falta)."""
    ajustes, _ = limpiar(valores)
    carpeta = os.path.dirname(ruta)
    if carpeta and not os.path.isdir(carpeta):
        os.makedirs(carpeta)
    datos = {"version": VERSION_PREAJUSTE, "nombre": nombre, "ajustes": ajustes}
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")
    return ruta


def carpeta_usuario(base=None):
    """Carpeta donde se guardan los preajustes del estudiante.

    Dentro de Maya es ``<carpeta de usuario de Maya>/trepadora/preajustes``
    (``base``); fuera, ``~/.trepadora/preajustes``. La variable de entorno
    ``TREPADORA_PREAJUSTES`` manda sobre ambas.
    """
    if os.environ.get("TREPADORA_PREAJUSTES"):
        return os.environ["TREPADORA_PREAJUSTES"]
    if base:
        return os.path.join(base, "trepadora", "preajustes")
    return os.path.join(os.path.expanduser("~"), ".trepadora", "preajustes")


# ------------------------------------------------------------ carga del visor
def hojas_estimadas(puntos, densidad):
    """Cuántas hojas saldrán, aproximadamente, de una planta con ``puntos`` puntos.

    Colocar las hojas de verdad tarda casi tanto como crecer; esta cuenta sale
    de la ruina de prueba (8324 hojas para 15859 puntos con densidad 0,82).
    """
    return int(round(puntos * densidad * 0.64))


UMBRAL_MEDIA = 10000
UMBRAL_ALTA = 25000


def carga(hojas):
    """``baja``, ``media`` o ``alta`` según el número de hojas."""
    if hojas >= UMBRAL_ALTA:
        return "alta"
    if hojas >= UMBRAL_MEDIA:
        return "media"
    return "baja"
