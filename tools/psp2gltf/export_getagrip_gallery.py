"""Get a Grip's court galleries -> the court mods' people (standard/HST-COURT-UMPIRE-STANDARD.md §2b; open-tennis
task M8f7). Run after export_getagrip_courts.py (it adds to out/mods/gag_cNN_<stem>/):

    python3 tools/psp2gltf/export_getagrip_gallery.py [01 04 ...]

writes npcs.json, npcs/*.glb and npcs/*.wav and a `npcs` line in mod.json.

What a court's gallery is made of (notes/getagrip.md "Courts"):
  courtNN_gallery    gallery/gall00..06.psp.i3r: one 1 x 1.95 m card each (gall00 an empty model: gall01's card),
                     drawn with gallNN_act0..7 (gall06 only act0); four texture animations (.tat) swap them:
                     front = act0, back = act1 (seen from behind), down = act2 (head down), clap = act3..7 over
                     0.2 s. setting/cNN_galleryarea.dat: u32 count, then per area u32 id, f32 centre x, y, z (metres,
                     Y up), f32 size x, y (height), z; setting/cNN_gallery.csv: per area the people with no / normal /
                     many gallery.
  c09, c16           no gallery xb: one whole-stand crowd model gallery/gall00/cNN_gall00.psp.i3r in courtNN_obj_0
                     (placed by haichi track cNN_gall00__01), same four .tats over gall00_act0..7.
  900_sound          galsg_GL_[mw]NN_[ab].sgd: the crowd voices, cues group_glee_0..2, group_sad_0..1, group_win,
                     group_lose (+ single spectators' praise lines, not used); co_seNN.sgd clap_1 (one clap).

Who stands where in which pose, and when the program swaps the textures or plays which voice, is in the encrypted
program: the people are spread at random (seeded by the court) over each area with the csv's "normal" count, and
the cues follow the standard (cheer / clap = the clap animation, groan = down).
"""
import hashlib
import json
import math
import os
import random
import struct
import sys
from glob import glob

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build  # noqa: E402
import glb  # noqa: E402
import i3d  # noqa: E402
import i3m  # noqa: E402
import export_getagrip_courts as courts  # noqa: E402

ROOT = courts.ROOT
AUDIO = courts.AUDIO

FRONT, BACK, DOWN = 0, 1, 2
CLAP = [(0.0, 3), (0.06667, 4), (0.1, 5), (0.16667, 6), (0.2, 7)]
CLAP_END = 0.26667  # act7 held one more 1/15 s before the loop starts over
STILL = 1.0  # length given to the one-frame clips so they loop like the rest
SPACING = 0.7  # metres kept between two people of an area
VOICES = ["m00_a", "w00_a", "m03_a", "w02_a"]  # four voice sets mixed: group cheers sound like a crowd


def gallery_dir(n):
    d = glob(os.path.join(courts.COURT, f"court{n:02d}_gallery.xb/data/court/c{n:02d}_*"))
    return d[0] if d else None


def areas(d, n):
    raw = open(os.path.join(d, "setting", f"c{n:02d}_galleryarea.dat"), "rb").read()
    k = struct.unpack_from("<I", raw)[0]
    box = {}
    for i in range(k):
        aid, *f = struct.unpack_from("<I6f", raw, 4 + 28 * i)
        box[aid] = f
    _, rows = courts.sjis_csv(os.path.join(d, "setting", f"c{n:02d}_gallery.csv"))
    return [(box[int(r[0])], int(r[2])) for r in rows if int(r[0]) in box]


class Glb:
    def __init__(self):
        self.b = glb.Builder()
        self.top = self.b.node(name="game_space", rotation=[0.0, 0.0, 1.0, 0.0], children=[])
        self.b.g["scenes"][0]["nodes"].append(self.top)

    def child(self, parent, **kw):
        i = self.b.node(**kw)
        self.b.g["nodes"][parent].setdefault("children", []).append(i)
        return i

    def clips(self, frames, clips):
        """One STEP scale channel per frame node per clip: the clip's frame at 1, the others at 0."""
        for name, keys, end in clips:
            chans, samps = [], []
            ts = [t for t, _ in keys] + [end]
            tin = self.b.accessor(np.array(ts, np.float32), glb.FLOAT, "SCALAR", minmax=True)
            for k, node in frames.items():
                on = [1.0 if f == k else 0.0 for _, f in keys]
                vals = np.array([[v] * 3 for v in on + on[-1:]], np.float32)
                samps.append({"input": tin, "output": self.b.accessor(vals, glb.FLOAT, "VEC3"),
                              "interpolation": "STEP"})
                chans.append({"sampler": len(samps) - 1, "target": {"node": node, "path": "scale"}})
            self.b.add("animations", {"name": name, "channels": chans, "samplers": samps})


