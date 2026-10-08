"""Reader for Clap Hanz "I3D_BIN" model resources (.psp.i3r) — Hot Shots Tennis: Get a Grip,
Hot Shots Golf Open Tee 1/2 (PSP). See notes/psp-formats.md for the format description.

All matrices are returned as numpy 4x4 in the file's convention: row vectors, translation in
row 3 (v' = v @ M).  Transpose for column-vector / glTF use.
"""
import struct
from dataclasses import dataclass, field

import numpy as np

BASE = 0x10  # every record/data offset in the file is relative to 0x10


@dataclass
class Rec:
    off: int        # file offset of the 16-byte record
    type: int       # record type with the 0x80 "shared data" bit removed
    shared: bool    # data is shared with an earlier record (dedup); children are still own
    data: int       # absolute file offset of the record's data
    count: int      # number of children (or element count)
    flags: int      # 4th word (constant per file, low byte differs on some records)
    children: list = field(default_factory=list)


def parse_tree(d):
    def rec(off):
        a, b, c, f = struct.unpack_from("<IIII", d, off)
        t = b >> 24
        r = Rec(off, t & 0x7F, bool(t & 0x80), BASE + a, b & 0xFFFFFF, f)
        if c:  # c == 0 would point at the root record: no children
            r.children = [rec(BASE + c + 16 * i) for i in range(b & 0xFFFFFF)]
        return r

    if d[:8] != b"I3D_BIN\0":
        raise ValueError("not I3D_BIN")
    return rec(BASE)



def iter_recs(r, path=()):
    yield r, path
    for c in r.children:
        yield from iter_recs(c, path + (r,))


def cstr(d, o):
    return d[o: d.index(b"\0", o)].decode("latin1")


def mat(d, o):
    return np.array(struct.unpack_from("<16f", d, o), dtype=np.float64).reshape(4, 4)


@dataclass
class Skeleton:
    names: list
    parents: list
    local: list      # per node, local matrix (relative to parent)
    world: list      # per node, model-space matrix (= local @ parent world)


def read_skeleton(d, root):
    """Root record (type 0x52) data: node table."""
    B = root.data
    (_cx, _cy, _cz, _r, o_local, o_world, o_file_name, o_name_order, o_names, _unk,
     n_nodes, n2, n_file, n3, _k) = struct.unpack_from("<4f6I4HI", d, B)
    sorted_names = [cstr(d, B + struct.unpack_from("<I", d, B + o_names + 4 * i)[0]) for i in range(n_nodes)]
    order = struct.unpack_from(f"<{n_nodes}H", d, B + o_name_order)  # sorted-name index -> node index
    names = [None] * n_nodes
    for k, j in enumerate(order):
        names[j] = sorted_names[k]
    local = [mat(d, B + o_local + 64 * i) for i in range(n_nodes)]
    world = [mat(d, B + o_world + 64 * i) for i in range(n_nodes)]
    # parents: root child list (type 0x02) of n_nodes type-0x2a records, data = s16 parent index
    parents = None
    for c in root.children:
        if c.type == 0x02 and c.count == n_nodes and c.children and c.children[0].type == 0x2A:
            parents = [struct.unpack_from("<h", d, k.data)[0] for k in c.children]
    if parents is None:
        raise ValueError("no node list")
    return Skeleton(names, parents, local, world)


@dataclass
class Material:
    texture: str
    raw: bytes       # the 0x26 record (texture/render state), name at +0x3a


def read_materials(d, root):
    mats = []
    for c in root.children:
        if c.type == 0x03 and c.children and c.children[0].type == 0x25:
            for m in c.children:
                tex = next((x for x, _ in iter_recs(m) if x.type == 0x26), None)
                # +0x18: offset of the texture name (0x3a in Get a Grip / OT2; OT1 has "Channel0000" first)
                name = cstr(d, tex.data + struct.unpack_from("<I", d, tex.data + 0x18)[0]) if tex else ""
                mats.append(Material(name, d[tex.data: tex.data + 0x3A] if tex else b""))
    return mats


# ---- GE vertex decoding -------------------------------------------------------------------
_SZ = {1: 1, 2: 2, 3: 4}
_COLSZ = {4: 2, 5: 2, 6: 2, 7: 4}


