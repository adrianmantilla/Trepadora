# Trepadora · Referencia avanzada

Para quien quiera usar Trepadora desde Python, rehacer sus texturas, traducirla o tocar el código. Para instalarla y usarla basta con el [README](../README.md).

## Uso desde el Script Editor

Lo mismo se puede hacer sin la ventana. Con Trepadora instalada, en la pestaña **Python**:

```python
import trepadora.prototipo as tp
tp.escena_de_prueba()        # crea suelo, muro, caja y un localizador, y hace crecer
tp.escena_ruina()            # una pequeña ruina: muro con ventana, columna y murete
```

Para usar tu propia escena: selecciona una o varias mallas y, si quieres, uno o varios
localizadores donde nace cada planta. Después:

```python
tp.ejecutar(semilla=3)                   # tallos y hojas
tp.ejecutar(semilla=3, modo="curvas")    # solo líneas, para probar ajustes rápido
tp.ejecutar(semilla=3, forma_hoja="corazon", tipo_tallo="verde")
tp.ejecutar(semilla=3, hoja_propia="miHoja")   # tu propia hoja modelada
tp.ejecutar(semilla=3, instancias=False)       # todas las hojas en una malla
```

Sin localizadores, la planta nace en la base del primer objeto seleccionado. Sin instalar,
añade antes la carpeta `scripts` a `sys.path`.

### Hojas, tallos y tipos

| Opción | Por defecto | Qué hace |
| --- | --- | --- |
| `instancias` | True | Las hojas son instancias de unas pocas hojas modelo (unas 50): la escena pesa mucho menos y el visor va más suelto. Con `False`, todas las hojas van en una sola malla, por ejemplo para exportarla |
| `forma_hoja` | `"hiedra"` | `"hiedra"` (con lóbulos, mezclada con acorazonada), `"corazon"`, `"alargada"` o `"redonda"` |
| `tipo_tallo` | `"lenoso"` | `"lenoso"` (marrón, puntas verdes), `"nudoso"` (más grueso, con corteza arrugada), `"verde"` (fino y verde) o `"rojizo"` (como la parra virgen) |
| `hoja_propia` | ninguna | Nombre de una malla de tu escena que se usa como hoja (siempre con instancias). Modélala con la base en el origen, la punta hacia +Y y la cara hacia +Z; el tamaño se ajusta solo y conserva su material |

Con instancias, el visor enseña cada hoja con el tono de su hoja modelo: seis tonos, cada
uno con su material de visor (`trepadora_hojas_tono1_mat` a `trepadora_hojas_tono6_mat`),
porque el visor no pinta los colores de vértice de las instancias. En el render de Arnold
cada hoja sale con su propio color, porque cada instancia lleva en `rgbPP` cuánto se aparta
del tono de su modelo. Las hojas modelo quedan
ocultas en el grupo `trepadora_hojas_modelos`, y las partículas que marcan dónde va cada
hoja, en `trepadora_hojas_puntos` (también ocultas).

### Ajustes del crecimiento

Se pasan por nombre, por ejemplo `tp.ejecutar(semilla=4, gravedad=1.0, prob_rama=0.08)`.

