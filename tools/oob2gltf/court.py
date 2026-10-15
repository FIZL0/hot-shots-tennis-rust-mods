#!/usr/bin/env python3
"""Hot Shots Golf: Out of Bounds (PS3) holes as HST court mods (standard/HST-COURT-UMPIRE-STANDARD.md §2,
notes/venues.md; open-tennis M8f10a3). The Out of Bounds counterpart of `fore2gltf court` (M8f10a2): same rules,
same laid court.

  python3 tools/oob2gltf/court.py out/files/oob out/venues/oob.json "iso/Hot Shots Tennis (USA).iso" out/mods [course…] [--end -] [--data DIR]

Per course (1–7, or the ones named) the survey's flattest spot whose ground the hole model draws becomes
`out/mods/oob_cCC_<stem>/` with `mod.json`, `court.glb` and `sky.glb`:
- `court.glb`: under `game_space`, `oob_spot` (the venue: Out of Bounds' Y-up metres turned 180° about Z into HST's
  Y-down game space, moved so the spot's centre lands on HST's court origin, its length along HST's z and its
  highest ground 3 cm under y = 0) holds the hole's ground model (`groundHH.xb`) and its placed trees, props,
  structures and billboards (the per-kind plant files of `half_p10.xb` / `half_p01.xb`); trees further than 60 m
  from the court use the game's own lowest level of detail (`_lvN`). Those within 45 m are `__clear`. Beside it
  `court`: the laid court (fore2gltf's: slab over the run-off, lines at HST's judging edges, net, posts, the
  umpire's chair under the layout court's chair, read from the HST disc by `fore2gltf chairs`).
- `sky.glb`: the course's sky dome, clouds and panorama (`bg/`, `_p10` front nine and h00, `_p01` back nine) at
  the eye, turned with the venue.
- `mod.json`: surface hard where the ground under the court is paved (car parks, paths), else grass; layout = the
  disc court of that surface whose run-off is closest to the flat ground measured round the spot.
`--end -` turns every venue round (180°). The hole models' own textures are loose files outside the xb archives
(`PS3_GAME/USRDIR/data/course/courseCC/hole/*.dds`): `--data DIR` names that `data` folder; by default
`out/files/oob/PS3_GAME/USRDIR/data`, else the first `iso/Hot Shots Golf - Out of Bounds*/**/PS3_GAME/USRDIR/data`.
"""
import io
import json
import math
import os
import re
import struct
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dds  # noqa: E402
from rem import Rem  # noqa: E402
import static  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FORE2GLTF = ROOT / 'tools/fore2gltf/target/release/fore2gltf'

# Course stems and names (notes/venues.md: the help text and challengeitem.csv; 07's name wasn't found)
COURSES = {1: ('georama', 'Highland Country Club'), 2: ('okinawa', 'Okinawa Golf Resort'), 3: ('eu', 'Euro Classic GC'),
           4: ('africa', 'Great Safari CC'), 5: ('fjord', 'Silver Peaks GC'), 6: ('major', 'The Crown Links'),
           7: ('aussie', 'Out of Bounds course 7')}
# HST's disc courts (layout 0–10): surface and run-off behind +z, -z baselines and beside +x, -x sidelines
# (fore2gltf court.rs `HST`)
HST = [('clay', [8.5, 8.5, 35.0, 4.9]), ('clay', [40.0, 40.0, 40.0, 40.0]), ('clay', [40.0, 13.1, 40.0, 37.7]),
       ('hard', [10.7, 10.7, 25.8, 8.4]), ('grass', [21.3, 21.3, 9.6, 9.4]), ('grass', [18.6, 29.2, 27.8, 10.8]),
       ('hard', [14.9, 14.4, 7.6, 7.6]), ('grass', [40.0, 13.6, 7.0, 14.5]), ('clay', [17.3, 15.5, 40.0, 40.0]),
       ('grass', [9.0, 9.0, 4.6, 3.2]), ('hard', [8.2, 8.2, 4.6, 4.6])]
HST_NAMES = ['Alps', 'Resort', 'Western', 'Park', 'Wim', 'Kar', 'Extra', 'Jungle', 'Kasen', 'Greece', 'Wafu']

# HST's judging edges, net posts and net heights; the height map's cell, the slab's height range, its sink, the
# ground tolerance, the seed run-off, the clear radius (fore2gltf court.rs)
DOUBLES, SINGLES, SERVICE, BASE = 5.485, 4.115, 6.4, 11.885
POST, NET_MID, NET_POST = 6.4, 0.914, 1.07
CELL, FLAT, SINK, GROUND = 1.3, 0.5, 0.03, 1.0
SEED = [3.0, 3.0, 2.0, 2.0]
CLEAR_WITHIN = 45.0
# Out of Bounds' plant kinds (u16 category at 0): what each keeps clear round its origin (metres times its scale
# clamped 1–4, tools/venues/venues.py `BLOCK`)
KINDS = {0x14: ('tree', 3.0), 0x15: ('prop', 2.0), 0x16: ('structure', 12.0), 0x17: ('billboard', 3.0)}
# Props, structures and billboards also block where their model stands (their vertices, not just a radius):
# clubhouses and car-park carts are bigger than 12 m. The ground model's own pieces standing this far above the
# height map (kerbs, walls, planters) block too.
STANDING = 0.3
# Trees this far from the court use their lowest level of detail
TREE_LOD = 60.0
# Ground-model material names that mean paved ground (the court goes on as a hard court there)
PAVED = ('asphalt', 'cart', 'road', 'concrete', 'paving', 'tile', 'brick', 'brock', 'stone', 'parking', 'floor')


