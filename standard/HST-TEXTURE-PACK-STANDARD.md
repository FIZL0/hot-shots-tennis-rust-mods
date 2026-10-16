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
- Any other field is ignored.

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

A pack named in neither line is on, above the listed ones, so a new install lands on top. The opentennis Installed
tab will edit these lines (M5b). Until then, edit them by hand while the game is closed.

The *Texture Replacements* setting (Settings → Graphics) is the master switch: off, or with the Original look, no
pack is read. Packs are read when a match or the menu starts, so a change to the order applies from the next start.
