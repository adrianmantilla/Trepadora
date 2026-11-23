# Corteza de Trepadora hecha en Substance Painter, para el puente
# (trepadora_puente.py). Crea un proyecto con un tubo de prueba, le pone el
# material «Wood Bark» de Painter y exporta la corteza a 512, 1K, 2K y 4K en
# DEV/trepadora_painter/texturas/<resolución>/corteza_<mapa>.jpg, con el
# formato de trepadora/texturas.py:
#
# * detalle: la luminancia de Painter pasada a lineal y dividida por su media
#   (media 0,5), porque en Maya se multiplica por el color de cada punto del tallo;
# * normal: OpenGL (Y arriba), como lo lee Maya;
# * rugosidad: en gris.
#
# (JPEG de calidad 91 o más: Qt no submuestrea el color.)
#
# Si hay un proyecto abierto que no es el de una prueba anterior (sin
# guardar y con un solo juego «corteza»), no hace nada.
import math
import os
import time

import substance_painter.export as ex
import substance_painter.layerstack as ls
import substance_painter.project as pr
import substance_painter.resource as rs
import substance_painter.textureset as ts
from PySide6 import QtCore, QtGui

TIEMPO_MAX = 1800
MALLAS = os.path.join(CARPETA, "mallas")
CRUDO = os.path.join(CARPETA, "export", "corteza")
TEXTURAS = os.path.join(CARPETA, "texturas")
RESOLUCIONES = (("512", 9), ("1k", 10), ("2k", 11), ("4k", 12))
# Ajustes del material Wood Bark (los que no estén aquí, los de Painter).
AJUSTES = {}
# Contraste del detalle alrededor de su media: con 1, Wood Bark deja motas
# blancas (el 5 % de los puntos pasa de 2 veces el color del tallo); con 0,6
# el tallo conserva su color y la textura no se recorta.
CONTRASTE = 0.6


def nombre_de(x):
    return str(x).split(".")[-1]


def cilindro(ruta, lados=48, anillos=12):
    """Tubo de largo 1 y circunferencia 1: la textura da una vuelta y sube 1."""
    radio = 1.0 / (2.0 * math.pi)
    lineas = ["o corteza", "usemtl corteza"]
    for k in range(anillos + 1):
        for j in range(lados + 1):
            a = 2.0 * math.pi * j / lados
            lineas.append("v {:.6f} {:.6f} {:.6f}".format(radio * math.cos(a), k / anillos,
                                                        radio * math.sin(a)))
            lineas.append("vt {:.6f} {:.6f}".format(j / lados, k / anillos))
    for k in range(anillos):
        for j in range(lados):
            a = k * (lados + 1) + j + 1
            b, c, d = a + 1, a + lados + 2, a + lados + 1
            lineas.append("f {0}/{0} {1}/{1} {2}/{2} {3}/{3}".format(a, d, c, b))
    with open(ruta, "w") as f:
        f.write("\n".join(lineas) + "\n")


def es_de_prueba():
    try:
        nombres = [c.name() for c in ts.all_texture_sets()]
    except Exception:
        return False
    return pr.file_path() is None and nombres == ["corteza"]


def esperar_libre(limite=300):
    t = time.time()
    while pr.is_busy():
        if time.time() - t > limite:
            raise RuntimeError("Painter sigue ocupado tras {} s".format(limite))
        yield


def exportar(nombre_set, log2, carpeta):
    param = {"fileFormat": "png", "bitDepth": "8", "dithering": False,
             "paddingAlgorithm": "infinite"}

    def rgb(mapa, tipo="documentMap"):
        return [{"destChannel": c, "srcChannel": c, "srcMapType": tipo, "srcMapName": mapa}
                for c in "RGB"]

    def gris(mapa):
        return [{"destChannel": "L", "srcChannel": "L", "srcMapType": "documentMap",
                 "srcMapName": mapa}]

    config = {
        "exportShaderParams": False,
        "exportPath": carpeta,
        "defaultExportPreset": "trepadora",
        "exportPresets": [{"name": "trepadora", "maps": [
            {"fileName": "$textureSet_detalle", "channels": rgb("basecolor"), "parameters": param},
            {"fileName": "$textureSet_normal", "channels": rgb("Normal_OpenGL", "virtualMap"),
             "parameters": param},
            {"fileName": "$textureSet_rugosidad", "channels": gris("roughness"), "parameters": param},
        ]}],
        "exportList": [{"rootPath": nombre_set}],
        "exportParameters": [{"parameters": {"sizeLog2": log2}}],
    }
    r = ex.export_project_textures(config)
    print("exportado", log2, nombre_de(r.status), r.message)
    return r


