"""Algoritmo de crecimiento de Trepadora.

Este modulo no depende de Maya: solo necesita un objeto "superficie" con un
metodo ``mas_cercano(punto) -> (punto_cercano, normal)``. Asi se puede probar
fuera de Maya y reutilizar con cualquier tipo de geometria.

Idea general
------------
Cada rama es una lista de puntos. En cada paso, la punta de cada rama viva
avanza una distancia fija. La direccion del avance mezcla varias fuerzas:

* inercia: seguir en la direccion que traia;
* aleatoriedad: pequenas desviaciones para que no crezca recta;
* luz: tendencia a ir hacia una direccion (por defecto, hacia arriba);
* adherencia: si la rama esta cerca de la superficie, se pega y la sigue;
* gravedad: si la rama pierde el apoyo, cuelga hacia abajo.

De vez en cuando una rama genera ramas hijas, que son mas cortas.
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import numpy as np

_EPS = 1e-9
_ABAJO = np.array([0.0, -1.0, 0.0])


@dataclass
class Parametros:
    """Ajustes del crecimiento. Las distancias van en unidades de la escena."""

    semilla: int = 1
    pasos: int = 200
    longitud_paso: float = 1.0
    # Hasta que distancia de la superficie se considera que la rama esta pegada.
    distancia_adherencia: float = 3.0
    # Separacion entre el tallo y la superficie, para que no la atraviese.
    separacion: float = 0.05
    # 0 = ignora la superficie, 1 = la sigue al maximo.
    adherencia: float = 0.8
    gravedad: float = 0.5
    luz: float = 0.6
    direccion_luz: Tuple[float, float, float] = (0.0, 1.0, 0.0)
    aleatoriedad: float = 0.35
    inercia: float = 1.0
    # Probabilidad por paso de que salga una rama hija.
    prob_rama: float = 0.04
    generaciones_max: int = 3
    # Numero maximo de puntos de una rama principal.
    longitud_max: int = 150
    # Cada generacion es esta fraccion de larga que su madre.
    reduccion_por_generacion: float = 0.6
    # Pasos que una rama puede ir en el aire antes de dejar de crecer.
    pasos_sueltos_max: int = 12
    # Tope de seguridad para no colgar Maya.
    limite_puntos: int = 50000


@dataclass
class Rama:
    puntos: List[np.ndarray]
    direccion: np.ndarray
    generacion: int
    longitud_max: int
    madre: Optional[int] = None
    viva: bool = True
    pasos_sueltos: int = 0

    def como_array(self) -> np.ndarray:
        return np.array(self.puntos)


def _unitario(v: np.ndarray) -> Optional[np.ndarray]:
    n = float(np.linalg.norm(v))
    if n < _EPS:
        return None
    return v / n


def _tangente(v: np.ndarray, normal: np.ndarray) -> np.ndarray:
    """Proyecta ``v`` sobre el plano perpendicular a ``normal``."""
    return v - normal * float(np.dot(v, normal))


def _perpendicular(normal: np.ndarray) -> np.ndarray:
    eje = np.array([1.0, 0.0, 0.0]) if abs(normal[0]) < 0.9 else np.array([0.0, 0.0, 1.0])
    return _unitario(np.cross(normal, eje))


def _rotar(v: np.ndarray, eje: np.ndarray, angulo: float) -> np.ndarray:
    """Rota ``v`` alrededor de ``eje`` (unitario) con la formula de Rodrigues."""
    c, s = np.cos(angulo), np.sin(angulo)
    return v * c + np.cross(eje, v) * s + eje * float(np.dot(eje, v)) * (1.0 - c)


class Crecimiento:
    """Hace crecer una o varias plantas sobre una superficie."""

    def __init__(self, superficie, parametros: Optional[Parametros] = None):
        self.superficie = superficie
        self.p = parametros or Parametros()
        self.rng = np.random.default_rng(self.p.semilla)
        self.ramas: List[Rama] = []
        self.total_puntos = 0
        self.limite_alcanzado = False
        self._luz = _unitario(np.asarray(self.p.direccion_luz, dtype=float))
        if self._luz is None:
            self._luz = np.array([0.0, 1.0, 0.0])

    # ------------------------------------------------------------------ origen
    def anadir_origen(self, punto, direccion=None) -> Rama:
        """Coloca el nacimiento de una planta en el punto de la superficie mas cercano."""
        punto = np.asarray(punto, dtype=float)
        cercano, normal = self.superficie.mas_cercano(punto)
        inicio = cercano + normal * self.p.separacion

        d = None
        if direccion is not None:
            d = _unitario(_tangente(np.asarray(direccion, dtype=float), normal))
        if d is None:
            d = _unitario(_tangente(self._luz, normal))
        if d is None:
            d = _perpendicular(normal)

        rama = Rama(puntos=[inicio], direccion=d, generacion=0, longitud_max=self.p.longitud_max)
        self.ramas.append(rama)
        self.total_puntos += 1
        return rama

    # ----------------------------------------------------------------- crecer
    def crecer(self, pasos: Optional[int] = None,
               al_progresar: Optional[Callable[[int, int], bool]] = None) -> int:
        """Ejecuta varios pasos. Devuelve cuantos se hicieron.

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
            self._avanzar(rama, indice, nuevas)
        self.ramas.extend(nuevas)
        return any(r.viva for r in self.ramas)

    def _avanzar(self, rama: Rama, indice: int, nuevas: List[Rama]) -> None:
        p = self.p
        punta = rama.puntos[-1]
        cercano, normal = self.superficie.mas_cercano(punta)
        hacia_sup = cercano - punta
        distancia = float(np.linalg.norm(hacia_sup))
        pegada = distancia <= p.distancia_adherencia

        d = rama.direccion * p.inercia
        d = d + self._aleatorio() * p.aleatoriedad

        if pegada:
            rama.pasos_sueltos = 0
            d = d + _tangente(self._luz, normal) * p.luz
            # Quita parte de la componente que se aleja de la superficie.
            d = d - normal * float(np.dot(d, normal)) * p.adherencia
            # Acerca la punta a la distancia de separacion.
            exceso = (distancia - p.separacion) / max(p.distancia_adherencia, _EPS)
            d = d - normal * exceso * p.adherencia
        else:
            rama.pasos_sueltos += 1
            d = d + self._luz * p.luz * 0.3
            d = d + _ABAJO * p.gravedad * rama.pasos_sueltos * 0.5
            if distancia > _EPS:
                d = d + (hacia_sup / distancia) * p.adherencia * 0.3

        d = _unitario(d)
        if d is None:
            d = rama.direccion

        nuevo = punta + d * p.longitud_paso

        # No atravesar la superficie: si el punto queda detras o demasiado cerca,
        # se recoloca justo encima.
        cercano2, normal2 = self.superficie.mas_cercano(nuevo)
        if float(np.dot(nuevo - cercano2, normal2)) < p.separacion:
            nuevo = cercano2 + normal2 * p.separacion

        direccion_real = _unitario(nuevo - punta)
        if direccion_real is not None:
            rama.direccion = direccion_real
        rama.puntos.append(nuevo)
        self.total_puntos += 1

        if len(rama.puntos) >= rama.longitud_max or rama.pasos_sueltos > p.pasos_sueltos_max:
            rama.viva = False

        self._quiza_ramificar(rama, indice, normal2, nuevas)

    def _quiza_ramificar(self, rama: Rama, indice: int, normal: np.ndarray,
                         nuevas: List[Rama]) -> None:
        p = self.p
        if rama.generacion >= p.generaciones_max or len(rama.puntos) < 4:
            return
        if self.rng.random() >= p.prob_rama:
            return
        longitud = int(rama.longitud_max * p.reduccion_por_generacion)
        if longitud < 3:
            return
        signo = 1.0 if self.rng.random() < 0.5 else -1.0
        angulo = np.radians(self.rng.uniform(30.0, 70.0)) * signo
        d = _unitario(_rotar(rama.direccion, normal, angulo))
        if d is None:
            return
        hija = Rama(puntos=[rama.puntos[-1].copy()], direccion=d,
                    generacion=rama.generacion + 1, longitud_max=longitud, madre=indice)
        nuevas.append(hija)

    def _aleatorio(self) -> np.ndarray:
        v = self.rng.normal(size=3)
        u = _unitario(v)
        return u if u is not None else np.zeros(3)

    # -------------------------------------------------------------- resultado
    def curvas(self) -> List[Tuple[int, np.ndarray]]:
        """Lista de (generacion, puntos) de cada rama con al menos dos puntos."""
        return [(r.generacion, r.como_array()) for r in self.ramas if len(r.puntos) >= 2]
