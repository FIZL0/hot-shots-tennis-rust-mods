"""I3M motion -> glTF animation (resampled, LINEAR)."""
import numpy as np

import glb
import i3m

FPS = 60.0
CONJUGATE = False  # file quaternion is the node's local rotation (column-vector sense); see notes


def sample_track(tr, duration, fps=FPS):
    n = max(int(round(duration * fps)), 0) + 1
    ts = np.minimum(np.arange(n) / fps, duration) if n > 1 else np.zeros(1)
    if len(tr.times) == 1:
        ts = ts[:1]
    P, R, S = [], [], []
    prev = None
    for t in ts:
        p, q, s = i3m.evaluate(tr, t)
        if CONJUGATE:
            q = q * np.array([-1, -1, -1, 1])
        if prev is not None and np.dot(prev, q) < 0:
            q = -q
        prev = q
        P.append(p)
        R.append(q)
        S.append(s)
    return ts, np.array(P), np.array(R), np.array(S)


def add_animation(b, name, motion, by_name, skeleton=None):
    chans, samps = [], []
    time_acc = {}
    for tr in motion.tracks:
        node = by_name.get(tr.name)
        if node is None:
            continue
        ts, P, R, S = sample_track(tr, motion.duration)
        key = len(ts)
        if key not in time_acc:
            time_acc[key] = b.accessor(ts, glb.FLOAT, "SCALAR", minmax=True)
        tin = time_acc[key]
        for path, vals, typ in (("translation", P, "VEC3"), ("rotation", R, "VEC4"), ("scale", S, "VEC3")):
            if path == "scale" and np.allclose(vals, 1, atol=1e-4):
                continue
            out = b.accessor(vals, glb.FLOAT, typ)
            samps.append({"input": tin, "output": out, "interpolation": "LINEAR"})
            chans.append({"sampler": len(samps) - 1, "target": {"node": node, "path": path}})
    if chans:
        b.add("animations", {"name": name, "channels": chans, "samplers": samps})
