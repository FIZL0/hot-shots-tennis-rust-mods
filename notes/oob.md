# Hot Shots Golf: Out of Bounds (PS3, Clap Hanz 2007) — playable characters

Exporter: `tools/oob2gltf` (Python 3: numpy, scipy, Pillow). No Rust, no game data in the tool.

```
python3 tools/oob2gltf/export.py                          # all 17 characters x 6 costumes + anims + PNGs (~3 min)
python3 tools/oob2gltf/export.py --pc 0 --costume 0       # one model (+ that character's anim file)
python3 tools/oob2gltf/export.py --no-anims --no-textures # models only
python3 tools/oob2gltf/check.py MODEL.glb out.png                       # bind pose, front/side/back
python3 tools/oob2gltf/check.py MODEL.glb out.png ANIMS.glb CLIP t0 t1  # posed by a clip (+ its morph weights)
python3 tools/oob2gltf/check.py --face MODEL.glb out.png                # head close-up: neutral + every target at 1
```

`check.py` re-reads the exported `.glb` (independent of the REM/MOT code path), skins on the CPU and rasterises
textured views with numpy (applies morph targets, incl. sparse accessors). All 119 outputs pass `gltf-validator`
(npm `gltf-validator`, `validateBytes`) with 0 errors / 0 warnings, morph targets and weight animations included.

## Outputs (`out/`, git-ignored)

| What | Where |
|---|---|
| Models (mesh + skeleton + skin + base colour/normal maps embedded) | `out/models/oob/<slug>/<slug>_cNN.glb`, NN = costume 00–05 (102 files) |
| Animations (skeleton + untextured `face` morph mesh of costume 00 + every clip, with morph-weight channels) | `out/anims/oob/<slug>.glb` (17 files, 82–86 clips each) |
| Face morph check sheets (head close-up, neutral + each target at weight 1) | `out/models/oob/_face_check/<slug>.png` (all 17) |
| All textures of each costume as PNG (incl. `_o`, `_s`, `_n`, portrait `face_pcNN_cNN`) | `out/textures/oob/<slug>/cNN/*.png` |

Slugs: `pc00_jasmine … pc16_gloria` (see roster). Anim files share node names/hierarchy/rest pose with the models
(node `i` = REM node `i`), so a clip from `anims/oob/<slug>.glb` plays on any costume of that character, and Biped
bone names (`Bip01Pelvis`, …) match across all characters.

## Roster

From `xbdata/kikkawa/menu/profile_txt.xb0/.../profile/profile2/pcNN.dat` (name, title, country). `ccNN.dat` there are
the 7 caddies (not exported).

| pc | name | | pc | name |
|---|---|---|---|---|
| 00 | Jasmine (England) | | 09 | L.J. (USA) |
| 01 | Nick (USA) | | 10 | Kate (Secret) |
| 02 | Sophie (France) | | 11 | Dino (Italy) |
| 03 | Bjorn (Sweden) | | 12 | Anya (Russia) |
| 04 | Sasha (USA) | | 13 | Suzuki (Japan) |
| 05 | Fernando (USA) | | 14 | S. Maruyama (Japan) |
| 06 | Sonia (Secret) | | 15 | Alex (USA) |
| 07 | Felipe (USA) | | 16 | Gloria (Russia) |
| 08 | Bloom (Brazil) | | | |

## Where things are (`out/files/oob/PS3_GAME/USRDIR/xbdata/...`)

