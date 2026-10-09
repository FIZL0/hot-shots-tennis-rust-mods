"""Hot Shots Golf: Open Tee (opentee, pc00-09) and Open Tee 2 (opentee2, pc00-20) character data for HST mods
(notes/opentee.md "Mod data"). Everything is read at run time from extracted/ and out/ (never committed).

stats(game), MAP[game], style(game, pc), heights(game), voices(game, pc), reactions(game, pc), faces(game, pc) as
package.py / gag_stats.py / sizing.py expect. `python3 tools/rerig/opentee_data.py` prints both games.
"""
import csv
import glob
import io
import json
import os
import struct
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAMES = ("opentee", "opentee2")
USR = "out/files/{g}/PSP_GAME/USRDIR/xbdata"
SLUG = ["mika", "rio", "alia", "shu", "julie", "cj", "patricia", "logan", "holly", "roger", "carly", "luke", "alice",
        "malachy", "frauada", "montcalm", "lauryn", "mifune", "lee", "chad", "gloria"]


def _p(*a):
    return os.path.join(ROOT, *a)


def _rows(game):
    f = _p(USR.format(g=game), "kuwa/param/param.xb/data/kuwabara/pc/face.csv")
    return list(csv.reader(io.StringIO(open(f, "rb").read().decode("cp932"))))


def _table(game):
    """{pc: row dict}. OT1: one row per pc. OT2: rows 000-020 per pc, then one PId block (Ctr/BS/TS/SS) of 21 rows each."""
    rows = _rows(game)
    h = next(i for i, r in enumerate(rows) if "名称" in r)
    hdr = [c.strip() for c in rows[h]]
    out = {}
    for r in rows[h + 1:]:
        r = [c.strip() for c in r]
        if not r or not r[0].strip().isdigit():
            continue
        d = dict(zip(hdr, r))
        if game == "opentee":
            d["sex"] = r[11]  # second タイプ column: 1 male, 2 female
            out[int(r[0])] = d
        else:
            pc = int(d["ＩＤ"])
            e = out.setdefault(pc, dict(d, sex=d["タイプ"]))
            e[d["PId"]] = d["LV00"]  # level-0 value of this stat (Pow: yards)
            e[d["PId"] + "_BL"] = d["BL"]
    return out


def stats(game):
    """{pc: {stat: str}}. OT1: Pow Ctr Imp Spn(back spin) 曲げ(side spin/curve), all 'bigger is better'.
    OT2: Pow (level-0 driver yards), Ctr, Imp, BS (back spin), SS (side spin), TS (top spin)."""
    keys = ["Pow", "Ctr", "Imp", "Spn", "曲げ"] if game == "opentee" else ["Pow", "Ctr", "Imp", "BS", "SS", "TS"]
    return {pc: {k: d.get(k, "") for k in keys} for pc, d in _table(game).items()}


_POW = "{} (golf shot power; OT2 = level-0 driver yards): longer hitter, harder strokes"
_IMP = "Imp (impact window size; the beginner Mika has the biggest): a forgiving sweet spot, as HST's bigger timing windows"


