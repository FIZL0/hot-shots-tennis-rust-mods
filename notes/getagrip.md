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
set), not costume sets. Every PC's default racket is `Racket_000` (racket000.xb → `parts/racket/racket00.glb`;
Racket_param: owned from the start, price 0, No 0, all stats 0). The rackets: 10 models, `racket00`–`08` (items
`Racket_0N0`–`0N2`, three colours of one model with no separate textures in the part) and `racket50` (`Racket_500`).
Since M1r (opentennis, 2026-10-13) each mod of a game gets a different racket (`package.py pick_racket`: Emi
keeps `Racket_000`, the others the next model in pc order, the rest and the golf games HST disc rackets via
`mod.json` `disc_racket`; Gloria and Suzuki get HST's own Gloria's/Suzuki's), a Get a Grip one packaged as `racket.glb` by
`tools/rerig/racket.py`: the source grip on the hand kept (scaled with the body), resized about the hand to HST's
0.944 m racket, baked into the `Racket` joint's space. Checked on Emi: in the hand frame its handle axis is within
3.7° and its string normal within 3.2° of HST pc00's; grip −0.01–0.31 m vs HST 0–0.32 m. (`Racket_500`, also owned
with zero stats, No 1, is not a default.) There is no per-character or per-costume racket in the data: `Racket_param.csv` /
`Racket_Racket_param.txt` have no character column (unlike `Parts_*`' `PC_ONLY_*`), `character.csv` none, and
the only other mention of rackets is the lobby prize table (`Challenge_LobbyItem.txt`); the program is encrypted.
Racket_000 is the item named "Standard" (`CommonText_Racket.to`).

## Size (tools/rerig/sizing.py, standard §3)
All 15 PCs share one skeleton (Bip01 0.5786 m, chibi head ratio ~0.93 vs HST's 0.538). Height: the roster's
height class (cm) × HST's metres per cm for the PC's sex (Parts_Body `PC_SEX` of Body_3NN: Emi, Wendy, Rosetta,
Paola, Rachel, Norma, Gloria women), × one game factor 0.9706 that gives Gloria (170) HST's Gloria's Bip01 0.8554 m
(M1l, 2026-10-12; was 0.9394, the tallest at 0.95 m): Emi 0.805, Ban 0.827, Taiga 0.827, Wendy 0.855, Brad 0.930, Rosetta 0.755, Mitsuzane 0.878, Paola 0.704, Fan 0.878, Rachel 0.855, Schneider 0.982, Norma 0.855, Suzuki 0.827, Gloria 0.855, Helghast 0.930. Heads shrink about the neck by one factor for the
whole cast, Gloria's 0.6277 (0.909 of the way from her head ratio to HST's median: the share that makes her 1.6547 m
head to foot, as HST's Gloria); per-character factors measured hair too and gave Taiga/Ban/Wendy ~0.50 (2026-10-12); `out/rerig/getagrip/sizing.json` has each. Donor: nearest Bip01 among HST's same-sex standard bodies.

## Stats → HST TParam (`tools/rerig/gag_stats.py`, run by `package.py`)
`character.csv` (`Pc_NN_00` rows, in each mod's `source_stats`) is mapped onto `params.override` **by rank**: a
character's position among Get a Grip's 15 on the source stat (ties share their average rank) picks the cell at the
same position in HST's 14 sorted values of that TParam column. Relative strengths stay Get a Grip's, every value is
one HST's own cast has (integers stay integers, `a/b/c` cells are whole HST cells). Each mod's `params_why` lists
source value, rank and result per column. All mapped directions: higher source → higher HST value.

| TParam column | Get a Grip source | note |
|---|---|---|
| Serv POW | mean(FlatservePower, SpinservePower, SliceservePower) | |
| Strk POW, LOW POW | Power | HST keeps LOW POW = Strk POW |
| Voley POW, V LOW POW | VolleyPower | |
| Lob POW, Lob POW2 | LobPower | only Taiga differs (82.5) → top, rest mid |
| Top SPIN | TopSpin | |
| Slice SPIN, Drop SPIN | Spin (overall) | Get a Grip's SliceSpin/DropSpin are the same for all 15 |
| Strk CON | Technique (overall) | CON = widest aim angle, higher = more control |
| Voley CON | VolleyTechnique | |
| Serv CON | mean(Flat/Spin/Sliceserve Technique) | |
| ショット ウサギIMP, ショット カメIMP | Impact | inferred: Impact 8 (Emi, Ban) … 2 (Gloria) = timing-window size, as HST's 9/0/10 (Ashley) … 1/1/8 (Will); Usa/Kame in both games = early/late |
| SPE | Speed | |
| STA | Stamina | HST is 40 for all but Suzuki (35) → only GaG Suzuki (1.0) gets 35 |
| Agili | Acceleration | |
| リーチ(cm) | Leach (90/95/100) | Paola → 60, 95s → 90, Brad/Schneider/Helghast → 100 |
| 飛びつき（遠）開始, 飛びつき限界 | Leach | HST's dive start/limit are 2×/4× reach in every row; ranking keeps that |
| タイプ | Playstyle | 1 → オール, 2 → ベース, 3 → ネット (3 = best volley technique and forward speed; 2 = worst volleys, rising/air/lob specialists) |

Left at the donor row (`params.base` = donor): heights (最適高度, smash/serve/underhand heights), リーチ基点, collision,
toss timing (強/弱トス IMP), Body/Vbdy/Back/Rizing ADJ, stamina costs, DWN columns — they belong to the donor's body and
motions (contact heights must match the motions the mod plays), or Get a Grip has no varying source (`Height`,
`HeightLimitServe`/`Toss` are its own body heights). `SwingBack` 1/2 (one-/two-handed backhand?) has no TParam column.
`ai_row`: an HST character of the same タイプ, same sex if one exists, nearest Bip01 height (`ai_row_why`); the body
donor keeps the same-sex nearest-height rule. Female ベース has only Carol; ネット men only Kaito.

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
- Position/scale tangent basis inferred (see formats); rotation exact. A/B layer pairing per shot is game code
  (EBOOT encrypted), so layers are exported as separate animations — combine A_* (upper) + B_* (lower) yourself.
- `body_type` per character unknown: 41 = 8 height classes × 5 builds (+040); height class from the roster
  number / character.csv `Height`, build index not found in data. Exported but not applied.
- 23 of 256 common motions have no skeleton tracks (`*_dum`, `*_ball*` = ball/dummy paths) → skipped.
- Lobby motions (`lobby/030_room/*_motion.xb`, l99), NPC faces, adhoc LODs,
  vertex morphs (2 prims), material render-state flags beyond alpha: not exported.

## Motions → HST (mod `motions.glb`)

`export_getagrip.py --only anims` also writes `out/anims/getagrip/pcNN_<name>_react.glb`: the character's own
reactions from `face/face0NN_anim.xb/data/chara/motion/NN/` (`re_pcNN_{gu,di,gu_set,di_set}{01,02}` each with a
`_loop`, plus `A_re_pcNN_co10`, an upper-body layer). `package.py` retargets four of them onto each mod's skeleton
with `tools/rerig/motions.py` (60 Hz, intro then loop until the donor clip's frames; only an intro longer than that
is squeezed), shipped as `motions.glb` (standard §6 `motions`, drawn only; the match runs on the donor's clips):

| HST motion | Get a Grip |
|---|---|
| `re_gu` 0x2c (point won) | `re_pcNN_gu01` + `_loop` |
| `re_di` 0x2d (point lost) | `re_pcNN_di01` + `_loop` |
| `re_gu_set` 0x2e (game won) | `re_pcNN_gu_set01` + `_loop` |
| `re_di_set` 0x2f (game lost) | `re_pcNN_di_set01` + `_loop` |

Not mapped: the `02` variants (HST has one clip per slot), `A_re_pcNN_co10` (a doubles reaction; HST's team
reactions 0x30–0x34 are one shared set from PCCG0, not per character), the prize motions (`win`, `lost`,
`rslt_good/bad/wait`, `hand`: HST has no match-end or result-screen motion), and the gameplay motions in
`common_motions.glb`. Those come in upper (`A_`) and lower (`B_`) body layers and have no one-to-one HST clip (no
plain idle: `aw` = await; strokes split by depth/height `t_d`/`t_s`); a stroke or serve drawn from them would also
leave the racket off the ball, since the contact IK and arm table are solved on the donor's swing.

## Chair umpires (`python3 tools/psp2gltf/export_getagrip_umpires.py`, after `tools/rerig/gag_umpires.py`)

`game/200_court/umpire.xb`: u_00..u_07 (`model/umpire/u_NN/u_NN.psp.i3r`, seated, one skeleton without leg bones:
the legs ride the pelvis) and `motion/umpire/u_NN/`. Only u_00 and u_04 have the full set (`_h _r _l _w _s _r_w
_l_w`, u_04's the same as u_00's); the rest only `_s`, so they take u_00's. Into each umpire mod's `umpire.glb`
(standard HST-COURT-UMPIRE-STANDARD.md §3b): `_h` → `idle` (hands together), `_r`/`_l` → `turn_r`/`turn_l` (the
right/left arm out toward that side, as HST's own `uNN_r/_l` end: checked hand positions against the disc's),
`_w` → `wait` (seated breathing, looped during play). `_s`, `_r_w`, `_l_w` and the `.tat` texture animations
(blinks) are not used. Size: Gloria's calibration (`F` = 0.8554 m / 57.9 cm), head ×0.6277 about Bip01Head.
The motions key Bip01Pelvis 45.7 cm lower than the bind pose (in motion the model's origin is the seat), so the
seat lift comes from `idle`'s first pelvis key; ROOTNODE and the locators are put in the skin so a player that
drops non-joint nodes keeps the lift. The PSP code is encrypted: which motion it plays when is a guess by name.
Helghast (u_04) has a canister (`Bip01RThigh9…`) that, with no thigh bone, rides the pelvis beside the chair.

Select pictures (`python3 tools/psp2gltf/export_getagrip_umpire_previews.py`, after the mod folders): each mod's
`previews/umpire.png` (standard §3) is cut out of the umpire's own art on their English loading panel
(`menu/loadmes/judge/loadmes_jNN.xb0/.../JNN.gim`, 480×272: seated in the chair, Helghast as u_04; the plain `.xb`
is Japanese with Yakkun, xb2/xb3 French/Spanish; the shop's 128×128 `r_judgechip.gim` cut-outs show Yakkun for 04
in every variant). Rendering `umpire.glb` instead was tried and dropped: u_01–03 and u_05–07 show stray
hands/feet (Kanani worst) in render.py, at rest too.

## Courts (`python3 tools/psp2gltf/export_getagrip_courts.py [NN ...]`)

Sixteen courts (01–09, 13–18, 20) → `out/mods/gag_cNN_<stem>/` court mods (standard court §2): `court.glb`,
`sky.glb`, `gimmick.glb`, `sound/bgm.wav` + `sound/ambience_0.wav` (with loop points), `lensflare.png` (outdoor),
`mod.json`. Everything about the file layout is in the script's docstring; the findings:

- **Space**: true scale in cm, net at the origin, long axis Z, Y up, umpire's chair on +X (`pc_locator__singles`
  (650, 172.8, 0) = HST's umpire seat). → HST game space (0.01x, −0.01y, −0.01z): `game_space` → `gag_cm`
  (rotation [1,0,0,0], scale 0.01). The painted lines' vertex rows sit on 5.485 / 4.115 / 11.885 / 6.40 m on all 16.
- **Placement** `haichi/cNN_<stem>__haichi.i3m`: one single-key track per instance, `<model>__<NN>[__singles|__doubles]`
  (or `<model>__singles`); tracks with `:` are Maya reference duplicates, `pc_locator`/`player_locator` people spots,
  `gall` the gallery (M8f7), c08's `eff560` effect emitters (no model). Models live in `obj/`, `tree/`, `bg/` and
  (c07) `gimmick/` of `courtNN_obj_0/1.xb`; `_col` = collision.
- **Gallery** (`export_getagrip_gallery.py` → `npcs.json`, `npcs/`): `courtNN_gallery.xb` (not c09/c16)
  `gallery/gall00..06.psp.i3r` = one 1 × 1.95 m card (`pPlane1`, x ±50, y −5..190 cm, u along +x; gall00 empty),
  textures `gallNN_act0..7` (gall06 act0 only): act0 front, act1 back view, act2 head down, act3 waving, act4–7
  clapping; `.tat`s (material `gallery`) front = act0, back = act1, down = act2, clap = act3..7 at 0, 0.067, 0.1,
  0.167, 0.2 s. `setting/cNN_galleryarea.dat`: u32 n, n × (u32 id, f32 x, y, z, sx, sy, sz) metres Y up (sy = 2,
  the height); `cNN_gallery.csv` people per area for no / normal / many gallery. c09, c16: one whole-stand crowd
  model `courtNN_obj_0.xb …/gallery/gall00/cNN_gall00.psp.i3r` (haichi `cNN_gall00__01`), same tats. Sounds:
  `galsg_GL_[mw]NN_[ab].sgd` group_glee_0..2 / group_sad_0..1 / group_win / group_lose (identical in some sets),
  `co_seNN.sgd` clap_1 (one clap; none on c02, c16, c17). Who stands where and the cue timing: encrypted program.
- **Sky**: the ground's `bg01_sky` (c04/c06: `meshSky01/02`) node, or a separate `bg01_Sky` model (c07), plus
  `bg02_cloud*` with a looping motion: untextured, vertex-coloured, 200–500 m across → `sky.glb` (unlit).
- **Gimmicks**: `cNN_escape_gimmick.csv` / `cNN_break_gimmick.csv` name each (Japanese; the script's `GIMMICK`
  table maps them to `giNN_<Name>` folders: カメ = 甕 the urn, バルーン = c16's Tools, c20's nameless row = 工具)
  with a route in `cNN_route.dat` (u32 routes; each u32 n then n × (u32 route id, f32 x, y, z in **metres**)). Placed
  at the route's first point, turned by the csv's default angle, looping a resting motion (Stay, Swim, WingBeat …).
  The reactions (escape along the route at the csv speed, break into `_b01`) are code: not exported. Folders with no
  csv row (Swallow, Weeds, koishi, Bird, dolphin, Can, Banana, Snow, Wolf, pool, seito, watari, Squirrel, Dragon,
  WTigers, phantom, Jumbo …) are spawned by the program: listed in each `todo`, not placed.
- **Behind Get a Grip's camera, in front of HST's**: HST's match camera rests 41 m from the centre (eye ~12 m up,
  ~39 m behind the net), further back than the PSP's; set pieces Get a Grip keeps behind its camera then stand
  between HST's eye and the court. c17's `ob13_NORMA` (placed 30 m behind one baseline, with a motion → gimmick.glb)
  has 17 m opaque black cables (`code01`, an ordinary opaque material record, not additive) rising around its core
  9–12 m in front of HST's eye: solid black bars over the match view. The script drops every gimmick.glb island
  with a corner inside HST's resting view within 20 m of either end's eye (`clear_view`; listed in `todo`): only
  those cables, on all 16 courts. Further out, every placed gimmick instance with a vertex inside that view behind
  the near baseline is named `…__clear` (standard §2; listed in `todo`): HST hides it while it stands between the
  eye and the court, so it's still there from the far end, in cut-aways and replays. That is what keeps c05's
  basket goals (4.8 m, 7.2 m behind each baseline, ~21 m from the eye, square over the view's middle) out of the
  match view. Gimmicks that come with only a break motion (`_b01_`: the goals) stand still; they used to loop it,
  falling over every 2.8 s.
  court.glb has the same problem with buildings: HST's eye stands inside c05's street block behind the +z baseline
  (the whole turned view was its facade), outside c02's hall and c16's studio (their end walls and c02's roof over
  the court) and just above c09's house roof. The script splits every court.glb island that a line from a resting
  eye (either end) to the playing area passes through (HST's own 9×9×2 lines) into its own `<node>_<k>__clear`
  child (listed in `todo`); an island reaching into the playing area (a shell round the court) splits into its flat
  faces first. The net, ground decals (< 0.5 m) and pieces over the court between its ends (c01's pine bough) stay.
  c02 10 pieces, c05 7 (the building, the +z wall with its graffiti and ivy, the −z fence), c09 2, c16 6, c17 2
  (the additive glass partitions), the other 11 none.
- **Settings** `1_courtsetting.xb`: `court.csv` (Shift-JIS; stem, GRASS/HARD/CLAY, indoor), `courtlight.csv` (row =
  court number; ambient, light 0/1 colour + direction toward the light, Y up → `sun`/`fill`), `fogsetting.csv` (near/
  far amount, near/far distance, colour; off when both amounts are 0 → `fog`). `playerlight.csv`/`balllight.csv` are
  the same on every court; `camera_time.csv` is per-gimmick cutaway timing.
- **Sound**: `900_sound/020_courtNN.xb` `BGM/bgm_court_NN` and `stream_SE/env_coNN` (the ambience loop); loop
  points from `vgmstream-cli -m` on the raw `.sgh` + `extracted/.../.sgb` side by side. `cNN_se.csv` (one-shot birds,
  bells, buzzers) is a template copied between courts whose cue names are in no bank: noted in `todo`.
- **Additive materials**: in each material's 0x3a-byte texture record (type 0x26, `i3d.Material.raw`) byte +0x24 is
  0x11 instead of 0x10 on additive draws; +0x31 = 2 and +0x33 = 0x10 always go with it (38 of 2558 records in
  `200_court`, no mixed cases; +0x31 = 2 alone is on 4 plain grounds/roofs). Flagged: light pools (`c01_yamate_light`,
  `c13_hiyoko_light01`, `c15_ob01_lightmask`), lamp rays and window light (c02, c08 `gaslamp02`), water glints
  (`c03_ob18_mizu`, `c04_resort_waterAdd`, c06's water/rainbow/fog, c13's pool ripples), fireworks (c15), c20's
  `bg_cloud02`, and c17's glow layers (`plates`, a `court` copy over the opaque court, `ob13` pieces). The textures
  are mostly black, so drawn plainly they are black patches (yamate's octagon). → `<name>@add`, BLEND.
- **Two-texture materials** (baked shadows): a material record (0x25) can hold two texture records (0x26); each 0x55
  batch of its mesh then holds one 0x4f per texture, in that order, the second drawing the same triangles again with
  its own UVs (`i3d.Material.passes`, `Prim.pass_`; 185 of 5013 batches in `200_court`, never more 0x4f than
  textures). The second texture's +0x24 is 0x12 on the grounds' baked shadow maps (`c01_yamate_shadow00/01`,
  `c03_baked01`, `c04_resort_baked`, `c05_GroundShadow`, `c07_baked`, `c08_castle_baketex01`, `c15_baked01`,
  `c18_china_shadow00`): black where lit, bright in shadow, so subtracted → `<name>@sub`, BLEND. 0x11 (additive) on
  c08's statue `c08_refmap02`, c09's chair highlight (untextured) and c16's `roof01` glow → `@add`. Read as one pass,
  the shadow pass was a second opaque copy of the ground in the court texture at the shadow map's UVs, z-fighting
  over the real one: why c01, c03, c04, c05, c07, c15 and c18 showed their lines only in fragments (and c04 looked
  low-res). The court textures carry the lines on all 16 (a quarter court per 512² texture).
- **Layout**: same surface as `court.csv`, then the HST court with the nearest flat run-off (shorter end and side,
  log ratio); a crude metric, the numbers are in `layout_why`.
- `201_court/` is a lower-detail copy of the same courts (`data/adcourt`, fewer textures): not exported.
- Validation: Khronos validator 0 errors / 0 warnings on all 47 glbs; top views of all 16 checked by eye.