| What | Where |
|---|---|
| Body, costume `cc` | `ueno/pc/pcNN/pcNN_cCC_0_core.xb/data/ueno/cgpc/pc/pcNN/pcNN_tTT_cCC.rem` (+ portrait `data/ueno/inpane/chara_face/face_pcNN_cCC.dds`) |
| Its textures | `ueno/pc/pcNN/pcNN_cCC_0_tex.xb/data/ueno/cgpc/pc/pcNN/*.dds` |
| Other LODs/variants (not exported) | `_0l_core` (same REM under `cgpc/pc_l/`, near-identical), `_1_3_core`, `_2_3_core` (`real/rpcNN_..._lv2.rem`, low LOD), each with `_tex` |
| Gameplay motions | `ueno/pc/pcNN/pcNN_motion.xb/data/ueno/cgpc/pc/pcNN/motion/*.{mot,mor,uva}` + `cgpc/ku/kuNN/kuNN_*.{mot,mor}` |
| Character-select motions | `pcNN_motion_menu.xb/.../menu/pcNN/charsel/chr_pcNN_{lp,ok}.mot` |
| Results-screen motions | `azuma/prize/pc/pcNN.xb/data/azuma/result/motion/pcNN/rslt_{wait,win,vict,loss,loss_2,clap,get}_pcNN.{mot,mor}` |
| Hole-result cameras / props | `pcNN_others.xb` (`ca_*.cam`, `ko_*.rem`) |
| Lobby avatars (chibi, 28 nodes) + their motions | `nakazawa/avatar_*.xb`, motions `nakazawa/avatar_common.xb/.../avatar/motion/aba00_*.mot` |

Clip families per character (pc00 durations): `ad_*` address (1.4–2.8 s), `sw_*` swings (`w`/`i`/`p` wood/iron/putt,
`f`/`h` full/half, `kn` knock-down), `st_*` stance/idle-at-ball loops, `ta_*` (`wi` = win?), `re_*_p_NN`/`re_*_wi_NN`
shot reactions (0.4–1 s), `ga_*_{ea,bi,pa,bo}_rNN` hole-result celebrations (eagle/birdie/par/bogey, ~1.5 s),
`ka_*` (club/green/gallery), `kuNN_{an,aw,cl,di,ga,gl,ha,sh,su}` short emotes (angry, …, clap, …, happy, shy?,
surprise; same codes as the Fore caddie set), `chr_*_lp` character-select idle loop, `rslt_*` results screen
(win/victory/loss/clap/wait/get). `avatar_aba00_*` are the lobby-avatar clips (wa = walk, ju = jump, si = sit, …)
put on each character — rotations only, pelvis translation scaled by pelvis height; low fidelity (chibi rig).
**There is no full-size walk/run clip for the playable characters** (the game never walks them).
Tennis-useful: `chr_*_lp`, `st_*` (idle), `rslt_win/vict/loss/clap/wait`, `ga_*` celebrations, `kuNN_*` emotes,
`re_*` reactions.

## Formats (all big-endian; strings are `u32 length + bytes`, no terminator, no padding)

### `.rem` model — confidence: high for everything exported

```
0x00 u32 ?(0x6d)  f32 5.0  f32 30.0  f32 50.0  u32 ?  u32 ?  u32 0  u32 0
0x20 u32 nTex;  nTex × { str dds_name; 8 bytes 0 }
     u32 nTexObj; nTexObj × { str name ("file274"); i32 self, tex_index, 0, 0, kind (0 colour, 1 _s, 2 _o), 0,0,0 }
     u32 nMat;    nMat × { str name; 42 words (168 bytes):
                   f32[4] diffuse, f32[4] ambient?, f32[4] specular, f32[4] emissive?, f32 power, ...,
                   +35*4 i32 slot count, +36*4 i32[6] slots (texobj index or -1):
                   slot0 colour map, slot1 `_o` (8-bit alpha-only), slot2 `_s` (8-bit), slot4 `_n` normal map }
     ... mesh blocks, cloth/spring data, morph blocks (interleaved, see below) ...
     node tree (starts at "\0\0\0\x08SMF2Root"), then dynamics (spring-bone) records to EOF
```

Material names carry flags: `__ds` = double-sided, `__ShadowF` = (shadow-related). `_o` = 8-bit occlusion-ish mask,
`_s` = specular mask (both DDS with DDPF_ALPHA, 8 bpp, which Pillow rejects — decoded by hand in `dds.py`).

**Mesh block** (found by signature scan in `rem.py: _find_meshes`; the bytes between meshes hold cloth/spring
setups (`h_mimi`, `hane1`, `skirt`, `uwagi` …, not decoded) and morph blocks (decoded, see below), so the scan locates each block
instead of walking the file sequentially):