| Ajuste | Por defecto | Qué hace |
| --- | --- | --- |
| `semilla` | 1 | Mismos ajustes y misma semilla dan siempre la misma planta |
| `pasos` | 260 | Cuánto crece |
| `adherencia` | 0.8 | Cuánto se pega a la superficie (0 a 1) |
| `gravedad` | 0.5 | Cuánto cuelga cuando pierde el apoyo; por encima de 0.5 caen cortinas por la pared |
| `luz` | 0.36 | Tendencia a subir por las paredes (hacia `direccion_luz`) |
| `aleatoriedad` | 0.45 | Cuánto serpentea |
| `cambio_deriva` | 0.25 | Bajo = curvas largas y tranquilas; alto = más nervioso |
| `giro_max` | 16 | Grados que puede girar una rama en cada paso |
| `evitar` | 0.9 | Cuánto se apartan las ramas de las zonas ya ocupadas |
| `densidad_max` | 10 | Una rama deja de crecer si tiene más vecinas que esto |
| `prob_rama` | 0.09 | Probabilidad por paso de que brote una rama nueva |
| `generaciones_max` | 4 | Niveles de ramas hijas |
| `longitud_max` | 220 | Puntos máximos de la rama principal |
| `brotes_basales` | 3 | Tallos extra que salen de la base |
| `rumbo` | 0.35 | Cuánto mantienen las ramas hijas la dirección con la que brotan (se abren en diagonal) |
| `luz_variacion` | 0.35 | Cada rama busca la luz con una fuerza distinta (evita franjas paralelas) |
| `buscar_hueco` | True | Las ramas nuevas brotan donde hay más hueco |
| `buscar_paredes` | 1.0 | Si la planta nace en el suelo, va hacia la pared más cercana y trepa |
| `prob_colgar` | 0.35 | Probabilidad de que caiga un tallo colgante desde un borde o un saliente |
| `largo_colgante` | 45 | Largo máximo de los tallos colgantes, en pasos |
| `ramillas` | 0 | Probabilidad por paso de una ramilla corta que rellena huecos (prueba 0.08) |
| `largo_ramilla` | 12 | Largo máximo de cada ramilla, en pasos |
| `limite_puntos` | 60000 | Tope de seguridad para no colgar Maya |
| `grosor` | 1.0 | Multiplica el grosor de los tallos |
| `paso` | automático | Largo de cada paso, en unidades de la escena |

### Ajustes de las hojas

Se pasan como diccionario: `tp.ejecutar(semilla=2, hojas={"densidad": 0.6, "tamano": 1.3})`.

| Ajuste | Por defecto | Qué hace |
| --- | --- | --- |
| `densidad` | 0.82 | Probabilidad de hoja en cada punto de rama |
| `tamano` | 1.0 | Tamaño relativo de las hojas |
| `variacion` | 0.5 | Diferencia de tamaño entre hojas |
| `puntas_jovenes` | 14 | Puntos desde la punta en los que las hojas son pequeñas |
| `peciolo` | 0.28 | Largo del rabillo, relativo al tamaño de la hoja |
| `despegue` | 0.35 | Cuánto se separan de la pared |
| `caida` | 0.45 | Cuánto cuelga la punta de la hoja |
| `degradado` | 0.7 | Cuánto menguan las hojas lejos de la raíz (0 = todas iguales) |
| `tronco_visible` | 1.0 | Cuánto se aclaran las hojas sobre los tallos gruesos (0 = nada) |
| `en_suelo` | 0.4 | Fracción de hojas en los tallos que reptan por el suelo |
| `manchas` | 0.6 | Cuánto se agrupan las hojas en matas tupidas, oscuras y abultadas (rabillos largos, hojas a distintas distancias del muro), con zonas más ralas, planas y de verde más claro entre ellas (0 = reparto uniforme) |
| `escala_manchas` | 9.0 | Tamaño de esas matas, en largos de hoja |
| `bronce` | 0.015 | Cuántas hojas tiran a bronce, como la hiedra en invierno (con 0.015, alrededor de una de cada cien); salen sueltas, nunca dos juntas, entre las hojas viejas de la parte baja |

Las distancias (paso, adherencia, separación) se calculan solas a partir del tamaño de los
objetos seleccionados.

## Estructura

