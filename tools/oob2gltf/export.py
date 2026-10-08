#!/usr/bin/env python3
"""Export Hot Shots Golf: Out of Bounds (PS3) playable characters to glTF 2.0.

  python3 tools/oob2gltf/export.py                 # everything: 17 characters x 6 costumes, textures, anims
  python3 tools/oob2gltf/export.py --pc 0 --costume 0 --check   # one model + check renders

Outputs (all git-ignored): out/models/oob/<slug>/<slug>_cNN.glb, out/anims/oob/<slug>.glb (+ avatar clips),
out/textures/oob/<slug>/cNN/*.png. See notes/oob.md.
"""
import argparse
import glob
import io
import os
import sys

import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dds  # noqa: E402
import glb  # noqa: E402
import mot  # noqa: E402
import paths  # noqa: E402
from rem import Rem, strips_to_tris  # noqa: E402


def trs(m):
    """Row-vector 4x4 (v' = v.M) -> glTF translation, rotation (x, y, z, w), scale."""
    a = m[:3, :3].copy()
    s = np.linalg.norm(a, axis=1)
    s[s == 0] = 1
    r = a / s[:, None]
    if np.linalg.det(r) < 0:
        s[0] = -s[0]
        r[0] = -r[0]
    q = Rotation.from_matrix(r.T).as_quat()
    return m[3, :3].tolist(), q.tolist(), s.tolist()


def add_skeleton(b, nodes):
    base = len(b.g['nodes'])
    for n in nodes:
        t, r, s = trs(n['local'])
        node = {'name': n['name'], 'translation': t, 'rotation': r}
        if not np.allclose(s, 1, atol=1e-4):
            node['scale'] = s
        b.g['nodes'].append(node)
    for i, n in enumerate(nodes):
        if n['parent'] >= 0:
            b.g['nodes'][base + n['parent']].setdefault('children', []).append(base + i)
    b.g['scenes'][0]['nodes'].append(base)
    return base


def png_bytes(im):
    f = io.BytesIO()
    im.save(f, 'PNG', optimize=False)
    return f.getvalue()


def export_textures(pc, costume):
    """All DDS of the costume's texture archive (and the portrait in the core archive) -> PNG."""
    out = os.path.join(paths.OUT_TEX, paths.slug(pc), f'c{costume:02d}')
    os.makedirs(out, exist_ok=True)
    srcs = glob.glob(os.path.join(paths.tex_dir(pc, costume), '*.dds'))
    srcs += glob.glob(os.path.join(paths.PC, f'pc{pc:02d}/pc{pc:02d}_c{costume:02d}_0_core.xb/**/*.dds'), recursive=True)
    for f in srcs:
        dst = os.path.join(out, os.path.splitext(os.path.basename(f))[0].lower() + '.png')
        if not os.path.exists(dst):
            dds.load(open(f, 'rb').read()).save(dst)
    return out


