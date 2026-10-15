"""Get a Grip's eight chair umpires' models and motions -> each umpire mod's `umpire.glb` (standard/
HST-COURT-UMPIRE-STANDARD.md §3b; HST-Remastered task M8f4).

    python3 tools/psp2gltf/export_getagrip_umpires.py

Reads out/files/getagrip/.../xbdata/game/200_court/umpire.xb (unpacked), writes out/mods/gag_umpNN_<name>/umpire.glb
next to the voices tools/rerig/gag_umpires.py packaged (run that first; it keeps the glb). Game data: out/ only.

umpire.xb holds u_00..u_07 (model u_NN.psp.i3r, seated, one 28-33 node skeleton shared by all eight: no leg bones,
the legs ride the pelvis; u_02/03/05-07's hands, u_02's legs and a u_04 pelvis piece
are one-bone groups stored in that bone's space, which i3d.py flags `bone_local` and build.py places by the bone's
bind world) and motions: u_00 and u_04 have h/r/l/w/s/r_w/l_w, the others only s (each the same
gesture as u_00's). The ones without their own set take u_00's (same skeleton; u_04's set equals u_00's key for key
on the sampled frames). What each motion is, by its poses (rendered, 2026-10-14):
  h    both hands brought together and held (0.5 s)        -> `idle`: HST's umpire motion 0, frame 0 during play,
                                                              played through once the match is over
  r/l  the right / left arm out toward that end, held       -> `turn_r` / `turn_l`: HST's motions 1 / 2 (u_r / u_l)
  w    seated breathing loop (2 s)                         -> `wait`: looped during play
  s    a head-turned arm gesture back to rest (1.8 s), r_w/l_w the arm held out, breathing: not used (HST has no slot)
The PSP game's code is encrypted, so which motion it plays when is not known; the HST names (`_h`, `_r`, `_l`) are
the same as the disc umpires' files.

Into HST game space (Y down, metres, facing +Z): f = Get a Grip's metres per centimetre from tools/rerig/sizing.py
(pc13 Gloria's Bip01 57.9 cm -> HST Gloria's 0.8554 m), the head shrunk about the neck by the cast's head factor
(0.6277, getagrip_pc13_gloria's size_why) as the players' are, and the seat at the origin: SEAT_CM is the underside
of u_00 behind the pelvis (52.9 cm, 5 cm under Bip01Pelvis at bind), the same skeleton for all eight; the motions
key the pelvis 45.7 cm lower than the bind pose, so the seat is at the origin in the animations (the bind pose,
never drawn, sits above it).
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools/rerig"))

import build  # noqa: E402
import glb  # noqa: E402
import i3m  # noqa: E402
from gag_umpires import UMPIRES  # noqa: E402

XB = os.path.join(ROOT, "out/files/getagrip/PSP_GAME/USRDIR/xbdata/game/200_court/umpire.xb/data/umpire")
RAW = os.path.join(ROOT, "out/models/getagrip/umpires")
F = 0.8554 / 57.9  # m per Get a Grip cm (Gloria-calibrated, sizing.py)
HEAD = 0.6277  # head scale about the neck (sizing.py, one factor for Get a Grip's cast)
SEAT_CM = 52.9
G = np.diag([-1.0, -1.0, 1.0, 1.0])  # glTF Y-up <-> HST game space (rerig.G)
MOTIONS = {"idle": "h", "turn_r": "r", "turn_l": "l", "wait": "w"}
HEAD_NODES = ("Bip01Head", "Bip01HeadNub")


def motion(n, k):
    p = os.path.join(XB, f"motion/umpire/u_{n:02d}/u_{n:02d}_{k}.i3m")
    return i3m.load(p if os.path.exists(p) else os.path.join(XB, f"motion/umpire/u_00/u_00_{k}.i3m"))


def quat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def trs(n):
    m = np.eye(4)
    m[:3, :3] = quat(n.get("rotation", [0, 0, 0, 1])) @ np.diag(n.get("scale", [1, 1, 1]))
    m[:3, 3] = n.get("translation", [0, 0, 0])
    return m


def bake(src, dst):
    """build.py's glTF (Y up, a 0.01-scaled top node over centimetre joints) -> game space under `game_space`.
    Every joint local L becomes K L K^-1 (K = f G: rotation G R G, translation f G t), the top joints also lifted by
    T (seat at the origin); skinned vertices T K v, rigid ones K v, inverse binds K IBM K^-1 T^-1; animation keys
    the same way. Then the head: vertices on Bip01Head/HeadNub (by weight) and rigid parts under the head scaled
    about the head joint, HeadNub's offset with them."""
    g, b = glb.read(src)
    nodes = g["nodes"]
    out = glb.Builder()
    out.bin = bytearray(b)
    out.g = {k: v for k, v in g.items() if k != "buffers"}
    K = G.copy()
    K[:3, :3] *= F
    Ki = np.linalg.inv(K)
    top = g["scenes"][0]["nodes"][0]  # build.py's scaled top node: dropped, its children become roots
    roots = list(nodes[top].get("children", []))
    parent = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}
    by_name = {n.get("name"): i for i, n in enumerate(nodes)}
    head = by_name["Bip01Head"]
    # the motions key Bip01Pelvis lower than the bind pose (the model's origin is the seat in motion, its feet at
    # bind): the seat in `idle`'s first frame goes to y = 0, the bind pose stays above it
    pelvis = by_name["Bip01Pelvis"]
    idle = next(a for a in g["animations"] if a["name"] == "idle")
    key = next(c for c in idle["channels"] if c["target"] == {"node": pelvis, "path": "translation"})
    drop = nodes[pelvis]["translation"][1] - glb.get_accessor(g, b, idle["samplers"][key["sampler"]]["output"])[0][1]
    T = np.eye(4)
    T[1, 3] = (SEAT_CM - drop) * F  # the seat (SEAT_CM up at bind) to y = 0, Y down

    def under_head(i):
        while i in parent:
            if i == head:
                return True
            i = parent[i]
        return i == head

    def in_head(i):
        """A node whose offset scales with the head (below it; rigid parts there scale their vertices too)."""
        return i != head and under_head(i)

    def setlocal(n, m):
        for k in ("translation", "rotation", "scale", "matrix"):
            n.pop(k, None)
        n.update(build._trs(m.T))  # build._trs takes row-vector matrices

    # joint locals; the head's children's offsets scaled with it
    local = {}
    for i, n in enumerate(nodes):
        if i == top or "skin" in n:
            continue
        m = K @ trs(n) @ Ki
        if i in roots:
            m = T @ m
        if in_head(i):
            m[:3, 3] *= HEAD
        local[i] = m
        setlocal(n, m)
    world = {}

    def w(i):
        if i not in world:
            world[i] = (w(parent[i]) if parent.get(i) in local else np.eye(4)) @ local[i]
        return world[i]

    hw = w(head)
    centre = hw[:3, 3]
    for i, n in enumerate(nodes):
        if "mesh" not in n:
            continue
        skinned = "skin" in n
        if skinned:
            joints = g["skins"][n["skin"]]["joints"]
            heady = np.array([nodes[j].get("name") in HEAD_NODES or under_head(j) for j in joints])
        prims = g["meshes"][n["mesh"]]["primitives"]
        for p in prims:
            a = p["attributes"]
            P = glb.get_accessor(g, b, a["POSITION"]).astype(np.float64)
            N = glb.get_accessor(g, b, a["NORMAL"]).astype(np.float64)
            if skinned:
                P = (T @ K @ np.c_[P, np.ones(len(P))].T).T[:, :3]
                share = (glb.get_accessor(g, b, a["WEIGHTS_0"]) * heady[glb.get_accessor(g, b, a["JOINTS_0"]).astype(np.int64)]).sum(1)
                P = centre + (P - centre) * (1 + (HEAD - 1) * share)[:, None]
            else:
                P = (K @ np.c_[P, np.ones(len(P))].T).T[:, :3] * (HEAD if under_head(i) else 1.0)
            N = N @ G[:3, :3].T
            a["POSITION"] = out.accessor(P.astype(np.float32), glb.FLOAT, "VEC3", 34962, minmax=True)
            a["NORMAL"] = out.accessor(N.astype(np.float32), glb.FLOAT, "VEC3", 34962)
        if skinned:
            sk = g["skins"][n["skin"]]
            # every joint's ancestors joints too (ROOTNODE carries the seat lift; a player drops non-joint nodes)
            for j in list(sk["joints"]):
                while parent.get(j) in local and parent[j] not in sk["joints"]:
                    j = parent[j]
                    sk["joints"].append(j)
            sk["inverseBindMatrices"] = out.accessor(np.array([np.linalg.inv(w(j)).T for j in sk["joints"]], np.float32), glb.FLOAT, "MAT4")
            sk.pop("skeleton", None)
            setlocal(n, np.eye(4))
    for an in g.get("animations", []):
        for c in an["channels"]:
            s = an["samplers"][c["sampler"]]
            i, path = c["target"]["node"], c["target"]["path"]
            v = glb.get_accessor(g, b, s["output"]).astype(np.float64)
            if path == "rotation":
                v = v * np.array([-1.0, -1.0, 1.0, 1.0])  # G R G
            elif path == "translation":
                v = v @ (F * G[:3, :3]).T
                if i in roots:
                    v = v + T[:3, 3]
                if in_head(i):
                    v = v * HEAD
            s["output"] = out.accessor(v.astype(np.float32), glb.FLOAT, "VEC4" if path == "rotation" else "VEC3")
    gs = out.node(name="game_space", rotation=[0.0, 0.0, 1.0, 0.0], children=roots + [i for i in g["scenes"][0]["nodes"] if i != top])
    out.g["scenes"] = [{"nodes": [gs]}]
    out.g["scene"] = 0
    nodes[top] = {"name": "unused"}  # the dropped scale node, left childless (indices stay)
    compact(out).write(dst)


