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
    densidad: float = 0.82
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
    # Cuánto menguan las hojas hacia las partes más jóvenes de la planta, las
    # más alejadas de la raíz (0 = todas iguales).
    degradado: float = 0.7
    # Cuánto se aclaran las hojas sobre los tallos gruesos para que se vea la
    # madera (0 = igual de tupidas que en el resto).
    tronco_visible: float = 1.0
    # Fracción de hojas que dan los tallos que reptan por el suelo.
    en_suelo: float = 0.4
    # Cuánto se agrupan las hojas en matas grandes y oscuras con zonas más
    # ralas y claras entre ellas (0 = reparto uniforme).
    manchas: float = 0.6
    # Tamaño de esas matas, en largos de hoja.
    escala_manchas: float = 7.0
    # Fracción de hojas viejas con tinte bronce, como la hiedra en invierno.
    bronce: float = 0.04


@dataclass
class Hoja:
    base: Vector          # punto donde empieza la lámina
    tallo: Vector         # punto del tallo del que sale
    adelante: Vector      # dirección de la base a la punta
    normal: Vector        # cara de la hoja
    tamano: float
    edad: float           # 0 = recién brotada, 1 = adulta
    lobulado: float = 1.0  # 1 = hoja de hiedra con lóbulos, 0 = acorazonada
    tono: float = 0.5      # 0..1, elige el matiz de verde de la hoja
    claridad: float = 0.0  # -1 = verde oscuro y viejo, 1 = claro y nuevo
    tinte: float = 0.0     # 0..1, cuánto tira la hoja a bronce


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
    # Lo gruesa que es cada parte de la planta (1 en la base del tronco) y lo
    # lejos que queda de la raíz (1 en la punta más alejada).
    grosor = crecimiento.grosores(1.0, 0.0)
    recorrido = _recorrido(crecimiento)
    raices = [r.puntos[0][1] for r in crecimiento.ramas if r.madre is None and r.puntos]
    piso = min(raices) + 2.0 if raices else None
    escala_manchas = max(p.tamano * p.escala_manchas, 1e-6)
    for i_rama, rama in enumerate(crecimiento.ramas):
        n = len(rama.puntos)
        if n < 2:
            continue
        lado = 1.0 if rng.random() < 0.5 else -1.0
        # Cada rama tiene su vigor: unas dan hojas grandes y tupidas, otras
        # pequeñas y ralas. Así la masa se agrupa en matas en vez de ser uniforme.
        vigor = max(0.55, min(1.45, rng.gauss(1.0, 0.22)))
        # Y su matiz: las hojas de una misma rama se parecen, así el color va
        # por manchas (más amarillento aquí, más azulado allá) y no a sal y
        # pimienta.
        tono_rama = rng.random()
        escala_gen = (1.12, 1.0, 0.86, 0.76, 0.7)[min(rama.generacion, 4)]
        colgante = getattr(rama, "colgante", False)
        frente = _frente_colgante(crecimiento, rama) if colgante else None
        # Las ramillas son cortas: sus hojas maduran antes. Las de los tallos
        # que cuelgan también, o el tallo parece un hilo con hojitas.
        jovenes = p.puntas_jovenes
        if getattr(rama, "ramilla", False):
            jovenes *= 0.35
        elif colgante:
            jovenes *= 0.5
        for k in range(1, n):
            punto = rama.puntos[k]
            normal_sup = rama.normales[k]
            grueso, lejos = grosor[i_rama][k], recorrido[i_rama][k]
            densidad = p.densidad * (0.65 + 0.35 * vigor)
            # La madera vieja y gruesa pierde parte de sus hojas y deja ver el
            # tronco; las partes más jóvenes, lejos de la raíz, están más ralas.
            if grueso > 0.3:
                densidad *= max(0.25, 1.0 - (grueso - 0.3) * 2.0 * p.tronco_visible)
            if lejos < 0.06:
                # El arranque de cada planta, junto a la raíz, es madera casi
                # desnuda.
                densidad *= 1.0 - 0.65 * p.tronco_visible * (1.0 - lejos / 0.06)
            densidad *= 1.0 - 0.6 * p.degradado * lejos * lejos
            # Matas y claros: un ruido suave en el espacio hace que unas zonas
            # estén más tupidas que otras, como en una hiedra de verdad.
            mata = _suave(_ruido(punto, escala_manchas, p.semilla))
            densidad *= 1.0 - 0.55 * p.manchas * (1.0 - mata)
            if piso is not None and normal_sup[1] > 0.8 and punto[1] < piso:
                densidad *= p.en_suelo
            if rng.random() >= densidad:
                continue
            lado = -lado
            anterior = rama.puntos[k - 1]
            t = v.unitario(v.resta(punto, anterior))
            if t is None:
                continue
            if frente is not None and abs(v.punto(normal_sup, v.ARRIBA)) > 0.5:
                # Cuelga en el aire bajo un saliente: la superficie más cercana
                # es un techo o un suelo, y las hojas quedarían de canto.
                normal_sup = frente
            costado = v.unitario(v.cruz(normal_sup, t))
            if costado is None:
                continue
            costado = v.escala(costado, lado)

            # Las hojas de una punta que sigue creciendo son pequeñas; si la rama
            # ya paró hace tiempo, sus últimas hojas también han madurado.
            desde_punta = (n - k) + (0 if rama.viva else jovenes * 0.3)
            edad = min(1.0, desde_punta / float(max(jovenes, 1.0)))
            tamano = p.tamano * (0.3 + 0.7 * edad) * vigor * escala_gen
            tamano *= 1.0 + p.degradado * (0.45 - lejos)
            tamano *= 1.0 + 0.35 * p.manchas * (mata - 0.5)
            if colgante:
                tamano *= 0.85
            tamano *= 1.0 + p.variacion * (rng.random() * 2.0 - 1.0)

            # Dirección de la hoja: hacia un costado, un poco hacia delante,
            # y con la punta cayendo hacia abajo sobre la pared. Algunas hojas
            # se levantan un poco de la pared (nunca hacia dentro).
            ruido, levanta = _aleatorio(rng), p.despegue * rng.random() * 0.8
            adelante = _direccion(costado, t, normal_sup, p.caida, ruido, levanta)
            if (adelante is not None and superficie is not None
                    and _choca_con_horizontal(superficie, punto, adelante, tamano, normal_sup)):
                # En lo alto de un muro, una hoja que apunta hacia arriba asoma
                # de pie por encima del borde como una bandera; al pie, una que
                # apunta hacia abajo acaba arrugada contra el suelo. Sale hacia
                # el otro lado. Encima quedan las hojas tumbadas de los tallos
                # que sí pasan al remate.
                costado = v.escala(costado, -1.0)
                adelante = _direccion(costado, t, normal_sup, p.caida, ruido, levanta)
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

            # El rabillo sale hacia fuera y hacia delante, con largo variable:
            # así las hojas se escalonan como tejas en vez de en fila.
            peciolo = v.suma(v.escala(costado, 0.45), v.escala(normal_sup, 0.6))
            peciolo = v.suma(peciolo, v.escala(t, rng.uniform(-0.1, 0.5)))
            peciolo = v.suma(peciolo, v.escala(_aleatorio(rng), 0.25))
            largo = tamano * p.peciolo * rng.uniform(0.45, 1.5)
            peciolo = v.escala(v.unitario(peciolo) or costado, largo)
            base = v.suma(punto, peciolo)

            if superficie is not None:
                base = _sin_atravesar(superficie, base, adelante, cara, tamano, normal_sup)
                if base is None:
                    continue
            # Las hojas de las puntas y de las ramas colgantes son más enteras.
            lobulado = min(1.0, max(0.0, rng.gauss(0.95, 0.15) - (0.35 if colgante else 0.0)))
            # Lo nuevo, lejos de la raíz y en los claros, es más claro; las
            # matas viejas, más oscuras. Alguna hoja vieja tira a bronce.
            claridad = (0.9 * (lejos - 0.4) + 0.8 * p.manchas * (0.5 - mata)
                        + rng.gauss(0.0, 0.18))
            tinte = 0.0
            if edad > 0.8 and rng.random() < p.bronce:
                tinte = rng.uniform(0.35, 0.8)
            hojas.append(Hoja(base=base, tallo=punto, adelante=adelante, normal=cara,
                              tamano=tamano, edad=edad, lobulado=lobulado,
                              tono=min(0.999, max(0.0, tono_rama + rng.gauss(0.0, 0.14))),
                              claridad=max(-1.0, min(1.0, claridad)), tinte=tinte))
    return hojas


