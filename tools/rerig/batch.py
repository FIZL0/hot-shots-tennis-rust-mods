"""Rerig every exported character model onto the HST standard and check each.

python3 tools/rerig/batch.py [game…]     (games: fore oob getagrip opentee opentee2; default all)

out/models/<game>/<char>/*.glb -> out/rerig/<game>/<char>/*.glb, and out/rerig/<game>/check.txt.
Parts folders (`parts`, `_face_check`) are skipped. Games `sizing.py` knows (Get a Grip) are rerigged twice: plain,
to measure, then sized to HST's cast (whole-body height, per-character head factor); out/rerig/<game>/sizing.json says how.
"""
import glob
import io
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import check  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import rerig  # noqa: E402
import sizing  # noqa: E402

GAMES = ["fore", "oob", "getagrip", "opentee", "opentee2"]


def one(src, height=None, head=1.0):
    rel = os.path.relpath(src, os.path.join(ROOT, "out/models"))
    dst = os.path.join(ROOT, "out/rerig", rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    buf = io.StringIO()
    try:
        o = rerig.rerig(src, dst, height=height, head=head)
        with redirect_stdout(buf):
            good = check.check(dst)
        warn = [line[5:] for line in buf.getvalue().splitlines() if not line.startswith("OK")]
        return rel, "PASS" if good else "FAIL", f"synth {len(o.g['extras']['synthesized'])}; " + "; ".join(warn)
    except Exception as e:  # keep going; the log says which
        return rel, "ERROR", repr(e)[:300]


def main():
    games = sys.argv[1:] or GAMES
    for game in games:
        files = sorted(f for f in glob.glob(os.path.join(ROOT, f"out/models/{game}/*/*.glb"))
                       if os.path.basename(os.path.dirname(f)) not in ("parts", "_face_check"))
        with ProcessPoolExecutor() as ex:
            rows = list(ex.map(one, files))
        pcs = {}
        for f in files:
            pcs.setdefault(int(re.match(r"pc(\d+)", os.path.basename(os.path.dirname(f))).group(1)), []).append(
                os.path.join(ROOT, "out/rerig", os.path.relpath(f, os.path.join(ROOT, "out/models"))))
        p = sizing.plan(game, pcs)
        if p:
            sizes, heads, info = p
            pc = [int(re.match(r"pc(\d+)", os.path.basename(os.path.dirname(f))).group(1)) for f in files]
            with ProcessPoolExecutor() as ex:
                rows = list(ex.map(one, files, [sizes[n][0] for n in pc], [heads[n][0] for n in pc]))
            json.dump(dict(info, characters={f"pc{n:02d}": {"bip01_height": round(h, 4), "why": w, "head_factor": round(heads[n][0], 4), "head_why": heads[n][1]}
                                             for n, (h, w) in sorted(sizes.items())}),
                      open(os.path.join(ROOT, f"out/rerig/{game}/sizing.json"), "w"), indent=1, ensure_ascii=False)
        log = os.path.join(ROOT, f"out/rerig/{game}/check.txt")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "w") as f:
            for r in rows:
                f.write(" | ".join(r) + "\n")
        n = {k: sum(r[1] == k for r in rows) for k in ("PASS", "FAIL", "ERROR")}
        print(game, len(rows), n, log)


if __name__ == "__main__":
    main()
