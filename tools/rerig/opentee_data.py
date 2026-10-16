"""Hot Shots Golf: Open Tee 2 (opentee2, pc00-20) character data for HST mods
(notes/opentee.md "Mod data"). Everything is read at run time from extracted/ and out/ (never committed).

stats(game), MAP[game], style(game, pc), heights(game), voices(game, pc), reactions(game, pc), faces(game, pc) as
package.py / gag_stats.py / sizing.py expect (they take `game` like the other data modules; only "opentee2").
`python3 tools/rerig/opentee_data.py` prints the cast.
"""
import csv
import glob
import io
import json
import os
import struct
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAMES = ("opentee2",)
USR = "out/files/{g}/PSP_GAME/USRDIR/xbdata"
SLUG = ["mika", "rio", "alia", "shu", "julie", "cj", "patricia", "logan", "holly", "roger", "carly", "luke", "alice",
        "malachy", "frauada", "montcalm", "lauryn", "mifune", "lee", "chad", "gloria"]


def _p(*a):
    return os.path.join(ROOT, *a)


def _rows(game):
    f = _p(USR.format(g=game), "kuwa/param/param.xb/data/kuwabara/pc/face.csv")
    return list(csv.reader(io.StringIO(open(f, "rb").read().decode("cp932"))))


def _table(game):
    """{pc: row dict}: rows 000-020 per pc, then one PId block (Ctr/BS/TS/SS) of 21 rows each."""
    rows = _rows(game)
    h = next(i for i, r in enumerate(rows) if "名称" in r)
    hdr = [c.strip() for c in rows[h]]
    out = {}
    for r in rows[h + 1:]:
        r = [c.strip() for c in r]
        if not r or not r[0].strip().isdigit():
            continue
        d = dict(zip(hdr, r))
        pc = int(d["ＩＤ"])
        e = out.setdefault(pc, dict(d, sex=d["タイプ"]))
        e[d["PId"]] = d["LV00"]  # level-0 value of this stat (Pow: yards)
        e[d["PId"] + "_BL"] = d["BL"]
    return out


def stats(game):
    """{pc: {stat: str}}: Pow (level-0 driver yards), Ctr, Imp, BS (back spin), SS (side spin), TS (top spin)."""
    keys = ["Pow", "Ctr", "Imp", "BS", "SS", "TS"]
    return {pc: {k: d.get(k, "") for k in keys} for pc, d in _table(game).items()}


_POW = "{} (golf shot power; OT2 = level-0 driver yards): longer hitter, harder strokes"
_IMP = "Imp (impact window size; the beginner Mika has the biggest): a forgiving sweet spot, as HST's bigger timing windows"


def _map(game):
    pw, bs = "Pow", "BS"
    m = {c: ([pw], _POW.format(pw)) for c in ("Serv POW", "Strk POW", "LOW POW", "Voley POW", "V LOW POW", "Lob POW", "Lob POW2")}
    m.update({c: (["Ctr"], "Ctr (golf shot control): straighter, steadier strokes") for c in ("Strk CON", "Voley CON", "Serv CON")})
    m.update({c: (["Imp"], _IMP) for c in ("ショット ウサギIMP GI/NI/BI", "ショット カメIMP GI/NI/BI")})
    m.update({c: ([bs], f"{bs} (golf back spin): more under-spin on slices and drops") for c in ("Slice SPIN", "Drop SPIN")})
    m["Top SPIN"] = (["TS"], "TS (golf top spin, 40 for most, 50 for Logan, Mifune, Chad)")
    return m


MAP = {g: _map(g) for g in GAMES}


def style(game, pc):
    return None, ("no play style in the data: golf types (face.csv タイプ = sex, 種別/カテゴリ = unlock class) "
                  "do not describe a tennis style")