def export_model(pc, costume, out_path):
    r = Rem(open(paths.rem_path(pc, costume), 'rb').read())
    b = glb.Builder()
    root = add_skeleton(b, r.nodes)
    ibm = np.stack([n['inv'] for n in r.nodes])
    ibm[:, :, 3] = [0, 0, 0, 1]  # exact affine (the files carry 1.0000001)
    ibm = ibm.astype(np.float32).reshape(-1, 16)  # a row-vector matrix flattened row-major == glTF column-major
    skin = b.add('skins', {'joints': list(range(root, root + len(r.nodes))), 'skeleton': root,
                           'inverseBindMatrices': b.accessor(ibm)})
    texcache, matmap, prims, skipped = {}, {}, [], []

    def texture(slot, normal=False):
        if slot < 0 or slot >= len(r.texobjs):
            return None, False
        name = r.textures[r.texobjs[slot][1]]
        if name not in texcache:
            p = paths.find_tex(pc, costume, name)
            if not p:
                texcache[name] = (None, False)
            else:
                im = dds.load(open(p, 'rb').read()).convert('RGBA')
                alpha = (not normal) and np.array(im)[:, :, 3].min() < 128
                if normal:
                    im = im.convert('RGB')
                texcache[name] = (b.image(png_bytes(im), os.path.splitext(name)[0].lower()), alpha)
        return texcache[name]

    def material(mi):
        if mi not in matmap:
            m = r.materials[mi]
            base, alpha = texture(m['slots'][0])
            if base is None:
                matmap[mi] = None
                return None
            mat = {'name': m['name'], 'pbrMetallicRoughness': {'baseColorTexture': {'index': base},
                                                              'metallicFactor': 0.0, 'roughnessFactor': 0.8}}
            nrm, _ = texture(m['slots'][4], normal=True)
            if nrm is not None:
                mat['normalTexture'] = {'index': nrm}
            if alpha:
                mat['alphaMode'] = 'MASK'
                mat['alphaCutoff'] = 0.5
            if '__ds' in m['name'].lower() or alpha:
                mat['doubleSided'] = True
            matmap[mi] = b.add('materials', mat)
        return matmap[mi]

    face_prims = []
    for m in r.meshes:
        mi = material(m['material'])
        if mi is None:
            skipped.append(r.materials[m['material']]['name'])
            continue
        p = primitive(b, m, mi, 'normalTexture' in b.g['materials'][mi])
        if p is not None:
            (face_prims if 'targets' in m else prims).append(p)
    mesh = b.add('meshes', {'name': os.path.basename(out_path)[:-4], 'primitives': prims})
    b.g['nodes'].append({'name': 'mesh', 'mesh': mesh, 'skin': skin})
    b.g['scenes'][0]['nodes'].append(len(b.g['nodes']) - 1)
    add_face_node(b, r, face_prims, skin)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    b.write(out_path)
    return r, sorted(set(skipped))


def add_face_node(b, r, face_prims, skin):
    """The morph-bearing primitives (face, teeth, tongue, ...) as their own mesh + node 'face' (same skin), so the
    targets do not have to be repeated as zeros on every body primitive. extras.targetNames = the game's names."""
    if not face_prims:
        return None
    nt = len(r.target_names)
    mesh = b.add('meshes', {'name': 'face', 'primitives': face_prims, 'weights': [0.0] * nt,
                            'extras': {'targetNames': list(r.target_names)}})
    b.g['nodes'].append({'name': 'face', 'mesh': mesh, 'skin': skin})
    b.g['scenes'][0]['nodes'].append(len(b.g['nodes']) - 1)
    return len(b.g['nodes']) - 1


def primitive(b, m, mi=None, tangents=False):
    """glTF primitive of one REM mesh (None if it has no triangles), with its morph targets as sparse accessors."""
    tris = strips_to_tris(m['indices'])
    if not len(tris):
        return None
    n = len(m['pos'])
    joints = np.zeros((n, 4), np.uint8)
    weights = np.zeros((n, 4), np.float32)
    k = m['joints'].shape[1]
    jj = m['joints'].astype(int)
    ww = np.where(jj == 255, 0, m['weights'])
    jj = np.where(jj == 255, 0, jj)
    joints[:, :k] = jj
    weights[:, :k] = ww
    tot = weights.sum(1, keepdims=True)
    weights = np.where(tot > 0, weights / np.where(tot > 0, tot, 1), np.array([1, 0, 0, 0], np.float32))
    nrm = m['normal'] / np.maximum(np.linalg.norm(m['normal'], axis=1, keepdims=True), 1e-8)
    attrs = {'POSITION': b.accessor(m['pos'], 34962, minmax=True),
             'NORMAL': b.accessor(nrm.astype(np.float32), 34962),
             'TEXCOORD_0': b.accessor(np.ascontiguousarray(m['uvs'][0][:, :2]), 34962),
             'JOINTS_0': b.accessor(joints, 34962), 'WEIGHTS_0': b.accessor(weights, 34962)}
    if m['tangent'] is not None and tangents:
        t = m['tangent'] - nrm * (m['tangent'] * nrm).sum(1, keepdims=True)
        tl = np.linalg.norm(t, axis=1, keepdims=True)
        t = np.where(tl > 1e-6, t / np.maximum(tl, 1e-8), np.array([1, 0, 0], np.float32))
        w = np.sign((np.cross(nrm, t) * m['binormal']).sum(1))
        w[w == 0] = 1
        attrs['TANGENT'] = b.accessor(np.c_[t, w].astype(np.float32), 34962)
    p = {'attributes': attrs, 'indices': b.accessor(tris.reshape(-1).astype(
        np.uint16 if n < 65536 else np.uint32), 34963)}
    if mi is not None:
        p['material'] = mi
    if 'targets' in m:
        zero = None
        p['targets'] = []
        for t in m['targets']:
            if t is None:
                zero = zero if zero is not None else b.sparse_vec3(n, [], [])
                p['targets'].append({'POSITION': zero, 'NORMAL': zero})
            else:
                idx, dp, dn = t
                p['targets'].append({'POSITION': b.sparse_vec3(n, idx, dp), 'NORMAL': b.sparse_vec3(n, idx, dn)})
    return p


