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
