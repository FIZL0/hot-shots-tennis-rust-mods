"""Export Hot Shots Golf: Open Tee (PSP) characters, parts, textures and motions to glTF.

    python3 tools/psp2gltf/export_opentee.py [--only textures,parts,characters,anims] [--pc 0,1]

Reads out/files/opentee/PSP_GAME/USRDIR/xbdata, writes out/{models,anims,textures}/opentee. See notes/opentee.md.
OT1 models are 3ds Max exports: Z-up, spaced Biped names ("Bip01 Pelvis"), attach separator '&'.
"""
import os
import re

from opentee_common import ROOT, Game, main, read_csv

XB = os.path.join(ROOT, "out/files/opentee/PSP_GAME/USRDIR/xbdata")
PARAM = os.path.join(XB, "kuwa/param/param.xb/data/kuwabara/pc")
GAME = Game("opentee", XB, sep="&", keep=re.compile(r"^(ROOTNODE|Bip01[^&]*|Dummy\d+)$"))


def roster():
    """face.csv rows = characters (English names in the table). Costume 'own' = the head/body named
    "<Name>'s ..." whose Gr column is -index (the character's signature items)."""
    rows = read_csv(os.path.join(PARAM, "face.csv"))[2:]
    items = {k: [r for r in read_csv(os.path.join(PARAM, f"{k}.csv"))[2:] if r and r[0].isdigit()]
             for k in ("head", "body")}
    out = []
    for r in rows:
        if not r or not r[0].isdigit():
            continue
        i = int(r[0])
        own = {k: [int(x[0]) for x in items[k] if "'s " in x[1] and x[9].strip() == str(-i)] for k in items}
        assert len(own["head"]) == 1 and len(own["body"]) == 1, (r[1], own)
        out.append(dict(index=i, name=r[1], slug=r[1].lower(), gender={"1": "m", "2": "f"}.get(r[11], "?"),
                        skin_tone=r[26].strip() or "f", scale_percent=int(r[27]), note_jp=r[25],
                        sets=[("own", own["head"][0], own["body"][0])]))
    return out


if __name__ == "__main__":
    main(GAME, roster)
