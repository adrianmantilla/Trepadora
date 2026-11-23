"""Colocación de hojas a lo largo de las ramas (sin Maya)."""

import bisect
import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from . import vectores as v
from .crecimiento import consultar

Vector = Tuple[float, float, float]


@dataclass
class ParametrosHojas:
    semilla: int = 1
    # Probabilidad de que salga una hoja en cada punto de rama.
    densidad: float = 0.82
    # Largo de una hoja adulta, en unidades de la escena.
    tamano: float = 1.0
    # Variación aleatoria del tamaño (0 = todas iguales).
    variacion: float = 0.5
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
    # Cuánto se agrupan las hojas en matas grandes, oscuras y abultadas, con
    # zonas más ralas, planas y claras entre ellas (0 = reparto uniforme).
    manchas: float = 0.6
    # Tamaño de esas matas, en largos de hoja.
    escala_manchas: float = 9.0
    # Cuántas hojas tiran a bronce, como la hiedra en invierno (con 0.015,
    # alrededor de una de cada cien). Salen sueltas, nunca dos juntas,
    # entre las hojas viejas de la parte baja.
    bronce: float = 0.015


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
    # Cada rama, y cada punto de rama, tiene su propio azar: así, si una hoja
    # se descarta o se ajusta algo en una, el resto de la planta no cambia.
    azar = p.semilla * 7919 + 17
    rng = random.Random(azar)
    hojas: List[Hoja] = []
    # Lo gruesa que es cada parte de la planta (1 en la base del tronco) y lo
    # lejos que queda de la raíz (1 en la punta más alejada).
    grosor = crecimiento.grosores(1.0, 0.0)
    recorrido = _recorrido(crecimiento)
    raices = [r.puntos[0][1] for r in crecimiento.ramas if r.madre is None and r.puntos]
    piso = min(raices) + 2.0 if raices else None
    escala_manchas = max(p.tamano * p.escala_manchas, 1e-6)
    # Alto de la planta, para saber qué hojas quedan abajo.
    alturas = [q[1] for r in crecimiento.ramas for q in r.puntos]
    alto_min = min(alturas) if alturas else 0.0
    alto_total = max(max(alturas) - alto_min, 1e-6) if alturas else 1.0
    matas = _campo_de_matas(crecimiento, escala_manchas, p.semilla)
    # Hojas bronce ya puestas, por celdas: una bronce no sale pegada a otra.
    bronces = {}
    lado_bronce = max(p.tamano * _BRONCE_SEPARACION, 1e-6)
    for i_rama, rama in enumerate(crecimiento.ramas):
        n = len(rama.puntos)
        if n < 2:
            continue
        azar_rama = azar + 1000003 * (i_rama + 1)
        rng.seed(azar_rama)
        lado = 1.0 if rng.random() < 0.5 else -1.0
        # Cada rama tiene su vigor: unas dan hojas grandes y tupidas, otras
        # pequeñas y ralas. Así la masa se agrupa en matas en vez de ser uniforme.
        vigor = max(0.55, min(1.45, rng.gauss(1.0, 0.22)))
        # Y su matiz: las hojas de una misma rama se parecen, así el color va
        # por manchas (más amarillento aquí, más azulado allá) y no a sal y
        # pimienta.
        tono_rama = rng.random()
        escala_gen = _ESCALA_GEN[min(rama.generacion, 4)]
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
            rng.seed(azar_rama + 7 * k)
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
            # Los tallos que cuelgan, aunque sean jóvenes, no se quedan en
            # hilos desnudos.
            densidad *= 1.0 - _K_DEG_DENSIDAD * p.degradado * lejos * lejos * (0.4 if colgante else 1.0)
            # Matas y claros: un ruido suave en el espacio hace que unas zonas
            # estén más tupidas que otras, como en una hiedra de verdad. Lo que
            # cuelga en el aire va siempre bien vestido.
            mata = _suave(matas[i_rama][k])
            if colgante:
                mata = max(mata, _MATA_COLGANTE)
            densidad *= 1.0 - _K_DENSIDAD * p.manchas * (1.0 - mata)
            if piso is not None and normal_sup[1] > 0.8 and punto[1] < piso:
                densidad *= p.en_suelo
            if rng.random() >= densidad:
                continue
            lado = -lado
            anterior = rama.puntos[k - 1]
            t = v.unitario(v.resta(punto, anterior))
            if t is None:
                continue
            if frente is not None and (abs(v.punto(normal_sup, v.ARRIBA)) > 0.5
                                       or v.punto(normal_sup, frente) < 0.5):
                # Cuelga en el aire bajo un saliente: la superficie más cercana
                # es un techo, un suelo o el lateral de una ventana, y las
                # hojas quedarían de canto. Miran hacia fuera, a la luz.
                normal_sup = frente
            costado = v.unitario(v.cruz(normal_sup, t))
            if costado is None:
                continue
            costado = v.escala(costado, lado)
            if frente is not None and v.punto(costado, rama.normales[k]) < -0.3:
                # Un tallo que cuelga junto al lateral de una ventana: la hoja
                # que iría contra la piedra se descarta al chocar y el tallo se
                # queda pelado. Sale hacia el hueco, como buscando la luz.
                costado = v.escala(costado, -1.0)

            # Las hojas de una punta que sigue creciendo son pequeñas; si la rama
            # ya paró hace tiempo, sus últimas hojas también han madurado.
            desde_punta = (n - k) + (0 if rama.viva else jovenes * 0.3)
            edad = min(1.0, desde_punta / float(max(jovenes, 1.0)))
            tamano = p.tamano * (0.4 + 0.6 * edad) * vigor * escala_gen
            # Más grandes cerca de la raíz y en las matas; sin llegar a hojitas
            # diminutas en los claros más alejados.
            zona = 1.0 + _K_DEG_TAMANO * p.degradado * (0.45 - lejos) * (0.4 if colgante else 1.0)
            zona *= 1.0 + _K_TAMANO * p.manchas * (mata - 0.5)
            tamano *= min(1.9, max(_ZONA_MIN, zona))
            tamano *= 1.0 + p.variacion * (rng.random() * 2.0 - 1.0)

            # Dirección de la hoja: hacia un costado, un poco hacia delante,
            # y con la punta cayendo hacia abajo sobre la pared. Algunas hojas
            # se levantan un poco de la pared (nunca hacia dentro).
            # En las matas las hojas se levantan más y la masa abulta. Sobre
            # lo alto de un muro o de un capitel, no: ahí se quedan tumbadas.
            encima = normal_sup[1] > 0.5
            abulta = 1.0 if encima else 1.0 + 1.4 * p.manchas * (mata - 0.4)
            ruido, levanta = _aleatorio(rng), p.despegue * rng.random() * 0.8 * abulta
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

            # La cara mira hacia fuera y a la luz, con giro al azar: en la pared,
            # bastante, para que la masa no se lea como una alfombra; en lo que
            # cuelga, menos, que una hoja de canto de frente no se ve.
            cara = v.suma(normal_sup, v.escala(_aleatorio(rng), 0.6 if colgante else 0.85))
            cara = v.suma(cara, v.escala(v.ARRIBA, 0.25))
            cara = v.unitario(v.tangente(cara, adelante))
            if cara is None:
                continue
            if v.punto(cara, normal_sup) < 0.15:
                cara = v.unitario(v.tangente(normal_sup, adelante)) or cara

            # El rabillo sale hacia fuera y hacia delante, con largo variable:
            # así las hojas se escalonan como tejas en vez de en fila.
            peciolo = v.suma(v.escala(costado, 0.45), v.escala(normal_sup, 0.25 if encima else 0.6))
            peciolo = v.suma(peciolo, v.escala(t, rng.uniform(-0.1, 0.5)))
            peciolo = v.suma(peciolo, v.escala(_aleatorio(rng), 0.25))
            # Rabillos largos en las matas: las hojas se escalonan a distintas
            # distancias del muro y la masa gana bulto y sombras. En los claros,
            # cortos, y las hojas quedan planas contra la piedra.
            largo = tamano * p.peciolo * rng.uniform(0.45, 1.5)
            largo *= 0.6 if encima else max(0.4, 1.0 + _K_RABILLO * p.manchas * (mata - 0.3))
            peciolo = v.escala(v.unitario(peciolo) or costado, largo)
            base = v.suma(punto, peciolo)

            if superficie is not None:
                tumbada = _tumbar_en_remate(superficie, base, adelante, cara, normal_sup, tamano)
                if tumbada is not None:
                    base, adelante, cara = tumbada
                base = _sin_atravesar(superficie, base, adelante, cara, tamano, normal_sup)
                if base is None:
                    continue
            # Las hojas de las puntas y de las ramas colgantes son más enteras.
            lobulado = min(1.0, max(0.0, rng.gauss(0.95, 0.15) - (0.35 if colgante else 0.0)))
            # Los claros son de un verde más claro y las matas, más oscuras;
            # por manchas, no hoja a hoja. Lo más alejado de la raíz aclara un
            # poco. Alguna hoja vieja tira a bronce.
            # Lo que cuelga queda a la sombra de dintel o saliente: un poco
            # más claro, para que no salga casi negro.
            claridad = (_K_CLARO_LEJOS * (lejos - 0.4)
                        + (_CLARO_COLGANTE if colgante else _K_CLARO_MATA * p.manchas * (0.5 - mata))
                        + rng.gauss(0.0, 0.1))
            if not colgante and not encima:
                # En una mata, las hojas de fuera reciben la luz y las de dentro
                # quedan a la sombra de las demás. Las de fuera, más claras: la
                # mata se lee con volumen y no como un bloque oscuro.
                fuera = (v.punto(v.resta(base, punto), normal_sup) / tamano
                         + 0.5 * max(0.0, v.punto(adelante, normal_sup)))
                claridad += _K_CLARO_FUERA * p.manchas * mata * (min(fuera, 0.9) - _FUERA_MEDIO)
            tinte = 0.0
            bajo = (punto[1] - alto_min) / alto_total
            if (p.bronce > 0.0 and edad > 0.85 and bajo < 0.3 and not colgante
                    and not encima):
                rodal = _ruido(punto, escala_manchas * 0.5, p.semilla + 57)
                if rng.random() < p.bronce * min(_BRONCE_MAX, _K_BRONCE * max(0.0, rodal - _BRONCE_UMBRAL)):
                    tinte = rng.uniform(0.55, 0.95)
                    if _bronce_cerca(bronces, base, lado_bronce):
                        tinte = 0.0
                    else:
                        celda = tuple(int(math.floor(c / lado_bronce)) for c in base)
                        bronces.setdefault(celda, []).append(base)
            hojas.append(Hoja(base=base, tallo=punto, adelante=adelante, normal=cara,
                              tamano=tamano, edad=edad, lobulado=lobulado,
                              tono=min(0.999, max(0.0, tono_rama + rng.gauss(0.0, 0.14))),
                              claridad=max(-1.0, min(1.0, claridad)), tinte=tinte))
    return hojas


