//! `fore2gltf court`: Hot Shots Golf Fore! holes as HST court mods (standard/HST-COURT-UMPIRE-STANDARD.md §2,
//! notes/venues.md; opentennis M8f10a2).
//!
//! ```text
//! fore2gltf court <out/files/fore> <out/venues/fore.json> <HST iso> <out/mods> [course…] [--end -]
//! ```
//! Per course (1–15, or the ones named) the survey's flattest spot (`tools/venues/venues.py fore`: the fitting
//! spot of least height range over all its holes) becomes `out/mods/fore_cCC_<name>/` with `mod.json`, `court.glb`
//! and `sky.glb`:
//! - `court.glb`: under `game_space`, `fore_spot` (the venue moved so the spot's centre lands on HST's court origin,
//!   the spot's length along HST's z, its highest ground 3 cm under y = 0) holds the hole's ground (spring,
//!   `SSN0/GRDccHH.XB`) and its placed trees, props, structures and billboards (HST's plant records, placed with
//!   HST's own `world::place`, models resolved by `layout::resolve` as HST does); those within 45 m of the court
//!   are `__clear`. Beside it `court`: the laid court in HST's game space (a grass slab over the flat ground the
//!   height map allows round the court: the court and its apron in the hole's own green texture with mown stripes,
//!   the rest in its fairway's, each at the scale and colour the hole draws it; lines at HST's judging edges, net
//!   and posts, the umpire's chair under the layout court's chair position read from the HST disc).
//! - `sky.glb`: the hole's first in-season sky and the course's `_clo`/`_acc`/`_bg` backdrops (`BGcc0` front nine,
//!   `BGcc1` back nine), each stood at the eye turned and lifted as HST stands its own (the course and hole
//!   `envir` files are HST's format), turned with the venue.
//! - `mod.json`: layout = the grass disc court whose run-off (the shorter end and side) is closest to the flat
//!   ground measured round the spot.
//! `--end -` turns every venue round (180°).

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use hst_data::{iso::Iso, layout, mdl, mtl};
use serde_json::{Value, json};

use crate::{Glb, R, materials, read, walk};

/// Course stems and names (notes/venues.md, from SYSTEM.BIN's course table; 14 and 15 have no name there).
const COURSES: [(&str, &str); 15] = [
    ("hakone", "Mt. Sakura C.C."),
    ("nangoku", "Aloha Beach Resort"),
    ("western", "Western Valley C.C."),
    ("england", "Bagpipe Classic"),
    ("america", "United Forest G.C."),
    ("hokkaido", "Northern Fox C.C."),
    ("extra", "Day Dream G.C."),
    ("jungle", "Wild Green C.C."),
    ("china", "Silk Road Classic"),
    ("carib", "Blue Lagoon C.C."),
    ("fujizakura", "Fujizakura C.C."),
    ("kawana", "Kawana Hotel G.C."),
    ("samurai", "Samurai Golf Club"),
    ("mini_a", "Mini-golf course 14"),
    ("mini_b", "Mini-golf course 15"),
];

/// HST's disc courts (layout 0–10): surface and run-off behind +z, -z baselines and beside +x, -x sidelines
/// (psp2gltf's `export_getagrip_courts.HST`, measured on the disc courts' collision).
const HST: [(&str, [f32; 4]); 11] = [
    ("clay", [8.5, 8.5, 35.0, 4.9]),
    ("clay", [40.0, 40.0, 40.0, 40.0]),
    ("clay", [40.0, 13.1, 40.0, 37.7]),
    ("hard", [10.7, 10.7, 25.8, 8.4]),
    ("grass", [21.3, 21.3, 9.6, 9.4]),
    ("grass", [18.6, 29.2, 27.8, 10.8]),
    ("hard", [14.9, 14.4, 7.6, 7.6]),
    ("grass", [40.0, 13.6, 7.0, 14.5]),
    ("clay", [17.3, 15.5, 40.0, 40.0]),
    ("grass", [9.0, 9.0, 4.6, 3.2]),
    ("hard", [8.2, 8.2, 4.6, 4.6]),
];
const HST_NAMES: [&str; 11] = ["Alps", "Resort", "Western", "Park", "Wim", "Kar", "Extra", "Jungle", "Kasen", "Greece", "Wafu"];

/// HST's judging edges (hst_sim::judge): doubles and singles sideline, service line, baseline (outer edges, m).
const DOUBLES: f32 = 5.485;
const SINGLES: f32 = 4.115;
const SERVICE: f32 = 6.4;
const BASE: f32 = 11.885;
/// The net posts (0.914 m outside the doubles sidelines) and the net's height at the centre and the posts.
const POST: f32 = 6.4;
const NET_MID: f32 = 0.914;
const NET_POST: f32 = 1.07;
/// The height map's cell, the slab's height range it may hide, how far the ground stands under it.
const CELL: f32 = 1.3;
const FLAT: f32 = 0.5;
const SINK: f32 = 0.03;
/// How far (m) a hole-model triangle may sit from the height map and still count as the ground under the slab.
const GROUND: f32 = 1.0;
/// Run-off (+z, -z, +x, -x) to grow from where the survey's footprint doesn't pass [`runoff`]'s check.
const SEED: [f32; 4] = [3.0, 3.0, 2.0, 2.0];
/// What a placed object keeps clear (tools/venues/venues.py `BLOCK`), metres times its scale clamped 1–4.
const BLOCK: [(u8, f32); 4] = [(17, 3.0), (18, 2.0), (19, 12.0), (20, 3.0)];
/// Placed pieces this near the court centre are `__clear` (hidden while between the eye and the court).
const CLEAR_WITHIN: f32 = 45.0;

type M4 = [[f32; 4]; 4];

/// Column-vector matrix product.
fn mm(a: &M4, b: &M4) -> M4 {
    std::array::from_fn(|r| std::array::from_fn(|c| (0..4).map(|k| a[r][k] * b[k][c]).sum()))
}

fn ident() -> M4 {
    std::array::from_fn(|r| std::array::from_fn(|c| if r == c { 1.0 } else { 0.0 }))
}

/// glTF's column-major array of a column-vector matrix.
fn gl(m: &M4) -> Vec<f32> {
    (0..16).map(|k| m[k % 4][k / 4]).collect()
}

/// Bevy's `Quat::from_rotation_y` as a column-vector matrix (how HST turns its backdrops).
fn rot_y(a: f32) -> M4 {
    let (s, c) = a.sin_cos();
    [[c, 0.0, s, 0.0], [0.0, 1.0, 0.0, 0.0], [-s, 0.0, c, 0.0], [0.0, 0.0, 0.0, 1.0]]
}

fn apply(m: &M4, p: [f32; 3]) -> [f32; 3] {
    std::array::from_fn(|r| m[r][0] * p[0] + m[r][1] * p[1] + m[r][2] * p[2] + m[r][3])
}

/// A hole's height and lie map (`*.HMP`, notes/venues.md): x-major cells of CELL m from (x0, z0), game y (down).
struct Hmp {
    x0: f32,
    z0: f32,
    nx: usize,
    nz: usize,
    y: Vec<f32>,
    lie: Vec<u8>,
}

impl Hmp {
    fn parse(d: &[u8]) -> R<Hmp> {
        let f = |o: usize| f32::from_le_bytes(d[o..o + 4].try_into().unwrap());
        let u = |o: usize| u32::from_le_bytes(d[o..o + 4].try_into().unwrap()) as usize;
        let (nx, nz) = (u(8), u(12));
        if d.len() < 16 + 5 * nx * nz {
            return Err("short HMP".into());
        }
        Ok(Hmp { x0: f(0), z0: f(4), nx, nz, y: (0..nx * nz).map(|i| f(16 + 4 * i)).collect(), lie: d[16 + 4 * nx * nz..16 + 5 * nx * nz].to_vec() })
    }