def add_clip(b, root, nodes, name, tracks, pelvis_scale=1.0, scale_tracks=True, mor=None, face=None, target_names=(),
             uva=None):
    """One glTF animation from a parsed .mot: rotation for every node, translation for Bip01Pelvis only (scaled by
    pelvis_scale, for clips authored on another skeleton such as the chibi lobby avatar). The other translation
    tracks are dropped: on Biped bones they equal the bind pose, and on the dynamic (hair/earring/cloth) bones they
    hold values in some other space that fling those parts off the body."""
    idx = {n['name']: i for i, n in enumerate(nodes)}
    chans, samps = [], []
    starts = [mot.start(tracks)] + [t[0] for tr in (mor or {}, uva or {}) for t, _ in tr.values() if len(t)]
    t0 = min(min(starts), 0.0)  # glTF wants times >= 0: clips with pre-roll are shifted to start at 0

    def sampler(times, vals, flat=False):
        t, keep = np.unique((times - t0).astype(np.float32), return_index=True)
        out = vals[keep].astype(np.float32)
        samps.append({'input': b.accessor(t, minmax=True), 'output': b.accessor(out.reshape(-1) if flat else out),
                      'interpolation': 'LINEAR'})
        return len(samps) - 1

    for nm, ((rt, rv), (pt, pv), (st, sv)) in tracks.items():
        if nm not in idx:
            continue
        node = root + idx[nm]
        if len(rt):
            q = rv.copy()
            q[:, :3] *= -1  # conjugate: row-vector -> column-vector rotation
            q /= np.linalg.norm(q, axis=1, keepdims=True)
            for i in range(1, len(q)):  # hemisphere continuity
                if np.dot(q[i], q[i - 1]) < 0:
                    q[i] = -q[i]
            chans.append({'sampler': sampler(rt, q), 'target': {'node': node, 'path': 'rotation'}})
        if len(pt) and nm == 'Bip01Pelvis':
            chans.append({'sampler': sampler(pt, pv * pelvis_scale), 'target': {'node': node, 'path': 'translation'}})
        if len(st) and scale_tracks and not np.allclose(sv, 1, atol=1e-3):
            chans.append({'sampler': sampler(st, sv), 'target': {'node': node, 'path': 'scale'}})
    if mor and face is not None:
        # morph weights: one sampler for all targets on the union of the track times (tracks are linear, so
        # resampling at the union is exact); targets without a track stay 0
        tr = {k: v for k, v in mor.items() if k in target_names and len(v[0])}
        if tr:
            ts = np.unique(np.concatenate([t for t, _ in tr.values()]))
            w = np.zeros((len(ts), len(target_names)))
            for k, (t, v) in tr.items():
                w[:, target_names.index(k)] = np.interp(ts, t, v[:, 0])
            chans.append({'sampler': sampler(ts, w, flat=True), 'target': {'node': face, 'path': 'weights'}})
    if chans:
        a = {'name': name, 'channels': chans, 'samplers': samps}
        if uva:  # UV-offset tracks (eye texture swaps), not expressible in core glTF
            a['extras'] = {'uva': [{'texobj': k, 'times': (t - t0).round(6).tolist(), 'offsets': v.round(6).tolist()}
                                   for k, (t, v) in uva.items()]}
        b.add('animations', a)


