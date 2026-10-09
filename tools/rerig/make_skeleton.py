"""Writes standard/hst_skeleton.json: the HST player skeleton every mod character must carry.

python3 tools/rerig/make_skeleton.py [TParam.csv]   (needs out/models/hst/pcNN_c00.glb from `fore2gltf hst`;
TParam.csv from the HST disc's PCDATA.XB, for each character's sex, 身長 and model type; without it they are kept
from the existing JSON)

Canonical frame data is pc00's (Ashley); every HST character shares names, parents and bone axes (bind orientations
within ~10°), only proportions differ, so `characters` lists each one's measures as the allowed range.
"""
import csv
import glob
import io
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools/psp2gltf"))
sys.path.insert(0, HERE)
import glb  # noqa: E402
from rerig import binds, mat_quat  # noqa: E402
from sizing import head_ratio  # noqa: E402

NAMES = ["Ashley", "Cody", "Jun", "Kaito", "Momoko", "JJ", "Carol", "Big Chief", "Miranda", "Kent", "Lola", "Will",
         "Gloria", "Suzuki"]
FACE = ["blink_eye", "joy_eye", "joy_mouth", "anger_eye", "anger_mouth", "sorrow_eye", "sorrow_mouth", "doki_eye",
        "doki_mouth"]


def tparam(path):
    """index -> sex ('f'/'m'), 身長 (cm), モデルタイプ, from HST's TParam.csv (cp932)."""
    rows = list(csv.reader(io.StringIO(open(path, "rb").read().decode("cp932"))))
    h = rows[0]
    return {int(r[0]): {"sex": "f" if r[h.index("性別")] == "女" else "m", "height_cm": int(r[h.index("身長")]),
                        "model_type": int(r[h.index("モデルタイプ")])} for r in rows[1:] if r and r[0].isdigit()}


def main():
    path = os.path.join(ROOT, "standard/hst_skeleton.json")
    old = {c["index"]: c for c in json.load(open(path))["characters"]} if os.path.exists(path) else {}
    tp = tparam(sys.argv[1]) if len(sys.argv) > 1 else {}
    chars = []
    ref = None
    for p in sorted(glob.glob(os.path.join(ROOT, "out/models/hst/pc*_c00.glb"))):
        g, b = glb.read(p)
        B, parent = binds(g, b)
        core = [n for n in B if n.startswith("Bip01")] + ["Racket"]
        if ref is None:
            ref = (core, B, parent)
        targets = sorted({t.split("\x01")[-1] for m in g["meshes"] for t in m.get("extras", {}).get("targetNames", [])})
        n = int(os.path.basename(p)[2:4])
        chars.append({"index": n, "name": NAMES[n], "bip01_height": round(-B["Bip01"][1, 3], 4),
                      "head_height": round(-B["Bip01Head"][1, 3], 4), "face_targets": targets})
        meta = tp.get(n) or {k: old.get(n, {}).get(k) for k in ("sex", "height_cm", "model_type")}
        chars[-1].update(meta, head_ratio=round(head_ratio(p), 4))
    core, B, parent = ref
    joints = []
    for n in core:
        P = parent[n]
        local = np.linalg.inv(B[P]) @ B[n] if P in core else B[n]
        joints.append({"name": n, "parent": P if P in core else None,
                       "bind_position": [round(float(x), 5) for x in B[n][:3, 3]],
                       "bind_rotation": [round(float(x), 6) for x in mat_quat(B[n][:3, :3])],
                       "rest_translation": [round(float(x), 5) for x in local[:3, 3]],
                       "rest_rotation": [round(float(x), 6) for x in mat_quat(local[:3, :3])]})
    out = {"about": "HST player skeleton (game space: metres, Y down, feet at y=0, facing +Z). Canonical frames from "
                    "pc00; see standard/HST-CHARACTER-STANDARD.md.",
           "joints": joints, "face_channels": FACE, "characters": chars}
    json.dump(out, open(path, "w"), indent=1)
    print(path, len(joints), "joints,", len(chars), "characters")


if __name__ == "__main__":
    main()
