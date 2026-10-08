"""Minimal glTF 2.0 binary writer."""
import json
import struct

import numpy as np

FLOAT, UBYTE, USHORT, UINT = 5126, 5121, 5123, 5125
_CT = {np.dtype('float32'): FLOAT, np.dtype('uint8'): UBYTE, np.dtype('uint16'): USHORT, np.dtype('uint32'): UINT}
_TY = {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4', 16: 'MAT4'}


class Builder:
    def __init__(self):
        self.g = {'asset': {'version': '2.0', 'generator': 'HST-MODS oob2gltf'}, 'scene': 0, 'scenes': [{'nodes': []}],
                  'nodes': [], 'buffers': [], 'bufferViews': [], 'accessors': []}
        self.bin = bytearray()

    def _view(self, data: bytes, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        v = {'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data)}
        if target:
            v['target'] = target
        self.bin += data
        self.g['bufferViews'].append(v)
        return len(self.g['bufferViews']) - 1

    def accessor(self, arr, target=None, minmax=False, normalized=False):
        arr = np.ascontiguousarray(arr)
        ncomp = 1 if arr.ndim == 1 else arr.shape[1]
        a = {'bufferView': self._view(arr.tobytes(), target), 'componentType': _CT[arr.dtype], 'count': len(arr),
             'type': _TY[ncomp]}
        if normalized:
            a['normalized'] = True
        if minmax:
            r = arr.reshape(len(arr), -1)
            a['min'] = [float(x) for x in r.min(0)]
            a['max'] = [float(x) for x in r.max(0)]
        self.g['accessors'].append(a)
        return len(self.g['accessors']) - 1

    def sparse_vec3(self, count, idx, vals):
        """VEC3 float accessor of `count` zeros with `vals` at `idx` (glTF sparse, no base bufferView); all zeros
        when idx is empty. Carries min/max (required for morph POSITION)."""
        a = {'componentType': FLOAT, 'count': int(count), 'type': 'VEC3'}
        if len(idx):
            idx = np.asarray(idx)
            it = np.uint16 if count < 65536 else np.uint32
            a['sparse'] = {'count': len(idx),
                           'indices': {'bufferView': self._view(idx.astype(it).tobytes()), 'componentType': _CT[np.dtype(it)]},
                           'values': {'bufferView': self._view(np.ascontiguousarray(vals, np.float32).tobytes())}}
        allv = np.asarray(vals, np.float32).reshape(-1, 3)
        if len(idx) < count:  # untouched elements are 0
            allv = np.concatenate([allv, np.zeros((1, 3), np.float32)])
        a['min'] = [float(x) for x in allv.min(0)]
        a['max'] = [float(x) for x in allv.max(0)]
        self.g['accessors'].append(a)
        return len(self.g['accessors']) - 1

    def image(self, png: bytes, name):
        self.g.setdefault('images', []).append({'bufferView': self._view(png), 'mimeType': 'image/png', 'name': name})
        self.g.setdefault('samplers', [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497}])
        self.g.setdefault('textures', []).append({'source': len(self.g['images']) - 1, 'sampler': 0})
        return len(self.g['textures']) - 1

    def add(self, key, obj):
        self.g.setdefault(key, []).append(obj)
        return len(self.g[key]) - 1

    def write(self, path):
        while len(self.bin) % 4:
            self.bin.append(0)
        self.g['buffers'] = [{'byteLength': len(self.bin)}]
        for k in [k for k, v in self.g.items() if v == []]:
            del self.g[k]
        js = json.dumps(self.g, separators=(',', ':')).encode()
        js += b' ' * (-len(js) % 4)
        out = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(self.bin))
        out += struct.pack('<II', len(js), 0x4E4F534A) + js
        out += struct.pack('<II', len(self.bin), 0x004E4942) + bytes(self.bin)
        with open(path, 'wb') as f:
            f.write(out)
