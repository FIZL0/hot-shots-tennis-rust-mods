"""Hot Shots Golf: Out of Bounds (PS3, pc00-16) character data for HST mods (notes/oob.md "Mod data").
Everything is read at run time from out/ (never committed).

stats(), MAP, style(pc), heights(), voices(pc), reactions(pc) as package.py / gag_stats.py / sizing.py expect.
`python3 tools/rerig/oob_data.py` prints all 17.
"""
import glob
import json
import os
import re
import struct
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USR = "out/files/oob/PS3_GAME/USRDIR/xbdata"
AUD = "out/audio/oob/PS3_GAME/USRDIR/xbdata"
N = 17


def _p(*a):
    return os.path.join(ROOT, *a)


# ---- stats ----------------------------------------------------------------------------------------------------

# ueno/ability/player.dat ("ABI_PLAY", big-endian): 17 records of 5 f32 + 7 i32. The floats are the character-select
# bars in order (charaselect chrsel_prmset: bar_power, bar_control, bar_impact, bar_spin, bar_side); the ints were
# read off the help texts (draw/fade, rough, bunker, rain, approach weaknesses), the last is the profile's sex.
FLOATS = ("power", "control_spread", "impact", "spin", "side")
INTS = ("curve", "rough", "bunker", "rain", "approach", "_const", "sex")
# menu_help.to strings 500-516 describe the 17 in character-select order, not pc order. Matched by the flags
# (e.g. "poor in rough" = rough -1, "hits draw" = curve +1) and the tiers (the 5 lowest powers are Novice, ...).
HELP_PC = [0, 1, 2, 3, 13, 4, 7, 6, 8, 5, 9, 10, 11, 12, 14, 15, 16]
TYPES = ("All-rounder", "Big Hitter", "Control Player", "Spin Player", "Special")


def _player():
    d = open(_p(USR, "ueno/common/main.xb0/data/ueno/ability/player.dat"), "rb").read()
    assert d[:8] == b"ABI_PLAY"
    n = struct.unpack_from(">I", d, 0x14)[0]
    out = []
    for k in range(n):
        o = struct.unpack_from(">I", d, 0x30 + 4 * k)[0]
        f = struct.unpack_from(">5f", d, o)
        i = struct.unpack_from(">7i", d, o + 20)
        out.append(dict(zip(FLOATS, (round(x, 4) for x in f)), **dict(zip(INTS, i))))
    return out


def _help():
    s = open(_p(USR, "ookubo/menu/menu_common.xb0/data/text/menu_help.to"), "rb").read().split(b"\0")
    i = next(k for k, x in enumerate(s) if x.startswith(b"Novice All-rounder"))
    return {pc: s[i + k].decode().strip() for k, pc in enumerate(HELP_PC)}


def _profile(pc):
    f = _p(USR, f"kikkawa/menu/profile_txt.xb0/data/kikkawa/menu/profile/profile2/pc{pc:02d}.dat")
    return open(f, encoding="utf-8-sig").read().splitlines()


def stats():
    """{pc: {stat: str}}. control = 2 - control_spread: the game's control value is a spread multiplier (lower is
    better: club.dat/ball.dat trade +power for +control, and the help calls Sonia 1.2 / L.J. 1.3 'poor/terrible
    control'), so it is inverted to make higher = better like every other column. power/impact/spin/side: higher
    = more (longer drives, bigger impact window, more backspin, more curve)."""
    hl = _help()
    out = {}
    for pc, r in enumerate(_player()):
        h = hl[pc]
        out[pc] = {"name": _profile(pc)[0], **{k: str(v) for k, v in r.items() if k != "_const"},
                   "control": str(round(2 - r["control_spread"], 4)), "help": h,
                   "tier": h.split()[0], "type": next(t for t in TYPES if t in h)}
    return out


