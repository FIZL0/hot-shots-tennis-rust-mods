"""Package every rerigged character as a mod folder (standard/HST-CHARACTER-STANDARD.md §1, §6).

python3 tools/rerig/package.py [game…]     (after batch.py; default every game)  ->  out/mods/<game>_<slug>/

Files are hard links into out/ (game data: never commit). Every game gets: costumes; a same-sex donor with the
nearest Bip01 height; the face (morph, or face.json for the PSP texture swaps); voices sorted into HST programs; the
source stats ranked onto TParam as params.override (gag_stats.overrides; needs HST's TParam.csv: HST_TPARAM or
../open-tennis/context/xb) with ai_row by play style where the game has one; the game's own point/set reactions
as motions.glb (motions.py; needs ../open-tennis/context/xb/PCANI for the donor clip lengths; golf roots held,
PIN); and a racket of its own (pick_racket: no two mods of a game share one). Get a Grip's data is
in gag_stats.py, the golf games' in fore_data.py / oob_data.py / opentee_data.py. Handedness: a golf mod whose
costumes wear a glove on the left hand is left-handed (glove hand = racket hand, standard §6 `hand`) and ships its
costumes pre-mirrored (mirror.py) instead of linked; the rest stay right-handed, left for a human to confirm.
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
import gag_stats as gagmap  # noqa: E402
import motions  # noqa: E402
import mirror  # noqa: E402

GAME_NAME = {"fore": "Hot Shots Golf Fore! (PS2)", "oob": "Hot Shots Golf: Out of Bounds (PS3)",
             "getagrip": "Hot Shots Tennis: Get a Grip (PSP)", "opentee": "Hot Shots Golf: Open Tee (PSP)",
             "opentee2": "Hot Shots Golf: Open Tee 2 (PSP)"}
# HST reaction motion <- Get a Grip's own reaction (intro, then its loop), per character (motions.py)
PIN = {"fore": True, "oob": True, "opentee": True, "opentee2": True}  # golf celebrations walk off their spot (notes/fore.md, oob.md): hold the root
GAG_REACT = {"re_gu": "gu01", "re_di": "di01", "re_gu_set": "gu_set01", "re_di_set": "di_set01"}
HST_ANI = gagmap.hst_xb(ROOT) + "/PCANI"
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


# HST voice program -> keys it plays (standard §5); reactions 7-10 take any number, capped like Get a Grip's at 5
KEYS = {0: 3, 1: 5, 2: 3, 3: 3, 4: 2, 6: 5, 7: 5, 8: 5, 9: 5, 10: 5}
# Rackets (M1r). No source game has a per-character racket (Get a Grip's Racket_param has no character column,
# notes/getagrip.md; the golf games have none), so each mod of a game gets a different one of the 24 there are:
# Get a Grip's 10 models (parts/racket: racket000-008 = items Racket_0N0-0N2, which share a model each, and
# racket050 = Racket_500) as racket.glb, or one of HST's 14 disc rackets (PC/PCnnC00.XB racket_nn, read from the
# user's disc: mod.json `disc_racket`). A golf mod holds a Get a Grip racket with Emi's grip, moved hand to hand.
GAG_RACKETS = ["00", "01", "02", "03", "04", "05", "06", "07", "08", "50"]
GAG_RACKET = os.path.join(ROOT, "out/models/getagrip/parts/racket/racket{}.glb")
GAG_GRIP = os.path.join(ROOT, "out/rerig/getagrip/pc00_emi/pc00_emi_set3.glb")
HST_NAMES = ["Ashley", "Cody", "Jun", "Kaito", "Momoko", "JJ", "Carol", "Big Chief", "Miranda", "Kent", "Lola", "Will",
             "Gloria", "Suzuki"]
HST_SAME = {"gloria": 12, "suzuki": 13}  # the same character in HST: her/his own racket there
_used = {}


def pick_racket(game, n, name, donor, mod, manifest, costumes, cast):
    """Racket for mod `n` of `game` (`cast`: every pc number -> name of the game, for the reserved HST picks).

    In pc order, the first free of: the same character's HST racket; for Get a Grip its own models in pc order
    (Emi keeps Racket_000 "Standard", the default everyone owns); for a golf mod its donor's HST racket (the
    character whose motions it plays); then Get a Grip's models in order; then HST's rackets in order."""
    used = _used.setdefault(game, set())
    reserved = {("disc", HST_SAME[c]) for c in cast.values() if c in HST_SAME}
    gag = [("gag", r) for r in GAG_RACKETS if os.path.exists(GAG_RACKET.format(r)) and (game == "getagrip" or os.path.exists(GAG_GRIP))]
    disc = [("disc", k) for k in range(14)]
    if name in HST_SAME:
        order = [("disc", HST_SAME[name])]
    elif game == "getagrip":
        order = gag + [("disc", donor["index"])] + disc
    else:
        order = [("disc", donor["index"])] + gag + disc
    pick = next(r for r in order if r not in used and (r not in reserved or name in HST_SAME))
    used.add(pick)
    out = os.path.join(mod, "racket.glb")
    manifest.pop("disc_racket", None)
    if pick[0] == "disc":
        if os.path.exists(out):
            os.remove(out)
        manifest["disc_racket"] = pick[1]
        why = (f"the same character's racket in HST ({HST_NAMES[pick[1]]})" if name in HST_SAME else
               f"its donor {HST_NAMES[pick[1]]}'s racket" if pick[1] == donor["index"] else
               f"HST {HST_NAMES[pick[1]]}'s racket, the first one no other {GAME_NAME[game]} mod holds")
        manifest["racket_why"] = f"{why}: PC/PC{pick[1]:02d}C00.XB racket_{pick[1]:02d}, read from your disc"
    else:
        part = GAG_RACKET.format(pick[1])
        item = "Racket_500" if pick[1] == "50" else f"Racket_0{int(pick[1])}0"
        if game == "getagrip":
            racket.make(part, costumes[0], out)
            grip = "its source grip on the hand"
        else:
            racket.make(part, GAG_GRIP, out, target=costumes[0])
            grip = "Get a Grip Emi's grip carried rigidly from her right hand to this one's (rerigged hands share HST's bone axes)"
        why = ("Get a Grip's starting racket Racket_000 'Standard', the one every character owns from the start" if pick[1] == "00" and game == "getagrip" else
               f"Get a Grip's racket{pick[1]}.xb (item {item}{', its other colours share the model' if pick[1] != '50' else ''}), "
               f"the first one no other {GAME_NAME[game]} mod holds")
        manifest["racket_why"] = f"{why} (Get a Grip has no per-character racket); {grip}, resized to HST's 0.944 m"
_cast = {}


def data(game):
    """The game's data module (fore_data / oob_data / opentee_data) as uniform callables, or None."""
    try:
        if game == "fore":
            import fore_data as d
        elif game == "oob":
            import oob_data as d
        else:
            import opentee_data as d
    except ImportError:
        return None
    if game in ("opentee", "opentee2"):
        mp = d.MAP[game] if isinstance(d.MAP, dict) and game in d.MAP else d.MAP
        return dict(stats=lambda: d.stats(game), map=mp, style=lambda n: d.style(game, n),
                    voices=lambda n: d.voices(game, n), reactions=lambda n: d.reactions(game, n),
                    faces=lambda n: d.faces(game, n), name=GAME_NAME[game].split(" (")[0])
    return dict(stats=d.stats, map=d.MAP, style=d.style, voices=d.voices, reactions=d.reactions,
                faces=getattr(d, "faces", lambda n: None), name=GAME_NAME[game].split(" (")[0])