def _a_lineal(i):
    c = i / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def detalle_relativo(origen, destino, escala=None):
    """Luminancia de Painter (sRGB) -> lineal, dividida por su media: media 0,5.

    Solo la luminancia: el tono lo pone el color de cada punto del tallo.
    Devuelve la escala; se calcula con la primera resolución y se usa la misma
    en las demás, para que todas den el mismo tono.
    """
    img = QtGui.QImage(origen).convertToFormat(QtGui.QImage.Format.Format_Grayscale8)
    ancho, alto = img.width(), img.height()
    datos = bytes(img.constBits())[:img.sizeInBytes()]
    fila = img.bytesPerLine()
    if fila != ancho:   # quitar el relleno de cada fila
        datos = b"".join(datos[y * fila:y * fila + ancho] for y in range(alto))
    lineal = [_a_lineal(i) for i in range(256)]
    if escala is None:
        cuenta = [datos.count(bytes([v])) for v in range(256)]
        media = sum(n * lineal[v] for v, n in enumerate(cuenta)) / max(1, len(datos))
        escala = 0.5 / max(media, 1e-4)
        print("   media lineal", round(media, 4))
    tabla = bytes(max(0, min(255, int(round(255.0 * (0.5 + CONTRASTE * (lineal[v] * escala - 0.5))))))
                  for v in range(256))
    buf = datos.translate(tabla)
    gris = QtGui.QImage(buf, ancho, alto, ancho, QtGui.QImage.Format.Format_Grayscale8)
    nueva = gris.convertToFormat(QtGui.QImage.Format.Format_RGB888)
    print("   ", os.path.basename(destino), ancho, nueva.save(destino, "JPG", 91))
    return escala


def a_jpg(origen, destino, gris=False):
    img = QtGui.QImage(origen)
    if gris:
        img = img.convertToFormat(QtGui.QImage.Format.Format_Grayscale8)
    print("   ", os.path.basename(destino), img.width(), img.save(destino, "JPG", 92 if not gris else 90))


def contacto(rutas, destino, lado=160):
    imagen = QtGui.QImage(lado * len(rutas), lado, QtGui.QImage.Format.Format_RGB888)
    imagen.fill(QtGui.QColor(30, 30, 30))
    pintor = QtGui.QPainter(imagen)
    for i, ruta in enumerate(rutas):
        img = QtGui.QImage(ruta)
        if not img.isNull():   # reducida con filtro: sin él, la corteza parece ruido
            pintor.drawImage(i * lado, 0, img.scaled(
                lado, lado, QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation))
    pintor.end()
    print("contacto", destino, imagen.save(destino, "JPG", 45), os.path.getsize(destino))


def pasos():
    if pr.is_open():
        if not es_de_prueba():
            print("HAY UN PROYECTO ABIERTO:", pr.name(), pr.file_path(), "- no sigo")
            return
        print("cierro el proyecto de prueba", pr.name())
        pr.close()
        yield
    for carpeta in (MALLAS, CRUDO, TEXTURAS):
        os.makedirs(carpeta, exist_ok=True)
    obj = os.path.join(MALLAS, "corteza.obj")
    cilindro(obj)
    ajustes = pr.Settings(normal_map_format=pr.NormalMapFormat.OpenGL,
                          default_texture_resolution=4096)
    pr.create(mesh_file_path=obj, settings=ajustes)
    t = time.time()
    while pr.is_busy() or not pr.is_in_edition_state():
        if time.time() - t > 300:
            print("el proyecto no termina de abrirse")
            return
        yield
    conjunto = ts.all_texture_sets()[0]
    print("proyecto", pr.name(), conjunto.name(), conjunto.get_resolution().width)
    pila = conjunto.get_stack()
    material = [r for r in rs.search("bark") if "/wood_bark/" in r.identifier().url()][0]
    capa = ls.insert_fill(ls.InsertPosition.from_textureset_stack(pila))
    capa.set_name("corteza")
    capa.set_material_source(material.identifier())
    fuente = capa.get_material_source()
    valores = fuente.get_parameters()
    print("parametros", {k: v for k, v in sorted(valores.items()) if not k.startswith("channel_")})
    if AJUSTES:
        fuente.set_parameters(AJUSTES)
    for _ in esperar_libre():
        yield
    escala = None
    for res, log2 in RESOLUCIONES:
        exportar(conjunto.name(), log2, os.path.join(CRUDO, res))
        for _ in esperar_libre():
            yield
        crudo = os.path.join(CRUDO, res, conjunto.name() + "_{}.png")
        final = os.path.join(TEXTURAS, res)
        os.makedirs(final, exist_ok=True)
        escala = detalle_relativo(crudo.format("detalle"),
                                  os.path.join(final, "corteza_detalle.jpg"), escala)
        a_jpg(crudo.format("normal"), os.path.join(final, "corteza_normal.jpg"))
        a_jpg(crudo.format("rugosidad"), os.path.join(final, "corteza_rugosidad.jpg"), gris=True)
        yield
    contacto([os.path.join(TEXTURAS, "1k", "corteza_" + m + ".jpg")
              for m in ("detalle", "normal", "rugosidad")],
             os.path.join(CARPETA, "export", "contacto_corteza.jpg"))
    for res, _ in RESOLUCIONES:
        carpeta = os.path.join(TEXTURAS, res)
        print("archivos", res, [(f, os.path.getsize(os.path.join(carpeta, f)))
                                for f in sorted(os.listdir(carpeta))])
    print("listo: el proyecto queda abierto, sin guardar")