def vtype_layout(vt):
    tc, col, nrm, pos = vt & 3, (vt >> 2) & 7, (vt >> 5) & 3, (vt >> 7) & 3
    wt, idx = (vt >> 9) & 3, (vt >> 11) & 3
    nw = ((vt >> 14) & 7) + 1 if wt else 0
    nmorph = ((vt >> 18) & 7) + 1
    off = 0
    lay = {}
    maxa = 1

    def take(name, n, sz):
        nonlocal off, maxa
        off = (off + sz - 1) // sz * sz
        lay[name] = (off, n, sz)
        off += n * sz
        maxa = max(maxa, sz)

    if wt:
        take("w", nw, _SZ[wt])
    if tc:
        take("uv", 2, _SZ[tc])
    if col:
        take("c", 1, _COLSZ[col])
    if nrm:
        take("n", 3, _SZ[nrm])
    take("p", 3, _SZ[pos])
    size = (off + maxa - 1) // maxa * maxa
    return dict(tc=tc, col=col, nrm=nrm, pos=pos, wt=wt, idx=idx, nw=nw, nmorph=nmorph, size=size, lay=lay)


def _comp(d, o, n, fmt_code, scale):
    if fmt_code == 3:
        return list(struct.unpack_from(f"<{n}f", d, o))
    if fmt_code == 2:
        return [v / scale[1] for v in struct.unpack_from(f"<{n}h" if scale[0] else f"<{n}H", d, o)]
    return [v / scale[2] for v in struct.unpack_from(f"<{n}b" if scale[0] else f"<{n}B", d, o)]