```
15 × i32 header ending right before the index count:
   [0] material index, [1] has tangents (0/1), [2] weights per vertex nw (1..3), [3] vertex count or 0, [4] flag, [5..] 0
u32 nIdx; u16 idx[nIdx]          triangle strips, 0xFFFE = restart; even/odd winding alternates; CCW front faces
streams, each { u32 n (= vertex count), u32 k (components), data }:
   pos f32x3, normal f32x3, colour u8x4 (almost always 255), uv f32x(2·sets) [one or more streams; set 0 = colour map],
   [tangent f32x3, binormal f32x3 if header[1]], joint u8 x nw (global node index, 255 = none), weight f32 x nw
```

Positions are in model space, bind pose; joints index the node list directly. Meshes whose material has no colour
texture (`futa`/`huta` "lid" caps, `pc00_Cloth`, `blinn1`, `notex`) are invisible helpers and are skipped.

**Node** (pre-order; parents from child counts; ends when all counted children are read):
`str name; f32[16] world (node→model); f32[16] inverse world; f32[16] local; i32 index; i32 flag; i32 0; i32 0;
i32 child count`. Matrices are row-vector (v' = v·M, translation in row 3); `world = local · parent.world`,
`inverse·world = I` (verified on all nodes). Space: metres, Y up, character faces +Z, its left at +X —
right-handed, same as glTF, so no axis change. Rig = 3ds Max Biped (`Bip01*`, 67 bones incl. `Nub`s and
`ForearmRoll`) under `SMF2Root → pcNN_Reference`, plus 3–53 per-character extra bones (hair `pony*`, earrings
`*_ering*`, cloth helpers `*__ClothSphere`, `iki__Breath__ref`, props). Node counts: 72–122.

### `.mot` skeletal motion — confidence: high

```
u32 0x28; u32 nNodes; u32 1,1,1; zeros to 0x48
per node: str name;
          rotation    u32 n; i32 time[n]; f32x4 quat[n]   (x, y, z, w)
          translation u32 n; i32 time[n]; f32x4 vec[n]    (w unused)
          scale       u32 n; i32 time[n]; f32x3 vec[n]
          u32 (1 or 3); then 64 bytes (u32 1,1,1, zeros) — except after the last node
```

Times are signed 3ds Max ticks, taken as 4800/s (keys every 80 ticks = 60 fps; some clips start at −400 ticks:
shifted to 0 in glTF). Values are the node's local TRS in the row-vector convention, so the glTF (column-vector)
rotation is the **conjugate** (−x, −y, −z, w). Biped translation tracks equal the bind pose except
`Bip01Pelvis` (carries the root motion/placement, e.g. stance offset from the ball); translation tracks of dynamic
bones hold values in some other space (they fling earrings/hair metres away), so the exporter keeps translation for
the pelvis only. Linear interpolation (keys are dense).

### `.mor` / `.uva` — confidence: high (every file in the game parses to the byte)

`.mor` (morph-weight anim): `u32 0x28; u32 nTracks; per track: str target ("blink_eye"); u32 n; i32 time[n];
f32 weight[n]`. `.uva` (UV-offset anim): `u32 0x28; u32 n; per track: str texobj name ("eye__ID"); u32 n;
i32 time[n]; (f32 du, f32 dv)[n]`. Times are ticks (4800/s) like `.mot`. They sit next to the `.mot` of the same
name (`ga_pc00_bi_r00.{mot,mor}`); a few have no `.mot` (`bs_pcNN_eye_00.mor` = a 0.1 s blink, 0→1→0, played on
its own). Every `.mor` track name exists in that character's target list except pc07 `sad_mouth3`, pc15 `close`
(ignored). Eye `.uva`s (`eye__ID` offsets of 0.1 in u) swap the eye texture cell, and are what makes e.g.
`laugh_eye` read as closed/happy — the geometry of some `*_eye` targets is subtle on its own.

### Face morph targets in `.rem` — confidence: high (solved)

Every mesh of the morph group (the face, plus teeth/tongue/skin/`hair`/`bandmetal` on some characters) carries a
target block right after its last stream; the shared name table follows the group's last block:

```
per morph mesh, right after its weight stream:
  u32 nTargets
  nTargets × { u32 n;  if n == 0: nothing else (target doesn't touch this mesh)
               else:   u32 target ordinal (= 0, 1, 2 … — this is what was misread as "vertex index 0");
                       u32 vertex_index[n]   (strictly increasing, indices into this mesh's render vertices)
                       f32x3 position_delta[n]   (model space, ≤ ~4 cm)
                       f32x3 normal_delta[n]     (base normal + delta is unit length to 1e-7) }
after the group's last mesh:  u32 nTargets; str name[nTargets]
```

The previous attempt read the ordinal as the first vertex index, shifting every delta by one vertex (hence the
tearing; it also left a 4·(n+1)-ish "unexplained" tail). No pre-split table, no remap, no half floats: deltas apply
directly to the split render vertices (duplicate split vertices each have their own entry). Verified by
symmetry (left/right mirrored deltas land on mirrored vertices), by normal unit length on all targets of all 102
files, and visually (contact sheets: closed surfaces, blink = eyes shut, smile = smile, mouth shapes open the lips
with the teeth/tongue following). Targets are identical across the 6 costumes of a character.

Target names (order = glTF target order) — **not** a common set; each character has its own list (12–21):

| pc | n | morph meshes | targets |
|---|---|---|---|
| 00 | 14 | face | blink_eye smile_eye smile_mouth anger_eye anger_mouth sorrow_eye wink_eye ayo_mouth i_mouth laugh_eye laugh_mouth puku_mouth doki_eye doki_mouth |
| 01 | 18 | face teeth | smile_mouth1 smile_mouth2 smile_mouth3 sad_eye sad_mouth2 sad_mouth1 smile_eye anger_eye2 anger_eye1 anger_mouth blink_eye u_mouth pe_mouth smile_mouth4 amaze_eye amaze_eye2 wink_eye amaze_mouth |
| 02 | 12 | face | anger_mouth sorrow_eye sorrow_mouth laugh_eye laugh_mouth muka_eye muka_mouth blink_eye chu_mouth smile_eye smile_mouth anger_eye |
| 03 | 15 | face | a_mouth i_mouth u_mouth n_mouth smile_mouth laugh_mouth blink_eye laugh_eye shy_eye sad_eye scowl_eye surprise_eye smile_eye angry_eye wink_eye |
| 04 | 21 | face teeth | blink_eye wink_R_eye wink_L_eye smile_mouth smile_eye anger_eye anger_mouth sorrow_eye sorrowA_mouth sorrowB_mouth amaze_R_eye amaze_LR_eye amaze_L_eye amaze_mouth smileB_mouth smileB_eye out_tongue_mouth u_mouth o_mouth base smileC_mouth |
| 05 | 15 | face teeth (`_blinn31`, untextured, not exported) | test talk_mouth2 anger_mouth sad_mouth2 sad_mouth1 smile_mouth1 smile_mouth2 talk_mouth1 smile_eye anger_eye sad_eye smile_mouth3 smile_mouth4 anger_eye2 face1 |
| 06 | 14 | face teeth | blink_eye smile_eye smile_mouth anger_eye anger_mouth sorrow_eye sorrow_mouth wink_eye laugh_eye laugh_mouth surprise_eye surprise_mouth u_mouth o_mouth |
| 07 | 12 | face teeth | smile_mouth1 smile_mouth2 smile_mouth3 talk_mouth sad_mouth1 sad_mouth2 close_eyeL close_eyeR smile_eye anger_eye1 anger_eye2 sad_eye |
| 08 | 17 | face tongue hair | blink_eye smile_eye anger_eye smile_mouth sorrow_eye henoji_mouth anger_mouth sorrow_mouth ayo_mouth i_mouth clench_mouth openM_mouth openL_mouth smileCls_mouth miken_eye provocation_mouth provocation_eye |
| 09 | 17 | face skinhead bandmetal teeth | smile_eye blink_eye frownL_eye frownR_eye smileB_mouth smile_mouth smileL_mouth sorrow_mouth sorrow_eye anger_eye anger_mouth tong_mouth narrow_mouth a_mouth i_mouth u_mouth o_mouth |
| 10 | 14 | face | a_mouth i_mouth u_mouth smile_mouth laugh_mouth angry_mouth blink_eye surprise_eye smile_eye laugh_eye angry_eye worry_eye sad_eye pucker_mouth |
| 11 | 18 | face tooth tongue | smile_mouth blink_eye anger_eye sorrow_eye smile_eye nihil_mouth upL_mouth anger_mouth sorrow_mouth ayo_mouth i_mouth U_mouth clench_mouth openM_mouth openL_mouth beaten_mouth beaten_eye nihil_eye |
| 12 | 15 | skin face tooth tongue | smile_eye anger_eye sorrow_eye wink_eye laugh_eye surprise_eye blink_eye smile_mouth i_mouth kiss_mouth anger_mouth ayo_mouth laugh_mouth surprise_mouth shout_mouth |
| 13 | 21 | face teeth | pain_eye pain_mouth o_mouth Lsmile_mouth Rsmile_mouth anger_mouth anger_eye vexing_eye vexing_mouth smile_eye smile_mouth joy_mouth joy_eye close_eye uplip_down Lbrow_up Rbrow_up Lbrow_down Rbrow_down narrow_mouth close_mouth |
| 14 | 16 | face | smile_mouth smile_mouth1 doki_eye doki_mouth smile_eye anger_mouth sorrow_eye sorrow_mouth awa_eye awa_mouth anger_eye ayo_mouth laugh_eye laugh_mouth blink_eye i_mouth |
| 15 | 17 | face | smile_eye laugh_eye a_mouth n_mouth i_mouth laugh_mouth u_mouth surprise_eye smile_mouth sad_eye pucker_mouth blink_eye wink_eye cry_eye sad_mouth angry_mouth angry_eye |
| 16 | 14 | face teeth | blink_eye wink_eye a_mouth i_mouth u_mouth laugh_eye laugh_mouth smile_mouth surprise_eye angry_eye angry_mouth sorrow_eye sorrow_mouth surprise_mouth |

`blink_eye` exists for all but pc05/pc07/pc13 (pc07: `close_eyeL`+`close_eyeR`, pc13: `close_eye`, pc05: none —
`smile_eye`). Targets never used by any `.mor`: pc04 amaze_L/R_eye, anger_mouth, base, out_tongue_mouth,
wink_L_eye; pc05 face1, smile_mouth4, test; pc06/pc11 anger_mouth; pc09 i_mouth, narrow_mouth.

Render check (`check.py --face`, all 17 characters, every target at weight 1, read back from the `.glb`): no tears
or holes anywhere; expressions read as named (blink/wink/close shut the eyes, smile/laugh/joy curve the mouth,
a/i/u/o/ayo/shout open it with teeth/tongue following, brow targets move the brows).

### DDS

Standard DDS: DXT1 (15k), DXT5 (900), DXT3 (48), and 8-bit alpha-only (9.5k, `_o`/`_s`). Colour maps are not
flipped (UV origin top-left, as glTF).

## glTF mapping

- One `.glb` per costume: all REM nodes as glTF nodes (TRS decomposed from the local matrix, transposed), one skin
  over all nodes (`inverseBindMatrices` = the REM inverse matrices, last column forced to exact 0,0,0,1), one
  mesh with a primitive per REM mesh. JOINTS_0 u8 (node index), WEIGHTS_0 normalised (≤3 influences in the data).
- Materials: base colour = slot 0 (embedded PNG), normal map = slot 4 + TANGENT (from the file tangent,
  w = sign((n×t)·binormal)) when the mesh has tangents; `alphaMode MASK` (0.5) when the colour map has alpha;
  double-sided for `__ds` and alpha-tested materials; metallic 0, roughness 0.8. `_o`/`_s` only as PNG files.
- Animations: rotation for every animated node, translation for `Bip01Pelvis`, scale when ≠ 1; LINEAR.
- Morph targets: the morph-group primitives are a separate mesh `face` on node `face` (same skin) — so the body
  primitives don't need zero targets — with `weights` = 0 and `extras.targetNames` = the game's names exactly.
  Each target has POSITION and NORMAL deltas as **sparse accessors** (no base bufferView); a target that doesn't
  touch a primitive (n = 0) is an all-zero accessor without bufferView. Body = node `mesh`, face = node `face`.
- Anim files also carry the `face` mesh (untextured, costume 00 geometry; all costumes have identical targets) and
  each clip's `.mor` as one `weights` channel on node `face` (all targets resampled at the union of key times,
  missing targets 0; LINEAR). `.mor`-only files (`bs_*_eye_00` blinks) are weight-only clips. `.uva` tracks are in
  `animation.extras.uva = [{texobj, times, offsets: [[du, dv], …]}]` (times shifted like the clip; texobj name
  matches the REM texobj, e.g. `eye__ID` — not applied to any texture transform).