def _direccion(costado, t, normal_sup, caida, ruido, levanta):
    abajo = v.unitario(v.tangente(v.ABAJO, normal_sup))
    adelante = v.suma(v.escala(costado, 1.0), v.escala(t, 0.25))
    adelante = v.suma(adelante, v.escala(abajo or v.CERO, caida * 1.5))
    adelante = v.suma(adelante, v.escala(ruido, 0.45))
    # Se normaliza antes de despegarla: si el costado, la caída y el azar casi
    # se anulan, la hoja saldría derecha de la pared, como una aleta.
    adelante = (v.unitario(v.tangente(adelante, normal_sup))
                or v.unitario(v.tangente(costado, normal_sup)))
    if adelante is None:
        return None
    if abajo is not None:
        # En un tallo que corre de lado por la pared, la mitad de las hojas
        # saldría hacia arriba, de pie como banderas. La hiedra no las pone
        # así: el rabillo gira y la lámina queda de lado o colgando.
        sube = -v.punto(adelante, abajo)
        if sube > _SUBIDA_MAX:
            lateral = (v.unitario(v.suma(adelante, v.escala(abajo, sube)))
                       or v.unitario(v.cruz(normal_sup, abajo)))
            adelante = v.suma(v.escala(abajo, -_SUBIDA_MAX),
                              v.escala(lateral, math.sqrt(1.0 - _SUBIDA_MAX ** 2)))
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
    cercano, n = consultar(superficie, punta)
    if n is None or n[1] <= 0.8:
        return False
    if adelante[1] > 0.0:
        return cercano[1] > punto[1] - tamano
    return cercano[1] < punto[1]


