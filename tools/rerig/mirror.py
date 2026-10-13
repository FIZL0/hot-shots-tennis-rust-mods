"""Left-handed golf mods: find the golf glove, and pre-mirror a costume so HST's left-hander mirror undoes it.

python3 tools/rerig/mirror.py glove <costume.glb>…          per costume: which hand wears a glove
python3 tools/rerig/mirror.py mirror <in.glb> <out.glb>     write the pre-mirrored copy

Golfers wear their glove on the hand that leads the grip, the left for a right-handed swing; in HST the glove hand is
the racket hand (standard §6 `hand`). HST draws a left-hander mirrored (the whole rig at x scale −1) and keeps the
racket on `Bip01RHand`, so `"hand": "left"` alone would put the racket in the drawn left hand but the glove in the drawn
right. A gloved golf mod therefore ships each costume mirrored across the character's middle (x = 0 in game space):
positions, normals, tangents and morph offsets reflected, each left joint's weights moved to its right twin and back,
triangle winding flipped. The game's mirror then brings the source's own look back (glove on the left, text reading
the right way) with `Bip01RHand`, and the racket, in that gloved hand.

Joints stay HST's (motions drive them by name). A vertex on joint j moves to j's twin m(j) and keeps its place
relative to it: v' = S·v + Σ wᵢ (P(m(jᵢ)) − S·P(jᵢ)), S the reflection, P the bind position (0 for a symmetric
skeleton; rerigged ones are within a few mm). Extra joints pair by mirrored bind position (≤ 1 cm, the L/R-swapped
name first); one without a twin gets a mirrored copy (`<name>_mirror`, same `extras`, so springs keep swinging).
Rigid mesh nodes (PSP heads, on `Bip01Head`) are reflected in their node's space.
"""
import io
import json
import os
import re
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools/psp2gltf"))
sys.path.insert(0, HERE)
import glb  # noqa: E402
from rerig import read, worlds, node_mat, mat_quat  # noqa: E402

S3 = np.diag([-1.0, 1.0, 1.0])
S4 = np.diag([-1.0, 1.0, 1.0, 1.0])
# mean texture colour of the two hands' vertices further apart than this (sum of |ΔRGB|) = one hand gloved. Measured
# over the 72 golf mods: bare/both-gloved pairs 0–11, one-glove pairs 44–564.
GLOVE_DIFF = 25
# per mod id: the gloved side where the colour test can't tell (none so far: in every costume with differing hands
# the right hand is skin-coloured and the left a glove or wrap)
GLOVE_OVERRIDE = {}


def _side(name):
    n = name.replace(" ", "")
    if n.startswith(("Bip01LHand", "Bip01LFinger")):
        return "L"
    if n.startswith(("Bip01RHand", "Bip01RFinger")):
        return "R"
    return None


