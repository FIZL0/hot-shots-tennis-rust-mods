# Tutorial: rerigging a character to the HST standard (for agents)

Read `HST-CHARACTER-STANDARD.md` first. Work in `/home/ryha/repos/HST-MODS`; never commit `out/`, `iso/`,
`extracted/` (game data). Don't edit `HST-Remastered`.

## 0. Inputs you already have

| game | exported models | notes |
|---|---|---|
| Hot Shots Tennis (reference) | `out/models/hst/pcNN_c00.glb` (with all 47 motions) | `fore2gltf hst` |
| Fore! (PS2) | `out/models/fore/pcNN/*.glb` | same Biped as HST; `notes/fore.md` |
| Get a Grip (PSP) | `out/models/getagrip/pcNN_name/*.glb`, parts | rotation-reset rig, cm; `notes/getagrip.md` |
| Open Tee 1/2 (PSP) | `out/models/opentee*/…` | `notes/opentee.md` |
| Out of Bounds (PS3) | `out/models/oob/pcNN_name/*.glb` | clavicles/thighs reparented; `notes/oob.md` |

All use Biped joint names (with or without spaces) — that's what makes one tool work for all.

## Everything at once

```
python3 tools/rerig/batch.py      # every character of every game -> out/rerig/<game>/…, check.txt per game
python3 tools/rerig/package.py    # -> out/mods/<game>_pcNN_<name>/ (mod.json, model/, face/, voice/)
```

State as built (2026-10-08): 356 models (Fore 192, OOB 102, Get a Grip 30, Open Tee 10, Open Tee 2 22), all PASS;
87 mod folders. Each `mod.json` has a `todo` list of what's still open for that character. The steps below are what
those scripts do, for one character, and how to check and fix one.

## 1. Rerig

```
python3 tools/rerig/rerig.py out/models/getagrip/pc00_emi/pc00_emi_set3.glb out/rerig/gag_pc00.glb \
    --preview out/models/hst/pc00_c00.glb --motions sh_pc00_f_t,mo_pc00_run_f
```

What it does (`tools/rerig/rerig.py`, ~400 lines):
1. Converts the source to game space (`G·K`: glTF Y-up → Y-down, source units → metres via the skin's own
   mesh-to-world transform).
2. Maps joints by name (spaces removed). Missing core joints are **synthesized**: on the line to the next mapped
   joint at HST's ratio (e.g. `Spine2` between `Spine1` and `Neck`), else at HST's offset scaled to the model
   (finger segments, `Racket`, `Bip01`). The printout lists them.
3. Builds each core joint's frame as HST's frame swung onto the model's bone direction (single-segment fingers
   use the `…Nub` marker for direction). This is the step that makes HST's absolute local rotations pose the mesh.
4. Keeps every other node as an extra under its nearest kept ancestor; drops scene roots/locators above the core
   (their weights go to `Bip01Pelvis`).
5. Rebinds weights, rewrites IBMs, renames morph targets (drops the `obj\x01` prefix) and adds alias targets for
   missing face channels.
6. `--preview` copies the donor's motions, scaled as the game scales them, for checking.

## 2. Check it — always look

```
python3 tools/psp2gltf/render.py out/rerig/gag_pc00.glb out/rerig/gag_pc00.png --anim sh_pc00_f_t --times 0,0.4 --views front,side
```

Open the PNG with the Read tool. Compare with the donor itself
(`render.py out/models/hst/pc00_c00.glb … --anim sh_pc00_f_t`). Look for: limbs pointing the same way as the
donor's, no stretched/torn vertices, feet on the ground, hands closing on the racket position. Also try
`mo_pc00_run_f`, `sh_pc00_serve_t`, `re_pc00_gu` (win), `re_pc00_di` (loss).

Then `python3 tools/rerig/check.py out/rerig/gag_pc00.glb --face-sheet face.png` and look at the face sheet.

Known failure signs and fixes (the first three bit us already and are handled):
- *Forearm stretched toward the body, hand floating*: a helper joint *between* core joints (OOB's
  `Bip01RForearmRoll` between Forearm and Hand) was dropped as a root helper, so its weights fell to the pelvis.
  Only nodes above the topmost mapped joint may be dropped.
- *Crash "non-positive determinant"*: a mirrored helper (3ds Max, Open Tee 1); stored as a negative scale.
- *Crash on accessors*: sparse morph deltas (OOB) — `rerig.read` densifies them.
- *Arm twisted along its length*: the source bind roll differs a lot from HST's; check the source's palms
  orientation in bind pose. Swing-only alignment keeps HST's roll.
- *Mesh explodes*: wrong K/units (multiple skins with different mesh spaces) — print `skin_binds` K per skin.
- *Part floating / static*: its weights sit on an extra joint whose ancestor was dropped; check the extras tree.
- *Face doesn't move*: no targets, or names don't match §4 — print `mesh.extras.targetNames`.

## 3. Faces

- Fore!, HST: morph targets present → rerig maps them. Check `extras.targetNames` contains the 8 required.
- Out of Bounds: morph targets decoded (`notes/oob.md`), 12–21 per character with their own names; rerig maps
  them by word (standard §4a). Some channels simply don't exist for some characters (check.txt WARN lines).
- Get a Grip: texture faces → `package.py` writes `face.json` from `out/models/getagrip/faces.json` (§4b) and
  copies the textures into `face/`.
- Open Tee 1/2: texture faces too, but the expression textures aren't labelled yet (`face: "none"` + a todo).
  Do it like Get a Grip: contact sheet of `out/textures/opentee*/…face*.png`, label, write `face.json`.

## 4. Package

`package.py` makes `out/mods/<id>/`: costumes, `mod.json`, voices. What it can't decide is in each `todo`:
- `donor` is the HST character with the nearest `Bip01` height — a placeholder. Pick by play style and body
  (`research/characters.md`) and set `params.base`/`ai_row` to match.
- `params.override`: map the source stats (`source_stats` for Get a Grip; Fore/OOB/Open Tee stats aren't
  extracted yet) onto TParam columns, one mapping per game (PLAN M8).
- Voices: Get a Grip is mapped (smash→0, st_ji→1, st_nb→2 (guess), receive→3, swing→4, start/call/go/chance→6,
  point_get→7, point_lost→8, set_get→9, set_lost→10). Other games are in `voice/unsorted/`: listen, then copy
  into `<program>_<key>.wav`. Upscaled textures: run `tools/chainner/upscale.chn` (in HST-Remastered) on the
PNGs and put them in `textures/upscaled/`.

## 5. Report

Per character: mapped/synthesized joints (from the rerig printout), face channels present/aliased, the render
PNG paths you checked, and anything odd.
