"""Get a Grip's court loading pictures -> each court mod's `previews/loading.png` (standard/
HST-COURT-UMPIRE-STANDARD.md §2: any size, drawn to cover the loading screen, cropped not stretched; opentennis
tasks M117, M119).

    python3 tools/psp2gltf/export_getagrip_court_loading.py [01 04 ...]

Get a Grip's own art of each court is its loading panel, `menu/loadmes/court/loadmes_cNN.xb0/data/menu/loadmes/
CNN.gim`: a 480x272 full-screen picture with nothing drawn on it (the court name comes from loadmes_courtname, a
separate layout). xb0 is English; the French and Spanish copies (xb2/xb3) are the same pixels, the Japanese one (xb)
carries the game's logo on some courts. Written at its own size as an opaque RGB PNG: the game scales it up to cover
the window (HST's own court pictures are 640x448). Run after `export_getagrip_courts.py` (the mod folders).
Game data: out/ only.
"""
import glob
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import gim  # noqa: E402
from export_getagrip_courts import COURTS  # noqa: E402

LOADMES = os.path.join(ROOT, "out/files/getagrip/PSP_GAME/USRDIR/xbdata/menu/loadmes/court")


def panel(n):
    """Court n's English loading panel as an RGB image."""
    path = os.path.join(LOADMES, f"loadmes_c{n:02d}.xb0/data/menu/loadmes/C{n:02d}.gim")
    return Image.fromarray(gim.decode(open(path, "rb").read()), "RGBA").convert("RGB")


def main():
    for n in [int(a) for a in sys.argv[1:]] or COURTS:
        mods = glob.glob(os.path.join(ROOT, f"out/mods/gag_c{n:02d}_*/mod.json"))
        if not mods:
            print(f"skip c{n:02d}: no out/mods/gag_c{n:02d}_*/mod.json (run export_getagrip_courts.py)")
            continue
        mod = os.path.dirname(mods[0])
        os.makedirs(os.path.join(mod, "previews"), exist_ok=True)
        dst = os.path.join(mod, "previews", "loading.png")
        panel(n).save(dst, optimize=True)
        print(dst)


if __name__ == "__main__":
    main()