def _direccion(costado, t, normal_sup, caida, ruido, levanta):
    abajo = v.unitario(v.tangente(v.ABAJO, normal_sup)) or v.CERO
    adelante = v.suma(v.escala(costado, 1.0), v.escala(t, 0.25))
    adelante = v.suma(adelante, v.escala(abajo, caida * 1.5))
    adelante = v.suma(adelante, v.escala(ruido, 0.45))
    adelante = v.tangente(adelante, normal_sup)
    return v.unitario(v.suma(adelante, v.escala(normal_sup, levanta)))


def _choca_con_horizontal(superficie, punto, adelante, tamano, normal_sup):
    """True si la hoja de un tallo en una pared acaba sobre una cara horizontal.

    Es decir, si apunta hacia arriba y su punta queda encima de un remate (lo
    alto de un muro, un alféizar), o apunta hacia abajo y su punta da en el
    suelo o en un alféizar que hay debajo.
    """
    if normal_sup[1] > 0.8 or abs(adelante[1]) <= 0.2:
        return False
    punta = v.suma(punto, v.escala(adelante, tamano * 1.2))
    cercano, normal = superficie.mas_cercano(punta)
    n = v.unitario(v.vec(normal))
    if n is None or n[1] <= 0.8:
        return False
    if adelante[1] > 0.0:
        return cercano[1] > punto[1] - tamano
    return cercano[1] < punto[1]