    /// (height, lie) of the cell under (x, z); `None` off the map.
    fn at(&self, x: f32, z: f32) -> Option<(f32, u8)> {
        let (r, c) = (((x - self.x0) / CELL).floor(), ((z - self.z0) / CELL).floor());
        if r < 0.0 || c < 0.0 || r as usize >= self.nx || c as usize >= self.nz {
            return None;
        }
        let i = r as usize * self.nz + c as usize;
        Some((self.y[i], self.lie[i]))
    }
}

/// The spot: centre (x, z) in the hole's game space, the court's length direction (yaw from +z toward +x).
#[derive(Clone, Copy)]
struct Spot {
    hole: u32,
    x: f32,
    z: f32,
    yaw: f32,
    range: f32,
}

impl Spot {
    /// Venue → HST game space (before the height): HST x along n = (cos, -sin), z along d = (sin, cos).
    fn venue(&self, top: f32) -> M4 {
        let (s, c) = self.yaw.to_radians().sin_cos();
        let (n, d) = ([c, -s], [s, c]);
        [
            [n[0], 0.0, n[1], -(self.x * n[0] + self.z * n[1])],
            [0.0, 1.0, 0.0, -top],
            [d[0], 0.0, d[1], -(self.x * d[0] + self.z * d[1])],
            [0.0, 0.0, 0.0, 1.0],
        ]
    }

    /// HST (x, z) → the hole's (x, z).
    fn to_hole(&self, x: f32, z: f32) -> (f32, f32) {
        let (s, c) = self.yaw.to_radians().sin_cos();
        (self.x + c * x + s * z, self.z - s * x + c * z)
    }
}

/// The survey's fitting spots per course, flattest first (every hole's best few yaws).
fn spots(survey: &Value) -> HashMap<u32, Vec<Spot>> {
    let mut out: HashMap<u32, Vec<Spot>> = HashMap::new();
    for r in survey.as_array().into_iter().flatten() {
        let (c, h) = (r["course"].as_u64().unwrap_or(0) as u32, r["hole"].as_u64().unwrap_or(0) as u32);
        for b in r["best"].as_array().into_iter().flatten().filter(|b| b["fits"].as_bool() == Some(true)) {
            let f = |k: &str| b[k].as_f64().unwrap_or(0.0) as f32;
            out.entry(c).or_default().push(Spot { hole: h, x: f("x"), z: f("z"), yaw: f("yaw"), range: f("range") });
        }
    }
    for v in out.values_mut() {
        v.sort_by(|a, b| a.range.total_cmp(&b.range).then(a.hole.cmp(&b.hole)));
    }
    out
}

/// Lower-case file name → path, for every file under the given archive directories.
fn index(dirs: &[PathBuf]) -> HashMap<String, PathBuf> {
    let mut out = HashMap::new();
    for d in dirs {
        for p in walk(d) {
            if let Some(n) = p.file_name().and_then(|n| n.to_str()) {
                out.entry(n.to_ascii_lowercase()).or_insert(p);
            }
        }
    }
    out
}

fn find(ix: &HashMap<String, PathBuf>, name: &str) -> Option<PathBuf> {
    ix.get(&name.to_ascii_lowercase()).cloned()
}

/// A model and its MTL: `stem.mdl` with `mtl_stem.mtl` (+ `.mti`).
fn load(ix: &HashMap<String, PathBuf>, stem: &str, mtl_stem: &str) -> R<(mdl::Model, mtl::Mtl)> {
    let m = find(ix, &format!("{stem}.mdl")).ok_or(format!("{stem}.mdl not found"))?;
    let t = find(ix, &format!("{mtl_stem}.mtl")).ok_or(format!("{mtl_stem}.mtl not found"))?;
    let mti = find(ix, &format!("{mtl_stem}.mti")).map(|p| read(&p)).transpose()?;
    let model = mdl::parse(&read(&m)?).map_err(|e| format!("{}: {e:?}", m.display()))?;
    let mats = mtl::parse(&read(&t)?, mti.as_deref()).map_err(|e| format!("{}: {e:?}", t.display()))?;
    Ok((model, mats))
}

/// The season mask of a stem's `_sXXXX` (HST's `layout` rule), all seasons when it has none.
fn season(stem: &str) -> [bool; 4] {
    if let Some(i) = stem.rfind("_s") {
        let m = stem.as_bytes().get(i + 2..i + 6).unwrap_or(&[]);
        if m.len() == 4 && m.iter().all(|c| matches!(c, b'0' | b'1')) {
            return std::array::from_fn(|k| m[k] == b'1');
        }
    }
    [true; 4]
}

/// One primitive's arrays.
#[derive(Default)]
struct Prim {
    pos: Vec<[f32; 3]>,
    nrm: Vec<[f32; 3]>,
    uv: Vec<[f32; 2]>,
    col: Vec<[f32; 4]>,
    idx: Vec<u32>,
    /// Texture coordinates in metres over this (a laid surface: x, z from above, along the side and down on a skirt).
    metres: Option<f32>,
}

impl Prim {
    fn quad(&mut self, p: [[f32; 3]; 4], col: [f32; 4]) {
        let b = self.pos.len() as u32;
        let e1: [f32; 3] = std::array::from_fn(|k| p[1][k] - p[0][k]);
        let e2: [f32; 3] = std::array::from_fn(|k| p[3][k] - p[0][k]);
        let n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]];
        let l = (n[0] * n[0] + n[1] * n[1] + n[2] * n[2]).sqrt().max(1e-9);
        for q in p {
            self.pos.push(q);
            self.nrm.push(n.map(|v| v / l));
            self.uv.push(match self.metres {
                Some(m) if (n[1] / l).abs() > 0.7 => [q[0] / m, q[2] / m],
                Some(m) => [(q[0] + q[2]) / m, q[1] / m],
                None => [0.0; 2],
            });
            self.col.push(col);
        }
        self.idx.extend([b, b + 1, b + 2, b, b + 2, b + 3]);
    }

    /// A flat rectangle at height y (game y down: smaller is higher), x0..x1 × z0..z1.
    fn flat(&mut self, x0: f32, x1: f32, z0: f32, z1: f32, y: f32, col: [f32; 4]) {
        self.quad([[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]], col);
    }

    /// A box from (x0, y0, z0) to (x1, y1, z1).
    fn cuboid(&mut self, a: [f32; 3], b: [f32; 3], col: [f32; 4]) {
        let [x0, y0, z0] = a;
        let [x1, y1, z1] = b;
        self.quad([[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]], col);
        self.quad([[x0, y1, z0], [x0, y1, z1], [x1, y1, z1], [x1, y1, z0]], col);
        self.quad([[x0, y0, z0], [x0, y1, z0], [x1, y1, z0], [x1, y0, z0]], col);
        self.quad([[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], col);
        self.quad([[x0, y0, z0], [x0, y0, z1], [x0, y1, z1], [x0, y1, z0]], col);
        self.quad([[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]], col);
    }
}

/// The glTF document being built.
struct Doc {
    g: Glb,
    doc: Value,
    nodes: Vec<Value>,
}

