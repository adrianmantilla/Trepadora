"""La ventana de Trepadora: tres pasos numerados, Crecer y Crear malla.

Abrirla desde el Script Editor::

    import trepadora.ui.ventana as v
    v.mostrar()

Todo lo que hace va a ``Sesion`` (``trepadora.sesion``); aquí solo se montan
los controles y se enseña el resultado. Ningún texto está escrito en el
código: salen del archivo de idioma (``i18n/es.json``).
"""

import os
import random

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # Maya 2024 y anteriores
    from PySide2 import QtCore, QtGui, QtWidgets

try:
    from maya import cmds
    from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

    EN_MAYA = True
except ImportError:  # fuera de Maya, para las pruebas
    cmds = None
    EN_MAYA = False

    class MayaQWidgetDockableMixin(object):
        def show(self, *args, **kwargs):
            QtWidgets.QWidget.show(self)

from .. import ajustes as aj
from .. import texturas
from ..ajustes import Aviso
from ..i18n import t

NOMBRE = "trepadoraVentana"
CONTROL = NOMBRE + "WorkspaceControl"
_COLOR_CARGA = {"baja": "#7cc576", "media": "#e3a948", "alta": "#e8675a"}
_COLOR_AVISO = "#e3a948"
_COLOR_BIEN = "#9fd39a"
_ESTILO = """
QPushButton#principal { font-weight: bold; padding: 6px; background-color: #4b7a45; }
QPushButton#principal:disabled { background-color: #3a3a3a; }
QPushButton#principal:hover { background-color: #5a8f53; }
QGroupBox { font-weight: bold; margin-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 3px; }
"""


def _numero(n):
    return "{:,}".format(int(n)).replace(",", t("separador_miles"))


# ------------------------------------------------------------------ widgets
class Deslizador(QtWidgets.QWidget):
    """Deslizador con su casilla numérica, para un ajuste real o entero."""

    cambiado = QtCore.Signal(object)
    _PASOS = 1000

    def __init__(self, control, parent=None):
        super(Deslizador, self).__init__(parent)
        self.control = control
        fila = QtWidgets.QHBoxLayout(self)
        fila.setContentsMargins(0, 0, 0, 0)
        self.barra = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.barra.setRange(0, self._PASOS)
        if control.tipo == "entero":
            self.casilla = QtWidgets.QSpinBox()
        else:
            self.casilla = QtWidgets.QDoubleSpinBox()
            self.casilla.setDecimals(control.decimales)
            self.casilla.setSingleStep(10 ** -control.decimales * 5 if control.decimales > 2
                                       else 0.05)
        self.casilla.setRange(control.minimo, control.maximo)
        self.casilla.setFixedWidth(64)
        self.casilla.setKeyboardTracking(False)
        fila.addWidget(self.barra, 1)
        fila.addWidget(self.casilla)
        self.barra.valueChanged.connect(self._desde_barra)
        self.casilla.valueChanged.connect(self._desde_casilla)
        self.poner(control.defecto)

    def _a_barra(self, valor):
        c = self.control
        return int(round(self._PASOS * (valor - c.minimo) / float(c.maximo - c.minimo)))

    def _desde_barra(self, posicion):
        c = self.control
        valor = c.minimo + (c.maximo - c.minimo) * posicion / float(self._PASOS)
        valor = aj.ajustar(c, valor)
        self.casilla.blockSignals(True)
        self.casilla.setValue(valor)
        self.casilla.blockSignals(False)
        self.cambiado.emit(valor)

    def _desde_casilla(self, valor):
        self.barra.blockSignals(True)
        self.barra.setValue(self._a_barra(valor))
        self.barra.blockSignals(False)
        self.cambiado.emit(aj.ajustar(self.control, valor))

    def valor(self):
        return aj.ajustar(self.control, self.casilla.value())

    def poner(self, valor):
        for w in (self.barra, self.casilla):
            w.blockSignals(True)
        self.casilla.setValue(valor)
        self.barra.setValue(self._a_barra(valor))
        for w in (self.barra, self.casilla):
            w.blockSignals(False)


