"""HST's five chair umpires as playable mods (open-tennis task M1g) -> out/mods/hst_umpire_NN_<name>/.

python3 tools/rerig/hst_umpires.py [open-tennis dir]      (default ../open-tennis)

Needs from the open-tennis checkout: the disc image `Hot Shots Tennis (USA).iso`, the unpacked `context/xb`, and
its release tools `hst-gltf` (`umpires`) and `bankwav` (in $CARGO_TARGET_DIR or target/release). Game data: the
outputs stay in out/ (git-ignored).

1. `hst-gltf umpires` -> out/models/hst/umpires/uNN.glb (the umpire's MDL, materials and its chair clips).
2. stand(): the umpires are bound sitting (thighs forward, shins down); each leg bone is swung onto HST's bind
   direction (standard/hst_skeleton.json) about its joint, skin re-bound to match, feet put on y = 0. No scaling:
   the umpire's own size.
3. rerig() to the 54-joint standard (it adds Spine1/2, finger segments and Racket the umpire rig lacks), check().
4. mod.json: donor/params/ai_row and why (UMPIRES below), face "none" (no morph targets), voices: the umpire's own
   calls in the reaction programs that fit (VOICE below), every other program the donor's disc takes (HST's mod
   loader falls back per program, standard §5).
"""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools/psp2gltf"))
sys.path.insert(0, HERE)
import glb  # noqa: E402
import rerig  # noqa: E402
from check import check  # noqa: E402
from package import link  # noqa: E402
import gag_stats  # noqa: E402

# n -> (slug, name as the game's umpire select names it, sex, donor, why). Sex from the model's look.
UMPIRES = {
    0: ("chika", "Chika", "f", None, ""),
    1: ("suzuki", "Suzuki", "m", 13, "the same Suzuki as HST's playable pc13 (same name, old man in both)"),
    2: ("lily", "Lily", "f", None, ""),
    3: ("robottennis", "RobotTennis", None, None, "a robot: no sex, nearest Bip01 height over all of HST's 14"),
    4: ("anna", "Anna", "f", None, ""),
}
# player voice program <- the umpire bank's (program, key) of the same meaning (bank: SND/UMP/UVnnA.XB0;
# program 1 = calls by judge call - 1, program 2 = announcements). Programs 0-4 (shouts) and 6 (partner calls)
# have no umpire equivalent: the donor's.
VOICE = {7: [(2, 1)],            # point won  <- "Game"
         8: [(1, 0), (1, 4)],    # point lost <- "Out", "Out" (after the net)
         9: [(2, 2), (2, 4)],    # set won    <- "Set", "Match"
         10: [(1, 2)]}           # set lost   <- "Double fault"
VOICE_WHY = {7: "umpire 'Game' (bank prog 2 key 1)", 8: "umpire 'Out' (prog 1 keys 0, 4)",
             9: "umpire 'Set', 'Match' (prog 2 keys 2, 4)", 10: "umpire 'Double fault' (prog 1 key 2)",
             "other": "programs 0-4, 6: the donor's disc takes (no umpire call means a shout or a partner call)"}


