"""Rerig every exported character model onto the HST standard and check each.

python3 tools/rerig/batch.py [game…]     (games: fore oob getagrip opentee opentee2; default all)

out/models/<game>/<char>/*.glb -> out/rerig/<game>/<char>/*.glb, and out/rerig/<game>/check.txt.
Parts folders (`parts`, `_face_check`) are skipped.
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
import rerig  # noqa: E402

GAMES = ["fore", "oob", "getagrip", "opentee", "opentee2"]


def one(src):
    rel = os.path.relpath(src, os.path.join(ROOT, "out/models"))
    dst = os.path.join(ROOT, "out/rerig", rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    buf = io.StringIO()
    try:
        o = rerig.rerig(src, dst)
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
        log = os.path.join(ROOT, f"out/rerig/{game}/check.txt")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "w") as f:
            for r in rows:
                f.write(" | ".join(r) + "\n")
        n = {k: sum(r[1] == k for r in rows) for k in ("PASS", "FAIL", "ERROR")}
        print(game, len(rows), n, log)


if __name__ == "__main__":
    main()
