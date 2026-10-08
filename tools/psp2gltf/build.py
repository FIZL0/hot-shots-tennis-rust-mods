"""Assemble I3D_BIN parts (one skinned body + rigid attachments) into a glTF scene."""
import io
import os
import re

import numpy as np
from PIL import Image

import gim
import glb
import i3d

F = np.diag([-1.0, -1.0, 1.0, 1.0])  # ROOTNODE's 180-degree Z flip (see notes)
KEEP = re.compile(r"^(ROOTNODE|Bip01[^9]*|.*_locator)$")  # "<Bone>9<x>" = attachment, not a bone
SCALE = 0.01  # file units are centimetres


def root_local(sk):
    """glTF local of ROOTNODE. Node worlds in the file are post-ROOTNODE (W = locals @ R0); F maps that space
    to glTF model space for every file, so ROOTNODE gets R0 @ F: identity for Maya exports (GaG, most OT2,
    R0 = diag(-1,-1,1)), the Z-up -> Y-up turn for 3ds Max exports (OT1, some OT2 parts, R0 = (x,y,z) ->
    (-x,-z,-y))."""
    r = sk.names.index("ROOTNODE") if "ROOTNODE" in sk.names else -1
    m = sk.local[r] @ F if r >= 0 else np.eye(4)
    return np.eye(4) if np.allclose(m, np.eye(4)) else m


def skin_space(part, sk):
    """Skinned vertices -> glTF model space: v @ C @ F, C = IB_k @ W_k (the skinned mesh node's world; == F for
    most parts, so this is identity; OT1's mesh node is Z-up with a non-uniform scale, some GaG/OT2 skirt and
    pouch groups are offset)."""
    k = next(i for i, n in enumerate(part.skin.names) if n in sk.names)
    M = part.skin.inv_bind[k] @ sk.world[sk.names.index(part.skin.names[k])] @ F
    return None if np.allclose(M, np.eye(4), atol=1e-3) else M  # GaG/OT2: float noise < 2e-5


def _xform(part, M):
    if M is None:
        return
    for pr in part.prims:
        pr.pos = pr.pos @ M[:3, :3] + M[3, :3]
        if len(pr.nrm):
            pr.nrm = pr.nrm @ np.linalg.inv(M[:3, :3]).T


def gl(m):
    """row-vector 4x4 -> glTF column-major flat list."""
    return [float(x) for x in np.asarray(m).reshape(-1)]


