"""Maya falso, en memoria, para ensayar sesion.py y la ventana sin Maya (ver ensayo.py)."""
nodos = {}      # nombre corto -> dict
seleccion = []
opciones = {}
avisos = []
deshacer = []


def _nuevo(nombre, tipo, padre=None, **extra):
    base = nombre.rstrip("0123456789") or nombre
    n, i = nombre, 1
    while n in nodos:
        n = "{}{}".format(base, i)
        i += 1
    nodos[n] = dict(tipo=tipo, padre=padre, attrs={}, pos=(0.0, 0.0, 0.0), **extra)
    return n


def _corto(nombre):
    return nombre.split("|")[-1].split(".")[0]


def _largo(n):
    partes = [n]
    while nodos[n]["padre"]:
        n = nodos[n]["padre"]
        partes.append(n)
    return "|" + "|".join(reversed(partes))


def objExists(nombre):
    return _corto(nombre) in nodos


def ls(*args, selection=False, long=False, type=None, **_):
    if selection:
        res = list(seleccion)
    else:
        res = []
        for a in args:
            if isinstance(a, (list, tuple)):
                res += list(a)
            else:
                res.append(a)
        if not args:
            res = list(nodos)
        res = [r for r in res if objExists(r)]
        if args and any("*" in str(a) for a in args):
            import fnmatch
            res = [n for n in nodos if any(fnmatch.fnmatch(n, a) for a in args)]
    if type:
        res = [r for r in res if nodos[_corto(r)]["tipo"] == type]
    return [_largo(_corto(r)) if long else _corto(r) for r in res]


def select(objs=None, replace=False, clear=False, **_):
    global seleccion
    if clear:
        seleccion = []
        return
    if isinstance(objs, str):
        objs = [objs]
    seleccion = [_largo(_corto(o)) for o in objs]


def nodeType(n):
    return nodos[_corto(n)]["tipo"]


def _hijos(n):
    return [k for k, v in nodos.items() if v["padre"] == n]


def listRelatives(n, children=False, shapes=False, parent=False, allDescendents=False,
                  fullPath=False, type=None, noIntermediate=False, **_):
    if isinstance(n, (list, tuple)):
        n = n[0]
    c = _corto(n)
    if parent:
        res = [nodos[c]["padre"]] if nodos[c]["padre"] else []
    elif allDescendents:
        res, pila = [], _hijos(c)
        while pila:
            h = pila.pop()
            res.append(h)
            pila += _hijos(h)
    elif shapes:
        res = [h for h in _hijos(c) if nodos[h]["tipo"] in ("mesh", "locator", "nurbsCurve")]
    else:
        res = _hijos(c)
    if type:
        res = [r for r in res if nodos[r]["tipo"] == type]
    if not res:
        return None
    return [_largo(r) if fullPath else r for r in res]


def getAttr(attr):
    n, a = attr.split(".", 1)
    if a == "intermediateObject":
        return False
    return nodos[_corto(n)]["attrs"].get(a)


def setAttr(attr, *valores, **kw):
    n, a = attr.split(".", 1)
    nodos[_corto(n)]["attrs"][a] = valores[0] if len(valores) == 1 else valores


def addAttr(n, longName=None, dataType=None, **_):
    nodos[_corto(n)]["attrs"].setdefault(longName, None)


def attributeQuery(a, node=None, exists=False, **_):
    return a in nodos[_corto(node)]["attrs"]


def optionVar(exists=None, query=None, stringValue=None, **_):
    if exists is not None:
        return exists in opciones
    if query is not None:
        return opciones[query]
    if stringValue is not None:
        opciones[stringValue[0]] = stringValue[1]


def group(empty=True, name="null1", world=False, parent=None, **_):
    return _nuevo(name, "transform", _corto(parent) if parent else None)


def spaceLocator(name="locator1", **_):
    t = _nuevo(name, "transform")
    _nuevo(t + "Shape", "locator", t)
    return [t]


def move(x, y, z, n, **_):
    nodos[_corto(n)]["pos"] = (float(x), float(y), float(z))


def xform(n, query=False, worldSpace=False, translation=False, **_):
    return list(nodos[_corto(n)]["pos"])


def parent(n, p, **_):
    nodos[_corto(n)]["padre"] = _corto(p)
    return [_corto(n)]


def delete(objs):
    if isinstance(objs, str):
        objs = [objs]
    for o in objs:
        c = _corto(o)
        if c not in nodos:
            continue
        pila = [c]
        while pila:
            h = pila.pop()
            pila += _hijos(h)
            nodos.pop(h, None)


def _caja(n):
    v = nodos[n]
    if "medidas" not in v:
        return None
    p, m = v["pos"], v["medidas"]
    return [p[i] - m[i] / 2.0 for i in range(3)], [p[i] + m[i] / 2.0 for i in range(3)]


def exactWorldBoundingBox(objs):
    if isinstance(objs, str):
        objs = [objs]
    lo, hi = [1e18] * 3, [-1e18] * 3
    for o in objs:
        c = _caja(_corto(o))
        if c:
            lo = [min(lo[i], c[0][i]) for i in range(3)]
            hi = [max(hi[i], c[1][i]) for i in range(3)]
    return lo + hi


def undoInfo(**_):
    pass


def progressWindow(query=False, isCancelled=False, **_):
    return False if query else None


def warning(texto):
    avisos.append(texto)


def curve(degree=1, point=(), name="curve1", **_):
    t = _nuevo(name, "transform")
    _nuevo(t + "Shape", "nurbsCurve", t, puntos=len(point))
    return t


def _malla(name, medidas):
    t = _nuevo(name, "transform", medidas=medidas)
    _nuevo(t + "Shape", "mesh", t)
    return [t, t + "_hist"]


def polyPlane(name="pPlane1", width=1, height=1, axis=(0, 1, 0), **_):
    if tuple(axis) == (0, 0, 1):
        return _malla(name, (width, height, 0.0))
    return _malla(name, (width, 0.0, height))


def polyCube(name="pCube1", width=1, height=1, depth=1, **_):
    return _malla(name, (width, height, depth))
