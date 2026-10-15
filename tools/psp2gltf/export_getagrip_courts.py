"""Get a Grip's sixteen courts -> court mods (standard/HST-COURT-UMPIRE-STANDARD.md §2; HST-Remastered task M8f5).

    python3 tools/psp2gltf/export_getagrip_courts.py [01 04 ...]

Reads the unpacked disc under out/files/getagrip/.../xbdata/game (200_court, 900_sound, common) and the decoded
audio under out/audio/getagrip (tools/audio), writes out/mods/gag_cNN_<stem>/: mod.json, court.glb, sky.glb,
gimmick.glb, sound/bgm.wav, sound/ambience_0.wav, lensflare.png. Game data: out/ only.

What each court is made of (notes/getagrip.md "Courts"):
  courtNN.xb         ground/cNN_<stem>.psp.i3r: the whole venue floor, stands, buildings (one node tree, rigid),
                     with the sky dome as its `bg01_sky` node (untextured, vertex colours) -> court.glb / sky.glb
  courtNN_obj_0/1    obj/, tree/, bg/ models, placed by haichi/cNN_<stem>__haichi.i3m: one single-key track per
                     instance, `<model>__<NN|singles|doubles>`, in the models' own space (centimetres, Y up). The
                     net and the umpire's chair come as __singles / __doubles pairs -> kept, named so (§2 there).
                     bg02_cloud (+ its looping motion) -> sky.glb, the rest -> court.glb. `_col` models are the
                     collision, not drawn; `pc_locator` / `player_locator` tracks are where the umpire / benched
                     players stand (informational).
  courtNN_gimmick    gimmick/giNN_<Name>/: the reactive set pieces (pigeons that fly off, baskets that tip over),
                     placed by setting/cNN_escape_gimmick.csv / cNN_break_gimmick.csv at the first point of their
                     route in cNN_route.dat (u32 routes; each u32 n, n x (u32 route id, f32 x, y, z metres)),
                     facing the csv's default angle -> gimmick.glb, each looping its resting motion. The reactions
                     (escape along the route, break into the `_b01` model) live in the encrypted program: not here.
  1_courtsetting     court.csv (stem, GRASS/HARD/CLAY, indoor), courtlight.csv (ambient, light 0 and 1: colour,
                     direction toward the light, Y up), fogsetting.csv (amount near/far, distance near/far, colour)
  900_sound          020_courtNN.xb bgm_court_NN (music), stream_SE/env_coNN (the ambience loop: birds, crowd,
                     wind); loop points from vgmstream-cli -m on the raw .sgh/.sgb pair
  lensflare.xb       one flare sprite (flare3.gim) for every outdoor court

Into HST game space: Get a Grip's courts are true scale in centimetres, net at the origin, long axis Z, Y up, the
umpire's chair on +X; HST's are metres, Y down, chair on +X. So (x, y, z) cm -> (0.01x, -0.01y, -0.01z) m: under
`game_space` (rotation [0,0,1,0], the standard's root) one `gag_cm` node, rotation [1,0,0,0] (that map) and scale 0.01.
Checked on every court: the painted lines' vertex rows land on HST's 5.485 / 4.115 / 11.885 / 6.40 m to the mm (`lines`).
"""
import csv
import io
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from glob import glob

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import anim  # noqa: E402
import build  # noqa: E402
import gim  # noqa: E402
import glb  # noqa: E402
import i3d  # noqa: E402
import i3m  # noqa: E402

GAME = os.path.join(ROOT, "out/files/getagrip/PSP_GAME/USRDIR/xbdata/game")
COURT = os.path.join(GAME, "200_court")
SETTING = os.path.join(COURT, "1_courtsetting.xb/data/court")
AUDIO = os.path.join(ROOT, "out/audio/getagrip/PSP_GAME/USRDIR/xbdata/game/900_sound")
RAW_SOUND = os.path.join(ROOT, "extracted/getagrip/PSP_GAME/USRDIR/data/sound")
NAMES = os.path.join(ROOT, "out/files/getagrip/PSP_GAME/USRDIR/xbdata/common/common_22.xb0/data/menu/text/CommonText_Court.to")
COURTS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 14, 15, 16, 17, 18, 20]  # in the game's court list order

# HST's eleven courts (the layout numbers): surface (`SURFACE`, HST-Remastered play/main_menu.rs) and flat run-off in
# metres beyond the baselines (+z, -z) and sidelines (+x, -x), measured on each disc court's ground model the same
# way `runoff` measures Get a Grip's (HST-Remastered mdlstat obj dump, 2026-10-15; capped at 40 m)
HST = [("clay", (8.5, 8.5, 35.0, 4.9)), ("clay", (40, 40, 40, 40)), ("clay", (40, 13.1, 40, 37.7)),
       ("hard", (10.7, 10.7, 25.8, 8.4)), ("grass", (21.3, 21.3, 9.6, 9.4)), ("grass", (18.6, 29.2, 27.8, 10.8)),
       ("hard", (14.9, 14.4, 7.6, 7.6)), ("grass", (40, 13.6, 7.0, 14.5)), ("clay", (17.3, 15.5, 40, 40)),
       ("grass", (9.0, 9.0, 4.6, 3.2)), ("hard", (8.2, 8.2, 4.6, 4.6))]
