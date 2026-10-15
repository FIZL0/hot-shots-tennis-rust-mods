"""Get a Grip's eight chair umpires' voices as umpire mods (standard/HST-COURT-UMPIRE-STANDARD.md §3; opentennis
task M8f2) -> out/mods/gag_umpNN_<name>/ (mod.json + voice/<program>_<key>.wav).

python3 tools/rerig/gag_umpires.py [opentennis dir]      (default ../opentennis)

Needs: tools/audio.py getagrip (the umpire banks as wavs with names.txt from the SEQD cue decode), and from the
opentennis checkout the disc image and its release `bankwav` (the donor umpires' calls, for the timing fit).
Game data: the outputs stay in out/ (git-ignored).

Umpire NN = `sound/game/010_umpire_NN_0V.xb` bank `gag_vcNN{a,b}` = model `200_court/umpire.xb` u_NN (face textures
named Natashya, Ryota, Vanessa, Javier, Yakun, Tenibo, Suzuki, Gloria) = loading card `menu/loadmes/judge/
loadmes_jNN.xb0` (English names below). Bank `a` is used: shorter single-word takes like HST's; `b` is a chattier
second take set ("That's out!", "We have a tie break!") that would mostly be cut by the donor's timing.

Each of HST's 24 calls (CALLS) has a Get a Grip cue of the same words, checked by a whisper transcript of all 16
banks (2026-10-14; opentennis research/journal/2026-10-14-m8f-courts-umpires/2-GAG-UMPIRE-VOICES-*.md). Unused
cues: `ballhit` (the umpire hit by the ball: HST has no such call) and `tiebreak_Nup/down` (Get a Grip calls tiebreak
points as numbers; HST's umpire calls no tiebreak points, `umpire.rs` `call_score`). `b` and the `_rev` banks are not shipped.

Donor (standard §3: its word lengths time the calls; its voice fills gaps; its model is drawn): the same umpire where
HST has one (Suzuki, Robot Tennis), else among HST's umpires of the same sex the one whose clips this voice overruns
least (sum over the 24 calls of how much longer the mod's clip is than the donor's: overrun is cut when the next
word starts, a shorter clip only leaves a pause).
"""
import json
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from package import link  # noqa: E402

GAG = os.path.join(ROOT, "out/audio/getagrip/PSP_GAME/USRDIR/xbdata/sound/game")
# n -> (slug, name on its loading card, sex, HST umpire that is the same character or None)
UMPIRES = {0: ("natasha", "Natasha", "f", None), 1: ("nate", "Nate", "m", None), 2: ("kanani", "Kanani", "f", None),
           3: ("xavier", "Xavier", "m", None), 4: ("helghast", "Helghast", "m", None),
           5: ("robo_t", "Robo T.", None, 3), 6: ("suzuki", "Suzuki", "m", 1), 7: ("gloria", "Gloria", "f", None)}
# HST's umpires (`--umpire` order) and their sex (tools/rerig/hst_umpires.py); 3 is a robot
HST = {0: ("Chika", "f"), 1: ("Suzuki", "m"), 2: ("Lily", "f"), 3: ("Robot Tennis", None), 4: ("Anna", "f")}
# HST call (program, key) <- Get a Grip cue; transcript of HST's / Get a Grip's take
CALLS = {
    (0, 0): "vc_voice_point_f_0", (0, 1): "vc_voice_point_f_1", (0, 2): "vc_voice_point_f_2", (0, 3): "vc_voice_point_f_3",
    (0, 4): "vc_voice_point_b_0", (0, 5): "vc_voice_point_b_1", (0, 6): "vc_voice_point_b_2", (0, 7): "vc_voice_point_b_3",
    (0, 8): "vc_voice_point_all",       # "all"
    (0, 9): "vc_voice_point_deuce_0",   # "deuce"
    (0, 10): "vc_voice_point_adv_0",    # "advantage"
    (0, 11): "vc_voice_point_adv_1",    # HST "server" / Get a Grip "server"
    (0, 12): "vc_voice_point_adv_2",    # "receiver"
    (0, 13): "vc_voice_point_deuce_1",  # Get a Grip "deuce again": HST's second-deuce key, which no disc umpire has a
                                        # take for (silent on the disc, no donor length; opentennis M8f3 decides)
    (1, 0): "vc_voice_miss_out", (1, 1): "vc_voice_miss_fault_0",  # "out", "fault"
    (1, 2): "vc_voice_miss_fault_1",    # "double fault"
    (1, 3): "vc_voice_miss_let", (1, 4): "vc_voice_miss_net",
    (2, 0): "vc_voice_break",           # "tie-break"
    (2, 1): "vc_voice_game", (2, 2): "vc_voice_set",
    (2, 3): "vc_voice_change",          # HST "change" / Get a Grip "change sides"
    (2, 4): "vc_voice_gameset",         # "game, set and match"
}


