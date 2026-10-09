"""Hot Shots Golf Fore! (PS2, SCUS-97401) character data for HST mods (notes/fore.md "Mod data").
Everything is read at run time from extracted/fore and out/ (never committed).

stats(), MAP, style(pc), heights(), voices(pc), reactions(pc) as package.py / gag_stats.py / sizing.py expect.
`python3 tools/rerig/fore_data.py` prints the whole cast.
"""
import glob
import json
import os
import re
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SYSTEM = "extracted/fore/ZZBIN/SYSTEM.BIN"
BASE = 0x22CC80      # SYSTEM.BIN load address (its own jal targets land on its function starts; the pointer list checks it)
NAMES = 0xFDE40      # 24 × 0x40 character records: body type, unlock, name[16] @2, 3-letter voice code @0x12
PTRS = 0x136430      # 24 pointers to those records (GAME.BIN's player struct keeps one)
STATS = 0x136490     # 24 × 0x20 stat records: 5 floats, then signed bytes (club / ball tables use the same 5 floats)
SLUG = ["phoebe", "mike", "emma", "sam", "misaki", "brad", "chaos", "regis", "maya", "falcon", "renee", "z", "mel",
        "allan", "tiffany", "kamala", "toni", "tbone", "lin", "louise", "zeus", "hubert", "ratchet", "jak"]


def _p(*a):
    return os.path.join(ROOT, *a)


def _sys():
    b = open(_p(SYSTEM), "rb").read()
    for i in range(24):
        assert struct.unpack_from("<I", b, PTRS + 4 * i)[0] == BASE + NAMES + 0x40 * i, "not SCUS-97401's SYSTEM.BIN"
    return b


def roster():
    """{pc: (name, voice code, body type)} from SYSTEM.BIN's character records."""
    b = _sys()
    out = {}
    for i in range(24):
        r = b[NAMES + 0x40 * i:NAMES + 0x40 * (i + 1)]
        out[i] = (r[2:18].split(b"\0")[0].decode(), r[0x12:0x15].decode().lower(), r[0])
    return out


def raw():
    """{pc: (5 floats, 12 signed bytes)} as stored."""
    b = _sys()
    return {i: (struct.unpack_from("<5f", b, STATS + 0x20 * i), struct.unpack_from("<12b", b, STATS + 0x20 * i + 20))
            for i in range(24)}


def stats():
    """{pc: {stat: str}}. Floats 0-3 of the stat record, by position (1.0 = average):
    Power  = float 0, the shot-power multiplier (code: driver power = it + club + ball; Z/Jak 1.17 top, Emma/Regis 0.98).
    Control = 2 - float 1, INVERTED: float 1 is lower-is-better (every club/ball that raises it gives power or
             spin, every one that lowers it costs impact or float 4: a penalty, i.e. dispersion).
    Impact = float 2, impact-zone size (beginners Emma/Regis 1.25, experts Z/Jak 0.75; capped in code; every
             upgraded club costs 0.07-0.15 of it, as forgiveness traded for performance).
    Spin   = float 3 (spin clubs/balls raise it).
    Float 4 (0.6-1.2, 1.0 for most) and the bytes (three -1/0/+1 flags, one 8-15 value) are not identified."""
    return {pc: {"Power": f"{f[0]:.2f}", "Control": f"{2 - f[1]:.2f}", "Impact": f"{f[2]:.2f}", "Spin": f"{f[3]:.2f}",
                 "Float4": f"{f[4]:.2f}"} for pc, (f, _) in raw().items()}


_POW = "Power (Fore's shot-power multiplier, SYSTEM.BIN stat float 0): longer hitter, harder strokes"
_IMP = "Impact (Fore's impact-zone size, stat float 2; beginners biggest): a forgiving sweet spot, as HST's timing windows"
MAP = {c: (["Power"], _POW) for c in ("Serv POW", "Strk POW", "LOW POW", "Voley POW", "V LOW POW", "Lob POW")}
MAP.update({c: (["Control"], "Control (2 − stat float 1, which is lower-is-better dispersion): straighter strokes")
            for c in ("Strk CON", "Voley CON", "Serv CON")})
