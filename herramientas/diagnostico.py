"""Cifras del crecimiento en la ruina (herramienta de desarrollo).

No forma parte del plugin. Da las mismas cifras dentro y fuera de Maya, para
comprobar que Maya y las pruebas hacen crecer la misma planta.

Fuera de Maya::

    python3 herramientas/diagnostico.py

En Maya (Script Editor, pestaña Python)::

    exec(open("/ruta/Trepadora/herramientas/diagnostico.py").read())
    print(cifras_en_maya())

O desde la terminal, abriendo Maya y cerrándolo al terminar::

    TREPADORA_RAIZ=/ruta/Trepadora TREPADORA_SALIDA=/ruta/de/salida TREPADORA_PREFIJO=maya2027 \
        maya -command "python(\\"exec(open('/ruta/Trepadora/herramientas/diagnostico.py').read()); diagnostico_y_salir()\\")"
"""

import json
import math
import os
import sys

_RAIZ = os.environ.get("TREPADORA_RAIZ") or os.path.dirname(
    os.path.dirname(os.path.abspath(globals().get("__file__", "."))))
for _carpeta in (os.path.join(_RAIZ, "scripts"), os.path.join(_RAIZ, "tests")):
    if _carpeta not in sys.path:
        sys.path.insert(0, _carpeta)


def _crecer(superficie, semilla=1):
    """Crece la ruina con los mismos ajustes que prototipo.escena_ruina()."""
    from trepadora import escenas
    from trepadora.crecimiento import Crecimiento, Parametros
    from trepadora.hojas import ParametrosHojas, colocar_hojas

    ajustes = dict(escenas.RUINA["ajustes"])
    paso = ajustes.pop("paso")
    hojas = dict(ajustes.pop("hojas", {}))
    base = {
        "longitud_paso": paso,
        "distancia_adherencia": paso * 3.0,
        "separacion": paso * 0.05,
        "radio_espacio": paso * 2.0,
        "semilla": semilla,
    }
    base.update(ajustes)
    crecimiento = Crecimiento(superficie, Parametros(**base))
    for origen in escenas.RUINA["origenes"]:
        crecimiento.anadir_origen(origen)
    pasos = crecimiento.crecer()
    hojas["tamano"] = paso * 2.4 * hojas.get("tamano", 1.0)
    hojas.setdefault("semilla", semilla)
    return crecimiento, colocar_hojas(crecimiento, ParametrosHojas(**hojas)), pasos, paso


def _cifras(crecimiento, hojas, pasos, paso):
    tamanos = sorted(h.tamano for h in hojas)
    # Hojas sobre el frente del pilar izquierdo del muro, por franjas de altura.
    franjas = []
    for y0 in range(0, 240, 60):
        zona = [h for h in hojas
                if -150 < h.tallo[0] < -40 and y0 <= h.tallo[1] < y0 + 60 and h.tallo[2] > 5]
        franjas.append([len(zona), round(sum(h.tamano for h in zona) / max(1, len(zona)), 2)])
    primera = crecimiento.ramas[0].puntos[:40:8] if crecimiento.ramas else []
    return {
        "paso": paso,
        "pasos": pasos,
        "ramas": len(crecimiento.ramas),
        "puntos": crecimiento.total_puntos,
        "hojas": len(hojas),
        "tamano_medio": round(sum(tamanos) / max(1, len(tamanos)), 2),
        "tamano_mediana": round(tamanos[len(tamanos) // 2], 2) if tamanos else 0,
        "tamano_max": round(tamanos[-1], 2) if tamanos else 0,
        "pilar_izq_por_franjas": franjas,
        "primeros_puntos": [[round(c, 1) for c in q] for q in primera],
    }


def cifras_fuera_de_maya(semilla=1):
    from superficies import escena_ruina
    return _cifras(*_crecer(escena_ruina(), semilla))


def cifras_en_maya(semilla=1):
    from maya import cmds
    from trepadora import prototipo
    from trepadora.superficie_maya import SuperficieMaya

    cmds.file(new=True, force=True)
    mallas, _ = prototipo.crear_escena("ruina")
    largas = cmds.ls(mallas, long=True)
    return _cifras(*_crecer(SuperficieMaya(largas), semilla))


def diagnostico_y_salir():
    carpeta = os.environ.get("TREPADORA_SALIDA", os.path.join(_RAIZ, "capturas"))
    prefijo = os.environ.get("TREPADORA_PREFIJO", "maya")
    if not os.path.isdir(carpeta):
        os.makedirs(carpeta)
    try:
        texto = json.dumps(cifras_en_maya(), sort_keys=True)
        with open(os.path.join(carpeta, prefijo + "_diagnostico.json"), "w") as f:
            f.write(texto + "\n")
        print(texto)
    except Exception:
        import traceback
        with open(os.path.join(carpeta, prefijo + "_diagnostico_error.txt"), "w") as f:
            traceback.print_exc(file=f)
    finally:
        sys.stdout.flush()
        os._exit(0)


if __name__ == "__main__":
    print(json.dumps(cifras_fuera_de_maya(), sort_keys=True))
