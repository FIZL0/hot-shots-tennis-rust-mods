"""Add the HST face channels a packaged model lacks, by rerig.py's FACE_WORDS / FACE_NAMES, in place.

python3 tools/rerig/face_alias.py MOD_DIR…     (every model/*.glb of each mod)

For mods already packaged when a stand-in was added to those tables: the same aliases a fresh rerig would append
(each a copy, or the sum, of the model's own targets), without rerigging, mirroring or repackaging. Channels the model
already has are left alone. Bump the mod's mod.json `version` before uploading it again.
"""
import glob
import json
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rerig import face_names, glb, read  # noqa: E402


def add_aliases(path):
    """-> the channels added to path's face meshes (rewritten only if any)."""
    g, b = glb.read(path)
    b = bytearray(b)
    added = []

    def accessor(arr):
        while len(b) % 4:
            b.append(0)
        data = np.ascontiguousarray(arr, np.float32).tobytes()
        g["bufferViews"].append({"buffer": 0, "byteOffset": len(b), "byteLength": len(data)})
        b.extend(data)
        g["accessors"].append({"bufferView": len(g["bufferViews"]) - 1, "componentType": glb.FLOAT,
                               "count": len(arr), "type": "VEC3"})
        return len(g["accessors"]) - 1

    for m in g.get("meshes", []):
        names = m.get("extras", {}).get("targetNames")
        if not names:
            continue
        short, alias = face_names(names)
        if not alias:
            continue
        for pr in m["primitives"]:
            ts = pr["targets"]
            for _, src in alias:
                if len(src) == 1:
                    ts.append(dict(ts[src[0]]))
                else:
                    ts.append({k: accessor(sum(read(g, bytes(b), ts[j][k]).astype(np.float64) for j in src))
                               for k in ts[src[0]]})
        m["extras"]["targetNames"] = short + [a for a, _ in alias]
        if "weights" in m:
            m["weights"] = m["weights"] + [0.0] * len(alias)
        added += [a for a, _ in alias]
    if added:
        while len(b) % 4:
            b.append(0)
        g["buffers"][0]["byteLength"] = len(b)
        js = json.dumps(g, separators=(",", ":")).encode()
        js += b" " * (-len(js) % 4)
        out = bytearray(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(b)))
        out += struct.pack("<I", len(js)) + b"JSON" + js
        out += struct.pack("<I", len(b)) + b"BIN\0" + b
        open(path, "wb").write(out)
    return added


if __name__ == "__main__":
    for d in sys.argv[1:]:
        for f in sorted(glob.glob(os.path.join(d, "model", "*.glb"))):
            print(os.path.relpath(f), add_aliases(f) or "-")
