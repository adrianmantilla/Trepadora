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
    luz: float = 0.36
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
    densidad_max: int = 10
    # Probabilidad por paso de que brote una rama hija.
    prob_rama: float = 0.09
    # Puntos mínimos entre dos brotes de la misma rama.
    separacion_brotes: int = 6
    generaciones_max: int = 4
    # Número máximo de puntos de una rama principal.
    longitud_max: int = 220
    # Cada generación es esta fracción de larga que su madre.
    reduccion_por_generacion: float = 0.6
    # Pasos que una rama puede ir en el aire antes de dejar de crecer.
    pasos_sueltos_max: int = 14
    # Pasos que una rama secundaria puede ir por el suelo (o una superficie que
    # mira hacia la luz) antes de parar. Evita alfombras de hojas en el suelo.
    pasos_suelo_max: int = 12
    # Caída de las ramas secundarias pegadas a la pared (cortinas que cuelgan).
    # None = se calcula a partir de la gravedad (0 con la gravedad por defecto).
    caida_ramas: Optional[float] = None
    # Los brotes nacen donde hay hueco: se prueban varios nudos y se elige el
    # de menos vecinos, y el lado más vacío.
    buscar_hueco: bool = True
    # Brotes extra que salen de la base del tallo principal (varios tallos).
    brotes_basales: int = 3
    # Fuerza con la que una rama que va por el suelo se dirige a la pared más
    # cercana para trepar por ella (0 = no busca paredes).
    buscar_paredes: float = 1.0
    # Hasta qué distancia busca paredes, en pasos.
    alcance_paredes: float = 16.0
    # Probabilidad de que al pasar por el borde de arriba de una pared (o por
    # debajo de un saliente) caiga un tallo colgante.
    prob_colgar: float = 0.35
    # Largo máximo de los tallos colgantes, en puntos.
    largo_colgante: int = 45
    # Tallos que se abren en abanico cuando el tallo principal empieza a
    # trepar por una pared (contando el principal; 1 = sin abanico, porque
    # ``brotes_basales`` ya saca varios tallos de la base).
    abanico: int = 1
    # Cuánto mantienen las ramas hijas el rumbo con el que brotan (0 = nada):
    # en vez de girar enseguida hacia la luz, se abren en diagonal.
    rumbo: float = 0.35
    # Cada rama hija busca la luz con una fuerza distinta (desviación típica
    # del factor; 0 = todas igual). Rompe las franjas paralelas.
    luz_variacion: float = 0.35
    # Probabilidad por paso de que salga una ramilla: un tallo corto con
    # hojas que no se ramifica y rellena los huecos junto a su madre.
    ramillas: float = 0.0
    # Largo máximo de una ramilla, en puntos.
    largo_ramilla: int = 12
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
    pasos_suelo: int = 0
    # Rama que cae pegada a la pared (cortina), solo con caída > 0.
    cortina: bool = False
    # Tallo que nace de la base: puede reptar más por el suelo hasta otro apoyo.
    basal: bool = False
    deriva: Vector = (0.0, 0.0, 0.0)
    # Pared hacia la que se dirige por el suelo: (pie, normal), o None.
    objetivo: Optional[Tuple[Vector, Vector]] = None
    # Si alguna vez ha ido por una superficie que no es suelo.
    toco_pared: bool = False
    # Tallo que cuelga por su peso desde un borde, separándose de ``salida``.
    colgante: bool = False
    salida: Vector = (0.0, 0.0, 0.0)
    # Pasos que un tallo colgante lleva arrastrándose por una pared.
    roce: int = 0
    # Dirección con la que brotó (ver ``Parametros.rumbo``).
    rumbo: Vector = (0.0, 0.0, 0.0)
    # Multiplica la luz que busca esta rama.
    luz_factor: float = 1.0
    # Tallo corto que no se ramifica (ver ``Parametros.ramillas``).
    ramilla: bool = False
    brotes: List[int] = field(default_factory=list)
    ramillas: List[int] = field(default_factory=list)
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
        g = self.p.gravedad
        self._caida = (self.p.caida_ramas if self.p.caida_ramas is not None
                       else max(0.0, g - 0.5) * 1.3)
        # Con mucha gravedad las ramas aguantan más tiempo colgando en el aire.
        # Altura (a lo largo de la luz) mínima y máxima a la que ha llegado la planta.
        self._altura = [None, None]
        self._sueltos_max = int(self.p.pasos_sueltos_max * (1.0 + 4.0 * max(0.0, g - 0.5)))

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
        self._nuevas = nuevas
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

        # El tallo principal es más decidido: serpentea menos y busca más la luz.
        principal = rama.generacion == 0
        d = v.escala(rama.direccion, p.inercia)
        nervio = 0.55 if principal else (0.35 if rama.cortina else 1.0)
        d = v.suma(d, v.escala(rama.deriva, p.aleatoriedad * nervio))
        luz = p.luz * rama.luz_factor * (1.6 if principal else (0.0 if rama.cortina else 1.0))

        subida = None
        if rama.colgante:
            # Cuelga: sobre todo gravedad, un poco de vaivén y se separa algo
            # de la cara de la que cae. No se agarra ni busca la luz.
            rama.pasos_sueltos = 0
            # Si cae rozando una pared, se arrastra por ella: serpentea más,
            # se queda pegada y se acaba antes que un tallo que cuelga libre.
            roce = pegada and abs(v.punto(normal, self._luz)) < 0.5
            d = v.escala(rama.direccion, 0.6 * p.inercia)
            d = v.suma(d, v.escala(v.ABAJO, 0.6 + p.gravedad))
            if roce:
                rama.roce += 1
                d = v.suma(d, v.escala(rama.deriva, 0.9 * p.aleatoriedad + 0.25))
                exceso = (dist - p.separacion) / max(p.distancia_adherencia, v.EPS)
                d = v.resta(d, v.escala(normal, v.punto(d, normal) * 0.8 + exceso * 0.5))
            else:
                d = v.suma(d, v.escala(rama.deriva, 0.35 * p.aleatoriedad + 0.1))
                d = v.suma(d, v.escala(rama.salida, 0.08))
        elif pegada:
            rama.pasos_sueltos = 0
            if v.punto(normal, self._luz) > 0.75:
                rama.pasos_suelo += 1
                subida, hacia_pared = self._buscar_pared(rama, punta, normal)
                if hacia_pared is not None:
                    d = v.suma(d, v.escala(hacia_pared, p.buscar_paredes * 1.2))
            else:
                rama.pasos_suelo = 0
                rama.toco_pared = True
                rama.objetivo = None
            # La luz solo empuja a lo largo de la superficie: en un muro hace
            # subir; en una superficie horizontal no empuja y la rama se extiende.
            d = v.suma(d, v.escala(v.tangente(self._luz, normal), luz))
            fuerza = max(p.rumbo, 0.5) if rama.ramilla else p.rumbo
            if fuerza > 0.0 and not principal and not rama.cortina:
                # Mantiene el rumbo con el que brotó, cada vez menos.
                resto = 1.0 - 0.6 * len(rama.puntos) / max(rama.longitud_max, 1)
                d = v.suma(d, v.escala(v.tangente(rama.rumbo, normal), fuerza * resto))
            if rama.cortina:
                # Las cortinas caen casi rectas por la pared.
                peso = self._caida * 2.2 * min(1.0, len(rama.puntos) / 6.0)
                d = v.suma(d, v.escala(v.tangente(v.ABAJO, normal), peso))
            elif not principal and self._caida > 0.0:
                peso = self._caida * 0.35 * min(1.0, len(rama.puntos) / 25.0)
                d = v.suma(d, v.escala(v.tangente(v.ABAJO, normal), peso))
            # Quita parte de la componente que se aleja o se mete en la superficie.
            d = v.resta(d, v.escala(normal, v.punto(d, normal) * p.adherencia))
            # Acerca la punta a la distancia de separación.
            exceso = (dist - p.separacion) / max(p.distancia_adherencia, v.EPS)
            d = v.resta(d, v.escala(normal, exceso * p.adherencia))
        else:
            # En el aire: cae por su peso y busca volver a agarrarse.
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
                # Las cortinas caen juntas, casi paralelas: se apartan menos.
                d = v.suma(d, v.escala(lejos, p.evitar * (0.65 if rama.cortina else 1.0)))

        d = v.unitario(d) or rama.direccion
        d = v.limitar_giro(rama.direccion, d, self._giro_max, normal)

        nuevo = v.suma(punta, v.escala(d, p.longitud_paso))
        if rama.colgante:
            # Un tallo que cae no debe atravesar superficies finas (un suelo
            # de poco grosor): se comprueba también el punto medio del paso.
            medio = v.escala(v.suma(punta, nuevo), 0.5)
            medio2, _, _, dentro = self._sin_atravesar(punta, cercano, normal, medio)
            if dentro:
                nuevo = medio2

        nuevo, cercano2, normal2, dentro = self._sin_atravesar(punta, cercano, normal, nuevo)
        pegado2 = v.suma(cercano2, v.escala(normal2, p.separacion))
        if dentro:
            pass
        elif pegada and not rama.colgante:
            # Rodear las aristas: si la rama iba pegada y el paso la despega
            # (por ejemplo al llegar al borde de un muro), se acerca a la
            # superficie según la adherencia. Una gravedad alta deja que más
            # ramas se descuelguen.
            agarre = p.adherencia * max(0.0, 1.0 - 0.5 * p.gravedad)
            nuevo = v.suma(v.escala(nuevo, 1.0 - agarre), v.escala(pegado2, agarre))

        if subida is not None:
            # Llega al pie de una pared: sube a ella y empieza a trepar.
            pie, normal_pared = subida
            nuevo = v.suma(pie, v.escala(normal_pared, p.separacion))
            normal2 = normal_pared
            rama.pasos_suelo = 0
            rama.objetivo = None
            arriba = v.unitario(v.tangente(self._luz, normal_pared)) or v.ARRIBA
            lado = v.tangente(rama.direccion, normal_pared)
            rama.direccion = v.unitario(v.suma(arriba, v.escala(lado, 0.4))) or arriba
            if rama.generacion == 0 and not rama.toco_pared:
                self._abrir_abanico(rama, indice, nuevo, normal_pared, arriba)
        else:
            direccion_real = v.unitario(v.resta(nuevo, punta))
            if direccion_real is not None:
                rama.direccion = direccion_real
        normal_antes = rama.normales[-1]
        rama.puntos.append(nuevo)
        rama.normales.append(normal2)
        self._registrar(nuevo, indice)
        if not rama.colgante and not rama.ramilla:
            self._quiza_colgar(rama, indice, normal_antes, normal2)

        if rama.colgante:
            # Un tallo colgante para al llegar al suelo o a su largo.
            if (len(rama.puntos) + rama.roce >= rama.longitud_max
                    or (v.punto(normal2, self._luz) > 0.75
                        and v.distancia(nuevo, cercano2) < p.distancia_adherencia * 0.5)):
                rama.viva = False
            return
        # El tallo principal es el tronco de la planta: no lo ahogan los brotes
        # que le salen alrededor de la base.
        tolerancia = 2.0 if principal else (1.3 if rama.cortina else 1.0)
        if (len(rama.puntos) >= rama.longitud_max
                or rama.pasos_sueltos > self._sueltos_max
                or (not principal and rama.pasos_suelo > p.pasos_suelo_max)
                or (principal and rama.toco_pared and rama.pasos_suelo > 3 * p.pasos_suelo_max)
                or (len(rama.puntos) > 6 and len(vecinos) > p.densidad_max * tolerancia)):
            rama.viva = False

    def _quiza_brotar(self, rama: Rama, indice: int, nuevas: List[Rama]) -> None:
        p = self.p
        n = len(rama.puntos)
        if rama.colgante or rama.ramilla:
            return
        self._quiza_ramilla(rama, indice, nuevas)
        if rama.generacion >= p.generaciones_max or n < 4:
            return
        if rama.cortina and self.rng.random() < 0.8:
            return
        basal = (rama.generacion == 0 and len(rama.brotes) < p.brotes_basales and n < 40)
        if not basal and self.rng.random() >= p.prob_rama:
            return
        if basal and self.rng.random() >= 0.25:
            return
        factor = 0.85 if basal else p.reduccion_por_generacion
        longitud = int(rama.longitud_max * factor * self.rng.uniform(0.6, 1.25))
        if longitud < 4:
            return
        # Candidatos: nudos recientes y nudos de cualquier punto de la rama, para
        # que la parte vieja (abajo) también se llene.
        candidatos = []
        for _ in range(4 if p.buscar_hueco else 1):
            if basal:
                i = self.rng.randint(1, n - 2)
            elif self.rng.random() < 0.5:
                i = self.rng.randint(max(1, n - 30), n - 2)
            else:
                i = self.rng.randint(1, n - 2)
            if any(abs(i - b) < p.separacion_brotes for b in rama.brotes):
                continue
            candidatos.append(i)
        if not candidatos:
            return
        radio = p.radio_espacio * 2.5
        if p.buscar_hueco and len(candidatos) > 1:
            candidatos.sort(key=lambda i: len(self._rejilla.vecinos(rama.puntos[i], radio, ())))
        i = candidatos[0]
        rama.brotes.append(i)
        origen = rama.puntos[i]
        normal = rama.normales[i]
        base = v.unitario(v.resta(rama.puntos[i + 1], rama.puntos[i - 1])) or rama.direccion
        angulo = math.radians(self.rng.uniform(30.0 if basal else 40.0, 85.0))
        opciones = []
        for signo in (1.0, -1.0):
            d = v.unitario(v.tangente(v.rotar(base, normal, angulo * signo), normal))
            if d is None:
                continue
            sonda = v.suma(origen, v.escala(d, radio))
            opciones.append((len(self._rejilla.vecinos(sonda, radio, ())), self.rng.random(), d))
        if not opciones:
            return
        if p.buscar_hueco:
            opciones.sort()
            d = opciones[0][2]
        else:
            d = self.rng.choice(opciones)[2]
        # Las cortinas brotan sobre todo de lo alto de la planta.
        cortina = False
        if self._caida > 0.0 and not basal and not rama.cortina:
            bajo, alto = self._altura
            relativa = (v.punto(origen, self._luz) - bajo) / max(alto - bajo, v.EPS)
            cortina = self.rng.random() < 0.15 + 0.75 * relativa
        if cortina:
            longitud = int(longitud * 1.3)
            abajo = v.unitario(v.tangente(v.ABAJO, normal))
            if abajo is not None:
                d = v.unitario(v.suma(d, abajo)) or d
        nuevas.append(Rama(puntos=[origen], normales=[normal], direccion=d,
                           generacion=rama.generacion + 1, longitud_max=longitud,
                           madre=indice, indice_en_madre=i, cortina=cortina,
                           basal=basal, rumbo=d, luz_factor=self._factor_luz()))

    def _factor_luz(self) -> float:
        if self.p.luz_variacion <= 0.0:
            return 1.0
        return max(0.15, self.rng.gauss(1.0, self.p.luz_variacion))

    def _quiza_ramilla(self, rama: Rama, indice: int, nuevas: List[Rama]) -> None:
        """De vez en cuando sale una ramilla corta hacia un lado."""
        p = self.p
        n = len(rama.puntos)
        if p.ramillas <= 0.0 or n < 6 or self.rng.random() >= p.ramillas:
            return
        i = self.rng.randint(max(1, n - 25), n - 3)
        if any(abs(i - b) < 3 for b in rama.ramillas + rama.brotes):
            return
        origen = rama.puntos[i]
        normal = rama.normales[i]
        base = v.unitario(v.resta(rama.puntos[i + 1], rama.puntos[i - 1])) or rama.direccion
        signo = 1.0 if self.rng.random() < 0.5 else -1.0
        angulo = math.radians(self.rng.uniform(35.0, 80.0)) * signo
        d = v.unitario(v.tangente(v.rotar(base, normal, angulo), normal))
        if d is None:
            return
        largo = self.rng.randint(max(4, p.largo_ramilla // 2), max(4, p.largo_ramilla))
        rama.ramillas.append(i)
        nuevas.append(Rama(puntos=[origen], normales=[normal], direccion=d,
                           generacion=rama.generacion + 1, longitud_max=largo,
                           madre=indice, indice_en_madre=i, ramilla=True, rumbo=d,
                           luz_factor=0.45, toco_pared=rama.toco_pared))

    def _abrir_abanico(self, rama: Rama, indice: int, pie: Vector, normal: Vector,
                       arriba: Vector) -> None:
        """Al pie de la pared salen varios tallos largos que se separan en abanico."""
        p = self.p
        extra = max(0, p.abanico - 1)
        for k in range(extra):
            # Ángulos repartidos a ambos lados de la vertical, con algo de azar.
            lado = -1.0 if k % 2 == 0 else 1.0
            angulo = math.radians(lado * (25.0 + 30.0 * self.rng.random() + 10.0 * (k // 2)))
            d = v.unitario(v.tangente(v.rotar(arriba, normal, angulo), normal))
            if d is None:
                continue
            largo = int(rama.longitud_max * (0.6 + 0.3 * self.rng.random()))
            # Se añaden como brotes del punto que se acaba de crear.
            self._nuevas.append(Rama(puntos=[pie], normales=[normal], direccion=d,
                                     generacion=1, longitud_max=largo, madre=indice,
                                     indice_en_madre=len(rama.puntos), toco_pared=True))

    # ---------------------------------------------------------- colgantes
    def _quiza_colgar(self, rama: Rama, indice: int, antes: Vector, ahora: Vector) -> None:
        """Al rebasar el borde de arriba de una pared, o bajo un saliente, deja caer un tallo."""
        p = self.p
        if p.prob_colgar <= 0.0 or p.largo_colgante < 4:
            return
        arriba_antes = v.punto(antes, self._luz)
        arriba_ahora = v.punto(ahora, self._luz)
        if abs(arriba_antes) < 0.5 and arriba_ahora > 0.75:
            # Borde superior: pasa de la cara de una pared a su parte de arriba.
            probabilidad, salida = p.prob_colgar, antes
        elif arriba_ahora < -0.75:
            # Por debajo de un saliente (dintel, cornisa): de vez en cuando.
            probabilidad, salida = p.prob_colgar * 0.25, v.CERO
        else:
            return
        i = len(rama.puntos) - 2
        if i < 1 or self.rng.random() >= probabilidad:
            return
        if any(abs(i - b) < p.separacion_brotes for b in rama.brotes):
            return
        rama.brotes.append(i)
        # Muchas cortas y pocas largas: un reparto parejo deja una fila de
        # hilos del mismo largo que se ve artificial.
        largo = int(p.largo_colgante * (0.2 + 0.8 * self.rng.random() ** 2))
        lado = v.escala(v.tangente(self._aleatorio(), v.ARRIBA), 0.2)
        direccion = v.unitario(v.suma(v.suma(v.ABAJO, v.escala(salida, 0.4)), lado)) or v.ABAJO
        self._nuevas.append(Rama(puntos=[rama.puntos[i]], normales=[rama.normales[i]],
                                 direccion=direccion, generacion=rama.generacion + 1,
                                 longitud_max=largo, madre=indice, indice_en_madre=i,
                                 colgante=True, salida=salida, toco_pared=True))

    # ------------------------------------------------------------ paredes
    def _buscar_pared(self, rama: Rama, punta: Vector, normal: Vector):
        """Para una rama que va por el suelo, busca una pared cercana.

        Devuelve (subida, hacia_pared): ``subida`` es (pie, normal) si la pared
        está a menos de un paso y la rama debe subir ya; ``hacia_pared`` es la
        dirección (a lo largo del suelo) hacia la pared, o None si no hay.

        Solo hace falta ``mas_cercano``: se consulta la superficie desde puntos
        elevados sobre el suelo. Si desde uno de ellos lo más cercano es una
        cara vertical y no el suelo, ahí hay una pared.
        """
        p = self.p
        if p.buscar_paredes <= 0.0:
            return None, None
        # Una rama que bajó por una pared no vuelve a ella enseguida (haría una U).
        if rama.toco_pared and rama.pasos_suelo < 6:
            return None, None
        paso = p.longitud_paso
        # Cerca: una consulta en cada paso, justo encima de la punta.
        cerca = self._pared_desde(punta, normal, punta, 3.0 * paso)
        if cerca is not None:
            rama.objetivo = cerca
        elif rama.objetivo is None or rama.pasos_suelo % 4 == 1:
            # Lejos: un anillo de consultas cada pocos pasos.
            rama.objetivo = self._pared_en_anillo(punta, normal)
        if rama.objetivo is None:
            return None, None
        pie, normal_pared = rama.objetivo
        hacia = v.tangente(v.resta(pie, punta), normal)
        distancia = v.largo(hacia)
        if (distancia <= 1.2 * paso
                and v.punto(rama.direccion, normal_pared) < 0.3):
            return rama.objetivo, None
        return None, v.unitario(hacia)

    def _pared_en_anillo(self, punta: Vector, normal: Vector):
        p = self.p
        paso = p.longitud_paso
        alcance = p.alcance_paredes * paso
        e1 = v.perpendicular(normal)
        e2 = v.cruz(normal, e1)
        mejor = None
        for fraccion in (0.25, 0.55, 1.0):
            radio = alcance * fraccion
            altura = max(3.0 * paso, radio * 0.45)
            for k in range(8):
                a = 2.0 * math.pi * (k + 0.5 * fraccion) / 8.0
                dh = v.suma(v.escala(e1, math.cos(a) * radio), v.escala(e2, math.sin(a) * radio))
                candidato = self._pared_desde(v.suma(punta, dh), normal, punta, altura)
                if candidato is None:
                    continue
                d = v.largo(v.tangente(v.resta(candidato[0], punta), normal))
                if d <= alcance and (mejor is None or d < mejor[0]):
                    mejor = (d, candidato)
        return None if mejor is None else mejor[1]

    def _pared_desde(self, base: Vector, normal: Vector, punta: Vector, altura: float):
        """Consulta desde ``base`` elevado ``altura``; devuelve (pie, normal) de una pared o None."""
        paso = self.p.longitud_paso
        sonda = v.suma(base, v.escala(normal, altura))
        cercano, n = self._consultar(sonda)
        # Tiene que ser una cara casi vertical, vista desde fuera.
        if abs(v.punto(n, normal)) > 0.5 or v.punto(v.resta(sonda, cercano), n) <= 0.0:
            return None
        # Pie de la pared, un poco por encima del suelo de la punta.
        alto = v.punto(v.resta(cercano, punta), normal)
        pie = v.suma(cercano, v.escala(normal, 0.8 * paso - alto))
        # Comprueba que la pared llega hasta abajo (no es algo que flota).
        c2, n2 = self._consultar(v.suma(pie, v.escala(n, 0.4 * paso)))
        if v.punto(n2, n) < 0.8 or v.distancia(c2, pie) > 0.5 * paso:
            return None
        return c2, n2

    # ------------------------------------------------------------- utilidades
    def _sin_atravesar(self, punta: Vector, cercano: Vector, normal: Vector, q: Vector):
        """Si ``q`` queda dentro o al otro lado de una superficie, lo saca por el lado bueno.

        Devuelve (punto, cercano, normal, corregido). En objetos cerrados y
        finos (un suelo hecho con un cubo plano, un muro delgado) un paso puede
        caer dentro, o atravesarlo entero, y la cara más cercana ser la de
        detrás. Entonces se busca a lo largo del paso la cara por la que entró.
        """
        sep = self.p.separacion
        c, n = self._consultar(q)
        delante = v.punto(v.resta(q, c), n) >= sep
        punta_detras = v.punto(v.resta(punta, c), n) < -sep
        if delante and not punta_detras:
            return q, c, n, False
        if not delante and not punta_detras:
            return v.suma(c, v.escala(n, sep)), c, n, True
        # La punta está al otro lado de esa cara: el paso ha cruzado un objeto.
        paso = v.resta(q, punta)
        for k in range(1, 10):
            m = v.suma(punta, v.escala(paso, k / 10.0))
            cm, nm = self._consultar(m)
            if v.punto(v.resta(m, cm), nm) < sep:
                if v.punto(v.resta(punta, cm), nm) >= -sep:
                    return v.suma(cm, v.escala(nm, sep)), cm, nm, True
                break
        if delante:
            # No se encontró por dónde entró (rodear una arista, por ejemplo).
            return q, c, n, False
        # Último recurso: se queda sobre la superficie de la punta.
        alto = v.punto(v.resta(q, cercano), normal)
        q2 = v.suma(q, v.escala(normal, sep - alto))
        return q2, v.resta(q2, v.escala(normal, sep)), normal, True

    def _consultar(self, punto: Vector) -> Tuple[Vector, Vector]:
        cercano, normal = self.superficie.mas_cercano(punto)
        n = v.unitario(v.vec(normal)) or v.ARRIBA
        return v.vec(cercano), n

    def _registrar(self, punto: Vector, rama: int) -> None:
        self._rejilla.anadir(punto, rama)
        h = v.punto(punto, self._luz)
        if self._altura[0] is None or h < self._altura[0]:
            self._altura[0] = h
        if self._altura[1] is None or h > self._altura[1]:
            self._altura[1] = h
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
