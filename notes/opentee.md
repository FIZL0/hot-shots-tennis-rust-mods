# Hot Shots Golf: Open Tee 1 & 2 (PSP) — character export

Re-run (≈1 min each; python3 + numpy + Pillow):
`python3 tools/psp2gltf/export_opentee.py` and `python3 tools/psp2gltf/export_opentee2.py`
(`--only textures,parts,characters,anims`, `--pc 0,3`). Shared logic: `tools/psp2gltf/opentee_common.py`; readers
`i3d.py / i3m.py / gim.py / build.py` are the Get a Grip ones (see "Reader changes"). Check render:
`python3 tools/psp2gltf/render.py file.glb out.png [--anim NAME --times 0,0.5]`. Formats: `notes/psp-formats.md`.

## Where things live (`out/files/<game>/PSP_GAME/USRDIR/xbdata/`)
- `kuwa/pc/{face,head,body,etc,club,ball}/<kind>NN.xb/data/kuwabara/pc/<kind>/NN/<kind>NN.psp.i3r` (+ `.gim`,
  skin-tone variants `_f00/_m00/_b00/_k00`). Face = the character (face only; hair comes from the head item).
- Tables: `kuwa/param/param.xb/data/kuwabara/pc/{face,head,body,etc,club,ball}.csv` (Shift-JIS). OT2 also
  `text/*.bin` name tables; `param.xb1` = English localisation (OT2 nested `.xb1` = English copy of an `.xb`).
- Motions per character `kuwa/pc/face/motionNN.xb` (+ `feel/waitNN`), result `tnk/result/Motion/r_motNN.xb`
  (`winNN/lostNN/waitNN`), menu/VS poses `tnk/motion/NN/motNN.xb`, entry `tagu/parts/afaceNN.xb` (`fixedNN`),
  OT2 also item-get `kuwa/pc/itemget/itemgetNN.xb` (`get_pcNN_*`) and `matu/lastchk/motionNN.xb` (`*_car`).
- `.i3c` (OT1 3212 / OT2 5291) are **only under `crs/`** (course structures/collision) — not character data.

## Rosters (index = pcNN = face number = voice bank number in notes/audio.md)
**OT1** (face.csv has English names): 00 Mika, 01 Rio, 02 Alia, 03 Shu, 04 Julie, 05 CJ, 06 Patricia, 07 Logan,
08 Holly, 09 Roger (10 = audio `pc00..09`).
**OT2** (English from `param.xb1/.../text/face.bin`; Japanese katakana from face.csv, literal romaji in
`characters.json`): 00 Mika ユメリ, 01 Rio シン, 02 Alia ミュウ, 03 Shu トシゾウ, 04 Julie サギリ, 05 CJ ジャン,
06 Patricia キャサリン, 07 Logan アーロン, 08 Holly アンジェラ, 09 Roger ブリッツ, 10 Carly メイ, 11 Luke レオ,
12 Alice ミズホ, 13 Malachy ジャック, 14 Frau Ada ジーナ, 15 Montcalm ロベルト, 16 Lauryn ブレンダ, 17 Mifune ミフネ,
18 Lee セイラン, 19 Chad ブライアン, 20 Gloria グロリア. Faces/motions/voices also exist for **pc21, pc22** (face21 node
`Bip01Head9face_ruri`) but they are in no table: no name, no outfit → exported as face parts + motions only.

## Costumes
Open Tee is mix-and-match: any character wears any head/body/etc item (OT1 96 bodies / 72 heads / 54 etc;
OT2 153 / 109 / 87). The character-specific look is the signature item pair, which is what is assembled:
- OT1: head/body named "<Name>'s Hair/outfit" with `Gr` = −index (Mika: Gr 0). Matches the VS-mode archives
  `matu/com/vsNN.xb`.
- OT2: head/body whose Japanese name is "<kana>の髪型 / <kana>の服" (カテゴリ `XNN`); Gloria has a second body
  (グロリアの服 黄, body 75) → `own2`. Matches `itemgetNN.xb` except Holly (item-get shows body 143, a tree costume).
- Skin tone = face.csv `色` (f/m/k/b) → texture variant. face.csv `scale` (82–110 %) and OT2 `頭scale` (head
  scale) are recorded in `characters.json` but **not applied**.
- OT2 bodies (and heads/faces `_y`) ship build variants `bodyNN_y` (slim), `_g` (wider), `_d` (heavy); which
  character uses which is not in the tables (the item-get scenes use the base file) → base assembled, variants
  exported as parts.

## Exported (out/ is git-ignored)
- `out/models/opentee/pcNN_<name>/pcNN_<name>_own.glb` (10), `out/models/opentee2/...` (22 incl. Gloria own2);
  `characters.json` lists parts, tone, scale, gender.
