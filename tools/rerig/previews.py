#!/usr/bin/env python3
"""Ship HST's pre-rendered select previews inside the mods (standard §1 `previews/`).

    python3 tools/rerig/previews.py HST_CACHE [MODS_DIR]

HST_CACHE is the game's `cache/previews/<boot file>-r<N>/` after `HST_MENU=chars HST_BAKE=all hst <iso>` has drawn every
mod costume (`m-<mod folder>-<stamp>-<costume>.png`); MODS_DIR defaults to out/mods. Each mod gets the newest bake of
each costume as `previews/<costume glb stem>.png`."""
import json, os, shutil, sys

cache = sys.argv[1]
mods = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), "../../out/mods")
best = {}  # (mod folder, costume) -> (stamp, file)
for f in os.listdir(cache):
    if f.startswith("m-") and f.endswith(".png"):
        name, stamp, k = f[2:-4].rsplit("-", 2)
        key = (name, int(k))
        if int(stamp, 16) >= best.get(key, (-1,))[0]:
            best[key] = (int(stamp, 16), f)
n = 0
for (name, k), (_, f) in best.items():
    mod = os.path.join(mods, name)
    if not os.path.isfile(os.path.join(mod, "mod.json")):
        continue
    costumes = json.load(open(os.path.join(mod, "mod.json")))["costumes"]
    if k < len(costumes):
        os.makedirs(os.path.join(mod, "previews"), exist_ok=True)
        shutil.copyfile(os.path.join(cache, f), os.path.join(mod, "previews", os.path.splitext(os.path.basename(costumes[k]))[0] + ".png"))
        n += 1
print(f"{n} previews copied")