impl Doc {
    fn new() -> Doc {
        let doc = json!({
            "asset": {"version": "2.0", "generator": "fore2gltf court"},
            "extensionsUsed": ["KHR_materials_unlit"],
            "scene": 0, "meshes": [], "materials": [], "images": [], "samplers": [], "textures": [],
        });
        Doc { g: Glb::default(), doc, nodes: vec![json!({"name": "game_space", "rotation": [0.0, 0.0, 1.0, 0.0]})] }
    }

    fn node(&mut self, parent: usize, mut node: Value) -> usize {
        if node.get("matrix").and_then(|m| m.as_array()).is_some_and(|m| m.iter().zip(gl(&ident())).all(|(a, b)| a.as_f64() == Some(b as f64))) {
            node.as_object_mut().unwrap().remove("matrix");
        }
        self.nodes.push(node);
        let i = self.nodes.len() - 1;
        let p = &mut self.nodes[parent];
        if p.get("children").is_none() {
            p["children"] = json!([]);
        }
        p["children"].as_array_mut().unwrap().push(json!(i));
        i
    }

    fn mesh(&mut self, name: &str, prims: Vec<(usize, Prim)>) -> Option<usize> {
        let mut out = Vec::new();
        for (material, p) in prims.iter().filter(|(_, p)| !p.idx.is_empty()) {
            let attrs = json!({
                "POSITION": self.g.floats(&p.pos, "VEC3", true, Some(34962)),
                "NORMAL": self.g.floats(&p.nrm, "VEC3", false, Some(34962)),
                "TEXCOORD_0": self.g.floats(&p.uv, "VEC2", false, Some(34962)),
                "COLOR_0": self.g.floats(&p.col, "VEC4", false, Some(34962)),
            });
            let ib: Vec<u8> = p.idx.iter().flat_map(|i| i.to_le_bytes()).collect();
            let indices = self.g.ints(&ib, 5125, "SCALAR", p.idx.len(), Some(34963));
            out.push(json!({"attributes": attrs, "indices": indices, "material": material, "mode": 4}));
        }
        if out.is_empty() {
            return None;
        }
        let meshes = self.doc["meshes"].as_array_mut().unwrap();
        meshes.push(json!({"name": name, "primitives": out}));
        Some(meshes.len() - 1)
    }

    /// A model's static mesh (its packets at the bind pose, as HST draws its own court models), a primitive per
    /// material; vertex colours in HST's units (textured: 0x80 = 1.0; untextured: /255, HST's court mod loader
    /// scales those by 255/128).
    fn model(&mut self, name: &str, model: &mdl::Model, mats: &mtl::Mtl) -> Option<usize> {
        let m0 = materials(&mut self.g, &mut self.doc, model, mats, &format!("{name}_"));
        let mut prims = Vec::new();
        for (mi, packets) in model.materials.iter().enumerate() {
            let textured = mats.materials.get(mi).and_then(|m| m.texture).is_some_and(|t| !mats.textures[t].rgba.is_empty());
            let unit = if textured { 128.0 } else { 255.0 };
            let mut p = Prim::default();
            for pk in packets {
                let base = p.pos.len() as u32;
                if pk.palette.len() > 1 {
                    let (verts, tris, _) = model.skin_packet(pk);
                    for v in &verts {
                        p.pos.push(v.pos);
                        p.nrm.push(unit_or_down(std::array::from_fn(|k| v.normals[0][k] + v.normals[1][k])));
                        p.uv.push(v.uv);
                        p.col.push(v.color.map(|c| c as f32 / unit));
                    }
                    p.idx.extend(tris.iter().flatten().map(|i| i + base));
                    continue;
                }
                // a packet bound to one node, by its bind matrix (row vectors)
                let b = pk.palette.first().and_then(|&n| model.node_bind.get(n)).copied();
                for v in &pk.vertices {
                    let (q, n) = match &b {
                        Some(m) => (
                            std::array::from_fn(|k| v.pos[0] * m[0][k] + v.pos[1] * m[1][k] + v.pos[2] * m[2][k] + m[3][k]),
                            std::array::from_fn(|k| v.normal[0] * m[0][k] + v.normal[1] * m[1][k] + v.normal[2] * m[2][k]),
                        ),
                        None => (v.pos, v.normal),
                    };
                    p.pos.push(q);
                    p.nrm.push(unit_or_down(n));
                    p.uv.push(v.uv);
                    p.col.push(v.color.map(|c| c as f32 / unit));
                }
                p.idx.extend(pk.triangles.iter().flatten().map(|i| i + base));
            }
            prims.push((m0 + mi, p));
        }
        self.mesh(name, prims)
    }

    /// A copy of material `m` (a hole model's, textured) drawn opaque with its texture repeating, for a laid surface.
    fn tiled(&mut self, name: &str, m: usize) -> usize {
        let mut mat = self.doc["materials"][m].clone();
        mat["name"] = json!(name);
        mat.as_object_mut().unwrap().remove("alphaMode");
        let tex = self.doc["textures"][mat["pbrMetallicRoughness"]["baseColorTexture"]["index"].as_u64().unwrap() as usize]["source"].clone();
        let samplers = self.doc["samplers"].as_array_mut().unwrap();
        samplers.push(json!({"magFilter": 9729, "minFilter": 9729, "wrapS": 10497, "wrapT": 10497}));
        let sampler = samplers.len() - 1;
        let textures = self.doc["textures"].as_array_mut().unwrap();
        textures.push(json!({"source": tex, "sampler": sampler}));
        mat["pbrMetallicRoughness"]["baseColorTexture"] = json!({"index": textures.len() - 1});
        let list = self.doc["materials"].as_array_mut().unwrap();
        list.push(mat);
        list.len() - 1
    }

    /// An untextured material (vertex colour × `color`).
    fn plain(&mut self, name: &str, color: [f32; 4], blend: bool) -> usize {
        let mut m = json!({"name": name, "pbrMetallicRoughness": {"baseColorFactor": color, "metallicFactor": 0.0, "roughnessFactor": 1.0},
                           "doubleSided": true, "extensions": {"KHR_materials_unlit": {}}});
        if blend {
            m["alphaMode"] = json!("BLEND");
        }
        let list = self.doc["materials"].as_array_mut().unwrap();
        list.push(m);
        list.len() - 1
    }

    fn finish(mut self) -> Vec<u8> {
        let mut doc = self.doc;
        doc["nodes"] = json!(self.nodes);
        doc["scenes"] = json!([{"nodes": [0]}]);
        for k in ["images", "samplers", "textures"] {
            if doc[k].as_array().unwrap().is_empty() {
                doc.as_object_mut().unwrap().remove(k);
            }
        }
        doc["accessors"] = json!(self.g.accessors);
        doc["bufferViews"] = json!(self.g.views);
        while self.g.bin.len() % 4 != 0 {
            self.g.bin.push(0);
        }
        doc["buffers"] = json!([{"byteLength": self.g.bin.len()}]);
        let mut js = serde_json::to_vec(&doc).unwrap();
        while js.len() % 4 != 0 {
            js.push(b' ');
        }
        let mut out = Vec::with_capacity(28 + js.len() + self.g.bin.len());
        out.extend(b"glTF");
        out.extend(2u32.to_le_bytes());
        out.extend(((28 + js.len() + self.g.bin.len()) as u32).to_le_bytes());
        out.extend((js.len() as u32).to_le_bytes());
        out.extend(b"JSON");
        out.extend(js);
        out.extend((self.g.bin.len() as u32).to_le_bytes());
        out.extend(b"BIN\0");
        out.extend(self.g.bin);
        out
    }
}

