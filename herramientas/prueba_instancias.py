"""Prueba en Maya de las hojas como instancias (herramienta de desarrollo).

No forma parte del plugin. Hace crecer la ruina con instancias y con una sola
malla y compara: tiempo, tamaño de la escena guardada, que cada instancia
quede donde dicen sus partículas (giro, escala y posición), que todo siga
igual al guardar y volver a abrir, las formas de hoja y los tipos de tallo, y
la hoja propia. Escribe las cifras en un JSON.

Uso desde la terminal, con mayapy (no hace falta abrir Maya)::

    TREPADORA_RAIZ=/ruta/Trepadora mayapy /ruta/Trepadora/herramientas/prueba_instancias.py \\
        /ruta/de/salida
"""

import json
import math
import os
import sys
import time
import traceback

_RAIZ = os.environ.get("TREPADORA_RAIZ") or os.path.dirname(
    os.path.dirname(os.path.abspath(globals().get("__file__", "."))))
for _ruta in (os.path.join(_RAIZ, "scripts"), os.path.join(_RAIZ, "herramientas")):
    if _ruta not in sys.path:
        sys.path.insert(0, _ruta)


def _iniciar():
    try:
        from maya import cmds
        cmds.about(version=True)
    except (ImportError, AttributeError):
        import maya.standalone
        maya.standalone.initialize(name="python")
    from maya import cmds
    try:
        if not cmds.pluginInfo("mtoa", query=True, loaded=True):
            cmds.loadPlugin("mtoa")
    except RuntimeError as error:
        print("prueba_instancias: sin Arnold ({})".format(error))
    return cmds


def _instancias(cmds):
    """(número de partículas, matrices de cada instancia, objetos instanciados) del instanciador."""
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaFX as omfx

    nodos = cmds.ls(type="instancer", long=True)
    if not nodos:
        return 0, [], []
    lista = om.MSelectionList()
    lista.add(nodos[0])
    fn = omfx.MFnInstancer(lista.getDagPath(0))
    rutas, matrices, _, _ = fn.allInstances()
    objetos = cmds.listConnections(nodos[0] + ".inputHierarchy") or []
    return fn.particleCount(), [list(m) for m in matrices], objetos


def _particulas(cmds):
    forma = cmds.ls(type="particle", long=True)[0]
    pos = cmds.getAttr(forma + ".position")
    giros = cmds.getAttr(forma + ".giroPP")
    escalas = cmds.getAttr(forma + ".escalaPP")
    rgb = cmds.getAttr(forma + ".rgbPP")
    return forma, pos, giros, escalas, rgb


def _error_de_colocacion(cmds, matrices):
    """Mayor diferencia entre la matriz de cada instancia y la que dan sus partículas."""
    from trepadora import instancias

    _, pos, giros, escalas, _ = _particulas(cmds)
    peor = 0.0
    for m, p, g, s in zip(matrices, pos, giros, escalas):
        filas = instancias.matriz_euler(g)
        for i in range(3):
            for j in range(3):
                peor = max(peor, abs(m[4 * i + j] - filas[i][j] * s[i]) / max(s[i], 1e-9))
        for j in range(3):
            peor = max(peor, abs(m[12 + j] - p[j]) / max(s[1], 1e-9))
    return peor


def _caja(cmds, nodo):
    try:
        return [round(x, 2) for x in cmds.exactWorldBoundingBox(nodo)]
    except RuntimeError as error:
        return str(error)


def _guardar(cmds, carpeta, nombre):
    tamanos = {}
    for tipo, ext in (("mayaBinary", ".mb"), ("mayaAscii", ".ma")):
        ruta = os.path.join(carpeta, nombre + ext)
        cmds.file(rename=ruta)
        cmds.file(save=True, type=tipo, force=True)
        tamanos[ext] = round(os.path.getsize(ruta) / 1e6, 2)
    return tamanos


def _hoja_de_prueba(cmds):
    """Una hoja plana de alto 1: base en el origen, punta hacia +Y, cara hacia +Z."""
    hoja = cmds.polyPlane(name="miHoja", width=0.6, height=1.0, subdivisionsX=2,
                          subdivisionsY=4)[0]
    cmds.rotate(90, 0, 0, hoja)
    cmds.move(0, 0.5, 0, hoja)
    cmds.makeIdentity(hoja, apply=True, translate=True, rotate=True, scale=True)
    cmds.move(300, 0, 0, hoja)  # lejos, para ver que no importa dónde esté
    return hoja