_POW = "power (golf drive power multiplier, 0.945-1.21): a longer hitter hits harder"
_CON = "control = 2 - control_spread (the game's shot-spread multiplier, inverted): straighter, more accurate"
_IMP = "impact (impact-zone size multiplier; the novices have the biggest): a forgiving sweet spot, as HST's timing windows"
MAP = {
    "Serv POW": (["power"], _POW),
    "Strk POW": (["power"], _POW),
    "Voley POW": (["power"], _POW),
    "Strk CON": (["control"], _CON),
    "Voley CON": (["control"], _CON),
    "Serv CON": (["control"], _CON),
    "ショット ウサギIMP GI/NI/BI": (["impact"], _IMP + " (early side)"),
    "ショット カメIMP GI/NI/BI": (["impact"], _IMP + " (late side)"),
    "Top SPIN": (["spin"], "spin (backspin multiplier): more spin on the ball"),
    "Drop SPIN": (["spin"], "spin (backspin multiplier): more bite on drop shots"),
    "Slice SPIN": (["spin", "side"], "spin + side (side = how far the character curves the ball): sidespin"),
}


def style(pc):
    """(タイプ or None, why) from the help text's class. Control/Spin/Special describe shot quality, not court
    position, so they get none."""
    s = stats()[pc]
    t = {"All-rounder": "オール", "Big Hitter": "ビッグ"}.get(s["type"])
    return t, f"menu help: \"{s['help']}\"" + ("" if t else " (no tennis style follows from it)")


def heights():
    """{pc: (sex, cm, why)}: profile2 height (feet'inches"), sex from player.dat (0 = female, as the bios' pronouns)."""
    out = {}
    for pc, r in enumerate(_player()):
        h = _profile(pc)[4]
        m = re.match(r"(\d+)'(\d+)", h)
        cm = round((int(m[1]) * 12 + int(m[2])) * 2.54) if m else None
        out[pc] = ("fm"[r["sex"]], cm, f"profile2 pc{pc:02d}.dat height {h}; player.dat sex {r['sex']}")
    return out


# ---- voices ---------------------------------------------------------------------------------------------------

def sgxd(path):
    """{(group, index): (cue name, [(wave, semitones)])}, plus each wave's sample count. A SEQD note is
    `d0|d2, n, n BCD digits` = program*128 + key; the RGND region with that key gives the wave and its root note
    (shift = key + 12 - root - fine/128: 0 = played as stored, which the exported wav is)."""
    d = open(path, "rb").read()
    u = lambda o: struct.unpack_from("<I", d, o)[0]
    ch, o = {}, 0x10
    while o + 8 < len(d) and d[o:o + 4].isalpha():
        ch[d[o:o + 4].decode()] = o
        o += 8 + u(o + 4)
    r = ch["RGND"]
    progs = [[struct.unpack_from("<14I", d, u(r + 0x14 + 8 * p) + 0x38 * k) for k in range(u(r + 0x10 + 8 * p))]
             for p in range(u(r + 0xc))]
    w = ch["WAVE"]
    samples = [u(w + 0x30 + 0x38 * k) for k in range(u(w + 0xc))]
    s, cues = ch["SEQD"], {}
    for g in range(u(s + 0xc)):
        t = u(s + 0x10 + 4 * g)
        if not t:
            continue
        for i in range(u(t + 4)):
            o = u(t + 8 + 4 * i) & 0x7fffffff
            if not o:
                continue
            h = struct.unpack_from("<5I", d, o)
            body = d[o + 20:o + 20 + h[4]]
            name = d[h[1]:d.find(b"\0", h[1])].decode() if 0 < h[1] < len(d) else "?"
            notes, k = [], 0
            while k < len(body):
                n = body[k + 1] if k + 1 < len(body) else 0
                if body[k] in (0xd0, 0xd2) and 1 <= n <= 2 and body[k + 2:k + 2 + n].hex().isdigit():
                    p, key = divmod(int(body[k + 2:k + 2 + n].hex()), 128)
                    rg = next((x for x in (progs[p] if p < len(progs) else [])
                               if (x[6] & 0xff) <= key <= (x[6] >> 8 & 0xff)), None)
                    if rg:
                        notes.append((rg[13], key + 12 - (rg[7] & 0xff) - (rg[7] >> 8 & 0xff) / 128))
                    k += 2 + n
                else:
                    k += 1
            cues[(g, i)] = (name, notes)
    return cues, samples


def _bank(pc, kind):
    f = glob.glob(_p(USR, f"sound/pc/ga_pc_{pc:02d}.xb*/data/sound/voice/game/pc/ga_{kind}_pc{pc:02d}.sgd"))[0]
    return f, _p(AUD, os.path.relpath(f, _p(USR)))


