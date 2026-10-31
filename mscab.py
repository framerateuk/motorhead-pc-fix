#!/usr/bin/env python3
"""Read a Microsoft cabinet (MSZIP or stored), also when it sits inside a self-extracting .exe
such as Motorhead's patch 3.0 (motorp30.exe / mhp30.exe).

  python3 mscab.py FILE              list
  python3 mscab.py FILE OUT          extract everything into OUT
"""
import os, struct, sys, zlib

STORED, MSZIP = 0, 1


class Cabinet:
    def __init__(self, data):
        o = data.find(b'MSCF')
        while o >= 0:                                     # the cabinet whose size runs to the end
            if struct.unpack_from('<I', data, o + 8)[0] == len(data) - o: break
            o = data.find(b'MSCF', o + 1)
        if o < 0: raise ValueError('no cabinet found')
        d = self.d = data[o:]
        coff_files, = struct.unpack_from('<I', d, 16)
        nfolders, nfiles, flags = struct.unpack_from('<HHH', d, 26)
        p, fres = 36, 0
        if flags & 4:                                     # reserved areas
            hres, fres, _ = struct.unpack_from('<HBB', d, 36); p = 40 + hres
        self.folders = []
        for _ in range(nfolders):
            self.folders.append(struct.unpack_from('<IHH', d, p)); p += 8 + fres
        self.files, p = [], coff_files
        for _ in range(nfiles):
            size, off, folder = struct.unpack_from('<IIH', d, p)
            end = d.index(b'\0', p + 16)
            self.files.append((d[p + 16:end].decode('latin-1').replace('\\', '/').lstrip('/'), size, off, folder))
            p = end + 1
        self._cache = {}

    def _folder(self, i):
        if i not in self._cache:
            start, nblocks, kind = self.folders[i]
            out, p = bytearray(), start
            for _ in range(nblocks):
                cb, = struct.unpack_from('<H', self.d, p + 4); block = self.d[p + 8:p + 8 + cb]; p += 8 + cb
                if kind & 0x0f == STORED: out += block
                elif kind & 0x0f == MSZIP:
                    if block[:2] != b'CK': raise ValueError('bad MSZIP block')
                    z = zlib.decompressobj(-15, zdict=bytes(out[-32768:]))   # window runs across blocks
                    out += z.decompress(block[2:])
                else: raise ValueError(f'compression type {kind} not supported')
            self._cache[i] = bytes(out)
        return self._cache[i]

    def read(self, name):
        for n, size, off, folder in self.files:
            if n.lower() == name.lower():
                return self._folder(folder)[off:off + size]
        raise KeyError(name)


if __name__ == '__main__':
    c = Cabinet(open(sys.argv[1], 'rb').read())
    for n, size, _, _ in c.files:
        if len(sys.argv) > 2:
            dst = os.path.join(sys.argv[2], *n.split('/')); os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, 'wb').write(c.read(n))
        print(f'{size:10d}  {n}')