# Cuánto cambian la densidad y el tamaño entre mata y claro. En los claros
# quedan menos hojas, pero no diminutas (_ZONA_MIN): si no, los tallos se ven
# como una red.
_K_DENSIDAD = 1.0
_K_TAMANO = 0.6
_ZONA_MIN = 0.6
# Cuánto más oscuras son las matas y más claros los claros.
_K_CLARO_MATA = 1.8
# Dentro de las matas, cuánto más claras son las hojas que sobresalen (las de
# fuera) que las pegadas a la pared. _FUERA_MEDIO es lo que sobresale una hoja
# típica de mata, en largos de hoja: por encima aclara y por debajo oscurece.
_K_CLARO_FUERA = 2.0
_FUERA_MEDIO = 0.45
# Los tallos que cuelgan van tupidos (como en una mata) pero con el verde de
# un claro.
_MATA_COLGANTE = 0.9
_CLARO_COLGANTE = 0.15
# Las matas salen de un ruido de dos octavas: manchas grandes de borde
# irregular, y la segunda octava abre algún claro dentro de las matas grandes
# (sin ella, lo alto de un muro podía quedar como un solo bloque). Como el
# ruido se pasa a percentil, con _ANCHO_MATA 0.8 queda un 10 % de la planta en
# claro pleno, un 10 % en mata plena y el resto en transición suave.
_OCTAVAS_MATA = 2
_PERSISTENCIA_MATA = 0.45
_ANCHO_MATA = 0.8
# Degradado por distancia a la raíz, flojo: si pesa mucho, la planta se lee
# como "tupida abajo, rala arriba" en vez de matas repartidas.
_K_DEG_DENSIDAD = 0.35
_K_DEG_TAMANO = 0.6
_K_CLARO_LEJOS = 0.2
# Rabillos más largos en las matas (bulto) que en los claros.
_K_RABILLO = 3.0
# Rodales de bronce: salen donde el ruido pasa de _BRONCE_UMBRAL (casi toda la
# parte baja y vieja de la planta) y ahí tiran a bronce como mucho _BRONCE_MAX
# veces la proporción pedida. Así quedan sueltas entre las verdes y no en una
# mancha marrón.
_BRONCE_UMBRAL = 0.35
_K_BRONCE = 200.0
_BRONCE_MAX = 5.0
# Distancia mínima entre dos hojas bronce, en tamaños de hoja: de dos en dos o
# de tres en tres, juntas, ya se leen como una mancha rojiza.
_BRONCE_SEPARACION = 1.5
# Tamaño de las hojas según la generación de la rama (tronco, rama, ramilla...).
_ESCALA_GEN = (1.12, 1.0, 0.86, 0.76, 0.7)
# Lo más que apunta hacia arriba una hoja en una pared (seno del ángulo con
# la horizontal): unos 17 grados.
_SUBIDA_MAX = 0.3


