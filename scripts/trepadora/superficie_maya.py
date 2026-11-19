"""Superficie basada en una o varias mallas de Maya (API 2.0)."""

import numpy as np
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
        mejor = None
        mejor_dist = None
        for malla in self._mallas:
            cercano, normal, _ = malla.getClosestPointAndNormal(consulta, om.MSpace.kWorld)
            dist = cercano.distanceTo(consulta)
            if mejor_dist is None or dist < mejor_dist:
                mejor_dist = dist
                mejor = (cercano, normal)
        cercano, normal = mejor
        n = np.array([normal.x, normal.y, normal.z], dtype=float)
        largo = np.linalg.norm(n)
        if largo > 0:
            n /= largo
        return np.array([cercano.x, cercano.y, cercano.z], dtype=float), n
