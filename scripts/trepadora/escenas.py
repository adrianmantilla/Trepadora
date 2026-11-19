"""Escenas de prueba descritas con cajas, compartidas por Maya y por las pruebas.

Cada caja es (centro, tamaño) en centímetros. Los orígenes son los puntos
donde nace cada planta.
"""

# Muro, caja y suelo: la escena mínima.
SENCILLA = {
    "suelo": ((0.0, -0.5, 0.0), (400.0, 1.0, 400.0)),
    "cajas": [
        ("muro", (0.0, 75.0, 0.0), (200.0, 150.0, 10.0)),
        ("caja", (60.0, 20.0, 30.0), (40.0, 40.0, 40.0)),
    ],
    "origenes": [(-20.0, 2.0, 5.5)],
}

# Una pequeña ruina: muro con ventana, columna y un murete delante.
RUINA = {
    "suelo": ((0.0, -0.5, 0.0), (700.0, 1.0, 700.0)),
    "cajas": [
        ("muro_izq", (-95.0, 115.0, 0.0), (110.0, 230.0, 20.0)),
        ("muro_der", (95.0, 115.0, 0.0), (110.0, 230.0, 20.0)),
        ("muro_bajo", (0.0, 40.0, 0.0), (80.0, 80.0, 20.0)),
        ("muro_alto", (0.0, 205.0, 0.0), (80.0, 50.0, 20.0)),
        ("alfeizar", (0.0, 83.0, 6.0), (96.0, 6.0, 32.0)),
        ("columna", (210.0, 140.0, 70.0), (36.0, 280.0, 36.0)),
        ("capitel", (210.0, 286.0, 70.0), (56.0, 12.0, 56.0)),
        ("murete", (-170.0, 22.0, 110.0), (120.0, 44.0, 30.0)),
        ("bloque", (90.0, 15.0, 120.0), (50.0, 30.0, 40.0)),
    ],
    "origenes": [(-120.0, 2.0, 12.0), (210.0, 2.0, 90.0), (-200.0, 2.0, 127.0),
                 (60.0, 2.0, 12.0)],
    # Ajustes con los que se ve mejor: paso fijo (la escena es grande), tallos
    # más serpenteantes y tallos que cuelgan de bordes y salientes.
    "ajustes": {
        "paso": 2.6, "pasos": 340, "longitud_max": 200, "prob_rama": 0.06,
        "aleatoriedad": 0.75, "cambio_deriva": 0.15, "evitar": 0.5,
        "prob_colgar": 0.5, "largo_colgante": 55,
    },
}

ESCENAS = {"sencilla": SENCILLA, "ruina": RUINA}


def cajas_min_max(escena):
    """Lista de (min, max) de todas las cajas, suelo incluido."""
    resultado = []
    for centro, tam in [escena["suelo"]] + [(c, t) for _, c, t in escena["cajas"]]:
        lo = tuple(centro[i] - tam[i] / 2.0 for i in range(3))
        hi = tuple(centro[i] + tam[i] / 2.0 for i in range(3))
        resultado.append((lo, hi))
    return resultado
