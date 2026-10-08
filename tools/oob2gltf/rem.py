"""Hot Shots Golf: Out of Bounds (PS3) `.rem` model parser. Big-endian throughout. See notes/oob.md."""
import re
import struct

import numpy as np


class Rem:
    def __init__(self, data: bytes):
        self.d = d = data
        self.textures = []  # DDS file names
        self.texobjs = []  # (name, texture index, kind) kind: 0 colour, 1 spec(_s), 2 occl(_o)?
        self.materials = []  # dicts
        o = 0x24
        for _ in range(self.u32(0x20)):
            s, o = self.pstr(o)
            self.textures.append(s)
            o += 8
        n = self.u32(o)
        o += 4
        for _ in range(n):
            s, o = self.pstr(o)
            v = struct.unpack('>8i', d[o:o + 32])
            o += 32
            self.texobjs.append((s, v[1], v[4]))
        n = self.u32(o)
        o += 4
        for _ in range(n):
            s, o = self.pstr(o)
            w = d[o:o + 168]
            o += 168
            f = struct.unpack('>42f', w)
            i = struct.unpack('>42i', w)
            self.materials.append(dict(name=s, colors=[f[0:4], f[4:8], f[8:12], f[12:16]], power=f[16],
                                       raw=i, slots=list(i[36:42]), nslots=i[35]))
        self.mesh_start = o
        self.nodes, self.node_start = self._find_nodes()
        self.meshes = self._find_meshes(self.mesh_start, self.node_start)
        self._find_morphs()

    def u32(self, o):
        return struct.unpack('>I', self.d[o:o + 4])[0]

    def pstr(self, o):
        n = self.u32(o)
        return self.d[o + 4:o + 4 + n].decode('latin1'), o + 4 + n

    # ---- skeleton -------------------------------------------------------------------------------------------
    def _parse_nodes(self, o):
        d = self.d
        out = []
        pending = 1  # nodes still owed by the pre-order child counts
        while pending > 0 and o + 4 < len(d):
            n = self.u32(o)
            if not 1 <= n < 256:
                break
            s = d[o + 4:o + 4 + n]
            if not re.fullmatch(rb'[\x20-\x7e]+', s):
                break
            p = o + 4 + n
            if p + 212 > len(d):
                break
            m = [np.array(struct.unpack('>16f', d[p + 64 * j:p + 64 * j + 64])).reshape(4, 4) for j in range(3)]
            t = struct.unpack('>5i', d[p + 192:p + 212])
            out.append(dict(name=s.decode(), world=m[0], inv=m[1], local=m[2], index=t[0], flag=t[1], nchild=t[4]))
            pending += t[4] - 1
            o = p + 212
        return out, o

    def _find_nodes(self):
        k = self.d.find(b'\x00\x00\x00\x08SMF2Root')
        if k < 0:
            raise ValueError('no SMF2Root')
        nodes, _ = self._parse_nodes(k)
        # parents from pre-order child counts
        stack = []
        for i, n in enumerate(nodes):
            while stack and stack[-1][1] == 0:
                stack.pop()
            n['parent'] = -1
            if stack:
                n['parent'] = stack[-1][0]
                stack[-1][1] -= 1
            stack.append([i, n['nchild']])
        return nodes, k

    # ---- face morph targets ---------------------------------------------------------------------------------
    def _targets(self, m):
        """Morph block right after a mesh's last stream: u32 nTargets; per target u32 n, and if n > 0: u32 target
        ordinal, u32 vertex_index[n] (sorted), f32x3 position delta[n], f32x3 normal delta[n]. None if absent."""
        d, o, nv = self.d, m['end'], len(m['pos'])
        if o + 8 > self.node_start:
            return None
        nt = self.u32(o)
        if not 1 <= nt < 64:
            return None
        o += 4
        out = []
        for t in range(nt):
            n = self.u32(o)
            if n == 0:
                out.append(None)
                o += 4
                continue
            if n > nv or self.u32(o + 4) != t:
                return None
            idx = np.frombuffer(d[o + 8:o + 8 + 4 * n], '>u4').astype(np.int64)
            o += 8 + 4 * n
            if idx.max() >= nv or np.any(np.diff(idx) <= 0):
                return None
            dp = np.frombuffer(d[o:o + 12 * n], '>f4').reshape(n, 3).astype(np.float32)
            dn = np.frombuffer(d[o + 12 * n:o + 24 * n], '>f4').reshape(n, 3).astype(np.float32)
            o += 24 * n
            out.append((idx, dp, dn))
        return out, o

    def _names(self, o, nt):
        if self.u32(o) != nt:
            return None
        o += 4
        out = []
        for _ in range(nt):
            n = self.u32(o)
            s = self.d[o + 4:o + 4 + n]
            if n > 64 or not re.fullmatch(rb'[\x20-\x7e]*', s):
                return None
            out.append(s.decode())
            o += 4 + n
        return out

    def _find_morphs(self):
        """Every mesh of the morph group (face, teeth, tongue, ...) carries its own target block; the shared target
        name table (u32 nTargets; str name[nTargets]) follows the last block of the group."""
        self.target_names = None
        group = []
        for m in self.meshes:
            r = self._targets(m)
            if r is None:
                continue
            m['targets'], o = r
            group.append(m)
            names = self._names(o, len(r[0]))
            if names is not None:
                if any(len(g['targets']) != len(names) for g in group):
                    raise ValueError('morph group with differing target counts')
                self.target_names = names
                group = []
        if group:
            raise ValueError('morph targets without a name table')

    # ---- meshes ---------------------------------------------------------------------------------------------
    def _chain(self, o, n):
        """Vertex streams: repeated (u32 count == n, u32 components, data). Element size is inferred from where the
        next header lands (float32 or u8); the final stream is float32."""
        out = []
        d = self.d
        while self.u32(o) == n:
            k = self.u32(o + 4)
            if not 1 <= k <= 8:
                break
            for es, ty in ((4, '>f4'), (1, 'u1')):
                p = o + 8 + n * k * es
                if p + 8 <= len(d) and self.u32(p) == n and 1 <= self.u32(p + 4) <= 8:
                    out.append(np.frombuffer(d[o + 8:p], ty).reshape(n, k))
                    o = p
                    break
            else:
                p = o + 8 + n * k * 4
                out.append(np.frombuffer(d[o + 8:p], '>f4').reshape(n, k))
                return out, p
        return out, o

    def _find_meshes(self, lo, end):
        """Locates mesh blocks by their signature: u32 index count, u16 strip indices, then a position and a normal
        stream (n, 3) back to back. The 15 words before the index count are the mesh header."""
        d = self.d
        out = []
        o = lo
        while o < end - 8:
            n = self.u32(o)
            if 3 <= n < 100000 and self.u32(o + 4) == 3:
                p = o + 8 + n * 12
                if p + 8 < end and self.u32(p) == n and self.u32(p + 4) == 3:
                    q = None
                    for c in range(3, 400000):
                        qq = o - 4 - 2 * c
                        if qq < lo:
                            break
                        if self.u32(qq) == c:
                            q = qq
                            break
                    if q is not None:
                        hdr = struct.unpack('>15i', d[q - 64:q - 4])
                        mat, has_tan, nw = hdr[0], hdr[1], hdr[2]
                        if 0 <= mat < len(self.materials) and has_tan in (0, 1) and 1 <= nw <= 4:
                            m = self._mesh(q, o, n, hdr)
                            if m is not None:
                                out.append(m)
                                o = m['end']
                                continue
            o += 1
        return out

    def _mesh(self, q, o, n, hdr):
        c = self.u32(q)
        idx = np.frombuffer(self.d[q + 4:q + 4 + 2 * c], '>u2').astype(np.int64)
        st, end = self._chain(o, n)
        mat, has_tan, nw = hdr[0], hdr[1], hdr[2]
        need = 3 + 2 * has_tan + 2
        if len(st) < need + 1:
            return None
        pos, nrm, col = st[0], st[1], st[2]
        bidx, bw = st[-2], st[-1]
        if bidx.dtype != np.uint8 or bidx.shape[1] != nw or bw.shape[1] != nw:
            return None
        tan = bit = None
        if has_tan:
            tan, bit = st[-4], st[-3]
            uvs = st[3:-4]
        else:
            uvs = st[3:-2]
        if not uvs:
            return None
        good = idx[idx < 0xfffe]
        if len(good) and good.max() >= n:
            return None
        return dict(offset=q, header=hdr, material=mat, indices=idx, pos=pos.astype(np.float32),
                    normal=nrm.astype(np.float32), color=col, uvs=[u.astype(np.float32) for u in uvs],
                    tangent=None if tan is None else tan.astype(np.float32),
                    binormal=None if bit is None else bit.astype(np.float32), joints=bidx, weights=bw.astype(np.float32),
                    end=end)


def strips_to_tris(idx):
    """Triangle strips separated by 0xfffe (0xffff also treated as restart). Degenerates are dropped."""
    tris = []
    cur = []
    for i in list(idx) + [0xfffe]:
        if i >= 0xfffe:
            for j in range(2, len(cur)):
                a, b, c = cur[j - 2], cur[j - 1], cur[j]
                if a == b or b == c or a == c:
                    continue
                tris.append((a, b, c) if j % 2 == 0 else (b, a, c))
            cur = []
        else:
            cur.append(int(i))
    return np.array(tris, dtype=np.uint32).reshape(-1, 3)
