"""Algoritmo de crecimiento de Trepadora.

Este módulo no depende de Maya ni de NumPy: solo necesita un objeto
"superficie" con un método ``mas_cercano(punto) -> (punto_cercano, normal)``.
Así se puede probar fuera de Maya y reutilizar con cualquier geometría.

Idea general
------------
Cada rama es una lista de puntos. En cada paso, la punta de cada rama viva
avanza una distancia fija. La dirección del avance mezcla varias fuerzas:

* inercia: seguir en la dirección que traía;
* deriva: una desviación que cambia poco a poco, para curvas largas y suaves;
* luz: tendencia a subir por las paredes (hacia ``direccion_luz``);
* adherencia: si la rama está cerca de la superficie, se pega y la sigue;
* gravedad: si la rama pierde el apoyo, cuelga y busca volver a agarrarse;
* espacio: las ramas se apartan de las zonas ya ocupadas, para repartirse.

Cada paso una rama solo puede girar un ángulo máximo, lo que evita bucles.
Las ramas hijas brotan a lo largo de la madre, separadas entre sí.
Al terminar, ``grosores()`` calcula el radio de cada punto: el tallo es más
grueso donde sostiene más planta y se afina hacia las puntas.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from . import vectores as v

Vector = Tuple[float, float, float]


@dataclass
class Parametros:
    """Ajustes del crecimiento. Las distancias van en unidades de la escena."""

    semilla: int = 1
    pasos: int = 260
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
    # Cuánto serpentea la rama.
    aleatoriedad: float = 0.45
    # Lo rápido que cambia la deriva: bajo = curvas largas, alto = nervioso.
    cambio_deriva: float = 0.25
    inercia: float = 1.0
    # Giro máximo por paso, en grados. Evita bucles y quiebros bruscos.
    giro_max: float = 16.0
    # Radio (en unidades) en el que una rama nota a las demás.
    radio_espacio: float = 2.0
    # Fuerza con la que se aparta de las zonas ocupadas.
    evitar: float = 0.9
    # Si hay más puntos ajenos que esto dentro del radio, la rama deja de crecer.
    densidad_max: int = 8
    # Probabilidad por paso de que brote una rama hija.
    prob_rama: float = 0.07
    # Puntos mínimos entre dos brotes de la misma rama.
    separacion_brotes: int = 6
    generaciones_max: int = 4
    # Número máximo de puntos de una rama principal.
    longitud_max: int = 220
    # Cada generación es esta fracción de larga que su madre.
    reduccion_por_generacion: float = 0.6
    # Pasos que una rama puede ir en el aire antes de dejar de crecer.
    pasos_sueltos_max: int = 14
    # Tope de seguridad para no colgar Maya.
    limite_puntos: int = 60000


@dataclass
class Rama:
    puntos: List[Vector]
    normales: List[Vector]
    direccion: Vector
    generacion: int
    longitud_max: int
    madre: Optional[int] = None
    # Índice del punto de la madre del que brota.
    indice_en_madre: int = 0
    viva: bool = True
    pasos_sueltos: int = 0
    deriva: Vector = (0.0, 0.0, 0.0)
    brotes: List[int] = field(default_factory=list)
    hijas: List[int] = field(default_factory=list)


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

    def vecinos(self, p: Vector, radio: float, excluir: Tuple[int, ...]) -> List[Vector]:
        cx, cy, cz = self._clave(p)
        r2 = radio * radio
        encontrados = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for q, rama in self._celdas.get((cx + dx, cy + dy, cz + dz), ()):
                        if rama in excluir:
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

        rama = Rama(puntos=[inicio], normales=[normal], direccion=d, generacion=0,
                    longitud_max=self.p.longitud_max)
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
            self._quiza_brotar(rama, indice, nuevas)
        for hija in nuevas:
            self.ramas.append(hija)
            indice = len(self.ramas) - 1
            self.ramas[hija.madre].hijas.append(indice)
            self._registrar(hija.puntos[0], indice)
        return any(r.viva for r in self.ramas)

    def _avanzar(self, rama: Rama, indice: int) -> None:
        p = self.p
        punta = rama.puntos[-1]
        cercano, normal = self._consultar(punta)
        hacia_sup = v.resta(cercano, punta)
        dist = v.largo(hacia_sup)
        pegada = dist <= p.distancia_adherencia

        # La deriva cambia poco a poco: da curvas largas en vez de temblores.
        nueva = v.suma(v.escala(rama.deriva, 1.0 - p.cambio_deriva),
                       v.escala(self._aleatorio(), p.cambio_deriva * 2.0))
        if pegada:
            nueva = v.tangente(nueva, normal)
        rama.deriva = v.unitario(nueva) or v.CERO

        d = v.escala(rama.direccion, p.inercia)
        d = v.suma(d, v.escala(rama.deriva, p.aleatoriedad))

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

        # Se aparta de los puntos de otras ramas que tiene cerca (salvo su madre,
        # de la que acaba de brotar).
        excluir = (indice,) if rama.madre is None else (indice, rama.madre)
        vecinos = self._rejilla.vecinos(punta, p.radio_espacio, excluir)
        if vecinos:
            centro = v.escala(_sumar(vecinos), 1.0 / len(vecinos))
            lejos = v.unitario(v.tangente(v.resta(punta, centro), normal) if pegada
                               else v.resta(punta, centro))
            if lejos is not None:
                d = v.suma(d, v.escala(lejos, p.evitar))

        d = v.unitario(d) or rama.direccion
        d = v.limitar_giro(rama.direccion, d, self._giro_max, normal)

        nuevo = v.suma(punta, v.escala(d, p.longitud_paso))

        cercano2, normal2 = self._consultar(nuevo)
        pegado2 = v.suma(cercano2, v.escala(normal2, p.separacion))
        if v.punto(v.resta(nuevo, cercano2), normal2) < p.separacion:
            # No atravesar la superficie.
            nuevo = pegado2
        elif pegada:
            # Rodear las aristas: si la rama iba pegada y el paso la despega
            # (por ejemplo al llegar al borde de un muro), se acerca a la
            # superficie según la adherencia. Una gravedad alta deja que más
            # ramas se descuelguen.
            agarre = p.adherencia * max(0.0, 1.0 - 0.5 * p.gravedad)
            nuevo = v.suma(v.escala(nuevo, 1.0 - agarre), v.escala(pegado2, agarre))

        direccion_real = v.unitario(v.resta(nuevo, punta))
        if direccion_real is not None:
            rama.direccion = direccion_real
        rama.puntos.append(nuevo)
        rama.normales.append(normal2)
        self._registrar(nuevo, indice)

        if (len(rama.puntos) >= rama.longitud_max
                or rama.pasos_sueltos > p.pasos_sueltos_max
                or (len(rama.puntos) > 6 and len(vecinos) > p.densidad_max)):
            rama.viva = False

    def _quiza_brotar(self, rama: Rama, indice: int, nuevas: List[Rama]) -> None:
        p = self.p
        n = len(rama.puntos)
        if rama.generacion >= p.generaciones_max or n < 4:
            return
        if self.rng.random() >= p.prob_rama:
            return
        longitud = int(rama.longitud_max * p.reduccion_por_generacion)
        if longitud < 4:
            return
        # El brote sale de un nudo reciente de la rama, separado de otros brotes.
        i = self.rng.randint(max(1, n - 30), n - 2)
        if any(abs(i - b) < p.separacion_brotes for b in rama.brotes):
            return
        rama.brotes.append(i)
        origen = rama.puntos[i]
        normal = rama.normales[i]
        base = v.unitario(v.resta(rama.puntos[i + 1], rama.puntos[i - 1])) or rama.direccion
        signo = 1.0 if self.rng.random() < 0.5 else -1.0
        angulo = math.radians(self.rng.uniform(40.0, 85.0)) * signo
        d = v.unitario(v.tangente(v.rotar(base, normal, angulo), normal))
        if d is None:
            return
        nuevas.append(Rama(puntos=[origen], normales=[normal], direccion=d,
                           generacion=rama.generacion + 1, longitud_max=longitud,
                           madre=indice, indice_en_madre=i))

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

    def grosores(self, radio_base: float, radio_punta: float) -> List[List[float]]:
        """Radio de cada punto de cada rama.

        Cada punto es tan grueso como la cantidad de planta que sostiene: lo
        que queda de su rama más todas las ramas que brotan por encima. Así la
        base del tallo principal es la más gruesa y las puntas, las más finas.
        """
        total: Dict[int, float] = {}

        def carga_total(i: int) -> float:
            if i not in total:
                r = self.ramas[i]
                total[i] = len(r.puntos) + sum(carga_total(h) for h in r.hijas)
            return total[i]

        cargas: List[List[float]] = []
        for i, rama in enumerate(self.ramas):
            n = len(rama.puntos)
            extra = [0.0] * (n + 1)
            for h in rama.hijas:
                extra[min(self.ramas[h].indice_en_madre, n - 1)] += carga_total(h)
            # Suma acumulada desde la punta hacia la base.
            acumulado = 0.0
            fila = [0.0] * n
            for k in range(n - 1, -1, -1):
                acumulado += 1.0 + extra[k]
                fila[k] = acumulado
            cargas.append(fila)

        maximo = max((f[0] for f in cargas if f), default=1.0)
        radios = []
        for fila in cargas:
            radios.append([radio_punta + (radio_base - radio_punta) * math.sqrt(c / maximo)
                           for c in fila])
        return radios


def _sumar(puntos: List[Vector]) -> Vector:
    x = y = z = 0.0
    for q in puntos:
        x += q[0]
        y += q[1]
        z += q[2]
    return (x, y, z)