def card_clips(acts):
    """The four .tats as the standard's cues; a clip whose frame the card lacks is left out (plays idle)."""
    out = [("idle", [(0.0, FRONT)], STILL)]
    if BACK in acts:
        out += [(c + "_back", [(0.0, BACK)], STILL) for c in ("idle", "groan", "clap", "cheer")]
    if DOWN in acts:
        out.append(("groan", [(0.0, DOWN)], STILL))
    if all(f in acts for _, f in CLAP):
        out += [("clap", CLAP, CLAP_END), ("cheer", CLAP, CLAP_END)]
    return out


def card(d, k, quad):
    """gallKK: the card quad (game space, metres, facing +Z) once per act texture, as frame_<act> nodes."""
    imgs = sorted(glob(os.path.join(d, "gallery/sourceimages", f"gall{k:02d}_act*.gim")))
    acts = sorted(int(os.path.basename(p)[:-4].rsplit("act", 1)[1]) for p in imgs)
    g = Glb()
    tc = build.TextureCache(g.b, [os.path.join(d, "gallery/sourceimages")], None)
    P, U = quad
    # Get a Grip's card faces +Z with u growing along +x; turned to face game +Z (Y down): (-x, -y, 0) / 100
    pos = np.array([[-x / 100, -y / 100, 0.0] for x, y, _ in P], np.float32)
    nrm = np.tile(np.array([0, -1, 0], np.float32), (len(P), 1))  # lit like the ground under it
    b = g.b
    attrs = {"POSITION": b.accessor(pos, glb.FLOAT, "VEC3", 34962, minmax=True),
             "NORMAL": b.accessor(nrm, glb.FLOAT, "VEC3", 34962),
             "TEXCOORD_0": b.accessor(np.array(U, np.float32), glb.FLOAT, "VEC2", 34962)}
    idx = b.accessor(np.array([0, 1, 2, 3, 4, 5], np.uint32), glb.UINT, "SCALAR", 34963)
    person = g.child(g.top, name=f"gall{k:02d}", children=[])
    frames = {}
    for a in acts:
        mat = tc.material(f"gall{k:02d}_act{a}")
        m = b.add("meshes", {"name": f"gall{k:02d}_act{a}", "primitives": [{"attributes": attrs, "indices": idx,
                                                                              "material": mat, "mode": 4}]})
        frames[a] = g.child(person, name=f"frame_{a}", mesh=m, scale=[1.0] * 3 if a == FRONT else [0.0] * 3)
    g.clips(frames, card_clips(acts))
    return g, acts


def quad_of(path):
    m = i3d.load(path)
    for p in m.parts:
        for pr in p.prims:
            if len(pr.pos) == 6:
                return pr.pos.tolist(), pr.uv.tolist()
    return None


def spread(boxes, models, n):
    """The csv's people over each area: random spots (seeded by the court) at least SPACING apart, facing the
    court's centre; models dealt round so neighbours differ."""
    rng = random.Random(1000 + n)
    deck, people = [], []
    for (cx, cy, cz, sx, _sy, sz), count in boxes:
        spots = []
        for _ in range(count):
            for _try in range(200):
                x = cx + (rng.random() - 0.5) * sx
                z = cz + (rng.random() - 0.5) * sz
                if all(math.hypot(x - a, z - b) >= SPACING for a, b in spots):
                    break
            spots.append((x, z))
        for x, z in spots:
            if not deck:
                deck = models[:]
                rng.shuffle(deck)
            gx, gz = x, -z  # Get a Grip (x, y, z) Y up -> game (x, -y, -z)
            d = math.hypot(gx, gz) or 1.0
            people.append({"model": deck.pop(), "pos": [round(gx, 3), round(-cy, 3), round(gz, 3)],
                           "facing": [round(-gx / d, 4), round(-gz / d, 4)], "role": "gallery"})
    return people


def stands(n, out):
    """c09 / c16: the whole-stand crowd, once per act texture (the four .tats swap the one texture)."""
    dirs = courts.court_dirs(n)
    path = glob(os.path.join(courts.COURT, f"court{n:02d}_obj_0.xb/data/court/c{n:02d}_*/gallery/gall00/"
                                           f"c{n:02d}_gall00.psp.i3r"))[0]
    src = os.path.join(os.path.dirname(os.path.dirname(path)), "sourceimages")
    sc = courts.Scene([src])
    track = next((t for t in courts.haichi(dirs) if t.name.startswith(f"c{n:02d}_gall00__")), None)
    pos, rot, scl = i3m.evaluate(track, 0.0) if track else ((0, 0, 0), (0, 0, 0, 1), (1, 1, 1))
    place = sc.child(sc.top, name="gall00", **courts.placement(pos, rot, scl))
    find = sc.tc.find
    frames = {}
    for a in range(8):
        sc.meshes, sc.mats, sc.tc.mats = {}, {}, {}
        sc.tc.find = lambda name, a=a: find(name.replace("_act0", f"_act{a}"))
        f = sc.child(place, name=f"frame_{a}", scale=[1.0] * 3 if a == FRONT else [0.0] * 3)
        sc.add(path, f)
        frames[a] = f
    g = Glb.__new__(Glb)
    g.b = sc.b
    g.clips(frames, [c for c in card_clips(set(range(8))) if not c[0].endswith("_back")])
    sc.write(os.path.join(out, "stands.glb"))
    courts.Model.cache.clear()


