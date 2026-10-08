# Clap Hanz PSP formats (Get a Grip; expected identical in Open Tee 1/2)

Reader code: `tools/psp2gltf/` (`gim.py`, `i3d.py`, `i3m.py`). All little-endian. Confidence: **H** = verified by
rendering/arith, **M** = consistent across data, **L** = guess.

## GIM (`MIG.00.1PSP`) — H
Standard Sony GIM. 16-byte header, then blocks `{u16 id, u16 ?, u32 size (incl. children), u32 child_off,
u32 data_off}` (offsets relative to the block). Ids: 2 root, 3 picture (contain children), 4 image, 5 palette,
0xFF info. Image/palette header at block+data_off: `u16 hdr_size, ref, format, order, width, height, bpp_align,
pitch_align, height_align, dim, ...; +0x1C u32 pixels_start` (relative to header).
Formats 0 5650, 1 5551, 2 4444, 3 8888, 4 idx4, 5 idx8, 6 idx16, 7 idx32 (DXT unseen). `order 1` = PSP swizzle
(16-byte × 8-row tiles, row-major). Characters use idx8 + 256×RGBA8888 CLUT, swizzled.

## I3D_BIN (`.psp.i3r`) — model resource — H
`"I3D_BIN\0", u16 1, u16 0x10, u32 0` then a tree of 16-byte records starting at 0x10:
`u32 data, u32 (type<<24 | count), u32 children, u32 flags(≈const per file)`.
**Every offset (data and children) is relative to file offset 0x10.** `children` → `count` consecutive records
(c==0: none). Type bit 0x80 = data deduplicated (shared with an earlier record); children are still own.

Root (0x52, 8 children): `03` materials, `35`, `03` mesh groups, `02` node list, `37` bounds, `35`, `53`, `54`.

| type | meaning |
|---|---|
| 0x52 | root; data = node table (below) |
| 0x25 | material; child 0x26 = render state + texture name at **+0x3A** (GIM file stem), 0x29/0x32/0x4a/0x49 misc (0x49 = RGB 1,1,1) |
| 0x2d | mesh group; children 0x46 (skinned) and 0x45 (rigid), one of them empty |
| 0x46 | skin: data `u32 off_ibm, off_m2, off_names; u16 n×3` (rel. to data): n inverse-bind mat4, n mat4 (bone-space bounds?, unused), n u32 name offsets (sorted Bip01 names) |
| 0x45 | rigid group; child 0x4b (u32, mostly 0) instead of palettes |
| 0x4c | bone palette: `u32 8, u8 n, u8 4|12, u16 0, n × u16` indices into the 0x46 name list |
| 0x4d | submesh: data +0x0C u16 = material index |
| 0x55/0x4f | strip containers |
| 0x50 | GE primitive: 0x28-byte header `u32 vtype, u32 vertex_count, 0, 0, u32 0x28 (hdr size), u32 ?, 0,0,0, u32 (prim<<8 | 1)`; prim 4 = triangle strip, 3 = triangles; then raw GE vertices |
| 0x2a | node record (in the root node list, one per node, node order); data = s16 parent index; children 0x2b, 0x03 → 0x59 |
| 0x59 | mesh instance on a node: data `u32 ?, u32 mesh-group index (0x2d order), u32 ?` |
| 0x37 | bounding volume |

GE vertex = PSP `vtype` (bits: tc 0-1, col 2-4, nrm 5-6, pos 7-8, wt 9-10, idx 11-12, weight count-1 14-16,
morph count-1 18-20), components in order weights, uv, colour, normal, position, each aligned to its size,
stride aligned to largest. Seen: `0xc5bf` (4×u16 weights /32768, float uv, 8888, s8 normal /127, float pos),
2-8 weights, `0x1bf` (unskinned), `0x19f` (no normal), 2× morph (`0x801bf`, first target used). Weight i →
palette[i]. Vertices are in model space (skinned) or attach-node space (rigid). Units cm, +Y up, faces +Z.
Strip winding is not consistent → exporter orients each triangle by its vertex normals.

