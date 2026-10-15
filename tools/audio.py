#!/usr/bin/env python3
"""Convert every audio bank/stream of a game to WAV: out/audio/<game>/<relpath>/<NNN>.wav
usage: tools/audio.py <fore|getagrip|opentee|opentee2|oob> [jobs]
Fore .hd/.bd (PS2 SShd bank): one wav per sample at its true rate, NNN = tone sample order by BD address (index.txt lists
set/note/addr/semitones/rate).
Others: vgmstream-cli, all subsongs (NNN = subsong). Identical files are converted once and hard-linked.
Failures -> out/audio/<game>/FAILED.txt"""
import hashlib, os, shutil, struct, subprocess, sys, tempfile
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
game = sys.argv[1]
jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 4
OUT = f"{ROOT}/out/audio/{game}"
EXT = {"hd", "sgd", "sgh", "sgb", "at3"}


def md5(*paths):
    h = hashlib.md5()
    for p in paths:
        with open(p, "rb") as f:
            for c in iter(lambda: f.read(1 << 20), b""):
                h.update(c)
    return h.hexdigest()


def scan():
    byname, items = {}, []
    for base in (f"{ROOT}/out/files/{game}", f"{ROOT}/extracted/{game}"):
        for d, _, fs in os.walk(base, followlinks=True):
            for n in fs:
                ext = n.rsplit(".", 1)[-1].lower()
                if ext in EXT:
                    p = os.path.join(d, n)
                    byname[n.lower()] = p
                    items.append((os.path.relpath(p, base), p, ext))
    return items, byname


def companion(p, ext, byname, new):
    """the second file of a pair, searched beside p first, then anywhere in the game tree"""
    stem = p.rsplit(".", 1)[0]
    for e in new:
        for c in (stem + "." + e, stem + "." + e.upper()):
            if os.path.exists(c):
                return c
    return byname.get(os.path.basename(stem).lower() + "." + new[0])


def vag(data, rate=44100):
    return b"VAGp" + struct.pack(">IIII", 0x20, 0, len(data) + 16, rate) + bytes(12) + bytes(16) + bytes(16) + data


def fore_tones(h):
    """{bd address: (set, note, semitones)} of an SShd bank's tone sets. The sound driver (SNDN2DRV.IRX, the same pitch
    rule and 192-steps-per-octave table as HST's, open-tennis `snd::pitch`) plays a tone (note - root) semitones +
    fine/16 from 44.1 kHz, and every voice sequence keys on the tone's own note, so that is the sample's true rate."""
    if h[12:16] != b"SShd":
        raise RuntimeError("not SShd")
    u16 = lambda o: struct.unpack_from("<H", h, o)[0]
    sec = struct.unpack_from("<i", h, 0x24)[0]
    tones = {}
    if sec >= 0:
        for s in range(u16(sec) + 1):
            so = sec + u16(sec + 2 + 2 * s)
            lo, hi = h[so + 6], h[so + 7]
            for n in range(lo, hi + 1):
                o = so + 8 + (n - lo) * 16
                if o + 16 > len(h):
                    break
                # ponytail: first tone per sample wins (voice samples have one tone each)
                tones.setdefault(u16(o + 4) * 8, (s, n, n - h[o + 2] + struct.unpack_from("b", h, o + 3)[0] / 16))
    return tones


def fore_rate(semitones):
    return round(44100 * 2 ** (semitones / 12))


