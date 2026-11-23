"""Lo que hace la ventana, sin la ventana: superficie, orígenes, crecer y crear la malla.

La ventana solo llama a estos métodos y enseña su resultado. Los errores que
debe ver el estudiante llegan como ``Aviso``, con el texto ya traducido y
diciendo qué hacer.

Lo que la escena tiene que recordar (superficies, orígenes, hoja propia y los
últimos ajustes usados) se guarda en el grupo ``trepadora_origenes_grp``, así
que al abrir la escena otro día la ventana sigue donde estaba. Cada planta
creada guarda además los ajustes y la semilla con que se hizo, para poder
repetirla o corregir el trabajo.
"""

import json
import math
import time

import maya.api.OpenMaya as om
from maya import cmds

from . import ajustes as aj
from .ajustes import Aviso  # noqa: F401 (la ventana lo importa de aquí o de ajustes)
from . import escenas, prototipo
from dataclasses import fields

from .crecimiento import Crecimiento, Parametros
from .i18n import t

GRUPO_DATOS = "trepadora_origenes_grp"
ATR_SUPERFICIES = "trepadoraSuperficies"
ATR_AJUSTES = "trepadoraAjustes"
ATR_HOJA_PROPIA = "trepadoraHojaPropia"
ATR_PLANTA = "trepadoraAjustes"
OPCION_ULTIMOS = "trepadoraUltimosAjustes"
# Paso de crecimiento por defecto: esta fracción de la diagonal de la superficie.
FRACCION_PASO = 1.0 / 150.0
# Lo que añade «Crecer más», como fracción de los pasos ya hechos (con un mínimo).
FRACCION_MAS = 0.35
MINIMO_MAS = 40


def _largo(nombre):
    return (cmds.ls(nombre, long=True) or [nombre])[0]


def _mallas_de(nodos):
    """Transformaciones con malla dentro de ``nodos`` (también dentro de grupos)."""
    resultado = []
    for nodo in nodos:
        if cmds.nodeType(nodo) == "mesh":
            nodo = cmds.listRelatives(nodo, parent=True, fullPath=True)[0]
        formas = cmds.listRelatives(nodo, allDescendents=True, fullPath=True, type="mesh",
                                    noIntermediate=True) or []
        for forma in formas:
            if cmds.getAttr(forma + ".intermediateObject"):
                continue
            padre = cmds.listRelatives(forma, parent=True, fullPath=True)[0]
            if padre not in resultado and not _es_de_trepadora(padre):
                resultado.append(padre)
    return resultado


def _es_de_trepadora(nodo):
    """True si ``nodo`` es parte de una planta, de la vista previa o de los orígenes."""
    grupos = (GRUPO_DATOS, prototipo.GRUPO_PLANTA, prototipo.GRUPO_VISTA_PREVIA)
    return any(parte.startswith(grupos) for parte in nodo.split("|"))


def _es_localizador(nodo):
    formas = cmds.listRelatives(nodo, shapes=True, fullPath=True) or []
    return any(cmds.nodeType(f) == "locator" for f in formas)


def _corto(nombre):
    return nombre.split("|")[-1]


