# Pruebas de la corteza de Painter para el puente (trepadora_puente.py).
#
# Usa el proyecto de prueba que deja abierto corteza_painter.py (sin guardar,
# con un solo juego «corteza») y prueba varias densidades del material Wood
# Bark: para cada una exporta a 1K el color y el relieve y monta una hoja de
# contacto en DEV/trepadora_painter/export/contacto_pruebas.jpg. Arriba, el
# detalle (luminancia relativa, como lo usa Trepadora); abajo, el relieve. Cada
# recuadro es la textura entera reducida, que es como se ve en un tallo a la
# distancia de un render normal.
#
# Si el proyecto abierto no es ese, no hace nada.
import os
import time

import substance_painter.export as ex
import substance_painter.layerstack as ls
import substance_painter.project as pr
import substance_painter.textureset as ts
from PySide6 import QtCore, QtGui

TIEMPO_MAX = 900
DENSIDADES = (0.2, 0.35, 0.48)
LADO = 160
SALIDA = os.path.join(CARPETA, "export", "pruebas")


def nombre_de(x):
    return str(x).split(".")[-1]


def es_de_prueba():
    try:
        nombres = [c.name() for c in ts.all_texture_sets()]
    except Exception:
        return False
    return pr.is_open() and pr.file_path() is None and nombres == ["corteza"]


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

    config = {
        "exportShaderParams": False,
        "exportPath": carpeta,
        "defaultExportPreset": "pruebas",
        "exportPresets": [{"name": "pruebas", "maps": [
            {"fileName": "$textureSet_detalle", "channels": rgb("basecolor"), "parameters": param},
            {"fileName": "$textureSet_normal", "channels": rgb("Normal_OpenGL", "virtualMap"),
             "parameters": param},
        ]}],
        "exportList": [{"rootPath": nombre_set}],
        "exportParameters": [{"parameters": {"sizeLog2": log2}}],
    }
    r = ex.export_project_textures(config)
    print("exportado", nombre_de(r.status), r.message)
    return r


def _a_lineal(i):
    c = i / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def gris_relativo(origen):
    """Luminancia de Painter pasada a lineal y dividida por su media (media 0,5)."""
    img = QtGui.QImage(origen).convertToFormat(QtGui.QImage.Format.Format_Grayscale8)
    ancho, alto = img.width(), img.height()
    datos = bytes(img.constBits())[:img.sizeInBytes()]
    fila = img.bytesPerLine()
    if fila != ancho:
        datos = b"".join(datos[y * fila:y * fila + ancho] for y in range(alto))
    lineal = [_a_lineal(i) for i in range(256)]
    cuenta = [datos.count(bytes([v])) for v in range(256)]
    total = max(1, len(datos))
    media = sum(n * lineal[v] for v, n in enumerate(cuenta)) / total
    k = 0.5 / max(media, 1e-4)
    valores = [min(255, int(round(255.0 * lineal[v] * k))) for v in range(256)]
    m2 = sum(n * (valores[v] / 255.0) ** 2 for v, n in enumerate(cuenta)) / total
    m1 = sum(n * valores[v] / 255.0 for v, n in enumerate(cuenta)) / total
    recortado = sum(n for v, n in enumerate(cuenta) if valores[v] >= 255) / total
    buf = datos.translate(bytes(valores))
    salida = QtGui.QImage(buf, ancho, alto, ancho, QtGui.QImage.Format.Format_Grayscale8).copy()
    return salida, {"media_lineal": round(media, 4), "media": round(m1, 3),
                    "desviacion": round(max(0.0, m2 - m1 * m1) ** 0.5, 3),
                    "recortado": round(recortado, 4)}


def reducir(img):
    return img.scaled(LADO, LADO, QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                      QtCore.Qt.TransformationMode.SmoothTransformation)


def pasos():
    if not es_de_prueba():
        print("no está abierto el proyecto de prueba de la corteza - no sigo")
        return
    conjunto = ts.all_texture_sets()[0]
    capas = [c for c in ls.get_root_layer_nodes(conjunto.get_stack())
             if c.get_name() == "corteza"]
    if not capas:
        print("no encuentro la capa «corteza» - no sigo")
        return
    fuente = capas[0].get_material_source()
    print("densidad de antes", fuente.get_parameters().get("bark_density"))
    fila_detalle, fila_normal = [], []
    for d in DENSIDADES:
        fuente.set_parameters({"bark_density": d})
        for _ in esperar_libre():
            yield
        carpeta = os.path.join(SALIDA, "densidad_{:.2f}".format(d))
        exportar(conjunto.name(), 10, carpeta)
        for _ in esperar_libre():
            yield
        crudo = os.path.join(carpeta, conjunto.name() + "_{}.png")
        gris, datos = gris_relativo(crudo.format("detalle"))
        print("densidad", d, datos)
        fila_detalle.append(reducir(gris).convertToFormat(QtGui.QImage.Format.Format_RGB888))
        fila_normal.append(reducir(QtGui.QImage(crudo.format("normal"))))
        yield
    hoja = QtGui.QImage(LADO * len(DENSIDADES), LADO * 2, QtGui.QImage.Format.Format_RGB888)
    hoja.fill(QtGui.QColor(30, 30, 30))
    pintor = QtGui.QPainter(hoja)
    for i, (a, b) in enumerate(zip(fila_detalle, fila_normal)):
        pintor.drawImage(i * LADO, 0, a)
        pintor.drawImage(i * LADO, LADO, b)
    pintor.end()
    destino = os.path.join(CARPETA, "export", "contacto_pruebas.jpg")
    print("contacto", destino, hoja.save(destino, "JPG", 40), os.path.getsize(destino))
    print("listo: el proyecto queda abierto, sin guardar, con densidad", DENSIDADES[-1])