HST_NAMES = ["Alps", "Resort", "Western", "Park", "Wim", "Kar", "Extra", "Jungle", "Kasen", "Greece", "Wafu"]

# the csvs' Japanese gimmick names -> gimmick folder (giNN_<Name>); a trailing number is the instance's
GIMMICK = {"ハト": "HATO", "はと": "HATO", "ボールカゴ": "Basket", "しん": "shin", "すずめ": "Suzume", "にわとり": "NIWATORI",
           "犬": "HouseDog", "カニ": "crab", "サメ": "Shark", "ブルーマーリン": "Bluemarlin", "サーフボード": "surfboard",
           "ねこ": "cat", "ねずみ": "Mouse", "釣り人": "Fisherman", "雪だるま": "snowman", "サーモン": "Salmon",
           "列車": "Train", "熊": "grizzly", "ピエロ": "Clown", "スプリンクラー": "Sprinkler", "ブルドッグ": "Doberman",
           "ラジコンボーイ": "radioboy", "散歩中の人": "Walkman", "スポーツ用具": "Tools", "チア": "cheer",
           "カール君": "Karl", "バッター": "BaseBallMan", "土手の人": "dote", "つぼ": "Pot", "千両箱": "Moneybox",
           "忍者": "ninja", "花火": "HANABI", "バルーン": "Tools", "窓拭きの人": "spaceman", "カメ": "Pot", "ドラ": "Dora",
           "爆竹": "Bakutiku", "トラ": "Tigers", "マスターモンク": "mastermonk", "カラス": "Crow", "綱渡り人": "tunaman",
           "工具": "Tools", "": "Tools"}  # カメ = 甕 (an urn: c18's gi10_Pot); c20's nameless row is its 工具 (id 112)
# the resting motion a placed gimmick loops, first found; break-only pieces stand still
REST = ("Stay", "stay", "Stay2", "wait", "pool", "Swim", "Fly", "WingBeat", "kyorokyoro", "control", "aruku", "walk",
        "Walk", "Run")
# the two 車 rows (ids 11 and 31) are c05's two cars
CAR = {11: "gi10_Car", 31: "gi11_Car"}

# HST's match camera (HST-Remastered hst_sim::camera::base): 41 m from the court centre at 17 degrees, behind
# either baseline (it turns round when its human is on the far half), 20-degree lens on the PS2's 0.7 aspect ->
# 7 degrees above and below the view's centre; sideways up to a 21:9 window. Get a Grip's PSP camera sits closer,
# so set pieces it leaves behind its back (c17's NORMA, 17 m cables 9-12 m in front of HST's eye) stand in HST's
# view: their islands within EYE_CLEAR of either resting eye are left out of gimmick.glb (`clear_view`).
EYE_PITCH, EYE_DIST, EYE_HALF_V, EYE_WIDE = math.radians(17.0), 41.0, math.radians(7.0 + 1.5), 21 / 9
EYE_CLEAR = 20.0


def sjis_csv(path):
    rows = list(csv.reader(io.StringIO(open(path, "rb").read().decode("shift_jis"))))
    return rows[0], [r for r in rows[1:] if any(c.strip() for c in r)]


def court_dirs(n):
    """Every unpacked folder holding court n's files (its models sit in several xbs, one c13 piece in court03's)."""
    return sorted(glob(os.path.join(COURT, f"court*.xb/data/court/c{n:02d}_*")))


def names():
    s = [x.decode("latin1") for x in open(NAMES, "rb").read().split(b"\0") if len(x) > 2]
    i = s.index("No Preference")
    return dict(zip(COURTS, s[i + 1:i + 1 + len(COURTS)]))


# ---- models -------------------------------------------------------------------------------------------------