- `out/models/<game>/parts/{body,head,face,etc}/*.glb`: OT1 232, OT2 963 (incl. `_y/_g/_d`), on the body00 skeleton.
- `out/textures/<game>/{body,head,face,etc}/*.png`: OT1 830, OT2 1321 (incl. expression faces `faceNN_a..f`).
- `out/anims/<game>/pcNN_<name>.glb` (skeleton-only, animations target bones by name) + `common.glb`;
  `motions.json` lists exported/skipped per file. OT1 30–32 per character + 18 common; OT2 45–48 per character
  (also pc21/22) + 14 common. Contents: `winNN`, `lostNN`, `waitNN` (result screen), `vspose_NN`, `menu_0x`,
  `fixedNN` (entry), `re_pcNN_*` (shot reactions, 9 kinds), `kuNN_{an,aw,cl,di,gl,ha,sh}` (OT2 emotes — `ha` waves,
  `an` stamps, `cl` claps; others unchecked), `ga_*`, `tu_*`, `ad_*` (address), `sw_*` (swings), `get_*` (OT2).
  Code meanings beyond these are unverified. Skipped: `ca_*` (camera only), OT2 `re_pcNN_ko` (3ds-Max bone names,
  doesn't fit the OT2 rig), etc-accessory motions (`etcNN_*`, pets' own bones).
- Validation: Khronos validator — 0 errors / 0 warnings on all 253 (OT1) + 1009 (OT2) glbs. Visual: contact
  sheets of all assembled characters; win/lost/reaction/emote/swing poses checked on Mika (OT1), Gloria (OT2).

## Format differences vs Get a Grip
- **OT2 = Get a Grip format** (Maya export, `Bip01Pelvis` names, attach separator `9`), but no `pc_locator` /
  `pelvis_locator` (pelvis under ROOTNODE, sometimes via an identity Maya `group` node), and 379 parts are
  3ds Max exports with the OT1-style ROOTNODE.
- **OT1 = 3ds Max export**: spaced Biped names (`Bip01 Pelvis`), attach separator `&` (`Bip01 Head&00`), ROOTNODE
  = (x,y,z)→(−x,−z,−y) (Z-up), bones keep Biped axes, extra `Bip01` / `Bip01 Footsteps` / `DummyNN` nodes; skins
  name bones `InfluenceNNNN` (resolved by inverse-bind matching); the skinned mesh node carries a non-uniform
  scale (e.g. `woman_body` 0.69/0.85/0.53), i.e. vertices are in mesh-node space (IB·W = mesh world, not R0).
- Material texture name = string at `0x26 data + u32@+0x18` (GaG/OT2 0x3A; OT1 has `Channel0000` first).
- I3M `flags` 1 (OT2, 737 files): f32×4 position/scale pool at `off_vec`, s16×4/32767 quaternion pool at the 4th
  header offset; flags 0 = float, 25 = quantised as before. (Not yet in psp-formats.md.)
- OT2 accessories `etc05/58/102/...` are pets skinned to their own bones → exported as static bind-pose meshes.

## Reader changes (shared, Get a Grip re-verified)
`i3d.py` material-name offset + `resolve_skin_names`; `i3m.py` flags-1 variant; `build.py` ROOTNODE glTF local
= R0·F (identity for Maya files, Z-up→Y-up for Max files), skinned vertices taken to model space via IB·W·F,
`keep`/`sep` parameters, bones parented to the nearest kept ancestor, attach walk skips `polySurface39`-style names,
own-skeleton skinned accessories as static meshes. `export_getagrip.py` re-run: same 3211 files, all validate;
10 glbs changed (body100/157/194/195/198/204/314/414 + Helghast set3/4) — the skin-space fix moves offset skin
groups (e.g. Helghast's thigh pouch was below the feet) to their correct place. Everything else byte-identical.

## Skeleton vs Get a Grip / HST
- **OT2 ≈ Get a Grip**: same 44 `Bip01*` names and the same bind joint positions (pelvis 57.9, head 87.1 cm),
  bones rotation-reset (model axes); differences: no `pc_locator`/`pelvis_locator` (root motion would go on the
  pelvis), and OT2 adds `Bip01HeadNub`, `Finger0Nub`, `Toe0Nub` ends. GaG motions should drive OT2 rigs by name.
- **OT1 ≠ Get a Grip**: same joint positions but 3ds Max Biped structure: `Bip01` root (like HST), thighs
  under `Bip01 Spine` (like HST, unlike GaG/OT2), Biped bone axes (like HST), spaced names, `Footsteps`, `DummyNN`.
  Still no `Spine2`, one-segment fingers, no hair chain/racket bone (HST has these). Name map: drop spaces.
- vs HST (notes/getagrip.md): all three differ the same way on Spine2/fingers/hair/racket; retarget in model
  space by name as for Get a Grip. OT1's hierarchy/axes are the closest to HST of the three.

## Gaps
- TAT face-expression swaps not decoded (another agent is working on TAT); expression textures are exported.
- Character `scale`/`頭scale`, OT2 body-build variant choice, pc21/pc22 identity, club/ball items, reaction
  props (`ko_*.psp.i3r`) and their motions, pet/accessory animations, vertex morphs: not applied/exported.
- Position/scale tangent basis as in psp-formats.md (inferred).