```
instalar.py           instalador: se arrastra al visor de Maya
plug-ins/
  trepadora_plugin.py plug-in de Maya: crea el menú Trepadora y el paso de Ctrl+Z de Crear malla
icons/trepadora.png   icono del estante
scripts/trepadora/
  ajustes.py          los ajustes de la ventana, sus rangos y los preajustes (no depende de Maya)
  preajustes/         los preajustes incluidos (.json)
  sesion.py           lo que hace la ventana: superficie, orígenes, crecer, crear malla
  ui/ventana.py       la ventana (PySide6, acoplable)
  ui/herramienta.py   herramienta de clic en el visor para colocar orígenes
  menu.py             menú Trepadora
  deshacer.py         Ctrl+Z quita de una vez la planta creada (sus mallas se hacen con la API)
  crecimiento.py      algoritmo de crecimiento y grosor (no depende de Maya)
  hojas.py            colocación de hojas
  geometria.py        mallas de tallos, hojas y rabillos en Python puro; tipos de tallo y hoja
  instancias.py       hojas modelo y colocación de cada hoja para el instanciador
  vectores.py         operaciones con vectores
  superficie_maya.py  consultas de punto más cercano sobre mallas de Maya; zonas y curvas guía
  zonas.py            zonas prohibidas: cajas orientadas que la planta rodea (no depende de Maya)
  guias.py            curvas guía: el tirón que siguen las ramas (no depende de Maya)
  escenas.py          escenas de prueba (sencilla y ruina) y sus ajustes
  prototipo.py        crea en Maya la vista previa, la planta y sus materiales
  texturas.py         texturas de hojas y tallos: resoluciones, rutas y cambio en la escena
  exportar.py         exportar a FBX y Alembic: hornea las hojas en una malla (o en tarjetas
                      ligeras) y copia las texturas
  i18n/               textos por idioma (es.json, en.json); la interfaz se puede traducir
texturas/             texturas JPEG en 512/, 1k/, 2k/ y 4k/: <juego>_<mapa>.jpg
herramientas/
  texturas/generar_texturas.py  dibuja las texturas de las hojas (NumPy y Pillow, sin Maya)
  painter/            scripts para Substance 3D Painter: la corteza (Wood Bark) y el puente
  prueba_ventana.py   prueba de la ventana dentro de Maya, botón a botón, con capturas
  ensayo_sin_maya/    ensayo de la ventana con un Maya simulado (necesita PySide6)
  prueba_instancias.py  prueba de las hojas como instancias (mayapy)
  capturas_maya.py    genera las capturas de comparación en Maya
  render_arnold.py    render de prueba de la ruina con Arnold, con cielo y sol (mayapy)
  diagnostico.py      cifras del crecimiento de la ruina, iguales dentro y fuera de Maya
tests/                pruebas sin Maya, con una escena simulada
```

Pruebas automáticas (fuera de Maya, con Python 3): `python -m unittest discover tests`.
Las de la ventana necesitan PySide6 (`pip install PySide6`); si no está, se saltan.

## Rehacer las texturas

No hace falta para usar Trepadora: las texturas ya vienen hechas. Cada forma de hoja tiene
el juego `hoja_<forma>` (detalle, normal, rugosidad y traslucidez) y los tallos el juego
`corteza` (detalle, normal y rugosidad). El *detalle* es un gris que vale 0,5 de media: el
material lo multiplica por el color de cada hoja, así que las hojas conservan sus tonos.
Los relieves son mapas de normales de tipo OpenGL.

- **Hojas:** `python herramientas/texturas/generar_texturas.py` las dibuja en el espacio UV
  de cada forma de hoja y las guarda en `texturas/` a los cuatro tamaños (necesita NumPy y
  Pillow). Con `--solo 512,1k` hace solo esos tamaños. No toca la corteza salvo que se
  añada `--con-corteza`, que la sustituye por una corteza procedural para quien no tenga
  Painter.
- **Corteza:** sale de Substance 3D Painter con el material *Wood Bark*, mediante
  `herramientas/painter/corteza_painter.py`, que se ejecuta dentro de Painter con el
  complemento `herramientas/painter/trepadora_puente.py`.

## Traducir la interfaz

Todos los textos están en `scripts/trepadora/i18n/es.json` (y su traducción al inglés en
`en.json`). Para otro idioma, copia el archivo con el código del idioma (por ejemplo
`fr.json`), traduce los valores sin tocar las claves ni lo que va entre llaves. El idioma nuevo aparece solo en **Trepadora → Idioma /
Language** (con su código; para que salga su nombre, añádelo a `NOMBRES_IDIOMA` en
`scripts/trepadora/menu.py`). Lo que falte por traducir sale en español.
