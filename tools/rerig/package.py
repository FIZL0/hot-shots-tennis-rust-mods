"""Package every rerigged character as a mod folder (standard/HST-CHARACTER-STANDARD.md §1, §6).

python3 tools/rerig/package.py      (after batch.py)  ->  out/mods/<game>_<slug>/

Files are hard links into out/ (game data: never commit). Filled in: costumes, donor (the HST character with the
nearest Bip01 height), face mode (+ face.json for Get a Grip), voices (Get a Grip mapped onto HST programs; other
games copied raw to voice/unsorted/ until their cues are identified), the source game's raw stats where known.
Left for a human or agent: params.override (per-game stat mapping, PLAN M8), handedness, voice cues outside Get a Grip.
"""
import glob
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools/psp2gltf"))
sys.path.insert(0, HERE)
import glb  # noqa: E402
from rerig import binds  # noqa: E402
import racket  # noqa: E402
import sizing  # noqa: E402

GAME_NAME = {"fore": "Hot Shots Golf Fore! (PS2)", "oob": "Hot Shots Golf: Out of Bounds (PS3)",
             "getagrip": "Hot Shots Tennis: Get a Grip (PSP)", "opentee": "Hot Shots Golf: Open Tee (PSP)",
             "opentee2": "Hot Shots Golf: Open Tee 2 (PSP)"}
# Get a Grip cue -> HST voice program (programs 7-10 follow reaction motions 0x2c-0x2f: re_gu, re_di, re_gu_set,
# re_di_set). approx: 1 and 2 (st_ji/st_nb meaning unknown).
GAG_VOICE = {0: ["smash"], 1: ["st_ji"], 2: ["st_nb"], 3: ["receive"], 4: ["swing"], 6: ["start", "call", "go", "chance"],
             7: ["point_get"], 8: ["point_lost"], 9: ["set_get"], 10: ["set_lost"]}