**Node table** (root data, offsets relative to it): `f32 sphere[4]; u32 off_local, off_world, off_filename,
off_name_order, off_names, ?; u16 n, n, 1, n; u32 2`. `local`/`world`: n row-vector mat4 (v' = v·M,
translation in row 3; world = local·parent_world). `names`: n u32 offsets of **alphabetically sorted** names;
`name_order[k]` = node index of sorted name k. Parents from the 0x2a list.
`ROOTNODE` local = diag(-1,-1,1) (180° about Z). Skin inverse binds exclude it: `IB·W = diag(-1,-1,1)` for every
bone, i.e. bind pose == node default pose and **the model is authored with ROOTNODE = identity** (exporter
sets it to identity).

Naming: `<Bone>9<name>` = attachment node (`9` stands for a separator): rigid meshes under it (or its children)
follow `<Bone>` of the body skeleton; placement = node world (unflipped) · inverse bind of `<Bone>`.
Maya leftovers (`front/persp/side/top`, `polySurface*`) are ignored.

## I3D_I3M (`.i3m`) — motion — H (rotation/layout), M (position tangents)
`"I3D_I3M\0", u16 1, u16 2, u32 size; +0x10 u16 flags (25 = quantised, 0 = float), u16 11, u16 track_count,
u16 1; +0x18 f32 duration (s); +0x1C u32 off_tracks, off_vec, off_float, off_vec, 0`.
Quantised: +0x30 four vec4: pos extent, pos centre, scale extent, scale centre; vector pool = s16×4 /32767,
position/scale = centre + extent·v (also for their control values). Float variant: pool = f32×4.
Float pool: key times and 1/segment-duration, deduplicated. Track: `u32 name_off, u16 11, u16 nkeys,
u32 data_off`; key = 11 u16: `time, inv_dt, pos, rot, scale, pos_end, rot_end, scale_end, pos_start,
rot_start, scale_start` (indices into the pools).
Rotation: quaternion xyzw, the node's local rotation (column-vector sense; *not* conjugated — knee bend
direction checks), squad(q_k, q_k+1, rot_start_k, rot_end_k, u), `u=(t−t_k)·inv_dt_k`; start/end are the standard
squad inner points s_k, s_k+1 (verified numerically).
Position/scale controls: per-segment tangents; observed `stored = −1.3 × CatmullRom·dt` (cosine −1.000,
ratio 1.300 ± 0.002 over 1150 keys). Exact engine basis unknown; exporter uses Hermite with m = −stored/1.3.
Track names = node names; tracks not present keep the bind local. A_* = upper body layer, B_* = lower body
(+ `pc_locator` root motion, `pelvis_locator` carries pelvis height), unprefixed = full body.
`body_type_NNN.i3m` = 1-key "pose" with bone scales (proportion profile).

## TAT (`.tat`) — texture animation — H (layout), M (semantics)
Reader `tools/psp2gltf/tat.py` (parses all 11 561 files in 400_pc exactly to EOF). LE, no magic:
`u32 ntracks`; per track: `u32 L, char target[L]` (NUL-padded to 4) = `"<material>:<default GIM stem>"`;
`u32 ntex`, ntex × `{u32 L, char stem[L]}` (GIM stems, a per-track palette); `u32 nkeys`, `f32 time[nkeys]` (s),
`u32 index[nkeys]` (into the track's stem list). Step interpolation: texture `index[k]` from `time[k]` to the next
key; duplicate times = instant switch; last key ≈ motion duration. Plays alongside the same-named `.i3m`.
`<material>` is the i3r material *name* (Maya material, flags stripped: `CullingOFF__sortOff__face` → `face`).
Material names: a table of u32 string offsets (rel. 0x10) at file 0xAC, 16-byte stride, in material order.
PC faces: material `face` = right half of the face mesh (x<0), `faceL` = left half (x>0); both use the same
64×128 half-face texture (eyes+brows+mouth, mouth centre at u=0), mirrored. Tracks may differ per half
(winks: `win_pc00_a_r` ends face=0 / faceL=1). Shared `motion/099/*.tat` name generic `100_f_faceN` and
only a `face` track; the engine evidently substitutes the wearer's own `<stem>_faceN` (index N keeps meaning:
0 neutral, 1 blink, 3 impact shout, 4 dejected, …) and drives both halves — inferred (M). Missing stems are
ignored (Helghast tracks name `fourteen_face1..8`, which don't exist). `face/NN/faceNN.tat` (model dir) is a
1/15 s cycle through all textures (preview/preload, unused for expressions).

## Other
`.xb` containers as HST. `adhoc/` dirs hold lower-LOD copies (no fingers) for ad-hoc multiplayer.
