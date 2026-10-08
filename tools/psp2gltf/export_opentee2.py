"""Export Hot Shots Golf: Open Tee 2 (PSP) characters, parts, textures and motions to glTF.

    python3 tools/psp2gltf/export_opentee2.py [--only textures,parts,characters,anims] [--pc 0,1]

Reads out/files/opentee2/PSP_GAME/USRDIR/xbdata, writes out/{models,anims,textures}/opentee2. See notes/opentee.md.
OT2 models are Maya exports like Get a Grip (Y-up, "Bip01Pelvis", attach separator '9').
"""
import os

import build
from opentee_common import ROOT, Game, main, read_csv, text_table

XB = os.path.join(ROOT, "out/files/opentee2/PSP_GAME/USRDIR/xbdata")
PARAM = os.path.join(XB, "kuwa/param/param.xb/data/kuwabara")       # Japanese build of the tables
PARAM_EN = os.path.join(XB, "kuwa/param/param.xb1/data/kuwabara")   # .xb1 = English localisation
GAME = Game("opentee2", XB, sep="9", keep=build.KEEP)

# literal Hepburn of the Japanese names (the English build renames the characters, see roster())
ROMAJI = {"ユメリ": "yumeri", "シン": "shin", "ミュウ": "myuu", "トシゾウ": "toshizou", "サギリ": "sagiri",
          "ジャン": "jan", "キャサリン": "kyasarin", "アーロン": "aaron", "アンジェラ": "anjera",
          "ブリッツ": "burittsu", "メイ": "mei", "レオ": "reo", "ミズホ": "mizuho", "ジャック": "jakku",
          "ジーナ": "jiina", "ロベルト": "roberuto", "ブレンダ": "burenda", "ミフネ": "mifune",
          "セイラン": "seiran", "ブライアン": "buraian", "グロリア": "guroria"}


def roster():
    """face.csv: the first block of rows (連番 000-020) are the characters, ID = pcNN. English names: the
    .xb1 text/face.bin table (index = ID). Signature items: head/body rows named "<kana name>の髪型/の服"
    (カテゴリ XNN); Gloria has a second outfit (グロリアの服 黄)."""
    rows = read_csv(os.path.join(PARAM, "pc/face.csv"))
    hdr = rows[1]
    col = {h: hdr.index(h) for h in ("ＩＤ", "名称", "タイプ", "色", "scale", "頭scale", "性別")}
    en = text_table(os.path.join(PARAM_EN, "text/face.bin"))
    items = {k: [r for r in read_csv(os.path.join(PARAM, f"pc/{k}.csv"))[2:] if r and r[0].strip().isdigit()]
             for k in ("head", "body")}
    out, seen = [], set()
    for r in rows[2:]:
        if not r or not r[0].strip().isdigit() or int(r[col["ＩＤ"]]) in seen:
            continue
        i = int(r[col["ＩＤ"]])
        seen.add(i)
        kana = r[col["名称"]].strip()
        heads = [int(x[1]) for x in items["head"] if x[2].strip().startswith(kana + "の")]
        bodies = [int(x[1]) for x in items["body"] if x[2].strip().startswith(kana + "の")]
        assert len(heads) == 1 and bodies, (kana, heads, bodies)
        sets = [("own" if k == 0 else f"own{k + 1}", heads[0], b) for k, b in enumerate(bodies)]
        out.append(dict(index=i, name=en[i], kana=kana, romaji=ROMAJI[kana], slug=en[i].lower().replace(" ", ""),
                        gender={"1": "m", "2": "f"}.get(r[col["タイプ"]].strip(), "?"),
                        skin_tone=r[col["色"]].strip() or "f", scale_percent=int(r[col["scale"]]),
                        head_scale_percent=int(r[col["頭scale"]]), sets=sets))
    return out


if __name__ == "__main__":
    main(GAME, roster)