def link(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def gag_voices(n, dst):
    d = os.path.join(ROOT, f"out/voices/getagrip/pc{n:02d}")
    out = {}
    for prog, cues in GAG_VOICE.items():
        files = []
        for cue in cues:
            files += sorted(glob.glob(os.path.join(d, f"sgv_pc{n:02d}a_pc_voice_{cue}*.wav")))
        for k, f in enumerate(files[:5]):
            link(f, os.path.join(dst, f"voice/{prog}_{k}.wav"))
        out[prog] = len(files[:5])
    return out


def main():
    hst = json.load(open(os.path.join(ROOT, "standard/hst_skeleton.json")))["characters"]
    gag_faces = json.load(open(os.path.join(ROOT, "out/models/getagrip/faces.json")))
    gag_stats = {}
    csvp = glob.glob(os.path.join(ROOT, "out/files/getagrip/**/parameter/character.csv"), recursive=True)
    if csvp:
        rows = [r.split(",") for r in open(csvp[0], encoding="utf-8", errors="replace").read().splitlines() if r]
        head = rows[0]
        for r in rows[1:]:
            m = re.match(r"Pc_(\d+)_00", r[0])
            if m:
                gag_stats[int(m.group(1))] = dict(zip(head[1:], r[1:]))
    gag_sex = {"getagrip": sizing.getagrip()} if os.path.isdir(os.path.join(ROOT, "out/files/getagrip")) else {}
    made = 0
    for game in GAME_NAME:
        for cdir in sorted(glob.glob(os.path.join(ROOT, f"out/rerig/{game}/*/"))):
            costumes = sorted(glob.glob(cdir + "*.glb"))
            if not costumes:
                continue
            slug = os.path.basename(cdir.rstrip("/"))
            m = re.match(r"pc(\d+)_?(.*)", slug)
            n = int(m.group(1))
            name = m.group(2) or os.path.basename(costumes[0]).split("_")[1]
            mod = os.path.join(ROOT, f"out/mods/{game}_pc{n:02d}_{name}")
            for c in costumes:
                link(c, os.path.join(mod, "model", os.path.basename(c)))
            g, b = glb.read(costumes[0])
            h = -binds(g, b)[0]["Bip01"][1, 3]
            pool, why = hst, "nearest Bip01 height"
            if game in gag_sex:  # sex known: nearest of HST's same-sex standard bodies
                pool = [c for c in hst if c["sex"] == gag_sex[game][n][0] and c["model_type"] in sizing.STANDARD_BODY]
                why = f"nearest Bip01 height among HST's standard-body {'women' if gag_sex[game][n][0] == 'f' else 'men'}"
            donor = min(pool, key=lambda c: abs(c["bip01_height"] - h))
            manifest = {"standard": 1, "id": f"{game}_pc{n:02d}_{name}", "name": name.replace("_", " ").title(),
                        "source": f"{GAME_NAME[game]} pc{n:02d}",
                        "costumes": [f"model/{os.path.basename(c)}" for c in costumes],
                        "donor": donor["index"], "donor_why": f"{why} ({h:.3f} m vs {donor['name']} {donor['bip01_height']} m)",
                        "hand": "right", "params": {"base": donor["index"], "override": {}},
                        "ai_row": donor["index"], "face": "morph", "voice": None, "todo": []}
            if game in ("getagrip",):
                f = gag_faces.get(slug) or next((v for k, v in gag_faces.items() if k.startswith(f"pc{n:02d}")), None)
                if f:
                    # ship the face textures inside the mod, paths relative to it
                    def local(p):
                        link(os.path.join(ROOT, p), os.path.join(mod, "face", os.path.basename(p)))
                        return "face/" + os.path.basename(p)
                    f = dict(f, materials=[f["face_material"]], neutral=local(f["neutral"]), channels={k: v and local(v) for k, v in f["channels"].items()})
                    json.dump(f, open(os.path.join(mod, "face.json"), "w"), indent=1)
                    manifest["face"] = "texture"
                # the default racket (Racket_param Racket_000: owned from the start, price 0, all stats 0) as racket.glb
                part = os.path.join(ROOT, "out/models/getagrip/parts/racket/racket00.glb")
                if os.path.exists(part):
                    racket.make(part, costumes[0], os.path.join(mod, "racket.glb"))
                    manifest["racket_why"] = "Get a Grip default racket Racket_000 (racket000.xb), source grip on the hand, resized to HST's 0.944 m"
                sz = os.path.join(ROOT, "out/rerig/getagrip/sizing.json")
                if os.path.exists(sz):
                    sz = json.load(open(sz))
                    ch = sz["characters"][f"pc{n:02d}"]
                    manifest["size_why"] = f"{ch['why']}; head × {ch['head_factor']:.4f} about the neck ({ch['head_why']})"
                manifest["voice"] = "voice/"
                manifest["voice_counts"] = gag_voices(n, mod)
                manifest["source_stats"] = gag_stats.get(n, {})
                manifest["todo"] += ["map source_stats onto TParam (params.override)", "check voice programs 1/2 by ear (st_ji/st_nb)"]
            else:
                vd = os.path.join(ROOT, f"out/voices/{game}/pc{n:02d}")
                if os.path.isdir(vd):
                    for f in glob.glob(vd + "/*.wav"):
                        link(os.path.realpath(f), os.path.join(mod, "voice/unsorted", os.path.basename(f)))
                    manifest["voice"] = "voice/unsorted/"
                    manifest["todo"].append("sort voice/unsorted into <program>_<key>.wav (standard §5)")
                if game.startswith("opentee"):
                    manifest["face"] = "none"
                    manifest["todo"].append("texture faces: label the face textures (as Get a Grip's faces.json)")
                manifest["todo"].append("map the source game's stats onto TParam (params.override)")
            manifest["todo"].append("confirm handedness")
            json.dump(manifest, open(os.path.join(mod, "mod.json"), "w"), indent=1, ensure_ascii=False)
            made += 1
    print(made, "mods in out/mods/")


if __name__ == "__main__":
    main()
