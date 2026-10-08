# Audio extraction notes

Tools: `tools/audio.py <game> [jobs]` (everything -> `out/audio/<game>/<relpath>/NNN.wav`, failures in `FAILED.txt`),
`tools/voices.py` (relative symlinks -> `out/voices/<game>/pcNN/`). Identical files (md5) are converted once and hard-linked.
Rel paths are relative to `out/files/<game>` or `extracted/<game>`. Streams: `.sgd`, `.sgh`+`.sgb` (opened through the `.sgb`; the
`.sgh` may sit in an xb while the `.sgb` is a raw disc file, the script pairs them by name), `.at3`. NNN = 1-based subsong.

## Results (wav files incl. hard-linked dups / failures)
| game | wavs | failed | what failed |
|---|---|---|---|
| fore | 11686 | 76 | BGM/sequence-only banks (`s_NN`, `cNN_N` bgm: no sample table or missing .bd), `FRES/EFF.HD` (not SShd). `.SQ` skipped (sequences, not audio). No voices lost |
| getagrip | 15545 | 2 | `stream_se/env_lo0202.sgb`, `env_lo0700.sgb` (no .sgh anywhere) |
| opentee | 1629 | 0 | |
| opentee2 | 11451 | 0 | |
| oob | 13371 | 17 | 14 raw `.sgb` with no `.sgh` anywhere (ga_j_13/14, me_s_01_loop1/short, me_s_03/09/10, on_j_01/02, on_s_08, pz_j_04/05/07, pz_s_03_short); 3 `.sgd` vgmstream cannot open (lobby01/03.sgd, MG5_Bus.sgd) |

## Fore (PS2) - `.hd/.bd` are NOT readable by vgmstream (`SShd` header, no IECSsreV wrapper)
`audio.py` parses the SShd tone-set table (layout in HST-Remastered `crates/hst-data/src/snd.rs`), cuts each tone's sample out
of the `.bd` (address = u16*8) and decodes PS-ADPCM via a temp VAGp + vgmstream, **assumed 44100 Hz** (root-note rate; per-tone
pitch/fine tune ignored). One wav per distinct sample, `NNN` = order by BD address; `index.txt` in each bank dir gives
`set= note= addr=`. Mapping of game events (program/key -> sequence -> tone) is NOT applied.
- Character voice banks: `data/sound/voice/pc_game/<code>/` (3-letter code), inside `PC/PCNN/PCNNxxxx.XB/` (the NN dir
  gives the code -> index mapping; each PCNN holds exactly one code) and `SND/PC_GAME/<CODE>/SC_<CODE>NN.XB/`.
  Also `MENU/M_VOICE/MEPCNN.XB/.../me_pc/mepc_NNa|b.hd` (NN = index; char-select), `SND/PC_HONOR/HY_<CODE>N.XB` (`pc_honor`).
- Index -> code: 00 pho, 01 mik, 02 emm, 03 sam, 04 mis, 05 bra, 06 cha, 07 reg, 08 may, 09 fal, 10 ren, 11 zzz, 12 mel, 13 all,
  14 tif, 15 kam, 16 ton, 17 tbo, 18 lin, 19 lou, 20 zeu, 21 hub, 22 rat, 23 jak. **No text file maps code -> character name**
  (not guessed). 
- Per-character bank prefixes (counts per char): `g_<c>1..5(+)` in-game shouts (5-8), `jy_<c>0..6` (7), `sc_<c>00..23` (24; one per
  other character index 00-23, possibly reactions/scene lines - unverified), `vs_<c>00..07` (8), `co_<c>` (13 samples), `ya_<c>`
  (12 samples), `mepc_NNa/b`, `hy_<c>N`. Meaning of prefixes is not documented in the data; `g_` = game, `vs_` = versus, `ya_` = ?, 
  `jy_` = ? (guess only from names). 
- Caddies: `voice/cad/<name>/*` (180 banks, e.g. `bs_gre2`, `cu_kay1`, `pg_kay2`), `ca_honor`. Other: `gaya`, `me_ca`.

