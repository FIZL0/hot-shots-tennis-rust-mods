"""Get a Grip's character.csv stats -> HST TParam.csv overrides (standard §6 `params.override`).

Each mapped TParam column takes its value by rank: a Get a Grip character's position among Get a Grip's 15 on the
source stat (ties share their average rank) picks the cell at the same position in HST's 14 rows of that column,
sorted. So the cast keeps Get a Grip's relative strengths but only ever gets values HST's own cast has (integer
columns stay integers, `a/b/c` cells are whole HST cells). Columns with no Get a Grip source stay the donor row's.
"""
import csv
import io
import os

# TParam column -> (Get a Grip source stats, averaged; why). The table in notes/getagrip.md mirrors this.
MAP = {
    "Serv POW": (["FlatservePower", "SpinservePower", "SliceservePower"], "serve power (mean of the three serves)"),
    "Strk POW": (["Power"], "overall (stroke) power"),
    "LOW POW": (["Power"], "low-ball stroke power (HST keeps it = Strk POW)"),
    "Voley POW": (["VolleyPower"], "volley power"),
    "V LOW POW": (["VolleyPower"], "low volley power (HST keeps it ≈ Voley POW)"),
    "Lob POW": (["LobPower"], "lob power"),
    "Lob POW2": (["LobPower"], "lob power (second lob)"),
    "Top SPIN": (["TopSpin"], "topspin"),
    "Slice SPIN": (["Spin"], "overall spin (Get a Grip's own slice spin is the same for everyone)"),
    "Drop SPIN": (["Spin"], "overall spin (Get a Grip's own drop spin is the same for everyone)"),
    "Strk CON": (["Technique"], "overall technique = stroke aim range"),
    "Voley CON": (["VolleyTechnique"], "volley technique"),
    "Serv CON": (["FlatserveTechnique", "SpinserveTechnique", "SliceserveTechnique"], "serve technique (mean)"),
    "ショット ウサギIMP GI/NI/BI": (["Impact"], "Impact = timing window (Usa/Kame = early/late, as HST's ウサギ/カメ)"),
    "ショット カメIMP GI/NI/BI": (["Impact"], "Impact = timing window, late side"),
    "SPE": (["Speed"], "run speed"),
    "STA": (["Stamina"], "stamina"),
    "Agili": (["Acceleration"], "acceleration"),
    "リーチ(cm)": (["Leach"], "reach"),
    "飛びつき（遠）開始": (["Leach"], "dive start (HST: 2 × reach)"),
    "飛びつき限界": (["Leach"], "dive limit (HST: 4 × reach)"),
}
# Playstyle 1/2/3 -> TParam タイプ. Read off the stats: 3 has the best volley technique and forward speed (net),
# 2 the worst volleys and backward speed with rising/air/lob specialists (baseline), 1 sits between (all-round).
STYLE = {"1": "オール", "2": "ベース", "3": "ネット"}


def squash(s):
    return " ".join(s.split())


def tparam(path):
    """HST's TParam.csv (cp932): headers (line breaks as spaces) and the 14 character rows."""
    rows = list(csv.reader(io.StringIO(open(path, "rb").read().decode("cp932"))))
    return [squash(h) for h in rows[0]], [r for r in rows[1:] if r and r[0].isdigit()]


def key(cell):
    return tuple(float(x) for x in cell.split("/"))


def ranks(values):
    """Average 0-based rank of each value (ties share it)."""
    order = sorted(values)
    return [(order.index(v) + len(order) - 1 - order[::-1].index(v)) / 2 for v in values]


def find_tparam(root):
    for p in [os.environ.get("HST_TPARAM", ""),
              os.path.join(root, "../HST-Remastered/context/xb/PCDATA/PCDATA.XB/data/taguchi/Data/TParam.csv")]:
        if p and os.path.isfile(p):
            return p
    return None


def overrides(stats, path):
    """{pc: (override dict, why dict)} for Get a Grip's characters `stats` ({pc: character.csv row})."""
    head, rows = tparam(path)
    pcs = sorted(stats)
    out = {n: ({}, {}) for n in pcs}
    for col, (src, why) in MAP.items():
        c = head.index(squash(col))
        hst = sorted((r[c] for r in rows), key=key)
        vals = [sum(float(stats[n][s]) for s in src) / len(src) for n in pcs]
        for n, v, r in zip(pcs, vals, ranks(vals)):
            cell = hst[round(r / (len(pcs) - 1) * (len(hst) - 1))]
            o, w = out[n]
            o[col] = int(cell) if cell.isdigit() else cell
            w[col] = f"{why}: {'+'.join(src)} {v:g}, rank {r + 1:g} of {len(pcs)} -> {cell}"
    for n in pcs:
        o, w = out[n]
        p = stats[n].get("Playstyle")
        if p in STYLE:
            o["タイプ"] = STYLE[p]
            w["タイプ"] = f"Playstyle {p} -> {STYLE[p]}"
    return out


def ai_row(style, sex, height, chars):
    """The HST character whose AI row plays `style`: same type, same sex if one has it, nearest Bip01 height."""
    pool = [c for c in chars if c["type"] == style]
    pool = [c for c in pool if c["sex"] == sex] or pool
    return min(pool, key=lambda c: abs(c["bip01_height"] - height)) if pool else None


def hst_types(path):
    head, rows = tparam(path)
    return {int(r[0]): r[head.index("タイプ")] for r in rows}
