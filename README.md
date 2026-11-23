# Trepadora

Plugin para generar plantas trepadoras en Autodesk Maya 2026 y 2027, pensado para estudiantes.

> **Estado: fase 2 (texturas).** Ventana acoplable con los pasos en orden, preajustes e
> instalador de un solo gesto. Genera tallos con grosor, rabillos y hojas (instancias de
> unas pocas hojas modelo, o una sola malla) con materiales de Arnold y texturas de hoja y
> de corteza en cuatro tamaños, de 512 a 4K.

Funciona igual en Windows y en macOS, con el Python que trae Maya: no hay que instalar
nada más (no usa NumPy).

## Instalar

1. Descarga este repositorio (botón **Code → Download ZIP** en GitHub) y descomprímelo
   en una carpeta que no vayas a mover, por ejemplo `Documentos/Trepadora`.
2. Abre Maya y **arrastra el archivo `instalar.py`** de esa carpeta al visor.

Eso es todo. El instalador:

- escribe `trepadora.mod` en la carpeta de módulos de tu usuario de Maya, apuntando a la
  carpeta de Trepadora, para que Maya la encuentre cada vez que arranca;
- carga el plug-in y lo marca para que se cargue solo (aparece el menú **Trepadora**);
- crea el estante **Trepadora** con un botón que abre la ventana;
- abre la ventana.

**Aviso de seguridad de Maya 2027.** Maya avisa cuando carga un plug-in desde una carpeta
que no conoce: *Untrusted Plugin Loading - Security Warning*. Es el plug-in de Trepadora:
pulsa **Allow**. Si marcas antes **Apply to all plugins in this location**, Maya no lo
volverá a preguntar para esa carpeta. Si pulsas **Deny**, la ventana y el estante
funcionan, pero no aparece el menú al abrir Maya y Ctrl+Z no quita de una vez la planta
creada con **Crear malla**; para arreglarlo, arrastra otra vez `instalar.py` y pulsa
**Allow**.

No copia nada: si mueves la carpeta, vuelve a arrastrar `instalar.py`. Para actualizar a
una versión nueva, sustituye la carpeta y arrastra otra vez `instalar.py` (no hace falta
reiniciar Maya).

**Desinstalar:** en el Script Editor, pestaña Python, ejecuta (con tu ruta):

```python
import sys; sys.path.insert(0, r"C:/ruta/a/Trepadora")   # la carpeta de instalar.py
import instalar; instalar.desinstalar()
```

Quita el módulo, el plug-in y el estante. No borra la carpeta ni tus preajustes.

## Usar la ventana

Abre la ventana con el botón del estante o con **Trepadora → Abrir Trepadora…**. Se puede
acoplar a un lado de Maya y recuerda dónde la dejaste. Los pasos se activan en orden:

1. **Superficie.** Selecciona las mallas por las que trepa la planta (un muro, el suelo,
   una columna; también vale un grupo) y pulsa **Usar selección**. Si entre lo seleccionado
   hay localizadores, se usan como puntos de nacimiento.
2. **Origen** (opcional). Pulsa **Clic en el visor** y haz clic sobre la superficie donde
   nace cada planta; **Quitar** los borra. Sin orígenes, la planta nace en el centro de la
   base de la superficie.
3. **Aspecto.** Tipo de tallo, forma de hoja, Tamaño, Densidad de hojas, Grosor del tallo y
   Resolución de texturas (ver **Texturas** más abajo).
   Pulsa **Crecer** para ver la forma como líneas (es rápido). Cambia ajustes y vuelve a
   pulsar Crecer hasta que te guste; **Crecer más** la hace más grande sin empezar de cero
   y **Reiniciar** borra las líneas.
4. **Crear malla.** Crea los tallos con grosor, las hojas y los materiales, y deja la
   planta seleccionada. Todo se deshace con un solo **Ctrl+Z**; **Esc** detiene el
   crecimiento y se conserva lo crecido.

El pie de la ventana dice cuántas hojas saldrán y si la carga es baja, media o alta. Con
carga alta, la ventana pregunta antes de crear la malla.

