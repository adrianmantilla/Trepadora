"""Textos de la interfaz, separados del codigo para poder traducirlos.

Cada idioma es un archivo JSON en esta carpeta (``es.json``, ``en.json``...).
Si falta una clave en el idioma elegido, se usa el espanol.
"""

import json
import os

_CARPETA = os.path.dirname(os.path.abspath(__file__))
_IDIOMA_BASE = "es"
_cache = {}
_idioma = os.environ.get("TREPADORA_IDIOMA", _IDIOMA_BASE)


def _cargar(idioma):
    if idioma not in _cache:
        ruta = os.path.join(_CARPETA, idioma + ".json")
        try:
            with open(ruta, encoding="utf-8") as f:
                _cache[idioma] = json.load(f)
        except (OSError, ValueError):
            _cache[idioma] = {}
    return _cache[idioma]


def usar_idioma(idioma):
    global _idioma
    _idioma = idioma


def idioma():
    """El idioma activo (``es``, ``en``...)."""
    return _idioma


def idiomas():
    """Los idiomas que hay en esta carpeta, el español primero."""
    hay = sorted(os.path.splitext(a)[0] for a in os.listdir(_CARPETA) if a.endswith(".json"))
    return sorted(hay, key=lambda i: (i != _IDIOMA_BASE, i))


def t(clave, **valores):
    """Devuelve el texto de ``clave`` en el idioma activo, con ``valores`` sustituidos."""
    texto = _cargar(_idioma).get(clave) or _cargar(_IDIOMA_BASE).get(clave) or clave
    try:
        return texto.format(**valores)
    except (KeyError, IndexError):
        return texto