/// A model's triangles at the bind pose (as [`Doc::model`] places them).
fn triangles(model: &mdl::Model) -> Vec<[[f32; 3]; 3]> {
    let mut out = Vec::new();
    for pk in model.materials.iter().flatten() {
        let (verts, tris): (Vec<[f32; 3]>, Vec<[u32; 3]>) = if pk.palette.len() > 1 {
            let (v, t, _) = model.skin_packet(pk);
            (v.iter().map(|v| v.pos).collect(), t)
        } else {
            let b = pk.palette.first().and_then(|&n| model.node_bind.get(n)).copied();
            let v = pk.vertices.iter().map(|v| match &b {
                Some(m) => std::array::from_fn(|k| v.pos[0] * m[0][k] + v.pos[1] * m[1][k] + v.pos[2] * m[2][k] + m[3][k]),
                None => v.pos,
            });
            (v.collect(), pk.triangles.clone())
        };
        out.extend(tris.iter().filter(|t| t.iter().all(|&i| (i as usize) < verts.len())).map(|t| t.map(|i| verts[i as usize])));
    }
    out
}

/// A model's triangles at the bind pose with their material, UVs and vertex colours (0x80 = 1.0).
fn textured_triangles(model: &mdl::Model) -> Vec<(usize, [[f32; 3]; 3], [[f32; 2]; 3], [[f32; 4]; 3])> {
    let mut out = Vec::new();
    for (mi, packets) in model.materials.iter().enumerate() {
        for pk in packets {
            let (verts, tris): (Vec<([f32; 3], [f32; 2], [u8; 4])>, Vec<[u32; 3]>) = if pk.palette.len() > 1 {
                let (v, t, _) = model.skin_packet(pk);
                (v.iter().map(|v| (v.pos, v.uv, v.color)).collect(), t)
            } else {
                let b = pk.palette.first().and_then(|&n| model.node_bind.get(n)).copied();
                let v = pk.vertices.iter().map(|v| {
                    let q = match &b {
                        Some(m) => std::array::from_fn(|k| v.pos[0] * m[0][k] + v.pos[1] * m[1][k] + v.pos[2] * m[2][k] + m[3][k]),
                        None => v.pos,
                    };
                    (q, v.uv, v.color)
                });
                (v.collect(), pk.triangles.clone())
            };
            for t in tris.iter().filter(|t| t.iter().all(|&i| (i as usize) < verts.len())) {
                let v = t.map(|i| verts[i as usize]);
                out.push((mi, v.map(|v| v.0), v.map(|v| v.1), v.map(|v| v.2.map(|c| c as f32 / 128.0))));
            }
        }
    }
    out
}

/// A hole-model material laid as a surface: which, its metres per texture repeat, and its mean vertex colour.
#[derive(Clone, Copy, Debug)]
struct Surface {
    material: usize,
    metres: f32,
    colour: [f32; 4],
}

/// The hole model's textured material covering the most ground (by area seen from above) where `keep` says (the
/// triangle's centre in the hole's x, z, and its lie), with the scale and colour it's drawn at there.
fn surface_of(tris: &[(usize, [[f32; 3]; 3], [[f32; 2]; 3], [[f32; 4]; 3])], mats: &mtl::Mtl, keep: impl Fn(f32, f32) -> bool) -> Option<Surface> {
    let mut area: HashMap<usize, (f32, f32, [f32; 4])> = HashMap::new();
    for (mi, p, uv, col) in tris {
        if !mats.materials.get(*mi).and_then(|m| m.texture).is_some_and(|t| !mats.textures[t].rgba.is_empty()) {
            continue;
        }
        let (cx, cz) = ((p[0][0] + p[1][0] + p[2][0]) / 3.0, (p[0][2] + p[1][2] + p[2][2]) / 3.0);
        if !keep(cx, cz) {
            continue;
        }
        let cross = |a: [f32; 2], b: [f32; 2]| (a[0] * b[1] - a[1] * b[0]).abs() / 2.0;
        let flat = cross([p[1][0] - p[0][0], p[1][2] - p[0][2]], [p[2][0] - p[0][0], p[2][2] - p[0][2]]);
        let e1: [f32; 3] = std::array::from_fn(|k| p[1][k] - p[0][k]);
        let e2: [f32; 3] = std::array::from_fn(|k| p[2][k] - p[0][k]);
        let n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]];
        let world = (n[0] * n[0] + n[1] * n[1] + n[2] * n[2]).sqrt() / 2.0;
        let tex = cross([uv[1][0] - uv[0][0], uv[1][1] - uv[0][1]], [uv[2][0] - uv[0][0], uv[2][1] - uv[0][1]]);
        if flat < 1e-4 || tex < 1e-9 {
            continue;
        }
        let a = area.entry(*mi).or_insert((0.0, 0.0, [0.0; 4]));
        a.0 += flat;
        // metres per UV unit, area-weighted (as √(world area / UV area))
        a.1 += flat * (world / tex).sqrt();
        let c: [f32; 4] = std::array::from_fn(|k| (col[0][k] + col[1][k] + col[2][k]) / 3.0);
        a.2 = std::array::from_fn(|k| a.2[k] + flat * c[k]);
    }
    let (&material, &(a, m, c)) = area.iter().max_by(|x, y| x.1.0.total_cmp(&y.1.0))?;
    Some(Surface { material, metres: m / a, colour: c.map(|v| v / a) })
}

fn unit_or_down(n: [f32; 3]) -> [f32; 3] {
    let l = (n[0] * n[0] + n[1] * n[1] + n[2] * n[2]).sqrt();
    if l > 1e-6 { n.map(|v| v / l) } else { [0.0, -1.0, 0.0] }
}

/// HST's backdrop turn and lift (opentennis `gs::backdrop`): the course envir's yaw for backdrop kind `i`
/// (sky, clo, acc, bg) less the hole envir's turn, folded into ±π; the hole envir's lift (370 without one).
fn backdrop(envir: &[u8], hole: Option<&[u8]>, i: usize) -> (f32, f32) {
    use hst_sim::ps2::{add, mul, sub};
    let f = |d: &[u8], o: usize| d.get(o..o + 4).map_or(0.0, |b| f32::from_le_bytes(b.try_into().unwrap()));
    let (turn, lift) = hole.map_or((0.0, 370.0), |h| (f(h, 0x58), f(h, 0x10 + 4 * i)));
    let mut yaw = sub(add(f(envir, 0x450 + 4 * i), 0.0), mul(turn, 0.017453292));
    if yaw > std::f32::consts::PI {
        yaw = sub(yaw, 6.2831855);
    } else if yaw < -std::f32::consts::PI {
        yaw = add(yaw, 6.2831855);
    }
    (yaw, lift)
}

