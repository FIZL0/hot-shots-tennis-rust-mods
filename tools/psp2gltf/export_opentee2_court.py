"""Open Tee 2's Nakagawa Public G.C. hole 7 tennis courts -> a court mod (standard/HST-COURT-UMPIRE-STANDARD.md §2;
HST-Remastered task M8f10a1, notes/venues.md "Real tennis courts").

    python3 tools/psp2gltf/export_opentee2_court.py [--court +|-] [--end +|-]

Reads the unpacked disc under out/files/opentee2/.../xbdata/crs/13 and the decoded audio under out/audio/opentee2,
writes out/mods/ot2_c13_h07_nakagawa/: mod.json, court.glb, sky.glb, sound/bgm.wav, sound/ambience_0.wav.
Game data: out/ only.

What the venue is made of:
  hol07.xb hole/kasen_h07_s1111      the hole's ground (one `polySurface3` mesh: fairway, rough, river bank, the
                                     tennis courts), `net` (two nets, posts), `kanaami1` (the courts' wire fence),
                                     `tekkyo01` (a railway bridge), `water`, the tee boxes -> court.glb
  hol07.xb hole/kasen_h07_s1111_g    the green and its cups -> court.glb
  hol07.xb plant/plant_c13_h07_0.dat HST's 0x40-byte plant records: trees (17, index n -> tree/tNN+1*), props (18,
                                     the tee markers), structures (19, index n -> structure/stNN+1*), the billboard
                                     (20, hio) -> court.glb. Their game space is the meshes' (x, y, z) -> (-x, -y, z)
                                     (the tee markers stand by the tee boxes), turned as HST's own (hst_sim::world::place)
  hol07.xb bg/kasen00_sky_s1111      the sky dome (vertex colours; kasen01 is a paler second one, not used)
  bg0.xb  kasen_{bg,clo}_s1111_p10   the front nine's backdrop: a photo panorama of the river (pSphere2) over a grey
                                     floor (bott), and a cloud band -> sky.glb (bg1.xb's p01 set is the back nine's)
  cmn.xb  sound/at_c_07.sgh + sgb/at_c_07.sgb   the course's music (71 s, looped from 3.5 s) -> sound/bgm.wav
  hol07.xb sound/co_40.sgd           the hole's looping ambience (1 s loop, played at 19644 Hz) -> sound/ambience_0.wav
                                     (co_15, a 0.3 s one-shot, has no place in the standard: left out)

The two courts lie side by side, nets collinear: each a doubles court of 0.1 m lines (`breakwator02@asphalt`
strips; the sidelines' outer edges at 5.49 / 4.11 m, the service lines' at 6.40, the baselines' at 11.88 m from
the court's centre) on bare earth (`c13bare@mud`, 3.8 m run-off behind the baselines), framed by a 1.6 m
`redge01@rough` border, then the hole's rough. Into HST game space (metres, Y down, net along x, the court's long
axis z): one court's centre goes to the origin, the net's direction to x (`--court` picks which court, the other
then stands 19.5 m off along +x or -x; `--end` turns it 180 degrees), the courts' ground (4.48 m up the mesh) to
y = 0. Under `game_space` one `ot2_cm` node carries that map (cm -> m).
"""
import argparse
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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import build  # noqa: E402
import export_getagrip_courts as gag  # noqa: E402
import i3d  # noqa: E402

XB = os.path.join(ROOT, "out/files/opentee2/PSP_GAME/USRDIR/xbdata")
CRS = os.path.join(XB, "crs/13")
HOLE = os.path.join(CRS, "hol07.xb/data")
C13 = os.path.join(HOLE, "course/course13")
BG = os.path.join(CRS, "bg0.xb/data/course/course13/bg")
AUDIO = os.path.join(ROOT, "out/audio/opentee2/PSP_GAME/USRDIR/xbdata/crs/13")
SGB = os.path.join(ROOT, "extracted/opentee2/PSP_GAME/USRDIR/xbdata/sgb")
SLUG = "ot2_c13_h07_nakagawa"

GROUND_Y = 4.48           # the courts' ground, mesh metres (Y up)
SKY_DROP = 386.0          # sky.glb: the panorama's far-bank waterline (386 m up its model) to the eye's level
PLANT = {17: "tree", 18: "prop", 19: "structure", 20: "billboard"}


