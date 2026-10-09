# Hot Shots Tennis Rust Mods

Tools that pull the playable characters out of other Hot Shots games and turn them into character mods for the
Hot Shots Tennis (PS2) remaster, [Hot Shots Tennis Rust](https://github.com/FIZL0/hot-shots-tennis-rust)
(HST below). They extract models, textures, animations,
faces and voices, then rerig each character onto HST's player skeleton.

The remaster has no mod loader yet. `standard/` defines what one should load.

| Game | Platform | Characters |
|---|---|---|
| Hot Shots Golf Fore! | PS2 | 24 × 8 costumes |
| Hot Shots Tennis: Get a Grip | PSP | 15 |
| Hot Shots Golf: Open Tee | PSP | 10 |
| Hot Shots Golf: Open Tee 2 | PSP | 22 |
| Hot Shots Golf: Out of Bounds | PS3 | 17 × 6 costumes |

**No game data is in this repo.** You supply your own disc images. Everything taken from them goes in `iso/`,
`extracted/` and `out/`, which git ignores.

## Layout

```
standard/   the character mod standard, the HST skeleton as JSON, and a step-by-step tutorial
notes/      format notes for each game: where things live, file layouts, rosters, known gaps
tools/
  unxb/       Rust: unpacks the `xe\0\x01` archives every game uses (little-endian on PS2/PSP, big-endian on PS3)
  fore2gltf/  Rust: Fore! (and HST's own) MDL/MTL/TM2/ANI/MOR to glTF, using Hot Shots Tennis Rust's hst-data crate
  psp2gltf/   Python: GIM/I3R/I3M/TAT (Get a Grip, Open Tee 1/2) to glTF; render.py is a small software renderer
  oob2gltf/   Python: REM/MOT/MOR/DDS (Out of Bounds) to glTF
  audio.py    every sound bank to WAV (vgmstream; Fore!'s PS2 banks are decoded directly)
  voices.py   folders of each character's voice lines
  rerig/      rerig onto the HST skeleton, conformance check, batch run, mod packaging
```

## Requirements

- Rust (cargo), and a checkout of [Hot Shots Tennis Rust](https://github.com/FIZL0/hot-shots-tennis-rust) next to this
  one as `../HST-Remastered`, since `fore2gltf` depends on its `hst-data` crate.
- Python 3 with numpy, scipy and Pillow.
- `vgmstream-cli`, `ffmpeg` and `7z`.
- Optional: `npx` with the `gltf-validator` npm package, for checking output files.

## Pipeline

```sh
# 1. Unpack each disc image into extracted/<game>/
#    (7z x on the ISO; Out of Bounds is a decrypted PS3 folder, linked as extracted/oob)
#    Game names: fore getagrip opentee opentee2 oob
cargo build --release --manifest-path tools/unxb/Cargo.toml
for g in fore getagrip opentee opentee2 oob; do
  tools/unxb/target/release/unxb extracted/$g/ out/files/$g
done

# 2. Models, textures, animations, faces -> out/models, out/anims, out/textures
cargo build --release --manifest-path tools/fore2gltf/Cargo.toml
tools/fore2gltf/target/release/fore2gltf fore out/files/fore out
tools/fore2gltf/target/release/fore2gltf hst ../HST-Remastered/context/xb out/models/hst   # HST reference rigs
python3 tools/psp2gltf/export_getagrip.py && python3 tools/psp2gltf/export_getagrip_faces.py
python3 tools/psp2gltf/export_opentee.py
python3 tools/psp2gltf/export_opentee2.py
python3 tools/oob2gltf/export.py

# 3. Audio -> out/audio, plus per-character voice folders in out/voices
for g in fore getagrip opentee opentee2 oob; do python3 tools/audio.py $g 8; done
python3 tools/voices.py

# 4. Rerig to the HST standard and package -> out/rerig, out/mods
python3 tools/rerig/make_skeleton.py   # standard/hst_skeleton.json, from the HST reference rigs
python3 tools/rerig/batch.py           # every character; writes out/rerig/<game>/check.txt
python3 tools/rerig/package.py         # out/mods/<game>_pcNN_<name>/
```

One model, with HST's forehand to look at:

```sh
python3 tools/rerig/rerig.py SRC.glb out.glb --preview out/models/hst/pc00_c00.glb --motions sh_pc00_f_t
python3 tools/rerig/check.py out.glb --face-sheet face.png
python3 tools/psp2gltf/render.py out.glb pose.png --anim sh_pc00_f_t --times 0,0.4
```

## The standard in short

All the detail is in `standard/HST-CHARACTER-STANDARD.md`. For how to rerig a character, see `standard/TUTORIAL.md`.

- **Model:** a `.glb` in HST game space (metres, Y down, facing +Z, under a `game_space` root).
- **Skeleton:** HST's 54 Biped joints with exact names, parents and bone axes. Proportions are free, and extra
  joints such as hair or skirts are allowed. HST motions store absolute local rotations, so the axes matter as
  much as the names.
- **Face:** morph targets named after HST's channels (`joy`, `anger`, `sorrow` and `doki`, each with `_eye` and
  `_mouth`, plus `blink_eye`). The PSP games swap face textures instead, so their mods carry a `face.json`.
- **Voice:** `voice/<program>_<key>.wav`, using HST's voice programs (serve/smash, stroke, mis-hit, dive, whiff,
  calls, post-point reactions).
- **`mod.json`:** the costumes, plus a donor HST character whose motions, faces, AI and stat sheet the mod uses,
  stat overrides, handedness and a `todo` list.

## Status

- **Rerigged:** 356 models from five games, all passing `check.py`. They're packaged as 87 mods, and all render
  intact.
- **Spot-checked by eye:** HST motions on one character from each game and on edge cases (a very small
  character, one with no neck bone).
- **Every game's mods** now carry stats ranked onto `TParam` (`params.override`, with `params_why`), an
  `ai_row` where the game names a play style, voices sorted into HST's programs (`voice_why` says which are
  heuristic), each game's own point/set reactions as `motions.glb`, Get a Grip's standard racket, and HST-size
  scaling with a head shrink. Per-game data modules: `tools/rerig/{gag_stats,fore_data,oob_data,opentee_data}.py`.
- **Still open** (also listed per character in each `mod.json` `todo`):
  - confirming handedness;
  - voice pitch for SGXD banks (Get a Grip, Open Tee, Out of Bounds): the region root note isn't applied yet.

Known gaps for each game are in `notes/<game>.md`.