# ---- the height map (big-endian HMP, OOB space: Y up) ----------------------------------------------------------
class Hmp:
    def __init__(self, d):
        self.x0, self.z0, self.nx, self.nz = struct.unpack('>ffII', d[:16])
        n = self.nx * self.nz
        self.y = np.frombuffer(d[16:16 + 4 * n], '>f4').reshape(self.nx, self.nz).astype(np.float32)
        self.lie = np.frombuffer(d[16 + 4 * n:16 + 5 * n], np.uint8).reshape(self.nx, self.nz)

    def at(self, x, z):
        """Heights (OOB y, up) and lies of the cells under OOB (x, z) arrays; lie 0 off the map."""
        r = np.floor((np.asarray(x) - self.x0) / CELL).astype(np.int64)
        c = np.floor((np.asarray(z) - self.z0) / CELL).astype(np.int64)
        ok = (r >= 0) & (c >= 0) & (r < self.nx) & (c < self.nz)
        rr, cc = np.where(ok, r, 0), np.where(ok, c, 0)
        return np.where(ok, self.y[rr, cc], np.nan), np.where(ok, self.lie[rr, cc], 0)


# ---- the spot: OOB (x, y up, z) <-> HST game space (X, Y down, Z) ----------------------------------------------
class Spot:
    """Centre (x, z) in the hole's space, the court's length direction (yaw from +z toward +x). HST's game space
    is OOB's turned 180° about Z (the standard's `game_space` turn undone), then turned so the length lies on Z."""

    def __init__(self, hole, x, z, yaw, rng):
        self.hole, self.x, self.z, self.yaw, self.range = hole, x, z, yaw, rng

    def venue(self, top):
        """OOB -> HST (column vectors): X = -cos·dx + sin·dz, Z = sin·dx + cos·dz, Y = -y - top (`top`: HST y, down,
        of the OOB ground that lands on the court's plane)."""
        s, c = math.sin(math.radians(self.yaw)), math.cos(math.radians(self.yaw))
        return np.array([[-c, 0, s, c * self.x - s * self.z], [0, -1, 0, -top], [s, 0, c, -(s * self.x + c * self.z)],
                         [0, 0, 0, 1]], np.float64)

    def to_hole(self, X, Z):
        s, c = math.sin(math.radians(self.yaw)), math.cos(math.radians(self.yaw))
        return self.x - c * X + s * Z, self.z + s * X + c * Z

    def to_hst(self, x, z):
        s, c = math.sin(math.radians(self.yaw)), math.cos(math.radians(self.yaw))
        dx, dz = x - self.x, z - self.z
        return -c * dx + s * dz, s * dx + c * dz


def spots(survey):
    out = {}
    for r in survey:
        for b in r['best']:
            if b['fits']:
                out.setdefault(r['course'], []).append(Spot(r['hole'], b['x'], b['z'], b['yaw'], b['range']))
    for v in out.values():
        v.sort(key=lambda s: (s.range, s.hole))
    return out


# ---- files -----------------------------------------------------------------------------------------------------
LOOSE = None  # the disc's loose `PS3_GAME/USRDIR/data` (hole ground textures), see --data


def index(dirs):
    """Lower-case file name -> path over the archives (first wins)."""
    out = {}
    for d in dirs:
        for p in sorted(Path(d).rglob('*')) if Path(d).is_dir() else []:
            if p.is_file():
                out.setdefault(p.name.lower(), p)
    return out


def entries(text):
    """entry.txt -> {kind dir: [model stems, the plant records' index order]} (levels of detail left out)."""
    out = {}
    for line in text.replace('\r', '').splitlines():
        parts = line.strip().split('\\')
        if len(parts) < 2 or not parts[-1].lower().endswith('.rem'):
            continue
        stem = parts[-1][:-4]
        if re.search(r'_lv\d$', stem):
            continue
        out.setdefault(parts[-2].lower(), []).append(stem)
    return out


def plants(data):
    """[(category, index, pos (x, y, z), yaw, scale)] of an Out of Bounds plant file (0x40-byte big-endian records:
    u16 category, u16 index at 4, f32 pos at 8, four words 0x14–0x20 not used here, f32 yaw at 0x24, scale 0x28)."""
    out = []
    for o in range(0, len(data) - 0x3F, 0x40):
        cat = struct.unpack('>H', data[o:o + 2])[0]
        idx = struct.unpack('>H', data[o + 4:o + 6])[0]
        x, y, z = struct.unpack('>3f', data[o + 8:o + 20])
        yaw, scale = struct.unpack('>2f', data[o + 0x24:o + 0x2C])
        out.append((cat, idx, (x, y, z), yaw, scale))
    return out


