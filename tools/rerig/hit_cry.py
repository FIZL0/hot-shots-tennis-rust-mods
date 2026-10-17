"""Add HST voice program 5 (the cry of a player the ball hits) to packaged character mods, in place.

python3 tools/rerig/hit_cry.py MOD_DIR…     (e.g. out/mods/*_pc*)

For mods packaged before package.py filled program 5 (opentennis B560): voice/5_0.wav from the same source a fresh
package.py run takes (Get a Grip: its own `body` cue; Out of Bounds / Open Tee 2: the data module's HIT pick; Fore!
has no pained take, so nothing), voice_counts/voice_why updated, and the mod.json `version` bumped (absent = 1) so
the store offers the update. A mod that already has the same 5_0.wav is left alone.
"""
import filecmp
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import package  # noqa: E402


def source(game, n):
    """(wav, why) for program 5, or None."""
    if game == "getagrip":
        f = sorted(glob.glob(os.path.join(package.ROOT, f"out/voices/getagrip/pc{n:02d}/sgv_pc{n:02d}a_pc_voice_body*.wav")))
        return (f[0], None) if f else None
    D = package.data(game)
    if D is None:
        return None
    prog, why = D["voices"](n)
    return (prog[5][0], why.get(5)) if prog.get(5) else None


def bump(v):
    """'2' -> '3', '1.4' -> '1.5', None -> '2'."""
    parts = str(v or "1").split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def main(dirs):
    for d in dirs:
        mf = os.path.join(d, "mod.json")
        if not os.path.exists(mf):
            continue
        m = json.load(open(mf))
        g = re.match(r"(getagrip|oob|opentee2|fore)_pc(\d\d)", m.get("id", ""))
        if not g:
            continue
        src = source(g.group(1), int(g.group(2)))
        if not src:
            print(m["id"], "no hit cry")
            continue
        wav, why = src
        dst = os.path.join(d, m.get("voice") or "voice/", "5_0.wav")
        if os.path.exists(dst) and filecmp.cmp(dst, wav, shallow=False):
            print(m["id"], "already has it")
            continue
        package.link(os.path.realpath(wav), dst)
        for k, v in (("voice_counts", 1), ("voice_why", why)):
            if v is not None:
                m[k] = dict(sorted({**m.get(k, {}), "5": v}.items(), key=lambda kv: int(kv[0])))
        m["version"] = bump(m.get("version"))
        json.dump(m, open(mf, "w"), indent=1, ensure_ascii=False)
        print(m["id"], "->", os.path.relpath(wav, package.ROOT), "version", m["version"])


if __name__ == "__main__":
    main(sys.argv[1:])