/// Flat ground round the court on the height map: run-off behind the +z, -z baselines and beside the +x, -x
/// sidelines (HST metres), grown 0.5 m at a time from the survey's footprint while the whole slab stays on the map,
/// off water, clear of placed objects and within FLAT of height; capped at 15 m behind and 10 m beside. `fits`:
/// the footprint itself passed.
fn runoff(hmp: &Hmp, spot: &Spot, blockers: &[(f32, f32, f32)]) -> ([f32; 4], f32, bool) {
    let ok = |ro: &[f32; 4]| -> Option<f32> {
        let (mut lo, mut hi) = (f32::MAX, f32::MIN);
        let (x0, x1, z0, z1) = (-(DOUBLES + ro[3]), DOUBLES + ro[2], -(BASE + ro[1]), BASE + ro[0]);
        let step = 0.5;
        let (nx, nz) = (((x1 - x0) / step).ceil() as usize, ((z1 - z0) / step).ceil() as usize);
        for i in 0..=nx {
            for k in 0..=nz {
                let (x, z) = (x0 + (x1 - x0) * i as f32 / nx as f32, z0 + (z1 - z0) * k as f32 / nz as f32);
                let (hx, hz) = spot.to_hole(x, z);
                let (y, lie) = hmp.at(hx, hz)?;
                if lie == 0 || lie == 27 || blockers.iter().any(|&(bx, bz, r)| (bx - hx).powi(2) + (bz - hz).powi(2) <= r * r) {
                    return None;
                }
                (lo, hi) = (lo.min(y), hi.max(y));
            }
        }
        (hi - lo <= FLAT).then_some(hi - lo)
    };
    let mut ro = [BASE.mul_add(-1.0, 20.0), BASE.mul_add(-1.0, 20.0), DOUBLES.mul_add(-1.0, 10.0), DOUBLES.mul_add(-1.0, 10.0)];
    let fits = ok(&ro).is_some();
    // the survey's window is cell-sized and can sit a cell off: then grow from a small run-off instead
    if !fits && ok(&SEED).is_some() {
        ro = SEED;
    }
    if ok(&ro).is_some() {
        let mut grew = true;
        while grew {
            grew = false;
            for k in 0..4 {
                let cap = if k < 2 { 15.0 } else { 10.0 };
                let mut t = ro;
                t[k] = (t[k] + 0.5).min(cap);
                if t[k] > ro[k] && ok(&t).is_some() {
                    ro = t;
                    grew = true;
                }
            }
        }
    }
    let range = ok(&ro).unwrap_or(f32::NAN);
    (ro, range, fits)
}

/// How far round the court the court's own surface runs (beside the doubles sidelines, behind the baselines, m);
/// the run-off beyond it is the hole's fairway.
const APRON: [f32; 2] = [1.8, 3.0];

/// The laid court in HST's game space: slab over the run-off (mown stripes), white lines, net, posts and the chair.
/// `turf`: the hole's own green and fairway (M8f10a4: glTF material, how they're laid): the court in the green's
/// texture, the run-off and the slab's skirts in the fairway's; without them a plain striped slab.
fn laid(d: &mut Doc, ro: [f32; 4], depth: f32, chair: [f32; 3], turf: Option<[(usize, Surface); 2]>) {
    let grass = d.plain("court_grass", [1.0; 4], false);
    let white = d.plain("court_lines", [1.0; 4], false);
    let net = d.plain("court_net", [1.0, 1.0, 1.0, 0.55], true);
    let (x0, x1, z0, z1) = (-(DOUBLES + ro[3]), DOUBLES + ro[2], -(BASE + ro[1]), BASE + ro[0]);
    // grass: 0..1 vertex colours (the loader's untextured scale makes 1.0 full brightness); laid turf: the colour the
    // hole draws it at, the darker stripes 8 % down
    let (light, dark, side) = match turf {
        Some([(_, g), (_, f)]) => (g.colour, g.colour.map(|c| c * 0.92), f.colour.map(|c| c * 0.8)),
        None => ([0.36, 0.56, 0.24, 1.0], [0.31, 0.50, 0.21, 1.0], [0.27, 0.40, 0.18, 1.0]),
    };
    let opaque = |c: [f32; 4]| [c[0], c[1], c[2], 1.0];
    let (light, dark, side) = (opaque(light), opaque(dark), opaque(side));
    let mut g = Prim { metres: turf.map(|t| t[0].1.metres), ..Prim::default() };
    let mut f = Prim { metres: turf.map(|t| t[1].1.metres), ..Prim::default() };
    // the striped part: the whole slab, or with turf the court and its apron (the fairway round it)
    let (cx0, cx1, cz0, cz1) = match turf {
        Some(_) => (x0.max(-DOUBLES - APRON[0]), x1.min(DOUBLES + APRON[0]), z0.max(-BASE - APRON[1]), z1.min(BASE + APRON[1])),
        None => (x0, x1, z0, z1),
    };
    if let Some([_, (_, fw)]) = turf {
        let c = opaque(fw.colour);
        for (a, b, c0, c1) in [(x0, x1, z0, cz0), (x0, x1, cz1, z1), (x0, cx0, cz0, cz1), (cx1, x1, cz0, cz1)] {
            if a < b && c0 < c1 {
                f.flat(a, b, c0, c1, 0.0, c);
            }
        }
    }
    // stripes across the court, 12 to a baseline-to-baseline length, from the court's centre
    let w = 2.0 * BASE / 12.0;
    let mut z = cz0;
    while z < cz1 {
        let k = ((z - cz0 + 1e-3) / w).floor();
        let zn = (cz0 + (k + 1.0) * w).min(cz1);
        let band = ((z + 1e-3 + BASE) / w).floor() as i32;
        g.flat(cx0, cx1, z, zn, 0.0, if band.rem_euclid(2) == 0 { light } else { dark });
        z = zn;
    }
    let skirt = if turf.is_some() { &mut f } else { &mut g };
    for (a, b) in [([x0, 0.0, z0], [x1, 0.0, z0]), ([x1, 0.0, z0], [x1, 0.0, z1]), ([x1, 0.0, z1], [x0, 0.0, z1]), ([x0, 0.0, z1], [x0, 0.0, z0])] {
        skirt.quad([a, b, [b[0], depth, b[2]], [a[0], depth, a[2]]], side);
    }
    // lines 3 mm above the slab, outer edges on HST's judging edges
    let mut l = Prim::default();
    let c = [0.95, 0.95, 0.93, 1.0];
    let y = -0.003;
    for s in [-1.0f32, 1.0] {
        l.flat(s * DOUBLES - 0.05, s * DOUBLES + 0.05, -BASE, BASE, y, c); // doubles sidelines (0.1 m)
        l.flat(s * SINGLES - 0.05, s * SINGLES + 0.05, -BASE, BASE, y, c); // singles sidelines
        l.flat(-DOUBLES, DOUBLES, s * BASE - 0.05, s * BASE + 0.05, y, c); // baselines
        l.flat(-SINGLES, SINGLES, s * SERVICE - 0.025, s * SERVICE + 0.025, y, c); // service lines (5 cm)
        l.flat(-0.05, 0.05, s * BASE - s * 0.25, s * BASE - s * 0.05, y, c); // centre marks
    }
    l.flat(-0.025, 0.025, -SERVICE, SERVICE, y, c); // centre service line
    // net: the mesh as a see-through panel sagging from the posts to the centre, a white tape on top, a strap
    let mut n = Prim::default();
    let height = |x: f32| NET_MID + (NET_POST - NET_MID) * (x.abs() / POST);
    let steps = 16;
    for i in 0..steps {
        let (a, b) = (-POST + 2.0 * POST * i as f32 / steps as f32, -POST + 2.0 * POST * (i + 1) as f32 / steps as f32);
        n.quad([[a, -0.02, 0.0], [b, -0.02, 0.0], [b, -height(b) + 0.05, 0.0], [a, -height(a) + 0.05, 0.0]], [0.05, 0.05, 0.05, 1.0]);
        l.quad([[a, -height(a) + 0.05, -0.012], [b, -height(b) + 0.05, -0.012], [b, -height(b), -0.012], [a, -height(a), -0.012]], c);
        l.quad([[a, -height(a) + 0.05, 0.012], [b, -height(b) + 0.05, 0.012], [b, -height(b), 0.012], [a, -height(a), 0.012]], c);
        l.quad([[a, -height(a), -0.012], [b, -height(b), -0.012], [b, -height(b), 0.012], [a, -height(a), 0.012]], c);
    }
    l.cuboid([-0.025, 0.0, -0.01], [0.025, -NET_MID, 0.01], c);
    let mut p = Prim::default();
    let post = [0.14, 0.26, 0.16, 1.0];
    for s in [-1.0f32, 1.0] {
        p.cuboid([s * POST - 0.04, 0.0, -0.04], [s * POST + 0.04, -NET_POST - 0.03, 0.04], post);
    }
    // the umpire's chair: four legs, a footrest, a seat under her placement, a back on the far side from the court
    let (cx, cy, cz) = (chair[0], chair[1], chair[2]);
    let out = cx.signum();
    let seat = cy;
    let wood = [0.42, 0.30, 0.18, 1.0];
    let frame = [0.20, 0.30, 0.22, 1.0];
    for (dx, dz) in [(-0.3, -0.3), (0.3, -0.3), (-0.3, 0.3), (0.3, 0.3)] {
        p.cuboid([cx + dx - 0.03, 0.0, cz + dz - 0.03], [cx + dx + 0.03, seat, cz + dz + 0.03], frame);
    }
    p.cuboid([cx - 0.35, seat, cz - 0.35], [cx + 0.35, seat - 0.05, cz + 0.35], wood);
    p.cuboid([cx + out * 0.33 - 0.03, seat - 0.05, cz - 0.35], [cx + out * 0.33 + 0.03, seat - 0.65, cz + 0.35], wood);
    for s in [-1.0f32, 1.0] {
        p.cuboid([cx - 0.35, seat - 0.05, cz + s * 0.35 - 0.025], [cx + 0.35, seat - 0.3, cz + s * 0.35 + 0.025], frame);
    }
    let foot = seat * 0.55;
    p.cuboid([cx - out * 0.55, foot, cz - 0.3], [cx - out * 0.3, foot - 0.04, cz + 0.3], wood);
    for k in 1..5 {
        let y = seat * k as f32 / 5.0;
        p.cuboid([cx - out * 0.33 - 0.02, y, cz - 0.3], [cx - out * 0.33 + 0.02, y - 0.03, cz + 0.3], frame);
    }
    let court = d.node(0, json!({"name": "court"}));
    let (court_mat, run_mat) = turf.map_or((grass, grass), |[(g, _), (f, _)]| (g, f));
    for (name, prims) in [("slab", vec![(court_mat, g), (run_mat, f)]), ("lines", vec![(white, l)]), ("net", vec![(net, n)]), ("posts_chair", vec![(grass, p)])] {
        if let Some(m) = d.mesh(name, prims) {
            d.node(court, json!({"name": name, "mesh": m}));
        }
    }
}