# The in-game bank ga_sg_pcNN has the same 58 SEQD slots (group 0: 42, group 1: 16 second takes) for everyone;
# the cue *names* are each actor's script lines (pc01: 04A-38E, Felipe: 20A-61) and pc00's are partly out of
# order, so the slot is the event. The profile screen's voice bank (me_pro_pcNN) names its groups in one numbering
# for all 17 and its "Play Animation" page (profile_chip04) lists Victory Pose, Reaction, Taunt 1, Taunt 2:
#   Victory Pose = 49A 49B 50A 51A = sg slots (0,29) (0,30) (0,31) (0,33)
#   Reaction     = 30 48 60A 39    = sg slots (0,10) (0,28) (0,40) (0,19)
#   Taunts       = 140-150         = ga_ya (yaji: heckling the other player's shot)
# (0,29)-(0,34) and their second takes (1,9)-(1,14) are one family (pc01 calls them all line 16A-16L; two are
# named Rare_Gattsu = rare guts pose): 6 hole-result celebrations, multi-part cues timed to the ga_* clips.
# No table ties any other slot to a golf event (the program, HSG5PS3.self, is encrypted), so the rest is chosen by
# duration only: (0,6)/(1,3) is the A/B pair that is the shortest line in every bank (~0.1 s): an effort shout.
SHOUT, SHOUT2 = [(0, 6), (1, 3), (0, 2)], [(0, 38), (0, 13)]
REACTION = [(0, 10), (0, 28), (0, 40), (0, 19)]
VICTORY, VICTORY2 = [(0, 29), (0, 30), (0, 31), (0, 33)], [(1, 9), (1, 10), (1, 11), (1, 13), (0, 32)]


def voices(pc):
    """({program: [wav]}, {program: why}). Each cue gives one file: its longest note's wave (a celebration cue
    plays 2-17 fragments in sequence; the wav is the main one)."""
    path, wd = _bank(pc, "sg")
    cues, samples = sgxd(path)
    shifted = []

    def files(slots):
        out = []
        for sl in slots:
            name, notes = cues.get(sl, ("", []))
            if not notes or "dummy" in name:
                continue
            w, sh = max(notes, key=lambda n: samples[n[0]])
            f = os.path.join(wd, f"{w + 1:03d}.wav")
            if os.path.exists(f):
                out.append(f)
                if abs(sh) > 0.01:
                    shifted.append((os.path.basename(f), round(sh, 2)))
        return out

    prog = {0: files(SHOUT), 1: files(REACTION), 3: files(SHOUT), 4: files(SHOUT2),
            7: files(VICTORY), 9: files(VICTORY2)}
    why = {0: "sg slots (0,6)/(1,3)/(0,2): the shortest lines in every bank (~0.1-0.3 s), i.e. effort shouts "
              "(heuristic: duration only, no event table)",
           1: "sg slots the profile's 'Reaction' set plays (lines 30/48/60A/39): shot reactions, sign unknown "
              "(heuristic: unlabelled)",
           3: "same effort shouts as program 0 (no dive in golf)",
           4: "sg slots (0,38)/(0,13): the next-shortest lines (heuristic: duration only)",
           7: "sg slots the profile's 'Victory Pose' set plays (lines 49A/49B/50A/51A, the hole-result celebrations)",
           9: "the same celebrations' second takes (1,9)-(1,13) and the rare guts pose (0,32)",
           2: "no mis-hit line identifiable (no event table; the program is encrypted)",
           6: "no partner call in golf; the taunts (ga_ya, lines 140-150) heckle the opponent, not a partner",
           8: "no losing line identifiable: nothing marks any line as disappointment (the profile's Disappointed "
              "slot is an animation only, ku_di)",
           10: "no losing line identifiable"}
    prog = {p: f for p, f in prog.items() if f}
    if shifted:
        why["pitch"] = (f"{len(shifted)} chosen file(s) are played {sorted({s for _, s in shifted})} semitones off "
                        "their stored pitch by the game (RGND root note; tools/audio.py exports them unshifted)")
    return prog, why


# ---- reactions ------------------------------------------------------------------------------------------------

SLUGS = {int(os.path.basename(f)[2:4]): f for f in glob.glob(_p("out/anims/oob/pc*.glb"))}


def _glb(f):
    d = open(f, "rb").read()
    n = struct.unpack_from("<I", d, 12)[0]
    j = json.loads(d[20:20 + n])
    return j, d, 28 + n


