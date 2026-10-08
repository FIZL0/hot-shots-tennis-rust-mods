#!/usr/bin/env python3
"""Get a Grip face expressions: decode TAT tracks, label face textures, write
  out/anims/getagrip/face_tracks.json   per character: motion -> {track: [[time, faceN], ...]}
  out/models/getagrip/faces.json        per character: neutral + HST PS2 expression channels -> PNG
  out/textures/getagrip/_face_sheets/   labelled contact sheets (mirrored half-face previews)
Labels are hand-assigned from the sheets + TAT usage (LABELS below). See notes/getagrip.md.
Run: python3 tools/psp2gltf/export_getagrip_faces.py
"""
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import tat  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
XB = os.path.join(ROOT, "out/files/getagrip/PSP_GAME/USRDIR/xbdata")
PC = os.path.join(XB, "game/400_pc/face")
TEX = "out/textures/getagrip/face"
STEMS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen"]
GENERIC = "100_f_face"   # 099 (shared) TATs name the generic NPC face; engine substitutes the PC's own

# faceN index -> label, per PC (from the contact sheets; 0..5 also fixed by the shared 099 motions:
# 0 neutral, 1 blink, 2 smile (rally win), 3 effort shout at ball impact, 4 dejected (miss / tired *_01),
# 5 high-ball / smash look-up).  Free-text labels; channel picks below.
LABELS = {
    0: ["neutral", "blink", "joy_open", "shout_determined", "sad_eyes_closed", "laugh", "frustrated_eyes_closed",
        "strain_xx", "angry_glare", "surprised_small_o", "shocked", "smirk"],
    1: ["neutral", "blink", "grin", "serious_frown", "worried", "surprised_shout", "angry_shout_xx", "strain_xx",
        "shocked", "smile_open"],
    2: ["neutral_scowl", "blink", "slight_smile", "angry_shout", "annoyed", "surprised_shout", "strain_xx",
        "smirk", "smile_eyes_closed", "small_open"],
    3: ["neutral", "blink", "joy_open", "pout", "sad_eyes_closed", "laugh", "surprised_o", "shout_xx",
        "shocked", "smile"],
    4: ["neutral", "blink", "grin", "shout", "sad_eyes_closed", "laugh", "wail", "smile_open", "shocked", "smirk"],
    5: ["neutral", "blink", "joy_open", "angry_shout", "strain_eyes_closed", "laugh", "content_eyes_closed",
        "sulk", "shocked", "small_open"],
    6: ["neutral", "blink", "slight_smile", "shout", "pained_eyes_closed", "calm_eyes_closed", "angry_shout_xx",
        "neutral_b", "neutral_c", "neutral_d", "shocked", "slight_open"],
    7: ["neutral", "blink", "joy_open", "pout", "worried", "content_eyes_closed", "smile", "laugh",
        "tongue_out", "crying_xx", "joy_open_b", "shocked", "grin"],
    8: ["neutral_eyes_closed", "blink", "laugh_eyes_closed", "surprised_o", "pain_xx", "smile_eyes_open",
        "smile_eyes_open_b", "dismayed", "laugh_xx", "glum", "shocked", "grin"],
    9: ["neutral", "blink", "grin", "frown", "angry_shout", "small_open", "content_eyes_closed",
        "shout_eyes_closed", "shout_xx", "calm_eyes_closed", "surprised_o", "smile"],
    10: ["neutral", "blink", "grin", "angry_grit", "strain_grit_eyes_closed", "smirk", "smug_eyes_closed",
         "neutral_b", "frown", "dismayed", "shocked", "slight_open"],
    11: ["neutral", "blink", "smile", "pout", "sad_eyes_closed", "flustered_happy", "content_eyes_closed",
         "surprised_small_o", "worried_open", "neutral_b", "crying_shock", "small_pout", "shocked", "smile_b"],
    12: ["neutral", "blink", "laugh", "angry_grit", "dismayed", "grin", "pain_xx", "shout", "smile"],
    13: ["neutral", "blink", "smile", "surprised_o_annoyed", "worried", "sad_eyes_closed", "annoyed_eyes_closed",
          "small_open", "small_open_eyes_closed", "surprised", "smile_b"],
    14: ["mask"],
}

