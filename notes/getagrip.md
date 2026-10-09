# Hot Shots Tennis: Get a Grip (PSP) — character export

Re-run everything (≈1 min): `python3 tools/psp2gltf/export_getagrip.py`
(`--only textures,parts,characters,anims`, `--pc 0,3`). Needs python3 + numpy + Pillow.
Check render: `python3 tools/psp2gltf/render.py file.glb out.png [--anim NAME --times 0,0.3 --views front,side]`.
Formats: `notes/psp-formats.md`.

## Where things live (`out/files/getagrip/PSP_GAME/USRDIR/xbdata/`)
- `game/400_pc/`: `face/faceNNN.xb` (face + the character's own hair; face 000-014 = PCs, 1xx/2xx/3xx = NPC
  faces), `head/headNNN.xb` (hair/hats), `body/bodyNNN.xb` (skinned outfits + full skeleton), `etc/` (accessories),
  `racket/`, `body_type/` (proportion poses), `face/common_motion_0..3.xb` (all gameplay motions, shared, `pc099`),
  `face/faceNNN_anim.xb` (TAT expression swaps).
- `game/700_prize/020_prize_pcNN.xb`: per-character win/lose motions (+ camera `_cam`).
- Parts tables: `common/common_10.xb/data/chara/parameter/Parts_{Face,Head,Body,Acce}.txt` (UTF-8 TSV).
- Roster: `menu/chrsel_010_param.xb/.../chrsel_param_chara.csv` (row = Pc_NN), stats `character.csv`.

## Roster (from chrsel_param_chara.csv, katakana romanised literally; number = height class)
00 エミ emi 160 · 01 バン ban 160 · 02 タイガ taiga 160 · 03 ウェンディ wendy 170 · 04 ブラッド brad 180 ·
05 ロゼッタ rosetta 150 · 06 ミツザネ mitsuzane 170 · 07 パオラ paola 140 · 08 ファン fan 170 ·
09 レイチェル rachel 170 · 10 シュナイダー schneider 190 · 11 ノーマ norma 170 · 12 スズキ suzuki 160 ·
13 グロリア gloria 170 · 14 ヘルガスト helghast 180

A character = face0NN + head item + body item (+ accessories). Costume sets: `Head_3NN/Body_3NN` and
`Head_4NN/Body_4NN` have PC_ONLY_1 = NN (character-exclusive; 3NN renders as the familiar default look).
Skin tone of body/head textures (`_f/_m/_b/_k00` variants) = suffix of the `head3NN_?00.gim` shipped in the
face archive.
Hats: a hat head item has two groups, `Bip01Head9for_org` (the hat alone) and `Bip01Head9for_hat` (hat + a
generic hair/ears cap, for faces without their own); every PC face has a `Bip01Head9for_hat` group = the
character's own hair/ears/back of head under a hat (textured with its `head3NN` skin). So with a hat
(head 312/314/412/414) the set is face (all groups) + head `for_org`; with a hair item the face's `for_hat` is
left out. (Head/Acce `Site` is not the hat flag: Head `Site` is 0 everywhere.)
Costume accessories: `Acce_3NN`/`Acce_4NN` (PC_ONLY_1 = NN) → `etc/etc3NN`/`etc4NN`: Brad 304/404 wristband
(RForearm), Rosetta 305/405 top hat, Paola 307/407 flower, Fan 308/408 glasses, Suzuki 312/412 sunglasses,
Helghast 314/414 belt (Spine1). Other PCs have none. `Acce_6xx`/`Head_6xx`/`Body_6xx` are shop items (Price
set), not costume sets. Every PC's default racket is `Racket_000` (racket000), not packaged (the mod uses the
donor's racket; see Gaps).

## Exported (out/ is git-ignored)
- `out/models/getagrip/pcNN_<name>/pcNN_<name>_set{3,4}.glb` — 30 assembled characters (face + head + body +
  costume accessory); `characters.json` lists the parts/tone/hat/acce per file.
- `out/models/getagrip/parts/{body,head,face,etc,racket}/*.glb` — all 564 parts, each on the reference
  skeleton (bodies skinned; others rigid under their attach bone; etc50 is a skinned accessory).
- `out/textures/getagrip/<kind>/*.png` — all 2599 GIMs of 400_pc (incl. expression faces, tone variants).
- `out/anims/getagrip/common_motions.glb` (233 of 256 motions), `body_types.glb` (41), `pcNN_<name>_prize.glb`
  (10 each). Skeleton-only glbs; animations target nodes by name (same names as the model glbs).

