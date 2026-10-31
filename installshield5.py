#!/usr/bin/env python3
"""Read an InstallShield 5 cabinet (data1.cab with the header inside, as on 1997-1999 discs).

  python3 installshield5.py DATA1.CAB                      list file groups and files
  python3 installshield5.py DATA1.CAB OUT GROUP [GROUP...] extract those file groups into OUT

Each file lands at OUT/<its directory>/<name> (the file group only selects files, as the
installer does). These early version 5 cabinets store no usable MD5 (the field holds leftover
bytes), so each file is checked for its size and for every compressed chunk ending cleanly; the
caller can check known hashes. Layout as documented by unshield (lib/libunshield.c, file.c,
file_group.c), header version 5 only.
"""
import os, struct, sys, zlib

COMPRESSED, INVALID = 4, 8


def u16(b, o): return struct.unpack_from('<H', b, o)[0]
def u32(b, o): return struct.unpack_from('<I', b, o)[0]


class Cabinet:
    def __init__(self, src, path='data1.cab'):
        self.path = src if isinstance(src, str) else path
        d = self.d = open(src, 'rb').read() if isinstance(src, str) else bytes(src)
        if d[:4] != b'ISc(': raise ValueError(f'{self.path}: not an InstallShield cabinet')
        cd = self.cd = u32(d, 0x0c)                      # cabinet descriptor
        self.ft = cd + u32(d, cd + 0x0c)                 # file table
        ndirs, nfiles = u32(d, cd + 0x1c), u32(d, cd + 0x28)
        tab = [u32(d, self.ft + 4 * i) for i in range(ndirs + nfiles)]
        self.dirs = [self._str(self.ft + tab[i]) for i in range(ndirs)]
        self.files = []
        for i in range(nfiles):
            p = self.ft + tab[ndirs + i]
            if u16(d, p + 8) & INVALID:                  # unused slot: junk name and directory
                self.files.append(dict(flags=INVALID, offset=0)); continue
            self.files.append(dict(
                name=self._str(self.ft + u32(d, p)), dir=self.dirs[u32(d, p + 4)], flags=u16(d, p + 8),
                size=u32(d, p + 0x0a), csize=u32(d, p + 0x0e), offset=u32(d, p + 0x26)))
        self.groups = {}
        for i in range(71):                              # file group hash table, chained lists
            o = u32(d, cd + 0x3e + 4 * i)
            while o:
                name, desc, nxt = (u32(d, cd + o + k) for k in (0, 4, 8))
                g = cd + desc
                self.groups[self._str(cd + name)] = (u32(d, g + 0x4c), u32(d, g + 0x50))
                o = nxt

    def _str(self, o):
        return self.d[o:self.d.index(b'\0', o)].decode('latin-1')

    def group_files(self, group):
        first, last = self.groups[group]
        return [f for f in self.files[first:last + 1] if not f['flags'] & INVALID and f['offset']]

    def read(self, f):
        raw = self.d[f['offset']:f['offset'] + f['csize']]
        if f['flags'] & COMPRESSED:
            out, q = bytearray(), 0
            try:
                while q < len(raw):
                    n = u16(raw, q); q += 2
                    z = zlib.decompressobj(-15); out += z.decompress(raw[q:q + n]); q += n
                    if not z.eof: raise zlib.error('chunk ends early')
            except (zlib.error, struct.error):
                out = None
            raw = bytes(out) if out is not None else b''
        if len(raw) != f['size']:
            raise ValueError(f"{self.path}: {f['dir']}\\{f['name']} is damaged (bad image?)")
        return raw

    def extract(self, groups, out):
        n = 0
        for g in groups:
            for f in self.group_files(g):
                dst = os.path.join(out, *[p for p in f['dir'].split('\\') if p], f['name'])
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                open(dst, 'wb').write(self.read(f)); n += 1
        return n


if __name__ == '__main__':
    c = Cabinet(sys.argv[1])
    if len(sys.argv) == 2:
        for g in c.groups:
            fs = c.group_files(g)
            print(f'{g}: {len(fs)} files')
            for f in fs: print(f"  {f['size']:9d}  {f['dir']}\\{f['name']}")
    else:
        print(f'{c.extract(sys.argv[3:], sys.argv[2])} files')
