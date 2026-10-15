"""Which golf holes of Fore!, Open Tee 2 and Out of Bounds could hold a tennis court (opentennis M8f10).

`python3 tools/venues/venues.py [fore|opentee2|oob ...]` -> out/venues/<game>.json and a table per course: for every
hole its best spot (survey.py) from its height map and placements (course.py). Reads `out/files/<game>/` (extract.py).
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import course
import survey

ROOT = Path(__file__).resolve().parents[2]
FILES = ROOT / "out/files"
OUT = ROOT / "out/venues"
# what a placed object keeps clear, metres around its origin times its scale: trees and props by eye from the
# hole renders, structures are clubhouses, huts, bridges and stands
BLOCK = {"tree": 3.0, "prop": 2.0, "structure": 12.0, "billboard": 3.0}
CATEGORY = {17: "tree", 18: "prop", 19: "structure", 20: "billboard"}       # Fore! / Open Tee 2 (HST's numbering)


def fore():
    """(course, hole, hmp path, [(kind, x, z, scale)], big-endian) per hole; spring (SSN0), the ground is the same
    in every season."""
    for hmp in sorted((FILES / "fore/CRS/SSN0").glob("HOL*.XB/database/course*/hole/*_h??.HMP")):
        c, h = int(hmp.parts[-5][3:5]), int(hmp.parts[-5][5:7])
        dat = next(hmp.parents[3].glob("database/plant/plant_*_0.dat"), None)
        yield c, h, hmp, placed(dat, False), False


def opentee2():
    root = FILES / "opentee2/PSP_GAME/USRDIR/xbdata/crs"
    # crs/NN = courseNN; 01-06 and 13-18 are the twelve 18-hole courses (HMPs in hmpHH.xb), 07-12 nine-hole
    # versions of 01-06 and 19 a nine-hole course (HMPs in holHH.xb)
    for hmp in sorted(root.glob("*/h??[0-9][0-9].xb/data/course/course*/hole/*_h??.HMP")):
        c, h = int(hmp.parts[-7]), int(hmp.stem[-2:])
        dat = next(root.glob(f"{hmp.parts[-7]}/hol{h:02d}.xb/data/course/plant/plant_*_h{h:02d}_0.dat"), None)
        yield c, h, hmp, placed(dat, False), False


def oob():
    """The front nine's placements live in half_p10.xb, the back nine's in half_p01.xb, one file per kind."""
    root = FILES / "oob/PS3_GAME/USRDIR/xbdata/course"
    for hmp in sorted(root.glob("course*/hole??.xb/data/course/course*/hole/*_h??_*.HMP")):
        if hmp.stem.endswith("_g"):
            continue
        c, h = int(hmp.parts[-7][6:]), int(re.search(r"_h(\d\d)_", hmp.name)[1])
        objs = []
        for kind in BLOCK:
            for dat in root.glob(f"course{c:02d}/half_p*.xb/data/course/plant/course{c:02d}/{kind}/{kind}_c{c:02d}_h{h:02d}_0.dat"):
                d = dat.read_bytes()
                for o in range(0, len(d) - 0x3F, 0x40):
                    x, _, z = course.struct.unpack(">3f", d[o + 8:o + 20])
                    scale = course.struct.unpack(">f", d[o + 0x28:o + 0x2C])[0]
                    objs.append((kind, x, z, scale))
        yield c, h, hmp, objs, True


def placed(dat, big):
    if dat is None:
        return []
    return [(CATEGORY[p[0]], p[2], p[4], p[6]) for p in course.plants(dat.read_bytes(), big) if p[0] in CATEGORY]


GAMES = {"fore": fore, "opentee2": opentee2, "oob": oob}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for game in sys.argv[1:] or GAMES:
        res = []
        for c, h, hmp, objs, big in GAMES[game]():
            m = course.Hmp(hmp.read_bytes(), big)
            blockers = [(x, z, BLOCK[k] * min(max(abs(s), 1.0), 4.0)) for k, x, z, s in objs]
            best = survey.search(m, blockers)
            res.append({"course": c, "hole": h, "hmp": str(hmp.relative_to(ROOT)), "objects": len(objs),
                        "fits": sum(b["fits"] for b in best), "best": best[:3]})
            print(f"{game} c{c:02d} h{h:02d} {'FITS' if res[-1]['fits'] else '    '} {best[0] if best else '-'}", flush=True)
        (OUT / f"{game}.json").write_text(json.dumps(res, indent=1))
        per = defaultdict(list)
        for r in res:
            per[r["course"]].append(r)
        print(f"\n{game}: course, holes with a court spot / holes")
        for c, rs in sorted(per.items()):
            print(f"  {c:02d}  {sum(1 for r in rs if r['fits'])}/{len(rs)}")


if __name__ == "__main__":
    main()