class Model:
    """An I3D_BIN file: its node tree, the rigid mesh groups on its nodes and its skinned parts, these already in
    glTF model space (build.skin_space)."""
    cache = {}

    def __new__(cls, path):
        if path not in cls.cache:
            m = super().__new__(cls)
            m.load(path)
            cls.cache[path] = m
        return cls.cache[path]

    def load(self, path):
        self.path = path
        self.m = i3d.load(path)
        sk = self.sk = self.m.skeleton
        d = open(path, "rb").read()
        root = i3d.parse_tree(d)
        groups = build._group_parts(d, root, self.m)
        self.rigid = {}
        for j, gi in build._node_groups(d, root, sk):
            ps = [p for p in groups[gi] if not p.skinned] if gi < len(groups) else []
            if ps:  # c07's ground hangs both its groups on ROOTNODE
                self.rigid.setdefault(j, []).extend(ps)
        self.skinned = [p for p in self.m.parts if p.skinned]
        for p in self.skinned:
            build._xform(p, build.skin_space(p, sk))
        self.baked = set()
        self.children = {}
        for j, p in enumerate(sk.parents):
            self.children.setdefault(p, []).append(j)

    def bake(self, j, loc):
        """Node j's (sheared) local into its rigid group's vertices, once."""
        if j in self.baked:
            return
        self.baked.add(j)
        for p in self.rigid.get(j, []):
            build._xform(p, loc)

    def subtree(self, name):
        out, todo = set(), [self.sk.names.index(name)]
        while todo:
            j = todo.pop()
            out.add(j)
            todo += self.children.get(j, [])
        return out


