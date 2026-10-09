"""Export Hot Shots Tennis: Get a Grip (PSP) characters, parts, textures and motions to glTF.

    python3 tools/psp2gltf/export_getagrip.py [--only textures,parts,characters,anims] [--pc 0,1]

Reads out/files/getagrip/PSP_GAME/USRDIR/xbdata (unpacked .xb archives), writes
out/textures/getagrip, out/models/getagrip, out/anims/getagrip. See notes/getagrip.md.
"""
import argparse
import csv
import glob
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
XB = os.path.join(ROOT, "out/files/getagrip/PSP_GAME/USRDIR/xbdata")
PC = os.path.join(XB, "game/400_pc")
OUT_M = os.path.join(ROOT, "out/models/getagrip")
OUT_A = os.path.join(ROOT, "out/anims/getagrip")
OUT_T = os.path.join(ROOT, "out/textures/getagrip")

# Katakana names from data/menu/chrselect/chrsel_param_chara.csv (row order = Pc_NN), romanised literally.
ROMAJI = {"エミ": "emi", "バン": "ban", "タイガ": "taiga", "ウェンディ": "wendy", "ブラッド": "brad",
          "ロゼッタ": "rosetta", "ミツザネ": "mitsuzane", "パオラ": "paola", "ファン": "fan",
          "レイチェル": "rachel", "シュナイダー": "schneider", "ノーマ": "norma", "スズキ": "suzuki",
          "グロリア": "gloria", "ヘルガスト": "helghast"}


def roster():
    p = os.path.join(XB, "menu/chrsel_010_param.xb/data/menu/chrselect/chrsel_param_chara.csv")
    rows = list(csv.reader(io.StringIO(open(p, "rb").read().decode("shift_jis"))))[4:]
    out = []
    for i, r in enumerate(rows):
        m = re.match(r"(\D+)(\d+)", r[0])
        out.append(dict(index=i, kana=m.group(1), height_class=int(m.group(2)), name=ROMAJI.get(m.group(1), f"pc{i:02d}")))
    return out


def parts_table(kind):
    p = os.path.join(XB, f"common/common_10.xb/data/chara/parameter/Parts_{kind}.txt")
    lines = open(p, encoding="utf-8-sig").read().replace("\r", "").split("\n")
    hdr = lines[0].split("\t")
    return {l.split("\t")[0]: dict(zip(hdr, l.split("\t"))) for l in lines[1:] if l.strip()}


def model_path(kind, num):
    g = glob.glob(os.path.join(PC, f"{kind}/{kind}{num:03d}.xb/data/chara/model/{kind}/*/*.psp.i3r"))
    return g[0] if g else None


def face_tone(face_path):
    """Skin tone variant letter (f/m/b/k) = suffix of the head3NN_<t>00.gim shipped with the face."""
    for f in os.listdir(os.path.dirname(face_path)):
        m = re.match(r"head\d+_([fmbk])00\.gim$", f)
        if m:
            return m.group(1)
    return "f"


def do_textures():
    n = 0
    for p in sorted(glob.glob(os.path.join(PC, "*/*.xb/data/chara/model/**/*.gim"), recursive=True)):
        kind = os.path.relpath(p, PC).split("/")[0]
        dst = os.path.join(OUT_T, kind, os.path.basename(p)[:-4] + ".png")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        gim.to_png(p, dst)
        n += 1
    print("textures:", n)


def ref_skeleton():
    return model_path("body", 0)


def do_parts():
    n = 0
    for kind in ("body", "head", "face", "etc", "racket"):
        os.makedirs(os.path.join(OUT_M, "parts", kind), exist_ok=True)
        for p in sorted(glob.glob(os.path.join(PC, f"{kind}/*.xb/data/chara/model/{kind}/*/*.psp.i3r"))):
            stem = os.path.basename(p).split(".")[0]
            out = os.path.join(OUT_M, "parts", kind, stem + ".glb")
            if kind == "body":
                build.build(p, [], out, name=stem)
            else:
                build.build(None, [p], out, name=stem, skel_path=ref_skeleton())
            n += 1
    print("parts:", n)


def mesh_groups(path):
    """Names of the '<Bone>9<x>' nodes that carry mesh groups in a rigid part."""
    import i3d
    m = i3d.load(path)
    d = open(path, "rb").read()
    return {m.skeleton.names[j] for j, _ in build._node_groups(d, i3d.parse_tree(d), m.skeleton)}