class Semilla(QtWidgets.QWidget):
    """Número de semilla y un botón para probar otra al azar."""

    cambiado = QtCore.Signal(object)

    def __init__(self, control, parent=None):
        super(Semilla, self).__init__(parent)
        self.control = control
        fila = QtWidgets.QHBoxLayout(self)
        fila.setContentsMargins(0, 0, 0, 0)
        self.casilla = QtWidgets.QSpinBox()
        self.casilla.setRange(control.minimo, control.maximo)
        self.casilla.setKeyboardTracking(False)
        self.otra = QtWidgets.QPushButton(t("semilla_otra"))
        self.otra.setToolTip(t("ayuda_semilla_otra"))
        fila.addWidget(self.casilla, 1)
        fila.addWidget(self.otra)
        self.casilla.valueChanged.connect(lambda v: self.cambiado.emit(int(v)))
        self.otra.clicked.connect(
            lambda: self.casilla.setValue(random.randint(control.minimo, control.maximo)))
        self.poner(control.defecto)

    def valor(self):
        return int(self.casilla.value())

    def poner(self, valor):
        self.casilla.blockSignals(True)
        self.casilla.setValue(int(valor))
        self.casilla.blockSignals(False)


class Opciones(QtWidgets.QComboBox):
    cambiado = QtCore.Signal(object)

    def __init__(self, control, parent=None):
        super(Opciones, self).__init__(parent)
        self.control = control
        for opcion in control.opciones:
            self.addItem(t("opcion_{}_{}".format(control.clave, opcion)), opcion)
        self.currentIndexChanged.connect(lambda i: self.cambiado.emit(self.itemData(i)))
        self.poner(control.defecto)

    def valor(self):
        return self.currentData()

    def poner(self, valor):
        self.blockSignals(True)
        self.setCurrentIndex(max(0, self.findData(valor)))
        self.blockSignals(False)


class SiNo(QtWidgets.QCheckBox):
    cambiado = QtCore.Signal(object)

    def __init__(self, control, parent=None):
        super(SiNo, self).__init__(parent)
        self.control = control
        self.toggled.connect(lambda v: self.cambiado.emit(bool(v)))
        self.poner(control.defecto)

    def valor(self):
        return self.isChecked()

    def poner(self, valor):
        self.blockSignals(True)
        self.setChecked(bool(valor))
        self.blockSignals(False)


def control_para(control):
    if control.clave == "semilla":
        return Semilla(control)
    return {"opcion": Opciones, "si_no": SiNo}.get(control.tipo, Deslizador)(control)


class Plegable(QtWidgets.QWidget):
    """Un título con flecha que enseña u oculta lo que tiene debajo."""

    def __init__(self, titulo, abierto=False, parent=None):
        super(Plegable, self).__init__(parent)
        caja = QtWidgets.QVBoxLayout(self)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(2)
        self.boton = QtWidgets.QToolButton()
        self.boton.setText(titulo)
        self.boton.setCheckable(True)
        self.boton.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.boton.setAutoRaise(True)
        self.boton.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
        self.contenido = QtWidgets.QWidget()
        caja.addWidget(self.boton)
        caja.addWidget(self.contenido)
        self.boton.toggled.connect(self.abrir)
        self.boton.setChecked(abierto)
        self.abrir(abierto)

    def abrir(self, abierto):
        self.boton.setArrowType(QtCore.Qt.DownArrow if abierto else QtCore.Qt.RightArrow)
        self.contenido.setVisible(abierto)