def heights(game):
    """{pc: (sex, None, why, scale)}: the game gives no cm heights, only a body scale % (OT2 also a head scale %);
    sizing.py multiplies the shared body's own Bip01 height by `scale`."""
    out = {}
    for pc, d in _table(game).items():
        sx = "m" if d["sex"] == "1" else "f"
        hs = f", head scale {d['頭scale']} %" if d.get("頭scale") else ""
        out[pc] = (sx, None, f"Open Tee 2 face.csv has no height in cm, "
                             f"only a model scale of {d['scale']} %{hs}", float(d["scale"]) / 100)
    return out


# ---- voices ---------------------------------------------------------------------------------------------------

def _wavlen(p):
    with wave.open(p) as w:
        return w.getnframes()


def _rms(p):
    import numpy as np
    with wave.open(p) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float)
    return float(np.sqrt((a ** 2).mean())) if len(a) else 0.0


def _tail(p):
    with wave.open(p) as w:
        return w.readframes(w.getnframes())


def _ot2_bank(kind, pc, v="a"):
    """OT2 hats/snd bank pc_<kind>_NN<v> (v = a, or b: the second take set) waves from the .xb1 copy (English takes: names 'Mika_..', '_US'; the .xb copy
    holds the Japanese 'Yum_..'). Its names.txt does not tie names to waves reliably (pc10+), so no names."""
    d = sorted(glob.glob(_p(USR.format(g="opentee2").replace("out/files", "out/audio"),
                            f"hats/snd/pc_*_{pc:02d}{v}.xb1/data/sound/pc_{kind}_{pc:02d}{v}.sgd")))
    return sorted(glob.glob(os.path.join(d[0], "[0-9][0-9][0-9].wav"))) if d else []


def _shared(first, *others):
    """Waves of `first` whose samples also appear in every other bank (the lines all play modes share)."""
    keys = [{_tail(f) for f in o} for o in others]
    return [f for f in first if all(_tail(f) in k for k in keys)]


# Won/lost lines by what they say (faster-whisper transcripts of the unused st/vs/ya/g waves, out/voice_candidates/
# opentee2_pcNN/index.tsv; notes/opentee.md "Voice lines"). "<bank>/<wave>" of the `a` banks, "<bank>b/<wave>" of the
# `b` ones. ya (heckles) lines that talk to the other player ("Good shot!", "What's wrong?") are left out. English
# copies only: the Japanese copy's grunts are another actor's voice.
WON = {0: ["st/006", "vs/007", "vs/005", "g/005"],  # Good! Yeah! Amazing! Yes!
       1: ["vs/010", "st/005", "vs/007", "g/003", "g/004"],  # Woo! YES! Nice! Ha ha! Oh yeah! Woohoo!
       2: ["st/006", "st/007", "st/005", "ya/008", "g/004"],  # Good! Yes! Yes, that's it! Nice shot! All right!
       3: ["st/003", "ya/008", "vs/005", "g/005"],  # Woo! Nice shot! Oh, pretty good! ..Yeah!
       4: ["st/006", "vs/007", "ya/008", "g/005"],  # Yeah! Nice! Nice shot! Ha ha ha!
       5: ["vs/007", "vs/005", "st/007", "st/005", "g/006"],  # Great! Excellent! Perfect! Very good! Hooray!
       6: ["st/005", "st/004", "vs/006", "vs/005"],  # There's a good one! Yes, that's it! Very good! Oh, wow, yes!
       7: ["st/005", "st/006", "ya/007", "g/003"],  # Yeah! Yeah! You got it! Ha ha ha ha! Yeah!
       8: ["st/005", "g/003", "g/004", "g/005"],  # Very nice. Yes! I am that good. Yeah!
       9: ["st/004", "vs/006"],  # Yes! Excellent job!
       10: ["st/001", "vs/009", "st/012", "vs/011", "g/004"],  # Yeah! Great! Alright! Awesome! Yes! One, two..
       11: ["vs/009", "st/010", "st/011", "vs/007", "g/003"],  # Yeah! Good! Great! Cool! Hey, yes!
       12: ["stb/003", "stb/011", "vsb/010", "gb/006"],  # Yes! Very nice! Wonderful! I did it! I did it!
       13: ["st/011", "st/010", "st/012", "stb/011", "g/007"],  # Yes! Yeah! YAHOO! Oh yeah! Yay! Woohoo! Fantastic!
       14: ["st/008", "vs/014", "stb/012", "vs/011", "vs/010"],  # Yeah! Good! I did it! Woo! Nice work!
       15: ["st/008", "stb/012", "vs/008", "st/012", "g/006"],  # Oh yeah. Perfect! Fantastic! Yeah, great. Ha ha! Gotcha!
       16: ["stb/009", "st/008", "st/012", "vs/010", "g/004"],  # Woo! Yeah! Yes! Excellent! Yeah! That's cool!
       17: ["st/009", "vsb/008", "vsb/010", "stb/008", "vs/008"],  # Yes. Wow! Uncanny! There! Beyond the words!
       18: ["stb/001", "st/012", "st/008", "vsb/014"],  # Yeah. Yes. Yes. Even I can be lucky.
       19: ["stb/011", "vsb/010", "vs/009", "g/004", "gb/003"],  # Good. Nice! Pretty good! Hehehe! Yes! Yes, yes, on..
       20: ["st/011", "vsb/011", "st/012", "stb/009", "stb/010"]}  # Good! Yes, yes! Did it! Perfect! That felt good!
