# HST court and umpire mod standard (v1, draft)

What a custom **court** or **umpire** for the Hot Shots Tennis remaster (`HST-Remastered`) provides. Characters are
`HST-CHARACTER-STANDARD.md`; this file shares its folder layout (§1 there), glTF rules (§2 there: embedded `.glb`,
game space = metres, **Y down**, root node `game_space` rotated `[0,0,1,0]`) and voice format (§5 there: one
`voice/<program>_<key>.wav` per take, any rate, mono or stereo).

The one rule both kinds keep: **a mod changes looks and sound, never play.** A court mod plays as a disc court's
layout and an umpire mod times its calls as a disc umpire does, so a match (and its replay, rollback and online
sync) runs exactly as on that disc court with that disc umpire, whether the mod is installed or not. A player
online without the mod gets the disc court / disc umpire it names.

Status: the manifest fields and the umpire voice table are fixed; the loader lands in steps (HST-Remastered
`plan/M8f.md`): umpire voices M8f3, umpire model M8f4, court visuals and sound M8f6, court NPCs M8f7. Until a step
lands its files are ignored, not rejected.

## 1. Kind

Every `mod.json` may carry `"kind"`:

| kind | what | standard |
|---|---|---|
| `character` (or absent) | a player | `HST-CHARACTER-STANDARD.md` |
| `court` | a venue | §2 here |
| `umpire` | a chair umpire | §3 here |

Any other value is a kind this loader doesn't know yet (e.g. `textures`, HST-Remastered M5a): it is skipped
quietly, not reported as broken. The character select only lists `character` mods; the court select lists `court`
mods, the umpire select `umpire` mods. Store metadata (`meta.json`) carries the same `kind`.

## 2. Court mod

```
mods/<id>/
  mod.json
  court.glb            the venue: everything drawn (ground, stands, buildings, props), static
  sky.glb              optional: the sky dome/backdrop, drawn behind everything, follows the camera's position
  gimmick.glb          optional: animated set pieces (flags, fountains, boats), each animation looping
  npcs.json + npcs/    optional: the people (§2b)
  sound/ambience_<n>.wav  optional: looping background layers, all played at once
  sound/bgm.wav (or .ogg)  optional: the court's music, looped
  previews/court.png   optional: the court select's picture (640×360 RGBA PNG)
```

```json
{
  "standard": 1, "kind": "court", "id": "gag_c01_yamate", "name": "Yamate", "source": "Hot Shots Tennis: Get a Grip court01",
  "layout": 3,
  "light": {"sun": [0.3, -1.0, 0.4], "sun_colour": [1.0, 0.95, 0.85], "ambient": [0.45, 0.45, 0.5], "fog": null},
  "bgm_loop": [0, 0]
}
```

- `layout` (0–10, the `--court` number / court select order): the **disc court whose collision, lines, net,
  surface bounce, judging, umpire chair, serve placement, camera and change-of-ends this court plays with**. Read
  from the player's disc, never shipped. Pick the disc court with the same surface (0, 1, 2, 8 clay; 4, 5, 7, 9
  grass; 3, 6, 10 hard: `SURFACE` in `play/main_menu.rs`) and a similar run-off.
- `court.glb` is in the layout court's game space (the same origin and axes as the disc court's own models; Y
  down). Line it up against the layout court's model: lines and net must sit where the layout's are, since the
  ball bounces and is called there, and the ground must not rise above the layout's playing surface. Drawn as the disc court's own models are
  (materials as character §2; alpha cut-outs `MASK`, see-through `BLEND`); no skin.
- `light`: the scene light (direction in game space, colours 0–1 linear); `fog` `null` or `{"colour": [r,g,b],
  "near": m, "far": m}`. Absent: the layout court's.
- Sound: absent `bgm` → the layout court's BGM; absent ambience → the layout court's court bank sounds. Ball
  bounces and net/prop hits keep the layout's material sounds (they come from the collision materials). `bgm_loop`:
  loop start and end in samples (0, 0 = the whole file).
- Optional, informational: `layout_why` (why that disc court), `surface` (`clay`, `grass`, `hard`, `carpet`: shown
  in Browse; must agree with `layout`), `time` (`day`/`night`), `todo`.

### 2b. Court people (`npcs.json`)

Spectators, ball kids, line judges, mascots: drawn and animated only, never touching the ball or the players.