# ------------------------------------------------------------------ ventana
class Ventana(MayaQWidgetDockableMixin, QtWidgets.QWidget):
    """Panel acoplable con los tres pasos. ``sesion`` hace el trabajo."""

    def __init__(self, sesion=None, parent=None):
        super(Ventana, self).__init__(parent=parent)
        if sesion is None:
            from ..sesion import Sesion

            sesion = Sesion()
        self.sesion = sesion
        self.setObjectName(NOMBRE)
        self.setWindowTitle(t("ventana_titulo"))
        self.setStyleSheet(_ESTILO)
        self.setMinimumWidth(320)
        self.resize(380, 820)
        self.controles = {}
        self.preajustes = []
        self._trabajos = []
        self._ultima_exportacion = None
        self._construir()
        self._cargar_preajustes()
        self._poner_controles(self.sesion.ajustes)
        self._actualizar()

    # ------------------------------------------------------------ montaje
    def _construir(self):
        exterior = QtWidgets.QVBoxLayout(self)
        exterior.setContentsMargins(0, 0, 0, 0)
        desplazable = QtWidgets.QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setFrameShape(QtWidgets.QFrame.NoFrame)
        exterior.addWidget(desplazable)
        interior = QtWidgets.QWidget()
        desplazable.setWidget(interior)
        caja = QtWidgets.QVBoxLayout(interior)
        caja.setContentsMargins(8, 8, 8, 8)
        caja.setSpacing(8)

        caja.addLayout(self._cabecera())
        caja.addWidget(self._paso_superficie())
        caja.addWidget(self._paso_origen())
        caja.addWidget(self._paso_aspecto())
        caja.addLayout(self._botones_crecer())
        caja.addWidget(self._avanzados())
        caja.addLayout(self._pie())
        self.mensaje = QtWidgets.QLabel()
        self.mensaje.setWordWrap(True)
        self.mensaje.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        caja.addWidget(self.mensaje)
        caja.addStretch(1)

    def _cabecera(self):
        fila = QtWidgets.QHBoxLayout()
        titulo = QtWidgets.QLabel(t("ventana_titulo"))
        letra = titulo.font()
        letra.setPointSizeF(letra.pointSizeF() * 1.3)
        letra.setBold(True)
        titulo.setFont(letra)
        self.combo_preajustes = QtWidgets.QComboBox()
        self.combo_preajustes.setToolTip(t("ayuda_preajustes"))
        self.combo_preajustes.activated.connect(self._elegir_preajuste)
        self.mas_preajustes = QtWidgets.QToolButton()
        self.mas_preajustes.setText("…")
        self.mas_preajustes.setToolTip(t("ayuda_menu_preajustes"))
        self.mas_preajustes.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(self.mas_preajustes)
        menu.addAction(t("preajuste_guardar"), self._guardar_preajuste)
        menu.addAction(t("preajuste_importar"), self._importar_preajuste)
        menu.addAction(t("preajuste_exportar"), self._exportar_preajuste)
        self.accion_borrar = menu.addAction(t("preajuste_borrar"), self._borrar_preajuste)
        menu.addAction(t("preajuste_carpeta"), self._abrir_carpeta)
        menu.addSeparator()
        menu.addAction(t("preajuste_de_planta"), self._ajustes_de_planta)
        menu.addAction(t("preajuste_por_defecto"), self._por_defecto)
        menu.aboutToShow.connect(self._menu_preajustes)
        self.mas_preajustes.setMenu(menu)
        fila.addWidget(titulo)
        fila.addStretch(1)
        fila.addWidget(self.combo_preajustes, 2)
        fila.addWidget(self.mas_preajustes)
        return fila

    def _paso_superficie(self):
        caja = QtWidgets.QGroupBox(t("paso_superficie"))
        fila = QtWidgets.QHBoxLayout(caja)
        self.boton_superficie = QtWidgets.QPushButton(t("usar_seleccion"))
        self.boton_superficie.setToolTip(t("ayuda_usar_seleccion"))
        self.boton_superficie.clicked.connect(self._usar_seleccion)
        self.estado_superficie = QtWidgets.QLabel()
        self.estado_superficie.setWordWrap(True)
        fila.addWidget(self.boton_superficie)
        fila.addWidget(self.estado_superficie, 1)
        return caja

    def _paso_origen(self):
        self.caja_origen = QtWidgets.QGroupBox(t("paso_origen"))
        columna = QtWidgets.QVBoxLayout(self.caja_origen)
        fila = QtWidgets.QHBoxLayout()
        self.boton_clic = QtWidgets.QPushButton(t("clic_visor"))
        self.boton_clic.setCheckable(True)
        self.boton_clic.setToolTip(t("ayuda_clic_visor"))
        self.boton_clic.toggled.connect(self._clic_visor)
        self.boton_quitar = QtWidgets.QPushButton(t("quitar_origenes"))
        self.boton_quitar.setToolTip(t("ayuda_quitar_origenes"))
        self.boton_quitar.clicked.connect(self._quitar_origenes)
        fila.addWidget(self.boton_clic, 1)
        fila.addWidget(self.boton_quitar)
        self.estado_origen = QtWidgets.QLabel()
        self.estado_origen.setWordWrap(True)
        columna.addLayout(fila)
        columna.addWidget(self.estado_origen)
        return self.caja_origen

    def _fila(self, formulario, control):
        widget = control_para(control)
        widget.cambiado.connect(lambda valor, c=control.clave: self._al_cambiar(c, valor))
        etiqueta = QtWidgets.QLabel(t("ajuste_" + control.clave))
        ayuda = t("ayuda_" + control.clave)
        etiqueta.setToolTip(ayuda)
        widget.setToolTip(ayuda)
        formulario.addRow(etiqueta, widget)
        self.controles[control.clave] = widget
        return widget

    def _formulario(self, padre=None):
        formulario = QtWidgets.QFormLayout(padre)
        formulario.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        formulario.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        return formulario

    def _paso_aspecto(self):
        caja = QtWidgets.QGroupBox(t("paso_aspecto"))
        formulario = self._formulario(caja)
        for control in aj.controles_del_grupo("aspecto"):
            self._fila(formulario, control)
        # No es un ajuste de la planta (no va en los preajustes): vale para toda
        # la escena y cambia también las plantas que ya están creadas.
        control = aj.Control("texturas", "planta", "opcion", "aspecto", texturas.POR_DEFECTO,
                             opciones=texturas.RESOLUCIONES)
        self.combo_texturas = Opciones(control)
        self.combo_texturas.poner(self.sesion.resolucion_texturas())
        self.combo_texturas.cambiado.connect(self._cambiar_texturas)
        etiqueta = QtWidgets.QLabel(t("ajuste_texturas"))
        for widget in (etiqueta, self.combo_texturas):
            widget.setToolTip(t("ayuda_texturas"))
        formulario.addRow(etiqueta, self.combo_texturas)
        return caja

    def _cambiar_texturas(self, resolucion):
        resultado = self._hacer(self.sesion.cambiar_texturas, resolucion)
        if resultado is None:
            return
        cambiadas, usada = resultado
        nombre = t("opcion_texturas_" + resolucion).split(" ")[0]
        if usada != resolucion:
            self.avisar(t("texturas_faltan", resolucion=nombre,
                          usada=t("opcion_texturas_" + usada).split(" ")[0]))
        elif cambiadas:
            self.avisar(t("texturas_cambiadas", resolucion=nombre, n=cambiadas), aviso=False)
        else:
            self.avisar(t("texturas_sin_cambios", resolucion=nombre), aviso=False)

    def _botones_crecer(self):
        fila = QtWidgets.QHBoxLayout()
        self.boton_crecer = QtWidgets.QPushButton(t("crecer"))
        self.boton_crecer.setObjectName("principal")
        self.boton_crecer.setToolTip(t("ayuda_crecer"))
        self.boton_crecer.clicked.connect(self._crecer)
        self.boton_mas = QtWidgets.QPushButton(t("crecer_mas"))
        self.boton_mas.setToolTip(t("ayuda_crecer_mas"))
        self.boton_mas.clicked.connect(self._crecer_mas)
        self.boton_reiniciar = QtWidgets.QPushButton(t("reiniciar"))
        self.boton_reiniciar.setToolTip(t("ayuda_reiniciar"))
        self.boton_reiniciar.clicked.connect(self._reiniciar)
        for boton in (self.boton_crecer, self.boton_mas, self.boton_reiniciar):
            boton.setMinimumHeight(32)
            fila.addWidget(boton)
        return fila

    def _avanzados(self):
        self.plegable_avanzados = Plegable(t("avanzados"))
        caja = QtWidgets.QVBoxLayout(self.plegable_avanzados.contenido)
        caja.setContentsMargins(12, 0, 0, 0)
        self.grupos = {}
        for grupo in aj.GRUPOS_AVANZADOS:
            plegable = Plegable(t("grupo_" + grupo))
            formulario = self._formulario(plegable.contenido)
            for control in aj.controles_del_grupo(grupo):
                self._fila(formulario, control)
            if grupo == "hojas":
                formulario.addRow(QtWidgets.QLabel(t("ajuste_hoja_propia")), self._hoja_propia())
            caja.addWidget(plegable)
            self.grupos[grupo] = plegable
        return self.plegable_avanzados

    def _hoja_propia(self):
        widget = QtWidgets.QWidget()
        widget.setToolTip(t("ayuda_hoja_propia"))
        fila = QtWidgets.QHBoxLayout(widget)
        fila.setContentsMargins(0, 0, 0, 0)
        self.estado_hoja = QtWidgets.QLabel()
        self.boton_hoja = QtWidgets.QPushButton(t("usar_seleccion"))
        self.boton_hoja.clicked.connect(self._usar_hoja_propia)
        self.boton_quitar_hoja = QtWidgets.QPushButton("×")
        self.boton_quitar_hoja.setFixedWidth(24)
        self.boton_quitar_hoja.setToolTip(t("ayuda_quitar_hoja_propia"))
        self.boton_quitar_hoja.clicked.connect(self._quitar_hoja_propia)
        fila.addWidget(self.estado_hoja, 1)
        fila.addWidget(self.boton_hoja)
        fila.addWidget(self.boton_quitar_hoja)
        return widget

    def _pie(self):
        fila = QtWidgets.QHBoxLayout()
        self.boton_malla = QtWidgets.QPushButton(t("crear_malla"))
        self.boton_malla.setObjectName("principal")
        self.boton_malla.setMinimumHeight(36)
        self.boton_malla.setToolTip(t("ayuda_crear_malla"))
        self.boton_malla.clicked.connect(self._crear_malla)
        self.boton_exportar = QtWidgets.QPushButton(t("exportar"))
        self.boton_exportar.setMinimumHeight(36)
        self.boton_exportar.setToolTip(t("ayuda_exportar"))
        self.boton_exportar.clicked.connect(self._exportar)
        self.estado_pie = QtWidgets.QLabel()
        self.estado_pie.setWordWrap(True)
        fila.addWidget(self.boton_malla, 1)
        fila.addWidget(self.boton_exportar)
        fila.addWidget(self.estado_pie, 1)
        return fila

    # ------------------------------------------------------------ valores
    def _poner_controles(self, valores):
        for clave, widget in self.controles.items():
            widget.poner(valores[clave])

    def _al_cambiar(self, clave, valor):
        self.sesion.ajustes[clave] = valor
        self._actualizar()

    def leer_controles(self):
        return {clave: widget.valor() for clave, widget in self.controles.items()}

    # ------------------------------------------------------------ estado
    def _actualizar(self):
        s = self.sesion
        superficies = s.superficies_validas()
        hay = bool(superficies)
        if not superficies:
            self.estado_superficie.setText(t("superficie_ninguna"))
        elif len(superficies) == 1:
            self.estado_superficie.setText(t("superficie_una", nombre=superficies[0].split("|")[-1]))
        else:
            nombres = ", ".join(n.split("|")[-1] for n in superficies[:3])
            if len(superficies) > 3:
                nombres += "…"
            self.estado_superficie.setText(t("superficie_varias", n=len(superficies),
                                             nombres=nombres))
        origenes = len(s.origenes()) if hay else 0
        self.caja_origen.setEnabled(hay)
        self.boton_quitar.setEnabled(origenes > 0)
        if not hay:
            self.estado_origen.setText(t("origen_antes_superficie"))
        elif origenes == 0:
            self.estado_origen.setText(t("origen_ninguno"))
        elif origenes == 1:
            self.estado_origen.setText(t("origen_uno"))
        else:
            self.estado_origen.setText(t("origen_varios", n=origenes))
        self.boton_crecer.setEnabled(hay)
        self.boton_malla.setEnabled(hay)
        crecido = s.hay_crecimiento()
        self.boton_mas.setEnabled(hay and crecido)
        self.boton_reiniciar.setEnabled(crecido)
        if s.hoja_propia:
            self.estado_hoja.setText(s.hoja_propia.split("|")[-1])
        else:
            self.estado_hoja.setText(t("hoja_propia_ninguna"))
        self.boton_quitar_hoja.setEnabled(bool(s.hoja_propia))
        self._actualizar_pie()

    def _actualizar_pie(self):
        estado = self.sesion.estado()
        if not estado.get("crecido"):
            self.estado_pie.setText(t("pie_sin_crecer"))
            self.estado_pie.setStyleSheet("")
            return
        texto = t("pie_crecido", hojas=_numero(estado["hojas"]),
                  carga=t("carga_" + estado["carga"]))
        if not estado["al_dia"]:
            texto += "\n" + t("pie_cambiado")
        self.estado_pie.setText(texto)
        self.estado_pie.setStyleSheet("color: {};".format(_COLOR_CARGA[estado["carga"]]))

    def avisar(self, texto, aviso=True):
        """Enseña un mensaje bajo los botones (y en la línea de avisos de Maya)."""
        self.mensaje.setText(texto)
        self.mensaje.setStyleSheet("color: {};".format(_COLOR_AVISO if aviso else _COLOR_BIEN))
        if EN_MAYA and aviso:
            cmds.warning(texto)

    def _hacer(self, funcion, *args):
        """Llama a ``funcion``; si avisa de algo, lo enseña. Devuelve su resultado o None."""
        try:
            return funcion(*args)
        except Aviso as aviso:
            self.avisar(str(aviso))
            return None
        finally:
            self._actualizar()

    # ------------------------------------------------------------ pasos 1 y 2
    def _usar_seleccion(self):
        mallas = self._hacer(self.sesion.usar_seleccion)
        if mallas:
            self.avisar(t("superficie_lista", n=len(mallas)), aviso=False)

    def _clic_visor(self, activo):
        if not EN_MAYA:
            return
        from . import herramienta

        if activo:
            herramienta.activar(self._al_clic)
            self.avisar(t("clic_instrucciones"), aviso=False)
        else:
            herramienta.desactivar()

    def _al_clic(self, x, y, panel=None):
        if self._hacer(self.sesion.anadir_origen_en, x, y, panel):
            self.avisar(t("origen_colocado"), aviso=False)

    def _quitar_origenes(self):
        self._hacer(self.sesion.borrar_origenes)

    def _herramienta_cambiada(self):
        from . import herramienta

        if self.boton_clic.isChecked() and not herramienta.activa():
            self.boton_clic.blockSignals(True)
            self.boton_clic.setChecked(False)
            self.boton_clic.blockSignals(False)

    def _usar_hoja_propia(self):
        nombre = self._hacer(self.sesion.usar_hoja_propia)
        if nombre:
            self.avisar(t("hoja_propia_lista", nombre=nombre.split("|")[-1]), aviso=False)

    def _quitar_hoja_propia(self):
        self._hacer(self.sesion.quitar_hoja_propia)

    # ------------------------------------------------------------ crecer
    def _informe(self, resultado, clave):
        if resultado is None:
            return
        estado = self.sesion.estado()
        partes = [t(clave, ramas=_numero(estado.get("ramas", 0)),
                    hojas=_numero(resultado.get("hojas") or estado.get("hojas", 0)),
                    segundos="{:.1f}".format(resultado["segundos"]).replace(".", t("coma")))]
        if resultado.get("cancelado"):
            partes.append(t("detenido"))
        if resultado.get("limite"):
            partes.append(t("limite_corto"))
        if resultado.get("alargado"):
            partes.append(t("crecer_mas_alargado", largo=_numero(resultado["alargado"])))
        motivo = resultado.get("motivo")
        if motivo in ("espacio", "largo", "superficie") and not resultado.get("cancelado") \
                and resultado["hechos"] < resultado["pedidos"]:
            partes.append(t("parada_" + motivo, pasos=resultado["paso_final"]))
        aviso = bool(resultado.get("cancelado") or resultado.get("limite"))
        self.avisar(" ".join(partes), aviso=aviso)

    def _crecer(self):
        self._informe(self._hacer(self.sesion.crecer), "resultado_crecer")

    def _crecer_mas(self):
        resultado = self._hacer(self.sesion.crecer_mas)
        if resultado is not None:
            self._poner_controles(self.sesion.ajustes)
        self._informe(resultado, "resultado_crecer")

    def _reiniciar(self):
        self._hacer(self.sesion.reiniciar)
        self.avisar(t("reiniciado"), aviso=False)

    def _crear_malla(self):
        previstas = self.sesion.hojas_previstas()
        if aj.carga(previstas) == "alta":
            respuesta = QtWidgets.QMessageBox.question(
                self, t("ventana_titulo"), t("confirmar_carga_alta", hojas=_numero(previstas)))
            if respuesta != QtWidgets.QMessageBox.Yes:
                return
        resultado = self._hacer(self.sesion.crear_malla)
        if resultado is not None and resultado.get("planta"):
            self._informe(resultado, "resultado_malla")
        elif resultado is not None:
            self.avisar(t("malla_cancelada"))

    def _exportar(self):
        if self.sesion.planta_para_exportar() is None:
            self.avisar(t("sin_planta_seleccionada"))
            return
        ruta = self._pedir_ruta_exportar()
        if not ruta:
            return
        self._ultima_exportacion = ruta
        informe = self._hacer(self.sesion.exportar, ruta)
        if informe is None:
            return
        self.avisar(t("exportado", archivo=os.path.basename(informe["ruta"]),
                      n=len(informe["texturas"]),
                      carpeta=os.path.basename(informe["carpeta"])), aviso=False)
        if informe["sin_color"]:
            self.avisar(t("exportado_sin_color", juegos=", ".join(informe["sin_color"])))

    def _pedir_ruta_exportar(self):
        """Ruta del archivo (con .fbx o .abc), o None si se cancela."""
        ruta, filtro = QtWidgets.QFileDialog.getSaveFileName(
            self, t("exportar_titulo"), self._ultima_exportacion or "trepadora_planta.fbx",
            t("exportar_filtro"))
        if not ruta:
            return None
        if not os.path.splitext(ruta)[1]:
            ruta += ".abc" if "*.abc" in (filtro or "") else ".fbx"
        return ruta

    # ------------------------------------------------------------ preajustes
    def carpeta_preajustes(self):
        base = cmds.internalVar(userAppDir=True) if EN_MAYA else None
        return aj.carpeta_usuario(base)

    def _cargar_preajustes(self, elegir=None):
        incluidos = aj.preajustes_incluidos()
        propios = aj.preajustes_de_usuario(self.carpeta_preajustes())
        self.preajustes = incluidos + propios
        combo = self.combo_preajustes
        combo.blockSignals(True)
        combo.clear()
        for i, p in enumerate(self.preajustes):
            if i == len(incluidos) and propios:
                combo.insertSeparator(combo.count())
            nombre = t(p.clave_nombre) if p.clave_nombre else p.nombre
            combo.addItem(nombre, i)
        combo.setCurrentIndex(-1)
        if hasattr(combo, "setPlaceholderText"):
            combo.setPlaceholderText(t("preajustes_elegir"))
        if elegir is not None:
            for i, p in enumerate(self.preajustes):
                if p.ruta == elegir:
                    combo.setCurrentIndex(combo.findData(i))
        combo.blockSignals(False)

    def _preajuste_actual(self):
        indice = self.combo_preajustes.currentData()
        if indice is None:
            return None
        return self.preajustes[indice]

    def _elegir_preajuste(self, _posicion=None):
        preajuste = self._preajuste_actual()
        if preajuste is None:
            return
        self.aplicar_ajustes(preajuste.ajustes)
        self.sesion.extra = {}
        nombre = t(preajuste.clave_nombre) if preajuste.clave_nombre else preajuste.nombre
        self.avisar(t("preajuste_aplicado", nombre=nombre), aviso=False)

    def aplicar_ajustes(self, valores):
        ajustes, _ = aj.limpiar(valores)
        self.sesion.ajustes = ajustes
        self._poner_controles(ajustes)
        self._actualizar()

    def _menu_preajustes(self):
        actual = self._preajuste_actual()
        self.accion_borrar.setEnabled(bool(actual and not actual.incluido))

    def _guardar_preajuste(self):
        nombre, ok = QtWidgets.QInputDialog.getText(self, t("preajuste_guardar"),
                                                    t("preajuste_nombre"))
        nombre = (nombre or "").strip()
        if not ok or not nombre:
            return
        ruta = os.path.join(self.carpeta_preajustes(), aj.nombre_de_archivo(nombre))
        if os.path.exists(ruta):
            respuesta = QtWidgets.QMessageBox.question(
                self, t("preajuste_guardar"), t("preajuste_existe", nombre=nombre))
            if respuesta != QtWidgets.QMessageBox.Yes:
                return
        try:
            aj.guardar_preajuste(ruta, nombre, self.sesion.ajustes)
        except OSError as error:
            self.avisar(t("preajuste_error", error=error))
            return
        self._cargar_preajustes(elegir=ruta)
        self.avisar(t("preajuste_guardado", nombre=nombre), aviso=False)

    def _importar_preajuste(self):
        ruta, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, t("preajuste_importar"), "", t("preajuste_filtro"))
        if not ruta:
            return
        try:
            preajuste = aj.leer_preajuste(ruta)
            destino = os.path.join(self.carpeta_preajustes(),
                                   aj.nombre_de_archivo(preajuste.nombre))
            aj.guardar_preajuste(destino, preajuste.nombre, preajuste.ajustes)
        except (OSError, ValueError) as error:
            self.avisar(t("preajuste_no_valido", error=error))
            return
        self._cargar_preajustes(elegir=destino)
        self._elegir_preajuste()

    def _exportar_preajuste(self):
        actual = self._preajuste_actual()
        nombre = (t(actual.clave_nombre) if actual and actual.clave_nombre
                  else actual.nombre if actual else t("preajuste_sin_nombre"))
        ruta, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, t("preajuste_exportar"), aj.nombre_de_archivo(nombre), t("preajuste_filtro"))
        if not ruta:
            return
        try:
            aj.guardar_preajuste(ruta, nombre, self.sesion.ajustes)
        except OSError as error:
            self.avisar(t("preajuste_error", error=error))
            return
        self.avisar(t("preajuste_exportado", ruta=ruta), aviso=False)

    def _borrar_preajuste(self):
        actual = self._preajuste_actual()
        if not actual or actual.incluido:
            return
        respuesta = QtWidgets.QMessageBox.question(
            self, t("preajuste_borrar"), t("preajuste_confirmar_borrar", nombre=actual.nombre))
        if respuesta != QtWidgets.QMessageBox.Yes:
            return
        try:
            os.remove(actual.ruta)
        except OSError as error:
            self.avisar(t("preajuste_error", error=error))
            return
        self._cargar_preajustes()

    def _abrir_carpeta(self):
        carpeta = self.carpeta_preajustes()
        if not os.path.isdir(carpeta):
            os.makedirs(carpeta)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(carpeta))

    def _por_defecto(self):
        self.aplicar_ajustes(aj.valores_por_defecto())
        self.sesion.extra = {}
        self.combo_preajustes.setCurrentIndex(-1)
        self.avisar(t("valores_por_defecto"), aviso=False)

    def _ajustes_de_planta(self):
        resultado = self._hacer(self.sesion.ajustes_de_planta)
        if resultado:
            ajustes, extra = resultado
            self.aplicar_ajustes(ajustes)
            self.sesion.extra = extra
            self.combo_preajustes.setCurrentIndex(-1)
            self.avisar(t("ajustes_de_planta_cargados", semilla=ajustes["semilla"]),
                        aviso=False)

    # ------------------------------------------------------------ escena
    def cambiar_sesion(self, sesion):
        self.sesion = sesion
        self._poner_controles(sesion.ajustes)
        self.combo_preajustes.setCurrentIndex(-1)
        self.mensaje.setText("")
        self._actualizar()

    def _escena_nueva(self):
        from ..sesion import Sesion

        if not _valida(self):
            return
        try:
            self.cambiar_sesion(Sesion())
        except Exception:
            import traceback

            traceback.print_exc()

    def _deshecho(self):
        """Tras deshacer o rehacer: superficies, hoja propia y vista previa, como en la escena."""
        if not _valida(self):
            return
        self.sesion.revisar_escena()
        self._actualizar()

    def escena_de_prueba(self, nombre):
        self._hacer(self.sesion.preparar_escena_de_prueba, nombre)
        self._poner_controles(self.sesion.ajustes)
        # La escena trae sus propios ajustes: ya no corresponden al preajuste elegido.
        self.combo_preajustes.setCurrentIndex(-1)
        self._actualizar()
        self.avisar(t("escena_prueba_lista"), aviso=False)

    def conectar_maya(self):
        """Avisos de Maya: escena nueva o abierta, cambio de herramienta, deshacer."""
        if not EN_MAYA or self._trabajos:
            return
        padre = CONTROL if cmds.workspaceControl(CONTROL, exists=True) else None
        eventos = (("SceneOpened", self._escena_nueva), ("NewSceneOpened", self._escena_nueva),
                   ("ToolChanged", self._herramienta_cambiada), ("Undo", self._deshecho),
                   ("Redo", self._deshecho))
        for evento, funcion in eventos:
            opciones = {"event": [evento, funcion]}
            if padre:
                opciones["parent"] = padre
            self._trabajos.append(cmds.scriptJob(**opciones))

    def desconectar_maya(self):
        if not EN_MAYA:
            return
        for trabajo in self._trabajos:
            if cmds.scriptJob(exists=trabajo):
                cmds.scriptJob(kill=trabajo, force=True)
        self._trabajos = []
        try:
            from . import herramienta

            herramienta.desactivar()
        except RuntimeError:
            pass

    def recordar(self):
        if EN_MAYA:
            import json

            cmds.optionVar(stringValue=("trepadoraUltimosAjustes",
                                        json.dumps(self.sesion.ajustes)))

    def dockCloseEventTriggered(self):
        self.recordar()
        self.desconectar_maya()

    def closeEvent(self, evento):
        self.recordar()
        self.desconectar_maya()
        super(Ventana, self).closeEvent(evento)