def stand(src, dst):
    """Swing the seated legs straight (HST bind directions), re-bind the skin, feet on y = 0."""
    J, _ = rerig.load_standard()
    g, b = glb.read(src)
    b = bytearray(b)
    nodes = g["nodes"]
    W, parent = rerig.worlds(g)
    SB, K = rerig.skin_binds(g, bytes(b))
    G = rerig.G
    assert max(np.abs(G @ W[j] - SB[j]).max() for j in SB) < 1e-4, "rest pose != bind pose"
    by = {rerig.norm(nodes[j]["name"]): j for j in SB}

    def sub(i):
        yield i
        for c in nodes[i].get("children", []):
            yield from sub(c)

    D = {j: np.eye(4) for j in SB}
    for side in "LR":
        chain = [f"Bip01{side}{x}" for x in ("Thigh", "Calf", "Foot")]  # the foot: sole levelled below
        for a, c in zip(chain, chain[1:]):
            pa = (D[by[a]] @ SB[by[a]])[:3, 3]
            pc = (D[by[c]] @ SB[by[c]])[:3, 3]
            T = np.eye(4)
            T[:3, :3] = rerig.swing(pc - pa, J[c][1][:3, 3] - J[a][1][:3, 3])
            T[:3, 3] = pa - T[:3, :3] @ pa
            for k in sub(by[a]):
                if k in D:
                    D[k] = T @ D[k]
    skin = g["skins"][0]
    sj = skin["joints"]
    mesh_nodes = [n for n in nodes if "mesh" in n and n.get("skin") == 0]
    Ks = K[0]
    A = G @ Ks

    def put(i, arr):
        a = g["accessors"][i]
        v = g["bufferViews"][a["bufferView"]]
        assert not v.get("byteStride") and not a.get("normalized")
        off = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        data = np.ascontiguousarray(arr, glb._DT[a["componentType"]]).tobytes()
        b[off: off + len(data)] = data
        if "min" in a:
            a["min"], a["max"] = [float(x) for x in arr.min(0)], [float(x) for x in arr.max(0)]

    # the chair model skins its legs rigidly to the pelvis (they never move): give the pelvis' vertices to the
    # nearest two bones of pelvis->spine and each leg chain (softmin over distance to the bone segments)
    P = lambda j: SB[j][:3, 3]
    segs = [(by["Bip01Pelvis"], by["Bip01Spine"])]
    for side in "LR":
        chain = [by[f"Bip01{side}{x}"] for x in ("Thigh", "Calf", "Foot", "Toe0")]
        chain.append(next(c for c in nodes[chain[-1]]["children"] if c in SB))  # the toe's end marker
        segs += list(zip(chain, chain[1:]))
    sa, sb_ = np.stack([P(a) for a, _ in segs]), np.stack([P(c) for _, c in segs])
    pelvis = sj.index(by["Bip01Pelvis"])

    def legs(js, ws, vg):
        own = (ws[:, 0] > 0.999) & (js[:, 0] == pelvis)
        d = vg[own, None, :] - sa[None]
        ab = sb_ - sa
        t = np.clip(np.einsum("vsi,si->vs", d, ab) / (ab * ab).sum(1), 0, 1)
        dist = np.linalg.norm(d - t[..., None] * ab[None], axis=2)
        near = np.argsort(dist, 1)[:, :2]
        dn = np.take_along_axis(dist, near, 1)
        w = np.exp(-(dn - dn[:, :1]) / 0.02)
        w /= w.sum(1, keepdims=True)
        js[own] = 0
        ws[own] = 0
        js[own, :2] = np.array([sj.index(segs[k][0]) for k in range(len(segs))])[near]
        ws[own, :2] = w

    data = []
    for m in mesh_nodes:
        for pr in g["meshes"][m["mesh"]]["primitives"]:
            at = pr["attributes"]
            js = rerig.read(g, bytes(b), at["JOINTS_0"]).astype(int)
            ws = rerig.read(g, bytes(b), at["WEIGHTS_0"]).astype(np.float64)
            ws /= ws.sum(1, keepdims=True)
            v = rerig.read(g, bytes(b), at["POSITION"]).astype(np.float64)
            vg = (A[:3, :3] @ v.T).T + A[:3, 3]
            legs(js, ws, vg)
            put(at["JOINTS_0"], js)
            put(at["WEIGHTS_0"], ws)
            data.append((at, js, ws, vg))

    # sole flat: pitch each foot about the ankle until its lowest heel and toe points are level (skipped when the
    # skin has no points below the ankle joint: Anna's foot joints sit behind her shoes, which then keep the shin's)
    for side in "LR":
        foot = by[f"Bip01{side}Foot"]
        pa = (D[foot] @ SB[foot])[:3, 3]
        leg = np.array([k in set(sub(by[f"Bip01{side}Thigh"])) for k in sj])
        Dj = np.stack([D[j] for j in sj])
        pts = []
        for _, js, ws, vg in data:  # this leg's skin below the ankle, posed so far
            M = np.einsum("vk,vkij->vij", ws, Dj[js])
            p = np.einsum("vij,vj->vi", M[:, :3, :3], vg) + M[:, :3, 3]
            pts.append(p[((ws * leg[js]).sum(1) > 0.5) & (p[:, 1] > pa[1])])
        pts = np.concatenate(pts)
        if len(pts) < 8:
            continue
        lo, hi = np.quantile(pts[:, 2], [0.3, 0.7])
        heel, toe = pts[pts[:, 2] <= lo], pts[pts[:, 2] >= hi]
        u = toe[toe[:, 1].argmax()] - heel[heel[:, 1].argmax()]
        T = np.eye(4)
        T[:3, :3] = rerig.swing(np.array([0, u[1], u[2]]), np.array([0, 0, np.hypot(u[1], u[2])]))
        T[:3, 3] = pa - T[:3, :3] @ pa
        for k in sub(foot):
            if k in D:
                D[k] = T @ D[k]
    Dj = np.stack([D[j] for j in sj])
    prims = []
    for at, js, ws, vg in data:
        M = np.einsum("vk,vkij->vij", ws, Dj[js])  # per-vertex blended delta (game space)
        vg = np.einsum("vij,vj->vi", M[:, :3, :3], vg) + M[:, :3, 3]
        nn = None
        if "NORMAL" in at:
            n = (A[:3, :3] @ rerig.read(g, bytes(b), at["NORMAL"]).astype(np.float64).T).T
            n = np.einsum("vij,vj->vi", M[:, :3, :3], n)
            nn = (np.linalg.inv(A[:3, :3]) @ n.T).T
            nn /= np.linalg.norm(nn, axis=1, keepdims=True)
        prims.append((at, vg, nn))
    floor = max(vg[:, 1].max() for _, vg, _ in prims)  # game space is Y down: the lowest point
    F = np.eye(4)
    F[1, 3] = -floor
    Ai = np.linalg.inv(A)

    for at, vg, nn in prims:
        vg = vg + F[:3, 3]
        put(at["POSITION"], (Ai[:3, :3] @ vg.T).T + Ai[:3, 3])
        if nn is not None:
            put(at["NORMAL"], nn)
    for j in D:
        D[j] = F @ D[j]
    put(skin["inverseBindMatrices"], np.stack([(np.linalg.inv(D[j] @ SB[j]) @ G @ Ks).T.ravel() for j in sj]))
    Wn = {j: G @ D[j] @ G @ W[j] for j in D}
    for j in D:
        p = parent.get(j)
        loc = np.linalg.inv(Wn.get(p, W.get(p, np.eye(4))) if p is not None else np.eye(4)) @ Wn[j]
        n = nodes[j]
        n.pop("matrix", None)
        sc = np.linalg.norm(loc[:3, :3], axis=0)
        n["translation"] = [float(x) for x in loc[:3, 3]]
        n["rotation"] = [float(x) for x in rerig.mat_quat(loc[:3, :3] / sc)]
        n["scale"] = [float(x) for x in sc]
    g.pop("animations", None)  # the chair clips are for the seated bind
    out = glb.Builder()
    out.g, out.bin = g, b
    g.pop("buffers", None)
    out.write(dst)
    return -floor


