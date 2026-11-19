"""Algoritmo de crecimiento de Trepadora.

Este módulo no depende de Maya ni de NumPy: solo necesita un objeto
"superficie" con un método ``mas_cercano(punto) -> (punto_cercano, normal)``.
Así se puede probar fuera de Maya y reutilizar con cualquier geometría.

Idea general
------------
Cada rama es una lista de puntos. En cada paso, la punta de cada rama viva
avanza una distancia fija. La dirección del avance mezcla varias fuerzas:

* inercia: seguir en la dirección que traía;
* aleatoriedad: pequeñas desviaciones para que no crezca recta;
* luz: tendencia a subir por las paredes (hacia ``direccion_luz``);
* adherencia: si la rama está cerca de la superficie, se pega y la sigue;
* gravedad: si la rama pierde el apoyo, cuelga y busca volver a agarrarse;
* espacio: las ramas se apartan de las zonas ya ocupadas, para repartirse.

Además, cada paso una rama solo puede girar un ángulo máximo, lo que evita
bucles y da curvas suaves. De vez en cuando sale una rama hija desde un punto
cualquiera de la rama madre, no solo desde la punta.
"""

import math
import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from . import vectores as v

Vector = Tuple[float, float, float]


@dataclass
class Parametros:
    """Ajustes del crecimiento. Las distancias van en unidades de la escena."""

    semilla: int = 1
    pasos: int = 200
    longitud_paso: float = 1.0
    # Hasta qué distancia de la superficie se considera que la rama está pegada.
    distancia_adherencia: float = 3.0
    # Separación entre el tallo y la superficie, para que no la atraviese.
    separacion: float = 0.05
    # 0 = ignora la superficie, 1 = la sigue al máximo.
    adherencia: float = 0.8
    gravedad: float = 0.5
    luz: float = 0.3
    direccion_luz: Tuple[float, float, float] = (0.0, 1.0, 0.0)
    aleatoriedad: float = 0.35
    inercia: float = 1.0
    # Giro máximo por paso, en grados. Evita bucles y quiebros bruscos.
    giro_max: float = 20.0
    # Radio (en unidades) en el que una rama nota a las demás.
    radio_espacio: float = 2.0
    # Fuerza con la que se aparta de las zonas ocupadas.
    evitar: float = 0.9
    # Si hay más puntos ajenos que esto dentro del radio, la rama deja de crecer.
    densidad_max: int = 8
    # Probabilidad por paso de que salga una rama hija.
    prob_rama: float = 0.06
    generaciones_max: int = 3
    # Número máximo de puntos de una rama principal.
    longitud_max: int = 150
    # Cada generación es esta fracción de larga que su madre.
    reduccion_por_generacion: float = 0.6
    # Pasos que una rama puede ir en el aire antes de dejar de crecer.
    pasos_sueltos_max: int = 10
    # Tope de seguridad para no colgar Maya.
    limite_puntos: int = 50000


@dataclass
class Rama:
    puntos: List[Vector]
    direccion: Vector
    generacion: int
    longitud_max: int
    madre: Optional[int] = None
    viva: bool = True
    pasos_sueltos: int = 0


class _Rejilla:
    """Rejilla espacial para encontrar rápido los puntos cercanos."""

    def __init__(self, celda: float):
        self.celda = max(celda, v.EPS)
        self._celdas: Dict[Tuple[int, int, int], List[Tuple[Vector, int]]] = {}

    def _clave(self, p: Vector) -> Tuple[int, int, int]:
        c = self.celda
        return (int(math.floor(p[0] / c)), int(math.floor(p[1] / c)), int(math.floor(p[2] / c)))

    def anadir(self, p: Vector, rama: int) -> None:
        self._celdas.setdefault(self._clave(p), []).append((p, rama))

    def vecinos(self, p: Vector, radio: float, excluir: int) -> List[Vector]:
        cx, cy, cz = self._clave(p)
        r2 = radio * radio
        encontrados = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for q, rama in self._celdas.get((cx + dx, cy + dy, cz + dz), ()):
                        if rama == excluir:
                            continue
                        d = v.resta(q, p)
                        if v.punto(d, d) <= r2:
                            encontrados.append(q)
        return encontrados