```json
{
  "models": {"fan_a": "npcs/fan_a.glb", "ballkid": "npcs/ballkid.glb"},
  "people": [
    {"model": "fan_a", "pos": [12.0, 0.0, -3.5], "facing": [-1.0, 0.0], "role": "gallery"},
    {"model": "ballkid", "pos": [0.0, 0.0, 13.2], "facing": [0.0, -1.0], "role": "ballkid"}
  ]
}
```

- Each model is a skinned `.glb` (own skeleton allowed) with animations named by **cue**: `idle` (required,
  looped), and any of `cheer`, `clap`, `groan`, `point`, `rally` (watching a long rally), `serve` (quiet before a
  serve), `change_ends`. A cue the model lacks plays `idle`.
- `role`: `gallery` (cued like the disc gallery: cheer on a point won, groan on an error, clap on a game),
  `ballkid`, `linejudge` (turns its head with the ball; `point` on an out call), `mascot` (like gallery, bigger
  reactions). The cues follow the match the way the disc gallery's do (HST-Remastered `play/npcs.rs`), so they fire
  on the same ticks; they read the match, never write it.
- `sounds` (optional): `{"cheer": ["npcs/cheer_0.wav", …], …}` per cue, picked at random.

## 3. Umpire mod

```
mods/<id>/
  mod.json
  voice/<program>_<key>.wav   the calls (§3a); any missing → the donor's
  umpire.glb                  optional: model + motions (§3b); absent → the donor's model
  previews/umpire.png         optional: the umpire select's picture (384×480 RGBA PNG, transparent background)
```

```json
{
  "standard": 1, "kind": "umpire", "id": "gag_ump00", "name": "Umpire 00", "source": "Hot Shots Tennis: Get a Grip gag_vc00",
  "donor": 4,
  "voice": "voice/"
}
```

- `donor` (0–4, the `--umpire` order: 0 Chika, 1 Suzuki, 2 Lily, 3 Robot Tennis, 4 Anna): the disc umpire whose
  **call timing** the match uses (each word's length decides when the next word and the next phase start), whose
  voice fills any call the mod doesn't ship, and whose model is drawn when there's no `umpire.glb`. The mod's own
  clip plays in place of the donor's take but never moves the timeline: keep each clip about as long as the
  donor's (a longer one is cut when the next word starts).
- Optional, informational: `donor_why`, `calls` (the list of `program_key` it ships, for Browse's "n of 24
  calls"), `language`, `todo`.

### 3a. Calls

The umpire speaks from three programs (HST-Remastered `hst-sim/src/umpire.rs`). Ship one wav per key you have:

| program | key | call |
|---|---|---|
| 0 | 0–3 | the server's score, first word: love, fifteen, thirty, forty |
| 0 | 4–7 | the receiver's score, second word: love, fifteen, thirty, forty |
| 0 | 8 | "all" (second word of fifteen all, thirty all) |
| 0 | 9 | "deuce" |
| 0 | 10 | "advantage" (first word) |
| 0 | 11 | the server's side (second word after advantage / game / set) |
| 0 | 12 | the receiver's side (second word after advantage / game / set) |
| 0 | 13 | "deuce" again (a second deuce in a game; not used on court 5) |
| 1 | 0 | "out" |
| 1 | 1 | "fault" |
| 1 | 2 | "double fault" |
| 1 | 3 | "let" |
| 1 | 4 | "net" (a rally ball into the net) |
| 2 | 0 | "tiebreak" |
| 2 | 1 | "game" (first word, then 0_11/0_12) |
| 2 | 2 | "set" (first word, then 0_11/0_12) |
| 2 | 3 | "change ends" |
| 2 | 4 | "game, set and match" |

24 calls. A source game's umpire usually names the winner ("game, Emi") where HST says the side: map its generic
line, or leave the key to the donor. Check each clip says the call of its row (a speech-recognition transcript, as
`tools/voice_lang.py` does for language) before shipping it.

### 3b. Model (`umpire.glb`)

- One skinned model in game space, seated: the chair's seat at the origin, facing +Z (toward the court centre; the
  match places and turns it at the layout court's chair, mirrored on the courts whose chair is on the other side).
  Bring the chair in the model, or leave it out and the disc chair stays.
- Animations: `idle` (looped), `turn_r` and `turn_l` (turned toward the right / left end after a point, held), at
  60 Hz key times. The head joint named `head` (or `Bip01 Head`) follows the ball during the rally on top of them.
