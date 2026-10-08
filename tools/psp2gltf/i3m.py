"""Reader for Clap Hanz "I3D_I3M" motions (.i3m). See notes/psp-formats.md.

Per track (bone name) a list of keys; each key has 11 u16 fields:
  0 time (index into float pool)    1 1/duration of the segment to the next key (float pool)
  2 position  3 rotation  4 scale                       (values, index into vector pool)
  5 pos ctrl  6 rot ctrl  7 scale ctrl  at the END of the segment k -> k+1
  8 pos ctrl  9 rot ctrl 10 scale ctrl  at the START of the segment k -> k+1
Rotation is squad(q_k, q_k+1, s_start, s_end); position/scale are cubic Hermite with tangents
(confidence of the tangent convention: see notes).
"""
import struct
from dataclasses import dataclass

import numpy as np


@dataclass
class Track:
    name: str
    times: np.ndarray       # (k,)
    invdt: np.ndarray       # (k,)
    pos: np.ndarray         # (k, 3) values
    rot: np.ndarray         # (k, 4) quaternion x y z w (file order, see notes)
    scl: np.ndarray         # (k, 3)
    pos_end: np.ndarray     # control/tangent at the end of segment k
    rot_end: np.ndarray
    scl_end: np.ndarray
    pos_start: np.ndarray   # control/tangent at the start of segment k
    rot_start: np.ndarray
    scl_start: np.ndarray


@dataclass
class Motion:
    duration: float
    tracks: list


def load(path):
    return parse(open(path, "rb").read())


def parse(d):
    if d[:8] != b"I3D_I3M\0":
        raise ValueError("not I3D_I3M")
    flags, nfields, ntracks, _one = struct.unpack_from("<4H", d, 0x10)
    duration = struct.unpack_from("<f", d, 0x18)[0]
    o_tracks, o_vec, o_flt, o_rot, _o4 = struct.unpack_from("<5I", d, 0x1C)
    quant = flags not in (0, 1)
    if flags == 1:  # Open Tee 2: f32x4 position/scale pool at o_vec, s16x4 /32767 rotation pool at o_rot
        vec = np.array(struct.unpack_from(f"<{(o_rot - o_vec) // 4}f", d, o_vec), np.float64).reshape(-1, 4)
        rvec = np.array(struct.unpack_from(f"<{(o_flt - o_rot) // 2}h", d, o_rot), np.float64).reshape(-1, 4) / 32767.0
    elif quant:
        q = np.array(struct.unpack_from("<16f", d, 0x30)).reshape(4, 4)
        p_ext, p_ctr, s_ext, s_ctr = q[0, :3], q[1, :3], q[2, :3], q[3, :3]
        nvec = (o_flt - o_vec) // 8
        vec = np.array(struct.unpack_from(f"<{nvec * 4}h", d, o_vec), np.float64).reshape(-1, 4) / 32767.0
    else:
        nvec = (o_flt - o_vec) // 16
        vec = np.array(struct.unpack_from(f"<{nvec * 4}f", d, o_vec), np.float64).reshape(-1, 4)
    if flags != 1:
        rvec = vec
    nflt = (len(d) - o_flt) // 4
    flt = np.array(struct.unpack_from(f"<{nflt}f", d, o_flt))
    tracks = []
    for i in range(ntracks):
        name_off, nf, nk, data_off = struct.unpack_from("<IHHI", d, o_tracks + 12 * i)
        name = d[name_off: d.index(b"\0", name_off)].decode("latin1")
        k = np.array(struct.unpack_from(f"<{nk * nf}H", d, data_off)).reshape(nk, nf)

        def P(col, tangent=False):
            v = vec[k[:, col], :3]
            return p_ctr + p_ext * v if quant else v

        def S(col):
            v = vec[k[:, col], :3]
            return s_ctr + s_ext * v if quant else v

        def R(col):
            r = rvec[k[:, col]]
            n = np.linalg.norm(r, axis=1, keepdims=True)
            return r / np.where(n > 0, n, 1)

        tracks.append(Track(name, flt[k[:, 0]], flt[k[:, 1]], P(2), R(3), S(4), P(5), R(6), S(7), P(8), R(9), S(10)))
    return Motion(duration, tracks)


# ---- evaluation ------------------------------------------------------------------------------
def slerp(a, b, t):
    d = np.dot(a, b)
    if d < 0:
        b, d = -b, -d
    if d > 0.9995:
        r = a + t * (b - a)
        return r / np.linalg.norm(r)
    th = np.arccos(d)
    return (np.sin((1 - t) * th) * a + np.sin(t * th) * b) / np.sin(th)


def squad(q0, q1, s0, s1, t):
    return slerp(slerp(q0, q1, t), slerp(s0, s1, t), 2 * t * (1 - t))


def hermite(p0, m0, p1, m1, t):
    t2, t3 = t * t, t * t * t
    return (2 * t3 - 3 * t2 + 1) * p0 + (t3 - 2 * t2 + t) * m0 + (-2 * t3 + 3 * t2) * p1 + (t3 - t2) * m1


POS_TANGENTS = True   # set False to fall back to linear position/scale interpolation
# Observed over the character motions: stored pos control == -1.3 * (Catmull-Rom tangent * segment dt),
# i.e. the controls are negated, scaled Hermite tangents. The exact engine basis is unknown (EBOOT is
# encrypted); we evaluate a Hermite with m = -stored / 1.3, which reproduces a Catmull-Rom-like curve.
TANGENT_SCALE = -1.0 / 1.3


def evaluate(tr, t):
    """-> (pos(3), quat xyzw(4), scale(3)) at time t (clamped)."""
    n = len(tr.times)
    if n == 1 or t <= tr.times[0]:
        return tr.pos[0], tr.rot[0], tr.scl[0]
    if t >= tr.times[-1]:
        return tr.pos[-1], tr.rot[-1], tr.scl[-1]
    k = int(np.searchsorted(tr.times, t, side="right") - 1)
    u = (t - tr.times[k]) * tr.invdt[k]
    q0, q1 = tr.rot[k], tr.rot[k + 1]
    q = squad(q0, q1 if np.dot(q0, q1) >= 0 else -q1, tr.rot_start[k], tr.rot_end[k], u)
    if POS_TANGENTS:
        c = TANGENT_SCALE
        p = hermite(tr.pos[k], c * tr.pos_start[k], tr.pos[k + 1], c * tr.pos_end[k], u)
        s = hermite(tr.scl[k], c * tr.scl_start[k], tr.scl[k + 1], c * tr.scl_end[k], u)
    else:
        p = tr.pos[k] * (1 - u) + tr.pos[k + 1] * u
        s = tr.scl[k] * (1 - u) + tr.scl[k + 1] * u
    return p, q / np.linalg.norm(q), s