LOST = {0: ["st/009", "st/008", "g/001"],  # Ugh! Oh no! Oh, why?
        1: ["g/001", "g/002"],  # Ugh! Awww!
        2: ["st/010"],  # No!
        3: ["st/008", "vs/009", "ya/009"],  # UGH! Bad luck! NO! NO!
        4: ["st/010", "st/009", "vs/008"],  # Ugh! Oh no! No good.
        5: ["st/009", "g/002"],  # This could be bad. No! No! No!
        6: ["st/003", "st/009", "st/008"],  # No! Terrible! Oh no!
        7: ["st/009", "g/001"],  # No! Nah, I didn't miss that shot!
        8: ["st/010", "vs/008"],  # Aww. That's awful.
        10: ["stb/013", "stb/015", "st/015", "g/001"],  # Oh no! UGH! Unlucky! Oh, sheesh! Why me?
        11: ["vs/011", "st/012", "stb/013", "g/001"],  # No! No! No good! No! What went wrong?
        12: ["stb/014", "vsb/013", "st/013"],  # No! Oh no! Oh no.
        13: ["st/014", "stb/014", "st/013", "st/015"],  # That's bad. No! Oh no! No good.
        14: ["st/014", "vsb/013", "stb/013"],  # NO! Shame! I've lost it!
        15: ["st/014", "stb/015", "gb/001", "g/001"],  # No way. No cigar. Ugh, disgraceful. Horrendous, just terrible
        16: ["vs/014", "st/013", "stb/014", "vs/012", "gb/001"],  # Ugh. No. Why me? Oh that's no good. How? Oh no.
        17: ["stb/005", "stb/015", "st/015", "stb/014", "stb/009"],  # No. UGH! I failed. Alas! It's over!
        18: ["stb/013", "st/014", "stb/015", "vs/012"],  # Why? But why? No way! No hope.
        19: ["st/014", "stb/015", "stb/014", "gb/001"],  # No! Ugh. No way! Oh, no comment.
        20: ["vsb/012", "st/013", "gb/001"]}  # That's no good. A bad one. Ugh, I think they're cheating!
# mis-hit / whiff (programs 2, 4): "What?", "Huh?", "Hmm", "Uh-oh"
MISS = {0: ["st/010", "vs/009"], 1: ["st/010", "st/009"], 2: ["st/009"], 4: ["vs/009"], 5: ["vs/008"], 6: ["vs/009"],
        8: ["st/008"], 9: ["st/008", "vs/007"], 10: ["vsb/012"], 11: ["vsb/012"], 13: ["stb/015", "vsb/011"],
        14: ["stb/003", "st/011"], 16: ["stb/015"], 17: ["stb/013", "vs/011"], 18: ["st/011", "vs/011", "st/015"],
        19: ["st/005", "vsb/013", "vs/012"], 20: ["vs/011"]}