class Scene:
    """One .glb: game_space -> gag_cm -> instances."""

    def __init__(self, tex_dirs, unlit=False, clear_view=False):
        self.b = glb.Builder()
        self.clear_view, self.cleared = clear_view, []
        self.tc = build.TextureCache(self.b, tex_dirs, None)
        self.unlit = unlit
        self.meshes, self.mats, self.ibm = {}, {}, {}
        gs = self.b.node(name="game_space", rotation=[0.0, 0.0, 1.0, 0.0], children=[])
        self.b.g["scenes"][0]["nodes"].append(gs)
        self.top = self.b.node(name="gag_cm", rotation=[1.0, 0.0, 0.0, 0.0], scale=[0.01] * 3, children=[])
        self.b.g["nodes"][gs]["children"].append(self.top)

    def child(self, parent, **kw):
        n = self.b.node(**kw)
        self.b.g["nodes"][parent].setdefault("children", []).append(n)
        return n

    @staticmethod
    def draws_below(M, j, drawn):
        return any(c in drawn and (c in M.rigid or Scene.draws_below(M, c, drawn)) for c in M.children.get(j, []))

    def material(self, name, vertex_alpha, add=False):
        """build.TextureCache's material; untextured ones (the sky, the bushes' shadow cards) white so their
        vertex colours show; BLEND where the vertex colours carry alpha. `add`: GaG draws it additively (light
        pools, lamp rays, water glints; render-state byte +0x24 bit 0 of its texture record), which the standard
        spells as an `@add` name suffix, BLEND."""
        key = (name, vertex_alpha, add)
        if key not in self.mats:
            if name and self.tc.find(name):
                i = self.tc.material(name)
            else:
                i = self.b.add("materials", {"name": name or "vertex_colour", "doubleSided": True,
                                             "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1],
                                                                      "metallicFactor": 0.0, "roughnessFactor": 1.0}})
            if vertex_alpha or self.unlit or add:
                m = dict(self.b.g["materials"][i])
                if vertex_alpha or add:
                    m["alphaMode"] = "BLEND"
                if add:
                    m["name"] = m.get("name", "") + "@add"
                if self.unlit:
                    m["extensions"] = {"KHR_materials_unlit": {}}
                    self.b.g["extensionsUsed"] = ["KHR_materials_unlit"]
                i = self.b.add("materials", m)
            self.mats[key] = i
        return self.mats[key]

    def world(self, n):
        """glTF node n's rest world matrix (metres, glTF axes: Y up)."""
        parent = {c: i for i, nd in enumerate(self.b.g["nodes"]) for c in nd.get("children", [])}
        M = np.eye(4)
        while True:
            nd = self.b.g["nodes"][n]
            L = np.eye(4)
            if "matrix" in nd:
                L = np.array(nd["matrix"]).reshape(4, 4).T
            else:
                x, y, z, w = nd.get("rotation", (0, 0, 0, 1))
                R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                              [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                              [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
                L[:3, :3] = R * np.array(nd.get("scale", (1, 1, 1)))
                L[:3, 3] = nd.get("translation", (0, 0, 0))
            M = L @ M
            if n not in parent:
                return M
            n = parent[n]

    @staticmethod
    def in_view(Q):
        """Points of Q (glTF world, metres) inside HST's resting match view, within EYE_CLEAR of the eye, from
        either end."""
        lift = math.atan(0.02 * math.tan(math.radians(10.0)) * 0.7)
        hit = np.zeros(len(Q), bool)
        for s in (1, -1):
            o = EYE_PITCH - lift
            eye = np.array([0, EYE_DIST * math.sin(o), -s * EYE_DIST * math.cos(o)])
            fw = np.array([0, -math.sin(EYE_PITCH), s * math.cos(EYE_PITCH)])
            up = np.array([0, math.cos(EYE_PITCH), s * math.sin(EYE_PITCH)])
            D = Q - eye
            d = D @ fw
            tv = math.tan(EYE_HALF_V) * d
            hit |= (d > 0.3) & (d < EYE_CLEAR) & (np.abs(D @ up) < tv) & (np.abs(D @ np.cross(fw, up)) < tv * EYE_WIDE)
        return hit

    def clear(self, A, W, label):
        """Drop from A's triangles the islands (triangles joined by shared or coincident corners) that have a
        corner in HST's view near its eye (`in_view`), W the mesh node's world matrix."""
        Q = (np.c_[A["P"], np.ones(len(A["P"]))] @ W.T)[:, :3]
        _, weld = np.unique(np.round(Q, 2), axis=0, return_inverse=True)
        weld = weld.reshape(-1)
        T = weld[A["I"].reshape(-1, 3)]
        root = np.arange(weld.max() + 1)

        def find(a):
            while root[a] != a:
                root[a] = root[root[a]]
                a = root[a]
            return a
        for a, b, c in T:
            ra = find(a)
            for x in (b, c):
                rx = find(x)
                if rx != ra:
                    root[rx] = ra
        isl = np.array([find(a) for a in T[:, 0]])
        bad = np.unique(isl[self.in_view(Q)[A["I"].reshape(-1, 3)].any(1)])
        drop = np.isin(isl, bad)
        if drop.any():
            self.cleared.append(f"{label}: {int(drop.sum())} of {len(T)} triangles")
            A["I"] = A["I"].reshape(-1, 3)[~drop].reshape(-1)
        return bool(drop.any())

    def prims(self, parts, materials, joint_map, world=None, label=""):
        """world: the mesh node's world matrix, to `clear` the view (rigid meshes of a clear_view scene)."""
        by_mat = {}
        for p in parts:
            by_mat.setdefault(p.material, []).append(p)
        out = []
        for mi, ps in sorted(by_mat.items()):
            arrs = [build._prim_arrays(p, joint_map) for p in ps]
            off = np.cumsum([0] + [len(a["P"]) for a in arrs])
            A = {k: np.concatenate([a[k] for a in arrs]) for k in arrs[0] if k != "I"}
            A["I"] = np.concatenate([a["I"] + o for a, o in zip(arrs, off)])
            name = materials[mi].texture if mi < len(materials) else ""
            if world is not None:
                self.clear(A, world, f"{label} {name}")
            if not len(A["I"]):
                continue
            A["N"][np.linalg.norm(A["N"], axis=1) < 0.5] = (0, 1, 0)  # c17 has zero normals
            b = self.b
            attrs = {"POSITION": b.accessor(A["P"], glb.FLOAT, "VEC3", 34962, minmax=True),
                     "NORMAL": b.accessor(A["N"], glb.FLOAT, "VEC3", 34962),
                     "TEXCOORD_0": b.accessor(A["U"], glb.FLOAT, "VEC2", 34962)}
            if (A["C"] != 255).any():
                attrs["COLOR_0"] = b.accessor(A["C"], glb.UBYTE, "VEC4", 34962, normalized=True)
            if joint_map is not None:
                attrs["JOINTS_0"] = b.accessor(A["J"], glb.USHORT, "VEC4", 34962)
                attrs["WEIGHTS_0"] = b.accessor(A["W"], glb.FLOAT, "VEC4", 34962)
            raw = materials[mi].raw if mi < len(materials) else b""
            add = len(raw) > 0x24 and raw[0x24] & 1 == 1
            out.append({"attributes": attrs, "indices": b.accessor(A["I"], glb.UINT, "SCALAR", 34963),
                        "material": self.material(name, bool((A["C"][:, 3] < 255).any()), add), "mode": 4})
        return out

    def add(self, path, parent, nodes=None, mesh_nodes=None):
        """The model's node tree under `parent` (only `nodes` if given; meshes only on `mesh_nodes`); its rigid
        groups as meshes on their nodes, its skinned parts as one skinned mesh. -> {node name: glTF node}."""
        M = Model(path)
        sk = M.sk
        keep = set(range(len(sk.names))) if nodes is None else nodes
        drawn = keep if mesh_nodes is None else mesh_nodes
        gl = {}
        for j in range(len(sk.names)):
            if j not in keep:
                continue
            loc = build.root_local(sk) if sk.parents[j] < 0 else sk.local[j]
            p = sk.parents[j]
            trs = build._trs(loc)
            if "matrix" in trs:  # sheared (c04's net shadows): baked into the node's own mesh
                assert not self.draws_below(M, j, drawn), sk.names[j]  # (only empty Shape nodes hang there)
                M.bake(j, loc)
                trs = {}
            gl[j] = self.child(gl[p] if p in gl else parent, name=sk.names[j], **trs)
            if j in M.rigid and j in drawn:
                key = (path, j)
                if self.clear_view:  # each placement looks different from the eye
                    key = (path, j, gl[j])
                    label = self.b.g["nodes"][parent]["name"] + "/" + sk.names[j]
                    self.meshes[key] = self.b.add("meshes", {"name": f"{os.path.basename(path)}:{sk.names[j]}",
                                                             "primitives": self.prims(M.rigid[j], M.m.materials, None,
                                                                                      self.world(gl[j]), label)})
                if key not in self.meshes:
                    self.meshes[key] = self.b.add("meshes", {"name": f"{os.path.basename(path)}:{sk.names[j]}",
                                                             "primitives": self.prims(M.rigid[j], M.m.materials, None)})
                self.b.g["nodes"][gl[j]]["mesh"] = self.meshes[key]
        skinned = [p for p in M.skinned if all(sk.names.index(n) in drawn for n in p.skin.names)] if M.skinned else []
        if skinned:
            joints = sorted({sk.names.index(n) for p in skinned for n in p.skin.names})
            if path not in self.meshes:
                k = {j: i for i, j in enumerate(joints)}
                for p in skinned:
                    p.palette = [k[sk.names.index(p.skin.names[q])] for q in p.palette]
                self.meshes[path] = self.b.add("meshes", {"name": os.path.basename(path), "primitives":
                                                          self.prims(skinned, M.m.materials, {i: i for i in range(len(joints))})})
                ibm = np.array([np.linalg.inv(sk.world[j] @ build.F) for j in joints], np.float32)
                self.ibm[path] = self.b.accessor(ibm, glb.FLOAT, "MAT4")
            skin = self.b.add("skins", {"joints": [gl[j] for j in joints], "inverseBindMatrices": self.ibm[path]})
            n = self.b.node(name=os.path.basename(path).split(".")[0] + ":skinned", mesh=self.meshes[path], skin=skin)
            self.b.g["scenes"][0]["nodes"].append(n)
        return {sk.names[j]: n for j, n in gl.items()}

    def animate(self, name, motion, by_name):
        """A looping motion on one instance's nodes (track `ns:Bone` also finds `Bone`); ROOTNODE keeps its
        model-space turn."""
        by = {k: v for k, v in by_name.items() if k != "ROOTNODE"}
        for tr in motion.tracks:
            if tr.name not in by and tr.name.split(":")[-1] in by:
                by[tr.name] = by[tr.name.split(":")[-1]]
        anim.add_animation(self.b, name, motion, by)

    def write(self, path):
        self.b.write(path)


def placement(pos, rot=(0, 0, 0, 1), scl=(1, 1, 1)):
    out = {"translation": [float(x) for x in pos]}
    if abs(rot[3]) < 1 - 1e-9:
        out["rotation"] = [float(x) for x in rot]
    if np.abs(np.asarray(scl) - 1).max() > 1e-6:
        out["scale"] = [float(x) for x in scl]
    return out


def yaw(deg):
    h = math.radians(deg) / 2
    return (0.0, math.sin(h), 0.0, math.cos(h))


# ---- one court ----------------------------------------------------------------------------------------------

def find(dirs, sub, pattern):
    for d in dirs:
        hit = sorted(glob(os.path.join(d, sub, pattern)))
        if hit:
            return hit
    return []


def haichi(dirs):
    p = find(dirs, "haichi", "*__haichi.i3m")
    return i3m.load(p[0]).tracks if p else []


def object_model(dirs, n, model):
    """`c01_ob05_parasol` -> its .psp.i3r under obj/, tree/ or bg/."""
    for sub in ("obj", "tree", "bg", "gimmick"):
        hit = find(dirs, sub, f"*/{model}.psp.i3r")
        if hit:
            return hit[0]
    return None


def routes(path):
    d = open(path, "rb").read()
    n, o, out = struct.unpack_from("<I", d, 0)[0], 4, {}
    for _ in range(n):
        k = struct.unpack_from("<I", d, o)[0]
        o += 4
        pts = [struct.unpack_from("<I3f", d, o + 16 * i) for i in range(k)]
        o += 16 * k
        out.setdefault(pts[0][0], []).extend(p[1:] for p in pts)
    return out


def gimmicks(dirs, n, sc, todo, by_haichi):
    """Place the csv's gimmicks at their routes' first points -> gimmick.glb's instances; returns what's in it.
    by_haichi: folders the placement file already put down."""
    folders = {}
    for d in dirs:
        for g in glob(os.path.join(d, "gimmick", "gi*")):
            folders.setdefault(os.path.basename(g), g)
    setting = next((os.path.join(d, "setting") for d in dirs if glob(os.path.join(d, "setting", "*_route.dat"))), None)
    if not setting:
        return []
    rt = routes(glob(os.path.join(setting, "*_route.dat"))[0])
    rows = []
    for kind, col_route, col_angle in (("escape", 3, 7), ("break", 2, 3)):
        p = glob(os.path.join(setting, f"*_{kind}_gimmick.csv"))
        if p:
            for r in sjis_csv(p[0])[1]:
                rows.append((kind, re.sub(r"\d+$", "", r[0]), int(r[1]), int(r[col_route]), float(r[col_angle])))
    placed, used = [], set()
    for kind, jp, gid, route, angle in rows:
        if jp == "車":
            folder = CAR[gid]
        else:
            folder = next((f for f in folders if f.split("_", 1)[1] == GIMMICK[jp]), None)
        if folder is None or route not in rt:
            todo.append(f"gimmick {jp} (id {gid}, route {route}): no model or route found, not placed")
            continue
        used.add(folder)
        model = next(p for p in sorted(glob(os.path.join(folders[folder], "*.psp.i3r")))
                     if not re.search(r"_(col|b01)\.psp", p))
        x, y, z = rt[route][0]
        inst = f"{folder}_r{route}"
        node = sc.child(sc.top, name=inst, **placement((100 * x, 100 * y, 100 * z), yaw(angle)))
        by = sc.add(model, node)
        mots = {os.path.basename(m)[:-4].split("_", 3)[-1]: m for m in glob(os.path.join(folders[folder], "*.i3m"))}
        rest = next((k for k in REST if k in mots), None)
        if rest:
            sc.animate(inst, i3m.load(mots[rest]), by)
        placed.append(f"{inst} ({kind}, {'loops ' + rest if rest else 'still'})")
    for f in sorted(set(folders) - used - {os.path.basename(x) for x in by_haichi}):
        todo.append(f"gimmick {f}: no row in the escape/break csvs (placed by the program), not in gimmick.glb")
    return placed


def runoff(sc_ground):
    """Flat ground beyond the baselines (+z, -z) and sidelines (+x, -x) in HST metres: walk out from the line
    centre in 0.1 m steps until the ground nearest y = 0 there is more than 5 cm off the court's height (cap 40)."""
    T = np.concatenate(sc_ground)
    A, B, C = T[:, 0], T[:, 1], T[:, 2]

    def height(x, z):
        d = (B[:, 2] - C[:, 2]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 2] - C[:, 2])
        ok = abs(d) > 1e-9
        dd = np.where(ok, d, 1)
        l1 = ((B[:, 2] - C[:, 2]) * (x - C[:, 0]) + (C[:, 0] - B[:, 0]) * (z - C[:, 2])) / dd
        l2 = ((C[:, 2] - A[:, 2]) * (x - C[:, 0]) + (A[:, 0] - C[:, 0]) * (z - C[:, 2])) / dd
        l3 = 1 - l1 - l2
        m = ok & (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        if not m.any():
            return None
        y = l1[m] * A[m, 1] + l2[m] * B[m, 1] + l3[m] * C[m, 1]
        return y[np.argmin(abs(y))]

    y0 = height(0, 0)

    def walk(sx, sz, dx, dz):
        for s in np.arange(0, 40, 0.1):
            h = height(sx + dx * s, sz + dz * s)
            if h is None or abs(h - y0) > 0.05:
                return round(float(s), 1)
        return 40.0

    return [walk(0, 11.885, 0, 1), walk(0, -11.885, 0, -1), walk(5.485, 0, 1, 0), walk(-5.485, 0, -1, 0)]


def ground_triangles(M, skip):
    """Ground model triangles in HST metres (for runoff and the line check), the sky's left out."""
    out = []
    for j, ps in M.rigid.items():
        if j in skip:
            continue
        W = M.sk.world[j] @ build.F
        for p in ps:
            for pr in p.prims:
                P = pr.pos @ W[:3, :3] + W[3, :3]
                P = P * np.array([0.01, -0.01, -0.01])
                t = np.array(i3d.prim_triangles(pr), np.int64).reshape(-1, 3)
                if len(t):
                    out.append(P[t])
    return out


def lines(M, skip):
    """The painted lines' edges as the ground's vertex rows on the court: the outermost x of vertices with
    |z| < 11.9 and the outermost |z| with |x| < 5.5 (m) -> (doubles sideline, baseline)."""
    P = np.concatenate([t.reshape(-1, 3) for t in ground_triangles(M, skip)])
    flat = P[abs(P[:, 1]) < 0.05]
    xs = np.unique(np.round(abs(flat[(abs(flat[:, 2]) < 11.9) & (abs(flat[:, 0]) < 5.6)][:, 0]), 3))
    zs = np.unique(np.round(abs(flat[(abs(flat[:, 0]) < 5.5) & (abs(flat[:, 2]) < 12.0)][:, 2]), 3))
    return xs[-1], zs[-1], xs, zs


def choose_layout(surface, ro):
    back, side = min(ro[0], ro[1]), min(ro[2], ro[3])
    best = None
    for k, (s, r) in enumerate(HST):
        if s != surface:
            continue
        score = abs(math.log(back / min(r[0], r[1]))) + abs(math.log(side / min(r[2], r[3])))
        if best is None or score < best[0]:
            best = (score, k)
    k = best[1]
    r = HST[k][1]
    why = (f"{surface}, like Get a Grip's; of HST's {surface} courts the closest run-off: {back:g} m behind the "
           f"baselines and {side:g} m beside the sidelines here (flat ground, the shorter end/side), "
           f"{min(r[0], r[1]):g} / {min(r[2], r[3]):g} m at {HST_NAMES[k]}")
    return k, why


def loop(sgh, sgb):
    """(start, end) in samples from vgmstream on the raw .sgh/.sgb pair (it needs them side by side)."""
    with tempfile.TemporaryDirectory() as t:
        shutil.copy(sgh, t)
        shutil.copy(sgb, t)
        out = subprocess.run(["vgmstream-cli", "-m", os.path.join(t, os.path.basename(sgb))],
                             capture_output=True, text=True).stdout
    s = re.search(r"loop start: (\d+)", out)
    e = re.search(r"loop end: (\d+)", out)
    return [int(s.group(1)), int(e.group(1))] if s and e else [0, 0]


def sound(n, mod, man, todo):
    os.makedirs(os.path.join(mod, "sound"), exist_ok=True)
    base = os.path.join(AUDIO, f"020_court{n:02d}.xb/data/sound")
    for kind, sub, stem, dst, raw in (("bgm", "BGM", f"bgm_court_{n:02d}", "bgm.wav", "bgm"),
                                      ("ambience", "stream_SE", f"env_co{n:02d}", "ambience_0.wav", "stream_se")):
        wav = os.path.join(base, sub, stem + ".sgh", "001.wav")
        if not os.path.exists(wav):
            todo.append(f"sound/{dst}: {stem} not decoded")
            continue
        shutil.copy(wav, os.path.join(mod, "sound", dst))
        sgh = os.path.join(GAME, f"900_sound/020_court{n:02d}.xb/data/sound", sub, stem + ".sgh")
        lp = loop(sgh, os.path.join(RAW_SOUND, raw, stem + ".sgb"))
        man["bgm_loop" if kind == "bgm" else "ambience_loop"] = lp if kind == "bgm" else [lp]


def light(n):
    _, rows = sjis_csv(os.path.join(SETTING, "courtlight.csv"))
    v = [float(x) for x in rows[n]]
    to_game = np.array([1.0, -1.0, -1.0])

    def unit(d):
        d = np.asarray(d) * to_game
        return [round(float(x), 4) for x in d / (np.linalg.norm(d) or 1)]

    out = {"ambient": v[0:3], "sun_colour": v[3:6], "sun": unit(v[6:9])}
    if any(v[9:12]):
        out["fill_colour"], out["fill"] = v[9:12], unit(v[12:15])
    _, fog = sjis_csv(os.path.join(SETTING, "fogsetting.csv"))
    f = [float(x) for x in fog[n]]
    out["fog"] = None if not (f[0] or f[1]) else {"colour": f[4:7], "near": f[2], "far": f[3], "amount": f[0:2]}
    return out


def export(n, label):
    dirs = court_dirs(n)
    stem = os.path.basename(dirs[0]).split("_", 1)[1]
    _, crows = sjis_csv(os.path.join(SETTING, "court.csv"))
    row = crows[n]
    assert row[0] == f"c{n:02d}_{stem}", row
    surface = row[1].lower()
    indoor = row[3] == "1"
    slug = f"gag_c{n:02d}_{stem}"
    mod = os.path.join(ROOT, "out/mods", slug)
    os.makedirs(mod, exist_ok=True)
    tex = sorted({d for c in dirs for d in glob(os.path.join(c, "**", "sourceimages"), recursive=True)}
                 | {os.path.join(c, "attr") for c in dirs})
    todo = []

    # court.glb: the ground (less its sky) and every placed object; the sky dome and clouds go to sky.glb, placed
    # models that come with motions (flags, a merry-go-round) to gimmick.glb, looping
    sc, ss, gs = Scene(tex), Scene(tex, unlit=True), Scene(tex, clear_view=True)
    gpath = find(dirs, "ground", f"c{n:02d}_{stem}.psp.i3r")[0]
    G = Model(gpath)
    # the dome: `bg01_sky`, or `meshSky01`/`02` (c04, c06): untextured, vertex-coloured, 200-500 m across
    skies = [j for j, x in enumerate(G.sk.names) if re.fullmatch(r"bg01_sky|meshsky\d*", x.lower())]
    sky = set().union(*(G.subtree(G.sk.names[j]) for j in skies))
    sc.add(gpath, sc.child(sc.top, name="ground"), nodes=set(range(len(G.sk.names))) - sky)
    if sky:
        anc = set()
        for j in skies:
            j = G.sk.parents[j]
            while j >= 0:
                anc.add(j)
                j = G.sk.parents[j]
        ss.add(gpath, ss.child(ss.top, name="sky"), nodes=sky | anc, mesh_nodes=sky)
    skipped, placed, drawn_sky, folders = [], [], bool(sky), set()
    for tr in haichi(dirs):
        if ":" in tr.name or "locator" in tr.name or "_gall" in tr.name:
            continue  # a Maya reference duplicate of the next track / where people stand / the gallery (M8f7)
        model = tr.name.split("__", 1)[0]  # `<model>__<NN>`, `<model>__<NN>__singles`, `<model>__doubles`
        path = object_model(dirs, n, model)
        if path is None:
            skipped.append(tr.name)
            continue
        pos, rot, scl = i3m.evaluate(tr, 0.0)
        mots = sorted(glob(os.path.join(os.path.dirname(path), "*.i3m")))
        # only the dome and the clouds follow the eye; distant scenery (c02's and c14's `bg02_Enkei`, 75-200 m out, with its own
        # ground) stays put, as seen from the HST match camera 41 m off the centre
        to_sky = re.search(r"_bg01_|_bg02_cloud", model, re.I)
        scene = ss if to_sky else gs if mots else sc
        node = scene.child(scene.top, name=tr.name, **placement(pos, rot, scl))
        by = scene.add(path, node)
        drawn_sky |= bool(to_sky)
        folders.add(os.path.dirname(path))
        if mots:
            names = {os.path.basename(m)[:-4].rsplit("_", 1)[-1]: m for m in mots}
            m = names[next((k for k in REST if k in names), sorted(names)[0])]
            scene.animate(tr.name, i3m.load(m), by)
            if scene is gs:
                placed.append(f"{tr.name} (placed, loops {os.path.basename(m)[:-4]})")
    if skipped:
        todo.append("haichi tracks without a model on the disc: " + ", ".join(skipped))
    sc.write(os.path.join(mod, "court.glb"))
    if drawn_sky:
        ss.write(os.path.join(mod, "sky.glb"))
    elif os.path.exists(os.path.join(mod, "sky.glb")):
        os.remove(os.path.join(mod, "sky.glb"))
    placed += gimmicks(dirs, n, gs, todo, folders)
    if gs.cleared:
        todo.append("left out of gimmick.glb, standing in HST's match view within %g m of its eye (Get a Grip's "
                    "closer camera has them behind it): %s" % (EYE_CLEAR, "; ".join(gs.cleared)))
    if placed:
        gs.write(os.path.join(mod, "gimmick.glb"))
        todo.append("gimmicks only rest where the csvs put them; their reactions to the ball (pigeons fly off "
                    "along their route, baskets tip into their _b01 model) are the encrypted program's: not reproduced")

    # layout, light, sound
    ro = runoff(ground_triangles(G, sky))
    sideline, baseline, _, _ = lines(G, sky)
    layout, why = choose_layout(surface, ro)
    man = {"standard": 1, "kind": "court", "id": slug, "name": label,
           "source": f"Hot Shots Tennis: Get a Grip (PSP) court{n:02d} (c{n:02d}_{stem})",
           "layout": layout, "layout_why": why, "surface": surface, "light": light(n)}
    sound(n, mod, man, todo)
    se = find(dirs, "setting", f"c{n:02d}_se.csv")
    if se:
        cues = sorted({r[0] for r in sjis_csv(se[0])[1]})
        todo.append("one-shot ambience cues of setting/c%02d_se.csv (%s): their sounds are in no bank on the disc "
                    "(the csv is a template copied from court to court); the stream_SE loop is the ambience" % (n, ", ".join(cues)))
    if not indoor:
        rgba = gim.decode(open(os.path.join(COURT, "lensflare.xb/data/menu/game_eff/flare/flare3.gim"), "rb").read())
        Image.fromarray(rgba, "RGBA").save(os.path.join(mod, "lensflare.png"))
        man["lens_flare"] = "lensflare.png"
    man["indoor"] = indoor
    if placed:
        man["gimmicks"] = placed
    man["todo"] = todo
    json.dump(man, open(os.path.join(mod, "mod.json"), "w"), indent=1, ensure_ascii=False)
    Model.cache.clear()
    return slug, ro, sideline, baseline, layout


def main():
    want = [int(a) for a in sys.argv[1:]] or COURTS
    label = names()
    for n in want:
        slug, ro, sl, bl, layout = export(n, label[n])
        print(f"{slug:24s} {label[n]:30s} lines x {sl:.3f} z {bl:.3f} | run-off {ro} -> layout {layout} {HST_NAMES[layout]}")


if __name__ == "__main__":
    main()