# HST PS2 channel -> (faceN, approx). Whole-face textures, so *_eye and *_mouth of one emotion share a texture
# unless a better partial match exists. doki = flustered/nervous/surprised.
CH = ["blink_eye", "joy_eye", "joy_mouth", "anger_eye", "anger_mouth", "sorrow_eye", "sorrow_mouth",
      "doki_eye", "doki_mouth"]
PICK = {  # joy, anger, sorrow, doki  (each (N, approx)); blink always 1
    0: ((5, 0), (8, 0), (4, 0), (10, 0)),
    1: ((2, 0), (6, 0), (4, 0), (8, 0)),
    2: ((8, 1), (3, 0), (4, 1), (5, 0)),
    3: ((5, 0), (3, 1), (4, 0), (8, 0)),
    4: ((5, 0), (3, 1), (4, 0), (8, 0)),
    5: ((5, 0), (3, 0), (7, 1), (8, 0)),
    6: ((2, 1), (6, 0), (4, 0), (10, 0)),
    7: ((7, 0), (3, 1), (4, 0), (11, 0)),
    8: ((2, 0), (4, 1), (9, 0), (10, 0)),
    9: ((2, 0), (4, 0), (9, 1), (10, 0)),
    10: ((2, 0), (3, 0), (9, 0), (10, 0)),
    11: ((2, 0), (3, 1), (4, 0), (12, 0)),
    12: ((5, 0), (3, 0), (4, 0), (7, 1)),
    13: ((2, 0), (6, 1), (4, 0), (9, 0)),
}


def roster():
    p = os.path.join(ROOT, "out/models/getagrip/characters.json")
    seen = {}
    for c in json.load(open(p)):
        seen.setdefault(c["pc"], c)
    return [seen[k] for k in sorted(seen)]


def faceno(stem):
    return int(re.search(r"face(\d+)$", stem).group(1))


def resolve(tracks, stem):
    """{track material: [[t, N], ...]}; generic 100_f_faceN -> <stem>_faceN."""
    out = {}
    for t in tracks:
        names = [s.replace(GENERIC, f"{stem}_face") for s in t["textures"]]
        out[t["material"]] = [[k[0], faceno(names[k[1]])] for k in t["keys"]]
    return out


def png(stem, n):
    p = f"{TEX}/{stem}_face{n}.png"
    return p if os.path.exists(os.path.join(ROOT, p)) else None


