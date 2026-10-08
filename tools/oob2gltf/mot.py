"""Hot Shots Golf: Out of Bounds (PS3) `.mot` skeletal motion parser. Big-endian. See notes/oob.md.

u32 version (0x28), u32 node count, then 0x40 bytes (u32 1,1,1, zeros); per node:
  pstr name; 3 tracks: rotation (u32 n, u32 time[n], f32x4 quat[n]), translation (n, times, f32x4 [w unused]),
  scale (n, times, f32x3); then u32 (1 or 3); then 0x40 bytes (u32 1,1,1, zeros) except after the last node.
Times are signed 3ds Max ticks (4800/s; some clips start at negative times, e.g. -400). Quaternions are (x, y, z, w) of the row-vector local matrix (v' = v·M), i.e. the
glTF (column-vector) rotation is the conjugate.
"""
import struct

import numpy as np

TICKS_PER_SECOND = 4800.0


def parse_mot(d: bytes):
    u32 = lambda o: struct.unpack('>I', d[o:o + 4])[0]
    n = u32(4)
    o = 0x48
    tracks = {}
    for i in range(n):
        l = u32(o)
        name = d[o + 4:o + 4 + l].decode('latin1')
        o += 4 + l
        tr = []
        for vs, nc in ((16, 4), (16, 3), (12, 3)):
            c = u32(o)
            o += 4
            t = np.frombuffer(d[o:o + 4 * c], '>i4').astype(np.float64) / TICKS_PER_SECOND
            o += 4 * c
            v = np.frombuffer(d[o:o + vs * c], '>f4').reshape(c, vs // 4)[:, :nc].astype(np.float64)
            o += vs * c
            tr.append((t, v))
        o += 4 if i == n - 1 else 68
        tracks[name] = tr
    if o != len(d):
        raise ValueError(f'mot parse ended at {o:#x} of {len(d):#x}')
    return tracks


def duration(tracks):
    return max((t[-1] for tr in tracks.values() for t, _ in tr if len(t)), default=0.0)


def start(tracks):
    return min((t[0] for tr in tracks.values() for t, _ in tr if len(t)), default=0.0)


def _tracks(d: bytes, ncomp):
    """Shared layout of .mor / .uva: u32 0x28; u32 nTracks; per track: pstr name; u32 n; i32 time[n];
    f32 value[n][ncomp]. Returns {name: (times s, values n x ncomp)}."""
    u32 = lambda o: struct.unpack('>I', d[o:o + 4])[0]
    o, out = 8, {}
    for _ in range(u32(4)):
        l = u32(o)
        name = d[o + 4:o + 4 + l].decode('latin1')
        o += 4 + l
        c = u32(o)
        t = np.frombuffer(d[o + 4:o + 4 + 4 * c], '>i4').astype(np.float64) / TICKS_PER_SECOND
        o += 4 + 4 * c
        v = np.frombuffer(d[o:o + 4 * c * ncomp], '>f4').reshape(c, ncomp).astype(np.float64)
        o += 4 * c * ncomp
        out[name] = (t, v)
    if o != len(d):
        raise ValueError(f'track parse ended at {o:#x} of {len(d):#x}')
    return out


def parse_mor(d: bytes):
    """Morph-weight animation: {target name: (times, weights n x 1)}."""
    return _tracks(d, 1)


def parse_uva(d: bytes):
    """UV-offset animation: {texobj name (e.g. 'eye__ID'): (times, (du, dv) n x 2)}."""
    return _tracks(d, 2)