MAP.update({c: (["Impact"], _IMP) for c in ("ショット ウサギIMP GI/NI/BI", "ショット カメIMP GI/NI/BI")})
MAP.update({c: (["Spin"], "Spin (Fore's spin, stat float 3)") for c in ("Top SPIN", "Slice SPIN", "Drop SPIN")})


def style(pc):
    return None, ("no play style in the data: Fore's stat record has -1/0/+1 flags (likely shot curve/trajectory, "
                  "unconfirmed) that do not describe a tennis style")


# Body types 0 and 3 are shared templates (0: six women with skirt/hair bones; 3: Sam, Maya, Falcon, Allan, Toni,
# Zeus, Jak). The others are one-off bodies; sex for those is from the roster, not the data.
_SEX_ONE_OFF = {1: "m", 2: "f", 5: "m", 6: "m", 7: "m", 10: "f", 11: "m", 12: "f", 17: "m", 21: "m", 22: "m"}


def heights():
    """{pc: (sex, None, why)}: Fore has no heights in its data (the character record holds only body type, name, voice
    code and flags), so each keeps its own model height."""
    out = {}
    for pc, (name, _, body) in roster().items():
        if body in (0, 3):
            sx, how = ("f" if body == 0 else "m"), f"body template t{body:02d} (shared, {'women' if body == 0 else 'men'})"
        else:
            sx, how = _SEX_ONE_OFF[pc], f"one-off body t{body:02d}; sex from the roster, not the data"
        out[pc] = (sx, None, f"Fore's SYSTEM.BIN character record has no height or sex; {how}")
    return out


# ---- voices ---------------------------------------------------------------------------------------------------

def _guts(pc, code):
    """{celebration: bank number} from the costume-0 celebration archives PCNN00SS.XB, each holding one ga_ motion
    and the g_<code>K voice bank played with it (GAME.BIN 'GUTSVOICE')."""
    out = {}
    for x in sorted(glob.glob(_p(f"out/files/fore/PC/PC{pc:02d}/PC{pc:02d}00[0-9][0-9].XB"))):
        ga = [os.path.basename(f) for f in glob.glob(f"{x}/**/ga_*.ani", recursive=True)]
        g = [re.match(rf"g_{code}(\d+)\.hd", os.path.basename(f)) for f in glob.glob(f"{x}/**/g_*.hd", recursive=True)]
        if len(ga) == 1 and len(g) == 1 and g[0]:
            out[ga[0][8:-4]] = int(g[0].group(1))  # 'ea_r00' -> 5
    return out


def _wav(pc, bank):
    return sorted(glob.glob(_p(f"out/voices/fore/pc{pc:02d}/{bank}_[0-9][0-9][0-9].wav")))


