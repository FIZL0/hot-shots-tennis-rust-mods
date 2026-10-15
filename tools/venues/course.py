"""Readers shared by the three golf engines (Fore! PS2 little-endian, Open Tee 2 PSP little-endian, Out of Bounds
PS3 big-endian): a hole's height/lie map (`*_hNN*.HMP`) and its placements (`plant_cNN_hNN_N.dat`).

HMP: `f32 x0, f32 z0, u32 nx, u32 nz`, then nx*nz f32 heights (game space, Y down) and nx*nz u8 lies, both stored
x-major (row = x, column = z), cells CELL m square from (x0, z0). Lie 0 = outside the hole's playable area.
Plant: HST's 0x40-byte records (open-tennis `hst_data::layout`): i16 index, u8 category-0x11, u8 sub,
f32 pos[3], f32 extra[4], f32 yaw (0x20), f32 scale (0x24), u8 code[4], ..., f32 radius (0x30).
"""
import struct

import numpy as np

CELL = 1.3


class Hmp:
    def __init__(self, data, big=False):
        e = ">" if big else "<"
        self.x0, self.z0, self.nx, self.nz = struct.unpack(e + "ffII", data[:16])
        n = self.nx * self.nz
        self.y = np.frombuffer(data[16:16 + 4 * n], e + "f4").reshape(self.nx, self.nz).astype(np.float32)
        self.lie = np.frombuffer(data[16 + 4 * n:16 + 5 * n], np.uint8).reshape(self.nx, self.nz)

    def at(self, x, z):
        """(height, lie) of the cell under game-space (x, z), or (nan, 0) off the map."""
        r, c = int((x - self.x0) // CELL), int((z - self.z0) // CELL)
        if 0 <= r < self.nx and 0 <= c < self.nz:
            return float(self.y[r, c]), int(self.lie[r, c])
        return float("nan"), 0


def plants(data, big=False):
    """[(category, index, x, y, z, yaw, scale)] with HST's category numbers (17 tree, 18 prop, 19 structure, ...)."""
    e = ">" if big else "<"
    out = []
    for o in range(0, len(data) - 0x3F, 0x40):
        r = data[o:o + 0x40]
        idx, cat = struct.unpack(e + "h", r[:2])[0], (r[2] + 0x11) & 0xFF
        x, y, z = struct.unpack(e + "3f", r[4:16])
        yaw, scale = struct.unpack(e + "2f", r[0x20:0x28])
        out.append((cat, idx, x, y, z, yaw, scale))
    return out
