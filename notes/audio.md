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
| opentee2 | 11451 | 0 | |
| oob | 13371 | 17 | 14 raw `.sgb` with no `.sgh` anywhere (ga_j_13/14, me_s_01_loop1/short, me_s_03/09/10, on_j_01/02, on_s_08, pz_j_04/05/07, pz_s_03_short); 3 `.sgd` vgmstream cannot open (lobby01/03.sgd, MG5_Bus.sgd) |

## Fore (PS2) - `.hd/.bd` are NOT readable by vgmstream (`SShd` header, no IECSsreV wrapper)
`audio.py` parses the SShd tone-set table (layout in opentennis `crates/hst-data/src/snd.rs`), cuts each tone's sample out
of the `.bd` (address = u16*8) and decodes PS-ADPCM via a temp VAGp + vgmstream at the sample's **true rate**:
44100 * 2^((note - root + fine/16) / 12). Fore's sound driver `MODULES2/SNDN2DRV.IRX` holds the same 192-steps-per-octave
pitch table as HST's and packs root/note/fine/bend and scales by 441/480 the same way (opentennis `snd::pitch`), and
every voice sequence keys on the tone's own note. Voice tones sit at -6.625 (30.1 kHz), -12 (22.05), -7.25, -7.8125 ...
semitones; most SE at -5.5 (32.1 kHz). Before 2026-10-11 everything was written at 44.1 kHz (voices 5-12 st too high).
Checked 2026-10-12 against the running game (opentennis `research/tools/fore_spu_rates.py`: SPU2 pitch registers of
save states in Fore's attract demo, sample identified by SPU RAM bytes): Brad's shout `g_bra2` 29004 Hz in game vs 29011 here
(-7.25 st), caddie Kaz -7.8125/-9.8125/-10.875 st likewise within the pitch table's rounding (<0.05%). SE banks such as
`plse` also play at other pitches (sequenced), so an SE wav is only its keyed-at-own-note rate. Sam: -6.625 (139 tones),
-13.25, -9.125, -7.625.
One wav per distinct sample, `NNN` = order by BD address; `index.txt` in each bank dir gives
`set= note= addr= bytes= semitones= rate=`. Mapping of game events (program/key -> sequence -> tone) is NOT applied.
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
`set_lost_0/1`, `gut_0/1`, `chance`, `body` (hit by the ball: "Ow!", "Ouch!", "Nah, I'm hit!" → HST program 5). Umpire `gag_vc*`: `vc_voice_point_*`, `tiebreak_*`, `miss_*`.
Cue -> wave is **decoded** (2026-10-14, opentennis M8f2; `audio.py sgxd_cue_waves`): cue c plays SEQD group 0
sequence c, which keys on with `d0 01 NN`, NN the note in decimal digits (0x32 = note 32); the RGND region whose key range
holds the note gives the wave. Checked by whisper transcript on all 16 umpire banks (every cue says its name) and on
`dgv_NPC_m06a` (`start_0` "Shall we?", `match` "Last one!", `go` "Now!", `hello` "Ready when you are!"). Before, the
mapping was inferred as cue c -> region c, which matches the decode for the playable `sgv/dgv_PC00-13` banks but was one
off from cue 5 on in 44 of the 46 `dgv_NPC_*` banks (their cue order isn't their region order) and gave no names at all for
`sgv/dgv_PC14` (Helghast; cue count != region count). Since rerun (`voices.py`, `rerig/package.py getagrip`, opentennis
M92) `getagrip_pc14_helghast` ships `voice/` like the other 14 (27 wavs, same program counts).
Subsong order is the raw index (`NNN.wav`).
Umpires: `sound/game/010_umpire_NN_0V.xb` -> `gag_vcNN{a,b}` (+`_rev`), NN = model `200_court/umpire.xb` u_NN = loading
card `menu/loadmes/judge/loadmes_jNN.xb0`: 00 Natasha, 01 Nate, 02 Kanani, 03 Xavier, 04 Helghast, 05 Robo T., 06 Suzuki,
07 Gloria. 45 cues: `vc_voice_point_f_0-3` (love..forty, first word), `point_b_0-3` (second word), `point_all`,
`point_deuce_0` "deuce", `point_deuce_1` "deuce again", `point_adv_0` "advantage", `adv_1` "server", `adv_2` "receiver",
`miss_out/fault_0/fault_1 (double fault)/let/net`, `break` "tie-break", `game`, `set`, `change` "change sides",
`gameset`, `ballhit` (hit by the ball: "Hey!", "Careful now!"), `tiebreak_0-9up/down` (tiebreak point numbers).
`b` = a second, chattier take set ("That's out!", "We have a tie break!"). Packaged as umpire mods by
`tools/rerig/gag_umpires.py` (bank `a`, all 24 HST calls; standard HST-COURT-UMPIRE-STANDARD.md §3).
Character index -> name: not found in any csv/txt (character.csv is `Pc_NN_00` params only). Not guessed.

## Open Tee 2 (PSP)
`pc_g_NN[ab].sgd` (in-game shouts) are stereo ATRAC3 RIFFs with no RGND pitch table: really 44.1 kHz, hence no `rates.txt`
(no rate-less SGXD bank of any game has an RGND chunk, checked 2026-10-12).
Per PC `NN` (00-22): `hats/snd/pc_{g,st,vs,ya}_NN{a,b}.xb` (g: 7 waves with names `P1_pcNN_g_a_0_k[_US]`; st/vs/ya: 9-10).
`tnk/charsel/charselvoice_*.xb/mepc_cs_99a|b.sgd` and `matu/lastchk/dataN.xb/mepcNNb.sgd` = char-select. `cd_hy_NN[abc]`, `cd_hyi`,
`meca_*` are caddie (ca) voices. The char-select bank lists the caddie name stems Alo Cre Den Hel Lep Myu Sag Sin Suq Yum
(caddie order 00..10 as listed, unverified) and `pc00..pc11`.
## Out of Bounds (PS3)
Per PC `NN` (00-16): `xbdata/.../ga_{sg,ev,pz,ya,vs}_pcNN.sgd` (60/34/29/17/15 subsongs), `me_pro_pcNN.sgd` (profile, 20);
caddie `*_caNN`. `data/sound/voice/menu/me_pc.sgd` (all characters, menu). Cue names in `names.txt` are raw (`?\t0xID\tname`, e.g.
`pc00_20A`), id -> wave mapping not decoded. Streams `data/sound/stream/*.sgb` (music/ambience).

## Unused lines (`out/voice_candidates/`, 2026-10-16)
`tools/voice_candidates.py` transcribes (faster-whisper small) every voice wave of a golf mod's character that the mod does not
ship and sorts it by keyword into `0-1-3_shout`, `2-4_mishit_whiff`, `7-9_won_point`, `8-10_lost_point`, `other_long`, with
`index.tsv`. Sources: the English banks the mods draw from, plus OOB's prize (`ga_pz_pcNN`) and profile (`me_pro_pcNN`) banks; wordless grunts (< 1 s, kana interjections only, not はい/いや/..) from the Japanese copies (OOB `ga_pc_NN.xb`, pc00-14; Open Tee 2 `.xb`) go in `grunts_from_japanese/`. Samples in more than one character's banks are left out (OOB `ga_ya` 012-017 are shared effects; Open Tee 2's `lastchk/dataNN` select-screen banks are identical for all). Keyword buckets are rough (whisper mishears grunts; "Not bad" lands in lost); pick by ear. Used so far: Open Tee 2
pc00-09 won/lost (`opentee_data.py` WON/LOST). Thin spots it can fill: Open Tee 2 pc10-20 (no 7-10), pc03 Shu (no shouts),
pc06 Patricia (1 shout), every golf mod's 2/4 except OOB/Fore, Fore's single-take 8/10.

## Unresolved
- Character names for all games. - Fore event -> sample mapping (and any EE-side pitch scale on a play call; voices assumed 1.0). - OOB / Open Tee cue name -> wave mapping not decoded.

## Language (checked 2026-10-12, HST M1p)
Some discs carry each voice archive twice, one per language. Use the English copy:
| game | English copy | other copies |
|---|---|---|
| oob | `sound/pc/ga_pc_NN.xb0` (all 17) | `ga_pc_NN.xb` (pc00-14) is the **Japanese** cast for pc01-06 and 08-14; pc00 and pc07 hold English there too |
| opentee2 | `hats/snd/pc_*_NN[ab].xb1` (wave names `_US`) | `.xb` = Japanese |
| getagrip | the only `face_voice/*.xb` copy | `.xb0/.xb2/.xb3` exist for other archives only, never for voices |
| fore | single copy, English | |
Before this, `oob_data._bank` globbed `ga_pc_NN.xb*` and took whichever came first, which was the Japanese `.xb` for
most of the cast. Every game has English takes for every packaged line: no mod is Japanese-only.
Checked with `tools/voice_lang.py` (faster-whisper language ID over each mod's four longest voice wavs). Short grunts
("えぇ?", "おいしょ") come out as ja/zh/ko at low confidence in every game; only lines with words count.