def compact(b):
    """A copy holding only the buffer views the document still points at."""
    c = glb.Builder()
    c.g = {k: v for k, v in b.g.items() if k not in ("bufferViews", "accessors")}
    c.g["bufferViews"], c.g["accessors"] = [], []
    views = {}

    def view(i):
        if i not in views:
            v = b.g["bufferViews"][i]
            o = v.get("byteOffset", 0)
            views[i] = c.view(bytes(b.bin[o:o + v["byteLength"]]), v.get("target"))
        return views[i]

    acc = {}

    def accessor(i):
        if i not in acc:
            a = dict(b.g["accessors"][i])
            a["bufferView"] = view(a["bufferView"])
            c.g["accessors"].append(a)
            acc[i] = len(c.g["accessors"]) - 1
        return acc[i]

    for m in c.g.get("meshes", []):
        for p in m["primitives"]:
            p["attributes"] = {k: accessor(v) for k, v in p["attributes"].items()}
            p["indices"] = accessor(p["indices"])
    for s in c.g.get("skins", []):
        s["inverseBindMatrices"] = accessor(s["inverseBindMatrices"])
    for an in c.g.get("animations", []):
        for s in an["samplers"]:
            s["input"], s["output"] = accessor(s["input"]), accessor(s["output"])
    for im in c.g.get("images", []):
        im["bufferView"] = view(im["bufferView"])
    return c