def export_anims(pc, out_path, rem):
    """Skeleton + the untextured morph mesh ('face', same skin) + every clip. A clip gets the .mor (morph weights)
    and .uva (animation extras) of the same name; .mor files without a .mot become weight-only clips."""
    b = glb.Builder()
    root = add_skeleton(b, rem.nodes)
    ibm = np.stack([n['inv'] for n in rem.nodes])
    ibm[:, :, 3] = [0, 0, 0, 1]
    skin = b.add('skins', {'joints': list(range(root, root + len(rem.nodes))), 'skeleton': root,
                           'inverseBindMatrices': b.accessor(ibm.astype(np.float32).reshape(-1, 16))})
    face = add_face_node(b, rem, [p for p in (primitive(b, m) for m in rem.meshes if 'targets' in m) if p], skin)
    tn = list(rem.target_names or [])
    mors = {k: mot.parse_mor(open(f, 'rb').read()) for k, f in paths.motion_files(pc, 'mor')}
    uvas = {k: mot.parse_uva(open(f, 'rb').read()) for k, f in paths.motion_files(pc, 'uva')}
    mots = dict(paths.motion_files(pc))
    names = []
    for name in sorted(set(mots) | set(mors)):
        tracks = mot.parse_mot(open(mots[name], 'rb').read()) if name in mots else {}
        add_clip(b, root, rem.nodes, name, tracks, mor=mors.get(name), face=face, target_names=tn,
                 uva=uvas.get(name))
        names.append(name)
    av = Rem(open(paths.avatar_body_rem(), 'rb').read())
    h = lambda r: next(n['world'][3, 1] for n in r.nodes if n['name'] == 'Bip01Pelvis')
    for name, f in paths.avatar_motion_files():
        add_clip(b, root, rem.nodes, 'avatar_' + name, mot.parse_mot(open(f, 'rb').read()),
                 pelvis_scale=h(rem) / h(av), scale_tracks=False)
        names.append('avatar_' + name)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    b.write(out_path)
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pc', type=int, action='append')
    ap.add_argument('--costume', type=int, action='append')
    ap.add_argument('--no-anims', action='store_true')
    ap.add_argument('--no-textures', action='store_true')
    a = ap.parse_args()
    pcs = a.pc or list(range(len(paths.ROSTER)))
    costumes = a.costume or list(range(6))
    for pc in pcs:
        slug = paths.slug(pc)
        rem0 = None
        for c in costumes:
            if not paths.rem_path(pc, c):
                continue
            out = os.path.join(paths.OUT_MODELS, slug, f'{slug}_c{c:02d}.glb')
            r, skipped = export_model(pc, c, out)
            rem0 = rem0 or r
            if not a.no_textures:
                export_textures(pc, c)
            print(f'{out}: {len(r.nodes)} nodes, {len(r.meshes)} meshes' + (f', skipped untextured {skipped}' if skipped else ''))
        if not a.no_anims:
            if rem0 is None:
                rem0 = Rem(open(paths.rem_path(pc, 0), 'rb').read())
            out = os.path.join(paths.OUT_ANIMS, f'{slug}.glb')
            names = export_anims(pc, out, rem0)
            print(f'{out}: {len(names)} clips')


if __name__ == '__main__':
    main()
