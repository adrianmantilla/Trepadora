"""Colocación de hojas a lo largo de las ramas (sin Maya)."""

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from . import vectores as v

Vector = Tuple[float, float, float]


@dataclass
class ParametrosHojas:
    semilla: int = 1
    # Probabilidad de que salga una hoja en cada punto de rama.
    densidad: float = 0.75
    # Largo de una hoja adulta, en unidades de la escena.
    tamano: float = 1.0
    # Variación aleatoria del tamaño (0 = todas iguales).
    variacion: float = 0.4
    # Puntos desde la punta en los que las hojas todavía son pequeñas.
    puntas_jovenes: int = 14
    # Largo del pecíolo (rabillo), como fracción del tamaño de la hoja.
    peciolo: float = 0.28
    # Cuánto se despega la hoja de la pared (0 = plana contra ella).
    despegue: float = 0.35
    # Cuánto cuelga la punta de la hoja hacia abajo (0 a 1).
    caida: float = 0.45


@dataclass
class Hoja:
    base: Vector          # punto donde empieza la lámina
    tallo: Vector         # punto del tallo del que sale
    adelante: Vector      # dirección de la base a la punta
    normal: Vector        # cara de la hoja
    tamano: float
    edad: float           # 0 = recién brotada, 1 = adulta


def colocar_hojas(crecimiento, parametros: ParametrosHojas = None, superficie=None) -> List[Hoja]:
    """Coloca hojas a lo largo de las ramas.

    Si se pasa ``superficie`` (por defecto, la del crecimiento), cada hoja se
    comprueba contra ella: si la punta o los bordes quedan dentro de la pared,
    por ejemplo en una esquina, se separa o se descarta.
    """
    p = parametros or ParametrosHojas()
    superficie = superficie if superficie is not None else getattr(crecimiento, "superficie", None)
    rng = random.Random(p.semilla * 7919 + 17)
    hojas: List[Hoja] = []
    for rama in crecimiento.ramas:
        n = len(rama.puntos)
        if n < 2:
            continue
        lado = 1.0 if rng.random() < 0.5 else -1.0
        for k in range(1, n):
            if rng.random() >= p.densidad:
                continue
            lado = -lado
            punto = rama.puntos[k]
            anterior = rama.puntos[k - 1]
            t = v.unitario(v.resta(punto, anterior))
            if t is None:
                continue
            normal_sup = rama.normales[k]
            costado = v.unitario(v.cruz(normal_sup, t))
            if costado is None:
                continue
            costado = v.escala(costado, lado)

            # Las hojas de una punta que sigue creciendo son pequeñas; si la rama
            # ya paró hace tiempo, sus últimas hojas también han madurado.
            desde_punta = (n - k) + (0 if rama.viva else p.puntas_jovenes * 0.6)
            edad = min(1.0, desde_punta / float(max(p.puntas_jovenes, 1)))
            tamano = p.tamano * (0.3 + 0.7 * edad)
            tamano *= 1.0 + p.variacion * (rng.random() * 2.0 - 1.0)

            # Dirección de la hoja: hacia un costado, un poco hacia delante,
            # y con la punta cayendo hacia abajo sobre la pared.
            abajo = v.unitario(v.tangente(v.ABAJO, normal_sup)) or v.CERO
            adelante = v.suma(v.escala(costado, 1.0), v.escala(t, 0.25))
            adelante = v.suma(adelante, v.escala(abajo, p.caida * 1.5))
            adelante = v.suma(adelante, v.escala(_aleatorio(rng), 0.45))
            adelante = v.tangente(adelante, normal_sup)
            # Algunas hojas se levantan un poco de la pared (nunca hacia dentro).
            adelante = v.unitario(v.suma(adelante, v.escala(
                normal_sup, p.despegue * rng.random() * 0.8)))
            if adelante is None:
                continue

            # La cara mira hacia fuera y a la luz, con giro al azar.
            cara = v.suma(normal_sup, v.escala(_aleatorio(rng), 0.55))
            cara = v.suma(cara, v.escala(v.ARRIBA, 0.25))
            cara = v.unitario(v.tangente(cara, adelante))
            if cara is None:
                continue
            if v.punto(cara, normal_sup) < 0.15:
                cara = v.unitario(v.tangente(normal_sup, adelante)) or cara

            peciolo = v.suma(v.escala(costado, 0.5), v.escala(normal_sup, 0.7))
            peciolo = v.escala(v.unitario(peciolo) or costado, tamano * p.peciolo)
            base = v.suma(punto, peciolo)

            if superficie is not None:
                base = _sin_atravesar(superficie, base, adelante, cara, tamano, normal_sup)
                if base is None:
                    continue
            hojas.append(Hoja(base=base, tallo=punto, adelante=adelante, normal=cara,
                              tamano=tamano, edad=edad))
    return hojas


def _sin_atravesar(superficie, base, adelante, cara, tamano, normal_sup):
    """Separa la hoja de la superficie si alguna parte queda dentro.

    Comprueba la punta y los dos bordes. Devuelve la nueva base, o None si la
    hoja tendría que separarse demasiado (mejor no ponerla).
    """
    lado = v.cruz(adelante, cara)
    margen = tamano * 0.04
    # Puntos de la hoja ya curvada y plegada (ver geometria.malla_hojas).
    abajo = v.escala(cara, -1.0)
    muestras = [
        v.suma(v.suma(base, v.escala(adelante, tamano)), v.escala(abajo, tamano * 0.32)),
        v.suma(v.suma(v.suma(base, v.escala(adelante, tamano * 0.26)), v.escala(lado, tamano * 0.5)),
               v.escala(abajo, tamano * 0.22)),
        v.suma(v.suma(v.suma(base, v.escala(adelante, tamano * 0.26)), v.escala(lado, -tamano * 0.5)),
               v.escala(abajo, tamano * 0.22)),
        v.suma(v.suma(base, v.escala(adelante, tamano * 0.6)), v.escala(abajo, tamano * 0.2)),
    ]
    falta = 0.0
    for q in muestras:
        cercano, normal = superficie.mas_cercano(q)
        altura = v.punto(v.resta(q, cercano), v.unitario(v.vec(normal)) or normal_sup)
        falta = max(falta, margen - altura)
    if falta <= 0.0:
        return base
    if falta > tamano * 0.6:
        return None
    return v.suma(base, v.escala(normal_sup, falta))


def _aleatorio(rng) -> Vector:
    g = rng.gauss
    return v.unitario((g(0.0, 1.0), g(0.0, 1.0), g(0.0, 1.0))) or v.CERO
