"""Maya falso que sigue las reglas de Maya para los nombres de los nodos.

Sirve para probar ``prototipo.crear_planta`` fuera de Maya. Lo que imita:

- Al crear un nodo con un nombre ya usado en la escena, Maya le pone un
  número (``trepadora_planta_grp`` -> ``trepadora_planta_grp1``).
- ``rename`` y ``parent`` solo evitan repetir el nombre entre hermanos: bajo
  padres distintos puede haber dos ``trepadora_tallos``, como en dos plantas.
- Buscar un nodo por un nombre corto repetido falla con «More than one object
  matches name», igual que en Maya. Con la ruta completa (``|a|b``) no falla.
- Los comandos devuelven el nombre corto, aunque se repita (lo peor que puede
  hacer Maya).

Solo están los comandos que usa ``crear_planta``.
"""

import re
import types


class Nodo(object):
    def __init__(self, nombre, tipo, padre=None, dag=True):
        self.nombre, self.tipo, self.padre, self.dag = nombre, tipo, padre, dag
        self.attrs = {}
        self.objetos = []   # los modelos de un instanciador


class Escena(object):
    def __init__(self):
        self.nodos = []
        self.avisos = []
        self.conexiones = []    # (nodo origen, atributo, nodo destino, atributo)
        self.arnold = False     # si MtoA está cargado
        self.opciones = {}      # optionVar

    # ------------------------------------------------------------- nombres
    def ruta(self, nodo):
        if not nodo.dag:
            return nodo.nombre
        partes = []
        while nodo is not None:
            partes.append(nodo.nombre)
            nodo = nodo.padre
        return "|" + "|".join(reversed(partes))

    def coincidencias(self, nombre):
        nombre = nombre.split(".")[0]
        if nombre.startswith("|"):
            return [n for n in self.nodos if n.dag and self.ruta(n) == nombre]
        if "|" in nombre:
            return [n for n in self.nodos if n.dag and self.ruta(n).endswith("|" + nombre)]
        return [n for n in self.nodos if n.nombre == nombre]

    def buscar(self, nombre):
        nodos = self.coincidencias(nombre)
        if not nodos:
            raise ValueError("No object matches name: " + nombre)
        if len(nodos) > 1:
            raise ValueError("More than one object matches name: " + nombre)
        return nodos[0]

    def _libre(self, nombre, usados):
        if nombre not in usados:
            return nombre
        base = nombre.rstrip("0123456789")
        i = 1
        while "{}{}".format(base, i) in usados:
            i += 1
        return "{}{}".format(base, i)

    def nombre_nuevo(self, nombre):
        """Al crear: un nombre que no esté en toda la escena."""
        return self._libre(nombre, {n.nombre for n in self.nodos})

    def nombre_entre_hermanos(self, nombre, padre, sin=None):
        """Al renombrar o mover: un nombre que no tenga ningún hermano."""
        return self._libre(nombre, {n.nombre for n in self.nodos
                                    if n.dag and n.padre is padre and n is not sin})

    def crear(self, nombre, tipo, padre=None, dag=True):
        nodo = Nodo(self.nombre_nuevo(nombre), tipo, padre, dag)
        self.nodos.append(nodo)
        return nodo

    def hijos(self, nodo):
        return [n for n in self.nodos if n.dag and n.padre is nodo]

    def borrar(self, nodo):
        for hijo in self.hijos(nodo):
            self.borrar(hijo)
        if nodo in self.nodos:
            self.nodos.remove(nodo)