def tool(hst, name):
    for d in (os.environ.get("CARGO_TARGET_DIR"), os.path.join(hst, "target")):
        if d and os.path.exists(os.path.join(d, "release", name)):
            return os.path.join(d, "release", name)
    sys.exit(f"{name}: build it in {hst} (cargo build --release -p hst-gltf -p hst-data)")


def main():
    hst = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "../open-tennis"))
    iso = os.path.join(hst, "Hot Shots Tennis (USA).iso")
    chars = json.load(open(os.path.join(ROOT, "standard/hst_skeleton.json")))["characters"]
    models = os.path.join(ROOT, "out/models/hst/umpires")
    os.makedirs(models, exist_ok=True)
    subprocess.run([tool(hst, "hst-gltf"), "umpires", os.path.join(hst, "context/xb"), models], check=True)
    for n, (slug, name, sex, donor_ix, why) in UMPIRES.items():
        stood = os.path.join(models, f"u{n:02d}_stand.glb")
        stand(os.path.join(models, f"u{n:02d}.glb"), stood)
        mod = os.path.join(ROOT, f"out/mods/hst_umpire_{n:02d}_{slug}")
        os.makedirs(os.path.join(mod, "model"), exist_ok=True)
        c00 = os.path.join(mod, "model/c00.glb")
        rerig.rerig(stood, c00)
        assert check(c00), f"u{n:02d}: check.py FAIL"
        g, b = glb.read(c00)
        h = -rerig.binds(g, b)[0]["Bip01"][1, 3]
        if donor_ix is None:
            pool = [c for c in chars if c["model_type"] in (0, 4, 5) and c["sex"] == sex] if sex else chars
            donor = min(pool, key=lambda c: abs(c["bip01_height"] - h))
            why = (f"nearest Bip01 height among HST's standard-body {'women' if sex == 'f' else 'men'}" if sex else why) + \
                f" ({h:.3f} m vs {donor['name']} {donor['bip01_height']} m)"
        else:
            donor = chars[donor_ix]
            why = f"{why} ({h:.3f} m vs {donor['name']} {donor['bip01_height']} m)"
        # the umpire's calls -> voice/<program>_<key>.wav
        bank = os.path.join(ROOT, f"out/voices/hst/umpire{n:02d}")
        subprocess.run([tool(hst, "bankwav"), iso, f"SND/UMP/UV{n:02d}A.XB0", f"data/sound/UMPIRE/gag_vc{n:02d}a.hd", bank],
                       check=True, stdout=subprocess.DEVNULL)
        counts = {}
        for p, takes in VOICE.items():
            for k, (bp, bk) in enumerate(takes):
                link(os.path.join(bank, f"{bp}_{bk}.wav"), os.path.join(mod, f"voice/{p}_{k}.wav"))
            counts[p] = len(takes)
        manifest = {"standard": 1, "id": f"hst_umpire_{n:02d}_{slug}", "name": name,
                    "source": f"Hot Shots Tennis (PS2) chair umpire u{n:02d} (\"Umpire {name}\")",
                    "costumes": ["model/c00.glb"], "donor": donor["index"], "donor_why": why,
                    "size_why": "the umpire's own size (no scaling); bound seated, legs swung straight to HST's bind directions, feet on y = 0 (tools/rerig/hst_umpires.py)",
                    "hand": "right", "hand_why": "no handedness in the umpire data (it never holds a racket); right as most of HST's cast",
                    "params": {"base": donor["index"], "override": {}},
                    "params_why": "umpires have no stats in the game: the donor's TParam row",
                    "ai_row": donor["index"], "ai_row_why": "no play style: the donor's AIParam row",
                    "face": "none", "voice": "voice/", "voice_counts": counts, "voice_why": VOICE_WHY,
                    "todo": ["motions are the donor's; the umpire's own chair clips (_h/_r/_l) are seated and not used"]}
        if gag_stats.find_tparam(ROOT):
            gag_stats.expert(manifest, gag_stats.find_tparam(ROOT), chars)
        json.dump(manifest, open(os.path.join(mod, "mod.json"), "w"), indent=1, ensure_ascii=False)
        print(f"{mod}: Bip01 {h:.3f} m, donor {donor['name']}")


if __name__ == "__main__":
    main()
