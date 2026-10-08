#!/usr/bin/env python3
"""Convert every audio bank/stream of a game to WAV: out/audio/<game>/<relpath>/<NNN>.wav
usage: tools/audio.py <fore|getagrip|opentee|opentee2|oob> [jobs]
Fore .hd/.bd (PS2 SShd bank): one wav per sample, NNN = tone sample order by BD address (index.txt lists set/note/addr).
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


def conv_fore(hd, bd, out, tmp):
    h, b = open(hd, "rb").read(), open(bd, "rb").read()
    if h[12:16] != b"SShd":
        raise RuntimeError("not SShd")
    u16 = lambda o: struct.unpack_from("<H", h, o)[0]
    sec = struct.unpack_from("<i", h, 0x24)[0]
    tones = {}  # addr -> (set, note)
    if sec >= 0:
        for s in range(u16(sec) + 1):
            so = sec + u16(sec + 2 + 2 * s)
            lo, hi = h[so + 6], h[so + 7]
            for n in range(lo, hi + 1):
                o = so + 8 + (n - lo) * 16
                if o + 16 > len(h):
                    break
                tones.setdefault(u16(o + 4) * 8, (s, n))
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
        open(vp, "wb").write(vag(data))
        r = subprocess.run(["vgmstream-cli", "-i", "-o", f"{out}/{i:03d}.wav", vp], capture_output=True)
        if r.returncode:
            raise RuntimeError(f"sample {i} decode failed")
        idx.append(f"{i:03d} set={tones[a][0]} note={tones[a][1]} addr=0x{a:x} bytes={len(data)}")
    open(f"{out}/index.txt", "w").write("\n".join(idx) + "\n")


def conv_vgm(p, out, tmp):
    os.makedirs(out, exist_ok=True)
    r = subprocess.run(["vgmstream-cli", "-i", "-S", "0", "-o", f"{out}/?03s.wav", p], capture_output=True, text=True)
    if not any(f.endswith(".wav") for f in os.listdir(out)):
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else "no output")


def sgxd_names(path, out):
    """names.txt: 'NNN<TAB>name' per subsong where the SGXD NAME table can be tied to a wave.
    id 0x3000wwww = wave name (Open Tee 2); id 0x2000cccc = cue name, cue c -> RGND region c -> wave (Get a Grip; inferred,
    only used when region count == cue count). Anything else (PS3 pcNN banks) is dumped raw as '?<TAB>0xID<TAB>name'."""
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
    lines = []
    for i_d, n in names:
        if i_d >> 28 == 3:
            lines.append((i_d & 0xffff, n))
        elif i_d >> 28 == 2 and len(reg) == len(cues) and i_d & 0xffff < len(reg):
            lines.append((reg[i_d & 0xffff], n))
        elif i_d:
            lines.append((-1, f"0x{i_d:08x}\t{n}"))
    with open(f"{out}/names.txt", "w") as f:
        for w, n in sorted(lines):
            f.write(f"{w + 1:03d}\t{n}\n" if w >= 0 else f"?\t{n}\n")


def work(a):
    rel, p, ext, byname = a
    out = f"{OUT}/{rel}"
    if os.path.isdir(out) and any(f.endswith(".wav") for f in os.listdir(out)):
        if ext in ("sgd", "sgh") and not os.path.exists(f"{out}/names.txt"):  # resume: just (re)write names
            try: sgxd_names(p, out)
            except Exception: pass
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
        else:
            conv_vgm(p, out, tmp)
            if ext == "sgd":
                sgxd_names(p, out)
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
