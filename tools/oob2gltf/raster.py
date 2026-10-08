"""Tiny numpy z-buffer rasterizer for check renders (orthographic, textured, flat lambert)."""
import numpy as np
from PIL import Image


def _proj(p, view):
    if view == 'front':
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
    elif view == 'side':  # from the character's left (+X), looking toward -X
        x, y, z = -p[:, 2], p[:, 1], p[:, 0]
    elif view == 'back':
        x, y, z = -p[:, 0], p[:, 1], -p[:, 2]
    else:
        x, y, z = p[:, 2], p[:, 1], -p[:, 0]
    return np.stack([x, y, z], 1)


def render(meshes, W=600, H=900, view='front', out=None, bounds=None):
    """meshes: list of (pos Nx3, tris Mx3, uv Nx2|None, tex HxWx4 uint8|None, rgb). Returns a PIL image."""
    P = _proj(np.concatenate([m[0] for m in meshes]), view)
    lo, hi = (P.min(0), P.max(0)) if bounds is None else bounds
    s = min((W - 20) / (hi[0] - lo[0] + 1e-9), (H - 20) / (hi[1] - lo[1] + 1e-9))
    img = np.full((H, W, 3), 40, np.uint8)
    zb = np.full((H, W), -1e9)
    L = np.array([0.3, 0.5, 0.8])
    L /= np.linalg.norm(L)
    for pos, tris, uv, tex, col in meshes:
        Q = _proj(np.asarray(pos, float), view)
        X = (Q[:, 0] - lo[0]) * s + 10
        Y = H - 10 - (Q[:, 1] - lo[1]) * s
        Z = Q[:, 2]
        for a, b, c in tris:
            x0, y0, x1, y1, x2, y2 = X[a], Y[a], X[b], Y[b], X[c], Y[c]
            den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(den) < 1e-9:
                continue
            n = np.cross(Q[b] - Q[a], Q[c] - Q[a])
            nn = np.linalg.norm(n)
            sh = 0.35 + 0.65 * abs(n @ L) / nn if nn > 0 else 1
            xmin, xmax = max(int(min(x0, x1, x2)), 0), min(int(max(x0, x1, x2)) + 1, W - 1)
            ymin, ymax = max(int(min(y0, y1, y2)), 0), min(int(max(y0, y1, y2)) + 1, H - 1)
            if xmin > xmax or ymin > ymax:
                continue
            xs, ys = np.meshgrid(np.arange(xmin, xmax + 1) + 0.5, np.arange(ymin, ymax + 1) + 0.5)
            w0 = ((y1 - y2) * (xs - x2) + (x2 - x1) * (ys - y2)) / den
            w1 = ((y2 - y0) * (xs - x2) + (x0 - x2) * (ys - y2)) / den
            w2 = 1 - w0 - w1
            m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            if not m.any():
                continue
            z = (w0 * Z[a] + w1 * Z[b] + w2 * Z[c])[m]
            iy = (ys[m] - 0.5).astype(int)
            ix = (xs[m] - 0.5).astype(int)
            ok = z > zb[iy, ix]
            iy, ix, z = iy[ok], ix[ok], z[ok]
            if tex is not None and uv is not None:
                bw = [w[m][ok] for w in (w0, w1, w2)]
                u = bw[0] * uv[a, 0] + bw[1] * uv[b, 0] + bw[2] * uv[c, 0]
                v = bw[0] * uv[a, 1] + bw[1] * uv[b, 1] + bw[2] * uv[c, 1]
                th, tw = tex.shape[:2]
                tx = np.floor(u * tw).astype(int) % tw
                ty = np.floor(v * th).astype(int) % th
                cc = tex[ty, tx, :3].astype(float)
                keep = tex[ty, tx, 3] > 64
                iy, ix, z, cc = iy[keep], ix[keep], z[keep], cc[keep]
            else:
                cc = np.array(col, float)[None].repeat(len(iy), 0)
            zb[iy, ix] = z
            img[iy, ix] = np.clip(cc * sh, 0, 255).astype(np.uint8)
    im = Image.fromarray(img)
    if out:
        im.save(out)
    return im


def montage(images, out):
    c = Image.new('RGB', (sum(i.width for i in images), max(i.height for i in images)))
    x = 0
    for i in images:
        c.paste(i, (x, 0))
        x += i.width
    c.save(out)
