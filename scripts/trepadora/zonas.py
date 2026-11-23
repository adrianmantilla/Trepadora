"""Zonas prohibidas: cajas por las que la planta no crece (sin Maya).

El estudiante pone una caja (o cualquier malla) delante de una ventana o una
puerta y la marca como zona prohibida. Para la planta, cada zona es la caja
que envuelve esa malla, con su giro y su escala: una caja orientada.

* ``dentro(p)``: si un punto cae en alguna zona. Una rama que entra en una
  zona deja de crecer y una hoja que caería dentro no se pone.
* ``empuje(p, alcance)``: hacia dónde apartarse de la zona más cercana y con
  qué fuerza (0 a ``alcance`` de distancia o más, 1 al tocarla). Las ramas lo
  notan unos pasos antes de llegar y la rodean.
"""

from typing import List, Optional, Sequence, Tuple

from . import vectores as v

Vector = Tuple[float, float, float]


class Zona:
    """Caja orientada: centro, tres ejes unitarios y la mitad de cada medida."""

    def __init__(self, centro: Vector, ejes: Sequence[Vector], medias: Sequence[float],
                 nombre: str = ""):
        self.centro = v.vec(centro)
        self.ejes = [v.unitario(v.vec(e)) or base for e, base in
                     zip(ejes, ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))]
        self.medias = [max(float(m), 0.0) for m in medias]
        self.nombre = nombre

    @classmethod
    def desde_caja(cls, minimo: Vector, maximo: Vector, matriz=None, nombre: str = ""):
        """Zona a partir de la caja de una malla en su espacio y de su matriz de mundo.

        ``matriz``: 16 números por filas, como ``cmds.xform(q=True, matrix=True)``
        (la traslación al final); sin ella, la caja ya está en el mundo.
        """
        centro = tuple((a + b) / 2.0 for a, b in zip(minimo, maximo))
        medias = [(b - a) / 2.0 for a, b in zip(minimo, maximo)]
        if matriz is None:
            return cls(centro, ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), medias,
                       nombre)
        m = [float(x) for x in matriz]
        filas = [(m[0], m[1], m[2]), (m[4], m[5], m[6]), (m[8], m[9], m[10])]
        mundo = (centro[0] * m[0] + centro[1] * m[4] + centro[2] * m[8] + m[12],
                 centro[0] * m[1] + centro[1] * m[5] + centro[2] * m[9] + m[13],
                 centro[0] * m[2] + centro[1] * m[6] + centro[2] * m[10] + m[14])
        escalas = [v.largo(f) for f in filas]
        return cls(mundo, filas, [h * s for h, s in zip(medias, escalas)], nombre)

    def local(self, p: Vector) -> Tuple[float, float, float]:
        d = v.resta(p, self.centro)
        return tuple(v.punto(d, e) for e in self.ejes)

    def dentro(self, p: Vector, margen: float = 0.0) -> bool:
        return all(abs(c) <= h + margen for c, h in zip(self.local(p), self.medias))

    def distancia(self, p: Vector) -> Tuple[float, Vector]:
        """(distancia con signo, dirección hacia fuera): negativa dentro de la caja."""
        local = self.local(p)
        exceso = [abs(c) - h for c, h in zip(local, self.medias)]
        if max(exceso) <= 0.0:
            # Dentro: sale por la cara más cercana.
            i = max(range(3), key=lambda k: exceso[k])
            signo = 1.0 if local[i] >= 0.0 else -1.0
            return exceso[i], v.escala(self.ejes[i], signo)
        fuera = (0.0, 0.0, 0.0)
        for c, h, e, x in zip(local, self.medias, self.ejes, exceso):
            if x > 0.0:
                fuera = v.suma(fuera, v.escala(e, x if c > 0.0 else -x))
        d = v.largo(fuera)
        return d, (v.escala(fuera, 1.0 / d) if d > v.EPS else self.ejes[0])


class Zonas:
    """Todas las zonas prohibidas de una planta."""

    def __init__(self, zonas: Optional[List[Zona]] = None):
        self.zonas = list(zonas or [])

    def __bool__(self):
        return bool(self.zonas)

    def __len__(self):
        return len(self.zonas)

    def dentro(self, p: Vector, margen: float = 0.0) -> bool:
        return any(z.dentro(p, margen) for z in self.zonas)

    def empuje(self, p: Vector, alcance: float) -> Optional[Tuple[Vector, float, Vector]]:
        """La zona más cercana a menos de ``alcance``: (hacia fuera, fuerza 0..1, centro).

        Devuelve None si no hay ninguna tan cerca.
        """
        mejor = None
        for z in self.zonas:
            d, fuera = z.distancia(p)
            if d < alcance and (mejor is None or d < mejor[0]):
                mejor = (d, fuera, z.centro)
        if mejor is None:
            return None
        d, fuera, centro = mejor
        fuerza = 1.0 if d <= 0.0 else 1.0 - d / max(alcance, v.EPS)
        return fuera, fuerza, centro
