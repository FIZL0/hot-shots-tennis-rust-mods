"""GIM (PSP "MIG.00.1PSP") image decoder -> RGBA numpy array / PNG.

Generic: handles RGBA5650/5551/4444/8888 direct colour, INDEX4/8/16/32 with a CLUT block,
swizzled ("PSPImage" order 1) or linear pixel order. DXT formats are not used by the Clap Hanz
titles seen so far and raise NotImplementedError.

Usage: python3 gim.py in.gim out.png
"""
import struct
import sys

import numpy as np

MAGIC = b"MIG.00.1PSP\0"
BPP = {0: 16, 1: 16, 2: 16, 3: 32, 4: 4, 5: 8, 6: 16, 7: 32}


def _blocks(d, off, end, out):
    """Walk the block tree. Block = u16 id, u16 ?, u32 size (incl. children), u32 child_off, u32 data_off."""
    while off + 16 <= end:
        bid, _, size, child, data = struct.unpack_from("<HHIII", d, off)
        if size == 0:
            break
        out.append((bid, off, size, data))
        if bid in (2, 3):  # root / picture: contain child blocks
            _blocks(d, off + child, off + size, out)
        off += size
    return out


def _image_header(d, off):
    # 0x00 u16 hdr_size, u16 ref, u16 format, u16 order, u16 w, u16 h, u16 bpp_align, u16 pitch_align,
    # 0x10 u16 height_align, u16 dim, u32 ?, u32 index_start, 0x1c u32 pixels_start, u32 pixels_end,
    # u32 plane_mask, u16 level_type, u16 level_count, u16 frame_type, u16 frame_count, then level offsets.
    (hs, _ref, fmt, order, w, h, _ba, pitch_align, height_align) = struct.unpack_from("<9H", d, off)
    pix_start = struct.unpack_from("<I", d, off + 0x1C)[0]
    return dict(fmt=fmt, order=order, w=w, h=h, pitch_align=pitch_align or 16,
                height_align=height_align or 1, pix=off + pix_start)


def _unswizzle(buf, rowbytes, rows):
    """PSP swizzle: 16-byte x 8-row tiles, tiles laid out row-major."""
    rows8 = (rows + 7) // 8 * 8
    a = np.frombuffer(buf[: rowbytes * rows8].ljust(rowbytes * rows8, b"\0"), np.uint8)
    tiles_x = rowbytes // 16
    a = a.reshape(rows8 // 8, tiles_x, 8, 16).transpose(0, 2, 1, 3).reshape(rows8, rowbytes)
    return a[:rows]


def _colors(raw, fmt):
    """raw: uint8 array (n*bytes) -> (n,4) uint8 RGBA."""
    if fmt == 3:
        return raw.reshape(-1, 4).copy()
    v = raw.view("<u2").astype(np.uint32)
    if fmt == 0:  # 5650
        r, g, b, a = v & 31, (v >> 5) & 63, (v >> 11) & 31, np.full_like(v, 255)
        return np.stack([r * 255 // 31, g * 255 // 63, b * 255 // 31, a], -1).astype(np.uint8)
    if fmt == 1:  # 5551
        r, g, b, a = v & 31, (v >> 5) & 31, (v >> 10) & 31, (v >> 15) & 1
        return np.stack([r * 255 // 31, g * 255 // 31, b * 255 // 31, a * 255], -1).astype(np.uint8)
    if fmt == 2:  # 4444
        r, g, b, a = v & 15, (v >> 4) & 15, (v >> 8) & 15, (v >> 12) & 15
        return (np.stack([r, g, b, a], -1) * 17).astype(np.uint8)
    raise NotImplementedError(f"colour format {fmt}")


def _pixels(d, hdr):
    fmt, w, h = hdr["fmt"], hdr["w"], hdr["h"]
    if fmt not in BPP:
        raise NotImplementedError(f"GIM format {fmt}")
    bpp = BPP[fmt]
    pa = hdr["pitch_align"]
    rowbytes = (w * bpp + 7) // 8
    rowbytes = (rowbytes + pa - 1) // pa * pa
    if hdr["order"] == 1:
        rowbytes = (rowbytes + 15) // 16 * 16
        rows8 = (h + 7) // 8 * 8
        raw = _unswizzle(d[hdr["pix"]: hdr["pix"] + rowbytes * rows8], rowbytes, h)
    else:
        raw = np.frombuffer(d[hdr["pix"]: hdr["pix"] + rowbytes * h].ljust(rowbytes * h, b"\0"),
                            np.uint8).reshape(h, rowbytes)
    if bpp == 4:
        lo, hi = raw & 15, raw >> 4
        idx = np.stack([lo, hi], -1).reshape(h, -1)[:, :w]
        return idx.astype(np.uint32), True
    raw = raw[:, : w * bpp // 8]
    if fmt in (4, 5, 6, 7):
        dt = {8: np.uint8, 16: "<u2", 32: "<u4"}[bpp]
        return np.ascontiguousarray(raw).view(dt).astype(np.uint32), True
    return _colors(np.ascontiguousarray(raw).reshape(-1), fmt).reshape(h, w, 4), False


def decode(d):
    """bytes -> RGBA uint8 array (h, w, 4) of the first image (level 0, frame 0)."""
    if d[:12] != MAGIC:
        raise ValueError("not a GIM")
    blocks = _blocks(d, 16, len(d), [])
    img = next(b for b in blocks if b[0] == 4)
    hdr = _image_header(d, img[1] + img[3])
    px, indexed = _pixels(d, hdr)
    if not indexed:
        return px
    pal = next(b for b in blocks if b[0] == 5)
    ph = _image_header(d, pal[1] + pal[3])
    n = ph["w"] * ph["h"]
    psize = BPP[ph["fmt"]] // 8
    clut = _colors(np.frombuffer(d[ph["pix"]: ph["pix"] + n * psize], np.uint8), ph["fmt"])
    return clut[np.minimum(px, n - 1)]


def to_png(src, dst):
    from PIL import Image
    Image.fromarray(decode(open(src, "rb").read()), "RGBA").save(dst)


if __name__ == "__main__":
    to_png(sys.argv[1], sys.argv[2])
