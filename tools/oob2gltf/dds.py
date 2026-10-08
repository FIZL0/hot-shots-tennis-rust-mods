"""DDS -> PIL image. OOB uses DXT1/3/5 (Pillow) and uncompressed 8-bit alpha-only (`_o`/`_s` masks), which Pillow
rejects; those are read by hand into an 'L' image (top mip only)."""
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
    raise ValueError(f'unsupported DDS pixel format flags={flags} bits={bits}')
