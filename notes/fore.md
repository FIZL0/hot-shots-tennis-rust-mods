# Hot Shots Golf Fore! (PS2, SCUS-97401) — characters

Exporter: `tools/fore2gltf` (Rust; depends on HST-Remastered's `hst-data` + `hst-sim` by path).

```
cargo build --release --manifest-path tools/fore2gltf/Cargo.toml
B=tools/fore2gltf/target/release/fore2gltf
$B hst  /home/ryha/repos/HST-Remastered/context/xb out/models/hst   # HST reference rig (pc00 costume 0)
$B fore out/files/fore out                                           # all Fore characters (≈25 s)
$B info <file.mdl>                                                   # print the node tree
$B retarget <mdl> <mtl> <out.glb> <ani2…>                            # Biped motions onto a model, names matched sans spaces
```

## Where things are (`out/files/fore/<archive>.XB/<entry>`)

| What | Where |
|---|---|
| Body, costume `cc` of character `NN` | `PC/PCNN/PCNNcc.XB/data/pc/pcNN/<v>p/pcNN_tTT_cCC.{mdl,mtl,MTI,noi}` |
| Golf motions (address, swings, reactions) | `PC/PCNN/PCNNSW00.XB` (costumes 0–3) / `PCNNSW04.XB` (4–7): `ad_*`, `sw_*`, `re_*`, `tu_*` `.ani/.mor` |
| Hole-result celebrations | `PC/PCNN/PCNNccxx.XB`: `ga_pcNN_{ea,bi,pa,bo}_rKK.{ani,mor,uva,mta}` + camera `ca_*.cam` + sometimes a prop `ko_*.mdl` |
| Results screen | `RESULT/PCNN/COLcc.XB/data/result/{win,lost,up,clap}_NN[c].{ANI,MOR}` |
| Character-select poses | `MENU/M_CHAR/COL0|COL4/MCNN.XB/data/menu/smf/player/{win,vspose}_NN[c].ani` (+ menu copy of the model) |
| Clubs | `PC/PCNN/CLUB/CLkk.XB`: `clkk_tTT_{w,i,p}.mdl` + `club0k.tm2` |
| Caddies (not playable) | `KC/KCNNCcc.XB/data/kc/kcNN/01p/kuNN_c00.mdl`, motions `kuNN_{aw,gl,an,di,su,sh,ha,cl,ju}.ani` |
| Character names | `ZZBIN/SYSTEM.BIN` (in `extracted/fore`), 0x40-byte records at 0xfde40 |

Each character has **two body meshes**: costumes 0–3 share the `01p` MDL (only the MTL/MTI change), costumes
4–7 share the `05p` MDL. Their skeletons differ in the extra (non-Biped) bones for 22 of 24 characters, and a few
motions differ, so motions are exported per body variant.

`.ani` here is HST's ANI2 format byte for byte (ticks per frame 80 = 3ds Max 4800 ticks/s at 60 Hz); every one of
Fore's character `.ani` parses with `hst_data::ani::parse`. `.MOR` = HST's MOR. `.UVA`, `.MTA`, `.NOI`, `.cam` present
but not exported.

## Roster (pcNN → name)

From SYSTEM.BIN's character table, record `i` = pcNN `i`; verified: each record's first byte (body type) equals the
`tTT` of that pcNN's model file for all 24, and the renders match (pc22 is Ratchet, pc11 Z is a robot, pc07 a bulldog).

| pc | name | type | pc | name | type | pc | name | type |
|---|---|---|---|---|---|---|---|---|
| 00 | Phoebe | t00 | 08 | Maya | t03 | 16 | Toni | t03 |
| 01 | Mike | t01 | 09 | Falcon | t03 | 17 | T-Bone | t04 |
| 02 | Emma | t07 | 10 | Renee | t02 | 18 | Lin | t00 |
| 03 | Sam | t03 | 11 | Z | t10 | 19 | Louise | t00 |
| 04 | Misaki | t00 | 12 | Mel | t05 | 20 | Zeus | t03 |
| 05 | Brad | t06 | 13 | Allan | t03 | 21 | Hubert | t12 |
| 06 | Chaos | t08 | 14 | Tiffany | t00 | 22 | Ratchet | t11 |
| 07 | Regis | t09 | 15 | Kamala | t00 | 23 | Jak | t03 |

## Skeleton vs Hot Shots Tennis

**Same 3ds Max Biped, same topology, same bone axes** (bones run along local −X, Y down, feet at the origin, same
units: HST pc00 pelvis at 0.83, Fore pc00 at 0.72). Differences:

- Names: Fore keeps Biped's spaces (`Bip01 L Thigh`), HST's are stripped (`Bip01LThigh`). Match with spaces removed.
- All 53 HST `Bip01*` joints exist in every Fore skeleton with the same parents, except: **pc07 Regis** has no
  `Finger02/12/22/32` and no fourth finger (`Finger4*`); **pc22 Ratchet** has no `Bip01 Neck` (Head and clavicles
  hang off `Spine2`).
- Extras: Fore adds `Bip01 Footsteps`, Biped nub dummies (`Dummy01…`), hair/cloth/costume bones (`Bone001…`,
  `Body`, `skirt`, `Lhair`, …: 18–58 per model); HST adds `Racket`, `s_body`, `pony`, `face`, `Bone0001…` etc.
- Proportions vary per character (Emma and Regis are child-/dog-sized: pelvis ≈ 0.25), but the ANI player scales
  position keys by bone length (`hst_sim::pose::Clip`), and rotations are full local rotations in the shared Biped
  frames.

Verified: `retarget` of HST's `mo_pc00_run_f` and `sh_pc00_f_t` onto Fore Phoebe renders correct running / forehand
poses with no fix-ups. **Fore models drop straight onto HST motions** (rename tracks sans spaces). A `Racket` joint
has to be added (HST: child of `Bip01RHand`, local t ≈ (−0.085, 0.085, −0.041) for pc00).

## Export (`out/`)

- `out/models/hst/pc00_c00.glb`: HST pc00 costume 0 + racket (rigid mesh under `Racket`) + 47 skeletal motions
  (HST motion table order; ball paths/dummies dropped; doubles team reactions co01–05 from `PCDATA/PCCG0.XB` not included).
- `out/models/fore/pcNN/pcNN_<name>_cCC.glb`: 24 × 8 = **192** models (mesh, skeleton, skin, textures, face morphs).
- `out/anims/fore/pcNN_<name>_{c00-03,c04-07}.glb`: **48** files, 30–32 motions each (1466 total), on that variant's
  skeleton with the costume 0 / 4 mesh. Motions: `ad_*` address/idle stances (`t00/t01`, `i/w` = iron/wood, `_f`),
  `sw_*` swings (`w_d/w_f/w_m/w_h`, `i_f/i_h`, `p_f/p_h`; w/i/p match the club models' wood/iron/putter), `re_*`
  reactions (`bw ga lp os tp`), `tu_*_w`, `ga_*` eagle/birdie/par/bogey celebrations, results `win/lost/up/clap`,
  menu `win`/`vspose`. No walk/run exists for Fore players. Face `.MOR` tracks are exported as morph-weight channels.

glTF layout: node `game_space` (rotation 180° about Z: game Y-down → glTF Y-up, character faces +Z) holds the joint
tree; joints are named as in the MDL (unreadable Shift-JIS names → `nodeN`); `body` mesh node at scene root, one
primitive per MTL material, `KHR_materials_unlit`, `doubleSided`, OPAQUE (the remaster draws characters opaque —
texture alpha is kept in the PNGs), REPEAT/CLAMP from the MDL wrap modes. Inverse binds = inverse of the MDL bind
matrices. Animations are the game sampler (squad / Hermite / bone-length scale) baked per game frame as LINEAR.
To use in game space drop `game_space`'s rotation.

Validation: `gltf-validator` 0 errors, 0 warnings on all 241 files (infos only: unused TEXCOORD on untextured
primitives). Software renders checked (bind pose, HST idle/run, Fore win/swing/celebration, several costumes).

## Known gaps

- `.UVA` (eye/mouth texture scroll), `.MTA` (material anims), `.NOI` (hair/cloth noise deformer) not exported.
- `ga_*` props (`ko_*.mdl`) and cameras (`ca_*.cam`), clubs, caddies (KC), menu-only models (`MMCHAR/top_ladyNN`) not exported.
- `ga_*` celebrations carry root translation (the character walks off its spot).
- Vertex colours clamped to 1.0 (PS2 0x80 = 1.0; values above brighten); VU1 per-bone normals merged into one normal.
- Material blend tags (`@add`/`@sub`) and GS alpha test not mapped.
- Anim files duplicate the costume mesh (kept so they are viewable); every primitive carries all morph targets
  (zeros where unused) because glTF requires equal target counts.