class Crecimiento:
    """Hace crecer una o varias plantas sobre una superficie."""

    def __init__(self, superficie, parametros: Optional[Parametros] = None):
        self.superficie = superficie
        self.p = parametros or Parametros()
        self.rng = random.Random(self.p.semilla)
        self.ramas: List[Rama] = []
        self.total_puntos = 0
        self.limite_alcanzado = False
        self._luz = v.unitario(v.vec(self.p.direccion_luz)) or v.ARRIBA
        self._giro_max = math.radians(self.p.giro_max)
        self._rejilla = _Rejilla(self.p.radio_espacio)

    # ------------------------------------------------------------------ origen
    def anadir_origen(self, punto, direccion=None) -> Rama:
        """Coloca el nacimiento de una planta en el punto de la superficie más cercano."""
        cercano, normal = self._consultar(v.vec(punto))
        inicio = v.suma(cercano, v.escala(normal, self.p.separacion))

        d = None
        if direccion is not None:
            d = v.unitario(v.tangente(v.vec(direccion), normal))
        if d is None:
            d = v.unitario(v.tangente(self._luz, normal))
        if d is None:
            d = v.perpendicular(normal)

        rama = Rama(puntos=[inicio], direccion=d, generacion=0, longitud_max=self.p.longitud_max)
        self.ramas.append(rama)
        self._registrar(inicio, len(self.ramas) - 1)
        return rama

    # ----------------------------------------------------------------- crecer
    def crecer(self, pasos: Optional[int] = None,
               al_progresar: Optional[Callable[[int, int], bool]] = None) -> int:
        """Ejecuta varios pasos. Devuelve cuántos se hicieron.

        ``al_progresar(paso, total)`` se llama tras cada paso; si devuelve False,
        el crecimiento se detiene y se conserva lo ya generado.
        """
        total = self.p.pasos if pasos is None else pasos
        hechos = 0
        for i in range(total):
            seguir = self.paso()
            hechos += 1
            if al_progresar is not None and al_progresar(i + 1, total) is False:
                break
            if not seguir:
                break
        return hechos

    def paso(self) -> bool:
        """Avanza un paso todas las ramas vivas. Devuelve True si queda alguna viva."""
        nuevas: List[Rama] = []
        for indice in range(len(self.ramas)):
            rama = self.ramas[indice]
            if not rama.viva:
                continue
            if self.total_puntos >= self.p.limite_puntos:
                rama.viva = False
                self.limite_alcanzado = True
                continue
            self._avanzar(rama, indice)
            self._quiza_ramificar(rama, indice, nuevas)
        for hija in nuevas:
            self.ramas.append(hija)
            self._registrar(hija.puntos[0], len(self.ramas) - 1)
        return any(r.viva for r in self.ramas)

    def _avanzar(self, rama: Rama, indice: int) -> None:
        p = self.p
        punta = rama.puntos[-1]
        cercano, normal = self._consultar(punta)
        hacia_sup = v.resta(cercano, punta)
        dist = v.largo(hacia_sup)
        pegada = dist <= p.distancia_adherencia

        d = v.escala(rama.direccion, p.inercia)
        d = v.suma(d, v.escala(self._aleatorio(), p.aleatoriedad))

        if pegada:
            rama.pasos_sueltos = 0
            # La luz solo empuja a lo largo de la superficie: en un muro hace
            # subir; en una superficie horizontal no empuja y la rama se extiende.
            d = v.suma(d, v.escala(v.tangente(self._luz, normal), p.luz))
            # Quita parte de la componente que se aleja o se mete en la superficie.
            d = v.resta(d, v.escala(normal, v.punto(d, normal) * p.adherencia))
            # Acerca la punta a la distancia de separación.
            exceso = (dist - p.separacion) / max(p.distancia_adherencia, v.EPS)
            d = v.resta(d, v.escala(normal, exceso * p.adherencia))
        else:
            # En el aire: cuelga por su peso y busca volver a agarrarse.
            rama.pasos_sueltos += 1
            d = v.suma(d, v.escala(v.ABAJO, p.gravedad * (0.5 + 0.5 * rama.pasos_sueltos)))
            if dist > v.EPS:
                d = v.suma(d, v.escala(v.escala(hacia_sup, 1.0 / dist), p.adherencia))

        # Se aparta de los puntos de otras ramas que tiene cerca.
        vecinos = self._rejilla.vecinos(punta, p.radio_espacio, indice)
        if vecinos:
            centro = v.escala(_sumar(vecinos), 1.0 / len(vecinos))
            lejos = v.unitario(v.tangente(v.resta(punta, centro), normal) if pegada
                               else v.resta(punta, centro))
            if lejos is not None:
                d = v.suma(d, v.escala(lejos, p.evitar))

        d = v.unitario(d) or rama.direccion
        d = v.limitar_giro(rama.direccion, d, self._giro_max, normal)

        nuevo = v.suma(punta, v.escala(d, p.longitud_paso))

        # No atravesar la superficie: si el punto queda detrás o demasiado cerca,
        # se recoloca justo encima.
        cercano2, normal2 = self._consultar(nuevo)
        pegado2 = v.suma(cercano2, v.escala(normal2, p.separacion))
        if v.punto(v.resta(nuevo, cercano2), normal2) < p.separacion:
            nuevo = pegado2
        elif pegada:
            # Rodear las aristas: si la rama iba pegada y el paso la despega
            # (por ejemplo al llegar al borde de un muro), se acerca a la
            # superficie según la adherencia en vez de salir disparada al aire.
            # Una gravedad alta deja que más ramas se descuelguen.
            agarre = p.adherencia * max(0.0, 1.0 - 0.5 * p.gravedad)
            nuevo = v.suma(v.escala(nuevo, 1.0 - agarre), v.escala(pegado2, agarre))

        direccion_real = v.unitario(v.resta(nuevo, punta))
        if direccion_real is not None:
            rama.direccion = direccion_real
        rama.puntos.append(nuevo)
        self._registrar(nuevo, indice)

        if (len(rama.puntos) >= rama.longitud_max
                or rama.pasos_sueltos > p.pasos_sueltos_max
                or (len(rama.puntos) > 6 and len(vecinos) > p.densidad_max)):
            rama.viva = False

    def _quiza_ramificar(self, rama: Rama, indice: int, nuevas: List[Rama]) -> None:
        p = self.p
        if rama.generacion >= p.generaciones_max or len(rama.puntos) < 4:
            return
        if self.rng.random() >= p.prob_rama:
            return
        longitud = int(rama.longitud_max * p.reduccion_por_generacion)
        if longitud < 3:
            return
        # La hija nace en un punto cualquiera de la madre (no en los extremos).
        i = self.rng.randint(1, len(rama.puntos) - 2)
        origen = rama.puntos[i]
        base = v.unitario(v.resta(rama.puntos[i + 1], rama.puntos[i - 1])) or rama.direccion
        _, normal = self._consultar(origen)
        signo = 1.0 if self.rng.random() < 0.5 else -1.0
        angulo = math.radians(self.rng.uniform(35.0, 80.0)) * signo
        d = v.unitario(v.tangente(v.rotar(base, normal, angulo), normal))
        if d is None:
            return
        nuevas.append(Rama(puntos=[origen], direccion=d, generacion=rama.generacion + 1,
                           longitud_max=longitud, madre=indice))

    # ------------------------------------------------------------- utilidades
    def _consultar(self, punto: Vector) -> Tuple[Vector, Vector]:
        cercano, normal = self.superficie.mas_cercano(punto)
        n = v.unitario(v.vec(normal)) or v.ARRIBA
        return v.vec(cercano), n

    def _registrar(self, punto: Vector, rama: int) -> None:
        self._rejilla.anadir(punto, rama)
        self.total_puntos += 1

    def _aleatorio(self) -> Vector:
        g = self.rng.gauss
        return v.unitario((g(0.0, 1.0), g(0.0, 1.0), g(0.0, 1.0))) or v.CERO

    # -------------------------------------------------------------- resultado
    def curvas(self) -> List[Tuple[int, List[Vector]]]:
        """Lista de (generación, puntos) de cada rama con al menos dos puntos."""
        return [(r.generacion, list(r.puntos)) for r in self.ramas if len(r.puntos) >= 2]


def _sumar(puntos: List[Vector]) -> Vector:
    x = y = z = 0.0
    for q in puntos:
        x += q[0]
        y += q[1]
        z += q[2]
    return (x, y, z)