# shot shouts (programs 0, 1, 3) where the shared-shout heuristic finds none or one: Shu, Patricia, Roger
SHOUT = {3: ["st/002", "st/004", "st/003"],  # Hai! Come on! Woo!
         6: ["st/002", "ya/002"],  # HA! Ah!
         9: ["st/007"]}  # Behold!


def _picks(pc, table):
    out = []
    for k in table.get(pc, []):
        bank, w = k.split("/")
        fs = _ot2_bank(bank[:-1], pc, "b") if bank.endswith("b") else _ot2_bank(bank, pc)
        if int(w) <= len(fs):
            out.append(fs[int(w) - 1])
    return out


def voices(game, pc):
    """({program: [wav]}, {program: why}). No voice is labelled with an event in either game (no cue table in the
    program or the banks): shouts from bank layout, won/lost lines from transcripts (WON/LOST)."""
    why = {}
    common = _shared(*[_ot2_bank(k, pc) for k in ("st", "vs", "ya")])
    prog = {}
    if common:
        loud = sorted(common, key=_rms, reverse=True)
        prog[0] = loud[:3]
        prog[1] = loud[:5]
        prog[3] = loud[:3]
        why[0] = (f"the {len(common)} short (0.1-0.6 s) waves every per-mode bank shares "
                  "(st/vs/ya, equal samples; the rest are mode lines), i.e. the in-play shouts; the three loudest by RMS "
                  "(heuristic: unlabelled)")
        why[1] = "the same shared in-play shouts, loudest first (heuristic: unlabelled)"
        why[3] = "same three loudest shouts as program 0 for the dive effort (heuristic: no dive voice in golf)"
    shout = _picks(pc, SHOUT)
    if shout:
        for p in (0, 1, 3):
            prog[p] = (prog.get(p, []) + shout)[:5 if p == 1 else 3]
        for p in (0, 1, 3):
            why[p] = (why[p] + " + " if p in why else "") + "the shouts picked by transcript (SHOUT)"
    miss = _picks(pc, MISS)
    if miss:
        prog[2], prog[4] = miss[:3], miss[:2]
        why[2] = why[4] = "the st/vs lines that say a slip ('What?', 'Huh?', 'Hmm', 'Uh-oh'; by transcript, MISS)"
    won, lost = _picks(pc, WON), _picks(pc, LOST)
    if won:
        prog[7] = prog[9] = won
        why[7] = why[9] = "the st/vs/ya/g lines that say a win ('Yes!', 'Nice!', 'Hooray!'; by transcript, WON)"
    if lost:
        prog[8] = prog[10] = lost
        why[8] = why[10] = "the st/vs/ya/g lines that say a loss ('Oh no!', 'Ugh!', 'Bad luck!'; by transcript, LOST)"
    for p, w in ((2, "no mis-hit voice identifiable"), (4, "no whiff voice identifiable"),
                 (6, "no partner call in golf; the long g bank lines (1.5-4 s, unlabelled) are not calls"),
                 (8, "no losing line sorted yet (candidates: out/voice_candidates)"),
                 (10, "no losing line sorted yet")):
        why.setdefault(p, w)
    if 7 not in prog:
        why[7] = why[9] = "no winning line sorted yet (candidates: out/voice_candidates; cd_hy_NN are the caddies')"
    return prog, why


SGXD = "yes: every voice bank is .sgd (SGXD), so the region root-note pitch issue in tools/audio.py applies"


# ---- reactions ------------------------------------------------------------------------------------------------

def _anims(game, pc):
    f = _p(f"out/anims/{game}/pc{pc:02d}_{SLUG[pc]}.glb")
    m = json.load(open(_p(f"out/anims/{game}/motions.json"))).get(f"pc{pc:02d}", {})
    return f, set(m.get("exported", []))


