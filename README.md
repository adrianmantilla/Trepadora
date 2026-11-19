# Trepadora

Plugin para generar plantas trepadoras en Autodesk Maya 2026 y 2027, pensado para estudiantes.

> **Estado: fase 0 (prototipo del crecimiento).** Todavía no hay interfaz, hojas ni mallas:
> el objetivo es validar cómo crecen las ramas. Se dibujan como curvas.

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
   tp.ejecutar(semilla=3)
   ```

   Sin localizadores, la planta nace en la base del primer objeto seleccionado.
   Pulsa **Esc** para detener el crecimiento; todo se deshace con un solo **Ctrl+Z**.

### Ajustes que puedes probar

Cualquier ajuste se pasa por nombre, por ejemplo `tp.ejecutar(semilla=4, gravedad=1.0, prob_rama=0.08)`.

| Ajuste | Por defecto | Qué hace |
| --- | --- | --- |
| `semilla` | 1 | Mismos ajustes y misma semilla dan siempre la misma planta |
| `pasos` | 200 | Cuánto crece |
| `adherencia` | 0.8 | Cuánto se pega a la superficie (0 a 1) |
| `gravedad` | 0.5 | Cuánto cuelga cuando pierde el apoyo |
| `luz` | 0.3 | Tendencia a crecer hacia `direccion_luz` (arriba por defecto) |
| `aleatoriedad` | 0.35 | Cuánto serpentea |
| `prob_rama` | 0.06 | Probabilidad por paso de que salga una rama nueva |
| `giro_max` | 20 | Grados que puede girar una rama en cada paso (menos = curvas más suaves) |
| `evitar` | 0.9 | Cuánto se apartan las ramas de las zonas ya ocupadas |
| `generaciones_max` | 3 | Niveles de ramas hijas |
| `longitud_max` | 150 | Puntos máximos de la rama principal |
| `limite_puntos` | 50000 | Tope de seguridad para no colgar Maya |

Las distancias (`longitud_paso`, `distancia_adherencia`, `separacion`) se calculan solas a partir
del tamaño de los objetos seleccionados.

## Estructura

```
scripts/trepadora/
  crecimiento.py      algoritmo de crecimiento (no depende de Maya ni de NumPy)
  vectores.py         operaciones con vectores en Python puro
  superficie_maya.py  consultas de punto más cercano sobre mallas de Maya
  prototipo.py        prueba de la fase 0: crecer y dibujar curvas
  i18n/               textos por idioma (es.json); la interfaz se puede traducir
tests/                pruebas del algoritmo sin Maya
```

No necesita instalar nada: funciona con el Python que trae Maya.

Pruebas automáticas (fuera de Maya, con Python 3): `python -m unittest discover tests`
