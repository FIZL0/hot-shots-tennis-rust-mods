"""Out of Bounds' static `.rem` models (course ground, trees, props, structures, skies): the character format
(rem.py, notes/oob.md) with mesh blocks that carry no joint or weight streams (header word 2 = 0).

`meshes(rem)` -> [dict(material, tris (n, 3) u32, pos, normal, color (n, 4) u8, uvs [(n, 2)], tangent?)] in model
space (metres, Y up)."""
import struct

import numpy as np

from rem import strips_to_tris


def _chain(d, o, n, nw):
    """The vertex streams from `o` (each `u32 n, u32 k, data`): pos, normal (f32x3), colour (u8x4), uv sets (f32x2),
    [tangent, binormal (f32x3)], [joints u8 x nw, weights f32 x nw]."""
    u = lambda p: struct.unpack('>I', d[p:p + 4])[0] if p + 4 <= len(d) else None
    out = []
    while u(o) == n:
        k = u(o + 4)
        if not 1 <= k <= 8:
            break
        i = len(out)
        byte = i == 2 or (nw and k == nw and u(o + 8 + n * k) == n and u(o + 8 + n * k + 4) == nw)
        es = 1 if byte else 4
        p = o + 8 + n * k * es
        if p > len(d):
            break
        out.append(np.frombuffer(d[o + 8:p], 'u1' if byte else '>f4').reshape(n, k))
        o = p
    return out, o


def meshes(r):
    d = r.d
    lo, end = r.mesh_start, r.node_start
    u = lambda p: struct.unpack('>I', d[p:p + 4])[0]
    out = []
    o = lo
    while o < end - 8:
        n = u(o)
        if 3 <= n < 200000 and u(o + 4) == 3 and o + 8 + n * 12 + 8 < end and u(o + 8 + n * 12) == n and u(o + 12 + n * 12) == 3:
            q = None
            for c in range(3, 600000):
                qq = o - 4 - 2 * c
                if qq < lo:
                    break
                if u(qq) == c:
                    q = qq
                    break
            if q is not None and q - 64 >= 0:
                hdr = struct.unpack('>15i', d[q - 64:q - 4])
                mat, has_tan, nw = hdr[0], hdr[1], hdr[2]
                if 0 <= mat < len(r.materials) and has_tan in (0, 1) and 0 <= nw <= 4:
                    st, e = _chain(d, o, n, nw)
                    nuv = len(st) - 3 - 2 * has_tan - (2 if nw else 0)
                    idx = np.frombuffer(d[q + 4:q + 4 + 2 * u(q)], '>u2').astype(np.int64)
                    good = idx[idx < 0xfffe]
                    if len(st) >= 3 and st[2].dtype == np.uint8 and nuv >= 0 and (not len(good) or good.max() < n):
                        out.append(dict(offset=q, header=hdr, material=mat, tris=strips_to_tris(idx),
                                        pos=st[0].astype(np.float32), normal=st[1].astype(np.float32), color=st[2],
                                        uvs=[s.astype(np.float32) for s in st[3:3 + nuv]],
                                        tangent=st[3 + nuv].astype(np.float32) if has_tan else None))
                        o = e
                        continue
        o += 1
    return out
