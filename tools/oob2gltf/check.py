#!/usr/bin/env python3
"""Check render of the exported glTF (reads the .glb back, independent of the REM/MOT code path).

  python3 tools/oob2gltf/check.py MODEL.glb OUT.png [ANIMS.glb CLIP t0 t1 ...]
  python3 tools/oob2gltf/check.py --face MODEL.glb OUT.png     # head close-up, neutral + every morph target at 1
Renders front + side views for the bind pose (no clip) or for each time of CLIP.
"""
import io
import json
import os
import struct
import sys

import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation, Slerp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import raster  # noqa: E402

NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
CT = {5126: '<f4', 5125: '<u4', 5123: '<u2', 5121: 'u1'}


class Glb:
    def __init__(self, path):
        d = open(path, 'rb').read()
        jl = struct.unpack_from('<I', d, 12)[0]
        self.g = json.loads(d[20:20 + jl])
        self.bin = d[20 + jl + 8:]

    def view(self, i):
        v = self.g['bufferViews'][i]
        return self.bin[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']]

    def _raw(self, view, ct, count, off=0):
        v = self.g['bufferViews'][view]
        return np.frombuffer(self.bin, CT[ct], count, v.get('byteOffset', 0) + off)

    def acc(self, i):
        a = self.g['accessors'][i]
        n = NC[a['type']]
        if 'bufferView' in a:
            arr = self._raw(a['bufferView'], a['componentType'], a['count'] * n, a.get('byteOffset', 0)).copy()
        else:
            arr = np.zeros(a['count'] * n, CT[a['componentType']])
        if 'sparse' in a:
            sp = a['sparse']
            ix = self._raw(sp['indices']['bufferView'], sp['indices']['componentType'], sp['count'],
                           sp['indices'].get('byteOffset', 0)).astype(int)
            vals = self._raw(sp['values']['bufferView'], a['componentType'], sp['count'] * n,
                             sp['values'].get('byteOffset', 0))
            arr = arr.reshape(-1, n)
            arr[ix] = vals.reshape(-1, n)
            arr = arr.reshape(-1)
        return arr.reshape(a['count'], n) if n > 1 else arr

    def image(self, tex):
        src = self.g['textures'][tex]['source']
        return np.array(Image.open(io.BytesIO(self.view(self.g['images'][src]['bufferView']))).convert('RGBA'))


def local_mats(g, nodes, anim=None, t=0.0):
    trs = {i: [np.array(n.get('translation', [0, 0, 0]), float), np.array(n.get('rotation', [0, 0, 0, 1]), float),
               np.array(n.get('scale', [1, 1, 1]), float)] for i, n in enumerate(nodes)}
    if anim is not None:
        ag, a = anim
        names = {n['name']: i for i, n in enumerate(nodes)}
        for ch in a['channels']:
            nm = ag.g['nodes'][ch['target']['node']]['name']
            if nm not in names or ch['target']['path'] == 'weights':
                continue
            s = a['samplers'][ch['sampler']]
            ts, vs = ag.acc(s['input']), ag.acc(s['output']).astype(float)
            tt = np.clip(t, ts[0], ts[-1])
            p = ch['target']['path']
            if p == 'rotation':
                val = vs[0] if len(ts) == 1 else Slerp(ts, Rotation.from_quat(vs))(tt).as_quat()
            else:
                val = np.array([np.interp(tt, ts, vs[:, k]) for k in range(vs.shape[1])])
            trs[names[nm]][{'translation': 0, 'rotation': 1, 'scale': 2}[p]] = val
    out = []
    for i in range(len(nodes)):
        tr, q, s = trs[i]
        m = np.eye(4)
        m[:3, :3] = Rotation.from_quat(q).as_matrix() @ np.diag(s)
        m[:3, 3] = tr
        out.append(m)
    return out


def anim_weights(ag, a, t):
    """{target name: weight} of the clip's morph-weight channel at time t (names from the target mesh's extras)."""
    out = {}
    for ch in a['channels']:
        if ch['target']['path'] != 'weights':
            continue
        names = ag.g['meshes'][ag.g['nodes'][ch['target']['node']]['mesh']]['extras']['targetNames']
        s = a['samplers'][ch['sampler']]
        ts, vs = ag.acc(s['input']), ag.acc(s['output']).reshape(-1, len(names))
        tt = np.clip(t, ts[0], ts[-1])
        out.update({nm: float(np.interp(tt, ts, vs[:, k])) for k, nm in enumerate(names)})
    return out


def worlds(nodes, loc):
    par = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
    w = [None] * len(nodes)

    def get(i):
        if w[i] is None:
            w[i] = (get(par[i]) @ loc[i]) if i in par else loc[i]
        return w[i]
    return [get(i) for i in range(len(nodes))]


def posed_meshes(m, anim=None, t=0.0, weights=None):
    """weights: {target name: weight} applied to meshes with extras.targetNames."""
    g = m.g
    W = worlds(g['nodes'], local_mats(g, g['nodes'], anim, t))
    out = []
    for node in g['nodes']:
        if 'mesh' not in node:
            continue
        sk = g['skins'][node['skin']]
        ibm = m.acc(sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)
        J = [W[j] @ ibm[k] for k, j in enumerate(sk['joints'])]
        mesh = g['meshes'][node['mesh']]
        names = mesh.get('extras', {}).get('targetNames', [])
        for p in mesh['primitives']:
            at = p['attributes']
            base = m.acc(at['POSITION']).astype(float)
            for k, tg in enumerate(p.get('targets', [])):
                wt = (weights or {}).get(names[k], 0.0)
                if wt:
                    base = base + wt * m.acc(tg['POSITION'])
            pos = np.c_[base, np.ones(len(base))]
            js, ws = m.acc(at['JOINTS_0']).astype(int), m.acc(at['WEIGHTS_0'])
            sp = np.zeros((len(pos), 3))
            for k in range(4):
                for j in np.unique(js[:, k]):
                    sel = js[:, k] == j
                    sp[sel] += ws[sel, k, None] * (pos[sel] @ J[j].T)[:, :3]
            mat = g['materials'][p['material']]
            tex = m.image(mat['pbrMetallicRoughness']['baseColorTexture']['index'])
            out.append((sp, m.acc(p['indices']).reshape(-1, 3), m.acc(at['TEXCOORD_0']), tex, (200, 200, 200)))
    return out


def face_sheet(model, out, cols=5):
    """Contact sheet: front view of the head, neutral and each morph target at weight 1."""
    from PIL import ImageDraw
    m = Glb(model)
    face = next(n for n in m.g['nodes'] if n.get('name') == 'face')
    names = m.g['meshes'][face['mesh']]['extras']['targetNames']
    ms0 = posed_meshes(m)
    fp = np.concatenate([m.acc(p['attributes']['POSITION']) for p in m.g['meshes'][face['mesh']]['primitives']])
    lo, hi = fp.min(0), fp.max(0)
    c = (lo + hi) / 2
    r = max(hi[0] - lo[0], hi[1] - lo[1]) * 0.45
    lo3, hi3 = np.array([c[0] - r, c[1] - r, -9]), np.array([c[0] + r, c[1] + r, 9])

    def crop(ms):  # drop triangles outside the head box (speed)
        out = []
        for pos, tris, uv, tex, col in ms:
            inb = np.all((pos[:, :2] > lo3[:2] - 0.05) & (pos[:, :2] < hi3[:2] + 0.05), 1)
            t = tris[inb[tris].any(1)]
            if len(t):
                out.append((pos, t, uv, tex, col))
        return out
    ims = []
    for nm in [None] + names:
        ms = crop(posed_meshes(m, weights={nm: 1.0} if nm else None))
        im = raster.render(ms, 260, 260, bounds=(lo3, hi3))
        ImageDraw.Draw(im).text((6, 4), nm or '(neutral)', fill=(255, 255, 0))
        ims.append(im)
    rows = [ims[i:i + cols] for i in range(0, len(ims), cols)]
    sheet = Image.new('RGB', (260 * cols, 260 * len(rows)), (40, 40, 40))
    for y, row in enumerate(rows):
        for x, im in enumerate(row):
            sheet.paste(im, (260 * x, 260 * y))
    sheet.save(out)


def main():
    if sys.argv[1] == '--face':
        return face_sheet(sys.argv[2], sys.argv[3])
    model, out = sys.argv[1], sys.argv[2]
    m = Glb(model)
    ims = []
    if len(sys.argv) > 3:
        ag = Glb(sys.argv[3])
        a = next(x for x in ag.g['animations'] if x['name'] == sys.argv[4])
        for t in [float(x) for x in sys.argv[5:]] or [0.0]:
            ms = posed_meshes(m, (ag, a), t, anim_weights(ag, a, t))
            ims += [raster.render(ms, 400, 600), raster.render(ms, 400, 600, view='side')]
    else:
        ms = posed_meshes(m)
        ims += [raster.render(ms, 400, 600), raster.render(ms, 400, 600, view='side'),
                raster.render(ms, 400, 600, view='back')]
    raster.montage(ims, out)


if __name__ == '__main__':
    main()
