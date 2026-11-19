"""Superficies simuladas para probar el crecimiento sin Maya."""


class Muro:
    """Plano vertical infinito z = 0 con la cara hacia +z."""

    def mas_cercano(self, punto):
        return (punto[0], punto[1], 0.0), (0.0, 0.0, 1.0)


class Cajas:
    """Unión de cajas alineadas con los ejes, como el suelo, el muro y la caja de la escena de prueba.

    Cada caja es (min, max). Devuelve el punto más cercano sobre la superficie de
    cualquiera de ellas y la normal de la cara correspondiente.
    """

    def __init__(self, cajas):
        self.cajas = cajas

    @staticmethod
    def _sobre_caja(p, lo, hi):
        dentro = all(lo[i] <= p[i] <= hi[i] for i in range(3))
        if dentro:
            # Cara más cercana.
            mejor = None
            for i in range(3):
                for lado, valor in ((-1.0, lo[i]), (1.0, hi[i])):
                    d = abs(p[i] - valor)
                    if mejor is None or d < mejor[0]:
                        mejor = (d, i, lado, valor)
            _, i, lado, valor = mejor
            q = list(p)
            q[i] = valor
            n = [0.0, 0.0, 0.0]
            n[i] = lado
            return tuple(q), tuple(n)
        q = tuple(min(max(p[i], lo[i]), hi[i]) for i in range(3))
        # Normal de la cara: el eje en el que el punto sobresale más.
        mejor_i, mejor_d, signo = 0, -1.0, 1.0
        for i in range(3):
            d = p[i] - q[i]
            if abs(d) > mejor_d:
                mejor_i, mejor_d, signo = i, abs(d), (1.0 if d > 0 else -1.0)
        n = [0.0, 0.0, 0.0]
        n[mejor_i] = signo
        return q, tuple(n)

    def mas_cercano(self, punto):
        mejor = None
        for lo, hi in self.cajas:
            q, n = self._sobre_caja(punto, lo, hi)
            d = sum((punto[i] - q[i]) ** 2 for i in range(3))
            if mejor is None or d < mejor[0]:
                mejor = (d, q, n)
        return mejor[1], mejor[2]


def escena_de_prueba():
    """Igual que prototipo.escena_de_prueba(): suelo, muro y caja."""
    suelo = ((-200.0, -1.0, -200.0), (200.0, 0.0, 200.0))
    muro = ((-100.0, 0.0, -5.0), (100.0, 150.0, 5.0))
    caja = ((40.0, 0.0, 10.0), (80.0, 40.0, 50.0))
    return Cajas([suelo, muro, caja])
