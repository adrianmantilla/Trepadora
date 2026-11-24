"""OpenPBR: el material de Maya 2026 y 2027 (``openPBRSurface``).

Lo renderizan Arnold y otros motores, se ve en el visor y es el que usa
Materials. Este módulo traduce los nombres de ``standardSurface`` y
``aiStandardSurface`` a los de OpenPBR y convierte los materiales viejos de una
escena. Es igual en Trepadora y en Árboles: si se cambia, cambiar los dos.
"""

from maya import cmds

TIPO = "openPBRSurface"
VIEJOS = ("aiStandardSurface", "standardSurface")

# Atributos que cambian de nombre; el resto se llama igual en los dos.
NOMBRES = {
    "base": "baseWeight",
    "metalness": "baseMetalness",
    "diffuseRoughness": "baseDiffuseRoughness",
    "specular": "specularWeight",
    "thinWalled": "geometryThinWalled",
    "subsurface": "subsurfaceWeight",
    "transmission": "transmissionWeight",
    "coat": "coatWeight",
    "sheen": "fuzzWeight",
    "sheenColor": "fuzzColor",
    "sheenRoughness": "fuzzRoughness",
    "emission": "emissionLuminance",
}
# Lo que se copia al convertir un material viejo.
COPIAR = ("base", "baseColor", "metalness", "diffuseRoughness", "specular", "specularColor",
          "specularRoughness", "specularIOR", "thinWalled", "subsurface", "subsurfaceColor",
          "subsurfaceRadius", "transmission", "transmissionColor", "coat", "coatColor",
          "coatRoughness", "sheen", "sheenColor", "sheenRoughness", "emission", "emissionColor",
          "normalCamera")
# La emisión de OpenPBR va en nits: 1 de standardSurface son 1000 nits.
NITS = 1000.0


def disponible():
    """True si este Maya tiene openPBRSurface (Maya 2025.3 o posterior)."""
    try:
        return TIPO in (cmds.allNodeTypes() or [])
    except (RuntimeError, AttributeError):
        return False


def tipo():
    """El tipo de material que hay que crear: OpenPBR si existe; si no, ``standardSurface``."""
    return TIPO if disponible() else "standardSurface"


def atributo(nombre, tipo_material=TIPO):
    """Nombre del atributo ``nombre`` (de standardSurface) en un material de ese tipo."""
    if tipo_material != TIPO:
        return nombre
    hijo = nombre[-1:] if nombre[-1:] in "RGB" and nombre[:-1] in NOMBRES else ""
    base = nombre[:-1] if hijo else nombre
    return NOMBRES.get(base, base) + hijo


def valor(nombre, v, tipo_material=TIPO):
    """El valor de ``nombre`` traducido (solo cambia la emisión, que pasa a nits)."""
    if tipo_material == TIPO and nombre == "emission":
        return v * NITS
    return v


def poner(material, nombre, *v, **opciones):
    """setAttr con el nombre y el valor de standardSurface, sea cual sea el material."""
    t = cmds.nodeType(material)
    if len(v) == 1:
        v = (valor(nombre, v[0], t),)
    cmds.setAttr(material + "." + atributo(nombre, t), *v, **opciones)


def conectar(origen, material, nombre):
    """connectAttr a la entrada ``nombre`` (de standardSurface) del material."""
    cmds.connectAttr(origen, material + "." + atributo(nombre, cmds.nodeType(material)), force=True)


def es_viejo(material):
    return cmds.objExists(material) and cmds.nodeType(material) in VIEJOS


def _plug(texto):
    nodo, _punto, atrib = texto.partition(".")
    return nodo, atrib


def convertir(material):
    """Cambia ``material`` (standardSurface o aiStandardSurface) por un openPBRSurface.

    Copia valores y texturas, pasa sus conexiones (grupo de sombreado,
    aiSurfaceShader…) al nuevo, borra el viejo y le da su nombre. Devuelve el
    nombre del nuevo, o None si no se ha podido.
    """
    if not disponible() or not es_viejo(material):
        return None
    nombre = material.split("|")[-1]
    nuevo = cmds.shadingNode(TIPO, asShader=True, name=nombre + "_openpbr_tmp")
    entradas = cmds.listConnections(material, source=True, destination=False,
                                    connections=True, plugs=True) or []
    conectados = set()
    for destino, origen in zip(entradas[0::2], entradas[1::2]):
        atrib = _plug(destino)[1]
        base = atrib[:-1] if atrib[-1:] in "RGB" and atrib[:-1] in COPIAR else atrib
        if base not in COPIAR:
            continue
        conectados.add(base)
        try:
            cmds.connectAttr(origen, nuevo + "." + atributo(atrib), force=True)
        except RuntimeError:
            pass
    for nombre_viejo in COPIAR:
        if nombre_viejo in conectados or nombre_viejo == "normalCamera":
            continue
        try:
            v = cmds.getAttr(material + "." + nombre_viejo)
        except (RuntimeError, ValueError):
            continue
        if v is None:
            continue
        try:
            if isinstance(v, (list, tuple)):
                trio = v[0] if v and isinstance(v[0], (list, tuple)) else v
                cmds.setAttr(nuevo + "." + atributo(nombre_viejo), *trio, type="double3")
            else:
                cmds.setAttr(nuevo + "." + atributo(nombre_viejo), valor(nombre_viejo, v))
        except (RuntimeError, ValueError, TypeError):
            pass
    salidas = cmds.listConnections(material, source=False, destination=True,
                                   connections=True, plugs=True) or []
    for origen, destino in zip(salidas[0::2], salidas[1::2]):
        atrib = _plug(origen)[1]
        try:
            cmds.connectAttr(nuevo + "." + atrib, destino, force=True)
        except RuntimeError:
            pass
    cmds.delete(material)
    return cmds.rename(nuevo, nombre)


def convertir_escena(patrones):
    """Convierte los materiales viejos cuyo nombre encaja con ``patrones`` («arboles_*»…).

    Devuelve la lista de materiales convertidos.
    """
    tipos = (cmds.allNodeTypes() or []) if disponible() else []
    hechos = []
    for t in VIEJOS:
        if t not in tipos:   # aiStandardSurface sin Arnold: ls avisaría
            continue
        viejos = cmds.ls(*patrones, type=t) or []
        for material in viejos:
            nuevo = convertir(material)
            if nuevo:
                hechos.append(nuevo)
    return hechos