**Cuando la planta para sola.** La planta deja de crecer cuando llena el espacio que tiene
o cuando sus ramas llegan a su largo máximo, así que a partir de ahí subir el Tamaño no la
hace más grande. La ventana lo dice al crecer. Si pararon por su largo, **Crecer más** las
alarga; si llenó el espacio, añade otra malla en el paso 1 o pon un origen en una zona libre.

**Ajustes avanzados** (plegados): crecimiento (semilla, escala, adherencia, gravedad, luz,
ramificación…), hojas (tamaño, caída, manchas, bronce, instancias y **hoja propia**: una
malla tuya que se usa como hoja) y la resolución de los tallos. Cada ajuste explica qué hace
al dejar el ratón encima.

**Preajustes.** El desplegable de arriba trae cinco: Hiedra de fachada, Enredadera colgante,
Musgo trepador, Hoja de corazón y Ramas secas. Con el botón **…** puedes guardar los tuyos,
importarlos y exportarlos como archivos `.json` (para repartirlos a la clase), borrar los
tuyos y volver a los valores por defecto. Los tuyos se guardan en la carpeta de preferencias
de Maya, en `trepadora/preajustes`.

**La escena recuerda.** La superficie, los orígenes, la hoja propia y los ajustes se guardan
en la escena (grupo `trepadora_origenes_grp`): al abrirla otro día la ventana sigue donde
estaba. Cada planta creada guarda además los ajustes y la semilla con que se hizo: selecciónala
y usa **… → Copiar los ajustes de la planta seleccionada** para repetirla o revisar cómo se hizo.

**Escenas de prueba.** En el menú **Trepadora** hay dos escenas listas para practicar: muro
y caja, y una pequeña ruina.

**Arnold.** Si Arnold (MtoA) está cargado al crear la malla, cada pieza lleva además un
material de Arnold que toma el color de cada hoja y le suma las texturas: nervios, relieve,
brillo y la luz que deja pasar la hoja, que a contraluz brilla y enseña los nervios. Si no
está cargado, la planta solo lleva el material del visor y en el render todas las hojas
salen del mismo verde.

**Texturas.** Las hojas y los tallos llevan texturas que vienen con Trepadora (no hace falta
Substance ni ningún otro programa). En el visor se ven los nervios con la tecla **6**
(texturas); en el render, siempre. Cada textura está en cuatro tamaños y el ajuste
**Resolución de texturas** del paso 3 elige cuál se usa:

| Resolución | Para qué |
|---|---|
| 512 | juegos y escenas con muchas plantas |
| 1K | clase (por defecto) |
| 2K | renders |
| 4K | renders de cerca |

Cambiarla cambia también las plantas que ya están en la escena, y se recuerda para la
próxima vez. No es un ajuste de cada planta: no se guarda en los preajustes. Si falta un
tamaño en la carpeta, se usa el siguiente más pequeño que haya (o uno más grande si no hay
ninguno) y la ventana lo avisa; por ejemplo, si no vas a usar 4K puedes borrar la carpeta
`texturas/4k` (unos 45 MB). Al renderizar, Arnold puede crear archivos `.tx` junto a las
texturas: son una caché y se pueden borrar.

Las escenas guardan la ruta de las texturas. Si abres una escena hecha en otro ordenador
(en casa con macOS y en clase con Windows, por ejemplo), el plug-in apunta sus texturas a la
carpeta de Trepadora de este ordenador, con la misma resolución, y lo dice en la línea de
mensajes de Maya.

## Uso desde el Script Editor (avanzado)

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
  superficie_maya.py  consultas de punto más cercano sobre mallas de Maya
  escenas.py          escenas de prueba (sencilla y ruina) y sus ajustes
  prototipo.py        crea en Maya la vista previa, la planta y sus materiales
  texturas.py         texturas de hojas y tallos: resoluciones, rutas y cambio en la escena
  i18n/               textos por idioma (es.json); la interfaz se puede traducir
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

Todos los textos están en `scripts/trepadora/i18n/es.json`. Para otro idioma, copia el
archivo con el código del idioma (por ejemplo `en.json`), traduce los valores sin tocar las
claves ni lo que va entre llaves, y en Maya ejecuta
`cmds.optionVar(stringValue=("trepadoraIdioma", "en"))` y reinicia Maya. Lo que falte por
traducir sale en español.