def _recorrido(crecimiento):
    """Distancia de cada punto a la raíz por el tallo, de 0 a 1."""
    distancias = []
    for rama in crecimiento.ramas:
        if rama.madre is not None and rama.madre < len(distancias) and distancias[rama.madre]:
            madre = distancias[rama.madre]
            d = madre[min(rama.indice_en_madre, len(madre) - 1)]
        else:
            d = 0.0
        fila = []
        anterior = rama.puntos[0] if rama.puntos else None
        for q in rama.puntos:
            d += v.largo(v.resta(q, anterior))
            anterior = q
            fila.append(d)
        distancias.append(fila)
    maximo = max((f[-1] for f in distancias if f), default=0.0) or 1.0
    return [[d / maximo for d in fila] for fila in distancias]


def _frente_colgante(crecimiento, rama):
    """Hacia dónde miran las hojas de un tallo que cuelga en el aire.

    Hacia fuera de la pared de la que cae: su salida, o la última cara
    vertical por la que pasó la rama madre antes de soltarlo.
    """
    candidatos = [getattr(rama, "salida", None)]
    madre = getattr(rama, "madre", None)
    if madre is not None:
        normales = crecimiento.ramas[madre].normales
        i = min(rama.indice_en_madre, len(normales) - 1)
        candidatos += [normales[j] for j in range(i, max(-1, i - 15), -1)]
    for n in candidatos:
        if n is None:
            continue
        horizontal = v.tangente(n, v.ARRIBA)
        if v.largo(horizontal) > 0.6:
            return v.unitario(v.suma(v.unitario(horizontal), v.escala(v.ARRIBA, 0.3)))
    return None


def _sin_atravesar(superficie, base, adelante, cara, tamano, normal_sup):
    """Separa la hoja de la superficie si alguna parte queda dentro.

    Comprueba la punta, los dos bordes y el centro contra todas las caras
    cercanas, no solo la del tallo: al pie de un muro, una hoja que cuelga se
    mete en el suelo aunque el tallo vaya por el muro. Cada vez la saca en la
    dirección de la cara que atraviesa más. Devuelve la nueva base, o None si
    la hoja tendría que separarse demasiado (mejor no ponerla).
    """
    lado = v.cruz(adelante, cara)
    margen = tamano * 0.04
    # Puntos de la hoja ya curvada y plegada (ver geometria.malla_hojas),
    # relativos a la base.
    abajo = v.escala(cara, -1.0)
    desplazamientos = [
        v.suma(v.escala(adelante, tamano), v.escala(abajo, tamano * 0.32)),
        v.suma(v.suma(v.escala(adelante, tamano * 0.26), v.escala(lado, tamano * 0.5)),
               v.escala(abajo, tamano * 0.22)),
        v.suma(v.suma(v.escala(adelante, tamano * 0.26), v.escala(lado, -tamano * 0.5)),
               v.escala(abajo, tamano * 0.22)),
        v.suma(v.escala(adelante, tamano * 0.6), v.escala(abajo, tamano * 0.2)),
    ]
    movido = 0.0
    for _ in range(3):
        falta, salida = 0.0, normal_sup
        for d in desplazamientos:
            q = v.suma(base, d)
            cercano, normal = superficie.mas_cercano(q)
            n = v.unitario(v.vec(normal)) or normal_sup
            hueco = margen - v.punto(v.resta(q, cercano), n)
            if hueco > falta:
                falta, salida = hueco, n
        if falta <= 0.0:
            return base
        movido += falta
        if movido > tamano * 0.6:
            return None
        base = v.suma(base, v.escala(salida, falta))
    return base


def _hash(i, j, k, semilla):
    n = (i * 73856093) ^ (j * 19349663) ^ (k * 83492791) ^ (semilla * 2654435761)
    n = (n ^ (n >> 13)) * 1274126177
    return ((n ^ (n >> 16)) & 0xFFFFFF) / float(0xFFFFFF)


def _ruido(punto, escala, semilla):
    """Ruido de valor 3D suave, de 0 a 1, con dos octavas."""
    total, peso, amplitud = 0.0, 0.0, 1.0
    for octava in range(2):
        e = escala / (2.0 ** octava)
        x, y, z = punto[0] / e, punto[1] / e, punto[2] / e
        i, j, k = math.floor(x), math.floor(y), math.floor(z)
        fx, fy, fz = x - i, y - j, z - k
        fx, fy, fz = (f * f * (3.0 - 2.0 * f) for f in (fx, fy, fz))
        s = semilla + 101 * octava
        valor = 0.0
        for di in (0, 1):
            for dj in (0, 1):
                for dk in (0, 1):
                    w = ((fx if di else 1.0 - fx) * (fy if dj else 1.0 - fy)
                         * (fz if dk else 1.0 - fz))
                    valor += w * _hash(i + di, j + dj, k + dk, s)
        total += amplitud * valor
        peso += amplitud
        amplitud *= 0.5
    return total / peso


def _suave(n):
    """Estira el ruido para que haya matas y claros marcados."""
    t = min(1.0, max(0.0, (n - 0.25) / 0.5))
    return t * t * (3.0 - 2.0 * t)


def _aleatorio(rng) -> Vector:
    g = rng.gauss
    return v.unitario((g(0.0, 1.0), g(0.0, 1.0), g(0.0, 1.0))) or v.CERO