# ---------------------------------------------------------------- abrir
_ventana = None


def _valida(widget):
    try:
        widget.objectName()
        return True
    except RuntimeError:
        return False


def mostrar(restaurar=False):
    """Abre la ventana (o la trae delante si ya estaba abierta) y la devuelve."""
    global _ventana
    if restaurar:
        # Maya vuelve a crear el panel acoplado al arrancar (ver uiScript).
        import maya.OpenMayaUI as omui

        padre = omui.MQtUtil.getCurrentParent()
        _ventana = Ventana()
        puntero = omui.MQtUtil.findControl(_ventana.objectName())
        omui.MQtUtil.addWidgetToMayaLayout(int(puntero), int(padre))
        _ventana.conectar_maya()
        return _ventana
    if EN_MAYA and cmds.workspaceControl(CONTROL, exists=True):
        if _ventana is not None and _valida(_ventana):
            cmds.workspaceControl(CONTROL, edit=True, restore=True)
            cmds.workspaceControl(CONTROL, edit=True, visible=True)
            return _ventana
        cmds.deleteUI(CONTROL)
    _ventana = Ventana()
    _ventana.show(dockable=True, floating=True, area="right", retain=False, width=380,
                  height=820, uiScript="import trepadora.ui.ventana as v\nv.mostrar(restaurar=True)")
    _ventana.conectar_maya()
    return _ventana


def cerrar():
    """Cierra la ventana si está abierta (al descargar el plugin)."""
    global _ventana
    if _ventana is not None and _valida(_ventana):
        _ventana.desconectar_maya()
    if EN_MAYA and cmds.workspaceControl(CONTROL, exists=True):
        cmds.deleteUI(CONTROL)
    _ventana = None