def reactions(game, pc):
    """(glb, {hst: [intro, loop?]}, {hst: why}). Times are as exported (60 Hz); the face TATs run twice as long as
    the I3M clips (e.g. win00 3.0 s vs 90 frames), so the game likely plays them at 30 Hz. package.py retimes to
    the donor's clip anyway. Golf celebrations walk off their spot: package.py holds the root (PIN). Each is one
    clip, never followed by the idle: it holds its last frame to the end of the transition (opentennis B478)."""
    f, a = _anims(game, pc)
    if not a:
        return f, {}, {}
    n = f"{pc:02d}"
    pick = lambda *c: next((x for x in c if x in a), None)
    clips, why = {}, {}
    gu = pick(f"ku{n}_gl", f"ga_pc{n}_bi_r00", f"ga_pc{n}_pa_r00")
    di = pick(f"ku{n}_di", f"re_pc{n}_os", f"ga_pc{n}_bo_r00")
    if gu:
        clips["re_gu"] = [gu]
        why["re_gu"] = ("ku_gl, Open Tee 2's 'glad' emote (joy face)" if gu.startswith("ku") else
                        "ga_bi_r00, the birdie celebration")
    if di:
        clips["re_di"] = [di]
        why["re_di"] = {"k": "ku_di, Open Tee 2's 'down' emote (sorrow face)", "r": "re_pc_os, the "
                        "missed-shot reaction (sorrow face)", "g": "ga_bo_r00, the bogey reaction"}[di[0]]
    if f"win{n}" in a:
        clips["re_gu_set"] = [f"win{n}"]
        why["re_gu_set"] = "win, the result screen's winner motion"
    if f"lost{n}" in a:
        clips["re_di_set"] = [f"lost{n}"]
        why["re_di_set"] = "lost, the result screen's loser motion"
    return f, clips, why


# ---- faces ----------------------------------------------------------------------------------------------------

def _tat(path):
    """Like psp2gltf/tat.py but tolerant: some names carry a fullwidth 'ｆ' (cp932), read as 'f'."""
    b = open(path, "rb").read()
    o = 4
    tracks = []
    for _ in range(struct.unpack_from("<I", b)[0]):
        def s():
            nonlocal o
            n, = struct.unpack_from("<I", b, o)
            v = b[o + 4:o + 4 + n].split(b"\0")[0].decode("cp932", "replace").replace("ｆ", "f")
            o += 4 + n
            return v
        target = s()
        ntex, = struct.unpack_from("<I", b, o)
        o += 4
        tex = [s() for _ in range(ntex)]
        nk, = struct.unpack_from("<I", b, o)
        t = struct.unpack_from(f"<{nk}f", b, o + 4)
        i = struct.unpack_from(f"<{nk}I", b, o + 4 + 4 * nk)
        o += 4 + 8 * nk
        tracks.append((target, tex, list(zip(t, i))))
    return tracks


def _held(path):
    """{face letter: seconds shown} over a TAT's face track ('' = neutral)."""
    out = {}
    for target, tex, keys in _tat(path):
        if not target.startswith("face"):
            continue
        for k, (t, i) in enumerate(keys):
            nxt = keys[k + 1][0] if k + 1 < len(keys) else t
            stem = tex[i]
            letter = stem.split("_", 1)[1] if "_" in stem else ""
            out[letter] = out.get(letter, 0) + max(nxt - t, 0)
    return out


def _tats(pc):
    """Open Tee 2's face TATs for this pc by motion name."""
    u = _p(USR.format(g="opentee2"))
    fs = glob.glob(f"{u}/kuwa/pc/face/motion{pc:02d}.xb/data/kuwabara/pc/face/{pc:02d}/*.tat")
    fs += glob.glob(f"{u}/tnk/result/Motion/r_mot{pc:02d}.xb/data/tanaka/result/Motion/*.tat")
    return {os.path.basename(f)[:-4]: f for f in fs}


