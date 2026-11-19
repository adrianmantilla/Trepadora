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
    densidad: float = 0.85
    # Largo de una hoja adulta, en unidades de la escena.
    tamano: float = 1.0
    # Variación aleatoria del tamaño (0 = todas iguales).
    variacion: float = 0.35
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


def colocar_hojas(crecimiento, parametros: ParametrosHojas = None) -> List[Hoja]:
    p = parametros or ParametrosHojas()
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

            edad = min(1.0, (n - k) / float(max(p.puntas_jovenes, 1)))
            tamano = p.tamano * (0.3 + 0.7 * edad)
            tamano *= 1.0 + p.variacion * (rng.random() * 2.0 - 1.0)

            # Dirección de la hoja: hacia un costado, un poco hacia delante,
            # y con la punta cayendo hacia abajo sobre la pared.
            abajo = v.unitario(v.tangente(v.ABAJO, normal_sup)) or v.CERO
            adelante = v.suma(v.escala(costado, 1.0), v.escala(t, 0.25))
            adelante = v.suma(adelante, v.escala(abajo, p.caida * 1.5))
            adelante = v.suma(adelante, v.escala(_aleatorio(rng), 0.35))
            # Se despega de la pared levantando la base.
            adelante = v.unitario(v.suma(adelante, v.escala(normal_sup, -p.despegue * 0.3)))
            if adelante is None:
                continue

            # La cara mira hacia fuera, con algo de giro al azar.
            cara = v.suma(normal_sup, v.escala(_aleatorio(rng), 0.3))
            cara = v.suma(cara, v.escala(adelante, p.despegue))
            cara = v.unitario(v.tangente(cara, adelante))
            if cara is None:
                continue

            peciolo = v.suma(v.escala(costado, 0.6), v.escala(normal_sup, 0.6))
            peciolo = v.escala(v.unitario(peciolo) or costado, tamano * p.peciolo)
            base = v.suma(punto, peciolo)
            hojas.append(Hoja(base=base, tallo=punto, adelante=adelante, normal=cara,
                              tamano=tamano, edad=edad))
    return hojas


def _aleatorio(rng) -> Vector:
    g = rng.gauss
    return v.unitario((g(0.0, 1.0), g(0.0, 1.0), g(0.0, 1.0))) or v.CERO