# ---- glTF ------------------------------------------------------------------------------------------------------
class Doc:
    def __init__(self, generator):
        self.g = {'asset': {'version': '2.0', 'generator': generator}, 'extensionsUsed': ['KHR_materials_unlit'],
                  'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'name': 'game_space', 'rotation': [0.0, 0.0, 1.0, 0.0]}],
                  'meshes': [], 'materials': [], 'images': [], 'samplers': [], 'textures': [], 'accessors': [],
                  'bufferViews': []}
        self.bin = bytearray()
        self.tex = {}

    def view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        v = {'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data)}
        if target:
            v['target'] = target
        self.bin += data
        self.g['bufferViews'].append(v)
        return len(self.g['bufferViews']) - 1

    def acc(self, arr, kind, ct, target=None, minmax=False):
        arr = np.ascontiguousarray(arr)
        a = {'bufferView': self.view(arr.tobytes(), target), 'componentType': ct, 'count': len(arr), 'type': kind}
        if minmax:
            a['min'] = [float(x) for x in arr.min(0)]
            a['max'] = [float(x) for x in arr.max(0)]
        self.g['accessors'].append(a)
        return len(self.g['accessors']) - 1

    def node(self, parent, node):
        self.g['nodes'].append(node)
        i = len(self.g['nodes']) - 1
        self.g['nodes'][parent].setdefault('children', []).append(i)
        return i

    def mesh(self, name, prims):
        """prims: [(material, pos (n,3), normal, uv (n,2), colour (n,4) 0..1, tris (m,3))]."""
        out = []
        for mat, pos, nrm, uv, col, tris in prims:
            if not len(tris):
                continue
            attrs = {'POSITION': self.acc(pos.astype(np.float32), 'VEC3', 5126, 34962, True),
                     'NORMAL': self.acc(nrm.astype(np.float32), 'VEC3', 5126, 34962),
                     'TEXCOORD_0': self.acc(uv.astype(np.float32), 'VEC2', 5126, 34962),
                     'COLOR_0': self.acc(col.astype(np.float32), 'VEC4', 5126, 34962)}
            out.append({'attributes': attrs, 'indices': self.acc(tris.reshape(-1).astype(np.uint32), 'SCALAR', 5125, 34963),
                        'material': mat, 'mode': 4})
        if not out:
            return None
        self.g['meshes'].append({'name': name, 'primitives': out})
        return len(self.g['meshes']) - 1

    def plain(self, name, color, blend):
        m = {'name': name, 'pbrMetallicRoughness': {'baseColorFactor': color, 'metallicFactor': 0.0, 'roughnessFactor': 1.0},
             'doubleSided': True, 'extensions': {'KHR_materials_unlit': {}}}
        if blend:
            m['alphaMode'] = 'BLEND'
        self.g['materials'].append(m)
        return len(self.g['materials']) - 1

    def texture(self, path):
        """A DDS as an embedded PNG texture -> (texture index, has cut-out alpha)."""
        if path not in self.tex:
            im = dds.load(path.read_bytes())
            if im.mode == 'L':  # an alpha-only mask: white with that alpha
                a = im
                im = a.convert('RGBA')
                im.putalpha(a)
            im = im.convert('RGBA')
            alpha = int(np.asarray(im)[:, :, 3].min()) < 128
            f = io.BytesIO()
            im.save(f, 'PNG')
            self.g['images'].append({'bufferView': self.view(f.getvalue()), 'mimeType': 'image/png', 'name': path.stem.lower()})
            if not self.g['samplers']:
                self.g['samplers'].append({'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497})
            self.g['textures'].append({'source': len(self.g['images']) - 1, 'sampler': 0})
            self.tex[path] = (len(self.g['textures']) - 1, alpha)
        return self.tex[path]

    def model(self, name, r, ix):
        """A static .rem's meshes, a primitive per mesh, its colour map (the first slot that isn't a specular or
        normal map) as the base colour; vertex colours /255 (1.0 = the texture as stored)."""
        mats = {}
        prims = []
        for m in static.meshes(r):
            mi = m['material']
            if mi not in mats:
                mat = r.materials[mi]
                tex = None
                for s in mat['slots']:
                    if not 0 <= s < len(r.texobjs):
                        continue
                    t = r.textures[r.texobjs[s][1]]
                    stem = os.path.splitext(t)[0].lower()
                    if stem.endswith(('_sp', '_s', '-nomal', '-normal', '_n', '_nomal', '_normal')):
                        continue
                    p = ix.get(stem + '.dds')
                    if p is not None:
                        tex = p
                        break
                g = {'name': f'{name}_{mat["name"]}', 'pbrMetallicRoughness': {'metallicFactor': 0.0, 'roughnessFactor': 1.0},
                     'doubleSided': True, 'extensions': {'KHR_materials_unlit': {}}}
                if tex is None:
                    c = [min(max(x, 0.0), 1.0) for x in mat['colors'][0]]
                    g['pbrMetallicRoughness']['baseColorFactor'] = c[:3] + [1.0] if sum(c[:3]) > 0 else [0.5, 0.5, 0.5, 1.0]
                else:
                    t, alpha = self.texture(tex)
                    g['pbrMetallicRoughness']['baseColorTexture'] = {'index': t}
                    if alpha:
                        g['alphaMode'] = 'MASK'
                        g['alphaCutoff'] = 0.5
                self.g['materials'].append(g)
                mats[mi] = len(self.g['materials']) - 1
            uv = m['uvs'][0][:, :2] if m['uvs'] else np.zeros((len(m['pos']), 2), np.float32)
            nrm = m['normal'] / np.maximum(np.linalg.norm(m['normal'], axis=1, keepdims=True), 1e-8)
            prims.append((mats[mi], m['pos'], nrm, uv, m['color'].astype(np.float32) / 255.0, m['tris']))
        return self.mesh(name, prims)

    def write(self, path):
        g = self.g
        for k in ['images', 'samplers', 'textures', 'meshes', 'materials']:
            if not g[k]:
                del g[k]
        while len(self.bin) % 4:
            self.bin.append(0)
        g['buffers'] = [{'byteLength': len(self.bin)}]
        js = json.dumps(g, separators=(',', ':')).encode()
        js += b' ' * (-len(js) % 4)
        out = struct.pack('<III', 0x46546C67, 2, 28 + len(js) + len(self.bin))
        out += struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(self.bin), 0x004E4942) + bytes(self.bin)
        Path(path).write_bytes(out)


def gl(m):
    """glTF's column-major array of a column-vector matrix."""
    return [float(v) for v in np.asarray(m, np.float64).T.reshape(-1)]


def rot_y(a):
    s, c = math.sin(a), math.cos(a)
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]], np.float64)