def seconds(wav):
    """length of a 16-bit PCM wav, walking its chunks (bankwav leaves the RIFF size 0, so `wave` refuses it)"""
    b = open(wav, "rb").read()
    rate, o = None, 12
    while o + 8 <= len(b):
        tag, n = b[o:o + 4], struct.unpack_from("<I", b, o + 4)[0]
        if tag == b"fmt ":
            ch, rate = struct.unpack_from("<HI", b, o + 10)
        elif tag == b"data":
            return n / (2 * ch * rate)
        o += 8 + n + (n & 1)
    raise ValueError(f"{wav}: no data chunk")


def cues(n):
    d = os.path.join(GAG, f"010_umpire_{n:02d}_00.xb/data/sound/Voice/nml/gag_vc{n:02d}a.sgd")
    return {name: os.path.join(d, f"{k}.wav") for k, name in (l.rstrip("\n").split("\t") for l in open(os.path.join(d, "names.txt")))}


def tool(hst, name):
    for d in (os.environ.get("CARGO_TARGET_DIR"), os.path.join(hst, "target")):
        if d and os.path.exists(os.path.join(d, "release", name)):
            return os.path.join(d, "release", name)
    sys.exit(f"{name}: build it in {hst} (cargo build --release -p hst-data)")


def donor_lengths(hst):
    """{umpire: {(program, key): seconds}} of HST's five umpires' takes (bank variant a, the one a match plays)"""
    iso = os.path.join(hst, "Hot Shots Tennis (USA).iso")
    out = {}
    for u in HST:
        bank = os.path.join(ROOT, f"out/voices/hst/umpire{u:02d}")
        subprocess.run([tool(hst, "bankwav"), iso, f"SND/UMP/UV{u:02d}A.XB0", f"data/sound/UMPIRE/gag_vc{u:02d}a.hd", bank],
                       check=True, stdout=subprocess.DEVNULL)
        out[u] = {c: seconds(os.path.join(bank, f"{c[0]}_{c[1]}.wav")) for c in CALLS
                  if os.path.exists(os.path.join(bank, f"{c[0]}_{c[1]}.wav"))}
    return out


def main():
    hst = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "../opentennis"))
    lengths = donor_lengths(hst)
    for n, (slug, name, sex, same) in UMPIRES.items():
        c = cues(n)
        mine = {k: seconds(c[cue]) for k, cue in CALLS.items()}
        over = {u: sum(max(0.0, mine[k] - L[k]) for k in CALLS if k in L) for u, L in lengths.items()}
        if same is not None:
            donor, why = same, f"the same umpire in HST ({HST[same][0]})"
        else:
            pool = [u for u, (_, s) in HST.items() if s == sex]
            donor = min(pool, key=lambda u: over[u])
            why = (f"of HST's {'women' if sex == 'f' else 'men'} umpires ({', '.join(HST[u][0] for u in pool)}) the one "
                   f"this voice overruns least")
        why += f": {over[donor]:.2f} s over the donor's takes in all"
        mod = os.path.join(ROOT, f"out/mods/gag_ump{n:02d}_{slug}")
        for f in os.listdir(os.path.join(mod, "voice")) if os.path.isdir(os.path.join(mod, "voice")) else []:
            os.remove(os.path.join(mod, "voice", f))
        for (p, k), cue in CALLS.items():
            link(c[cue], os.path.join(mod, f"voice/{p}_{k}.wav"))
        long = [f"{p}_{k}" for (p, k) in CALLS if (p, k) in lengths[donor] and mine[(p, k)] > lengths[donor][(p, k)] + 0.1]
        manifest = {"standard": 1, "kind": "umpire", "id": f"gag_ump{n:02d}_{slug}", "name": name,
                    "source": f"Hot Shots Tennis: Get a Grip (PSP) umpire {n:02d} (gag_vc{n:02d}a)",
                    "donor": donor, "donor_why": why, "voice": "voice/",
                    "calls": [f"{p}_{k}" for p, k in CALLS], "language": "en",
                    "calls_why": {f"{p}_{k}": cue for (p, k), cue in CALLS.items()},
                    "todo": []}
        if not os.path.exists(os.path.join(mod, "umpire.glb")):  # tools/psp2gltf/export_getagrip_umpires.py
            manifest["todo"].append("umpire.glb: model and motions (tools/psp2gltf/export_getagrip_umpires.py)")
        if long:
            manifest["todo"].append(f"clips more than 0.1 s longer than the donor's, cut when the next word starts: {', '.join(long)}")
        if not manifest["todo"]:
            del manifest["todo"]
        json.dump(manifest, open(os.path.join(mod, "mod.json"), "w"), indent=1, ensure_ascii=False)
        print(f"{mod}: donor {HST[donor][0]} ({over[donor]:.2f} s over; " + ", ".join(f"{HST[u][0]} {v:.2f}" for u, v in over.items()) + ")")


if __name__ == "__main__":
    main()