def conv_fore(hd, bd, out, tmp):
    h, b = open(hd, "rb").read(), open(bd, "rb").read()
    tones = fore_tones(h)
    if not tones:
        raise RuntimeError("no tones")
    addrs = sorted(a for a in tones if a < len(b))
    os.makedirs(out, exist_ok=True)
    idx = []
    for i, a in enumerate(addrs, 1):
        e = a
        while e + 16 <= len(b) and not (b[e + 1] & 1):
            e += 16
        e += 16
        if i < len(addrs):
            e = min(e, addrs[i])
        data = b[a:e]
        if len(data) < 32:
            continue
        vp = os.path.join(tmp, "s.vag")
        s, n, st = tones[a]
        open(vp, "wb").write(vag(data, fore_rate(st)))
        r = subprocess.run(["vgmstream-cli", "-i", "-o", f"{out}/{i:03d}.wav", vp], capture_output=True)
        if r.returncode:
            raise RuntimeError(f"sample {i} decode failed")
        idx.append(f"{i:03d} set={s} note={n} addr=0x{a:x} bytes={len(data)} semitones={st:+.4f} rate={fore_rate(st)}")
    open(f"{out}/index.txt", "w").write("\n".join(idx) + "\n")


def fore_rates(hd, out):
    """resume: give wavs converted before fore_tones knew the pitch their true rate (index.txt rewritten with it)"""
    tones = fore_tones(open(hd, "rb").read())
    idx = []
    for line in open(f"{out}/index.txt").read().split("\n"):
        if line:
            i, a = int(line[:3]), int(line.split("addr=")[1].split()[0], 16)
            s, n, st = tones[a]
            set_rate(f"{out}/{i:03d}.wav", fore_rate(st))
            idx.append(f"{line} semitones={st:+.4f} rate={fore_rate(st)}")
    open(f"{out}/index.txt", "w").write("\n".join(idx) + "\n")