def _bronce_cerca(bronces, punto, lado):
    """True si alguna hoja de ``bronces`` (por celdas de ``lado``) queda a menos de ``lado``."""
    cx, cy, cz = (int(math.floor(c / lado)) for c in punto)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for otra in bronces.get((cx + dx, cy + dy, cz + dz), ()):
                    if v.distancia(otra, punto) < lado:
                        return True
    return False


def _tumbar_en_remate(superficie, base, adelante, cara, normal_sup, tamano):
    """Tumba sobre un remate la hoja que quedaría de pie encima de él.

    Una hoja de canto (de una pared, del lateral de una ventana) que cae
    sobre un alféizar, lo alto de un murete o el suelo parecería una aleta
    clavada en la piedra. Se apoya en él: sale hacia fuera de su pared, en
    leve pendiente si nace algo más alta, con la cara hacia arriba.
    Devuelve (base, adelante, cara) o None si no hace falta.
    """
    if abs(cara[1]) >= 0.5:
        return None
    # Apoyada por la punta (cae sobre el remate) o por la base (nace en el
    # borde de lo alto de un muro y se alza como una bandera).
    apoyos = [v.suma(base, v.escala(adelante, tamano * 0.8))]
    if adelante[1] > 0.2:
        apoyos.append(base)
    for q in apoyos:
        cercano, n = consultar(superficie, q)
        if n[1] > 0.8 and v.punto(v.resta(q, cercano), n) <= tamano * 0.5:
            break
    else:
        return None
    plano = v.suma(v.tangente(adelante, n), v.escala(v.tangente(normal_sup, n), 0.6))
    plano = v.unitario(plano)
    if plano is None:
        return None
    alto = v.punto(v.resta(base, cercano), n)
    margen = tamano * 0.06
    if alto < margen:
        base = v.suma(base, v.escala(n, margen - alto))
        alto = margen
    pendiente = min(0.6, (alto - margen) / tamano)
    nuevo = v.unitario(v.suma(plano, v.escala(n, -pendiente)))
    nueva_cara = v.unitario(v.tangente(n, nuevo)) if nuevo is not None else None
    if nuevo is None or nueva_cara is None:
        return None
    return base, nuevo, nueva_cara


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
            cercano, n = consultar(superficie, q)
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