## Comparison with the HST (PS2) player skeleton

HST `pc00_t00_c00.MDL` has 70 nodes: a `Bip01` root + 52 Biped bones. OOB has the same 52 Biped bones under the same names
(spaces removed in both), so **bone names map 1:1 for all 52 HST Biped bones** (Pelvis, Spine/1/2, Neck, Head,
Clavicle/UpperArm/Forearm/Hand, 5 fingers × 3, Thigh/Calf/Foot/Toe0 per side). It is **not** 1:1 as a tree:

| | OOB | HST |
|---|---|---|
| Extra Biped bones | `HeadNub`, 10 `Finger*Nub`, 2 `ToeNub`, `L/RForearmRoll` (Hand's parent) | `Bip01` root; `Racket` (child of RHand) |
| Clavicle parent | `Bip01Spine2` | `Bip01Neck` |
| Thigh parent | `Bip01Pelvis` | `Bip01Spine` |
| Hand parent | `ForearmRoll` | `Forearm` |
| Root | `SMF2Root → pcNN_Reference → Pelvis` | `Bip01 → Pelvis` |
| Model space | Y up, left = +X, forward +Z | Y **down**, left = −X, forward +Z (= OOB rotated 180° about Z) |

Proportions are close (both metres): Jasmine OOB vs HST pc00 — pelvis height 0.858 / 0.828, head 1.255 / 1.224,
hand reach 0.51 / 0.56, ankle 0.131 / 0.144. So retargeting should go by bone name with world-space
(or bind-relative) rotations rather than copying local rotations, because the reparented clavicles/thighs and the
inserted ForearmRoll change the local frames; drop or merge the Nub/Roll bones, and add a `Racket` socket on RHand.

## Gaps

- `.uva` eye UV offsets are exported as extras only (no KHR_texture_transform); which material/texobj they drive
  (`eye__ID`) has to be wired up by the consumer.
- Cloth/spring-bone setup data (hair, skirts, earrings simulate in-game); exported as plain skinned bones in bind pose.
- LOD/`_l` variants, clubs (`ueno/club`), caddies (`kikkawa/caddie`), avatars' bodies.
- Tick rate 4800/s is the 3ds Max default and gives plausible durations, but is not confirmed from the executable.
- `ad_*`/`st_*` pelvis translation includes the in-game placement offset relative to the ball (e.g. x −0.58,
  z −0.65); strip root motion when using them as idles.

## Mod data: stats, voices, reactions

`tools/rerig/oob_data.py` (stats(), MAP, style(pc), heights(), voices(pc), reactions(pc); run it for a summary of all 17).

**Stats.** The source is `ueno/common/main.xb0/data/ueno/ability/player.dat` ("ABI_PLAY", big-endian). It holds 17 records of 5 f32 + 7 i32, with the offsets at 0x30.
- The floats are the character-select bars in order: power, control, impact, spin, side. The names come from charaselect `chrsel_prmset.dbo`. The E–S rank letters are computed in code, which is encrypted.
- Control is a spread multiplier, so lower is better:
  - club.dat and ball.dat ("ABI_CLUB", "ABI_BALL", same field order) pay for +power with +control.
  - The help text calls 1.2 and 1.3 "poor" and "terrible" control.
  - stats() therefore gives `control = 2 - control_spread`.
- Ints 0–4 are curve (+1 draw, −1 fade), rough, bunker, rain and approach (−1 weak, +1 good). Int 5 is always 4. Int 6 is sex (0 = f).
  - These meanings were read off `ookubo/menu/menu_common.xb0/data/text/menu_help.to` strings 500–516. Those strings are in select order: pc 0 1 2 3 13 4 7 6 8 5 9 10 11 12 14 15 16.
  - The `__main__` check asserts that every weakness the text names matches the flag.
- Heights come from profile2 `pcNN.dat` line 5 (ft'in"). They run from Bjorn 137 cm to L.J. 216 cm.
- The play class comes from the help text: All-rounder → オール, Big Hitter → ビッグ. Control, Spin and Special describe shot quality and get no タイプ.

| TParam | source | why |
|---|---|---|
| Serv/Strk/Voley POW | power | drive power multiplier |
| Strk/Voley/Serv CON | control (inverted) | shot spread |
| ショット ウサギ/カメ IMP | impact | impact-zone size (novices biggest) |
| Top/Drop SPIN | spin | backspin multiplier |
| Slice SPIN | spin + side | side = how much the character curves the ball |

There is no golf data for speed, stamina, agility or reach.

**Voice banks (SGXD).**
- SEQD layout:
  - The group count is at +0xc. Some banks give a larger count with zero table offsets, so skip those.
  - Each group table is `[?, count, offsets…]`. Bit 31 of an offset is a flag.
  - A note is `d0|d2, n, n BCD digits` = program·128 + key. The RGND region with that key gives the wave (`wave+1` = vgmstream's `NNN.wav`, checked against the WAVE sample counts).
- The pitch shift is key + 12 − root − fine/128. Measured per chosen file:
  - pc00 and pc07: 0.
  - pc15 and pc16: +0.53 semitones.
  - All other banks: +5.55 semitones (root key+6, fine 0x3a). These are probably 32 kHz recordings labelled 44.1 kHz, so the exported wavs play about 27% slow and low.
  - pc00's multi-part cues also reuse one fragment at +6 and +8.
  - This is the root-note pitch issue `tools/audio.py` is fixing; oob_data only reports it.
- `ga_sg_pcNN` has the same 58 slots (group 0: 42; group 1: 16 second takes) for everyone. The cue names are each actor's script lines (pc01 04A–38E, Felipe 20A–61; pc00's are partly out of order), so **the slot is the event**.
- The profile voice bank `me_pro_pcNN` uses one numbering for all 17 characters. Its groups match the profile "Play Animation" page:
  - Victory Pose = sg (0,29) (0,30) (0,31) (0,33).
  - Reaction = (0,10) (0,28) (0,40) (0,19).
  - Taunts = `ga_ya` lines 140–150 (yaji).
  - (0,29)–(0,34) and (1,9)–(1,14) are the six hole-result celebrations, two takes each. They are multi-part cues with delays timed to the `ga_*` clips. pc02 and pc10 name one of them Rare_Gattsu.
- The rest is unlabelled: no event table exists outside the encrypted HSG5PS3.self. The other banks:
  - `ga_ev` is a subset of sg.
  - `ga_vs` holds lines 70–84 (versus).
  - `ga_pz` holds lines 100–134 (results/prize).
  - None of them is signed (won or lost).

| HST program | OOB source | basis |
|---|---|---|
| 0 strong shot, 3 dive | sg (0,6) (1,3) (0,2) | shortest lines in every bank (~0.1 s): duration heuristic |
| 1 good shot | profile "Reaction" set | unlabelled reactions, heuristic |
| 4 whiff | sg (0,38) (0,13) | next shortest: duration heuristic |
| 7 point won | profile "Victory Pose" set (4) | data |
| 9 set won | second takes (1,9)–(1,13) + rare guts (0,32) | data (same family) |
| 2, 6, 8, 10 | — | no mis-hit, partner call or losing line is identifiable |

For each cue the longest note's wave is used, because celebrations play 2–17 fragments.

**Reactions** (`out/anims/oob/<slug>.glb`, 60 Hz). The meanings come from the names and are checked against each clip's face-morph channel: smile/laugh vs anger/sorrow/sad.

| HST | clip | frames |
|---|---|---|
| re_gu | `kuNN_ga` (guts pose) | 30–45 |
| re_di | `kuNN_di` (disappointed) | 35–40 |
| re_gu_set | `ga_pcNN_bi_r00` (birdie) | 85–90 |
| re_di_set | `ga_pcNN_bo_r00` (bogey) | 90–95 |

- The alternatives are `rslt_win` (120 frames) and `rslt_loss` (90). `re_*_p/wi` are shot reactions with mixed faces.
- The pelvis carries root motion: 0.07–0.56 units of horizontal travel. package.py pins it.