def main():
    chars = roster()
    tracks, faces = {}, {}
    usage = {}
    for c in chars:
        i, stem = c["pc"], STEMS[c["pc"]]
        slug = f"pc{i:02d}_{c['name']}"
        base = os.path.join(PC, f"face{i:03d}_anim.xb/data/chara/motion")
        files = sorted(glob.glob(f"{base}/099/*.tat")) + sorted(glob.glob(f"{base}/{i:02d}/*.tat")) + sorted(
            glob.glob(os.path.join(XB, f"game/700_prize/020_prize_pc{i:02d}.xb/data/chara/prize_motion/*/*.tat")))
        mot = {}
        u = collections.defaultdict(set)
        for p in files:
            name = os.path.basename(p)[:-4]
            r = resolve(tat.load(p), stem)
            src = "common" if "/099/" in p else ("prize" if "700_prize" in p else "own")
            mot[name] = {"source": src, **r}
            for keys in r.values():
                for _, n in keys:
                    u[n].add(name)
        tracks[slug] = mot
        usage[slug] = u

        n_tex = len(glob.glob(os.path.join(ROOT, TEX, f"{stem}_face*.png")))
        lab = LABELS[i]
        assert len(lab) == n_tex, (slug, len(lab), n_tex)
        entry = {"face_material": f"{stem}_face0", "slot": "face", "mirrored_halves": i != 14,
                 "half_tracks": ["face", "faceL"] if i != 14 else ["face"],
                 "neutral": png(stem, 0), "channels": {}, "approx": {}, "labels": {}}
        if i in PICK:
            joy, ang, sor, dok = PICK[i]
            pick = {"blink_eye": (1, 0), "joy_eye": joy, "joy_mouth": joy, "anger_eye": ang, "anger_mouth": ang,
                    "sorrow_eye": sor, "sorrow_mouth": sor, "doki_eye": dok, "doki_mouth": dok}
            for ch in CH:
                n, ap = pick[ch]
                entry["channels"][ch] = png(stem, n)
                if ap:
                    entry["approx"][ch] = True
        else:  # Helghast mask: one texture, no expressions
            entry["channels"] = {ch: None for ch in CH}
        used = set(entry["channels"].values()) | {entry["neutral"]}
        for n, l in enumerate(lab):
            entry["labels"][f"face{n}"] = l
        entry["extras"] = {lab[n]: png(stem, n) for n in range(len(lab)) if png(stem, n) not in used}
        faces[slug] = entry

    os.makedirs(os.path.join(ROOT, "out/anims/getagrip"), exist_ok=True)
    meta = {"_doc": "per character: motion -> {source: common|own|prize, <material track>: [[time_s, faceN], ...]}."
            " Step keys: faceN shown from time until the next key. Tracks: 'face' = right half (x<0), 'faceL' = "
            "left half; a motion with only 'face' drives both halves. faceN -> "
            "out/textures/getagrip/face/<stem>_faceN.png (see faces.json). Motion names match the i3m motions"
            " (common_motions.glb / pcNN_prize.glb; 'own' = re_*/A_re_* reactions, lobby co* = comments)."}
    json.dump({**meta, **tracks}, open(os.path.join(ROOT, "out/anims/getagrip/face_tracks.json"), "w"), indent=1)
    json.dump({"_doc": "HST PS2 expression channel -> Get a Grip face texture. Textures are whole half-face "
               "(eyes+brows+mouth) mirrored onto both halves, so *_eye and *_mouth of an emotion are the same "
               "texture: drive the single face material with the dominant channel. approx[ch]=true: no exact "
               "expression, closest picked.", **faces},
              open(os.path.join(ROOT, "out/models/getagrip/faces.json"), "w"), indent=1)
    sheets(faces)
    for slug, u in usage.items():
        print(slug, {n: len(v) for n, v in sorted(u.items())})
    print("chars", len(faces), "motions", sum(len(v) for v in tracks.values()))


def sheets(faces, S=3):
    from PIL import Image, ImageDraw, ImageOps
    out = os.path.join(ROOT, "out/textures/getagrip/_face_sheets")
    os.makedirs(out, exist_ok=True)
    for slug, e in faces.items():
        labs = e["labels"]
        inv = {v: k for k, v in e["channels"].items() if v}
        rev = collections.defaultdict(list)
        for ch, p in e["channels"].items():
            if p:
                rev[p].append(ch + ("~" if e["approx"].get(ch) else ""))
        W, H = 128 * S + 8, 128 * S + 46
        n = len(labs)
        cols = min(n, 7)
        img = Image.new("RGB", (W * cols, H * ((n + cols - 1) // cols)), (70, 70, 70))
        dr = ImageDraw.Draw(img)
        stem = e["face_material"][:-1]
        for k in range(n):
            t = Image.open(os.path.join(ROOT, TEX, f"{stem}{k}.png")).convert("RGBA")
            t = Image.alpha_composite(Image.new("RGBA", t.size, (255, 255, 255, 255)), t)
            if e["mirrored_halves"]:
                full = Image.new("RGBA", (t.width * 2, t.height))
                full.paste(ImageOps.mirror(t), (0, 0))
                full.paste(t, (t.width, 0))
            else:
                full = t
            full = full.resize((128 * S, 128 * S), Image.NEAREST)
            x, y = (k % cols) * W, (k // cols) * H
            img.paste(full.convert("RGB"), (x + 4, y + 42))
            p = f"{TEX}/{stem}{k}.png"
            dr.text((x + 6, y + 3), f"face{k}: {labs[f'face{k}']}", fill=(255, 255, 0))
            dr.text((x + 6, y + 16), ("NEUTRAL " if k == 0 else "") + " ".join(rev.get(p, [])), fill=(120, 255, 120))
        img.save(os.path.join(out, f"{slug}.png"))
    _ = inv


if __name__ == "__main__":
    main()