def _map(game):
    pw, bs = ("Pow", "Spn") if game == "opentee" else ("Pow", "BS")
    m = {c: ([pw], _POW.format(pw)) for c in ("Serv POW", "Strk POW", "LOW POW", "Voley POW", "V LOW POW", "Lob POW", "Lob POW2")}
    m.update({c: (["Ctr"], "Ctr (golf shot control): straighter, steadier strokes") for c in ("Strk CON", "Voley CON", "Serv CON")})
    m.update({c: (["Imp"], _IMP) for c in ("ショット ウサギIMP GI/NI/BI", "ショット カメIMP GI/NI/BI")})
    m.update({c: ([bs], f"{bs} (golf back spin): more under-spin on slices and drops") for c in ("Slice SPIN", "Drop SPIN")})
    if game == "opentee2":
        m["Top SPIN"] = (["TS"], "TS (golf top spin, 40 for most, 50 for Logan, Mifune, Chad)")
    # ponytail: OT1 has no top-spin stat (its 'TS' column is a different, unlabelled number), so Top SPIN keeps HST's
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
        out[pc] = (sx, None, f"{'Open Tee 2' if game == 'opentee2' else 'Open Tee'} face.csv has no height in cm, "
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


def _ot1_clips(bank):
    """OT1 banks decode with every wave running on to the bank's end (wave k = clip k + all later clips, checked
    sample for sample). Cut each to its own part into out/voices/opentee/trim/ (generated, gitignored)."""
    d = glob.glob(_p(USR.format(g="opentee").replace("out/files", "out/audio"), f"**/{bank}.sgd"), recursive=True)
    if not d:
        return []
    fs = sorted(glob.glob(os.path.join(d[0], "[0-9][0-9][0-9].wav")))
    out = []
    for i, f in enumerate(fs):
        nxt = _wavlen(fs[i + 1]) if i + 1 < len(fs) else 0
        dst = _p("out/voices/opentee/trim", f"{bank}_{i + 1:03d}.wav")
        if not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with wave.open(f) as w:
                par, n = w.getparams(), w.getnframes()
                data = w.readframes(n)
            keep = n - nxt if nxt and data.endswith(_tail(fs[i + 1])) else n
            with wave.open(dst, "wb") as o:
                o.setparams(par)
                o.writeframes(data[:keep * par.sampwidth * par.nchannels])
        out.append(dst)
    return out


def _tail(p):
    with wave.open(p) as w:
        return w.readframes(w.getnframes())


def _ot2_bank(kind, pc):
    """OT2 hats/snd bank pc_<kind>_NNa waves from the .xb1 copy (English takes: names 'Mika_..', '_US'; the .xb copy
    holds the Japanese 'Yum_..'). Its names.txt does not tie names to waves reliably (pc10+), so no names."""
    d = sorted(glob.glob(_p(USR.format(g="opentee2").replace("out/files", "out/audio"),
                            f"hats/snd/pc_*_{pc:02d}a.xb1/data/sound/pc_{kind}_{pc:02d}a.sgd")))
    return sorted(glob.glob(os.path.join(d[0], "[0-9][0-9][0-9].wav"))) if d else []


def _shared(first, *others):
    """Waves of `first` whose samples also appear in every other bank (the lines all play modes share)."""
    keys = [{_tail(f) for f in o} for o in others]
    return [f for f in first if all(_tail(f) in k for k in keys)]


def voices(game, pc):
    """({program: [wav]}, {program: why}). No voice is labelled with an event in either game (no cue table in the
    program or the banks), so this is a heuristic from bank layout, not from listening."""
    why = {}
    if game == "opentee":
        banks = [_ot1_clips(f"{k}_{pc:02d}") for k in ("st", "vs", "ya")]
        hy = _ot1_clips(f"hy_{pc:02d}")
    else:
        banks = [_ot2_bank(k, pc) for k in ("st", "vs", "ya")]
        hy = _ot1_clips(f"hy_{pc:02d}") if pc < 10 else []
    # OT1: every bank ends with the same four lines (equal lengths, not always equal samples): st's last four
    common = banks[0][-4:] if game == "opentee" else _shared(*banks)
    prog = {}
    if common:
        loud = sorted(common, key=_rms, reverse=True)
        prog[0] = loud[:3]
        prog[1] = loud[:5]
        prog[3] = loud[:3]
        why[0] = (f"the {len(common)} short (0.1-0.6 s) waves every per-mode bank shares "
                  "(st/vs/ya; OT2: equal samples, OT1: each bank's last four; the rest are mode lines), i.e. the in-play shouts; the three loudest by RMS "
                  "(heuristic: unlabelled)")
        why[1] = "the same shared in-play shouts, loudest first (heuristic: unlabelled)"
        why[3] = "same three loudest shouts as program 0 for the dive effort (heuristic: no dive voice in golf)"
    if hy:
        prog[7] = hy
        prog[9] = hy
        why[7] = why[9] = ("tnk/result/Voice hy_NN: the awards-ceremony (表彰, menu 'mHyousyouVoice') lines, i.e. winning "
                           "lines" + (" (Open Tee's own, for its pc00-09: Open Tee 2 keeps their voices; e.g. Mika's first shared shout is identical sample for sample)" if game == "opentee2" else ""))
    for p, w in ((2, "no mis-hit voice identifiable"), (4, "no whiff voice identifiable"),
                 (6, "no partner call in golf; the long g bank lines (1.5-4 s, unlabelled) are not calls"),
                 (8, "no losing line identifiable (no labels; the mode-specific st/vs/ya lines are unsigned)"),
                 (10, "no losing line identifiable")):
        why.setdefault(p, w)
    if 7 not in prog:
        why[7] = why[9] = "no winning lines: Open Tee 2's own result voices (cd_hy_NN) are the caddies', not the golfers'"
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
    the donor's clip anyway. Golf celebrations walk off their spot: package.py holds the root (PIN)."""
    f, a = _anims(game, pc)
    if not a:
        return f, {}, {}
    n = f"{pc:02d}"
    pick = lambda *c: next((x for x in c if x in a), None)
    clips, why = {}, {}
    gu = pick(f"ku{n}_gl", f"ga_pc{n}_bi_r00", f"ga_pc{n}_pa_r00")
    di = pick(f"ku{n}_di", f"re_pc{n}_os", f"ga_pc{n}_bo_r00")
    wait = pick(f"wait{n}")
    if gu:
        clips["re_gu"] = [gu]
        why["re_gu"] = ("ku_gl, Open Tee 2's 'glad' emote (joy face)" if gu.startswith("ku") else
                        "ga_bi_r00, the birdie celebration (Open Tee has no emotes)")
    if di:
        clips["re_di"] = [di] + ([wait] if wait and di.startswith("ku") else [])
        why["re_di"] = {"k": "ku_di, Open Tee 2's 'down' emote (sorrow face), then the idle", "r": "re_pc_os, the "
                        "missed-shot reaction (sorrow face; Open Tee has no emotes)", "g": "ga_bo_r00, the bogey reaction"}[di[0]]
    if f"win{n}" in a:
        clips["re_gu_set"] = [f"win{n}"]
        why["re_gu_set"] = "win, the result screen's winner motion"
    if f"lost{n}" in a:
        clips["re_di_set"] = [f"lost{n}"] + ([wait] if wait else [])
        why["re_di_set"] = "lost, the result screen's loser motion, then the idle"
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
    """Open Tee 2's face TATs for this pc by motion name (Open Tee pc00-09 faces are the same textures)."""
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
            "why": "Open Tee 2 TAT face tracks" + (" (same textures as Open Tee's)" if game == "opentee" else "")}


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
    assert MAP["opentee"]["Serv POW"][0] == ["Pow"] and "Top SPIN" not in MAP["opentee"]