def _ruido(punto, escala, semilla, octavas=2, persistencia=0.5):
    """Ruido de valor 3D suave, de 0 a 1, con varias octavas."""
    total, peso, amplitud = 0.0, 0.0, 1.0
    for octava in range(octavas):
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
        amplitud *= persistencia
    return total / peso


def _girar(q):
    """Gira el punto para que las matas no sigan la rejilla del ruido.

    Sin girar, los bordes de las manchas salen paralelos a los ejes: en una
    columna, una línea horizontal que corta la mata de golpe.
    """
    return (0.8572 * q[0] - 0.5150 * q[1],
            0.3767 * q[0] + 0.6269 * q[1] - 0.6820 * q[2],
            0.3513 * q[0] + 0.5846 * q[1] + 0.7314 * q[2])


def _campo_de_matas(crecimiento, escala, semilla):
    """Ruido de matas en cada punto de rama, pasado a su percentil (0 a 1).

    Así cada planta tiene la misma proporción de matas y de claros, sea cual
    sea su tamaño: en una escena pequeña, una sola mancha de ruido podía
    dejar casi todo el muro en claro.
    """
    crudo = [[_ruido(_girar(q), escala, semilla, _OCTAVAS_MATA, _PERSISTENCIA_MATA)
              for q in rama.puntos] for rama in crecimiento.ramas]
    orden = sorted(x for fila in crudo for x in fila)
    if len(orden) < 2:
        return crudo
    total = float(len(orden) - 1)
    return [[bisect.bisect_left(orden, x) / total for x in fila] for fila in crudo]


def _suave(n):
    """Estira el ruido para que haya matas y claros marcados."""
    t = min(1.0, max(0.0, (n - 0.5 + _ANCHO_MATA / 2.0) / _ANCHO_MATA))
    return t * t * (3.0 - 2.0 * t)


def _aleatorio(rng) -> Vector:
    g = rng.gauss
    return v.unitario((g(0.0, 1.0), g(0.0, 1.0), g(0.0, 1.0))) or v.CERO