def court_frame():
    """(centre of the two nets (x, z), unit direction along them, unit normal), mesh metres: from the net cloth."""
    M = gag.Model(os.path.join(C13, "hole/kasen_h07_s1111.psp.i3r"))
    j = M.sk.names.index("net")
    W = M.sk.world[j] @ build.F
    P = np.concatenate([(build._prim_arrays(q, None)["P"] @ W[:3, :3] + W[3, :3]) * 0.01 for q in M.rigid[j]
                        if M.m.materials[q.material].texture == "net@cloth"])[:, [0, 2]]
    c = (P.min(0) + P.max(0)) / 2
    d = np.linalg.svd(P - c)[2][0]
    d = d if d[0] > 0 else -d
    u = (P - c) @ d
    c = c + d * (u.min() + u.max()) / 2  # the middle between the nets' outer ends
    return c, d, np.array([-d[1], d[0]])


def to_game(court, end):
    """3x3 R and t: HST game metres = R @ mesh metres + t. The chosen court's centre -> origin, nets -> x."""
    c, d, n = court_frame()
    M = gag.Model(os.path.join(C13, "hole/kasen_h07_s1111.psp.i3r"))
    j = M.sk.names.index("polySurface3")
    W = M.sk.world[j] @ build.F
    # the court's centre along the net: the middle of its doubles lines (asphalt strips on that side)
    P = np.concatenate([(build._prim_arrays(q, None)["P"] @ W[:3, :3] + W[3, :3]) * 0.01 for q in M.rigid[j]
                        if M.m.materials[q.material].texture == "breakwator02@asphalt"])
    u, v = (P[:, [0, 2]] - c) @ d, (P[:, [0, 2]] - c) @ n
    side = (u * court > 0) & (np.abs(v) < 12.5) & (np.abs(u) < 16)
    mid_u = (u[side].min() + u[side].max()) / 2
    mid_v = (v[side].min() + v[side].max()) / 2
    centre = c + d * mid_u + n * mid_v
    s1 = end
    s2 = -end  # det(R) = -s1 s2 must be +1 (a turn, no mirror)
    R = np.array([[s1 * d[0], 0, s1 * d[1]], [0, -1, 0], [s2 * n[0], 0, s2 * n[1]]])
    assert abs(np.linalg.det(R) - 1) < 1e-9
    t = -R @ np.array([centre[0], GROUND_Y, centre[1]])
    return R, t


def node_matrix(R, t, unit=0.01):
    """glTF column-major matrix: unit-scaled R and translation t."""
    m = np.eye(4)
    m[:3, :3] = R * unit
    m[:3, 3] = t
    return [float(x) for x in m.T.reshape(-1)]


def set_top(sc, name, R, t):
    nd = sc.b.g["nodes"][sc.top]
    for k in ("rotation", "scale", "translation"):
        nd.pop(k, None)
    nd["name"] = name
    nd["matrix"] = node_matrix(R, t)


def plants():
    """[(category, index, pos, yaw, scale, code)] from the hole's plant file (hst_data::layout's record)."""
    d = open(glob(os.path.join(HOLE, "course/plant/plant_c13_h07_0.dat"))[0], "rb").read()
    out = []
    for o in range(0, len(d) - 0x3F, 0x40):
        r = d[o:o + 0x40]
        idx, cat = struct.unpack("<h", r[:2])[0], (r[2] + 0x11) & 0xFF
        out.append((cat, idx, struct.unpack("<3f", r[4:16]), *struct.unpack("<2f", r[0x20:0x28]), r[0x28:0x2C]))
    return out


def rot_y(a):
    s, c = math.sin(a), math.cos(a)
    return np.array([[c, 0, -s, 0], [0, 1, 0, 0], [s, 0, c, 0], [0, 0, 0, 1.0]])


def rot_x(a):
    s, c = math.sin(a), math.cos(a)
    return np.array([[1, 0, 0, 0], [0, c, s, 0], [0, -s, c, 0], [0, 0, 0, 1.0]])


def digit(c):
    c = c - 256 if c >= 128 else c
    return c - 0x30 if c < 0x3A else c - 0x37


def place(cat, pos, yaw, scale, code):
    """HST's prop matrix (row vectors, hst_sim::world::place, here in plain floats) in the plant's game space, then
    into the meshes' (cm): G m G with G = diag(-1, -1, 1) -> glTF column-major."""
    m = np.eye(4)
    m[3, :3] = pos
    m = rot_y(yaw) @ m
    if code[1]:
        a = math.pi * digit(code[1]) / 36
        m = rot_x(a - math.pi if a > math.pi / 2 else a) @ m
    if code[0]:
        a = 2 * math.pi * digit(code[0]) / 36
        a = a - 2 * math.pi if a > math.pi else a + 2 * math.pi if a < -math.pi else a
        m = rot_y(a) @ m
    if scale > 0:
        m = np.diag([scale, scale, scale, 1.0]) @ m
    G = np.diag([-1.0, -1.0, 1.0, 1.0])
    col = G @ m.T @ G
    col[:3, 3] *= 100
    return [float(x) for x in col.T.reshape(-1)]