def probar(carpeta):
    cmds = _iniciar()
    import capturas_maya
    tp = capturas_maya._recargar()
    from trepadora import geometria
    if not os.path.isdir(carpeta):
        os.makedirs(carpeta)
    informe = {"maya": cmds.about(version=True)}
    try:
        informe["mtoa"] = cmds.pluginInfo("mtoa", query=True, version=True)
    except RuntimeError:
        informe["mtoa"] = None

    # 1) Ruina con instancias.
    cmds.file(new=True, force=True)
    inicio = time.time()
    tp.escena_ruina(semilla=1)
    informe["instancias_segundos"] = round(time.time() - inicio, 2)
    particulas, matrices, objetos = _instancias(cmds)
    informe["instancias"] = dict(particulas=particulas, instancias=len(matrices),
                                 modelos=len(objetos),
                                 error_colocacion=_error_de_colocacion(cmds, matrices),
                                 caja=_caja(cmds, cmds.ls(type="instancer")[0]))
    forma, _, _, _, rgb = _particulas(cmds)
    informe["instancias"]["rgbPP_min_max"] = [
        [round(min(c[k] for c in rgb), 3) for k in range(3)],
        [round(max(c[k] for c in rgb), 3) for k in range(3)]]
    informe["instancias"]["puntos_visibles"] = cmds.getAttr(
        cmds.listRelatives(forma, parent=True, fullPath=True)[0] + ".visibility")
    if cmds.attributeQuery("aiExportAttributes", node=forma, exists=True):
        informe["instancias"]["aiExportAttributes"] = cmds.getAttr(forma + ".aiExportAttributes")
    informe["instancias"]["mallas_y_caras"] = {
        m: cmds.polyEvaluate(m, face=True) for m in cmds.ls(type="mesh")
        if not m.startswith("prueba_") and "modelo" not in m}
    informe["instancias"]["archivo_mb_ma_MB"] = _guardar(cmds, carpeta, "ruina_instancias")

    # 2) Guardar y volver a abrir: las hojas siguen en su sitio.
    cmds.file(new=True, force=True)
    cmds.file(os.path.join(carpeta, "ruina_instancias.mb"), open=True, force=True)
    particulas2, matrices2, objetos2 = _instancias(cmds)
    peor = 0.0
    for a, b in zip(matrices, matrices2):
        peor = max(peor, max(abs(x - y) for x, y in zip(a, b)))
    informe["reabrir"] = dict(particulas=particulas2, instancias=len(matrices2),
                              modelos=len(objetos2), diferencia_max=peor)

    # 3) Ruina con una sola malla, para comparar.
    cmds.file(new=True, force=True)
    inicio = time.time()
    tp.escena_ruina(semilla=1, instancias=False)
    informe["malla_segundos"] = round(time.time() - inicio, 2)
    hojas = cmds.ls("trepadora_hojas", long=True)
    informe["malla"] = dict(
        caras_hojas=cmds.polyEvaluate(hojas[0], face=True) if hojas else None,
        caja_hojas=_caja(cmds, hojas[0]) if hojas else None,
        archivo_mb_ma_MB=_guardar(cmds, carpeta, "ruina_malla"))

    # 4) Formas de hoja y tipos de tallo, en la escena sencilla.
    combinaciones = {}
    for forma_hoja in geometria.FORMAS_HOJA:
        for tipo in geometria.TIPOS_TALLO:
            cmds.file(new=True, force=True)
            clave = forma_hoja + "+" + tipo
            try:
                tp.escena_de_prueba(semilla=2, forma_hoja=forma_hoja, tipo_tallo=tipo)
                n, m, o = _instancias(cmds)
                combinaciones[clave] = dict(instancias=len(m), modelos=len(o),
                                            caras_tallos=cmds.polyEvaluate("trepadora_tallos",
                                                                           face=True))
            except Exception as error:  # noqa: BLE001 - se apunta y se sigue
                combinaciones[clave] = "ERROR: {}".format(error)
    informe["formas_y_tallos"] = combinaciones

    # 5) Hoja propia.
    cmds.file(new=True, force=True)
    _hoja_de_prueba(cmds)
    try:
        tp.escena_de_prueba(semilla=2, hoja_propia="miHoja")
        n, m, o = _instancias(cmds)
        propia = cmds.ls("trepadora_hoja_propia", long=True)
        informe["hoja_propia"] = dict(instancias=len(m), modelos=o,
                                      escala=cmds.getAttr(propia[0] + ".scale")[0] if propia else None,
                                      error_colocacion=_error_de_colocacion(cmds, m))
        _guardar(cmds, carpeta, "hoja_propia")
    except Exception as error:  # noqa: BLE001
        informe["hoja_propia"] = "ERROR: {}".format(error)

    texto = json.dumps(informe, indent=1, sort_keys=True, default=str)
    with open(os.path.join(carpeta, "prueba_instancias.json"), "w") as f:
        f.write(texto + "\n")
    print(texto)
    return informe


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    try:
        probar(sys.argv[1])
    except Exception:
        traceback.print_exc()
        sys.exit(2)
