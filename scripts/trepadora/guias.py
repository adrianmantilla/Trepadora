"""Curvas guía: el estudiante dibuja una curva y la planta crece a lo largo de ella (sin Maya).

Cada guía es una lista de puntos en orden, del principio al final de la curva.
Cerca de una guía, una rama nota dos tirones: seguir la dirección de la curva
(del principio hacia el final) y acercarse a ella si se ha separado. Lejos de
la guía los dos se apagan y la rama crece como siempre.
"""

import math
from typing import Dict, List, Optional, Sequence, Tuple

from . import vectores as v

Vector = Tuple[float, float, float]


class Guias:
    """Una o varias guías, con una rejilla para encontrar rápido el punto más cercano."""

    def __init__(self, guias: Sequence[Sequence[Vector]], alcance: float):
        self.alcance = max(float(alcance), v.EPS)
        self.guias: List[List[Vector]] = [[v.vec(p) for p in g] for g in guias if len(g) >= 2]
        self._celda = self.alcance
        self._rejilla: Dict[Tuple[int, int, int], List[Tuple[int, int]]] = {}
        for i, guia in enumerate(self.guias):
            for k in range(len(guia) - 1):
                # Cada tramo, en las celdas de sus extremos y de su centro.
                a, b = guia[k], guia[k + 1]
                for p in (a, b, v.escala(v.suma(a, b), 0.5)):
                    self._rejilla.setdefault(self._clave(p), []).append((i, k))

    def __bool__(self):
        return bool(self.guias)

    def _clave(self, p: Vector) -> Tuple[int, int, int]:
        c = self._celda
        return (int(math.floor(p[0] / c)), int(math.floor(p[1] / c)), int(math.floor(p[2] / c)))

    def inicios(self) -> List[Tuple[Vector, Vector]]:
        """(principio, dirección de salida) de cada guía: donde nace una planta si no hay orígenes.

        La dirección mira unos puntos más allá, para que un primer tramo muy
        corto o torcido no la desvíe.
        """
        resultado = []
        for guia in self.guias:
            mas_alla = guia[min(3, len(guia) - 1)]
            resultado.append((guia[0], v.unitario(v.resta(mas_alla, guia[0])) or v.ARRIBA))
        return resultado

    def mas_cercano(self, p: Vector) -> Optional[Tuple[Vector, Vector, float, bool]]:
        """(punto más cercano, dirección de la guía allí, distancia, pasado el final).

        «Pasado el final» es True si lo más cercano es el último punto de una
        guía: la rama ya la ha recorrido entera. Sin guías, None.
        """
        cx, cy, cz = self._clave(p)
        tramos = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    tramos.update(self._rejilla.get((cx + dx, cy + dy, cz + dz), ()))
        if not tramos:
            # Lejos de todas: se miran todos los tramos (pasa pocas veces).
            tramos = {(i, k) for i, g in enumerate(self.guias) for k in range(len(g) - 1)}
        mejor = None
        for i, k in sorted(tramos):
            a, b = self.guias[i][k], self.guias[i][k + 1]
            ab = v.resta(b, a)
            l2 = v.punto(ab, ab)
            t = 0.0 if l2 < v.EPS else max(0.0, min(1.0, v.punto(v.resta(p, a), ab) / l2))
            q = v.suma(a, v.escala(ab, t))
            d = v.distancia(p, q)
            if mejor is None or d < mejor[2]:
                final = k == len(self.guias[i]) - 2 and t >= 1.0
                mejor = (q, v.unitario(ab) or v.ARRIBA, d, final)
        return mejor

    def tiron(self, p: Vector) -> Optional[Tuple[Vector, float]]:
        """Hacia dónde tira la guía en ``p`` y con qué fuerza (0 a 1), o None.

        La dirección mezcla la de la curva con la de acercarse a ella: pegada
        a la guía, la sigue; a un alcance de distancia, va casi tanto hacia
        ella como a lo largo. La fuerza baja con la distancia. Pasado el final
        de la guía, solo empuja un poco hacia delante y se apaga en un alcance:
        la rama sigue creciendo a su aire en vez de volver atrás.
        """
        cercano = self.mas_cercano(p)
        if cercano is None:
            return None
        q, rumbo, d, final = cercano
        if final:
            fuerza = max(0.0, 1.0 - d / self.alcance)
            return (rumbo, fuerza) if fuerza > 0.0 else None
        acercarse = v.escala(v.resta(q, p), 1.0 / self.alcance)
        direccion = v.unitario(v.suma(rumbo, acercarse))
        if direccion is None:
            return None
        fuerza = 1.0 / (1.0 + (d / (2.0 * self.alcance)) ** 2)
        return direccion, fuerza
