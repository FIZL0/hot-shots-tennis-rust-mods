"""DDS -> PIL image. OOB uses DXT1/3/5 (Pillow) and uncompressed 8-bit alpha-only (`_o`/`_s` masks), which Pillow
rejects; those are read by hand into an 'L' image (top mip only), as are the uncompressed RGB(A) maps of the course
models."""
import io
import struct

from PIL import Image


def load(data: bytes) -> Image.Image:
    h, w = struct.unpack('<II', data[12:20])
    flags, fourcc, bits = struct.unpack('<I4sI', data[80:92])
    if flags & 0x4:  # FOURCC
        return Image.open(io.BytesIO(data)).convert('RGBA')
    if flags == 2 and bits == 8:  # DDPF_ALPHA
        return Image.frombytes('L', (w, h), data[128:128 + w * h])
    if flags & 0x40 and bits in (24, 32):  # DDPF_RGB (+ALPHAPIXELS): uncompressed, by the channel masks
        masks = struct.unpack('<4I', data[92:108])
        n = bits // 8
        px = data[128:128 + w * h * n]
        import numpy as np
        a = np.frombuffer(px, np.uint8).reshape(h, w, n).astype(np.uint32)
        v = sum(a[:, :, k] << (8 * k) for k in range(n))
        ch = []
        for m in masks:
            if m == 0:
                ch.append(np.full((h, w), 255, np.uint8))
                continue
            sh = (m & -m).bit_length() - 1
            ch.append(((v & m) >> sh).astype(np.uint8))
        if not flags & 0x1:  # no alpha
            ch[3] = np.full((h, w), 255, np.uint8)
        return Image.fromarray(np.dstack(ch), 'RGBA')
    raise ValueError(f'unsupported DDS pixel format flags={flags} bits={bits}')