def set_rate(f, new):
    """rewrite a 16-bit PCM wav header's sample rate (and byte rate)"""
    with open(f, "r+b") as fh:
        h = fh.read(36)
        ch_, bits = struct.unpack_from("<H", h, 22)[0], struct.unpack_from("<H", h, 34)[0]
        fh.seek(24); fh.write(struct.pack("<II", new, new * ch_ * bits // 8))


def conv_vgm(p, out, tmp):
    os.makedirs(out, exist_ok=True)
    r = subprocess.run(["vgmstream-cli", "-i", "-S", "0", "-o", f"{out}/?03s.wav", p], capture_output=True, text=True)
    if not any(f.endswith(".wav") for f in os.listdir(out)):
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else "no output")


def sgxd_cue_waves(b, u, ch):
    """{cue: wave} from SEQD: group 0 lists one sequence per cue (+0x10 group offset; group +4 count, +8 offsets); a
    sequence keys on with `d0 01 NN`, NN the note in decimal digits (0x32 = note 32: in all 14k Get a Grip sequences
    the digit reading lands on a region and the raw byte often doesn't). The region whose key range holds the note
    (RGND program p: count +0x10+8p, offset +0x14+8p; region +0 key lo, +1 key hi, +0x1c wave) gives the wave.
    Checked 2026-10-14 by transcript on all 16 umpire banks gag_vcNN[ab] (open-tennis M8f2): every cue says its name."""
    if b"SEQD" not in ch or b"RGND" not in ch:
        return {}
    r, s = ch[b"RGND"], ch[b"SEQD"]
    regions = [(b[g], b[g + 1], u(g + 0x1c)) for p in range(u(r + 0xc)) for k in range(u(r + 0x10 + 8 * p))
               for g in [r + 8 + u(r + 0x14 + 8 * p) + 0x38 * k]]
    g = u(s + 0x10)
    out = {}
    for c in range(u(g + 4)):
        q = u(g + 8 + 4 * c)
        k = b.find(b"\xd0\x01", q, q + 0x40)
        if k < 0 or (b[k + 2] & 15) > 9:
            continue
        note = (b[k + 2] >> 4) * 10 + (b[k + 2] & 15)
        out[c] = next((w for lo, hi, w in regions if lo <= note <= hi), None)
    return out


def sgxd_names(path, out):
    """names.txt: 'NNN<TAB>name' per subsong where the SGXD NAME table can be tied to a wave.
    id 0x3000wwww = wave name (Open Tee 2); id 0x2000cccc = cue name (Get a Grip): cue c plays SEQD sequence c, whose note
    (sgxd_cue_waves) picks the RGND region and so the wave. A cue whose sequence has no note falls back to region c when
    region count == cue count (the rule before 2026-10-14, inferred). Anything else (PS3 pcNN banks) is dumped raw as
    '?<TAB>0xID<TAB>name'."""
    b = open(path, "rb").read()
    if b[:4] != b"SGXD":
        return
    u = lambda o: struct.unpack_from("<I", b, o)[0]
    ch, o = {}, 0x10
    while o + 8 < len(b) and b[o:o + 4].isalpha() and b[o:o + 4].isupper():
        ch[b[o:o + 4]] = o; o += 8 + u(o + 4)
    if b"NAME" not in ch:
        return
    no = ch[b"NAME"]
    names = []
    for i in range(u(no + 12)):
        i_d, off = u(no + 16 + 8 * i), u(no + 20 + 8 * i)
        names.append((i_d, b[off:b.index(b"\0", off)].decode("ascii", "replace")))
    reg = [u(ch[b"RGND"] + 0x18 + k * 0x38 + 0x34) for k in range(u(ch[b"RGND"] + 0x10))] if b"RGND" in ch else []
    cues = [n for n in names if n[0] >> 28 == 2]
    seq = sgxd_cue_waves(b, u, ch)
    lines = []
    for i_d, n in names:
        if i_d >> 28 == 3:
            lines.append((i_d & 0xffff, n))
        elif i_d >> 28 == 2 and seq.get(i_d & 0xffff) is not None:
            lines.append((seq[i_d & 0xffff], n))
        elif i_d >> 28 == 2 and len(reg) == len(cues) and i_d & 0xffff < len(reg):
            lines.append((reg[i_d & 0xffff], n))
        elif i_d:
            lines.append((-1, f"0x{i_d:08x}\t{n}"))
    with open(f"{out}/names.txt", "w") as f:
        for w, n in sorted(lines):
            f.write(f"{w + 1:03d}\t{n}\n" if w >= 0 else f"?\t{n}\n")


def sgxd_rates(path, out):
    """rates.txt + true sample rates. An SGXD wave plays (region key - root note) + fine/128 semitones from its WAVE
    rate; RGND = programs, each a table of 0x38-byte regions (key lo +0, root +4, fine +5, wave +0x1c). Checked against
    PPSSPP's sceSasSetPitch on Get a Grip (Emi 55-75+18/128 = -19.86 st = 14 kHz, umpire -12 = 22.05 kHz); the stored
    audio is really 14/18/20/22.05/32 kHz labelled 44.1. vgmstream ignores this, so each NNN.wav header gets the rate."""
    b = open(path, "rb").read()
    if b[:4] != b"SGXD":
        return
    u = lambda o: struct.unpack_from("<I", b, o)[0]
    ch, o = {}, 0x10
    while o + 8 < len(b) and b[o:o + 4].isalpha() and b[o:o + 4].isupper():
        ch[b[o:o + 4]] = o; o += 8 + u(o + 4)
    if b"RGND" not in ch or b"WAVE" not in ch:
        return
    r, w = ch[b"RGND"], ch[b"WAVE"]
    st = {}
    for p in range(u(r + 0xc)):
        for k in range(u(r + 0x10 + 8 * p)):
            g = r + 8 + u(r + 0x14 + 8 * p) + 0x38 * k
            st.setdefault(u(g + 0x1c), b[g] - b[g + 4] + b[g + 5] / 128)  # ponytail: first region per wave wins
    lines = []
    for wv, s_ in sorted(st.items()):
        f = f"{out}/{wv + 1:03d}.wav"
        if not os.path.exists(f) or wv >= u(w + 0xc):
            continue
        rate = u(w + 0x10 + 0x38 * wv + 0xc)
        new = round(rate * 2 ** (s_ / 12))
        set_rate(f, new)
        lines.append(f"{wv + 1:03d}\t{s_:+.3f}\t{rate}->{new}")
    open(f"{out}/rates.txt", "w").write("\n".join(lines) + "\n")


def work(a):
    rel, p, ext, byname = a
    out = f"{OUT}/{rel}"
    if os.path.isdir(out) and any(f.endswith(".wav") for f in os.listdir(out)):
        if ext in ("sgd", "sgh") and not os.path.exists(f"{out}/names.txt"):  # resume: just (re)write names
            try: sgxd_names(p, out)
            except Exception: pass
        if ext in ("sgd", "sgh") and not os.path.exists(f"{out}/rates.txt"):  # resume: apply true rates once
            sgxd_rates(p, out)
        if ext == "hd" and "rate=" not in open(f"{out}/index.txt").read():  # resume: Fore true rates once
            fore_rates(p, out)
        return rel, None
    tmp = tempfile.mkdtemp()
    try:
        if ext == "hd":
            bd = companion(p, ext, byname, ["bd"])
            if not bd:
                raise RuntimeError("missing .bd")
            conv_fore(p, bd, out, tmp)
        elif ext == "sgh":
            sgb = companion(p, ext, byname, ["sgb"])
            if not sgb:
                raise RuntimeError("missing .sgb")
            hdr = p
            # vgmstream opens the pair through the .sgb (it finds the .sgh beside it), not the .sgh
            st = os.path.basename(p).rsplit(".", 1)[0]
            os.symlink(p, f"{tmp}/{st}.sgh")
            os.symlink(sgb, f"{tmp}/{st}.sgb")
            p = f"{tmp}/{st}.sgb"
            conv_vgm(p, out, tmp)
            sgxd_names(hdr, out)
            sgxd_rates(hdr, out)
        else:
            conv_vgm(p, out, tmp)
            if ext == "sgd":
                sgxd_names(p, out)
                sgxd_rates(p, out)
        return rel, None
    except Exception as e:
        shutil.rmtree(out, ignore_errors=True)
        return rel, str(e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    items, byname = scan()
    seen, uniq, dups = {}, [], []
    for rel, p, ext in sorted(items):
        if ext == "sgb" and os.path.basename(p)[:-3].lower() + "sgh" in byname:
            continue  # opened through its .sgh
        pair = {"hd": ["bd"], "sgh": ["sgb"]}.get(ext)
        c = companion(p, ext, byname, pair) if pair else None
        key = (ext, md5(p, *([c] if c else [])))
        if key in seen:
            dups.append((rel, seen[key]))
        else:
            seen[key] = rel
            uniq.append((rel, p, ext, byname))
    os.makedirs(OUT, exist_ok=True)
    failed = {}
    with Pool(jobs) as pool:
        for n, (rel, err) in enumerate(pool.imap_unordered(work, uniq, 4), 1):
            if err:
                failed[rel] = err
            if n % 200 == 0:
                print(game, n, "/", len(uniq), flush=True)
    nd = 0
    for rel, src in dups:  # hard-link duplicates of already converted files
        s, d = f"{OUT}/{src}", f"{OUT}/{rel}"
        if src in failed:
            failed[rel] = failed[src] + f" (same as {src})"
        elif os.path.isdir(s):
            os.makedirs(d, exist_ok=True)
            for f in os.listdir(s):
                if not os.path.exists(f"{d}/{f}"):
                    os.link(f"{s}/{f}", f"{d}/{f}")
            nd += 1
    with open(f"{OUT}/FAILED.txt", "w") as f:
        for rel in sorted(failed):
            f.write(f"{rel}\t{failed[rel]}\n")
    print(f"{game}: {len(items)} files, {len(uniq)} unique, {nd} linked dups, {len(failed)} failed")


if __name__ == "__main__":
    main()
