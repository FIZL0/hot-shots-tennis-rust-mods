"""Shared export logic for Hot Shots Golf: Open Tee 1 and 2 (PSP); both use the same "kuwabara" data layout.
Per-game settings live in export_opentee.py / export_opentee2.py. See notes/opentee.md.
"""
import collections
import csv
import glob
import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build  # noqa: E402
import gim  # noqa: E402
import i3m  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PART_KINDS = ("body", "head", "face", "etc")
# archives whose 2-digit number is the owning character (pcNN)
PC_ARCHIVE = re.compile(r"/(?:motion|r_mot|aface|face|mot|itemget)(\d\d)(?:_y)?\.xb1?/")


def read_csv(path):
    return list(csv.reader(io.StringIO(open(path, "rb").read().decode("shift_jis", "replace"))))


def text_table(path):
    """kuwabara/text/*.bin: u32 offsets, then CR-terminated strings (Shift-JIS)."""
    d = open(path, "rb").read()
    n = int.from_bytes(d[:4], "little") // 4
    offs = [int.from_bytes(d[4 * i: 4 * i + 4], "little") for i in range(n)]
    return [d[o: d.index(b"\r", o)].decode("shift_jis", "replace").strip() for o in offs]


class Game:
    """name: output folder; xb: xbdata dir; sep: attachment separator; keep: bone-name regex (build.build).
    Rosters (per game script) are lists of dicts with index, slug, skin_tone, sets [(label, head, body)]."""

    def __init__(self, name, xb, sep, keep):
        self.name, self.xb, self.sep, self.keep = name, xb, sep, keep
        self.pc = os.path.join(xb, "kuwa/pc")
        self.out_m = os.path.join(ROOT, "out/models", name)
        self.out_a = os.path.join(ROOT, "out/anims", name)
        self.out_t = os.path.join(ROOT, "out/textures", name)

    def bargs(self):
        return dict(sep=self.sep, keep=self.keep)

    def model_path(self, kind, stem):
        """stem e.g. 'body65' or 'body65_y'."""
        num = re.match(r"[a-z]+(\d+)", stem).group(1)
        g = glob.glob(os.path.join(self.pc, f"{kind}/{stem}.xb/data/kuwabara/pc/{kind}/{num}/{stem}.psp.i3r"))
        return g[0] if g else None

    def ref_skeleton(self):
        return self.model_path("body", "body00")

    # ---- textures --------------------------------------------------------------------------------
    def do_textures(self):
        n = 0
        seen = set()
        for kind in PART_KINDS:
            for p in sorted(glob.glob(os.path.join(self.pc, f"{kind}/*.xb/data/kuwabara/pc/{kind}/*/*.gim"))
                            + (sorted(glob.glob(os.path.join(self.pc, "face/motion*.xb/data/kuwabara/pc/face/*/*.gim")))
                               if kind == "face" else [])):
                stem = os.path.basename(p)[:-4]
                if (kind, stem) in seen:
                    continue
                seen.add((kind, stem))
                dst = os.path.join(self.out_t, kind, stem + ".png")
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                gim.to_png(p, dst)
                n += 1
        print("textures:", n)

    # ---- parts -----------------------------------------------------------------------------------
    def do_parts(self):
        n = 0
        ref = self.ref_skeleton()
        for kind in PART_KINDS:
            os.makedirs(os.path.join(self.out_m, "parts", kind), exist_ok=True)
            for p in sorted(glob.glob(os.path.join(self.pc, f"{kind}/{kind}*.xb/data/kuwabara/pc/{kind}/*/*.psp.i3r"))):
                stem = os.path.basename(p).split(".")[0]
                out = os.path.join(self.out_m, "parts", kind, stem + ".glb")
                if kind == "body":
                    build.build(p, [], out, name=stem, **self.bargs())
                else:
                    build.build(None, [p], out, name=stem, skel_path=ref, **self.bargs())
                n += 1
        print("parts:", n)

    # ---- assembled characters --------------------------------------------------------------------
    def do_characters(self, roster, pcs):
        index = []
        for c in roster:
            i = c["index"]
            if pcs and i not in pcs:
                continue
            face = self.model_path("face", f"face{i:02d}")
            d = os.path.join(self.out_m, f"pc{i:02d}_{c['slug']}")
            os.makedirs(d, exist_ok=True)
            for label, head, body in c["sets"]:
                hp, bp = self.model_path("head", f"head{head:02d}"), self.model_path("body", f"body{body:02d}")
                out = os.path.join(d, f"pc{i:02d}_{c['slug']}_{label}.glb")
                build.build(bp, [face, hp], out, tone=c["skin_tone"], name=f"pc{i:02d}_{c['slug']}_{label}",
                            **self.bargs())
                e = {k: v for k, v in c.items() if k != "sets"}
                e.update(set=label, file=os.path.relpath(out, ROOT), face=os.path.relpath(face, self.pc),
                         head=os.path.relpath(hp, self.pc), body=os.path.relpath(bp, self.pc))
                index.append(e)
                print(out)
        if not pcs:
            json.dump(index, open(os.path.join(self.out_m, "characters.json"), "w"), indent=1, ensure_ascii=False)

    # ---- animations ------------------------------------------------------------------------------
    def motions(self):
        """{owner ('pcNN' or 'common'): [(anim name, path)]}, deduplicated by content."""
        hashes = collections.defaultdict(set)
        by = collections.defaultdict(dict)
        for p in sorted(glob.glob(os.path.join(self.xb, "**/*.i3m"), recursive=True)):
            rel = os.path.relpath(p, self.xb)
            if rel.startswith(("crs/", "cmn/", "yumo/title")) or "/itemget_" in rel:
                continue  # course objects, HUD, title, item-get props: no character tracks
            m = PC_ARCHIVE.search("/" + rel)
            owner = f"pc{m.group(1)}" if m else "common"
            h = hashlib.md5(open(p, "rb").read()).hexdigest()
            if h in hashes[owner]:
                continue
            hashes[owner].add(h)
            name = os.path.basename(p)[:-4]
            if name in by[owner]:  # same name, different content: tag with the archive
                name = name + "_" + re.sub(r"\W+", "_", os.path.basename(rel.split("/data/")[0]))
            by[owner][name] = p
        return {o: sorted(v.items()) for o, v in by.items()}

    def do_anims(self, roster, pcs):
        os.makedirs(self.out_a, exist_ok=True)
        ref = self.ref_skeleton()
        names = {f"pc{c['index']:02d}": c["slug"] for c in roster}
        report = {}
        for owner, items in sorted(self.motions().items()):
            if pcs and owner != "common" and int(owner[2:]) not in pcs:
                continue
            anims = [(n, i3m.load(p)) for n, p in items]
            out = os.path.join(self.out_a, f"{owner}_{names[owner]}.glb" if owner in names else f"{owner}.glb")
            b = build.build(None, [], out, name=f"{self.name}_{owner}_motions", skel_path=ref, anims=anims,
                            **self.bargs())
            got = [a["name"] for a in b.b.g.get("animations", [])]
            report[owner] = dict(file=os.path.relpath(out, ROOT), exported=got,
                                 skipped=[n for n, _ in items if n not in got])
            print(owner, "motions:", len(got), "skipped (no skeleton tracks):", len(items) - len(got))
        if not pcs:
            json.dump(report, open(os.path.join(self.out_a, "motions.json"), "w"), indent=1)


def main(game, roster_fn):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="textures,parts,characters,anims")
    ap.add_argument("--pc", default="")
    a = ap.parse_args()
    pcs = [int(x) for x in a.pc.split(",") if x]
    steps = a.only.split(",")
    roster = roster_fn()
    if "textures" in steps:
        game.do_textures()
    if "parts" in steps:
        game.do_parts()
    if "characters" in steps:
        game.do_characters(roster, pcs)
    if "anims" in steps:
        game.do_anims(roster, pcs)