glTF layout: top node `<name>` scale 0.01 (cm → m) → `ROOTNODE` (identity; file has a 180° Z flip that the
skin excludes) → `pc_locator` → `pelvis_locator` → `Bip01Pelvis` … 44 Bip01 bones. +Y up, facing +Z.
One skin over all bones (IBM = inverse bind from the skeleton = the file's IBMs). Max 4 weights kept
(100 of 213k vertices had 5-8, renormalised). Animations resampled at 60 Hz, LINEAR.
Materials: base colour texture, double-sided, MASK/BLEND from texture alpha.

Validation: Khronos glTF validator (node lib; `npx gltf-validator` has no CLI) — 0 errors / 0 warnings on all
character + part + anim files (only infos: empty helper nodes). Visual: contact sheet of all 30 characters,
all accessories, run/forehand/jump-serve/win poses rendered with the software renderer — correct.

## Facial expressions (`python3 tools/psp2gltf/export_getagrip_faces.py`, needs the main export first)
Pure texture swaps, no bones/morphs: the face mesh has two materials `face` (right half) / `faceL` (left), both
mapped to one mirrored half-face texture `<stem>_faceN.gim` (stem = zero, one … fourteen for pc00-14; glb
material = `<stem>_face0`). Each texture is a **whole expression** (eyes+brows+mouth) — no separate eye/mouth
slots, so HST `*_eye`/`*_mouth` channels of one emotion map to the same texture. TAT files (format in
psp-formats.md) next to the motions switch the index: `faceNNN_anim.xb/.../099/` (shared gameplay: shots → 3
at impact then 0, misses / tired `*_01` → 4, high ball `*_vh`/`ball_hs_*_loop` → 5, dash/end → blinks 1),
`.../NN/` per character (`re_pcNN_gu*` point-won "guts" = joy, `re_pcNN_di*` point-lost = dismay/anger,
`A_re_pc099_coNN_00/_01` positive/negative comment reactions, `mo_pc099_ball_*`/`ko_si*`/`tu_00` hit by ball /
knocked down / stumble = shocked → pain), and `700_prize/.../*.tat` (win/lost/hand/rslt_good/bad/wait).
Index 0-5 roughly shared across PCs (0 neutral, 1 blink, 2 smile, 3 effort shout, 4 dejected, 5 varies);
6+ are character-specific. NPC faces 1xx-3xx have 7 textures × 4 skin tones (`_f/_m/_b/_k`, same tone codes
as bodies); PCs have one tone. Helghast (pc14) is a single mask texture, no expressions.
Outputs: `out/models/getagrip/faces.json` (per character: material, neutral, HST channels blink/joy/anger/
sorrow/doki → PNG, `approx` flags, all labels, extras), `out/anims/getagrip/face_tracks.json` (2166 motions:
motion → {source, face/faceL: [[t, N]]}, N already remapped to the character's own texture), labelled sheets
`out/textures/getagrip/_face_sheets/pcNN_<name>.png` (green = assigned HST channel, `~` = approx).
Confidence: blink/neutral H; joy/sorrow/doki M (sheet + usage in gu/di/ball-hit TATs agree); anger M-L
(several characters have no true angry face → pout/frown/grit picked, flagged approx).

## Skeleton vs HST (PS2 `pc00_t00_c00.MDL`, dumped with `tools/psp2gltf/hstskel`)
Not 1:1. Same 3ds Max Biped naming, so a **name-based** map covers every GaG bone, but:
- GaG has no `Bip01`; root motion is `pc_locator`, pelvis height on `pelvis_locator` (≈ HST `Bip01`).
- GaG has no `Bip01Spine2` (HST Spine2 → keep at rest or split Spine1).
- Fingers: GaG one segment (`FingerN` + `FingerNNub`); HST three (`FingerN, FingerN1, FingerN2`).
- Thighs: GaG children of `Bip01Pelvis`, HST children of `Bip01Spine`.
- HST extras: hair chain `Bone0001-5`, `Racket` bone, `s_*` mesh nodes; GaG racket is an attachment
  (`Bip01RHand9racket00`) and has `HeadNub`/`Toe0Nub`.
- Bind frames differ: GaG bones are rotation-reset (≈ identity, model axes); HST keeps Biped axes
  (x along the bone). HST is metres with −Y up; GaG cm +Y up. Proportions: chibi but pelvis/head ratio
  similar (GaG 57.9/87.1 cm, HST 0.83/1.22 m).
⇒ Retarget in model space (per-bone world rotation delta from bind, by name), not by copying locals.

## Gaps
- No `racket.glb` in the mods: GaG's racket000 (`Bip01RHand9racket00`) would need placing in HST's `Racket`
  joint frame (grip axis/orientation differ); the remaster draws the donor's racket meanwhile.
- Position/scale tangent basis inferred (see formats); rotation exact. A/B layer pairing per shot is game code
  (EBOOT encrypted), so layers are exported as separate animations — combine A_* (upper) + B_* (lower) yourself.
- `body_type` per character unknown: 41 = 8 height classes × 5 builds (+040); height class from the roster
  number / character.csv `Height`, build index not found in data. Exported but not applied.
- 23 of 256 common motions have no skeleton tracks (`*_dum`, `*_ball*` = ball/dummy paths) → skipped.
- Lobby motions (`lobby/030_room/*_motion.xb`, l99), NPC faces, adhoc LODs,
  vertex morphs (2 prims), material render-state flags beyond alpha: not exported.