def cast(game, D, tp):
    """The game's whole cast: (raw stats, {pc: (override, why)}), once per game (ranks need everyone)."""
    if game not in _cast:
        st = D["stats"]() or {}
        styles = {n: D["style"](n) for n in st}
        _cast[game] = (st, gagmap.overrides(st, tp, D["map"], styles) if tp and st else {})
    return _cast[game]


def voices(prog, dst):
    """{program: [wav]} -> voice/<program>_<key>.wav (old sorted and unsorted voices removed first)."""
    for f in glob.glob(os.path.join(dst, "voice/*.wav")):
        os.remove(f)
    shutil.rmtree(os.path.join(dst, "voice/unsorted"), ignore_errors=True)
    out = {}
    for p, files in sorted(prog.items()):
        files = files[:KEYS.get(p, 5)]
        for k, f in enumerate(files):
            link(os.path.realpath(f), os.path.join(dst, f"voice/{p}_{k}.wav"))
        if files:
            out[p] = len(files)
    return out


def golf(game, n, mod, manifest, costumes, donor, h, hst, tp, hst_type):
    """Fore, Out of Bounds, Open Tee 1/2 to the Get a Grip standard, from the game's data module."""
    D = data(game)
    if D is None:
        manifest["todo"].append("no data module for this game (tools/rerig/<game>_data.py)")
        return
    f = D["faces"](n)
    if f:
        def local(p):
            link(os.path.join(ROOT, p), os.path.join(mod, "face", os.path.basename(p)))
            return "face/" + os.path.basename(p)
        f = dict(f, materials=f.get("materials") or [f["face_material"]], neutral=local(f["neutral"]),
                 channels={k: v and local(v) for k, v in f["channels"].items()})
        json.dump(f, open(os.path.join(mod, "face.json"), "w"), indent=1, ensure_ascii=False)
        manifest["face"] = "texture"
    elif game.startswith("opentee"):
        manifest["face"] = "none"
    r = D["reactions"](n)
    if r and r[0] and r[1]:
        src, clips, whys = r
        plan = []
        for hst_name, seq in clips.items():
            pin = seq[-1] == "!" if seq and isinstance(seq[-1], str) else False
            seq = [x for x in seq if x != "!"]
            ani = os.path.join(HST_ANI, f"PC{donor['index']:02d}ANI.XB/data/taguchi/MtPc{donor['index']:02d}/{hst_name.replace('re_', f're_pc{donor['index']:02d}_')}.ANI2")
            plan.append((hst_name, seq, motions.ani_frames(ani) if os.path.exists(ani) else None, PIN.get(game, False) or pin))
        motions.make(costumes[0], src, os.path.join(mod, "motions.glb"), plan)
        manifest["motions"] = "motions.glb"
        manifest["motions_why"] = {k: f"{whys.get(k, '')}; {' then '.join(seq)}{', root held on its spot' if pin else ''}, played at 60 Hz, its own length and at least the donor's clip ({fr} frames)"
                                   for k, seq, fr, pin in plan}
    sz = os.path.join(ROOT, f"out/rerig/{game}/sizing.json")
    if os.path.exists(sz):
        ch = json.load(open(sz))["characters"].get(f"pc{n:02d}")
        if ch:
            manifest["size_why"] = f"{ch['why']}; head × {ch['head_factor']:.4f} about the neck ({ch['head_why']})"
    prog, vwhy = D["voices"](n)
    manifest["voice"] = "voice/"
    manifest["voice_counts"] = {str(k): v for k, v in voices(prog, mod).items()}
    manifest["voice_why"] = {str(k): v for k, v in vwhy.items()}
    st, params = cast(game, D, tp)
    manifest["source_stats"] = st.get(n, {})
    if n in params and params[n][0]:
        o, w = params[n]
        manifest["params"]["override"] = o
        manifest["params_why"] = dict(w, _rule=f"rank among {D['name']}'s {len(st)} -> same rank in HST's 14 rows of that column "
                                                f"(tools/rerig/gag_stats.py with tools/rerig/{game.rstrip('2')}_data.py MAP); other columns: the donor's row")
        if "タイプ" in o:
            chars = [dict(c, type=hst_type[c["index"]]) for c in hst]
            sex = (sizing.source(game) or {}).get(n, (donor["sex"],))[0] or donor["sex"]
            a = gagmap.ai_row(o["タイプ"], sex, h, chars)
            if a:
                manifest["ai_row"] = a["index"]
                manifest["ai_row_why"] = f"play style {o['タイプ']}: {'same sex, ' if a['sex'] == sex else ''}nearest Bip01 height among HST's {o['タイプ']} players ({a['name']} {a['bip01_height']} m)"
    else:
        manifest["todo"].append("no stats in the source data: params stay the donor's")