pub fn court(root: &Path, survey: &Path, iso: &Path, out: &Path, args: &[String]) -> R<()> {
    let end = args.iter().any(|a| a == "-") && args.iter().any(|a| a == "--end");
    let want: Vec<u32> = args.iter().filter_map(|a| a.parse().ok()).collect();
    let survey: Value = serde_json::from_slice(&read(survey)?).map_err(|e| e.to_string())?;
    let spots = spots(&survey);
    let mut iso = Iso::open(iso).map_err(|e| format!("{}: {e}", iso.display()))?;
    let ssn = root.join("CRS/SSN0");
    for c in 1..=15u32 {
        if !want.is_empty() && !want.contains(&c) {
            continue;
        }
        let Some(cands) = spots.get(&c) else {
            eprintln!("course {c:02}: no spot in the survey");
            continue;
        };
        // the flattest spot whose ground the hole model draws (mini-golf height maps run on past it)
        let mut done = false;
        for spot in cands {
            let spot = Spot { yaw: if end { spot.yaw + 180.0 } else { spot.yaw }, ..*spot };
            match one(&ssn, c, &spot, &mut iso, out) {
                Ok(dir) => {
                    println!("course {c:02} h{:02}: {}", spot.hole, dir.display());
                    done = true;
                    break;
                }
                Err(e) => eprintln!("course {c:02} h{:02} ({}, {}) yaw {}: {e}", spot.hole, spot.x, spot.z, spot.yaw),
            }
        }
        if !done {
            eprintln!("course {c:02}: no spot exported");
        }
    }
    Ok(())
}

/// `fore2gltf chairs <HST iso>`: the umpire chair of each disc court (layout 0–10) as a JSON list, for the
/// exporters written in Python (oob2gltf `court.py`).
pub fn chairs(iso: &Path) -> R<()> {
    let mut iso = Iso::open(iso).map_err(|e| format!("{}: {e}", iso.display()))?;
    let list: Vec<Value> = (1..=HST.len() as u32).map(|n| hst_sim::court::umpire_chair(&mut iso, n).map_or(Value::Null, |c| json!(c))).collect();
    println!("{}", Value::Array(list));
    Ok(())
}

