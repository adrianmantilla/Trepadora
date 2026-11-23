"""Superficie basada en una o varias mallas de Maya (API 2.0)."""

import maya.api.OpenMaya as om


class SuperficieMaya:
    """Responde a ``mas_cercano(punto)`` usando las mallas indicadas, en espacio de mundo."""

    def __init__(self, nombres_mallas):
        seleccion = om.MSelectionList()
        for nombre in nombres_mallas:
            seleccion.add(nombre)
        self._mallas = []
        for i in range(seleccion.length()):
            dag = seleccion.getDagPath(i)
            if dag.apiType() != om.MFn.kMesh:
                dag.extendToShape()
            self._mallas.append(om.MFnMesh(dag))
        if not self._mallas:
            raise ValueError("No hay mallas")

    def mas_cercano(self, punto):
        consulta = om.MPoint(float(punto[0]), float(punto[1]), float(punto[2]))
        candidatos = []
        for malla in self._mallas:
            cercano, normal, _ = malla.getClosestPointAndNormal(consulta, om.MSpace.kWorld)
            normal.normalize()
            candidatos.append((cercano.distanceTo(consulta), cercano, normal))
        mejor_dist = min(c[0] for c in candidatos)
        # Empates: dos caras a la misma distancia, por ejemplo el suelo y la
        # base de un muro apoyado en él (caras coplanarias con normales
        # opuestas). Si el punto queda detrás de alguna, está dentro de un
        # objeto o bajo el suelo, y esa cara es la que lo debe sacar; si no,
        # la base del muro lo dejaría "pegado" por debajo del suelo.
        empatados = [c for c in candidatos if c[0] <= mejor_dist * 1.02 + 1e-4]
        detras = [c for c in empatados if (consulta - c[1]) * c[2] < 0.0]
        _, cercano, normal = (detras or empatados)[0]
        return (cercano.x, cercano.y, cercano.z), (normal.x, normal.y, normal.z)


def _forma(nombre, tipo):
    """La primera forma de ``tipo`` (``mesh``, ``nurbsCurve``) de ``nombre``, o None."""
    from maya import cmds

    if cmds.nodeType(nombre) == tipo:
        return nombre
    formas = cmds.listRelatives(nombre, shapes=True, fullPath=True, type=tipo,
                                noIntermediate=True) or []
    return formas[0] if formas else None


def zona_de(nombre):
    """La zona prohibida de la malla ``nombre``, o None si no es una malla.

    Es la caja de la malla en su propio espacio llevada al mundo con su
    matriz: si el estudiante gira o escala la caja, la zona gira y escala con
    ella. La caja se lee de la forma, así que vale aunque esté oculta.
    """
    from maya import cmds

    from .zonas import Zona

    formas = cmds.listRelatives(nombre, shapes=True, fullPath=True, type="mesh",
                                noIntermediate=True) or []
    if not formas:
        return None
    minimo, maximo = [1e30] * 3, [-1e30] * 3
    for forma in formas:
        a = cmds.getAttr(forma + ".boundingBoxMin")[0]
        b = cmds.getAttr(forma + ".boundingBoxMax")[0]
        minimo = [min(m, x) for m, x in zip(minimo, a)]
        maximo = [max(m, x) for m, x in zip(maximo, b)]
    matriz = cmds.xform(nombre, query=True, matrix=True, worldSpace=True)
    return Zona.desde_caja(minimo, maximo, matriz, nombre.split("|")[-1])


def puntos_de_curva(nombre, separacion=None, cantidad=None, maximo=4000):
    """Puntos de la curva ``nombre`` en el mundo, del principio al final.

    Repartidos a lo largo de la curva cada ``separacion`` (o ``cantidad``
    puntos en total). Lista vacía si no es una curva.
    """
    forma = _forma(nombre, "nurbsCurve")
    if forma is None:
        return []
    lista = om.MSelectionList()
    lista.add(forma)
    curva = om.MFnNurbsCurve(lista.getDagPath(0))
    largo = curva.length()
    if cantidad is None:
        cantidad = int(largo / max(float(separacion or 1.0), 1e-6)) + 1
    cantidad = max(2, min(int(cantidad), maximo))
    final = curva.knotDomain[1]
    puntos = []
    for i in range(cantidad):
        if i == cantidad - 1:
            parametro = final
        else:
            parametro = min(curva.findParamFromLength(largo * i / (cantidad - 1)), final)
        p = curva.getPointAtParam(parametro, om.MSpace.kWorld)
        puntos.append((p.x, p.y, p.z))
    return puntos