def do_characters(pcs):
    acces = parts_table("Acce")
    index = []
    for c in roster():
        if pcs and c["index"] not in pcs:
            continue
        i = c["index"]
        face = model_path("face", i)
        tone = face_tone(face)
        d = os.path.join(OUT_M, f"pc{i:02d}_{c['name']}")
        os.makedirs(d, exist_ok=True)
        for set_ in (3, 4):
            num = set_ * 100 + i
            head, body = model_path("head", num), model_path("body", num)
            # Hat head items carry two variants: `for_org` (the hat alone) and `for_hat` (the hat + a generic
            # hair/ears cap for faces without their own). Every PC face has a `for_hat` group = the
            # character's own hair under a hat (textured with its head3NN skin), so: hat -> face.for_hat +
            # head.for_org; hair item -> face without for_hat (its hair is in the head item).
            hat = any(n.endswith("9for_org") for n in mesh_groups(head))
            parts = [(face, None if hat else r"9for_hat$"), (head, r"9for_hat$" if hat else None)]
            # Costume-set accessory: Acce_<set><NN> (same 3NN/4NN numbering as Head_/Body_, PC_ONLY_1 = NN)
            acce = acces.get(f"Acce_{num}")
            etc = model_path("etc", num) if acce and acce["PC_ONLY_1"] == str(i) else None
            if etc:
                parts.append(etc)
            out = os.path.join(d, f"pc{i:02d}_{c['name']}_set{set_}.glb")
            build.build(body, parts, out, tone=tone, name=f"pc{i:02d}_{c['name']}_set{set_}")
            index.append(dict(pc=i, name=c["name"], kana=c["kana"], set=set_, file=os.path.relpath(out, ROOT),
                              face=os.path.relpath(face, PC), head=os.path.relpath(head, PC),
                              body=os.path.relpath(body, PC),
                              acce=os.path.relpath(etc, PC) if etc else None, skin_tone=tone, hat=hat,
                              height_class=c["height_class"]))
            print(out)
    json.dump(index, open(os.path.join(OUT_M, "characters.json"), "w"), indent=1, ensure_ascii=False)


def _anim_name(p):
    return os.path.basename(p)[:-4]


def do_anims(pcs):
    os.makedirs(OUT_A, exist_ok=True)
    ref = ref_skeleton()
    common = sorted(glob.glob(os.path.join(PC, "face/common_motion_*.xb/data/chara/motion/099/*.i3m")))
    build.build(None, [], os.path.join(OUT_A, "common_motions.glb"), name="getagrip_common_motions",
                skel_path=ref, anims=[(_anim_name(p), i3m.load(p)) for p in common])
    print("common motions:", len(common))
    bt = sorted(glob.glob(os.path.join(PC, "body_type/*.xb/data/chara/model/body_type/*.i3m")))
    build.build(None, [], os.path.join(OUT_A, "body_types.glb"), name="getagrip_body_types",
                skel_path=ref, anims=[(_anim_name(p), i3m.load(p)) for p in bt])
    print("body types:", len(bt))
    for c in roster():
        if pcs and c["index"] not in pcs:
            continue
        ps = sorted(p for p in glob.glob(os.path.join(XB, f"game/700_prize/020_prize_pc{c['index']:02d}.xb/data/chara/prize_motion/*/*.i3m"))
                    if not p.endswith("_cam.i3m"))
        if ps:
            build.build(None, [], os.path.join(OUT_A, f"pc{c['index']:02d}_{c['name']}_prize.glb"),
                        name=f"pc{c['index']:02d}_prize", skel_path=ref,
                        anims=[(_anim_name(p), i3m.load(p)) for p in ps])
            print("prize", c["name"], len(ps))
        # the character's own point/set reactions (re_pcNN_gu01, di_set02_loop, …, A_re_pcNN_co10)
        rs = sorted(glob.glob(os.path.join(PC, f"face/face{c['index']:03d}_anim.xb/data/chara/motion/{c['index']:02d}/*re_pc{c['index']:02d}_*.i3m")))
        if rs:
            build.build(None, [], os.path.join(OUT_A, f"pc{c['index']:02d}_{c['name']}_react.glb"),
                        name=f"pc{c['index']:02d}_react", skel_path=ref,
                        anims=[(_anim_name(p), i3m.load(p)) for p in rs])
            print("reactions", c["name"], len(rs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="textures,parts,characters,anims")
    ap.add_argument("--pc", default="")
    a = ap.parse_args()
    pcs = [int(x) for x in a.pc.split(",") if x]
    steps = a.only.split(",")
    if "textures" in steps:
        do_textures()
    if "parts" in steps:
        do_parts()
    if "characters" in steps:
        do_characters(pcs)
    if "anims" in steps:
        do_anims(pcs)


if __name__ == "__main__":
    main()