def model_for(cat, idx):
    kind = PLANT[cat]
    if kind == "tree":
        hit = glob(os.path.join(C13, f"tree/t{idx + 1:02d}*.psp.i3r"))
    elif kind == "structure":
        hit = glob(os.path.join(C13, f"structure/st{idx + 1:02d}*.psp.i3r"))
    else:  # one model each on this hole
        hit = glob(os.path.join(C13, kind, "*.psp.i3r"))
    return hit[0] if len(hit) == 1 else None


def ground_game(R, t):
    """The hole's ground mesh triangles in HST game metres (Y down) and their materials."""
    M = gag.Model(os.path.join(C13, "hole/kasen_h07_s1111.psp.i3r"))
    out, mats = [], []
    for j, ps in M.rigid.items():
        if M.sk.names[j] != "polySurface3":
            continue
        W = M.sk.world[j] @ build.F
        for q in ps:
            for pr in q.prims:
                P = (pr.pos @ W[:3, :3] + W[3, :3]) * 0.01 @ R.T + t
                tr = np.array(i3d.prim_triangles(pr), np.int64).reshape(-1, 3)
                if len(tr):
                    out.append(P[tr])
                    mats += [M.m.materials[q.material].texture] * len(tr)
    return out, mats


def lines(T, mats):
    """The line strips' outer edges (the asphalt strips' vertex rows on the court): doubles sideline, singles
    sideline, service line, baseline, all in |m| from the court's centre."""
    A = np.concatenate([t for t, m in zip(np.concatenate(T), mats) if m == "breakwator02@asphalt"]).reshape(-1, 3)
    A = A[(np.abs(A[:, 0]) < 6) & (np.abs(A[:, 2]) < 12.5)]
    xs = np.unique(np.round(np.abs(A[:, 0]), 3))
    zs = np.unique(np.round(np.abs(A[:, 2]), 3))
    return xs, zs, float(np.abs(A[:, 1]).max())


def bgm(mod, man, todo):
    sgh = os.path.join(CRS, "cmn.xb/data/sound/at_c_07.sgh")
    sgb = os.path.join(SGB, "at_c_07.sgb")
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(sgh, tmp)
        shutil.copy(sgb, tmp)
        src = os.path.join(tmp, "at_c_07.sgb")
        meta = subprocess.run(["vgmstream-cli", "-m", src], capture_output=True, text=True).stdout
        r = subprocess.run(["vgmstream-cli", "-i", "-o", os.path.join(mod, "sound/bgm.wav"), src],
                           capture_output=True, text=True)
    if r.returncode:
        todo.append("sound/bgm.wav: vgmstream couldn't decode at_c_07")
        return
    s, e = re.search(r"loop start: (\d+)", meta), re.search(r"loop end: (\d+)", meta)
    man["bgm_loop"] = [int(s.group(1)), int(e.group(1))] if s and e else [0, 0]


