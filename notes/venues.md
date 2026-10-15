# Golf venues as tennis courts — Fore!, Open Tee 2, Out of Bounds

Survey for opentennis M8f10: which holes of Hot Shots Golf Fore! (PS2), Open Tee 2 (PSP) and Out of Bounds
(PS3) have room for a tennis court, and which umpires those games have. Tools: `tools/venues/` (Python 3 + numpy,
reads `out/files/<game>/` from `tools/extract.py`; no game data in the tools).

```
python3 tools/venues/venues.py                 # all three games (~2 min) -> out/venues/<game>.json + .log
python3 tools/venues/venues.py fore oob        # some of them
```

- `course.py` — the height map (`Hmp`) and HST-style placement (`plants`) readers (Out of Bounds' records are read
  in `venues.py`).
- `survey.py` — the court-spot search on one height map.
- `venues.py` — finds every hole's files per game, runs the search, writes per-hole results.

## Umpires

None. No game has a chair umpire, line judge or referee (no file or model named tennis/umpire/referee/judge/court;
golf has none). The nearest are the caddies (Fore! `KC/`, Out of Bounds `kikkawa/caddie`), which aren't umpires.
An umpire mod for these venues has to come from another game (Get a Grip, HST's own).

## Real tennis courts

Open Tee 2, **Nakagawa Public G.C.** (`crs/13`) hole 7: `hol07.xb/data/course/course13/hole/kasen_h07_s1111.psp.i3r`
draws a pair of tennis courts in its scenery. Render groups `sortOn____s__tennisnet` / `sortOff____s__tenniscover`,
node `net` (materials `net@cloth`, `netCover@cloth`, posts `tetu@metal`): two collinear nets ≈ 11.7 m long,
0.87–1.07 m tall, centre ≈ (13.9, −73.0) in psp2gltf's raw mesh space (×0.01, no flips), net running ≈ 25.3° off
mesh +X. In the net's frame the ground is `c13bare@mud` ±15.3 × ±15.8 m at height 4.48 (flat), the courts
`breakwator02@asphalt` ±15.3 × ±11.9 m (23.8 m long: one court length), edging `redge01@rough` ±16.9 × ±17.5 m and a
wire fence `kanami@metal` at ≈ 24.7 m. The spot isn't on the hole's height map (heights there vary by metres),
so it's scenery outside the play area; the mesh-to-height-map mapping isn't confirmed. It's the one venue in the
three games with a court already built: the first candidate for a court mod.

Looked at closer (opentennis M8f10a1): the playing surface is bare earth (`c13bare@mud`); the
`breakwator02@asphalt` pieces are the white lines, modelled as 0.1–0.2 m strips over the earth (no painted
texture); `redge01@rough` is a 1.6 m border. Two courts side by side, centres ±9.75 m along the nets; each net 11.74 m
(posts ±5.87 m), so no doubles alleys wider than HST's. Line rows in HST's game metres after the export: x 0.05,
4.015/4.115, 5.385/5.485; z 6.2/6.4, 11.585/11.685/11.885. The outer edges match HST's to the mm, and the court is
flat within 2 mm. The `+` court (along the net direction) is the flatter one, so it goes on HST's origin. Plant
records (HST's 0x40 format) map to mesh space as (x, y, z) → (−x, −y, z), checked against the tee marks.

Exported as `out/mods/ot2_c13_h07_nakagawa` by `tools/psp2gltf/export_opentee2_court.py` (`--court ±`, `--end ±`):
ground and scenery from the hole model, the kasen00 sky dome plus bg0's `p10` panorama and clouds (dropped 386 m so
the far bank sits at eye level; judged by eye), trees/huts/kei trucks/tee marks from the plant records, the course BGM
`at_c_07` and the hole's `co_40` ambience. Surface is **clay** (earth courts), and the layout is HST's Western (2) by the
closest-run-off rule. Light is the layout's; the hole's `envir_c13_h07.dat` isn't decoded.

No other course has courts: the string `tennis` appears in no other extracted file of the three games except a
profile text (Out of Bounds `pc16.dat`) and Open Tee 2's `body.bin` text.

## Height maps (`*.HMP`, all three games)

Same layout everywhere; Fore! and Open Tee 2 little-endian, Out of Bounds big-endian.

| Offset | Type | |
|---|---|---|
| 0 | f32 x0, f32 z0 | game-space corner of cell (0, 0) |
| 8 | u32 nx, u32 nz | cells along x, z |
| 16 | f32[nx·nz] | ground height per cell (game space, Y down like Fore!'s meshes) |
| 16+4n | u8[nx·nz] | lie per cell |

Both arrays x-major (row = x, column = z); a cell is 1.3 m. Checked against the placed pins/cups and tees: Fore!
≤ ~3 cm, Open Tee 2 ≤ ~18 cm, Out of Bounds ≤ ~0.1 m; against Fore!'s ground mesh, median 2 cm.
Lies: 0 off the map, 1 fairway, 27 water (all three; > 80 % of its cells flat), green 4 (Fore!, Open Tee 2) or 6
(Out of Bounds, under the cups). The others (2, 5, 12, 13, 21, 22, 48, …: rough, bunkers, paths, …) aren't named.
The map covers the playable hole only; scenery beyond it isn't surveyed.

Where they live:

- Fore!: `CRS/SSN0/HOLccHH.XB/database/courseCC/hole/*_hHH.HMP` (spring; the ground is the same every season).
- Open Tee 2: `xbdata/crs/NN/hmpHH.xb` (18-hole courses 01–06, 13–18) or `holHH.xb` (nine-hole 07–12, 19), path
  `data/course/courseNN/hole/*_hHH.HMP`.
- Out of Bounds: `xbdata/course/courseCC/holeHH.xb/data/course/courseCC/hole/*_hHH_*.HMP` (the `*_g.HMP` beside
  it is a separate green map, skipped).

## Placements

Fore! and Open Tee 2 use HST's 0x40-byte plant record (`hst-data` `layout.rs`): category = byte 2 + 0x11 —
17 tree, 18 prop, 19 structure, 20 billboard, 21 gallery, 7 pin, 11 tee. One `plant_*_0.dat` per hole.

Out of Bounds differs: big-endian, u16 category at 0 (0x14 tree, 0x15 prop, 0x16 structure, 7 cup, 8 tee), index
at +4, position f32×3 at +8, scale at +0x28; split per kind in `course/courseCC/half_p10.xb` (front nine) /
`half_p01.xb` (back nine), `data/course/plant/courseCC/<kind>/<kind>_cCC_hHH_0.dat`.

## The search (`survey.py`)

A spot fits when a 40 × 20 m rectangle (doubles court 23.77 × 10.97 m plus HST's smallest run-off: Wafu 8.2 m
behind the baselines, Alps 4.6 m beside the sidelines, rounded up), at any yaw 0–165° in 15° steps:

- lies wholly on the height map, with no water;
- varies in height by ≤ 0.5 m (a laid court slab at its highest point hides that);
- holds no blocker: tree 3 m, prop 2 m, billboard 3 m, structure 12 m around its origin, times its scale clamped
  to 1–4 (galleries don't block).

Thresholds and radii are judgement calls, not taken from any game. Per hole the result keeps the flattest spots,
their yaw, centre (x, z), height range and lie counts.

## Results (holes with a court spot / holes; flattest spot's hole)

### Fore! (`CRS/SSN0`, holes h00–h18; 13–15 have ten)

| Course | Name | Fits | Flattest |
|---|---|---|---|
| 01 hakone | Mt. Sakura C.C. | 15/19 | h01, fairway |
| 02 nangoku | Aloha Beach Resort | 18/19 | h00, fairway |
| 03 | Western Valley C.C. | 10/19 | h12 |
| 04 england | Bagpipe Classic | 17/19 | h00 |
| 05 america | United Forest G.C. | 16/19 | h01, fairway |
| 06 hokkaido | Northern Fox C.C. | 8/19 | h03 |
| 07 extra | Day Dream G.C. | 16/19 | h00 |
| 08 jungle | Wild Green C.C. | 11/19 | h05 |
| 09 china | Silk Road Classic | 12/19 | h09 |
| 10 carib | Blue Lagoon C.C. | 5/19 | h16 (0.37 m), fairway |
| 11 | Fujizakura C.C. | 2/19 | h14 (0.26 m) |
| 12 | Kawana Hotel G.C. | 5/19 | h02 (0.26 m) |
| 13 jap | Samurai Golf Club | 10/10 | h00 |
| 14 japan | (unnamed; likely mini-golf) | 10/10 | h00, green lie |
| 15 world | (unnamed; likely mini-golf) | 9/10 | h00, green lie |

Names from SYSTEM.BIN's course table (same order as the stems; it also holds a "Mini-golf 2" string).

### Open Tee 2 (`xbdata/crs/NN`)

| Course | Name | Fits | Flattest |
|---|---|---|---|
| 01 alps | South Alps C.C. | 5/18 | h12 |
| 02 kyoto | Autumn Pagoda G.C. | 5/18 | h14 |
| 03 med | Olive Coast C.C. | 17/18 | h01 |
| 04 egypt | Golden Desert G.C. | 10/18 | h06, fairway |
| 05 links | Royal & Links C.C. | 13/18 | h01 |
| 06 jurassic | Dino Park G.C. | 6/18 | h03 (0.16 m) |
| 07–12 | nine-hole versions of 01–06 | 4, 1, 8, 4, 7, 3 /9 | |
| 13 kasen | Nakagawa Public G.C. | 15/18 | h02 (real courts: h07 scenery, above) |
| 14 cp | Central Golf Square | 13/18 | h01 |
| 15 touge | Michinoku Pass C.C. | 6/18 | h04 (0.13 m) |
| 16 bali | Gamelan Island Resort | 10/18 | h10 |
| 17 ag | Fortress Yard G.C. | 4/18 | h12 (0.34 m) |
| 18 andes | El Andes G.C. | 5/18 | h16 |
| 19 western | (unnamed nine-hole) | 0/9 | h02 1.38 m |

Names from `msg1.bin`.

### Out of Bounds (holes h00–h19)

| Course | Name | Fits | Flattest |
|---|---|---|---|
| 00 practice | (copy of 06; no hole height maps) | — | |
| 01 georama | Highland Country Club | 14/20 | h00 |
| 02 okinawa | Okinawa Golf Resort | 19/20 | h00 |
| 03 eu | Euro Classic GC | 20/20 | h00 |
| 04 africa | Great Safari CC | 19/20 | h00, green lie |
| 05 fjord | Silver Peaks GC | 15/20 | h00 |
| 06 major | The Crown Links | 16/20 | h00 |
| 07 aussie | (name not found) | 19/20 | h00 |

Names from the help text and `challengeitem.csv`. Exact spots (yaw, centre, range, lies) per hole are in
`out/venues/<game>.json`.

## Making a court mod from a spot

A golf hole has no court lines, net or umpire chair: a mod built here lays its own court (slab, lines, net, chair)
at the chosen spot and moves the venue so that spot lands on HST's court origin, along the court's length
(standard §2: lines and net where the layout puts them). Export tasks in opentennis's plan (M8f10b–d) cover
the hole ground, sky/background, placed trees and props, and the laid court per game.

### Fore! (`tools/fore2gltf court`, opentennis M8f10a2)

```
cd tools/fore2gltf && cargo build --release && cd ../..
tools/fore2gltf/target/release/fore2gltf court out/files/fore out/venues/fore.json "iso/Hot Shots Tennis (USA).iso" out/mods [course…] [--end -]
```

Writes `out/mods/fore_cCC_<stem>/` (`mod.json`, `court.glb`, `sky.glb`) per course in ~1 s each. Per course:

- **Spot.** The flattest fitting survey spot (all holes, each hole's best yaws) whose ground the hole model draws
  (≥ 95 % of 0.5 m points under the slab): the mini-golf height maps (14, 15) run on as flat green well past the
  drawn holes. Course 14 has no such spot, so it isn't exported; 15 lands on h04.
- **Run-off.** Grown 0.5 m a side from the survey footprint (8.115 / 4.515 m) up to 15 / 10 m while the slab stays
  on the height map, off water (lie 27) and off-map (0), clear of placed objects and within 0.5 m of height. The
  survey's cell window can sit a cell off; where its footprint fails this 0.5 m check (06, 09, 11) the run-off grows
  from 3 / 2 m instead.
- **Layout.** Surface grass for every course (lawn); HST's grass court (Wimbledon 4, Kar 5, Jungle 7, Greece 9)
  with the closest run-off, |ln(back / min(+z, −z))| + |ln(side / min(+x, −x))|. Umpire chair at the layout's own
  plant position (from the HST ISO).
- **Ground height.** The highest point under the slab and 2 m round it, from the height map and from the hole
  model's near-level triangles within 1 m of it (vertices and every 0.5 m), goes 3 cm under the slab. Whole holes
  draw blended (PRIM ABE), so blending can't tell ground from decoration. The hole model is read by path: GRD's
  `data/arrow.MDL` sorts first, and `HOL…/holeend/` reuses the hole model's stem.
- **court.glb.** `fore_spot` (the venue: hole ground model, plant categories 17–20 placed with `world::place`;
  anything within 45 m of the court gets `__clear`), `court` (striped grass slab with skirts down to the ground,
  lines at HST's judging edges, net panel/tape/strap, posts at ±6.4 m, a simple umpire chair).
- **sky.glb.** The first in-season sky of the hole plus the course's `_clo` / `_acc` / `_bg`, BG`cc`0 (p10) for the
  front nine and h00, BG`cc`1 (p01) for the back nine where it exists; yaw and lift by HST's backdrop rule
  (course envir 0x450 yaws − hole heading, lifts from the hole envir, 370 without one).

| Course | Hole | Spot (x, z) yaw | Run-off +z −z +x −x | Layout | Notes |
|---|---|---|---|---|---|
| 01 hakone | h01 | (−53.1, −299.0) 0 | 15 15 10 5.0 | Jungle | fairway by the pond |
| 02 nangoku | h00 | (72.0, −136.8) 0 | 15 15 10 5.5 | Jungle | above the lagoon |
| 03 western | h12 | (−21.6, 93.9) 0 | 8.1 15 10 6.5 | Jungle | |
| 04 england | h00 | (69.2, −198.7) 0 | 9.6 8.1 10 6.0 | Jungle | between town houses (their backs are flat grey) |
| 05 america | h01 | (−14.5, −333.3) 90 | 10.6 11.6 8.0 8.0 | Jungle | |
| 06 hokkaido | h03 | (−107.7, −521.8) 120 | 12.5 6 4.5 10 | Greece | |
| 07 extra | h00 | (−144.2, −168.4) 135 | 15 15 6.0 10 | Jungle | in a fenced road cutting; road at both ends |
| 08 jungle | h05 | (−54.3, 20.2) 45 | 15 11.1 10 5.5 | Jungle | |
| 09 china | h09 | (−88.6, 10.0) 90 | 15 9.5 4 5.5 | Greece | on top of the fort wall; battlements beside |
| 10 carib | h16 | (22.8, −132.4) 135 | 8.6 9.1 5.5 6.5 | Greece | |
| 11 fujizakura | h14 | (−2.1, 73.9) 120 | 15 8 4 7 | Greece | |
| 12 kawana | h02 | (−2.2, −263.7) 90 | 12.1 10.6 5.5 5.5 | Jungle | |
| 13 samurai | h00 | (−83.7, −179.7) 0 | 15 8.1 10 10 | Jungle | on the beach; the slab overhangs the drawn sea |
| 15 mini_b | h04 | (−50.2, −28.2) 0 | 15 8.1 9.0 5.5 | Greece | flat panel by the sea |

Checked in HST by eye (`--play --singles --court-mod`, held eyes at both resting views and high above): slab,
lines, net and chair sit on HST's court, the umpire sits on the chair, the views are clear. Not done: Fore!'s
drifting clouds, creatures, galleries, pin flag and hole-end scenery, course music, a manifest light from the
envir files.

### Out of Bounds (`tools/oob2gltf/court.py`, opentennis M8f10a3)

```
python3 tools/oob2gltf/court.py out/files/oob out/venues/oob.json "iso/Hot Shots Tennis (USA).iso" out/mods [course…] [--end -] [--data DIR]
```

Needs `tools/fore2gltf` built (it reads the layout courts' umpire chairs from the HST ISO: `fore2gltf chairs`).
Writes `out/mods/oob_cCC_<stem>/` (`mod.json`, `court.glb`, `sky.glb`) per course in ~25 s each. The Fore! rules
above (spot, run-off, ground height, laid court, `__clear` within 45 m), with these differences:

- **Space.** OOB is Y-up metres, the height map in the hole model's own space (median |model y − HMP| 0.09 m);
  `oob_spot` turns it 180° about Z into HST's Y-down game space. The front nine (h00–h09, `_p10`) and the back
  nine (h10–h19, `_p01`) are separate worlds over the same coordinates (another nine's height map at the same x, z
  is a different height): every lookup stays in the spot's own nine.
- **Placements.** OOB's per-kind plant files cover only what each hole shows, so the spot takes every hole's files
  of its nine (plus the nine's `_out_` files), deduplicated by (category, index, position), where the hole's own
  ground model has vertices (10 m cells ± 1). Category 0x17 is billboards. A record's index is the position among
  the non-`_lvN` entries of its kind in `entry.txt`; placed by position, yaw (0x24, about +Y) and scale (0x28).
  Trees further than 60 m use their lowest `_lvN`.
- **Blockers.** Circles round each placement (tree 3 m, prop 2, structure 12, billboard 3, × scale 1–4), the
  vertices of props/structures/billboards within 80 m standing > 5 cm above the ground, and the hole model's own
  vertices > 0.3 m above the height map within 60 m (walls, steps and kerbs are in the ground model).
- **Surface.** Hard where > half the hole model's material samples under the slab are paved (names with asphalt,
  cart, road, concrete, paving, tile, brick, stone, parking, floor), else grass; HST's hard layouts are Park 3 and
  Extra 6. The laid hard court is a blue court on a green surround.
- **Textures.** Static `.rem` meshes (`static.py`), colour map = the first material slot that isn't a specular or
  normal map; alpha < 128 → MASK. The hole models' textures are loose files outside the xb archives
  (`PS3_GAME/USRDIR/data/course/courseCC/hole/*.dds`, `--data`); `plantmodel01.xb0` holds the billboards.
- **sky.glb.** The `bg/` models of the course (`_sky`, and `_bg` / `_clo` of the spot's nine) at the eye, turned
  with the venue, no lift (the envir files aren't decoded).

| Course | Hole | Spot (x, z) yaw | Run-off +z −z +x −x | Layout | Notes |
|---|---|---|---|---|---|
| 01 georama | h10 | (−88.9, −282.4) 0 | 15 15 10 6.0 | Extra (hard) | car park by the cart garage |
| 02 okinawa | h10 | (139.2, 43.5) 30 | 15 12.6 8.5 6.0 | Jungle | practice fairway on the cliff top, sea behind |
| 03 eu | h16 | (−211.7, 132.3) 150 | 15 11.6 8.5 6.5 | Jungle | windmill behind the far end |
| 04 africa | h00 | (410.0, 145.3) 0 | 10.6 10.6 6.5 10 | Jungle | on a round green |
| 06 major | h01 | (345.3, 99.5) 0 | 10.5 5.5 10 10 | Park (hard) | helipad by the manor house |
| 07 aussie | h00 | (−415.3, 245.6) 0 | 9.1 14.6 6.5 10 | Jungle | rough between red rock hills |

Course 05 (fjord) has no spot: all 41 survey candidates are blocked or not flat. Checked in HST by eye
(`--play --singles --court-mod`, `HST_WEATHER=0`, held eyes: play view, a resting view, low beside the court,
high above): slab, lines, net and chair sit on HST's court on the hole's ground, the venue upright around it. Not
done: plant words 0x14–0x20 (small angles, leans?), envir/light, sky lift, creatures, galleries, course music,
water shaders and multi-layer ground blends (one colour map each).
