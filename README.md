# Trepadora

Plugin para generar plantas trepadoras en Autodesk Maya 2026 y 2027, pensado para estudiantes.

> **Estado: fase 0 (prototipo del crecimiento).** Todavía no hay interfaz: se usa desde el
> Script Editor. Genera tallos con grosor y hojas como mallas, o solo curvas para ir rápido.

No necesita instalar nada: funciona con el Python que trae Maya (no usa NumPy).

## Probar el prototipo en Maya

1. Descarga o clona este repositorio, por ejemplo en `C:/trepadora` o `~/trepadora`.
2. Abre el Script Editor de Maya, pestaña **Python**, y ejecuta (cambia la ruta por la tuya):

   ```python
   import sys
   sys.path.append(r"C:/trepadora/scripts")   # en macOS: "/Users/tu_usuario/trepadora/scripts"

   import trepadora.prototipo as tp
   tp.escena_de_prueba()        # crea suelo, muro, caja y un localizador, y hace crecer
   ```

3. Para usar tu propia escena: selecciona una o varias mallas y, si quieres, uno o varios
   localizadores donde nace cada planta. Después:

   ```python
   tp.ejecutar(semilla=3)                   # tallos y hojas
   tp.ejecutar(semilla=3, modo="curvas")    # solo líneas, para probar ajustes rápido
   ```

   Sin localizadores, la planta nace en la base del primer objeto seleccionado.
   Pulsa **Esc** para detener el crecimiento; todo se deshace con un solo **Ctrl+Z**.

### Ajustes del crecimiento

Se pasan por nombre, por ejemplo `tp.ejecutar(semilla=4, gravedad=1.0, prob_rama=0.08)`.

| Ajuste | Por defecto | Qué hace |
| --- | --- | --- |
| `semilla` | 1 | Mismos ajustes y misma semilla dan siempre la misma planta |
| `pasos` | 260 | Cuánto crece |
| `adherencia` | 0.8 | Cuánto se pega a la superficie (0 a 1) |
| `gravedad` | 0.5 | Cuánto cuelga cuando pierde el apoyo |
| `luz` | 0.3 | Tendencia a subir por las paredes (hacia `direccion_luz`) |
| `aleatoriedad` | 0.45 | Cuánto serpentea |
| `cambio_deriva` | 0.25 | Bajo = curvas largas y tranquilas; alto = más nervioso |
| `giro_max` | 16 | Grados que puede girar una rama en cada paso |
| `evitar` | 0.9 | Cuánto se apartan las ramas de las zonas ya ocupadas |
| `prob_rama` | 0.07 | Probabilidad por paso de que brote una rama nueva |
| `generaciones_max` | 4 | Niveles de ramas hijas |
| `longitud_max` | 220 | Puntos máximos de la rama principal |
| `limite_puntos` | 60000 | Tope de seguridad para no colgar Maya |
| `grosor` | 1.0 | Multiplica el grosor de los tallos |

### Ajustes de las hojas

Se pasan como diccionario: `tp.ejecutar(semilla=2, hojas={"densidad": 0.6, "tamano": 1.3})`.

| Ajuste | Por defecto | Qué hace |
| --- | --- | --- |
| `densidad` | 0.85 | Probabilidad de hoja en cada punto de rama |
| `tamano` | 1.0 | Tamaño relativo de las hojas |
| `variacion` | 0.35 | Diferencia de tamaño entre hojas |
| `puntas_jovenes` | 14 | Puntos desde la punta en los que las hojas son pequeñas |
| `despegue` | 0.35 | Cuánto se separan de la pared |
| `caida` | 0.45 | Cuánto cuelga la punta de la hoja |

Las distancias (paso, adherencia, separación) se calculan solas a partir del tamaño de los
objetos seleccionados.

## Estructura

```
scripts/trepadora/
  crecimiento.py      algoritmo de crecimiento y grosor (no depende de Maya)
  hojas.py            colocación de hojas
  geometria.py        mallas de tallos, hojas y rabillos en Python puro
  vectores.py         operaciones con vectores
  superficie_maya.py  consultas de punto más cercano sobre mallas de Maya
  prototipo.py        prueba de la fase 0 en Maya
  i18n/               textos por idioma (es.json); la interfaz se puede traducir
herramientas/
  capturas_maya.py    genera las capturas de comparación en Maya
tests/                pruebas sin Maya, con una escena simulada
```

Pruebas automáticas (fuera de Maya, con Python 3): `python -m unittest discover tests`