def glove(path):
    """One costume -> ("left" | None, why): the left hand's texture colour differs from the right's."""
    from PIL import Image
    g, b = glb.read(path)
    imgs, col, mats = {}, {"L": [], "R": []}, {"L": set(), "R": set()}

    def img(i):
        if i not in imgs:
            v = g["bufferViews"][g["images"][i]["bufferView"]]
            o = v.get("byteOffset", 0)
            imgs[i] = np.asarray(Image.open(io.BytesIO(b[o:o + v["byteLength"]])).convert("RGB"), np.float64)
        return imgs[i]
    for n in g["nodes"]:
        if "mesh" not in n or "skin" not in n:
            continue
        side = np.array([_side(g["nodes"][j]["name"]) or "" for j in g["skins"][n["skin"]]["joints"]])
        for p in g["meshes"][n["mesh"]]["primitives"]:
            a = p["attributes"]
            if "JOINTS_0" not in a or "TEXCOORD_0" not in a:
                continue
            J, W = read(g, b, a["JOINTS_0"]).astype(np.int64), read(g, b, a["WEIGHTS_0"])
            mat = g["materials"][p["material"]] if "material" in p else {}
            tex = mat.get("pbrMetallicRoughness", {}).get("baseColorTexture", {}).get("index")
            uv = read(g, b, a["TEXCOORD_0"])
            for s in "LR":
                m = (W * (side[J] == s)).sum(1) > 0.5
                if not m.any():
                    continue
                mats[s].add(mat.get("name", "?"))
                if tex is not None:
                    I = img(g["textures"][tex]["source"])
                    h, w, _ = I.shape
                    u = uv[m]
                    col[s].append(I[(np.mod(u[:, 1], 1) * h).astype(int).clip(0, h - 1), (np.mod(u[:, 0], 1) * w).astype(int).clip(0, w - 1)])
    if not col["L"] or not col["R"]:
        return None, "no textured hand vertices"
    L, R = (np.concatenate(col[s]).mean(0) for s in "LR")
    d = float(np.abs(L - R).sum())
    rgb = lambda c: "#%02x%02x%02x" % tuple(int(round(x)) for x in c)  # noqa: E731
    if d < GLOVE_DIFF:
        return None, f"hands alike (left {rgb(L)}, right {rgb(R)}: bare or both gloved)"
    return "left", f"left hand {rgb(L)} ({', '.join(sorted(mats['L']))}) vs right {rgb(R)} ({', '.join(sorted(mats['R']))})"


def gloved(mod_id, costumes):
    """A mod -> (left-handed?, why, per-costume findings). Left when any costume wears a left glove."""
    found = {os.path.basename(c): glove(c) for c in costumes}
    if mod_id in GLOVE_OVERRIDE:
        side, why = GLOVE_OVERRIDE[mod_id]
        return side == "left", why, found
    left = [k for k, (s, _) in found.items() if s == "left"]
    if left:
        k = left[0]
        why = (f"golf glove on the left hand in {len(left)} of {len(found)} costumes (e.g. {k}: {found[k][1]}); glove hand = "
               "racket hand, so left-handed, its costumes pre-mirrored (tools/rerig/mirror.py) so HST's left-hander mirror "
               "shows the source's own look with the racket in the gloved hand")
    else:
        why = f"no costume wears a one-hand glove ({next(iter(found.values()))[1]}): stays right-handed"
    return bool(left), why, found


def _twin_name(n):
    for a, b in (("Bip01L", "Bip01R"), ("Left", "Right"), ("left", "right")):
        if a in n:
            return n.replace(a, b)
        if b in n:
            return n.replace(b, a)
    m = re.match(r"^(.*?)(?<![A-Za-z])([LRlr])(?=[A-Z_0-9.]|$)(.*)$", n)
    if m:
        sw = {"L": "R", "R": "L", "l": "r", "r": "l"}[m.group(2)]
        return m.group(1) + sw + m.group(3)
    m = re.match(r"^([LR])([a-z].*)$", n)
    if m:
        return {"L": "R", "R": "L"}[m.group(1)] + m.group(2)
    m = re.match(r"^(.*[a-z_])([LRlr])$", n)
    if m:
        return m.group(1) + {"L": "R", "R": "L", "l": "r", "r": "l"}[m.group(2)]
    return None