def ambience(mod, man, todo):
    wav = os.path.join(AUDIO, "hol07.xb/data/sound/co_40.sgd/001.wav")
    if not os.path.exists(wav):
        todo.append("sound/ambience_0.wav: co_40 not decoded (tools/audio.py)")
        return
    shutil.copy(wav, os.path.join(mod, "sound/ambience_0.wav"))
    meta = subprocess.run(["vgmstream-cli", "-m", os.path.join(HOLE, "sound/co_40.sgd")], capture_output=True,
                          text=True).stdout
    s, e = re.search(r"loop start: (\d+)", meta), re.search(r"loop end: (\d+)", meta)
    man["ambience_loop"] = [[int(s.group(1)), int(e.group(1))] if s and e else [0, 0]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--court", default="+", help="which of the two courts (along the nets' +/- side) goes to the origin")
    ap.add_argument("--end", default="+", help="'-' turns the court round (180 degrees)")
    ap.add_argument("--out", default=os.path.join(ROOT, "out/mods", SLUG))
    a = ap.parse_args()
    court, end = (1 if a.court == "+" else -1), (1 if a.end == "+" else -1)
    R, t = to_game(court, end)
    mod = a.out
    os.makedirs(os.path.join(mod, "sound"), exist_ok=True)
    todo = []
    tex = [os.path.join(C13, s) for s in ("hole", "tree", "prop", "structure", "billboard", "bg")] + [BG]

    # court.glb: the hole's ground, nets, fence, bridge, water, green, and the placed trees/structures/props
    sc = gag.Scene(tex, clear_blockers=True)
    set_top(sc, "ot2_cm", R, t)
    sc.add(os.path.join(C13, "hole/kasen_h07_s1111.psp.i3r"), sc.child(sc.top, name="hole"))
    sc.add(os.path.join(C13, "hole/kasen_h07_s1111_g.psp.i3r"), sc.child(sc.top, name="green"))
    placed, skipped = {}, []
    for k, (cat, idx, pos, yaw, scale, code) in enumerate(plants()):
        if cat not in PLANT:
            continue
        path = model_for(cat, idx)
        if path is None:
            skipped.append(f"{PLANT[cat]} {idx}")
            continue
        name = os.path.basename(path).split(".")[0]
        node = sc.child(sc.top, name=f"{name}_{k}", matrix=place(cat, pos, yaw, scale, code))
        sc.add(path, node)
        placed[name] = placed.get(name, 0) + 1
    if skipped:
        todo.append("plant records without a model on this hole: " + ", ".join(skipped))
    sc.write(os.path.join(mod, "court.glb"))
    if sc.split:
        todo.append("hidden by HST while they stand between its resting eye and the court (`__clear` children): "
                    + "; ".join(sc.split))

    # sky.glb: dome, panorama, clouds; dropped so the panorama's far bank sits at the eye's level
    ss = gag.Scene(tex, unlit=True)
    set_top(ss, "ot2_cm", R, np.array([0.0, SKY_DROP, 0.0]))  # game Y down: + drops it
    for name, path in (("sky", os.path.join(C13, "bg/kasen00_sky_s1111.psp.i3r")),
                       ("backdrop", os.path.join(BG, "kasen_bg_s1111_p10.psp.i3r")),
                       ("clouds", os.path.join(BG, "kasen_clo_s1111_p10.psp.i3r"))):
        ss.add(path, ss.child(ss.top, name=name))
    ss.write(os.path.join(mod, "sky.glb"))

    T, mats = ground_game(R, t)
    xs, zs, lift = lines(T, mats)
    ro = gag.runoff(T)
    surface = "clay"  # the courts are bare earth (`c13bare@mud`) with asphalt line strips
    back, side = min(ro[0], ro[1]), min(ro[2], ro[3])
    layout = min((k for k, (s, _) in enumerate(gag.HST) if s == surface),
                 key=lambda k: abs(math.log(back / min(gag.HST[k][1][:2]))) + abs(math.log(side / min(gag.HST[k][1][2:]))))
    r = gag.HST[layout][1]
    man = {"standard": 1, "kind": "court", "id": SLUG, "name": "Nakagawa Riverside Courts",
           "source": "Hot Shots Golf: Open Tee 2 (PSP) Nakagawa Public G.C. (crs/13 kasen) hole 7",
           "layout": layout,
           "layout_why": f"clay: the courts are bare earth (c13bare@mud, a golf 'mud' lie) with asphalt line strips, "
                         f"no hard surface; of HST's clay courts the closest run-off: {back:g} m behind the baselines and "
                         f"{side:g} m beside the sidelines here (flat ground, the shorter end/side), "
                         f"{min(r[0], r[1]):g} / {min(r[2], r[3]):g} m at {gag.HST_NAMES[layout]}",
           "surface": surface, "time": "day", "indoor": False}
    bgm(mod, man, todo)
    ambience(mod, man, todo)
    todo.append("light: none in the export (Open Tee 2's per-hole envir_c13_h07.dat isn't decoded): the layout court's")
    todo.append("sky.glb is dropped %g m so the backdrop photo's far-bank waterline sits at the eye's level, judged by "
                "eye: where Open Tee 2 draws its backdrop isn't decoded" % SKY_DROP)
    todo.append("sound: co_15 (a 0.3 s one-shot of the hole's) left out, the standard has no one-shot ambience")
    man["todo"] = todo
    json.dump(man, open(os.path.join(mod, "mod.json"), "w"), indent=1, ensure_ascii=False)
    print("lines: x rows", xs.tolist(), "z rows", zs.tolist(), "max |y| on the court", round(lift, 4))
    print("run-off (+z, -z, +x, -x):", ro, "placed:", placed)
    return mod, man, todo, ro, xs, zs, placed


if __name__ == "__main__":
    main()
