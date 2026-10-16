# HST texture pack standard (v1)

What a **texture pack** for the Hot Shots Tennis remaster (`opentennis`, task M5a) provides: replacement images for
the disc's own textures (courts, menus, HUD, crowd, players' disc models), in any size and with any content.
Character, court and umpire mods carry their textures inside their `.glb` files instead (`HST-CHARACTER-STANDARD.md`,
`HST-COURT-UMPIRE-STANDARD.md`).

**A pack changes looks only, never play.** A match with packs on plays exactly as one without, and a lobby never syncs
them: each player sees the packs they have themselves.

## 1. Folder

```
mods/<id>/
  mod.json                                  manifest (§2)
  textures/<any folders>/<name>-<key>.png   one replacement per disc texture (§3)
```

A pack installs like a character mod: the folder in `mods/` beside the ISO, or a `.zip` of it through Add mod
(desktop and browser). A pack is refused (and logged) when its manifest is broken or it holds no key-named PNG.

Don't put files under `textures/upscaled/`: that folder is a character mod's upscaled set (character standard §1), and
the browser build deletes it from every installed mod.

## 2. mod.json

```json
{ "standard": 1, "kind": "textures", "id": "crimson_courts", "name": "Crimson Courts", "author": "you" }
```

- `standard`: `1`.
- `kind`: `"textures"`. Without it the folder is read as a character mod (and fails as one).
- `id`, `name`: 1–64 characters, shown as plain text. `author` is optional (up to 64 characters).
- `covers` (optional): what the pack changes, for the mod store's *Covers* filter. One of `"everything"`,
  `"courts"`, `"characters"`, `"menus"` (menus and the in-match HUD) or `"mixed"` (several parts, not all).
- `look` (optional): what kind of change it is, for the store's *Kind* filter. One of `"upscale"` (the disc's
  pictures at a higher resolution), `"recolour"` (same pictures, new colours) or `"new"` (new pictures).
- Both are read in any case; `"recolor"`, `"menus & hud"` and `"new look"` are taken too. A missing or unknown value
  only means the pack shows under the filter's *Any* and nowhere else; it is never refused for them. They change
  nothing in the game itself.
- Any other field is ignored.

```json
{ "standard": 1, "kind": "textures", "id": "crimson_courts", "name": "Crimson Courts", "author": "you",
  "covers": "courts", "look": "recolour" }
```

## 3. Textures

The files are the same as the remaster's `mods/texture-replacements/` folder (opentennis `docs/DEVELOPING.md`,
*Texture replacements*):

- `hst <iso> --dump-textures` writes every disc texture, at its native size, to `mods/textures-src/` as
  `COURT/05/…/<name>-<key>.png`. Edit or upscale those files and put the results in the pack's `textures/` under the
  same names, either in the same folders or flat.
- A file is matched only by its **key**: the 16 lowercase hex digits after the last `-`, before `.png` (the extension
  is not case-sensitive). The rest of the name and the folders are just for you. Within a pack, the first file of a
  key in path order wins.
- PNG, RGBA or RGB, **straight** (non-premultiplied) 0–255 alpha, any size. A 2× or 4× upscale and a full repaint both
  work.
- A pack only needs the textures it changes. A texture it doesn't have comes from the next pack down (§4).
- A PCSX2 hash-named pack is not a texture pack. Those go in `mods/texture-replacements/` as they are.

## 4. Stacking and order

Several packs can be on at once. For each texture the game takes the first match from:

1. the packs that are on, top first;
2. `mods/texture-replacements/` (desktop only: key-named files, then a PCSX2 pack);
3. the disc.

The order is saved in `settings.txt` by folder name under `mods/` (`/`-separated):

```
texture_packs = crimson_courts, hd_menus      # top first
texture_packs_off = old_pack                  # installed but off
```

A pack named in neither line is on, above the listed ones, so a new install lands on top. Mods → Installed →
Texture packs edits these lines (order and on/off); by hand, edit them while the game is closed.

The *Texture Replacements* setting (Settings → Graphics) is the master switch: off, or with the Original look, no
pack is read. Packs are read when a match or the menu starts, so a change to the order applies from the next start.

## 5. Making one

`tools/texpack.py` (this repo) builds the folder and `mod.json` from your edited files:

```
python3 tools/texpack.py EDITED/ out/mods/crimson_courts --name "Crimson Courts" --author you \
    --src ../opentennis/mods/textures-src --zip
```

It copies every key-named PNG of `EDITED/` (same names as the dump, any folders) to `textures/`, leaves out files
that are byte-identical to the dump's (`--src`), and writes `covers` and `look`:

- `--covers auto` (default): from the dump folders the keys come from (`COURT`, `COURTSET` = courts; `PC` =
  characters; `MENU`, `AZUMA/INPANE`, `AZUMA/PRIZE`, `SAITOU` = menus; ball, effects and the rest are none of these).
  One part → that part; courts, characters and menus together → `everything`; otherwise `mixed`.
- `--look auto` (default): `upscale` when every file is its original at a whole multiple (2× or more, same in both
  directions); otherwise nothing, so say `--look recolour` or `--look new`.
- Either can be given outright, or `none` to leave it out. `--zip` also writes `out/mods/crimson_courts.zip` (the
  folder inside) for Add mod and the store.
