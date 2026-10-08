"""Bind/animated world matrices and CPU skinning (row-vector convention, as stored in the files)."""
import numpy as np
from scipy.spatial.transform import Rotation, Slerp


def sample(tracks, name, t, bind_local):
    """Local row-vector matrix of node `name` at time t (bind local where the motion has no track)."""
    if name not in tracks:
        return bind_local
    (rt, rv), (pt, pv), (st, sv) = tracks[name]

    def lerp(times, vals):
        if len(times) == 1:
            return vals[0]
        return np.array([np.interp(t, times, vals[:, k]) for k in range(vals.shape[1])])

    if len(rt) == 0:
        rm = bind_local[:3, :3]
    elif len(rt) == 1:
        rm = Rotation.from_quat(rv[0]).as_matrix()
    else:
        tt = np.clip(t, rt[0], rt[-1])
        rm = Slerp(rt, Rotation.from_quat(rv))(tt).as_matrix()
    p = lerp(pt, pv) if len(pt) else bind_local[3, :3]
    s = lerp(st, sv) if len(st) else np.ones(3)
    m = np.eye(4)
    m[:3, :3] = np.diag(s) @ rm
    m[3, :3] = p
    return m


def world(nodes, locals_):
    w = []
    for i, n in enumerate(nodes):
        w.append(locals_[i] @ w[n['parent']] if n['parent'] >= 0 else locals_[i])
    return w


def skin(mesh, nodes, worlds):
    pos = np.c_[mesh['pos'], np.ones(len(mesh['pos']))]
    out = np.zeros((len(pos), 3))
    for k in range(mesh['joints'].shape[1]):
        j = mesh['joints'][:, k].astype(int)
        w = mesh['weights'][:, k]
        for b in np.unique(j):
            if b == 255:
                continue
            sel = j == b
            m = nodes[b]['inv'] @ worlds[b]
            out[sel] += w[sel, None] * (pos[sel] @ m)[:, :3]
    return out