def main():
    hst = json.load(open(os.path.join(ROOT, "standard/hst_skeleton.json")))["characters"]
    fp = os.path.join(ROOT, "out/models/getagrip/faces.json")
    gag_faces = json.load(open(fp)) if os.path.exists(fp) else {}
    gag_stats = {}
    csvp = glob.glob(os.path.join(ROOT, "out/files/getagrip/**/parameter/character.csv"), recursive=True)
    if csvp:
        rows = [r.split(",") for r in open(csvp[0], encoding="utf-8", errors="replace").read().splitlines() if r]
        head = rows[0]
        for r in rows[1:]:
            m = re.match(r"Pc_(\d+)_00", r[0])
            if m:
                gag_stats[int(m.group(1))] = dict(zip(head[1:], r[1:]))
    gag_sex = {}
    for g in GAME_NAME:
        if os.path.isdir(os.path.join(ROOT, f"out/files/{g}")):
            src = sizing.source(g)
            if src:
                gag_sex[g] = src
    # Get a Grip's stats onto HST's TParam columns by rank (gag_stats.py; needs HST's TParam.csv)
    tp = gagmap.find_tparam(ROOT)
    gag_params = gagmap.overrides(gag_stats, tp) if tp and gag_stats else {}
    hst_type = gagmap.hst_types(tp) if tp else {}
    made = 0
    for game in [g for g in GAME_NAME if g in (sys.argv[1:] or GAME_NAME)]:
        cast_names = {int(m.group(1)): m.group(2) for d in glob.glob(os.path.join(ROOT, f"out/rerig/{game}/*/"))
                      if (m := re.match(r"pc(\d+)_?(.*)", os.path.basename(d.rstrip("/"))))}
        for cdir in sorted(glob.glob(os.path.join(ROOT, f"out/rerig/{game}/*/"))):
            costumes = sorted(glob.glob(cdir + "*.glb"))
            if not costumes:
                continue
            slug = os.path.basename(cdir.rstrip("/"))
            m = re.match(r"pc(\d+)_?(.*)", slug)
            n = int(m.group(1))
            name = m.group(2) or os.path.basename(costumes[0]).split("_")[1]
            mod = os.path.join(ROOT, f"out/mods/{game}_pc{n:02d}_{name}")
            lefty, hand_why = False, None
            if game in PIN:  # golf: the glove hand holds the racket
                lefty, hand_why, _ = mirror.gloved(f"{game}_pc{n:02d}_{name}", costumes)
            for c in costumes:
                if lefty:
                    mirror.mirror(c, os.path.join(mod, "model", os.path.basename(c)))
                else:
                    link(c, os.path.join(mod, "model", os.path.basename(c)))
            g, b = glb.read(costumes[0])
            h = -binds(g, b)[0]["Bip01"][1, 3]
            pool, why = hst, "nearest Bip01 height"
            if game in gag_sex and gag_sex[game].get(n, (None,))[0] in ("f", "m"):  # sex known: nearest of HST's same-sex standard bodies
                pool = [c for c in hst if c["sex"] == gag_sex[game][n][0] and c["model_type"] in sizing.STANDARD_BODY]
                why = f"nearest Bip01 height among HST's standard-body {'women' if gag_sex[game][n][0] == 'f' else 'men'}"
            donor = min(pool, key=lambda c: abs(c["bip01_height"] - h))
            manifest = {"standard": 1, "id": f"{game}_pc{n:02d}_{name}", "name": name.replace("_", " ").title(),
                        "source": f"{GAME_NAME[game]} pc{n:02d}",
                        "costumes": [f"model/{os.path.basename(c)}" for c in costumes],
                        "donor": donor["index"], "donor_why": f"{why} ({h:.3f} m vs {donor['name']} {donor['bip01_height']} m)",
                        "hand": "left" if lefty else "right", "params": {"base": donor["index"], "override": {}},
                        "ai_row": donor["index"], "face": "morph", "voice": None, "todo": []}
            if hand_why:
                manifest["hand_why"] = hand_why
            if game == "fore":
                # already high-res: open-tennis's upscale_mods.py leaves it alone
                manifest["upscale"] = False
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
                # its own point/set reactions, retargeted, timed to the donor's clips (visual only, standard §6 motions)
                react = os.path.join(ROOT, f"out/anims/getagrip/pc{n:02d}_{name}_react.glb")
                if os.path.exists(react):
                    clips = []
                    for hst_name, src in GAG_REACT.items():
                        ani = os.path.join(HST_ANI, f"PC{donor['index']:02d}ANI.XB/data/taguchi/MtPc{donor['index']:02d}/{hst_name.replace('re_', f're_pc{donor['index']:02d}_')}.ANI2")
                        clips.append((hst_name, [f"re_pc{n:02d}_{src}", f"re_pc{n:02d}_{src}_loop"], motions.ani_frames(ani) if os.path.exists(ani) else None))
                    motions.make(costumes[0], react, os.path.join(mod, "motions.glb"), clips)
                    manifest["motions"] = "motions.glb"
                    manifest["motions_why"] = {k: f"Get a Grip re_pc{n:02d}_{v} then its _loop, played at 60 Hz, its own length and at least the donor's clip ({f} frames)"
                                               for (k, v), (_, _, f) in zip(GAG_REACT.items(), clips)}
                sz = os.path.join(ROOT, "out/rerig/getagrip/sizing.json")
                if os.path.exists(sz):
                    sz = json.load(open(sz))
                    ch = sz["characters"][f"pc{n:02d}"]
                    manifest["size_why"] = f"{ch['why']}; head × {ch['head_factor']:.4f} about the neck ({ch['head_why']})"
                manifest["voice"] = "voice/"
                manifest["voice_counts"] = gag_voices(n, mod)
                manifest["source_stats"] = gag_stats.get(n, {})
                if n in gag_params:
                    o, w = gag_params[n]
                    manifest["params"]["override"] = o
                    manifest["params_why"] = dict(w, _rule="rank among Get a Grip's 15 -> same rank in HST's 14 rows of that column (tools/rerig/gag_stats.py); other columns: the donor's row")
                    # the computer plays it with an HST AI row of the same play style (body and motions stay the donor's)
                    if "タイプ" in o:
                        chars = [dict(c, type=hst_type[c["index"]]) for c in hst]
                        a = gagmap.ai_row(o["タイプ"], gag_sex[game][n][0], h, chars)
                        if a:
                            manifest["ai_row"] = a["index"]
                            manifest["ai_row_why"] = f"play style {o['タイプ']} (Playstyle {gag_stats[n]['Playstyle']}): {'same sex, ' if a['sex'] == gag_sex[game][n][0] else ''}nearest Bip01 height among HST's {o['タイプ']} players ({a['name']} {a['bip01_height']} m)"
                manifest["todo"] += ["check voice programs 1/2 by ear (st_ji/st_nb)"]
            else:
                golf(game, n, mod, manifest, costumes, donor, h, hst, tp, hst_type)
            pick_racket(game, n, name, donor, mod, manifest, costumes, cast_names)
            if not lefty:
                manifest["todo"].append("confirm handedness")
            if tp:
                gagmap.expert(manifest, tp, hst)
            json.dump(manifest, open(os.path.join(mod, "mod.json"), "w"), indent=1, ensure_ascii=False)
            made += 1
    print(made, "mods in out/mods/")


if __name__ == "__main__":
    main()
