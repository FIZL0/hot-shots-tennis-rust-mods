"""Where a golf hole could hold a tennis court (HST-Remastered M8f10).

A spot hosts a court when a FOOT_L x FOOT_W metre rectangle (the doubles court plus the smallest run-off of HST's
own disc courts, Wafu's 8.2 m behind the baselines and Alps' 4.6 m beside the sidelines, rounded up) lies on the
hole's height map (`course.Hmp`), varies in height by at most FLAT metres (a court slab laid at its highest point
then covers it), holds no water and no placed tree, building or prop. Every yaw in YAWS is tried.
"""
import numpy as np
from scipy import ndimage

from course import CELL

FOOT_L, FOOT_W = 40.0, 20.0          # 23.77 + 2 x 8.2, 10.97 + 2 x 4.6, rounded up
FLAT = 0.5                           # metres of height range a laid court slab may hide
YAWS = range(0, 180, 15)             # court length direction, degrees from +Z toward +X
WATER = 27                           # the same lie code in Fore!, Open Tee 2 and Out of Bounds (flat cells)


def rotated(hmp, yaw):
    """The map resampled on a grid turned by `yaw` (u across the court, v along it; nearest cell): heights (NaN
    off the map), lies, and the grid's (u0, v0)."""
    a = np.radians(yaw)
    c, s = np.cos(a), np.sin(a)
    cx = hmp.x0 + np.array([0, hmp.nx, 0, hmp.nx]) * CELL
    cz = hmp.z0 + np.array([0, 0, hmp.nz, hmp.nz]) * CELL
    cu, cv = cx * c - cz * s, cx * s + cz * c
    u0, v0 = cu.min(), cv.min()
    nu, nv = int((cu.max() - u0) / CELL) + 1, int((cv.max() - v0) / CELL) + 1
    gu, gv = np.meshgrid(u0 + (np.arange(nu) + 0.5) * CELL, v0 + (np.arange(nv) + 0.5) * CELL)
    r = np.floor((gu * c + gv * s - hmp.x0) / CELL).astype(int)
    k = np.floor((-gu * s + gv * c - hmp.z0) / CELL).astype(int)
    ok = (r >= 0) & (r < hmp.nx) & (k >= 0) & (k < hmp.nz)
    r, k = np.clip(r, 0, hmp.nx - 1), np.clip(k, 0, hmp.nz - 1)
    lie = np.where(ok, hmp.lie[r, k], 0)
    return np.where(ok, hmp.y[r, k], np.nan), lie, (u0, v0), (gu, gv)


def search(hmp, blockers, yaws=YAWS):
    """Best spot per yaw; `blockers`: (x, z, radius) of placed objects. A list of dicts (yaw, centre x z, top =
    the highest point's y in the map's own convention, height range, fits) sorted by range, the fitting ones first."""
    out = []
    wl, ww = int(np.ceil(FOOT_L / CELL)), int(np.ceil(FOOT_W / CELL))
    for yaw in yaws:
        h, lie, _, (gu, gv) = rotated(hmp, yaw)
        bad = np.isnan(h) | (lie == 0) | (lie == WATER)
        a = np.radians(yaw)
        c, s = np.cos(a), np.sin(a)
        for bx, bz, r in blockers:
            bu, bv = bx * c - bz * s, bx * s + bz * c
            bad |= (gu - bu) ** 2 + (gv - bv) ** 2 <= r * r
        # window (wl rows along v, ww columns along u): range = max - min; a bad cell or the grid's edge makes it
        # infinite
        mx = ndimage.maximum_filter(np.where(bad, np.inf, h), size=(wl, ww), mode="constant", cval=np.inf)
        mn = ndimage.minimum_filter(np.where(bad, -np.inf, h), size=(wl, ww), mode="constant", cval=-np.inf)
        rng = mx - mn
        rng[~np.isfinite(rng)] = np.inf
        if not np.isfinite(rng).any():
            continue
        j = np.unravel_index(np.argmin(rng), rng.shape)
        cu, cv = gu[j], gv[j]
        x, z = cu * c + cv * s, -cu * s + cv * c
        # the lies under it (ndimage centres an even window one cell past the middle)
        win = lie[j[0] - wl // 2:j[0] + (wl + 1) // 2, j[1] - ww // 2:j[1] + (ww + 1) // 2]
        lies = {int(k): int(n) for k, n in zip(*np.unique(win, return_counts=True))}
        out.append({"yaw": yaw, "x": round(float(x), 1), "z": round(float(z), 1), "range": round(float(rng[j]), 2),
                    "fits": bool(rng[j] <= FLAT), "lies": lies})
    return sorted(out, key=lambda o: (not o["fits"], o["range"]))
