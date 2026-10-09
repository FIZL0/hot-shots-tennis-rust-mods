"""Sizing a source game's characters to HST's cast (standard §2 "Size").

Height: HST's own metres per centimetre, by sex — the median over HST's standard-body characters (TParam モデル
標準: model types 0, 4, 5) of Bip01 rest height / TParam 身長 — times each source character's height in cm from its
game's data, then one factor for the whole game (≤ 1) so its tallest lands at HST's upper bound 0.95 m. One factor
per game keeps the source's relative heights; per-sex metres-per-cm keeps HST's women/men proportions.
Head: chibi games (Get a Grip) shrink each character's head about the neck by its own factor: HEAD_SHARE of the way
from 1 to the factor that would bring that character's head ratio (neck joint to the top of the head mesh, over Bip01
height; the smallest over its costumes, so a hat doesn't count) to the median of HST's standard bodies; never grown;
HEAD_KEEP characters stay at 1.
"""
import csv
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools/psp2gltf"))
sys.path.insert(0, HERE)
import glb  # noqa: E402
from rerig import G, binds, norm, read, worlds  # noqa: E402

STANDARD_BODY = (0, 4, 5)  # TParam モデルタイプ of 標準 bodies (1 JJ chibi, 2 power, 3 reach, 6 Suzuki)
TOP = 0.95  # standard §2: HST's Bip01 range 0.58–0.95 m
# each head factor goes this far from 1 toward the full match of HST's median head ratio: the full match looked a
# little small-headed on Get a Grip's bodies (user, 2026-10-08), so half of it
HEAD_SHARE = 0.5
# characters whose head is left unshrunk, by the user's eye on the sized model (2026-10-08)
HEAD_KEEP = {"getagrip": {14: "user: Helghast's head looked right unshrunk"}}


def head_ratio(path):
    """(top of the head mesh - Bip01Neck height) / Bip01 height of a game-space model (HST export or rerig output)."""
    g, b = glb.read(path)
    W, parent = worlds(g)
    B, _ = binds(g, b)
    nodes = g["nodes"]

    def in_head(i):
        while True:
            if norm(nodes[i].get("name", "")) == "Bip01Head":
                return True
            if i not in parent:
                return False
            i = parent[i]

    top = -np.inf
    for i, n in enumerate(nodes):
        if "mesh" not in n:
            continue
        for p in g["meshes"][n["mesh"]]["primitives"]:
            pos = read(g, b, p["attributes"]["POSITION"])
            if "skin" in n:  # skinned positions are game space
                hj = np.array([in_head(j) for j in g["skins"][n["skin"]]["joints"]])
                w = (read(g, b, p["attributes"]["WEIGHTS_0"]) * hj[read(g, b, p["attributes"]["JOINTS_0"]).astype(np.int64)]).sum(1)
                v = pos[w > 0.5]
            elif in_head(i):
                v = (G @ W[i] @ np.c_[pos, np.ones(len(pos))].T).T[:, :3]
            else:
                continue
            if len(v):
                top = max(top, float(-v[:, 1].min()))
    return (top + B["Bip01Neck"][1, 3]) / -B["Bip01"][1, 3]


def hst():
    """HST's metres per cm by sex ('f'/'m') and target head ratio, from standard/hst_skeleton.json."""
    cs = [c for c in json.load(open(os.path.join(ROOT, "standard/hst_skeleton.json")))["characters"] if c["model_type"] in STANDARD_BODY]
    k = {s: float(np.median([c["bip01_height"] / c["height_cm"] for c in cs if c["sex"] == s])) for s in "fm"}
    return k, float(np.median([c["head_ratio"] for c in cs]))


def getagrip():
    """slug -> (sex, height cm, source) for Get a Grip: height class from chrsel_param_chara.csv (the number after the
    name, = character.csv Height / 1.15), sex from Parts_Body.txt PC_SEX of the character's own Body_3NN (0 f, 1 m)."""
    base = os.path.join(ROOT, "out/files/getagrip/PSP_GAME/USRDIR/xbdata")
    sel = glob.glob(base + "/menu/**/chrsel_param_chara.csv", recursive=True)[0]
    rows = [r for r in csv.reader(open(sel, encoding="cp932")) if r and r[0][-3:].isdigit()]
    body = list(csv.reader(open(glob.glob(base + "/common/**/Parts_Body.txt", recursive=True)[0], encoding="utf-8-sig"), delimiter="\t"))
    h = body[0]
    sex = {int(r[h.index("PC_ONLY_1")]): "fm"[int(r[h.index("PC_SEX")])] for r in body[1:] if r[0].startswith("Body_3")}
    out = {}
    for n, r in enumerate(rows):
        out[n] = (sex[n], int(r[0][-3:]), f"chrsel_param_chara.csv height class {r[0][-3:]}, Parts_Body Body_3{n:02d} PC_SEX")
    return out


def plan(game, models):
    """game, {pc number: [plain-rerigged model paths]} -> ({pc: (height m, why)}, {pc: (head factor, why)}, info)
    or None."""
    if game != "getagrip":
        return None
    k, want = hst()
    src = getagrip()
    raw = {n: k[src[n][0]] * src[n][1] for n in models}
    c = min(1.0, TOP / max(raw.values()))
    sizes = {n: (raw[n] * c, f"{src[n][2]}: {src[n][1]} cm {'woman' if src[n][0] == 'f' else 'man'} × HST {k[src[n][0]]:.6f} m/cm × game factor {c:.4f}")
             for n in models}
    heads = {}
    for n in models:
        r = min(head_ratio(p) for p in models[n])
        f = min(1.0, 1 - HEAD_SHARE * (1 - want / r))
        why = f"head ratio {r:.3f}, {HEAD_SHARE:g} of the way to HST's {want:.3f}"
        if n in HEAD_KEEP.get(game, {}):
            f, why = 1.0, f"head ratio {r:.3f}, kept: {HEAD_KEEP[game][n]}"
        heads[n] = (f, why)
    return sizes, heads, {"hst_m_per_cm": k, "game_factor": c, "head_ratio_hst": want, "head_share": HEAD_SHARE}
