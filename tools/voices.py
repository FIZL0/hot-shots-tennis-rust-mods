#!/usr/bin/env python3
"""Symlink each playable character's voice WAVs: out/voices/<game>/pcNN/<bank>_<NNN>.wav (+ <bank>_<cue name>.wav where the bank has names) (relative links into out/audio).
usage: tools/voices.py   (run after tools/audio.py). Fore: the 3-letter code is mapped to NN via PC/PCNN/ dirs."""
import os, re, collections
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A, V = f"{R}/out/audio", f"{R}/out/voices"

def banks(g):
    for d, ds, fs in os.walk(f"{A}/{g}"):
        if re.search(r"\.(sgd|hd|sgb|sgh)$", d, re.I) and any(f.endswith(".wav") for f in fs):
            ds.clear()
            yield d, sorted(f for f in fs if f.endswith(".wav"))

def who(g, d):
    b = os.path.basename(d).rsplit(".", 1)[0].lower(); p = d.lower()
    if g == "fore":
        m = re.search(r"/sound/voice/(?:pc_game|pc_honor)/([a-z]{3})/", p)
        if m: return m[1]
        m = re.fullmatch(r"mepc_(\d+)[ab]", b)
        return f"#{int(m[1])}" if m else None
    m = re.search(r"npc_([mw])(\d+)", b)
    if m: return f"npc_{m[1]}{m[2]}"
    m = re.search(r"/pc(\d+)[vm]?\.xb\d?/", p) or re.search(r"(?:^|_)pc_?(?:[a-z]{1,2}_)?(\d+)", b) or re.search(r"^hy_(\d+)", b) or re.search(r"mepc(\d+)", b)
    return f"pc{m[1]}" if m else None

def main():
    for g in ["fore", "getagrip", "opentee", "opentee2", "oob"]:
        if not os.path.isdir(f"{A}/{g}"): continue
        code = {}
        if g == "fore":  # code -> NN from PC/PCNN/
            for d, _ in banks(g):
                m = re.search(r"/PC/PC(\d\d)/.*/sound/voice/pc_game/([a-z]{3})/", d.replace(f"{A}/{g}", ""), re.I)
                if m: code[m[2].lower()] = m[1]
        n = collections.Counter()
        for d, fs in sorted(banks(g)):
            w = who(g, d)
            if not w: continue
            if g == "fore": w = "pc" + (w[1:].zfill(2) if w[0] == "#" else code.get(w, "??" + w))
            out = f"{V}/{g}/{w}"; os.makedirs(out, exist_ok=True)
            b = os.path.basename(d).rsplit(".", 1)[0].lower()
            for f in fs:
                t = f"{out}/{b}_{f}"
                if not os.path.lexists(t):
                    os.symlink(os.path.relpath(f"{d}/{f}", out), t); n[w] += 1
            if os.path.exists(f"{d}/names.txt"):  # extra <bank>_<cue name>.wav aliases
                for l in open(f"{d}/names.txt"):
                    k, _, nm = l.rstrip("\n").partition("\t")
                    t = f"{out}/{b}_{nm}.wav"
                    if k.isdigit() and os.path.exists(f"{d}/{k}.wav") and not os.path.lexists(t):
                        os.symlink(os.path.relpath(f"{d}/{k}.wav", out), t)
        print(g, len(n), "dirs", sum(n.values()), "links")

main()