class TextureCache:
    def __init__(self, b, search_dirs, tone):
        self.b, self.dirs, self.tone, self.tex, self.mats = b, search_dirs, tone, {}, {}
        self.png = {}

    def find(self, name):
        cands = [name]
        m = re.match(r"(.*_)([fmbk])(\d\d)$", name)
        if m and self.tone:
            cands.insert(0, m.group(1) + self.tone + m.group(3))
        for c in cands:
            for d in self.dirs:
                p = os.path.join(d, c + ".gim")
                if os.path.exists(p):
                    return p
        return None

    def material(self, name):
        if name in self.mats:
            return self.mats[name]
        p = self.find(name)
        mat = {"name": name, "doubleSided": True,
               "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 1.0}}
        if p:
            rgba = gim.decode(open(p, "rb").read())
            a = rgba[..., 3]
            mid = np.mean((a > 16) & (a < 240))
            if mid > 0.05:
                mat["alphaMode"] = "BLEND"
            elif (a < 128).any():
                mat["alphaMode"] = "MASK"
            buf = io.BytesIO()
            Image.fromarray(rgba, "RGBA").save(buf, "PNG")
            self.png[os.path.basename(p)[:-4]] = buf.getvalue()
            t = self.b.image_png(buf.getvalue(), os.path.basename(p)[:-4])
            mat["pbrMetallicRoughness"]["baseColorTexture"] = {"index": t}
        else:
            mat["pbrMetallicRoughness"]["baseColorFactor"] = [1, 0, 1, 1]
        self.mats[name] = self.b.add("materials", mat)
        return self.mats[name]


def _prim_arrays(part, joint_map):
    """Merge a MeshPart's GE prims into one indexed triangle list."""
    P, N, U, C, J, W, idx = [], [], [], [], [], [], []
    base = 0
    for pr in part.prims:
        n = len(pr.pos)
        P.append(pr.pos)
        N.append(pr.nrm if len(pr.nrm) else np.tile([0, 1, 0], (n, 1)))
        U.append(pr.uv if len(pr.uv) else np.zeros((n, 2)))
        C.append(pr.col if len(pr.col) else np.full((n, 4), 255, np.uint8))
        if joint_map is not None:
            w = pr.w if pr.w.shape[1] else np.ones((n, 1))
            pal = np.array([joint_map[k] for k in part.palette[: w.shape[1]]])
            order = np.argsort(-w, axis=1)[:, :4]  # keep the 4 largest (glTF/Bevy JOINTS_0 only)
            ww = np.take_along_axis(w, order, 1)
            jj = pal[order]
            if ww.shape[1] < 4:
                pad = 4 - ww.shape[1]
                ww = np.pad(ww, ((0, 0), (0, pad)))
                jj = np.pad(jj, ((0, 0), (0, pad)))
            s = ww.sum(1, keepdims=True)
            ww = ww / np.where(s > 0, s, 1)
            jj = np.where(ww > 0, jj, 0)  # glTF: unused joint slots must be 0
            J.append(jj)
            W.append(ww)
        idx += [(a + base, b + base, c + base) for a, b, c in i3d.prim_triangles(pr)]
        base += n
    out = dict(P=np.concatenate(P), N=np.concatenate(N), U=np.concatenate(U), C=np.concatenate(C),
               I=np.array(idx, np.uint32).reshape(-1))
    if joint_map is not None:
        out["J"], out["W"] = np.concatenate(J), np.concatenate(W)
    nn = np.linalg.norm(out["N"], axis=1, keepdims=True)
    out["N"] = out["N"] / np.where(nn > 0, nn, 1)
    return out


def _gl_prims(b, parts, texcache, materials, joint_map):
    by_mat = {}
    for part in parts:
        by_mat.setdefault(part.material, []).append(part)
    prims = []
    for m, ps in sorted(by_mat.items()):
        arrs = [_prim_arrays(p, joint_map) for p in ps]
        off = np.cumsum([0] + [len(a["P"]) for a in arrs])
        A = {k: np.concatenate([a[k] for a in arrs]) for k in arrs[0] if k != "I"}
        A["I"] = np.concatenate([a["I"] + o for a, o in zip(arrs, off)])
        if not len(A["I"]):
            continue
        attrs = {"POSITION": b.accessor(A["P"], glb.FLOAT, "VEC3", 34962, minmax=True),
                 "NORMAL": b.accessor(A["N"], glb.FLOAT, "VEC3", 34962),
                 "TEXCOORD_0": b.accessor(A["U"], glb.FLOAT, "VEC2", 34962)}
        if (A["C"] != 255).any():
            attrs["COLOR_0"] = b.accessor(A["C"], glb.UBYTE, "VEC4", 34962, normalized=True)
        if joint_map is not None:
            attrs["JOINTS_0"] = b.accessor(A["J"], glb.USHORT, "VEC4", 34962)
            attrs["WEIGHTS_0"] = b.accessor(A["W"], glb.FLOAT, "VEC4", 34962)
        name = materials[m].texture if m < len(materials) else "missing"
        prims.append({"attributes": attrs, "indices": b.accessor(A["I"], glb.UINT, "SCALAR", 34963),
                      "material": texcache.material(name), "mode": 4})
    return prims


def build(body_path, attach_paths, out_path, tone=None, extra_tex_dirs=(), name="character", anims=(),
          skel_path=None, skip=None, keep=KEEP, sep="9"):
    """body_path: skinned I3D_BIN with the full skeleton (or None: skeleton only, from skel_path).
    attach_paths: rigid I3D_BIN parts whose attach nodes are named '<Bone>9<name>'.
    anims: list of (name, i3m.Motion). skip: regex of attach node names to leave out.
    keep: regex of node names that are bones. sep: attachment separator ('9'; OT1 '&')."""
    b = glb.Builder()
    body = i3d.load(body_path) if body_path else None
    sk = (body or i3d.load(skel_path)).skeleton
    keep = [j for j, n in enumerate(sk.names) if keep.match(n)]
    gl_of = {}
    top = b.node(name=name, scale=[SCALE] * 3, children=[])
    b.g["scenes"][0]["nodes"].append(top)
    for j in keep:
        loc = root_local(sk) if sk.parents[j] < 0 else _local_to_kept(sk, j, keep)
        gl_of[j] = b.node(name=sk.names[j])
        b.g["nodes"][gl_of[j]].update(_trs(loc))
    for j in keep:
        p = sk.parents[j]
        while p >= 0 and p not in gl_of:  # skip non-bone helpers (OT2 'group'); see _local_to_kept
            p = sk.parents[p]
        if p >= 0:
            b.g["nodes"][gl_of[p]].setdefault("children", []).append(gl_of[j])
        else:
            b.g["nodes"][top]["children"].append(gl_of[j])
    by_name = {sk.names[j]: gl_of[j] for j in keep}
    # bind-pose model-space matrix per bone (ROOTNODE flip removed)
    bind = {sk.names[j]: sk.world[j] @ F for j in keep}

    tdirs = ([os.path.dirname(body_path)] if body_path else []) + [os.path.dirname(p) for p in attach_paths]
    tc = TextureCache(b, tdirs + list(extra_tex_dirs), tone)

    skinned = [p for p in body.parts if p.skinned] if body else []
    skinned_mats = [body.materials] * len(skinned) if body else []
    for p in skinned:
        _xform(p, skin_space(p, sk))
    for ap in attach_paths:  # skinned accessories (e.g. etc50) share the body skeleton
        m = i3d.load(ap)
        sp = [p for p in m.parts if p.skinned]
        for p in sp:
            _xform(p, skin_space(p, m.skeleton))
        own = [p for p in sp if not all(n in by_name for n in p.skin.names)]
        if own:  # OT2 pets etc.: skinned to their own bones (not exported) -> static mesh in bind pose
            mesh = b.add("meshes", {"name": os.path.basename(ap) + ":bind_pose",
                                    "primitives": _gl_prims(b, own, tc, m.materials, None)})
            b.g["nodes"][top]["children"].append(b.node(name=os.path.basename(ap).split(".")[0] + "_bind_pose",
                                                        mesh=mesh))
            sp = [p for p in sp if all(p is not q for q in own)]
        skinned += sp
        skinned_mats += [m.materials] * len(sp)
    if skinned:
        # one glTF skin over all bones; inverse bind = inverse of the bind-pose model matrix, which is what
        # every 0x46 skin in the file stores (checked: IB @ W == F for all skin bones)
        bones = [j for j in keep if sk.names[j] != "ROOTNODE"]
        jidx = {sk.names[j]: k for k, j in enumerate(bones)}
        ibm = np.array([np.linalg.inv(bind[sk.names[j]]) for j in bones], np.float32)  # row-major == glTF col-major
        skin = b.add("skins", {"joints": [gl_of[j] for j in bones], "skeleton": by_name.get("ROOTNODE", gl_of[bones[0]]),
                               "inverseBindMatrices": b.accessor(ibm, glb.FLOAT, "MAT4")})
        for p in skinned:
            p.palette = [jidx[p.skin.names[k]] for k in p.palette]
        prims = []
        for mats in {id(m): m for m in skinned_mats}.values():
            prims += _gl_prims(b, [p for p, m in zip(skinned, skinned_mats) if m is mats], tc, mats,
                               {k: k for k in range(len(bones))})
        src = body_path or attach_paths[0]
        mesh = b.add("meshes", {"name": os.path.basename(src), "primitives": prims})
        n = b.node(name=os.path.basename(src).split(".")[0], mesh=mesh, skin=skin)
        b.g["scenes"][0]["nodes"].append(n)
    if body_path:
        attach(b, body_path, by_name, bind, tc, skip, sep)  # rigid attachments inside the body file
    for ap in attach_paths:
        attach(b, ap, by_name, bind, tc, skip, sep)

    for aname, motion in anims:
        import anim
        anim.add_animation(b, aname, motion, by_name, sk)
    b.write(out_path)
    return tc


def _local_to_kept(sk, j, keep):
    """Local matrix relative to the nearest kept ancestor (OT2 bodies may have a Maya 'group' node between
    ROOTNODE and Bip01Pelvis; when the direct parent is kept this is just the file's local)."""
    p = sk.parents[j]
    if p < 0 or p in keep:
        return sk.local[j]
    while p >= 0 and p not in keep:
        p = sk.parents[p]
    return sk.world[j] @ np.linalg.inv(sk.world[p]) if p >= 0 else sk.world[j] @ F


def _trs(m):
    """row-vector local matrix -> glTF TRS dict (falls back to matrix if it has shear)."""
    M = np.asarray(m, np.float64).T
    t = M[:3, 3]
    R = M[:3, :3]
    s = np.linalg.norm(R, axis=0)
    if np.linalg.det(R) < 0:
        s[0] = -s[0]
    Rn = R / s
    if not np.allclose(Rn.T @ Rn, np.eye(3), atol=1e-3):
        return {"matrix": gl(m)}
    q = quat_from_matrix(Rn)
    out = {}
    if np.abs(t).max() > 1e-7:
        out["translation"] = [float(x) for x in t]
    if abs(q[3]) < 1 - 1e-9:
        out["rotation"] = [float(x) for x in q]
    if np.abs(s - 1).max() > 1e-6:
        out["scale"] = [float(x) for x in s]
    return out


def quat_from_matrix(R):
    """column-vector rotation matrix -> (x, y, z, w)."""
    tr = R[0, 0] + R[1, 1] + R[2, 2]
    if tr > 0:
        s = np.sqrt(tr + 1.0) * 2
        q = [(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s]
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        q = [0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s, (R[2, 1] - R[1, 2]) / s]
    elif R[1, 1] > R[2, 2]:
        s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        q = [(R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s, (R[0, 2] - R[2, 0]) / s]
    else:
        s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        q = [(R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s, (R[1, 0] - R[0, 1]) / s]
    q = np.array(q)
    q /= np.linalg.norm(q)
    return q if q[3] >= 0 else -q


def attach(b, path, by_name, bind, tc, skip=None, sep="9"):
    """Rigid part: each '<Bone>9<x>' node with mesh groups becomes a child of <Bone>."""
    m = i3d.load(path)
    sk = m.skeleton
    d = open(path, "rb").read()
    root = i3d.parse_tree(d)
    groups = _group_parts(d, root, m)
    for j, gi in _node_groups(d, root, sk):
        nm = sk.names[j]
        a = j  # the attach node is the nearest '<Bone>9<name>' ancestor (or the node itself)
        # (skip names like 'polySurface39' whose text before the separator is not a bone)
        while a >= 0 and not (sep in sk.names[a] and sk.names[a].split(sep)[0] in by_name):
            a = sk.parents[a]
        bone = sk.names[a].split(sep)[0] if a >= 0 else None
        if bone not in by_name or gi >= len(groups) or not groups[gi]:
            continue
        if skip and re.search(skip, nm):
            continue
        rigid = [p for p in groups[gi] if not p.skinned]
        if not rigid:
            continue
        local = (sk.world[j] @ F) @ np.linalg.inv(bind[bone])  # model-space placement -> bone space
        prims = _gl_prims(b, rigid, tc, m.materials, None)
        mesh = b.add("meshes", {"name": f"{os.path.basename(path)}:{nm}", "primitives": prims})
        n = b.node(name=nm, mesh=mesh)
        b.g["nodes"][n].update(_trs(local))
        b.g["nodes"][by_name[bone]].setdefault("children", []).append(n)


def _group_parts(d, root, m):
    """Parts per mesh group (type 0x2d records, in order), as i3d.read_meshes would list them."""
    out = []
    for r, _ in i3d.iter_recs(root):
        if r.type != 0x2D:
            continue
        sub = i3d.Rec(r.off, 0x52, False, root.data, 0, 0, [r])
        fake_root = sub
        _, parts = i3d.read_meshes(d, fake_root)
        out.append(parts)
    return out


def _node_groups(d, root, sk):
    """(node index, mesh group index) from each node record's 0x59 children."""
    import struct
    lst = next(c for c in root.children if c.type == 0x02 and c.count == len(sk.names) and c.children
               and c.children[0].type == 0x2A)
    for j, nrec in enumerate(lst.children):
        for r, _ in i3d.iter_recs(nrec):
            if r.type == 0x59:
                yield j, struct.unpack_from("<I", d, r.data + 4)[0]