def instalar():
    """Devuelve (escena, módulos) para ``mock.patch.dict(sys.modules, módulos)``."""
    e = Escena()
    cmds = types.ModuleType("maya.cmds")

    def _lista(x):
        return list(x) if isinstance(x, (list, tuple)) else [x]

    def objExists(nombre):
        return bool(e.coincidencias(nombre))

    def ls(*nombres, long=False, type=None, **_):
        res = []
        if not nombres and type is not None:
            nombres = ("*",)
        for nombre in (x for n in nombres for x in _lista(n)):
            patron = re.compile("^" + re.escape(nombre).replace(r"\*", ".*") + "$")
            nodos = ([n for n in e.nodos if patron.match(n.nombre)] if "*" in nombre
                     else e.coincidencias(nombre))
            res += [n for n in nodos if type is None or n.tipo == type]
        return [e.ruta(n) if long else n.nombre for n in res]

    def nodeType(nombre):
        return e.buscar(nombre).tipo

    def group(empty=True, name="null1", parent=None, world=False, **_):
        padre = e.buscar(parent) if parent else None
        return e.crear(name, "transform", padre).nombre

    def rename(nombre, nuevo, **_):
        nodo = e.buscar(nombre)
        nodo.nombre = e.nombre_entre_hermanos(nuevo, nodo.padre, sin=nodo)
        for forma in e.hijos(nodo):
            if forma.tipo != "transform":
                forma.nombre = e.nombre_entre_hermanos(nodo.nombre + "Shape", nodo, sin=forma)
        return nodo.nombre

    def parent(hijo, padre, **_):
        nodo, nuevo = e.buscar(hijo), e.buscar(padre)
        nodo.padre = nuevo
        nodo.nombre = e.nombre_entre_hermanos(nodo.nombre, nuevo, sin=nodo)
        return [nodo.nombre]

    def listRelatives(nombre, shapes=False, children=False, parent=False, fullPath=False,
                      type=None, noIntermediate=False, **_):
        nodo = e.buscar(nombre)
        if parent:
            res = [nodo.padre] if nodo.padre else []
        else:
            res = e.hijos(nodo)
            if shapes:
                res = [n for n in res if n.tipo != "transform"]
        if type:
            res = [n for n in res if n.tipo == type]
        return [e.ruta(n) if fullPath else n.nombre for n in res] or None

    def setAttr(atributo, *valores, **_):
        nodo = e.buscar(atributo)
        nodo.attrs[atributo.split(".", 1)[1]] = valores

    def getAttr(atributo, **_):
        valor = e.buscar(atributo).attrs.get(atributo.split(".", 1)[1])
        return valor[0] if isinstance(valor, tuple) and len(valor) == 1 else valor

    def addAttr(nombre, longName=None, **_):
        e.buscar(nombre).attrs.setdefault(longName, None)

    def attributeQuery(atributo, node=None, exists=False, **_):
        return atributo in e.buscar(node).attrs

    def select(nombres, **_):
        for nombre in _lista(nombres):
            e.buscar(nombre)

    def delete(nombres):
        for nombre in _lista(nombres):
            e.borrar(e.buscar(nombre))

    def shadingNode(tipo, name=None, **_):
        return e.crear(name or tipo + "1", tipo, dag=False).nombre

    def sets(*objetos, renderable=False, empty=False, name=None, forceElement=None, **_):
        if forceElement:
            grupo = e.buscar(forceElement)
            for nombre in objetos:
                e.buscar(nombre)
            return grupo.nombre
        return e.crear(name or "set1", "shadingEngine", dag=False).nombre

    def connectAttr(origen, destino, force=False):
        o, d = e.buscar(origen), e.buscar(destino)
        e.conexiones.append((o, origen.split(".", 1)[1], d, destino.split(".", 1)[1]))

    def listConnections(atributo, type=None, **_):
        nodo, nombre = e.buscar(atributo), atributo.split(".", 1)[1]
        return [d.nombre for o, a, d, _b in e.conexiones
                if o is nodo and a == nombre and (type is None or d.tipo == type)] or None

    def particle(position=(), name="particle1", **_):
        t = e.crear(name, "transform")
        forma = e.crear(t.nombre + "Shape", "particle", t)
        forma.attrs.update({a: None for a in ("primaryVisibility", "castsShadows")})
        return [t.nombre, forma.nombre]

    def saveInitialState(nombre):
        e.buscar(nombre)

    def particleInstancer(forma, object=(), name="instancer1", **_):
        e.buscar(forma)
        nodo = e.crear(name, "instancer")
        nodo.objetos = [e.buscar(o) for o in _lista(object)]
        return nodo.nombre

    def duplicate(nombre, name=None, **_):
        original = e.buscar(nombre)

        def copiar(nodo, padre, nuevo):
            copia = Nodo(nuevo, nodo.tipo, padre)
            copia.attrs = dict(nodo.attrs)
            e.nodos.append(copia)
            for hijo in e.hijos(nodo):
                copiar(hijo, copia, hijo.nombre)   # los hijos conservan su nombre
            return copia

        return [copiar(original, original.padre, e.nombre_nuevo(name or original.nombre)).nombre]

    def xform(nombre, **_):
        e.buscar(nombre)

    def exactWorldBoundingBox(nombre, **_):
        e.buscar(nombre)
        return [-0.2, 0.0, -0.05, 0.2, 1.0, 0.05]

    def pluginInfo(nombre, query=False, loaded=False, **_):
        return e.arnold and nombre == "mtoa"

    def isConnected(origen, destino):
        o, d = e.buscar(origen), e.buscar(destino)
        return any(c == (o, origen.split(".", 1)[1], d, destino.split(".", 1)[1])
                   for c in e.conexiones)

    def polyColorSet(nombre, query=False, currentColorSet=False, **_):
        e.buscar(nombre)
        return ["colorSet1"]

    def optionVar(exists=None, query=None, stringValue=None, **_):
        if exists is not None:
            return exists in e.opciones
        if query is not None:
            return e.opciones.get(query, 0)
        if stringValue is not None:
            e.opciones[stringValue[0]] = stringValue[1]

    def colorManagementPrefs(query=False, cmEnabled=False, **_):
        return True

    def warning(texto):
        e.avisos.append(texto)

    for funcion in (objExists, ls, nodeType, group, rename, parent, listRelatives, setAttr,
                    getAttr, addAttr, attributeQuery, select, delete, shadingNode, sets,
                    connectAttr, listConnections, particle, saveInitialState,
                    particleInstancer, duplicate, xform, exactWorldBoundingBox, pluginInfo,
                    colorManagementPrefs, warning, isConnected, polyColorSet, optionVar):
        setattr(cmds, funcion.__name__, funcion)

    om = types.ModuleType("maya.api.OpenMaya")

    class MObject(object):
        def __init__(self, nodo):
            self.nodo = nodo

    class MFnMesh(object):
        def create(self, puntos, conteos, indices):
            t = e.crear("polySurface1", "transform")
            e.crear("polySurfaceShape1", "mesh", t)
            return MObject(t)

        def setVertexColors(self, colores, indices):
            pass

        def setUVs(self, us, vs):
            assert len(us) == len(vs)
            self.uvs = len(us)

        def assignUVs(self, conteos, indices):
            assert sum(conteos) == len(indices) and max(indices) < self.uvs

    class MFnDagNode(object):
        def __init__(self, objeto):
            self.objeto = objeto

        def fullPathName(self):
            return e.ruta(self.objeto.nodo)

    om.MObject, om.MFnMesh, om.MFnDagNode = MObject, MFnMesh, MFnDagNode
    om.MPoint = om.MColor = lambda *a: a
    om.MPointArray = om.MColorArray = om.MFloatArray = om.MIntArray = list

    api = types.ModuleType("maya.api")
    api.OpenMaya = om
    maya = types.ModuleType("maya")
    maya.cmds, maya.api = cmds, api
    mel = types.ModuleType("maya.mel")
    mel.eval = lambda *_a, **_k: None
    maya.mel = mel
    return e, {"maya": maya, "maya.cmds": cmds, "maya.api": api, "maya.api.OpenMaya": om,
               "maya.mel": mel}