def _acc(j, d, bo, i):
    a, comp = j["accessors"][i], {"SCALAR": 1, "VEC3": 3, "VEC4": 4}
    v = j["bufferViews"][a["bufferView"]]
    c = comp[a["type"]]
    return np.frombuffer(d, np.float32, a["count"] * c, bo + v.get("byteOffset", 0) + a.get("byteOffset", 0)).reshape(-1, c)


def _clips(f):
    """{name: (frames at 60 Hz, pelvis horizontal travel in model units)}."""
    j, d, bo = _glb(f)
    pelvis = next(i for i, nd in enumerate(j["nodes"]) if nd.get("name") == "Bip01Pelvis")
    out = {}
    for a in j["animations"]:
        t = max(j["accessors"][s["input"]]["max"][0] for s in a["samplers"])
        move = 0.0
        for c in a["channels"]:
            if c["target"].get("node") == pelvis and c["target"]["path"] == "translation":
                p = _acc(j, d, bo, a["samplers"][c["sampler"]]["output"])
                move = float(np.ptp(p[:, [0, 2]], axis=0).max())
        out[a["name"]] = (round(t * 60), move)
    return out


# Meanings from the names (ku = the shared emote set: ga guts pose, di disappointed; ga_* = hole-result clips:
# ea/bi/pa/bo = eagle/birdie/par/bogey) and checked against each clip's face-morph channel: ku_ga / ga_bi /
# rslt_win drive smile+laugh targets, ku_di anger, ga_bo / rslt_loss sorrow (or sad/scowl).
PICK = {"re_gu": (r"ku\d\d_ga$", "ku_ga, the guts-pose emote (smile/laugh face)"),
        "re_di": (r"ku\d\d_di$", "ku_di, the disappointed emote (anger/sad face)"),
        "re_gu_set": (r"ga_pc\d\d_bi_r00$", "ga_bi_r00, the birdie celebration (smile face; ~90 frames like "
                                             "re_gu_set; rslt_win is 120)"),
        "re_di_set": (r"ga_pc\d\d_bo_r00$", "ga_bo_r00, the bogey reaction (sorrow face; ~95 frames like "
                                             "re_di_set; rslt_loss is 90)")}


def reactions(pc):
    """(glb, {hst: [intro]}, {hst: why}). One clip each, no loop. Times are as exported (60 Hz); the pelvis
    carries root motion (travel given in the why): package.py holds the root (PIN)."""
    f = SLUGS[pc]
    cl = _clips(f)
    clips, why = {}, {}
    for hst, (rx, w) in PICK.items():
        c = next((n for n in cl if re.match(rx, n)), None)
        if c:
            clips[hst] = [c]
            why[hst] = f"{c} ({cl[c][0]} frames, pelvis travel {cl[c][1]:.2f}): {w}"
    return f, clips, why


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import gag_stats
    st, hs = stats(), heights()
    tp = gag_stats.find_tparam(ROOT)
    if tp:
        head, _ = gag_stats.tparam(tp)
        assert all(gag_stats.squash(c) in head for c in MAP), [c for c in MAP if gag_stats.squash(c) not in head]
    # self-check of the help-text order: flags the text names must be the ones player.dat has
    for pc, s in st.items():
        for word, k, v in (("rough", "rough", "-1"), ("rain", "rain", "-1"), ("draw", "curve", "1"),
                           ("fade", "curve", "-1"), ("good in the bunkers", "bunker", "1"), ("approach", "approach", "-1")):
            assert word not in s["help"] or s[k] == v, (pc, word)
    for pc, s in st.items():
        v, vw = voices(pc)
        g, cl, _ = reactions(pc)
        print(f"pc{pc:02d} {s['name']:<14} {hs[pc][0]} {hs[pc][1]}cm pow {s['power']} con {s['control']} "
              f"imp {s['impact']} spin {s['spin']} side {s['side']} | {s['tier']} {s['type']} -> {style(pc)[0]}")
        print("      voices", {p: len(f) for p, f in sorted(v.items())}, vw.get("pitch", ""))
        print("      reactions", {k: c[0] for k, c in cl.items()})
    print("override check:", {c: o for c, o in list(gag_stats.overrides(st, tp, MAP, {p: style(p) for p in st})[9][0].items())} if tp else "no TParam")
