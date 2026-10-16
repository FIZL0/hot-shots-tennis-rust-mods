#!/usr/bin/env python3
"""Make a texture pack (standard/HST-TEXTURE-PACK-STANDARD.md) from a folder of edited or upscaled PNGs.

    python3 tools/texpack.py EDITED/ out/mods/<id> --name "Crimson Courts" [--id crimson_courts] [--author you]
        [--src ../opentennis/mods/textures-src] [--covers auto|everything|courts|characters|menus|mixed]
        [--look auto|upscale|recolour|new] [--version 1] [--zip]

EDITED/ holds files named like the game's `--dump-textures` output (`<name>-<key>.png`, any folders, flat is fine).
Every key-named PNG is copied to `<out>/textures/` under its path in EDITED/; `mod.json` is written beside it.

`--src` is the dump the edits came from (`hst <iso> --dump-textures` → `mods/textures-src/`). With it, files that
are byte-identical to the disc texture are left out, and `--covers auto` / `--look auto` (the default) are worked out
from what the pack replaces:
- covers: which part of the dump the keys come from (COURT/COURTSET = courts, PC = characters, MENU and the
  HUD/result folders = menus; ball, effects and the rest count as "other"). One part → that part; courts, characters
  and menus all → everything; anything else → mixed.
- look: every replacement an integer multiple (≥2) of its original's size → upscale. Otherwise auto writes nothing:
  pass `--look recolour` or `--look new` yourself.
Without `--src`, auto covers uses EDITED/'s own folders the same way, and auto look writes nothing.
`covers` and `look` are optional in mod.json; they only drive the store's Browse filters.
"""
import argparse, json, re, shutil, struct, sys, zipfile
from pathlib import Path

COVERS = ["everything", "courts", "characters", "menus", "mixed"]  # = opentennis mods_textures::COVERS
LOOKS = ["upscale", "recolour", "new"]                               # = opentennis mods_textures::LOOKS
KEY = re.compile(r"-([0-9a-f]{16})\.png$", re.I)
ID = re.compile(r"^[a-z0-9_]+$")

# dump folder (first one or two parts of the path) -> what it covers
PARTS = {"COURT": "courts", "COURTSET": "courts", "PC": "characters", "MENU": "menus",
         "AZUMA/INPANE": "menus", "AZUMA/PRIZE": "menus", "SAITOU": "menus"}


def part(rel):
    p = Path(rel).parts
    for k in ("/".join(p[:2]), p[0] if p else ""):
        if k in PARTS:
            return PARTS[k]
    return "other"


def png_size(f):
    with open(f, "rb") as h:
        b = h.read(24)
    if b[:8] != b"\x89PNG\r\n\x1a\n" or b[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", b[16:24])


def keyed(root):
    """key -> path of the first key-named PNG under root, in path order (the game's rule)."""
    out = {}
    for f in sorted(p for p in root.rglob("*") if p.is_file()):
        m = KEY.search(f.name)
        if m and m.group(1).lower() not in out:
            out[m.group(1).lower()] = f
    return out


def guess_covers(parts):
    s = set(parts)
    if len(s) == 1 and "other" not in s:
        return s.pop()
    if {"courts", "characters", "menus"} <= s:
        return "everything"
    return "mixed"


def guess_look(pairs):
    for new, old in pairs:
        a, b = png_size(new), png_size(old)
        if not a or not b or a[0] % b[0] or a[1] % b[1] or a[0] // b[0] != a[1] // b[1] or a[0] // b[0] < 2:
            return None
    return "upscale" if pairs else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edited", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--id", help="default: the out folder's name")
    ap.add_argument("--author")
    ap.add_argument("--version")
    ap.add_argument("--src", type=Path, help="the --dump-textures folder the edits came from")
    ap.add_argument("--covers", default="auto", choices=["auto", "none"] + COVERS)
    ap.add_argument("--look", default="auto", choices=["auto", "none"] + LOOKS)
    ap.add_argument("--zip", action="store_true", help="also write <out>.zip for Add mod / the store")
    a = ap.parse_args()

    pid = a.id or a.out.name
    if not ID.match(pid) or len(pid) > 64:
        sys.exit(f"id {pid!r}: use 1-64 of a-z, 0-9, _")
    for k, v in (("name", a.name), ("author", a.author)):
        if v is not None and not 1 <= len(v) <= 64:
            sys.exit(f"{k} must be 1-64 characters")
    if a.out.resolve() == a.edited.resolve() or a.edited.resolve() in a.out.resolve().parents:
        sys.exit("out must not be inside the edited folder")

    edited = keyed(a.edited)
    src = keyed(a.src) if a.src else {}
    if a.src and not src:
        sys.exit(f"{a.src}: no key-named PNGs (run hst <iso> --dump-textures)")
    keep, same, unknown = {}, 0, 0
    for k, f in edited.items():
        o = src.get(k)
        if o is not None and o.read_bytes() == f.read_bytes():
            same += 1
            continue
        if a.src and o is None:
            unknown += 1
        keep[k] = f
    if not keep:
        sys.exit(f"{a.edited}: no changed key-named PNGs (a pack needs at least one)")

    covers = a.covers
    if covers == "auto":
        covers = guess_covers(part(src[k].relative_to(a.src) if k in src else f.relative_to(a.edited))
                              for k, f in keep.items())
    look = a.look
    if look == "auto":
        look = guess_look([(f, src[k]) for k, f in keep.items() if k in src]) if src and not unknown else None

    tex = a.out / "textures"
    if tex.exists():
        shutil.rmtree(tex)
    for k, f in keep.items():
        d = tex / f.relative_to(a.edited)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, d)
    man = {"standard": 1, "kind": "textures", "id": pid, "name": a.name}
    if a.author:
        man["author"] = a.author
    if a.version:
        man["version"] = a.version
    if covers not in (None, "none"):
        man["covers"] = covers
    if look not in (None, "none"):
        man["look"] = look
    (a.out / "mod.json").write_text(json.dumps(man, indent=2) + "\n")

    print(f"{a.out}: {len(keep)} textures, covers {man.get('covers', '-')}, look {man.get('look', '-')}"
          + (f" ({same} unchanged left out)" if same else "")
          + (f"; {unknown} keys not in {a.src}: check they come from this disc" if unknown else ""))
    if a.zip:
        z = a.out.with_suffix(".zip")
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(p for p in a.out.rglob("*") if p.is_file()):
                zf.write(f, Path(pid) / f.relative_to(a.out))
        print(f"wrote {z}")


if __name__ == "__main__":
    main()
