class MPoint(tuple):
    def __new__(cls, x=0, y=0, z=0):
        return tuple.__new__(cls, (x, y, z))
class MVector(MPoint):
    pass
class MFloatPoint(MPoint):
    pass
class MFloatVector(MPoint):
    pass
class MSpace:
    kWorld = 4
class MFn:
    kMesh = 296