def voices(pc):
    """({program: [wav]}, {program: why}). Labelled by the data, not by listening:
    g_<code>K: one per hole-result celebration, paired in its archive (bogey 1, par 2, birdie 3/4, eagle 5/6).
    jy_<code>0-4: loaded with the five shot reactions re_ga/os/bw/lp/tp in that archive order; their face morphs
    say ga/os/bw are upset (anger/sorrow) and lp/tp happy (smile/joy). The jy<->reaction pairing is by order only.
    jy5/6 (JY_<code>.XB): one of the two at random after a wait (code: elapsed time >= a threshold) — not used.
    ya/co/sc/vs: named next to BOOING/GALLERY in GAME.BIN's sound list (ya = 野次 heckles, co, sc = 24 per-opponent,
    vs = versus) — no tennis meaning, not used."""
    code = roster()[pc][1]
    gut = _guts(pc, code)
    g = lambda *k: [w for c in k if c in gut for w in _wav(pc, f"g_{code}{gut[c]}")]
    jy = lambda *k: [w for i in k for w in _wav(pc, f"jy_{code}{i}")]
    prog = {0: jy(4, 3), 1: jy(4, 3), 2: jy(0, 1, 2), 3: jy(4, 3), 4: jy(0, 1),
            7: g("bi_r00", "bi_r01", "pa_r00"), 8: g("bo_r00"), 9: g("ea_r00", "ea_r01", "bi_r00"), 10: g("bo_r00")}
    why = {0: "jy4/jy3, the voices loaded with the happy tp/lp shot reactions (heuristic: Fore has no effort shout)",
           1: "jy4/jy3, the happy post-shot exclamations (heuristic)",
           2: "jy0/1/2, loaded with the upset ga (がっかり)/os (惜しい)/bw reactions: bad-shot groans",
           3: "same as program 0 (heuristic: no dive in golf)",
           4: "jy0/1, the ga/os groans (heuristic: no whiff voice)",
           6: "none: golf has no partner calls (sc/vs are per-opponent versus lines)",
           7: "g banks of the birdie (r00, r01) and par celebrations",
           8: "g bank of the bogey celebration (Fore's only losing line)",
           9: "g banks of the eagle (r00, r01) and birdie celebrations",
           10: "g bank of the bogey celebration (same line as program 8)"}
    prog = {k: v for k, v in prog.items() if v}
    return prog, {k: w for k, w in why.items() if k in prog or k == 6}


# ---- reactions ------------------------------------------------------------------------------------------------

def _anim_names(f):
    b = open(f, "rb").read()
    n, = struct.unpack_from("<I", b, 12)
    return {a["name"] for a in json.loads(b[20:20 + n])["animations"]}


def reactions(pc):
    """(glb, {hst: [intro]}, {hst: why}). Fore clips run at 60 Hz as exported; package.py retimes to the donor's.
    No loops: Fore's clips end in a still pose. Root translation measured on Bip01 (start -> end, ground plane)."""
    n = f"{pc:02d}"
    f = _p(f"out/anims/fore/pc{n}_{SLUG[pc]}_c00-03.glb")
    if not os.path.exists(f):
        return f, {}, {}
    a = _anim_names(f)
    pick = lambda *c: next((x for x in c if x in a), None)
    choice = {"re_gu": (pick(f"re_pc{n}_tp", f"re_pc{n}_lp"), "the happy short shot reaction (tp, else lp; smile/joy face, "
                                                             "0.5-1.2 s, root moves ≤ 0.4 m)"),
              "re_di": (pick(f"re_pc{n}_ga", f"re_pc{n}_os"), "re_ga (がっかり, sorrow/anger face, 1.1-1.5 s, root ≤ 0.2 m)"),
              "re_gu_set": (pick(f"win_{n}", f"ga_pc{n}_ea_r00"), "win, the results screen's winner (4.0 s, no root motion)"),
              "re_di_set": (pick(f"lost_{n}", f"ga_pc{n}_bo_r00"), "lost, the results screen's loser (3.0 s, root drifts "
                                                                   "≤ 0.6 m: package.py pins it)")}
    return f, {k: [c] for k, (c, _) in choice.items() if c}, {k: w for k, (c, w) in choice.items() if c}


if __name__ == "__main__":
    st, hs, ro = stats(), heights(), roster()
    assert [ro[i][0] for i in (0, 11, 22, 23)] == ["Phoebe", "Z", "Ratchet", "Jak"]
    assert all(set(MAP[c][0]) <= set(st[0]) for c in MAP)
    print("pc name     sex  " + " ".join(f"{k:>7}" for k in st[0]) + "  voices{prog:n}  reactions")
    for pc in range(24):
        prog, _ = voices(pc)
        _, cl, _ = reactions(pc)
        print(f"{pc:02d} {ro[pc][0]:8} {hs[pc][0]}    " + " ".join(f"{v:>7}" for v in st[pc].values()),
              "{" + ", ".join(f"{k}:{len(v)}" for k, v in sorted(prog.items())) + "}",
              {k: v[0] for k, v in cl.items()})