def wav_md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def sounds(n, out):
    """cheer: the group_glee lines, groan: group_sad, win / lose: group_win / group_lose, across VOICES (repeats
    dropped); clap: the court's clap_1."""
    cues = {"cheer": ["group_glee_0", "group_glee_1", "group_glee_2"], "groan": ["group_sad_0", "group_sad_1"],
            "win": ["group_win"], "lose": ["group_lose"]}
    found = {c: [] for c in cues}
    seen = set()
    for v in VOICES:
        who, part = v.split("_")
        bank = glob(os.path.join(AUDIO, f"005_galsg_{who}_0{'ab'.index(part)}.xb/data/sound/Voice/nml/galsg_GL_{v}.sgd"))
        if not bank:
            continue
        names = dict(reversed(l.split("\t")[:2]) for l in open(os.path.join(bank[0], "names.txt")).read().split("\n")
                     if l.count("\t") >= 1 and l[:3].isdigit())
        for cue, keys in cues.items():
            for k in keys:
                if k in names:
                    p = os.path.join(bank[0], names[k] + ".wav")
                    if os.path.exists(p) and wav_md5(p) not in seen:
                        seen.add(wav_md5(p))
                        found[cue].append(p)
    se = glob(os.path.join(AUDIO, f"020_court{n:02d}.xb/data/sound/SE/co_se{n:02d}.sgd"))
    if se:
        for l in open(os.path.join(se[0], "names.txt")).read().split("\n"):
            f = l.split("\t")
            if len(f) >= 2 and f[1] == "clap_1" and f[0].isdigit():
                found["clap"] = [os.path.join(se[0], f[0] + ".wav")]
    man = {}
    for cue, ps in found.items():
        for i, p in enumerate(ps):
            rel = f"npcs/{cue}_{i}.wav"
            with open(p, "rb") as s, open(os.path.join(out, os.path.basename(rel)), "wb") as d:
                d.write(s.read())
            man.setdefault(cue, []).append(rel)
    return man


def export(n):
    mod = glob(os.path.join(ROOT, f"out/mods/gag_c{n:02d}_*"))
    if not mod:
        print(f"c{n:02d}: no court mod (run export_getagrip_courts.py first)")
        return
    mod = mod[0]
    out = os.path.join(mod, "npcs")
    os.makedirs(out, exist_ok=True)
    d = gallery_dir(n)
    if d:
        quad = quad_of(os.path.join(d, "gallery/gall01.psp.i3r"))
        models, kinds = {}, []
        for k in range(7):
            if not glob(os.path.join(d, "gallery/sourceimages", f"gall{k:02d}_act0.gim")):
                continue
            q = quad_of(os.path.join(d, f"gallery/gall{k:02d}.psp.i3r")) or quad
            g, acts = card(d, k, q)
            g.b.write(os.path.join(out, f"gall{k:02d}.glb"))
            models[f"gall{k:02d}"] = {"glb": f"npcs/gall{k:02d}.glb", "billboard": True}
            kinds.append(f"gall{k:02d}")
        people = spread(areas(d, n), kinds, n)
        what = f"{len(people)} gallery cards ({len(kinds)} looks) over the court's gallery areas"
    else:
        stands(n, out)
        models = {"stands": "npcs/stands.glb"}
        people = [{"model": "stands", "pos": [0, 0, 0], "facing": [0, 1], "role": "gallery"}]
        what = "the whole-stand crowd model"
    doc = {"models": models, "people": people, "sounds": sounds(n, out)}
    json.dump(doc, open(os.path.join(mod, "npcs.json"), "w"), indent=1)
    mp = os.path.join(mod, "mod.json")
    man = json.load(open(mp))
    man["npcs"] = what
    man["todo"] = [t for t in man.get("todo", []) if not t.startswith("npcs")] + [
        "npcs: who stands where, in which pose and when, and which crowd line plays, are the encrypted program's: "
        "people spread at random over the gallery areas; cues per the standard"]
    json.dump(man, open(mp, "w"), indent=1, ensure_ascii=False)
    print(f"{os.path.basename(mod):24s} {what}; sounds " + ", ".join(f"{k} {len(v)}" for k, v in doc["sounds"].items()))


def main():
    for n in [int(a) for a in sys.argv[1:]] or courts.COURTS:
        export(n)


if __name__ == "__main__":
    main()