def mirror(src, dst):
    """Write src's pre-mirrored copy to dst; returns {"paired", "copied", "fallback"} joint counts."""
    g, b = glb.read(src)
    b = bytearray(b)
    nodes = g["nodes"]
    assert len(g.get("skins", [])) == 1, "one skin (standard §2)"
    skin = g["skins"][0]
    ibm = read(g, bytes(b), skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1).astype(np.float64)
    joints = list(skin["joints"])
    B = [np.linalg.inv(m) for m in ibm]
    P = np.array([m[:3, 3] for m in B])
    names = [nodes[j]["name"].replace(" ", "") for j in joints]
    idx = {n: k for k, n in enumerate(names)}
    _, parent = worlds(g)
    jpar = [idx.get(nodes[parent[j]]["name"].replace(" ", "")) if j in parent else None for j in joints]
    tol = 0.01
    twin = [None] * len(joints)
    stats = {"paired": 0, "copied": 0, "midline": 0}
    for k, n in enumerate(names):  # core and name-swapped pairs
        t = _twin_name(n)
        if abs(P[k, 0]) < 0.005 and (t is None or t not in idx):
            twin[k] = k
            stats["midline"] += 1
        elif t in idx and np.linalg.norm(S3 @ P[k] - P[idx[t]]) < (0.05 if n.startswith("Bip01") else tol):
            twin[k] = idx[t]
            stats["paired"] += 1
    for k in range(len(joints)):  # extras by position: same mirrored spot, twin parents
        if twin[k] is not None:
            continue
        cand = [c for c in range(len(joints)) if c != k and np.linalg.norm(S3 @ P[k] - P[c]) < tol
                and (twin[c] is None or twin[c] == k)]
        cand.sort(key=lambda c: (jpar[c] is None or jpar[k] is None or twin[jpar[k]] != jpar[c], np.linalg.norm(S3 @ P[k] - P[c])))
        if cand:
            twin[k], twin[cand[0]] = cand[0], k
            stats["paired"] += 2
    # the rest that carry vertices: a mirrored copy of the joint, under its parent's twin (copied too if need be)
    used = set()
    for n in nodes:
        if "skin" in n and "mesh" in n:
            for p in g["meshes"][n["mesh"]]["primitives"]:
                J = read(g, bytes(b), p["attributes"]["JOINTS_0"]).astype(np.int64)
                W = read(g, bytes(b), p["attributes"]["WEIGHTS_0"])
                used.update(np.unique(J[W > 0]).tolist())
    new_ibm = []

    def copy(k):
        p = jpar[k]
        assert p is not None, f"{names[k]}: a root without a twin"
        if twin[p] is None:
            copy(p)
        Bk = S4 @ B[k] @ S4
        local = np.linalg.inv(B[twin[p]]) @ Bk
        sc = np.linalg.norm(local[:3, :3], axis=0)  # a scaled joint (oob pc01's head tape) keeps its scale
        node = {"name": nodes[joints[k]]["name"] + "_mirror", "translation": [float(x) for x in local[:3, 3]],
                "rotation": [float(x) for x in mat_quat(local[:3, :3] / sc)]}
        if not np.allclose(sc, 1, atol=1e-6):
            node["scale"] = [float(x) for x in sc]
        if "extras" in nodes[joints[k]]:
            node["extras"] = json.loads(json.dumps(nodes[joints[k]]["extras"]))
            # its vertices all move to the copy: the original would swing with nothing on it
            nodes[joints[k]]["extras"].pop("spring", None)
        nodes.append(node)
        nodes[joints[twin[p]]].setdefault("children", []).append(len(nodes) - 1)
        joints.append(len(nodes) - 1)
        B.append(Bk)
        jpar.append(twin[p])
        twin.append(k)
        twin[k] = len(joints) - 1
        new_ibm.append(np.linalg.inv(Bk))
        stats["copied"] += 1
    for k in sorted(used, key=lambda k: len(_chain(k, jpar))):
        if twin[k] is None:
            copy(k)
    P = np.array([m[:3, 3] for m in B])
    twin = [k if t is None else t for k, t in enumerate(twin)]  # unused, unpaired (Racket): no vertex to move
    twin = np.array(twin, dtype=np.int64)

    done = set()

    def put(ai, arr):
        """Overwrite accessor ai's tightly packed data in place."""
        a = g["accessors"][ai]
        assert "sparse" not in a and not a.get("normalized"), "dense, unnormalized accessors (rerig.py writes these)"
        v = g["bufferViews"][a["bufferView"]]
        n = glb._NC[a["type"]]
        dt = glb._DT[a["componentType"]]
        assert v.get("byteStride", 0) in (0, n * np.dtype(dt).itemsize)
        data = np.ascontiguousarray(arr, dt).tobytes()
        assert len(data) == a["count"] * n * np.dtype(dt).itemsize
        o = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        b[o:o + len(data)] = data
        if "min" in a:
            r = np.asarray(arr, np.float64).reshape(a["count"], n)
            a["min"], a["max"] = [float(x) for x in r.min(0)], [float(x) for x in r.max(0)]

    def once(ai, fn):
        if ai in done:
            return
        done.add(ai)
        put(ai, fn(read(g, bytes(b), ai)))

    Wd, _ = worlds(g)
    for ni, n in enumerate(nodes):
        if "mesh" not in n:
            continue
        mesh = g["meshes"][n["mesh"]]
        if "skin" in n:
            L3 = None
        else:  # rigid: reflect in the node's own space (its parent is a midline joint)
            Wn = Wd[ni]
            L4 = np.linalg.inv(Wn) @ S4 @ Wn
            L3 = L4[:3, :3]
        for p in mesh["primitives"]:
            assert p.get("mode", 4) == 4 and "indices" in p, "indexed triangle lists"
            at = p["attributes"]
            if L3 is None:
                J = read(g, bytes(b), at["JOINTS_0"]).astype(np.int64)
                W = read(g, bytes(b), at["WEIGHTS_0"]).astype(np.float64)
                corr = (W[..., None] * (P[twin[J]] - P[J] @ S3)).sum(1)
                assert at["POSITION"] not in done, "a position accessor shared between primitives"
                once(at["POSITION"], lambda x: x @ S3 + corr)
                once(at["JOINTS_0"], lambda x: twin[x.astype(np.int64)])
                lin = S3
            else:
                once(at["POSITION"], lambda x: x @ L4[:3, :3].T + L4[:3, 3])
                lin = L3
            if "NORMAL" in at:
                once(at["NORMAL"], lambda x: x @ lin.T)
            if "TANGENT" in at:
                once(at["TANGENT"], lambda x: np.hstack([x[:, :3] @ lin.T, -x[:, 3:]]))
            for t in p.get("targets", []):
                for k in ("POSITION", "NORMAL"):
                    if k in t:
                        once(t[k], lambda x: x @ lin.T)
            once(p["indices"], lambda x: x.reshape(-1, 3)[:, [0, 2, 1]].ravel())

    if new_ibm:  # the copies' inverse binds: a fresh accessor at the end of the buffer
        allm = np.concatenate([ibm, np.array(new_ibm)]).transpose(0, 2, 1).astype(np.float32)
        while len(b) % 4:
            b.append(0)
        g["bufferViews"].append({"buffer": 0, "byteOffset": len(b), "byteLength": allm.nbytes})
        b += allm.tobytes()
        g["accessors"].append({"bufferView": len(g["bufferViews"]) - 1, "componentType": glb.FLOAT, "count": len(allm), "type": "MAT4"})
        skin["inverseBindMatrices"] = len(g["accessors"]) - 1
        skin["joints"] = joints
    g.setdefault("extras", {})["hst_mirrored"] = ("pre-mirrored for a left-hander (tools/rerig/mirror.py): HST's mirror shows "
                                                  "the source's own look with the racket in the gloved left hand")
    while len(b) % 4:
        b.append(0)
    g["buffers"] = [{"byteLength": len(b)}]
    js = json.dumps(g, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    out = bytearray(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(b)))
    out += struct.pack("<I", len(js)) + b"JSON" + js
    out += struct.pack("<I", len(b)) + b"BIN\0" + b
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)  # may be a hard link into out/rerig
    open(dst, "wb").write(out)
    return stats


def _chain(k, jpar):
    c = []
    while k is not None:
        c.append(k)
        k = jpar[k]
    return c


if __name__ == "__main__":
    if sys.argv[1:2] == ["glove"]:
        for p in sys.argv[2:]:
            print(os.path.basename(p), *glove(p))
    elif sys.argv[1:2] == ["mirror"]:
        print(mirror(sys.argv[2], sys.argv[3]))
    else:
        print(__doc__)