## Get a Grip (PSP, Tennis) - the relevant one
Voice banks (`.sgd`) under `PSP_GAME/USRDIR/xbdata/game/400_pc/face_voice/<bank>.xb/data/sound/Voice/{nml,rev}/`; PCs are
`pc00..pc14` (15 playable), NPCs `npc_m00..m14`, `npc_w00..w07` (and `galsg_gl_[mw]NN_[ab]` crowd/girls, `gag_vcNN[ab]` umpire).
Banks per PC `NN`: `sgv_PCNNa/b` (32-33 cues; `a`/`b` = two variants), `dgv_PCNNa/b` (26; adds `go call hello whatsup`),
`hnr_PCNN` (8: `winA/B_0/1`, `loseA_0/1`, plus 2 unnamed), `mv_closet_PCNN` (1, `changecloth`). `_rev` = mirrored-side copies
(separate bank per variant; same cue names). Also copies in `menu/optionvoice/option_voice_pcNN.xb` and `game/700_prize/*prize_pcNN.xb`.
Cue names (from the SGXD NAME table; `names.txt` next to the wavs; `out/voices/getagrip/pcNN/<bank>_<cue>.wav` aliases):
`pc_voice_` + `smash_0-2, swing_0/1, receive_0-2` (shot shouts), `st_ji_0-4, st_nb_0-2` (stroke shouts, ji/nb unknown),
`start_0/1`, `match`, `point_get_0/1` (point won), `point_lost_0/1`, `rep_get / rep_lost` (rally?), `set_get_0/1` (set won),
`set_lost_0/1`, `gut_0/1`, `chance`, `body`. Umpire `gag_vc*`: `vc_voice_point_*`, `tiebreak_*`, `miss_*`.
Cue -> wave mapping is **inferred** (cue id = RGND region index -> wave index, 33 cues over 32 waves, one wave shared); the
SEQD chunk was not decoded, so spot-check by ear before relying on it. Subsong order is the raw index (`NNN.wav`).
Character index -> name: not found in any csv/txt (character.csv is `Pc_NN_00` params only). Not guessed.

## Open Tee 1 (PSP)
Per PC `NN` (00-09, 10 chars): `hats/snd/pcNN.xb` (`gNN_0..4`, `st_NN` x10), `pcNNv.xb` (`vs_NN` x10), `pcNNm.xb` (`ya_NN` x10),
`tnk/result/Voice/hy_NN.xb` (4). Caddies `ccNN` (`gacaNa/b`), `cy_NN`. `pc99` = shared. No names in tables (`names.txt` has the
original vag names in a few places).
## Open Tee 2 (PSP)
Per PC `NN` (00-22): `hats/snd/pc_{g,st,vs,ya}_NN{a,b}.xb` (g: 7 waves with names `P1_pcNN_g_a_0_k[_US]`; st/vs/ya: 9-10).
`tnk/charsel/charselvoice_*.xb/mepc_cs_99a|b.sgd` and `matu/lastchk/dataN.xb/mepcNNb.sgd` = char-select. `cd_hy_NN[abc]`, `cd_hyi`,
`meca_*` are caddie (ca) voices. The char-select bank lists the caddie name stems Alo Cre Den Hel Lep Myu Sag Sin Suq Yum
(caddie order 00..10 as listed, unverified) and `pc00..pc11`.
## Out of Bounds (PS3)
Per PC `NN` (00-16): `xbdata/.../ga_{sg,ev,pz,ya,vs}_pcNN.sgd` (60/34/29/17/15 subsongs), `me_pro_pcNN.sgd` (profile, 20);
caddie `*_caNN`. `data/sound/voice/menu/me_pc.sgd` (all characters, menu). Cue names in `names.txt` are raw (`?\t0xID\tname`, e.g.
`pc00_20A`), id -> wave mapping not decoded. Streams `data/sound/stream/*.sgb` (music/ambience).

## Unresolved
- Character names for all games. - Fore sample rate/pitch (44.1 kHz assumed) and event -> sample mapping. - Cue -> wave mapping for GaG is inferred.
- OOB / Open Tee cue name -> wave mapping not decoded.
