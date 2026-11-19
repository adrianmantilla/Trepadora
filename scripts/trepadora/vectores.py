"""Operaciones mínimas con vectores 3D en Python puro.

Trepadora no depende de NumPy: algunas instalaciones de Maya no lo traen, y
para el número de puntos de una planta el cálculo en Python puro es suficiente.
Los vectores son tuplas (x, y, z).
"""

import math

EPS = 1e-9
CERO = (0.0, 0.0, 0.0)
ARRIBA = (0.0, 1.0, 0.0)
ABAJO = (0.0, -1.0, 0.0)


def vec(v):
    return (float(v[0]), float(v[1]), float(v[2]))


def suma(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def resta(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def escala(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def punto(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cruz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def largo(a):
    return math.sqrt(punto(a, a))


def distancia(a, b):
    return largo(resta(a, b))


def unitario(a):
    """Devuelve el vector normalizado, o None si es casi nulo."""
    n = largo(a)
    if n < EPS:
        return None
    return (a[0] / n, a[1] / n, a[2] / n)


def tangente(v, normal):
    """Proyecta ``v`` sobre el plano perpendicular a ``normal``."""
    return resta(v, escala(normal, punto(v, normal)))


def perpendicular(normal):
    eje = (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 0.0, 1.0)
    return unitario(cruz(normal, eje))


def rotar(v, eje, angulo):
    """Rota ``v`` alrededor de ``eje`` (unitario) con la fórmula de Rodrigues."""
    c, s = math.cos(angulo), math.sin(angulo)
    return suma(suma(escala(v, c), escala(cruz(eje, v), s)),
                escala(eje, punto(eje, v) * (1.0 - c)))


def angulo_entre(a, b):
    """Ángulo en radianes entre dos vectores unitarios."""
    return math.acos(max(-1.0, min(1.0, punto(a, b))))


def limitar_giro(anterior, deseada, maximo, eje_respaldo):
    """Gira ``anterior`` hacia ``deseada`` como mucho ``maximo`` radianes."""
    angulo = angulo_entre(anterior, deseada)
    if angulo <= maximo:
        return deseada
    eje = unitario(cruz(anterior, deseada)) or eje_respaldo
    return unitario(rotar(anterior, eje, maximo)) or anterior
