"""Clap Hanz PSP TAT (texture animation) reader. See notes/psp-formats.md.

Layout (LE): u32 ntracks; per track:
  u32 L, char target[L] (NUL padded, "<material>:<default texture>")
  u32 ntex; ntex x {u32 L, char stem[L]}  (GIM stems)
  u32 nkeys; f32 time[nkeys] (s); u32 tex_index[nkeys]  (step: index holds until next key)
"""
import struct


def _str(b, o):
    n, = struct.unpack_from("<I", b, o)
    return b[o + 4:o + 4 + n].split(b"\0")[0].decode("ascii"), o + 4 + n


def parse(data):
    o = 0
    nt, = struct.unpack_from("<I", data, o); o += 4
    tracks = []
    for _ in range(nt):
        target, o = _str(data, o)
        ntex, = struct.unpack_from("<I", data, o); o += 4
        tex = []
        for _ in range(ntex):
            s, o = _str(data, o)
            tex.append(s)
        nk, = struct.unpack_from("<I", data, o); o += 4
        times = list(struct.unpack_from(f"<{nk}f", data, o)); o += 4 * nk
        idx = list(struct.unpack_from(f"<{nk}I", data, o)); o += 4 * nk
        mat, _, default = target.partition(":")
        tracks.append({"material": mat, "default": default, "textures": tex,
                       "keys": [[round(t, 5), i] for t, i in zip(times, idx)]})
    if o != len(data):
        raise ValueError(f"trailing {len(data) - o} bytes")
    return tracks


def load(path):
    with open(path, "rb") as f:
        return parse(f.read())


if __name__ == "__main__":
    import sys, json
    for p in sys.argv[1:]:
        print(p)
        for t in load(p):
            print(" ", json.dumps(t))
