"""A mod's racket.glb (standard §1) from a source game's rigid racket part.

python3 tools/rerig/racket.py PART.glb MODEL.glb OUT.glb [--node NAME] [--length M]

PART: the racket on the source's reference skeleton (Get a Grip: out/models/getagrip/parts/racket/racketNN.glb, the
mesh on `Bip01RHand9racketNN_game`, rigid under `Bip01 R Hand`). MODEL: the rerigged costume it goes with (its
`extras.scale` is the size rerig gave the body). The racket keeps the source's grip on the hand exactly (its pose
relative to the hand at bind, scaled with the body), is then resized about the hand's point on the handle to HST's
racket length (every HST character's racket is 0.944 m, butt to tip), and is written in the model's `Racket`-joint
space: metres, vertices baked (the loader reads positions as they are, node transforms ignored).
"""
import argparse
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

HST_LENGTH = 0.944  # butt to tip of every HST racket (PCnnC00 racket_nn.mdl, along its grip axis +Y)


def make(part, model, out_path, node=None, length=HST_LENGTH):
    g, b = glb.read(part)
    W, _ = worlds(g)
    names = [norm(n.get("name", "")) for n in g["nodes"]]
    if node is None:
        node = next(n for n in names if n.startswith("Bip01RHand9racket") and n.endswith("_game"))
    ri, hi = names.index(node), names.index("Bip01RHand")
    mg, mb = glb.read(model)
    MB, _ = binds(mg, mb)
    s = mg.get("extras", {}).get("scale", 1.0)
    # the source hand sits where the model's does (rerig keeps joint positions, times s)
    ph = s * (G @ W[hi])[:3, 3]
    assert np.allclose(ph, MB["Bip01RHand"][:3, 3], atol=1e-4), (ph, MB["Bip01RHand"][:3, 3])
    Wr = G @ W[ri]
    A, T = s * Wr[:3, :3], s * Wr[:3, 3]  # racket mesh space -> game space at bind
    R = Wr[:3, :3] / np.linalg.norm(Wr[:3, :3], axis=0)
    prims = []
    for p in g["meshes"][g["nodes"][ri]["mesh"]]["primitives"]:
        v = read(g, b, p["attributes"]["POSITION"]) @ A.T + T
        nrm = read(g, b, p["attributes"]["NORMAL"]) @ R.T if "NORMAL" in p["attributes"] else None
        prims.append((p, v, nrm))
    # the handle axis: the mesh's local +Z (butt at its min, tip at its max)
    allv = np.vstack([v for _, v, _ in prims])
    ax = R[:, 2]
    t = allv @ ax
    butt, tip = t.min(), t.max()
    c = T + ax * (np.clip((ph - T) @ ax, butt, tip) - T @ ax)  # the hand's point on the handle
    k = length / (tip - butt)
    Mr = np.linalg.inv(MB["Racket"])
    o = glb.Builder()
    o.g["asset"]["generator"] = "HST-MODS racket"
    imgs = {}
    for key in ("samplers",):
        if key in g:
            o.g[key] = json.loads(json.dumps(g[key]))
    mats = {}

    def material(i):
        if i not in mats:
            m = json.loads(json.dumps(g["materials"][i]))
            ti = m.get("pbrMetallicRoughness", {}).get("baseColorTexture", {}).get("index")
            if ti is not None:
                tx = g["textures"][ti]
                si = tx["source"]
                if si not in imgs:
                    im = g["images"][si]
                    v = g["bufferViews"][im["bufferView"]]
                    imgs[si] = o.add("images", {"bufferView": o.view(bytes(b[v.get("byteOffset", 0): v.get("byteOffset", 0) + v["byteLength"]])),
                                                "mimeType": im.get("mimeType", "image/png"), "name": im.get("name", "")})
                m["pbrMetallicRoughness"]["baseColorTexture"]["index"] = o.add("textures", dict(tx, source=imgs[si]))
            mats[i] = o.add("materials", m)
        return mats[i]

    out_prims = []
    for p, v, nrm in prims:
        v = c + (v - c) * k
        at = {"POSITION": o.accessor(((v @ Mr[:3, :3].T) + Mr[:3, 3]).astype(np.float32), glb.FLOAT, "VEC3", minmax=True)}
        if nrm is not None:
            at["NORMAL"] = o.accessor((nrm @ Mr[:3, :3].T).astype(np.float32), glb.FLOAT, "VEC3")
        for key in p["attributes"]:
            if key.startswith("TEXCOORD") or key.startswith("COLOR"):
                at[key] = o.accessor(read(g, b, p["attributes"][key]).astype(np.float32), glb.FLOAT, g["accessors"][p["attributes"][key]]["type"])
        q = {"attributes": at, "indices": o.accessor(read(g, b, p["indices"]).astype(np.uint32), glb.UINT, "SCALAR")}
        if "material" in p:
            q["material"] = material(p["material"])
        out_prims.append(q)
    mi = o.add("meshes", {"name": "racket", "primitives": out_prims})
    o.g["scenes"][0]["nodes"].append(o.node(name="racket", mesh=mi))
    o.g["extras"] = {"hst_racket": 1, "source": f"{os.path.basename(part)}:{node}", "length": length, "resize": float(k), "body_scale": s}
    o.write(out_path)
    return k


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("part")
    ap.add_argument("model")
    ap.add_argument("out")
    ap.add_argument("--node")
    ap.add_argument("--length", type=float, default=HST_LENGTH)
    a = ap.parse_args()
    print(a.out, "resize", make(a.part, a.model, a.out, a.node, a.length))


if __name__ == "__main__":
    main()