fn one(ssn: &Path, c: u32, spot: &Spot, iso: &mut Iso, out: &Path) -> R<PathBuf> {
    let h = spot.hole;
    let (stem, name) = COURSES[c as usize - 1];
    let hol = ssn.join(format!("HOL{c:02}{h:02}.XB"));
    let grd = ssn.join(format!("GRD{c:02}{h:02}.XB"));
    let cmn = ssn.join(format!("CMN{c:02}.XB"));
    // front nine (and h00) p10, back nine p01, where the course has one
    let nine = if h >= 10 && ssn.join(format!("BG{c:02}1.XB")).is_dir() { 1 } else { 0 };
    let bg = ssn.join(format!("BG{c:02}{nine}.XB"));
    let ix = index(&[hol.clone(), grd.clone(), cmn.clone(), bg.clone()]);
    let entries = layout::entries(&String::from_utf8_lossy(&read(&find(&ix, &format!("entry_c{c:02}.txt")).ok_or("no entry list")?)?));
    let plants = layout::plants(&read(&find(&ix, &format!("plant_c{c:02}_h{h:02}_0.dat")).ok_or("no plant file")?)?).map_err(|e| format!("{e:?}"))?;
    let envir = read(&find(&ix, &format!("envir_c{c:02}.dat")).ok_or("no course envir")?)?;
    let hole_envir = find(&ix, &format!("envir_c{c:02}_h{h:02}.dat")).map(|p| read(&p)).transpose()?;
    let hmp_path = walk(&hol).into_iter().find(|p| p.extension().is_some_and(|e| e.eq_ignore_ascii_case("hmp"))).ok_or("no height map")?;
    let hmp = Hmp::parse(&read(&hmp_path)?)?;

    // the run-off the height map allows, and the layout court closest to it
    let blockers: Vec<(f32, f32, f32)> = plants
        .iter()
        .filter_map(|p| BLOCK.iter().find(|b| b.0 == p.category).map(|b| (p.pos[0], p.pos[2], b.1 * p.scale.abs().clamp(1.0, 4.0))))
        .collect();
    let (ro, range, fits) = runoff(&hmp, spot, &blockers);
    let surface = "grass";
    let (back, side) = (ro[0].min(ro[1]), ro[2].min(ro[3]));
    let lay = (0..HST.len())
        .filter(|&k| HST[k].0 == surface)
        .min_by(|&a, &b| {
            let cost = |k: usize| (back / HST[k].1[0].min(HST[k].1[1])).ln().abs() + (side / HST[k].1[2].min(HST[k].1[3])).ln().abs();
            cost(a).total_cmp(&cost(b))
        })
        .unwrap();
    let chair = hst_sim::court::umpire_chair(iso, lay as u32 + 1).ok_or("the layout court's umpire chair isn't on the disc")?;

    // the hole's ground: its highest point under the slab (and 2 m round it) goes SINK under y = 0. The ground is
    // the height map and the hole model's near-level triangles within GROUND of it (vertices and every 0.5 m: flat
    // fairways are a few big triangles). Whole holes draw blended, so blending says nothing; walls and pieces
    // standing higher (c07's sheets 6 m up) are counted, sunken ones ignored
    let in_hole = |p: &PathBuf, ext: &str| p.parent().is_some_and(|d| d.ends_with("hole")) && p.extension().is_some_and(|e| e.eq_ignore_ascii_case(ext));
    // (the archive's data/ also holds the aim arrow's model)
    let hole_mdl = walk(&grd).into_iter().find(|p| in_hole(p, "mdl")).ok_or("no hole model")?;
    let hole_stem = hole_mdl.file_stem().unwrap().to_string_lossy().to_ascii_lowercase();
    let hole_mtl = walk(&grd).into_iter().find(|p| in_hole(p, "mtl")).ok_or("no hole MTL")?;
    // by path: the hole-end scenery in HOL…/holeend/ has the same stem
    let hole_mti = walk(&grd).into_iter().find(|p| in_hole(p, "mti")).map(|p| read(&p)).transpose()?;
    let ground = mdl::parse(&read(&hole_mdl)?).map_err(|e| format!("{}: {e:?}", hole_mdl.display()))?;
    let ground_mats = mtl::parse(&read(&hole_mtl)?, hole_mti.as_deref()).map_err(|e| format!("{}: {e:?}", hole_mtl.display()))?;
    let v0 = spot.venue(0.0);
    let tex_tris = textured_triangles(&ground);
    let name_of = |s: &Option<Surface>| s.map(|s| format!("{} ({:.1} m, colour {:.2?})", ground_mats.materials[s.material].name, s.metres, s.colour)).unwrap_or("-".into());
    let green = surface_of(&tex_tris, &ground_mats, |x, z| hmp.at(x, z).is_some_and(|h| h.1 == 4));
    let fairway = surface_of(&tex_tris, &ground_mats, |x, z| hmp.at(x, z).is_some_and(|h| h.1 == 1));
    let (x0, x1, z0, z1) = (-(DOUBLES + ro[3]) - 2.0, DOUBLES + ro[2] + 2.0, -(BASE + ro[1]) - 2.0, BASE + ro[0] + 2.0);
    let inside = |q: [f32; 3]| (x0..=x1).contains(&q[0]) && (z0..=z1).contains(&q[2]);
    let under = surface_of(&tex_tris, &ground_mats, |x, z| inside(apply(&v0, [x, 0.0, z])));
    eprintln!("  surfaces: green {}, fairway {}, under the slab {}", name_of(&green), name_of(&fairway), name_of(&under));
    let (mut top, mut low) = (f32::MAX, f32::MIN);
    let (mut above, mut above_n) = (Vec::<[f32; 3]>::new(), 0usize);
    let tris: Vec<[[f32; 3]; 3]> = triangles(&ground).into_iter().map(|t| t.map(|p| apply(&v0, p))).collect();
    let mut grid = Vec::new();
    let (nx, nz) = (((x1 - x0) / 0.5).ceil() as usize, ((z1 - z0) / 0.5).ceil() as usize);
    for i in 0..=nx {
        for k in 0..=nz {
            let (x, z) = (x0 + (x1 - x0) * i as f32 / nx as f32, z0 + (z1 - z0) * k as f32 / nz as f32);
            let (hx, hz) = spot.to_hole(x, z);
            if let Some((y, lie)) = hmp.at(hx, hz).filter(|h| h.1 != 0) {
                let _ = lie;
                (top, low) = (top.min(y), low.max(y));
            }
            grid.push((x, z));
        }
    }
    let height = |t: &[[f32; 3]; 3], x: f32, z: f32| -> Option<f32> {
        let d = (t[1][2] - t[2][2]) * (t[0][0] - t[2][0]) + (t[2][0] - t[1][0]) * (t[0][2] - t[2][2]);
        if d.abs() < 1e-9 {
            return None;
        }
        let l1 = ((t[1][2] - t[2][2]) * (x - t[2][0]) + (t[2][0] - t[1][0]) * (z - t[2][2])) / d;
        let l2 = ((t[2][2] - t[0][2]) * (x - t[2][0]) + (t[0][0] - t[2][0]) * (z - t[2][2])) / d;
        let l3 = 1.0 - l1 - l2;
        (l1 >= -1e-4 && l2 >= -1e-4 && l3 >= -1e-4).then(|| l1 * t[0][1] + l2 * t[1][1] + l3 * t[2][1])
    };
    let hmp_y = |x: f32, z: f32| {
        let (hx, hz) = spot.to_hole(x, z);
        hmp.at(hx, hz).filter(|h| h.1 != 0).map(|h| h.0)
    };
    let (mut mesh_top, mut mesh_low) = (f32::MAX, f32::MIN);
    let mut covered = std::collections::HashSet::new();
    for t in &tris {
        let (lo, hi) = (t.iter().fold([f32::MAX; 3], |a, p| std::array::from_fn(|k| a[k].min(p[k]))), t.iter().fold([f32::MIN; 3], |a, p| std::array::from_fn(|k| a[k].max(p[k]))));
        if hi[0] < x0 || lo[0] > x1 || hi[2] < z0 || lo[2] > z1 {
            continue;
        }
        let e1: [f32; 3] = std::array::from_fn(|k| t[1][k] - t[0][k]);
        let e2: [f32; 3] = std::array::from_fn(|k| t[2][k] - t[0][k]);
        let n = unit_or_down([e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]]);
        if n[1].abs() <= 0.7 {
            above.extend(t.iter().filter(|p| inside(**p)));
            continue;
        }
        let samples = t.iter().filter(|p| inside(**p)).map(|p| (usize::MAX, p[0], p[2], p[1])).chain(
            grid.iter().enumerate().filter(|(_, (x, z))| (lo[0]..=hi[0]).contains(x) && (lo[2]..=hi[2]).contains(z)).filter_map(|(i, &(x, z))| height(t, x, z).map(|y| (i, x, z, y))),
        );
        for (i, x, z, y) in samples {
            covered.insert(i);
            match hmp_y(x, z) {
                Some(h) if (y - h).abs() <= GROUND => (mesh_top, mesh_low) = (mesh_top.min(y), mesh_low.max(y)),
                Some(h) if y < h => above.push([x, y, z]),
                _ => {}
            }
        }
    }
    // the slab's own area (without the 2 m round it) on the drawn ground
    let slab = |&(x, z): &(f32, f32)| (x0 + 2.0..=x1 - 2.0).contains(&x) && (z0 + 2.0..=z1 - 2.0).contains(&z);
    let (n_slab, n_cov) = (grid.iter().filter(|q| slab(q)).count(), grid.iter().enumerate().filter(|(i, q)| slab(q) && covered.contains(i)).count());
    if (n_cov as f32) < 0.95 * n_slab as f32 {
        return Err(format!("off the hole model's ground ({n_cov} of {n_slab} points under the slab drawn)"));
    }
    let hmp_top = top;
    (top, low) = (top.min(mesh_top), low.max(mesh_low));
    above.retain(|p| p[1] < top - SINK);
    above_n += above.len();
    let depth = low - top + SINK + 0.1;
    let venue = spot.venue(top - SINK);

    // court.glb
    let mut d = Doc::new();
    let vn = d.node(0, json!({"name": "fore_spot", "matrix": gl(&venue)}));
    let hole_m0 = d.doc["materials"].as_array().unwrap().len();
    if let Some(m) = d.model("hole", &ground, &ground_mats) {
        d.node(vn, json!({"name": format!("hole_{hole_stem}"), "mesh": m}));
    }
    let mut meshes: HashMap<String, Option<usize>> = HashMap::new();
    let (mut placed, mut missing, mut cleared) = (HashMap::<String, usize>::new(), Vec::new(), 0);
    for (k, p) in plants.iter().enumerate().filter(|(_, p)| (17..=20).contains(&p.category)) {
        let Some(e) = layout::resolve(&entries, p, 0) else {
            missing.push(format!("cat {} index {}", p.category, p.index));
            continue;
        };
        let mesh = match meshes.get(&e.stem) {
            Some(m) => *m,
            None => {
                let m = match load(&ix, &e.stem, &e.stem) {
                    Ok((model, mats)) => d.model(&e.stem, &model, &mats),
                    Err(err) => {
                        missing.push(err);
                        None
                    }
                };
                meshes.insert(e.stem.clone(), m);
                m
            }
        };
        let Some(mesh) = mesh else { continue };
        let (m, post) = hst_sim::world::place(p.category, p.pos, p.yaw, p.code);
        let s = if p.scale > 0.0 { p.scale } else { 1.0 };
        // HST: Transform::from_matrix(m) (rows of `m` are glTF's columns) with the scale
        let m: M4 = if post {
            let r = rot_y(p.yaw);
            std::array::from_fn(|r_| std::array::from_fn(|c_| if c_ == 3 { if r_ < 3 { p.pos[r_] } else { 1.0 } } else { r[r_][c_] }))
        } else {
            std::array::from_fn(|r_| std::array::from_fn(|c_| m[c_][r_]))
        };
        let m = mm(&m, &[[s, 0.0, 0.0, 0.0], [0.0, s, 0.0, 0.0], [0.0, 0.0, s, 0.0], [0.0, 0.0, 0.0, 1.0]]);
        let at = apply(&venue, p.pos);
        let clear = (at[0] * at[0] + at[2] * at[2]).sqrt() < CLEAR_WITHIN;
        cleared += clear as usize;
        d.node(vn, json!({"name": format!("{}_{k}{}", e.stem, if clear { "__clear" } else { "" }), "mesh": mesh, "matrix": gl(&m)}));
        *placed.entry(e.stem.clone()).or_default() += 1;
    }
    // the court in the hole's green, the run-off in its fairway (else what's under the slab: mini-golf c15 has
    // neither green nor fairway lie under its spot's hole, so both are its own turf)
    let run = fairway.or(under);
    let turf = match (green.or(run), run) {
        (Some(g), Some(f)) => Some([(d.tiled("court_green", hole_m0 + g.material), g), (d.tiled("court_fairway", hole_m0 + f.material), f)]),
        _ => None,
    };
    laid(&mut d, ro, depth, chair, turf);
    let slug = format!("fore_c{c:02}_{stem}");
    let dir = out.join(&slug);
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    crate::write(&dir.join("court.glb"), &d.finish())?;

    // sky.glb: the backdrops at the eye, turned as HST turns its own and with the venue
    let mut s = Doc::new();
    let turn: M4 = std::array::from_fn(|r| std::array::from_fn(|c_| if r < 3 && c_ < 3 { venue[r][c_] } else if r == c_ { 1.0 } else { 0.0 }));
    let mut sky_done = false;
    let mut backdrops = Vec::new();
    for e in entries.iter().filter(|e| e.dir == "bg" && season(&e.stem)[0]) {
        let Some(i) = ["_sky", "_clo", "_acc", "_bg"].iter().position(|k| e.stem.contains(k)) else { continue };
        if i == 0 && sky_done {
            continue;
        }
        if i > 0 && !e.stem.ends_with(if nine == 1 { "_p01" } else { "_p10" }) {
            continue;
        }
        let Ok((model, mats)) = load(&ix, &e.stem, &e.stem) else { continue };
        sky_done |= i == 0;
        let (yaw, lift) = backdrop(&envir, hole_envir.as_deref(), i);
        let mut m = mm(&turn, &rot_y(yaw));
        m[1][3] = lift;
        if let Some(mesh) = s.model(&e.stem, &model, &mats) {
            s.node(0, json!({"name": e.stem, "mesh": mesh, "matrix": gl(&m)}));
            backdrops.push(format!("{} (turn {yaw:.3}, lift {lift})", e.stem));
        }
    }
    crate::write(&dir.join("sky.glb"), &s.finish())?;

    let r = HST[lay].1;
    let mut todo = vec![
        "the court is laid by the exporter (slab in the hole's own green texture over the court, its fairway's round it; lines at HST's judging edges, net, posts, umpire chair): Fore! has no tennis court".to_string(),
        "light: none in the manifest; the hole is lit as the layout court lights its own models (Fore!'s envir isn't mapped to the manifest light)".to_string(),
        "Fore!'s drifting clouds (cmn cloud models), creatures, galleries, the pin flag and the hole-end scenery are left out".to_string(),
        "sound: the layout court's (Fore!'s course music isn't exported)".to_string(),
    ];
    if !missing.is_empty() {
        missing.sort();
        missing.dedup();
        todo.push(format!("plant records without a model: {}", missing.join(", ")));
    }
    if above_n > 0 {
        todo.push(format!("{above_n} vertices of the hole model's walls/blended pieces stand above the slab round the court"));
    }
    if !fits {
        todo.push(if range.is_nan() {
            "the survey's footprint didn't pass this exporter's own check (0.5 m grid) and no smaller run-off did: run-off left at the footprint's, ground not checked".into()
        } else {
            "the survey's footprint didn't pass this exporter's own check (0.5 m grid, its window sits up to a cell off): run-off grown from 3 m / 2 m instead".into()
        });
    }
    let man = json!({
        "standard": 1, "kind": "court", "id": slug, "name": format!("{name} Courts"),
        "source": format!("Hot Shots Golf Fore! (PS2) {name} (course{c:02}) hole {h:02}, spring"),
        "layout": lay,
        "layout_why": format!("grass: a court laid on the golf course's lawn; of HST's grass courts the closest run-off: {back:.1} m behind the baselines and {side:.1} m beside the sidelines of flat ground here (height map, ≤ {FLAT} m), {} / {} m at {}",
            r[0].min(r[1]), r[2].min(r[3]), HST_NAMES[lay]),
        "surface": surface, "time": "day", "indoor": false,
        "todo": todo,
    });
    std::fs::write(dir.join("mod.json"), serde_json::to_string_pretty(&man).unwrap()).map_err(|e| e.to_string())?;
    let mut placed: Vec<_> = placed.into_iter().collect();
    placed.sort();
    println!(
        "  spot ({}, {}) yaw {} range {}; run-off +z {} -z {} +x {} -x {} (slab range {range:.2}); ground top {top:.3} (height map {hmp_top:.3}, model {mesh_top:.3}..{mesh_low:.3}) depth {depth:.2}; {above_n} non-ground vertices above the slab; layout {lay} {}; chair {chair:?}",
        spot.x, spot.z, spot.yaw, spot.range, ro[0], ro[1], ro[2], ro[3], HST_NAMES[lay]
    );
    println!("  placed {} ({cleared} __clear): {placed:?}", placed.iter().map(|p| p.1).sum::<usize>());
    println!("  backdrops: {}", backdrops.join(", "));
    Ok(dir)
}
