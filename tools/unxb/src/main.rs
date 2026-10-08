//! unxb <in_dir> <out_dir> — unpack every `xe\0\x01` archive (.xb, .xb0..3) under in_dir into out_dir,
//! mirroring the tree (archive `a/b.xb` → `out/a/b.xb/<entry>`). Endianness is detected per archive (PS2/PSP LE,
//! PS3 BE); decoders are HST-Remastered's `hst-data/src/xb.rs` with the word reads made endian-aware.
use std::path::{Path, PathBuf};

type R<T> = Result<T, String>;

#[derive(Clone, Copy)]
struct E(bool); // big-endian?
impl E {
    fn u32(self, d: &[u8], o: usize) -> R<u32> {
        let b: [u8; 4] = d.get(o..o + 4).ok_or(format!("read past end at {o:#x}"))?.try_into().unwrap();
        Ok(if self.0 { u32::from_be_bytes(b) } else { u32::from_le_bytes(b) })
    }
}

fn block(e: E, d: &[u8], at: usize, dec: fn(E, &[u8], usize) -> R<Vec<u8>>) -> R<Vec<u8>> {
    let size = e.u32(d, at)? as usize;
    let packed = e.u32(d, at + 4)?;
    let src = d.get(at + 8..).ok_or("block out of range")?;
    if packed == 0 {
        return src.get(..size).map(<[u8]>::to_vec).ok_or("stored block truncated".into());
    }
    dec(e, src, size)
}

fn lz(_: E, src: &[u8], size: usize) -> R<Vec<u8>> {
    let mut out = Vec::with_capacity(size);
    let mut s = 0;
    let b = |i: usize| src.get(i).copied().map(u32::from).ok_or("lz input truncated".to_string());
    while out.len() < size {
        let c = b(s)?;
        s += 1;
        let (len, dist) = if c & 3 == 0 {
            let n = (c >> 2) as usize + 1;
            out.extend_from_slice(src.get(s..s + n).ok_or("lz literal truncated")?);
            s += n;
            continue;
        } else if c & 1 == 1 {
            let v = c | b(s)? << 8;
            s += 1;
            ((v >> 1 & 7) + 3, v >> 4)
        } else {
            let v = c | b(s)? << 8 | b(s + 1)? << 16;
            s += 2;
            ((v >> 2 & 0x3ff) + 3, v >> 12)
        };
        let start = out.len().checked_sub(dist as usize).ok_or(format!("lz distance {dist} before start"))?;
        for i in 0..len as usize {
            out.push(out[start + i]);
        }
    }
    out.truncate(size);
    Ok(out)
}

fn huffman(e: E, src: &[u8], size: usize) -> R<Vec<u8>> {
    let mut table = [(0xffu8, 0u8); 1024];
    let mut p = 0;
    let rd = |p: &mut usize| -> R<u8> {
        let v = *src.get(*p).ok_or("huffman table truncated")?;
        *p += 1;
        Ok(v)
    };
    let max_len = rd(&mut p)? as u32;
    let mut code = 0u32;
    for len in 1..=max_len {
        for _ in 0..rd(&mut p)? {
            let sym = rd(&mut p)?;
            let mut i = (code & ((1 << len) - 1)).reverse_bits() >> (32 - len);
            while i < 1024 {
                table[i as usize] = (len as u8, sym);
                i += 1 << len;
            }
            if len < 11 {
                code += 1;
            }
        }
        code <<= 1;
    }
    p += p & 1;
    let mut half = || {
        let v = src.get(p..p + 2).map_or(0, |v| if e.0 { u16::from_be_bytes([v[0], v[1]]) } else { u16::from_le_bytes([v[0], v[1]]) } as u32);
        p += 2;
        v
    };
    let (mut bits, mut n) = (0u32, 0u32);
    let mut out = Vec::with_capacity(size);
    while out.len() < size {
        if n < 16 {
            bits |= half() << n;
            n += 16;
        }
        let (len, sym) = table[(bits & 0x3ff) as usize];
        if len < 11 {
            out.push(sym);
            bits >>= len;
            n -= len as u32;
        } else {
            bits >>= 10;
            n -= 10;
            if n < 16 {
                bits |= half() << n;
                n += 16;
            }
            out.push(bits as u8);
            bits >>= 8;
            n -= 8;
        }
    }
    Ok(out)
}

fn unpack(data: &[u8], dst: &Path) -> R<usize> {
    if data.get(..4) != Some(b"xe\0\x01") {
        return Err("not an xe archive".into());
    }
    let le = u32::from_le_bytes(data[4..8].try_into().unwrap());
    let e = E(le > 0xffff); // counts are small; a huge LE count means the header is BE
    let count = e.u32(data, 4)? as usize;
    let names = block(e, data, 8 + count * 8, lz)?;
    let mut p = 0;
    for i in 0..count {
        let len = *names.get(p).ok_or("name list truncated")? as usize;
        let name = String::from_utf8_lossy(names.get(p + 2..p + 2 + len).ok_or("name truncated")?).into_owned();
        p += len + 3;
        let size = e.u32(data, 8 + i * 8)? as usize;
        let w = e.u32(data, 12 + i * 8)?;
        let off = (w & 0x0fff_ffff) as usize * 4;
        let bytes = match w >> 28 {
            3 => data.get(off..off + size).ok_or("raw entry out of range")?.to_vec(),
            2 => block(e, data, off, lz)?,
            1 => block(e, data, off, huffman)?,
            0 => block(e, &block(e, data, off, huffman)?, 0, lz)?,
            k => return Err(format!("{name}: unknown kind {k}")),
        };
        if bytes.len() != size {
            return Err(format!("{name}: decoded {} bytes, expected {size}", bytes.len()));
        }
        // names look like `..\\data\\x.MDL`; keep only normal components so nothing escapes dst
        let rel: PathBuf = name.split(['\\', '/']).filter(|c| !matches!(*c, "" | "." | "..")).collect();
        let out = dst.join(rel);
        std::fs::create_dir_all(out.parent().unwrap()).map_err(|x| x.to_string())?;
        std::fs::write(out, bytes).map_err(|x| x.to_string())?;
    }
    Ok(count)
}

fn walk(dir: &Path, files: &mut Vec<PathBuf>) {
    for ent in std::fs::read_dir(dir).into_iter().flatten().flatten() {
        let p = ent.path();
        if p.is_dir() {
            walk(&p, files)
        } else if p.extension().is_some_and(|x| x.to_string_lossy().to_lowercase().starts_with("xb")) {
            files.push(p)
        }
    }
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let (src, out) = (Path::new(&a[1]), Path::new(&a[2]));
    let mut files = vec![];
    walk(src, &mut files);
    let (mut ok, mut bad, mut n) = (0, 0, 0);
    for f in &files {
        let data = std::fs::read(f).unwrap();
        match unpack(&data, &out.join(f.strip_prefix(src).unwrap())) {
            Ok(c) => { ok += 1; n += c }
            Err(e) => { bad += 1; println!("FAIL {}: {e}", f.display()) }
        }
    }
    println!("{} archives: {ok} ok ({n} entries), {bad} failed", files.len());
}
