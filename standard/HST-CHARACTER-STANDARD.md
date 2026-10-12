# HST character mod standard (v1, draft)

What a custom character for the Hot Shots Tennis remaster (`HST-Remastered`) must provide, so one loader can treat
it exactly like a disc character. It mirrors `crates/hst/src/character.rs` (`CharacterData`): a custom character
"only has to fill the same CharacterData". Machine-readable skeleton: `standard/hst_skeleton.json`
(regenerate: `python3 tools/rerig/make_skeleton.py`). How-to: `standard/TUTORIAL.md`.

## 1. Mod folder

```
mods/<id>/
  mod.json                 manifest (§6)
  model/<costume>.glb      one per costume, §2–§4 (c00 required)
  racket.glb               optional rigid racket in Racket-joint space (else the donor's)
                           (metres; vertices baked in that space: the loader reads POSITION/NORMAL/UV/
                           COLOR as stored and ignores node transforms. HST's rackets are 0.944 m butt to
                           tip along +Y, strings facing ±Z, grip 0–0.32 m; `racket.py` makes one from a
                           source game's racket, keeping its grip on the hand)
  textures/upscaled/<glb stem>/<image>.png
                           optional: one folder per .glb (costume or racket.glb), one PNG per embedded image,
                           named by the glTF image's `name` (else `image<index>`); drawn instead when the
                           "upscaled textures" setting is on, any size; missing files fall back to the embedded
                           one. `upscale_mods.py` makes them (with `sources.json`, the hashes it skips by; not for `"upscale": false`, §6)
  previews/<costume glb stem>.png
                           optional: the character select's picture of each costume (384×480 RGBA PNG, sRGB,
                           straight alpha, transparent background), shown while the cursor moves before the live
                           model loads. Without it the game draws one on first use and keeps it in its own cache;
                           `tools/rerig/previews.py` copies those bakes into the mods for shipping
  motions.glb              optional: the mod's own motions, drawn in place of the donor's (§6 `motions`)
  voice/<program>_<key>.wav  §5
  face.json                only for texture faces (§4b)
```

## 2. Model file (.glb, glTF 2.0)

- Scene root node `game_space`, rotation `[0,0,1,0]` (180° about Z). Everything under it is in **HST game
  space**: metres, **Y down**, feet at y = 0, character facing +Z (same as every exported HST character).
- One skin. Skinned vertices are in game space; inverse bind matrices are game space too. **Rest pose = bind
  pose** (node locals compose to the inverse of the IBMs).
- ≤ 4 influences per vertex (JOINTS_0/WEIGHTS_0), weights sum to 1.
- A mesh node without a skin rides the nearest joint at or above it, whole (PSP heads and faces).
- Materials: base-colour PNG embedded; `KHR_materials_unlit` allowed (the GS path lights per vertex anyway).
  Texture alpha is *not* coverage on HST bodies (it holds shading masks); mark real cut-outs `alphaMode: MASK`
  (alpha test, HST's ≥ 0x40) and see-through parts `BLEND` (HST's two-pass ≥ / < 0x70 with blending).
  `doubleSided: false` drops back faces. Highlights: `material.extras.hst_mtl = {"shininess": s, "highlight": h}`
  (the MTL's specular power and strength, as `hst-gltf` exports them); without it the material is matte.
- Normals: HST lights each vertex with its first influence's share of the normal on that joint and the rest on
  the weight blend of the others, i.e. exactly Σ wᵢ·Rᵢ·N.

## 3. Skeleton

The **54 core joints** of `hst_skeleton.json`, with exactly these names and parents (HST's 3ds Max Biped, spaces
removed): `Bip01` (root) › `Bip01Pelvis` › `Bip01Spine` › `Spine1` › `Spine2` › `Neck` › `Head`; clavicles under
**Neck**; thighs under **Spine**; `Hand` › `Finger0..4` with three segments each (`Finger0`, `Finger01`,
`Finger02`…); `Foot` › `Toe0`; `Racket` under `Bip01RHand`.

- **Bone axes must match HST's**: each joint's bind frame is HST pc00's frame swung onto the model's own bone
  direction (joint → its child). HST motions store *absolute local rotations* (`hst_sim::pose::Clip`), so a frame
  that differs (e.g. a rotation-reset rig) poses the mesh wrongly even with correct names.
- **Proportions are free.** The game scales motion positions to the model: `Bip01` by its rest height |y|,
  others by rest bone length, `Bip01Pelvis` not at all. HST's own range: `Bip01` height 0.58–0.95 m (see
  `characters` in the JSON). Keep `TParam` reach values (§6) consistent with the arm length.