def main():
    os.makedirs(RAW, exist_ok=True)
    for n, (slug, name, _, _) in UMPIRES.items():
        raw = os.path.join(RAW, f"u_{n:02d}.glb")
        build.build(os.path.join(XB, f"model/umpire/u_{n:02d}/u_{n:02d}.psp.i3r"), [], raw, name=f"u_{n:02d}",
                    anims=[(a, motion(n, k)) for a, k in MOTIONS.items()])
        mod = os.path.join(ROOT, f"out/mods/gag_ump{n:02d}_{slug}")
        os.makedirs(mod, exist_ok=True)
        bake(raw, os.path.join(mod, "umpire.glb"))
        man = os.path.join(mod, "mod.json")
        if os.path.exists(man):  # gag_umpires.py's manifest: the model is no longer a todo
            m = json.load(open(man))
            m["todo"] = [t for t in m.get("todo", []) if not t.startswith("umpire.glb")]
            if not m["todo"]:
                del m["todo"]
            m["model_why"] = (f"u_{n:02d}.psp.i3r with " + ("its own" if os.path.exists(os.path.join(XB, f"motion/umpire/u_{n:02d}/u_{n:02d}_h.i3m")) else "u_00's")
                              + " motions: idle = _h, turn_r = _r, turn_l = _l, wait = _w; Gloria-calibrated size, head x0.6277, seat at the origin")
            json.dump(m, open(man, "w"), indent=1, ensure_ascii=False)
        print(os.path.join(mod, "umpire.glb"), name)


if __name__ == "__main__":
    main()