def _letter(t, names):
    tot = {}
    for nm in names:
        if nm in t:
            for k, v in _held(t[nm]).items():
                if k not in ("", "a"):
                    tot[k] = tot.get(k, 0) + v
    return max(tot, key=tot.get) if tot else None, [nm for nm in names if nm in t]


def _png(game, pc, letter):
    d = _p(f"out/textures/{game}/face")
    if letter is None:
        p = f"{d}/face{pc:02d}.png"
    else:
        p = f"{d}/face{pc:02d}_{letter}.png"
        if not os.path.exists(p) and letter == "f":  # the fullwidth-ｆ texture's file name is garbled
            p = next(iter(x for x in glob.glob(f"{d}/face{pc:02d}_*.png")
                          if not os.path.basename(x)[7:-4].isascii()), p)
    return os.path.relpath(p, ROOT) if os.path.exists(p) else None


def _materials(game, pc):
    f = _p(f"out/models/{game}/pc{pc:02d}_{SLUG[pc]}/pc{pc:02d}_{SLUG[pc]}_own.glb")
    if not os.path.exists(f):
        return set()
    b = open(f, "rb").read()
    n, = struct.unpack_from("<I", b, 12)
    return {m.get("name") for m in json.loads(b[20:20 + n]).get("materials", [])}


def faces(game, pc):
    """Get a Grip faces.json style. Letters from Open Tee 2's TAT face tracks (the same in every motion that
    shows them): a = blink (idle and address blinks), joy = most-held letter over the clap/wave/glad emotes
    (fallback win, eagle, birdie), anger = the angry emote (fallback the shake emote), sorrow = the down emote
    (fallback lost). Eye and mouth share one whole-face texture. No consistent nervous (doki) face: null."""
    mat = f"face{pc:02d}"
    if mat not in _materials(game, pc):
        return None
    t, n = _tats(pc), f"{pc:02d}"
    joy, js = _letter(t, [f"ku{n}_cl", f"ku{n}_ha", f"ku{n}_gl"])
    if joy is None:
        joy, js = _letter(t, [f"win{n}", f"ga_pc{n}_ea_r00", f"ga_pc{n}_bi_r00"])
    ang, as_ = _letter(t, [f"ku{n}_an"])
    if ang is None:
        ang, as_ = _letter(t, [f"ku{n}_sh"])
    sor, ss = _letter(t, [f"ku{n}_di"])
    if sor is None:
        sor, ss = _letter(t, [f"lost{n}"])
    ch = {"blink_eye": _png(game, pc, "a")}
    for k, l in (("joy", joy), ("anger", ang), ("sorrow", sor)):
        p = l and _png(game, pc, l)
        ch[f"{k}_eye"] = ch[f"{k}_mouth"] = p
    ch["doki_eye"] = ch["doki_mouth"] = None
    return {"face_material": mat, "neutral": _png(game, pc, None), "channels": ch,
            "labels": {"joy": [joy, js], "anger": [ang, as_], "sorrow": [sor, ss], "blink": ["a", "wait/address"]},
            "why": "Open Tee 2 TAT face tracks"}


if __name__ == "__main__":
    for g in GAMES:
        st = stats(g)
        print(f"== {g}: {len(st)} characters; MAP columns {len(MAP[g])}; voices SGXD: {SGXD.split(':')[0]}")
        hs = heights(g)
        for pc in sorted(st):
            prog, _ = voices(g, pc)
            _, cl, _ = reactions(g, pc)
            f = faces(g, pc)
            lab = f and {k: v[0] for k, v in f["labels"].items()}
            print(f"pc{pc:02d} {SLUG[pc]:9} {hs[pc][0]} {st[pc]} voices {{{', '.join(f'{k}:{len(v)}' for k, v in sorted(prog.items()))}}}"
                  f" {cl} face {lab} missing={[k for k, v in (f or {}).get('channels', {}).items() if v is None]}")
    assert MAP["opentee2"]["Serv POW"][0] == ["Pow"] and "Top SPIN" in MAP["opentee2"]
