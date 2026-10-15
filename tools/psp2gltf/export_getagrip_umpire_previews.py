"""Get a Grip's eight chair umpires' select pictures -> each umpire mod's `previews/umpire.png` (standard/
HST-COURT-UMPIRE-STANDARD.md §3: 384x480 RGBA, transparent background; HST-Remastered task B400).

    python3 tools/psp2gltf/export_getagrip_umpire_previews.py

Get a Grip's own art of each umpire seated in their chair is on their loading panel, `menu/loadmes/judge/
loadmes_jNN.xb0/data/menu/loadmes/JNN.gim` (480x272; xb0 is English, the one with Helghast as u_04: the shop's
`r_judgechip.gim` cut-outs still show the Japanese Yakkun there). The panel also carries a gold band, the name and a
text box, so the umpire is cut out of it:
  - the band is what at least 4 of the 8 panels agree on, pixel for pixel (the umpires, all different, never do);
  - the name is what differs between the English, French and Spanish panels (xb0/xb2/xb3) in the name strip;
  - the name strip's see-through stripes run on behind the umpire, so only opaque pixels there are kept;
  - the text box (x >= 275) is dropped; specks are opened away and holes in the umpire filled.
The cut-out is fitted into 384x480 (the margins of HST's own previews), feet on the foot. Run after
`tools/rerig/gag_umpires.py` (the mod folders). Game data: out/ only.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import gim  # noqa: E402
from export_getagrip_umpires import UMPIRES  # noqa: E402

JUDGE = os.path.join(ROOT, "out/files/getagrip/PSP_GAME/USRDIR/xbdata/menu/loadmes/judge")
W, H = 384, 480
# the name strip's rows and the text box's left edge on the 480x272 panel
STRIP = slice(145, 245)
NAME = (slice(150, 240), slice(0, 260))
TEXT_X = 275


def panel(n, lang):
    """Umpire n's loading panel, language variant `lang` (0 English, 2 French, 3 Spanish), as int16 RGBA."""
    path = os.path.join(JUDGE, f"loadmes_j{n:02d}.xb{lang}/data/menu/loadmes/J{n:02d}.gim")
    return gim.decode(open(path, "rb").read()).astype(np.int16)


def cut(e, fr, es, band, isband):
    """The umpire's mask on English panel `e`."""
    name = np.zeros(e.shape[:2], bool)
    name[NAME] = True
    text = ((np.abs(e - fr).max(-1) > 40) | (np.abs(e - es).max(-1) > 40)) & name
    fig = (e[..., 3] > 0) & ((np.abs(e - band).max(-1) > 40) | ~isband) & ~text
    fig[:, TEXT_X:] = False
    fig[STRIP] &= e[STRIP][..., 3] >= 200
    lab, n = ndimage.label(ndimage.binary_opening(fig, iterations=1))
    sizes = ndimage.sum(fig, lab, range(1, n + 1))
    keep = np.isin(lab, 1 + np.flatnonzero(sizes > 0.05 * sizes.max()))
    keep = ndimage.binary_fill_holes(ndimage.binary_closing(keep, iterations=2)) & (e[..., 3] > 0)
    keep[STRIP] &= e[STRIP][..., 3] >= 200
    return keep


def fit(rgba):
    """The cut-out's box scaled into W x H (8% margin at the sides and top, 4% under the feet), centred."""
    img = Image.fromarray(rgba, "RGBA")
    x0, y0, x1, y1 = img.getbbox()
    img = img.crop((x0, y0, x1, y1))
    s = min(W * 0.84 / img.width, H * 0.88 / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(img, ((W - img.width) // 2, round(H * 0.96) - img.height))
    return out


def main():
    ns = sorted(UMPIRES)
    en = {n: panel(n, 0) for n in ns}
    E = np.stack([en[n] for n in ns])
    # the band: per pixel, the value the most panels share (within 30), where at least 4 do
    agree = np.stack([(np.abs(E - E[j]).max(-1) < 30).sum(0) for j in range(len(ns))])
    band = np.take_along_axis(E, agree.argmax(0)[None, ..., None], 0)[0]
    isband = agree.max(0) >= 4
    for n in ns:
        e = en[n]
        keep = cut(e, panel(n, 2), panel(n, 3), band, isband)
        rgba = e.astype(np.uint8).copy()
        rgba[..., 3] = np.where(keep, rgba[..., 3], 0)
        rgba[..., :3] = np.where(keep[..., None], rgba[..., :3], 0)
        mod = os.path.join(ROOT, f"out/mods/gag_ump{n:02d}_{UMPIRES[n][0]}")
        if not os.path.isfile(os.path.join(mod, "mod.json")):
            print(f"skip u_{n:02d}: no {mod}/mod.json (run tools/rerig/gag_umpires.py)")
            continue
        os.makedirs(os.path.join(mod, "previews"), exist_ok=True)
        dst = os.path.join(mod, "previews", "umpire.png")
        fit(rgba).save(dst)
        print(dst)


if __name__ == "__main__":
    main()