class Sesion:
    """El estado de la ventana: superficies, orígenes, ajustes y la planta en crecimiento."""

    def __init__(self, ajustes=None):
        self.superficies = []
        self.hoja_propia = None
        self.ajustes = aj.valores_por_defecto()
        # Ajustes del crecimiento que no están en la ventana (los usan las
        # escenas de prueba). Se olvidan al elegir un preajuste.
        self.extra = {}
        self._crecimiento = None
        self._firma = None
        self._paso = None
        self._pasos_hechos = 0
        self._pasos_pedidos = 0
        self.vista_previa = None
        self.ultima_planta = None
        self.leer_escena()
        if ajustes is not None:
            self.ajustes, _ = aj.limpiar(ajustes)

    # --------------------------------------------------------------- escena
    def leer_escena(self):
        """Recupera lo guardado en la escena, o los últimos ajustes usados en Maya."""
        guardados = None
        if cmds.objExists(prototipo.GRUPO_VISTA_PREVIA):
            # Líneas de una vista previa guardada: Crecer o Reiniciar las sustituyen.
            self.vista_previa = _largo(prototipo.GRUPO_VISTA_PREVIA)
        if cmds.objExists(GRUPO_DATOS):
            self.superficies = [s for s in self._leer_json(ATR_SUPERFICIES, [])
                                if isinstance(s, str) and cmds.objExists(s)]
            propia = self._leer_json(ATR_HOJA_PROPIA, None)
            self.hoja_propia = propia if propia and cmds.objExists(propia) else None
            guardados = self._leer_json(ATR_AJUSTES, None)
        if guardados is None and cmds.optionVar(exists=OPCION_ULTIMOS):
            try:
                guardados = json.loads(cmds.optionVar(query=OPCION_ULTIMOS))
            except (TypeError, ValueError):
                guardados = None
        if isinstance(guardados, dict):
            self.extra = dict(guardados.pop("_extra", {}) or {})
            self.ajustes, _ = aj.limpiar(guardados)

    def _leer_json(self, atributo, defecto):
        if not cmds.attributeQuery(atributo, node=GRUPO_DATOS, exists=True):
            return defecto
        try:
            return json.loads(cmds.getAttr(GRUPO_DATOS + "." + atributo) or "null")
        except (TypeError, ValueError):
            return defecto

    def _grupo_datos(self):
        if not cmds.objExists(GRUPO_DATOS):
            cmds.group(empty=True, name=GRUPO_DATOS, world=True)
        return GRUPO_DATOS

    def _guardar(self, atributo, valor):
        grupo = self._grupo_datos()
        if not cmds.attributeQuery(atributo, node=grupo, exists=True):
            cmds.addAttr(grupo, longName=atributo, dataType="string")
        cmds.setAttr(grupo + "." + atributo, json.dumps(valor, ensure_ascii=False),
                     type="string")

    def guardar_ajustes(self):
        """Recuerda los ajustes en la escena y para la próxima vez que se abra Maya."""
        datos = dict(self.ajustes)
        if self.extra:
            datos["_extra"] = self.extra
        if cmds.objExists(GRUPO_DATOS) or self.superficies:
            self._guardar(ATR_AJUSTES, datos)
        cmds.optionVar(stringValue=(OPCION_ULTIMOS, json.dumps(datos)))

    # ------------------------------------------------------------ superficie
    def usar_seleccion(self):
        """Paso 1: las mallas seleccionadas son la superficie por la que trepa.

        Si entre lo seleccionado hay localizadores, se añaden como orígenes.
        """
        seleccion = cmds.ls(selection=True, long=True) or []
        mallas = _mallas_de(seleccion)
        if not mallas:
            raise Aviso(t("falta_superficie"))
        cmds.undoInfo(openChunk=True, chunkName="Trepadora")
        try:
            self.superficies = mallas
            self._guardar(ATR_SUPERFICIES, mallas)
            for nodo in seleccion:
                if _es_localizador(nodo) and not _es_de_trepadora(nodo):
                    self._nuevo_origen(cmds.xform(nodo, query=True, worldSpace=True,
                                                  translation=True))
        finally:
            cmds.undoInfo(closeChunk=True)
        self._olvidar()
        return mallas

    def superficies_validas(self):
        self.superficies = [s for s in self.superficies if cmds.objExists(s)]
        return self.superficies

    def _exigir_superficie(self):
        if not self.superficies_validas():
            raise Aviso(t("falta_superficie"))

    # --------------------------------------------------------------- origen
    def origenes(self):
        """Los localizadores de origen que hay en la escena."""
        if not cmds.objExists(GRUPO_DATOS):
            return []
        hijos = cmds.listRelatives(GRUPO_DATOS, children=True, fullPath=True,
                                   type="transform") or []
        return [h for h in hijos if _es_localizador(h)]

    def punto_en_superficie(self, x, y):
        """Punto de la superficie bajo el píxel (x, y) del visor activo, o None."""
        import maya.api.OpenMayaUI as omui

        vista = omui.M3dView.active3dView()
        origen, direccion = om.MPoint(), om.MVector()
        vista.viewToWorld(int(x), int(y), origen, direccion)
        return self.punto_en_rayo(origen, direccion)

    def punto_en_rayo(self, origen, direccion):
        """Primer punto de la superficie que toca el rayo, o None."""
        self._exigir_superficie()
        fuente = om.MFloatPoint(origen[0], origen[1], origen[2])
        rumbo = om.MFloatVector(direccion[0], direccion[1], direccion[2])
        mejor = None
        lista = om.MSelectionList()
        for nombre in self.superficies:
            lista.add(nombre)
        for i in range(lista.length()):
            camino = lista.getDagPath(i)
            camino.extendToShape()
            try:
                resultado = om.MFnMesh(camino).closestIntersection(
                    fuente, rumbo, om.MSpace.kWorld, 1e9, False)
            except RuntimeError:
                continue
            if not resultado or resultado[2] < 0:
                continue
            punto, distancia = resultado[0], resultado[1]
            if mejor is None or distancia < mejor[0]:
                mejor = (distancia, (punto.x, punto.y, punto.z))
        return mejor[1] if mejor else None

    def anadir_origen_en(self, x, y):
        """Paso 2: coloca un origen donde se hizo clic. Devuelve el localizador."""
        punto = self.punto_en_superficie(x, y)
        if punto is None:
            raise Aviso(t("origen_fuera"))
        return self._nuevo_origen(punto)

    def anadir_origen(self, punto):
        self._exigir_superficie()
        return self._nuevo_origen(punto)

    def _nuevo_origen(self, punto):
        grupo = self._grupo_datos()
        loc = cmds.spaceLocator(name="trepadora_origen1")[0]
        cmds.move(punto[0], punto[1], punto[2], loc, absolute=True, worldSpace=True)
        tam = self._paso_automatico() * 6.0 if self.superficies else 1.0
        forma = cmds.listRelatives(loc, shapes=True, fullPath=True)[0]
        cmds.setAttr(forma + ".localScale", tam, tam, tam, type="double3")
        loc = _largo(cmds.parent(loc, grupo)[0])
        self._olvidar()
        return loc

    def borrar_origenes(self):
        origenes = self.origenes()
        if origenes:
            cmds.delete(origenes)
        self._olvidar()

    # ------------------------------------------------------------ hoja propia
    def usar_hoja_propia(self):
        """La malla seleccionada será la hoja. Devuelve su nombre."""
        mallas = _mallas_de(cmds.ls(selection=True, long=True) or [])
        if not mallas:
            raise Aviso(t("falta_hoja_propia"))
        self.hoja_propia = mallas[0]
        self._guardar(ATR_HOJA_PROPIA, self.hoja_propia)
        return self.hoja_propia

    def quitar_hoja_propia(self):
        self.hoja_propia = None
        if cmds.objExists(GRUPO_DATOS):
            self._guardar(ATR_HOJA_PROPIA, None)

    # --------------------------------------------------------------- crecer
    def _paso_automatico(self):
        caja = cmds.exactWorldBoundingBox(self.superficies)
        diagonal = math.sqrt(sum((caja[i + 3] - caja[i]) ** 2 for i in range(3)))
        return max(diagonal * FRACCION_PASO, 1e-3)

    def _firma_actual(self):
        crecimiento, _, planta = aj.repartir(self.ajustes)
        crecimiento.pop("pasos")
        posiciones = [tuple(round(c, 4) for c in cmds.xform(o, query=True, worldSpace=True,
                                                             translation=True))
                      for o in self.origenes()]
        return json.dumps([self.superficies, posiciones, crecimiento, planta["escala"],
                           self.extra], sort_keys=True)

    def _olvidar(self):
        self._crecimiento = None
        self._firma = None
        self._pasos_hechos = 0
        self._pasos_pedidos = 0

    def _nuevo_crecimiento(self):
        from .superficie_maya import SuperficieMaya

        self._exigir_superficie()
        crecimiento, _, planta = aj.repartir(self.ajustes)
        paso = self._paso_automatico() * planta["escala"]
        base = {"longitud_paso": paso, "distancia_adherencia": paso * 3.0,
                "separacion": paso * 0.05, "radio_espacio": paso * 2.0}
        base.update(self.extra)
        base.update(crecimiento)
        nuevo = Crecimiento(SuperficieMaya(self.superficies), Parametros(**base))
        origenes = self.origenes()
        for o in origenes:
            nuevo.anadir_origen(cmds.xform(o, query=True, worldSpace=True, translation=True))
        if not origenes:
            caja = cmds.exactWorldBoundingBox(self.superficies)
            nuevo.anadir_origen(((caja[0] + caja[3]) / 2.0, caja[1], (caja[2] + caja[5]) / 2.0))
        self._crecimiento, self._paso = nuevo, paso
        self._firma = self._firma_actual()
        self._pasos_hechos = 0
        self._pasos_pedidos = 0
        return nuevo

    def _hacer_crecer(self, pasos):
        """Crece ``pasos`` más con barra de progreso. Devuelve el resultado para la ventana."""
        inicio = time.time()
        hechos, cancelado = prototipo.crecer_con_progreso(self._crecimiento, pasos)
        self._pasos_hechos += hechos
        self._pasos_pedidos += pasos
        return {"cancelado": cancelado, "hechos": hechos, "pedidos": pasos,
                "paso_final": self._pasos_hechos, "motivo": self.motivo_parada(),
                "limite": self._crecimiento.limite_alcanzado,
                "segundos": time.time() - inicio}

    def quedan_ramas_vivas(self):
        return self._crecimiento is not None and any(r.viva for r in self._crecimiento.ramas)

    def motivo_parada(self):
        """Si todas las ramas han parado, por qué: espacio, largo, superficie o limite."""
        if self._crecimiento is None or self.quedan_ramas_vivas():
            return None
        if self._crecimiento.limite_alcanzado:
            return "limite"
        motivos = self._crecimiento.motivos_de_parada()
        motivos["superficie"] = motivos.pop("aire", 0) + motivos.pop("suelo", 0)
        motivo = max(sorted(motivos), key=motivos.get)
        return motivo if motivos[motivo] > 0 else "espacio"

    def crecer(self):
        """Crece desde cero con los ajustes actuales y dibuja la vista previa (líneas)."""
        cmds.undoInfo(openChunk=True, chunkName="Trepadora")
        try:
            self._nuevo_crecimiento()
            resultado = self._hacer_crecer(self.ajustes["pasos"])
            self._dibujar_vista_previa()
            self.guardar_ajustes()
        finally:
            cmds.undoInfo(closeChunk=True)
        return resultado

    def crecer_mas(self):
        """Hace la planta más grande.

        Si nada ha cambiado, sigue creciendo la planta actual (es lo mismo que
        crecer desde cero con más Tamaño, pero más rápido). Si se cambió algún
        ajuste, vuelve a crecer hasta más allá. Si todas las ramas pararon por
        su largo, las alarga (sube el Largo de las ramas) y vuelve a crecer.
        """
        maximo = aj.POR_CLAVE["pasos"].maximo
        mas = max(MINIMO_MAS, int(self._pasos_hechos * FRACCION_MAS))
        sigue = self._crecimiento is not None and self._firma == self._firma_actual()
        largo = None
        if sigue and not self.quedan_ramas_vivas():
            largo = self._largo_para_crecer_mas()
            sigue = False
            total = min(maximo, max(self.ajustes["pasos"], self._pasos_hechos + mas))
        else:
            total = (self._pasos_pedidos if sigue else self.ajustes["pasos"]) + mas
            if total > maximo:
                mas -= total - maximo
                total = maximo
            if mas <= 0:
                raise Aviso(t("crecer_mas_maximo"))
        cmds.undoInfo(openChunk=True, chunkName="Trepadora")
        try:
            if sigue:
                resultado = self._hacer_crecer(mas)
            else:
                if largo is not None:
                    self.ajustes["longitud_max"] = largo
                self._nuevo_crecimiento()
                resultado = self._hacer_crecer(total)
            self.ajustes["pasos"] = self._pasos_pedidos
            self._dibujar_vista_previa()
            self.guardar_ajustes()
        finally:
            cmds.undoInfo(closeChunk=True)
        resultado["alargado"] = largo
        return resultado

    def _largo_para_crecer_mas(self):
        """Nuevo Largo de las ramas si pararon por su largo; si no, avisa de por qué."""
        motivo = self.motivo_parada()
        control = aj.POR_CLAVE["longitud_max"]
        if motivo == "largo" and self.ajustes["longitud_max"] < control.maximo:
            return aj.ajustar(control, self.ajustes["longitud_max"] * (1.0 + FRACCION_MAS))
        raise Aviso(t("crecer_mas_" + {"largo": "largo_maximo"}.get(motivo, motivo)))

    def reiniciar(self):
        """Borra la vista previa y olvida lo crecido (superficies y orígenes se quedan)."""
        self._borrar_vista_previa()
        self._olvidar()

    def _borrar_vista_previa(self):
        if self.vista_previa and cmds.objExists(self.vista_previa):
            cmds.delete(self.vista_previa)
        self.vista_previa = None

    def _dibujar_vista_previa(self):
        self._borrar_vista_previa()
        self.vista_previa = _largo(prototipo.crear_vista_previa(self._crecimiento.curvas()))

    def hay_crecimiento(self):
        return self._crecimiento is not None

    def al_dia(self):
        """True si lo crecido corresponde a los ajustes, superficies y orígenes actuales.

        Si la planta paró sola, cualquier Tamaño a partir del paso en que paró
        da la misma planta.
        """
        if self._crecimiento is None or self._firma != self._firma_actual():
            return False
        pasos = self.ajustes["pasos"]
        if self._pasos_pedidos == pasos:
            return True
        return not self.quedan_ramas_vivas() and self._pasos_hechos <= pasos

    # ---------------------------------------------------------- crear malla
    def crear_malla(self):
        """Paso final: tallos con grosor, hojas y materiales. Devuelve el resultado."""
        self._exigir_superficie()
        inicio = time.time()
        cmds.undoInfo(openChunk=True, chunkName="Trepadora")
        try:
            crecido = None
            if not self.al_dia():
                self._nuevo_crecimiento()
                crecido = self._hacer_crecer(self.ajustes["pasos"])
                if crecido["cancelado"]:
                    return dict(crecido, planta=None, hojas=0)
            _, hojas, planta = aj.repartir(self.ajustes)
            resumen = {}
            grupo = prototipo.crear_planta(
                self._crecimiento, self._paso, hojas, planta["grosor"],
                self.ajustes["semilla"], instancias=planta["instancias"],
                forma_hoja=planta["forma_hoja"], tipo_tallo=planta["tipo_tallo"],
                hoja_propia=self.hoja_propia, lados=planta["lados"], resumen=resumen)
            grupo = _largo(grupo)
            datos = dict(self.ajustes, _extra=self.extra) if self.extra else dict(self.ajustes)
            cmds.addAttr(grupo, longName=ATR_PLANTA, dataType="string")
            cmds.setAttr(grupo + "." + ATR_PLANTA, json.dumps(datos), type="string")
            self._borrar_vista_previa()
            self.guardar_ajustes()
            self.ultima_planta = grupo
            cmds.select(grupo, replace=True)
        finally:
            cmds.undoInfo(closeChunk=True)
        resultado = {"planta": grupo, "hojas": resumen.get("hojas", 0),
                     "modelos": resumen.get("modelos", 0),
                     "segundos": time.time() - inicio,
                     "limite": self._crecimiento.limite_alcanzado, "cancelado": False}
        return resultado

    # ---------------------------------------------------------------- estado
    def estado(self):
        """Cifras para el pie de la ventana."""
        if self._crecimiento is None:
            return {"crecido": False}
        hojas = aj.hojas_estimadas(self._crecimiento.total_puntos, self.ajustes["densidad"])
        return {"crecido": True, "ramas": len(self._crecimiento.ramas),
                "puntos": self._crecimiento.total_puntos, "pasos": self._pasos_hechos,
                "hojas": hojas, "carga": aj.carga(hojas), "al_dia": self.al_dia()}

    def hojas_previstas(self):
        estado = self.estado()
        return estado.get("hojas", 0)

    # --------------------------------------------------- ajustes de una planta
    def ajustes_de_planta(self, nodo=None):
        """Los ajustes guardados en la planta ``nodo`` (o en la seleccionada)."""
        candidatos = [nodo] if nodo else cmds.ls(selection=True, long=True) or []
        for c in candidatos:
            actual = c
            while actual:
                if cmds.attributeQuery(ATR_PLANTA, node=actual, exists=True):
                    try:
                        datos = json.loads(cmds.getAttr(actual + "." + ATR_PLANTA))
                    except (TypeError, ValueError):
                        break
                    extra = datos.pop("_extra", {}) or {}
                    ajustes, _ = aj.limpiar(datos)
                    return ajustes, extra
                padres = cmds.listRelatives(actual, parent=True, fullPath=True)
                actual = padres[0] if padres else None
        raise Aviso(t("sin_planta_seleccionada"))

    # ------------------------------------------------------ escena de prueba
    def preparar_escena_de_prueba(self, nombre):
        """Crea una escena de prueba sin planta y la deja lista para pulsar Crecer."""
        mallas, localizadores = prototipo.crear_escena(nombre)
        cmds.select(mallas + localizadores, replace=True)
        self.usar_seleccion()
        cmds.delete(localizadores)
        cmds.select(clear=True)
        datos = dict(escenas.ESCENAS[nombre].get("ajustes", {}))
        hojas = datos.pop("hojas", {})
        paso = datos.pop("paso", None)
        ajustes = aj.valores_por_defecto()
        extra = {}
        de_parametros = {f.name for f in fields(Parametros)}
        for clave, valor in list(datos.items()) + list(hojas.items()):
            if clave in aj.POR_CLAVE:
                ajustes[clave] = valor
            elif clave in de_parametros:
                extra[clave] = valor
        if paso:
            ajustes["escala"] = paso / self._paso_automatico()
        self.ajustes, _ = aj.limpiar(ajustes)
        self.extra = extra
        self._olvidar()
        return mallas