def _color(d, o, col):
    if col == 7:
        return list(d[o: o + 4])
    v = struct.unpack_from("<H", d, o)[0]
    if col == 4:
        return [(v & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, ((v >> 11) & 31) * 255 // 31, 255]
    if col == 5:
        return [(v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31, 255 * (v >> 15)]
    return [(v & 15) * 17, ((v >> 4) & 15) * 17, ((v >> 8) & 15) * 17, (v >> 12) * 17]


@dataclass
class Prim:
    vtype: int
    prim: int            # GE primitive: 3 triangles, 4 triangle strip
    pos: np.ndarray
    nrm: np.ndarray
    uv: np.ndarray
    col: np.ndarray
    w: np.ndarray        # (n, nw) weights, or (n, 0)


def read_prim(d, o):
    """Type 0x50 record data: 0x28-byte header then vertices."""
    vt, n, _z0, _z1, hsz, _k, _z2, _z3, _z4, pinfo = struct.unpack_from("<10I", d, o)
    L = vtype_layout(vt)
    if L["idx"]:
        raise NotImplementedError("indexed GE vertices")
    v0 = o + hsz
    stride = L["size"] * L["nmorph"]  # morph targets are stored interleaved per vertex; use the first
    P, N, U, C, W = [], [], [], [], []
    for i in range(n):
        b = v0 + i * stride
        lay = L["lay"]
        if L["wt"]:
            wo, wn, _ = lay["w"]
            W.append(_comp(d, b + wo, wn, L["wt"], (False, 32768.0, 128.0)))
        if L["tc"]:
            U.append(_comp(d, b + lay["uv"][0], 2, L["tc"], (False, 32768.0, 128.0)))
        if L["col"]:
            C.append(_color(d, b + lay["c"][0], L["col"]))
        if L["nrm"]:
            N.append(_comp(d, b + lay["n"][0], 3, L["nrm"], (True, 32767.0, 127.0)))
        P.append(_comp(d, b + lay["p"][0], 3, L["pos"], (True, 32767.0, 127.0)))
    return Prim(vt, (pinfo >> 8) & 0xFF, np.array(P), np.array(N).reshape(-1, 3), np.array(U).reshape(-1, 2),
                np.array(C, dtype=np.uint8).reshape(-1, 4), np.array(W).reshape(n, -1))


@dataclass
class MeshPart:
    material: int
    palette: list        # node indices / skin bone indices, see `skinned`
    skinned: bool        # True: palette = indices into skin.names; False: palette[0] = record value of 0x4b
    prims: list
    skin: "Skin" = None  # the 0x46 skin this part's palette indexes (a file may have several)


@dataclass
class Skin:
    names: list
    inv_bind: list       # model space -> bone space, per skin bone
    extra: list          # second matrix per bone (bounding volume in bone space?), raw


def read_skin(d, r):
    S = r.data
    o1, o2, o3, c1, c2, c3 = struct.unpack_from("<3I3H", d, S)
    names = [cstr(d, S + struct.unpack_from("<I", d, S + o3 + 4 * i)[0]) for i in range(c3)]
    return Skin(names, [mat(d, S + o1 + 64 * i) for i in range(c1)], [mat(d, S + o2 + 64 * i) for i in range(c2)])


def _palette(d, o):
    _h, cnt, _fl = struct.unpack_from("<IBB", d, o)
    return list(struct.unpack_from(f"<{cnt}H", d, o + 8))


def read_meshes(d, root):
    """Returns (first skin or None, [MeshPart]) over all 0x46 (skinned) and 0x45 (rigid) groups."""
    skins = {}
    parts = []
    for r, path in iter_recs(root):
        if r.type == 0x46 and r.count:
            skins[r.off] = read_skin(d, r)
        if r.type != 0x4D:
            continue
        mat_id = struct.unpack_from("<H", d, r.data + 0xC)[0]
        group = next((p for p in reversed(path) if p.type in (0x4C, 0x4B)), None)
        if group is None:
            continue
        if group.type == 0x4C:
            pal, skinned = _palette(d, group.data), True
        else:
            pal, skinned = [struct.unpack_from("<I", d, group.data)[0]], False
        prims = [read_prim(d, x.data) for x, _ in iter_recs(r) if x.type == 0x50]
        owner = next((p for p in reversed(path) if p.type == 0x46), None)
        parts.append(MeshPart(mat_id, pal, skinned, prims, skins.get(owner.off) if owner else None))
    return next(iter(skins.values()), None), parts


@dataclass
class Model:
    skeleton: Skeleton
    materials: list
    skin: Skin
    parts: list


def load(path):
    d = open(path, "rb").read()
    root = parse_tree(d)
    skel = read_skeleton(d, root)
    skin, parts = read_meshes(d, root)
    for sk in {id(p.skin): p.skin for p in parts if p.skin}.values():
        resolve_skin_names(sk, skel)
    return Model(skel, read_materials(d, root), skin, parts)


def resolve_skin_names(skin, skel):
    """Open Tee 1 (3ds Max export) names skin bones "InfluenceNNNN" instead of the node name. Map each to the
    node j whose bind world W_j satisfies IB_k @ W_j == C for one constant C (the skinned mesh node's world)."""
    if all(n in skel.names for n in skin.names):
        return
    best = None
    for c in range(len(skel.names)):  # candidate: influence 0 binds to node c
        C = skin.inv_bind[0] @ skel.world[c]
        names, err = [], 0.0
        for IB in skin.inv_bind:
            e = [np.abs(IB @ W - C).max() for W in skel.world]
            j = int(np.argmin(e))
            names.append(skel.names[j])
            err = max(err, e[j])
        if best is None or err < best[0]:
            best = (err, names)
    if best[0] > 1e-2 or len(set(best[1])) != len(best[1]):
        raise ValueError(f"cannot resolve skin names (err {best[0]:.3g})")
    skin.names[:] = best[1]


def strip_to_tris(n):
    return [(i, i + 1, i + 2) if i % 2 == 0 else (i + 1, i, i + 2) for i in range(n - 2)]


def prim_triangles(p):
    n = len(p.pos)
    if p.prim == 4:
        tris = strip_to_tris(n)
    elif p.prim == 3:
        tris = [(i, i + 1, i + 2) for i in range(0, n - 2, 3)]
    else:
        raise NotImplementedError(f"GE prim {p.prim}")
    out = []
    for t in tris:
        a, b, c = (p.pos[k] for k in t)
        fn = np.cross(b - a, c - a)
        if np.dot(fn, fn) < 1e-12:
            continue  # degenerate (strip joins)
        if len(p.nrm) and np.dot(fn, p.nrm[t[0]] + p.nrm[t[1]] + p.nrm[t[2]]) < 0:
            t = (t[0], t[2], t[1])
        out.append(t)
    return out