- **Size to HST's cast** (`tools/rerig/sizing.py`, applied at packaging by re-rigging, so no mod.json field):
  `Bip01` height = HST's metres per cm for the character's sex (median `bip01_height / height_cm` over HST's
  standard bodies, `model_type` 0/4/5 in the JSON: women 0.005184, men 0.005322) × the source's own height in cm,
  then one factor per source game that gives the game's Gloria HST's Gloria's `Bip01` height (0.8554 m; she is the
  one character on HST's disc and in Get a Grip, Out of Bounds and Open Tee 2); relative heights stay the source's.
  Open Tee (no Gloria) takes Open Tee 2's sizes for the same ten characters; Fore! (no one shared) keeps its own
  model scale, the same engine units as HST. Chibi sources also shrink each head about `Bip01Neck` by its own
  factor: the game's head share of the way from 1 to the factor that would bring that character's head ratio
  ((top of head mesh − neck) / `Bip01` height, smallest over its costumes so a hat doesn't count) to HST's
  standard-body median (0.538), never above 1; the share is the one that makes the game's Gloria as tall head to
  foot as HST's (`top_height` 1.6547 m in the JSON), 0.909 for Get a Grip and Open Tee 2, else 0.5. Factors are in
  `out/rerig/<game>/sizing.json` and each mod's `size_why`. The donor is then the nearest
  `Bip01` height among HST's same-sex standard bodies.
- **Extra joints are allowed** (hair, skirts, earrings, accessories) anywhere below the core. HST motions don't
  drive them; they follow their parent, plus the sway of §3a or the spring of §3b.

### 3a. Sway (optional)

HST's hair, ribbons and skirts sway by `.NOI` deformers. `mesh.extras.noise = [{"name", "period", "rate",
"amp": [x, y, z]}, …]` lists a mesh's deformers; the vertex attribute `_HST_NOISE` (VEC2 float) gives each
vertex `[deformer index, share]` (share 0 = still). `hst-gltf` exports the disc's; `rerig.py` keeps them.
- `Racket`: where the racket's grip sits; the racket mesh is rigid in that joint's space.

### 3b. Spring bones (optional)

For sources whose hair simulates as bone chains (Out of Bounds) rather than `.NOI` noise. A joint node with
`extras.spring = {"limit", "stiffness", "gravity", "damping"}` is a point mass at that joint, hung on its parent; HST
steps it at 60 Hz after the pose and turns the **parent** to point at it:

- `limit` — degrees the mass may swing off the posed direction (0 = rigid);
- `stiffness` — share of the gap to the posed position pulled back each step (0..1);
- `gravity` — m/s², straight down in the world;
- `damping` — share of the last step's motion kept (0..1).

Missing keys default to 30, 0.5, 4.9, 0.83. A spring joint whose parent has none is its chain's **anchor**: pinned,
so a chain never turns the core joint it hangs on. Other keys are ignored (`oob2gltf` keeps the source's raw 16
words as `oob`). `rerig.py` keeps `extras.spring` on every joint it keeps. Visual only: the sim never sees it.

## 4. Face

### 4a. Morph faces (preferred — what HST uses)

Morph targets on the head/face mesh, names in `mesh.extras.targetNames`, **without** the PS2 object prefix
(HST stores `face\x01joy_eye`; mods store `joy_eye`; the loader matches the part after `\x01`):

| channel | required | meaning |
|---|---|---|
| `joy_eye`, `joy_mouth` | yes | happy (point won, win) |
| `anger_eye`, `anger_mouth` | yes | angry / frustrated |
| `sorrow_eye`, `sorrow_mouth` | yes | sad (point lost, loss) |
| `doki_eye`, `doki_mouth` | yes | flustered / surprised |
| `blink_eye` | recommended | blink (pc07 and pc13 have none) |

Weights 0–1, full expression at 1. HST plays the faces from the **donor's** `.MOR` tracks (§6) bound by these
names; extra targets (`smile_*`, `wink_eye`…) are kept but only play if the donor's tracks name them. A missing
required channel freezes that part of the face; fill it with the closest expression. `rerig.py` does this by
word (target name minus `_eye`/`_mouth`, side markers L/R, variant letters and digits), best first:
blink←close/wink, joy←smile/laugh/grin, anger←angry/vexing/muka/scowl/frown/clench, sorrow←sad/cry/worry/pain,
doki←surprise/amaze/awa/shy/open/o; left and right halves (`close_eyeL` + `close_eyeR`) are summed.

### 4b. Texture faces (PSP sources: Get a Grip, Open Tee)

These games swap one whole-face texture (eyes + mouth together) instead of morphing. `face.json`:
`{"materials": ["<glTF material>", …], "neutral": "<png>", "channels": {"joy_eye": "<png>", "joy_mouth": "<same png>",
…}}`. `materials` names the costume's face materials (Get a Grip: `<stem>_face0`; its mirrored halves `face`/`faceL`
are one material in the glTF). Each channel with a png is a weight driven by the donor's `.MOR` track of that name;
the loader shows the texture of the strongest channel above 0.5 (on a tie the first by channel name), else neutral. A `null`
channel stays neutral; other keys are ignored. The game's own per-motion swaps are in `out/anims/getagrip/face_tracks.json` if a mod
wants them exactly.

### 4c. Eyes (optional)

HST moves its eyes by scrolling the eye texture: a motion's `.UVA` keys a (u, v) offset on the model's eye node
(pc00 `s_me`, pc01 `eye`, …), added to the UVs of every part skinned to that node. A mod's eyes follow the donor's
eye track in either of two ways:
- keep the donor's eye node as a joint (same name) and skin the eye mesh to it (what a rerigged HST model does), or
- list the eye materials in `mod.json`: `"eyes": ["<glTF material>", …]`; every primitive with one of them takes the
  donor's eye offset, whatever its joints.

The offsets are the donor's, in UV units (pc00's inspect pose holds (−0.02, 0.02)), so lay the eye texture out for
them: the iris drawn where the shifted UVs land, with margin (wrap or clamp as the texture sampler says). Donors
whose track names no node of their own model (pc07) or that have none (pc13) never move their eyes, nor do their
mods'. Without either, the eyes stay still (the morph or texture face still plays). The eye track plays on the
select's inspect pose and its R2/L2 reactions.

## 5. Voice

HST plays per-character voice **programs** (each a set of keys = alternative takes) from
`SND/VOICE/PC/PCnnVCEk.XB0` (singles a/b, doubles a/b, 70/30 random). Ship `voice/<program>_<key>.wav`:

| program | when | keys |
|---|---|---|
| 0 | strong-toss serve / smash | 0–2 |
| 1 | good stroke shout | 0–4 |
| 2 | mis-hit | 0–2 |
| 3 | dive | 0–2 |
| 4 | whiff | 0–1 |
| 6 | partner / first-serve calls | 0–4 |
| 7–10 | post-point reactions (by reaction motion 0x2c–0x2f) | any |

(From `HST-Remastered/research/journal/2026-10-07-n3-audio/9-SHOUTS-FINAL.md`, `10-WHIFF-CALLS-FINAL.md`.)
A program you ship no wav for plays the donor's own disc takes (none at all: the donor's whole bank).
Get a Grip's labelled cues map almost 1:1: smash→0, swing→1, receive→3, point_get/point_lost→7–10, start→6.

## 6. mod.json

```json
{
  "standard": 1, "id": "gag_emi", "name": "Emi", "source": "Hot Shots Tennis: Get a Grip pc00",
  "costumes": ["model/c00.glb"],
  "donor": 0,
  "hand": "right",
  "params": {"base": 0, "override": {"Serv POW": 4, "SPE": 10}},
  "ai_row": 0,
  "face": "morph",
  "voice": "voice/"
}
```

- `donor`: HST character (0–13) whose **motions, `.MOR` faces, arm table, shot records and AI rows** are used.
  Pick by body type and play style (`research/characters.md`).
- `params`: `TParam.csv` row: `base` donor row, `override` by column header (e.g. `Serv POW`, `Strk POW`,
  `Voley POW`, `Top SPIN`, `Strk CON`, `SPE`, `STA`, `Agili`, reach `リーチ(cm)`, heights). Other games' stats are
  mapped once per game (PLAN M8), **by rank**: a character's position among its own game's cast on the source stat
  picks the value at the same position in HST's 14 rows of the mapped column, so values stay inside HST's balance
  (integer columns stay integers; `a/b/c` cells are whole HST cells); columns with no source stay the base row's.
  Keep the body-bound columns (contact/smash/serve heights, リーチ基点, collision) at the donor's, since its motions
  are played. Get a Grip's table: notes/getagrip.md (*Stats → HST TParam*); タイプ (オール/ベース/ネット/ビッグ) sets the
  select's play-style label.
- `ai_row`: the AIParam.csv row (and second-toss pick) the computer plays this character with; may differ from
  `donor` (e.g. the HST character of the same タイプ while the body donor is the nearest height).
- `hand`: `right`/`left` (the game mirrors left-handers, like Carol and Will).
- `upscale` (optional, default `true`): `false` for mods whose textures are already high-res (e.g. Hot Shots
  Golf Fore! players): `upscale_mods.py` skips the mod (the game still draws any `textures/upscaled/` it has).
- `motions` (optional): a `.glb` in the folder whose animations replace the donor's clips **on screen only**.
  Each animation is named by the motion without `_pc%02d` (`re_gu`, `re_di`, `re_gu_set`, `re_di_set`, `mo_ad00`,
  `sh_f_t`, … as `hst_data::ani::MOTIONS`, one the donor has) and keys the costume's joints by name with their
  local rotation and translation, in the costume's own terms (the costume's node tree, no meshes needed). Key
  times are seconds at 60 Hz (frame f at f/60), as the source plays it; the clip may run past the donor's (it is
  drawn on its own clock, holding its last frame or looping as the donor's motion does) but not stop short of it; gameplay (clip lengths, the
  arm table, serve toss, body hits, root paths, cut-away cameras) keeps reading the donor's clip, and a match
  plays out exactly as without it. Unkeyed joints hold their rest; the left-hand mirror applies as to the donor's.
  One file serves every costume: a key on a joint a costume lacks is skipped for that costume.
  `tools/rerig/motions.py` retargets a source game's motions (per-joint world rotation change from the shared bind pose; root
  from the pelvis, scaled by hip height; intro then loop played at 60 Hz: the whole intro, looped up to at least the donor's frames).
- `face`: `morph` (§4a channels), `texture` (§4b, needs `face.json`) or `none` (no face animation).
- `eyes` (optional): the glTF material names of the eyes, moved by the donor's `.UVA` eye track (§4c).
- The HST loader (`crates/hst/src/mods.rs`) rejects a mod with `<path>: <reason>` when the manifest is off
  (`standard` ≠ 1, a missing costume, `donor`/`base`/`ai_row` outside 0–13, `hand` not right/left, an `override`
  key that is no TParam column, an `eyes` that is not a list of names, a `motions` file that is missing, names no motion the donor has or is shorter than the donor's clip) or a costume fails §7's FAIL checks; WARN checks are logged. Buffers and images
  must be embedded in the `.glb`; it skips glTF accessor validation (older rerig output lacks POSITION min/max).
- Optional, informational: `donor_why`, `size_why` (how the height and head were set), `racket_why`, `source_stats` (the source game's raw stats), `params_why` (per overridden column: source stat, value, rank → HST value), `ai_row_why`, `motions_why`, `voice_counts`, and `todo`
  (what a human or agent still has to decide). A loader ignores unknown keys.

## 7. Conformance

`python3 tools/rerig/check.py MODEL.glb [--face-sheet face.png]` checks: root `game_space`; one skin; all 54 core
names and parents; rest = bind; each core bone's direction in its own frame within 10° of HST's (the axis rule of
§3); Bip01 height; feet at y = 0; ≤ 4 weights summing to 1 (FAIL on any of these); the face channels and
`blink_eye` (WARN — texture-face models warn by design, their faces are in `face.json`). The face sheet renders
neutral plus each channel at weight 1. Beyond the checker, a model conforms when an HST forehand and run render
without tearing or twisted limbs (`TUTORIAL.md` §2).