# ---- the laid court (fore2gltf court.rs `laid`) ----------------------------------------------------------------
class Prim:
    def __init__(self):
        self.pos, self.col, self.tris = [], [], []

    def quad(self, p, col):
        b = len(self.pos)
        self.pos += p
        self.col += [col] * 4
        self.tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]

    def flat(self, x0, x1, z0, z1, y, col):
        self.quad([[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]], col)

    def cuboid(self, a, b, col):
        (x0, y0, z0), (x1, y1, z1) = a, b
        self.flat(x0, x1, z0, z1, y1, col)
        self.flat(x0, x1, z0, z1, y0, col)
        self.quad([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0]], col)
        self.quad([[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], col)
        self.quad([[x0, y0, z0], [x0, y0, z1], [x0, y1, z1], [x0, y1, z0]], col)
        self.quad([[x1, y0, z0], [x1, y0, z1], [x1, y1, z1], [x1, y1, z0]], col)

    def arrays(self, mat):
        n = len(self.pos)
        return (mat, np.array(self.pos, np.float32).reshape(-1, 3), np.tile([[0.0, -1.0, 0.0]], (n, 1)),
                np.zeros((n, 2)), np.array(self.col, np.float32).reshape(-1, 4), np.array(self.tris, np.uint32).reshape(-1, 3))


def laid(d, ro, depth, chair, surface):
    """The laid court in HST's game space: the slab over the run-off (mown stripes on grass; a green surround and a
    blue court on hard), white lines on HST's judging edges, the net, posts and the umpire's chair."""
    plain = d.plain('court_plain', [1.0] * 4, False)
    net = d.plain('court_net', [1.0, 1.0, 1.0, 0.55], True)
    x0, x1, z0, z1 = -(DOUBLES + ro[3]), DOUBLES + ro[2], -(BASE + ro[1]), BASE + ro[0]
    g = Prim()
    if surface == 'grass':
        light, dark, side = [0.36, 0.56, 0.24, 1.0], [0.31, 0.50, 0.21, 1.0], [0.27, 0.40, 0.18, 1.0]
        w = 2.0 * BASE / 12.0
        z = z0
        while z < z1:
            k = math.floor((z - z0 + 1e-3) / w)
            zn = min(z0 + (k + 1) * w, z1)
            band = math.floor((z + 1e-3 + BASE) / w)
            g.flat(x0, x1, z, zn, 0.0, light if band % 2 == 0 else dark)
            z = zn
    else:
        surround, court, side = [0.22, 0.42, 0.30, 1.0], [0.17, 0.30, 0.50, 1.0], [0.30, 0.30, 0.30, 1.0]
        # the surround in four pieces round the court (no overlap to fight over)
        g.flat(x0, x1, z0, -BASE, 0.0, surround)
        g.flat(x0, x1, BASE, z1, 0.0, surround)
        g.flat(x0, -DOUBLES, -BASE, BASE, 0.0, surround)
        g.flat(DOUBLES, x1, -BASE, BASE, 0.0, surround)
        g.flat(-DOUBLES, DOUBLES, -BASE, BASE, 0.0, court)
    for a, b in [([x0, 0, z0], [x1, 0, z0]), ([x1, 0, z0], [x1, 0, z1]), ([x1, 0, z1], [x0, 0, z1]), ([x0, 0, z1], [x0, 0, z0])]:
        g.quad([a, b, [b[0], depth, b[2]], [a[0], depth, a[2]]], side)
    ln = Prim()
    c = [0.95, 0.95, 0.93, 1.0]
    y = -0.003
    for s in (-1.0, 1.0):
        ln.flat(s * DOUBLES - 0.05, s * DOUBLES + 0.05, -BASE, BASE, y, c)
        ln.flat(s * SINGLES - 0.05, s * SINGLES + 0.05, -BASE, BASE, y, c)
        ln.flat(-DOUBLES, DOUBLES, s * BASE - 0.05, s * BASE + 0.05, y, c)
        ln.flat(-SINGLES, SINGLES, s * SERVICE - 0.025, s * SERVICE + 0.025, y, c)
        ln.flat(-0.05, 0.05, s * BASE - s * 0.25, s * BASE - s * 0.05, y, c)
    ln.flat(-0.025, 0.025, -SERVICE, SERVICE, y, c)
    n = Prim()

    def height(x):
        return NET_MID + (NET_POST - NET_MID) * (abs(x) / POST)

    steps = 16
    for i in range(steps):
        a, b = -POST + 2 * POST * i / steps, -POST + 2 * POST * (i + 1) / steps
        n.quad([[a, -0.02, 0], [b, -0.02, 0], [b, -height(b) + 0.05, 0], [a, -height(a) + 0.05, 0]], [0.05, 0.05, 0.05, 1.0])
        ln.quad([[a, -height(a) + 0.05, -0.012], [b, -height(b) + 0.05, -0.012], [b, -height(b), -0.012], [a, -height(a), -0.012]], c)
        ln.quad([[a, -height(a) + 0.05, 0.012], [b, -height(b) + 0.05, 0.012], [b, -height(b), 0.012], [a, -height(a), 0.012]], c)
        ln.quad([[a, -height(a), -0.012], [b, -height(b), -0.012], [b, -height(b), 0.012], [a, -height(a), 0.012]], c)
    ln.cuboid([-0.025, 0, -0.01], [0.025, -NET_MID, 0.01], c)
    p = Prim()
    post = [0.14, 0.26, 0.16, 1.0]
    for s in (-1.0, 1.0):
        p.cuboid([s * POST - 0.04, 0, -0.04], [s * POST + 0.04, -NET_POST - 0.03, 0.04], post)
    cx, cy, cz = chair
    out = math.copysign(1.0, cx)
    seat = cy
    wood, frame = [0.42, 0.30, 0.18, 1.0], [0.20, 0.30, 0.22, 1.0]
    for dx, dz in [(-0.3, -0.3), (0.3, -0.3), (-0.3, 0.3), (0.3, 0.3)]:
        p.cuboid([cx + dx - 0.03, 0, cz + dz - 0.03], [cx + dx + 0.03, seat, cz + dz + 0.03], frame)
    p.cuboid([cx - 0.35, seat, cz - 0.35], [cx + 0.35, seat - 0.05, cz + 0.35], wood)
    p.cuboid([cx + out * 0.33 - 0.03, seat - 0.05, cz - 0.35], [cx + out * 0.33 + 0.03, seat - 0.65, cz + 0.35], wood)
    for s in (-1.0, 1.0):
        p.cuboid([cx - 0.35, seat - 0.05, cz + s * 0.35 - 0.025], [cx + 0.35, seat - 0.3, cz + s * 0.35 + 0.025], frame)
    foot = seat * 0.55
    p.cuboid([cx - out * 0.55, foot, cz - 0.3], [cx - out * 0.3, foot - 0.04, cz + 0.3], wood)
    for k in range(1, 5):
        yy = seat * k / 5
        p.cuboid([cx - out * 0.33 - 0.02, yy, cz - 0.3], [cx - out * 0.33 + 0.02, yy - 0.03, cz + 0.3], frame)
    court = d.node(0, {'name': 'court'})
    for name, prim, mat in [('slab', g, plain), ('lines', ln, plain), ('net', n, net), ('posts_chair', p, plain)]:
        m = d.mesh(name, [prim.arrays(mat)])
        if m is not None:
            d.node(court, {'name': name, 'mesh': m})


# ---- the run-off ------------------------------------------------------------------------------------------------
def rect_points(ro, margin=0.0, step=0.5):
    x0, x1 = -(DOUBLES + ro[3]) - margin, DOUBLES + ro[2] + margin
    z0, z1 = -(BASE + ro[1]) - margin, BASE + ro[0] + margin
    nx, nz = math.ceil((x1 - x0) / step), math.ceil((z1 - z0) / step)
    X, Z = np.meshgrid(x0 + (x1 - x0) * np.arange(nx + 1) / nx, z0 + (z1 - z0) * np.arange(nz + 1) / nz, indexing='ij')
    return X.reshape(-1), Z.reshape(-1), (x0, x1, z0, z1)


def runoff(hmp, spot, circles, points):
    """fore2gltf's run-off growth: the slab grows 0.5 m a side from the survey's footprint (or SEED) up to 15 m
    behind and 10 m beside while it stays on the height map, off water, clear of the blockers (`circles` (x, z, r)
    round placed objects' origins in the hole's space, `points` (X, Z) in HST's that stand on it) and within FLAT."""
    def ok(ro):
        X, Z, (x0, x1, z0, z1) = rect_points(ro)
        hx, hz = spot.to_hole(X, Z)
        y, lie = hmp.at(hx, hz)
        if (lie == 0).any() or (lie == 27).any():
            return None
        for bx, bz, r in circles:
            if (((hx - bx) ** 2 + (hz - bz) ** 2) <= r * r).any():
                return None
        if len(points) and ((points[:, 0] >= x0) & (points[:, 0] <= x1) & (points[:, 1] >= z0) & (points[:, 1] <= z1)).any():
            return None
        rng = float(np.nanmax(y) - np.nanmin(y))
        return rng if rng <= FLAT else None

    ro = [20.0 - BASE, 20.0 - BASE, 10.0 - DOUBLES, 10.0 - DOUBLES]
    fits = ok(ro) is not None
    if not fits and ok(SEED) is not None:
        ro = list(SEED)
    if ok(ro) is not None:
        grew = True
        while grew:
            grew = False
            for k in range(4):
                cap = 15.0 if k < 2 else 10.0
                t = list(ro)
                t[k] = min(t[k] + 0.5, cap)
                if t[k] > ro[k] and ok(t) is not None:
                    ro, grew = t, True
    rng = ok(ro)
    return ro, (float('nan') if rng is None else rng), fits


def tri_heights(tris, X, Z):
    """For each point, the y of the triangles (k, 3, 3) over it (HST space): list of (point index, y, tri index)."""
    out = []
    for k, t in enumerate(tris):
        lo, hi = t.min(0), t.max(0)
        sel = np.nonzero((X >= lo[0]) & (X <= hi[0]) & (Z >= lo[2]) & (Z <= hi[2]))[0]
        if not len(sel):
            continue
        d = (t[1, 2] - t[2, 2]) * (t[0, 0] - t[2, 0]) + (t[2, 0] - t[1, 0]) * (t[0, 2] - t[2, 2])
        if abs(d) < 1e-9:
            continue
        x, z = X[sel], Z[sel]
        l1 = ((t[1, 2] - t[2, 2]) * (x - t[2, 0]) + (t[2, 0] - t[1, 0]) * (z - t[2, 2])) / d
        l2 = ((t[2, 2] - t[0, 2]) * (x - t[2, 0]) + (t[0, 0] - t[2, 0]) * (z - t[2, 2])) / d
        l3 = 1 - l1 - l2
        inside = (l1 >= -1e-4) & (l2 >= -1e-4) & (l3 >= -1e-4)
        for i, y in zip(sel[inside], (l1 * t[0, 1] + l2 * t[1, 1] + l3 * t[2, 1])[inside]):
            out.append((int(i), float(y), k))
    return out


def chairs(iso):
    return json.loads(subprocess.run([str(FORE2GLTF), 'chairs', str(iso)], check=True, capture_output=True, text=True).stdout)


# ---- one course -------------------------------------------------------------------------------------------------
def one(root, c, spot, chair_of, out):
    h = spot.hole
    stem, name = COURSES[c]
    cd = root / f'course{c:02d}'
    nine = 'p01' if h >= 10 else 'p10'
    half = cd / f'half_{nine}.xb'
    archives = [cd / f'hole{h:02d}.xb', cd / f'ground{h:02d}.xb', half, cd / 'plantmodel00.xb', cd / 'plantmodel01.xb',
                cd / 'plantetc.xb', cd / 'etc.xb'] + sorted(cd.glob('*.xb0')) + sorted(cd.glob('hole??.xb')) + \
        [cd / 'half_p10.xb', cd / 'half_p01.xb'] + ([LOOSE / f'course/course{c:02d}', LOOSE / 'course/common'] if LOOSE else [])
    ix = index(archives)
    ents = entries((half / f'data/course/course{c:02d}/entry.txt').read_text('latin1'))
    hmp_path = next((p for p in (cd / f'hole{h:02d}.xb').rglob('*.HMP') if not p.stem.endswith('_g')), None)
    if hmp_path is None:
        raise ValueError('no height map')
    hmp = Hmp(hmp_path.read_bytes())
    ground_path = next((p for p in (cd / f'ground{h:02d}.xb').rglob('*.rem') if p.parent.name == 'hole'), None)
    if ground_path is None:
        raise ValueError('no hole ground model')
    ground = Rem(ground_path.read_bytes())
    gmeshes = static.meshes(ground)

    # placements: each hole's plant files (and the nine's `out` ones) cover only what that hole shows, so the spot
    # takes all of its nine's (the front and back nines are separate worlds over the same coordinates), once each,
    # where this hole's ground model is drawn (10 m cells)
    gall = np.concatenate([m['pos'] for m in gmeshes])
    occupied = set(map(tuple, np.floor(gall[:, [0, 2]] / 10.0).astype(np.int64).tolist()))
    recs, seen = [], set()
    for cat, (kind, _) in KINDS.items():
        for p in sorted(half.glob(f'data/course/plant/course{c:02d}/{kind}/{kind}_c{c:02d}_*_0.dat')):
            for r in plants(p.read_bytes()):
                key = (r[0], r[1], round(r[2][0], 2), round(r[2][1], 2), round(r[2][2], 2))
                cell = (math.floor(r[2][0] / 10.0), math.floor(r[2][2] / 10.0))
                if r[0] != cat or key in seen or not any((cell[0] + i, cell[1] + k) in occupied for i in (-1, 0, 1) for k in (-1, 0, 1)):
                    continue
                seen.add(key)
                recs.append(r)
    if not recs:
        raise ValueError('no placements over the hole')
    models, missing = {}, []

    def rem_of(st):
        if st not in models:
            p = ix.get(st.lower() + '.rem')
            try:
                models[st] = Rem(p.read_bytes()) if p else None
            except Exception as e:  # noqa: BLE001
                missing.append(f'{st}: {e}')
                models[st] = None
            if p is None:
                missing.append(f'{st}.rem not found')
        return models[st]

    def model_of(rec):
        cat, idx = rec[0], rec[1]
        lst = ents.get(KINDS[cat][0], [])
        return lst[idx] if idx < len(lst) else None

    def local(rec):
        _, _, pos, yaw, scale = rec
        s = scale if scale > 0 else 1.0
        m = rot_y(yaw) @ np.diag([s, s, s, 1.0])
        m[:3, 3] = pos
        return m

    # blockers: circles round every placement's origin, and the vertices of props, structures and billboards
    circles = [(r[2][0], r[2][2], KINDS[r[0]][1] * min(max(abs(r[4]), 1.0), 4.0)) for r in recs]
    near = [r for r in recs if (r[2][0] - spot.x) ** 2 + (r[2][2] - spot.z) ** 2 < 80.0 ** 2]
    pts = []
    for r in near:
        if r[0] == 0x14:
            continue
        st = model_of(r)
        rm = rem_of(st) if st else None
        if rm is None:
            continue
        P = np.concatenate([m['pos'] for m in static.meshes(rm)] or [np.zeros((0, 3))])
        if not len(P):
            continue
        W = (local(r) @ np.c_[P, np.ones(len(P))].T).T
        # what stands on the ground (not flat decals lying on it)
        yg, _ = hmp.at(W[:, 0], W[:, 2])
        W = W[~(W[:, 1] <= np.nan_to_num(yg, nan=-1e9) + 0.05)]
        X, Z = spot.to_hst(W[:, 0], W[:, 2])
        pts.append(np.c_[X, Z])
    # the ground model's own pieces standing above the height map near the spot
    sel = (gall[:, 0] - spot.x) ** 2 + (gall[:, 2] - spot.z) ** 2 < 60.0 ** 2
    gp = gall[sel]
    yg, lie = hmp.at(gp[:, 0], gp[:, 2])
    standing = gp[(lie != 0) & (gp[:, 1] > yg + STANDING)]
    if len(standing):
        X, Z = spot.to_hst(standing[:, 0], standing[:, 2])
        pts.append(np.c_[X, Z])
    points = np.concatenate(pts) if pts else np.zeros((0, 2))
    ro, rng, fits = runoff(hmp, spot, circles, points)
    if math.isnan(rng):
        raise ValueError('no run-off passes (blocked or not flat)')

    # the ground under the slab and 2 m round it (fore2gltf's rule, in HST space: y down)
    v0 = spot.venue(0.0)
    X, Z, (x0, x1, z0, z1) = rect_points(ro, 2.0)
    hx, hz = spot.to_hole(X, Z)
    yh, lie = hmp.at(hx, hz)
    yd = -yh  # HST y (down) of the height map
    top, low = float(np.nanmin(np.where(lie != 0, yd, np.nan))), float(np.nanmax(np.where(lie != 0, yd, np.nan)))
    tris, tmat = [], []
    for m in gmeshes:
        P = (v0 @ np.c_[m['pos'], np.ones(len(m['pos']))].T).T[:, :3]
        T = P[m['tris']]
        lo, hi = T.min(1), T.max(1)
        keep = (hi[:, 0] >= x0) & (lo[:, 0] <= x1) & (hi[:, 2] >= z0) & (lo[:, 2] <= z1)
        tris.append(T[keep])
        tmat += [ground.materials[m['material']]['name']] * int(keep.sum())
    tris = np.concatenate(tris) if tris else np.zeros((0, 3, 3))
    nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    level = np.abs(nrm[:, 1]) > 0.7
    mesh_top, mesh_low = math.inf, -math.inf
    covered, under = set(), Counter()
    slab = (X >= x0 + 2) & (X <= x1 - 2) & (Z >= z0 + 2) & (Z <= z1 - 2)
    lt = tris[level]
    ltm = [m for m, k in zip(tmat, level) if k]
    for i, y, k in tri_heights(lt, X, Z):
        covered.add(i)
        if not np.isnan(yd[i]) and lie[i] != 0 and abs(y - yd[i]) <= GROUND:
            mesh_top, mesh_low = min(mesh_top, y), max(mesh_low, y)
            if slab[i]:
                under[ltm[k]] += 1
    n_slab = int(slab.sum())
    n_cov = sum(1 for i in covered if slab[i])
    if n_cov < 0.95 * n_slab:
        raise ValueError(f"off the hole model's ground ({n_cov} of {n_slab} points under the slab drawn)")
    hmp_top = top
    top, low = min(top, mesh_top), max(low, mesh_low)
    depth = low - top + SINK + 0.1
    venue = spot.venue(top - SINK)

    # surface: paved ground under the slab -> hard, else grass
    paved = sum(v for k, v in under.items() if any(w in k.lower() for w in PAVED))
    surface = 'hard' if paved > 0.5 * sum(under.values()) else 'grass'
    back, side = min(ro[0], ro[1]), min(ro[2], ro[3])
    lay = min((k for k in range(len(HST)) if HST[k][0] == surface),
              key=lambda k: abs(math.log(back / min(HST[k][1][0], HST[k][1][1]))) + abs(math.log(side / min(HST[k][1][2], HST[k][1][3]))))
    chair = chair_of[lay]
    if chair is None:
        raise ValueError("the layout court's umpire chair isn't on the disc")

    # court.glb
    d = Doc('oob2gltf court')
    vn = d.node(0, {'name': 'oob_spot', 'matrix': gl(venue)})
    gm = d.model(f'hole_{ground_path.stem.lower()}', ground, ix)
    if gm is not None:
        d.node(vn, {'name': f'hole_{ground_path.stem.lower()}', 'mesh': gm})
    meshes, placed, cleared = {}, Counter(), 0
    for k, r in enumerate(recs):
        st = model_of(r)
        if st is None:
            missing.append(f'{KINDS[r[0]][0]} index {r[1]}')
            continue
        at = venue @ np.array([*r[2], 1.0])
        dist = math.hypot(at[0], at[2])
        use = st
        if r[0] == 0x14 and dist > TREE_LOD:
            lods = sorted(n[:-4] for n in ix if re.fullmatch(re.escape(st.lower()) + r'_lv\d\.rem', n))
            if lods:
                use = lods[-1]
        if use not in meshes:
            rm = rem_of(use) if use != st else rem_of(st)
            if use != st and rm is None:
                rm = Rem(ix[use + '.rem'].read_bytes())
            meshes[use] = d.model(use, rm, ix) if rm is not None else None
        if meshes[use] is None:
            continue
        clear = dist < CLEAR_WITHIN
        cleared += clear
        d.node(vn, {'name': f'{use}_{k}{"__clear" if clear else ""}', 'mesh': meshes[use], 'matrix': gl(local(r))})
        placed[st] += 1
    laid(d, ro, depth, chair, surface)
    slug = f'oob_c{c:02d}_{stem}'
    out_dir = out / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    d.write(out_dir / 'court.glb')

    # sky.glb: the course's sky, clouds and panorama at the eye, turned with the venue
    s = Doc('oob2gltf court')
    turn = np.eye(4)
    turn[:3, :3] = venue[:3, :3]
    backdrops = []
    for st in ents.get('bg', []):
        low_st = st.lower()
        if not ('_sky' in low_st or '-sky' in low_st or low_st.endswith(nine) or not re.search(r'_p\d\d$', low_st)):
            continue
        p = ix.get(low_st + '.rem')
        if p is None:
            continue
        m = s.model(st, Rem(p.read_bytes()), ix)
        if m is not None:
            s.node(0, {'name': st, 'mesh': m, 'matrix': gl(turn)})
            backdrops.append(st)
    s.write(out_dir / 'sky.glb')

    r = HST[lay][1]
    todo = [
        "the court is laid by the exporter (slab, lines at HST's judging edges, net, posts, umpire chair): Out of Bounds has no tennis court",
        "light: none in the manifest; the hole is lit as the layout court lights its own models (Out of Bounds' lighting isn't mapped)",
        "sky: dome, clouds and panorama at the eye with no lift (the game's own placement isn't decoded); clouds don't drift",
        "placements: position, yaw and scale only (the records' four other words, 0x14-0x20, aren't decoded; they look like leans)",
        "materials: the colour map only (no normal, specular or second-UV maps); creatures, galleries, the pin flag and the hole-end scenery are left out",
        "sound: the layout court's (Out of Bounds' course music isn't exported)",
    ]
    if missing:
        todo.append('plant records without a model: ' + ', '.join(sorted(set(missing))))
    if not fits:
        todo.append("the survey's footprint didn't pass this exporter's own check (0.5 m grid, model footprints): run-off grown from 3 m / 2 m instead")
    paved_names = sorted(k for k in under if any(w in k.lower() for w in PAVED))
    why = (f"{surface}: " + ("a court laid on paved ground (" + ', '.join(paved_names) + ")" if surface == 'hard' else "a court laid on the golf course's lawn")
           + f"; of HST's {surface} courts the closest run-off: {back:.1f} m behind the baselines and {side:.1f} m beside the sidelines of flat ground here"
           f" (height map, ≤ {FLAT} m), {min(r[0], r[1])} / {min(r[2], r[3])} m at {HST_NAMES[lay]}")
    man = {'standard': 1, 'kind': 'court', 'id': slug, 'name': f'{name} Courts',
           'source': f'Hot Shots Golf: Out of Bounds (PS3) {name} (course{c:02d}) hole {h:02d}',
           'layout': lay, 'layout_why': why, 'surface': surface, 'time': 'day', 'indoor': False, 'todo': todo}
    (out_dir / 'mod.json').write_text(json.dumps(man, indent=2, ensure_ascii=False) + '\n')
    print(f'  spot ({spot.x}, {spot.z}) yaw {spot.yaw} range {spot.range}; run-off +z {ro[0]} -z {ro[1]} +x {ro[2]} -x {ro[3]} '
          f'(slab range {rng:.2f}); ground top {top:.3f} (height map {hmp_top:.3f}, model {mesh_top:.3f}..{mesh_low:.3f}) depth {depth:.2f}; '
          f'{len(points)} blocker points near; under the slab {dict(under.most_common(4))}; {surface} layout {lay} {HST_NAMES[lay]}; chair {chair}')
    print(f'  placed {sum(placed.values())} ({cleared} __clear), {len(meshes)} models; backdrops {backdrops}')
    return out_dir


def main():
    a = sys.argv[1:]
    if len(a) < 4:
        sys.exit(__doc__)
    root, survey, iso, out = Path(a[0]) / 'PS3_GAME/USRDIR/xbdata/course', Path(a[1]), Path(a[2]), Path(a[3])
    rest = a[4:]
    global LOOSE
    if '--data' in rest:
        LOOSE = Path(rest[rest.index('--data') + 1])
        del rest[rest.index('--data'):rest.index('--data') + 2]
    else:
        LOOSE = next((p for p in [Path(a[0]) / 'PS3_GAME/USRDIR/data'] + sorted(Path('iso').glob('Hot Shots Golf - Out of Bounds*/**/PS3_GAME/USRDIR/data'))
                      if p.is_dir()), None)
    if LOOSE is None:
        print('no loose data folder: hole models untextured (--data DIR)', file=sys.stderr)
    end = '--end' in rest and '-' in rest
    want = [int(x) for x in rest if x.isdigit()]
    cands = spots(json.loads(survey.read_text()))
    chair_of = chairs(iso)
    for c in sorted(COURSES):
        if want and c not in want:
            continue
        done = False
        for sp in cands.get(c, []):
            if end:
                sp = Spot(sp.hole, sp.x, sp.z, sp.yaw + 180.0, sp.range)
            try:
                d = one(root, c, sp, chair_of, out)
                print(f'course {c:02d} h{sp.hole:02d}: {d}')
                done = True
                break
            except ValueError as e:
                print(f'course {c:02d} h{sp.hole:02d} ({sp.x}, {sp.z}) yaw {sp.yaw}: {e}', file=sys.stderr)
        if not done:
            print(f'course {c:02d}: no spot exported', file=sys.stderr)


if __name__ == '__main__':
    main()
