#!/usr/bin/env python3
"""Sitios del código de main que cargan una dirección dada con adrp+add (cadenas, tablas, globales).

Uso: python3 tools/refs.py <dirección_hex>...      (direcciones del main.elf de work/scope, las que da strings/flujo)
     python3 tools/refs.py --archivo <offset_hex>  (offset dentro del fichero main.elf en vez de dirección)
"""
import struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
elf = (ROOT / 'work/scope/main.elf').read_bytes()
phoff, = struct.unpack_from('<Q', elf, 0x20); nph, = struct.unpack_from('<H', elf, 0x38)
segs = []
for i in range(nph):
    t, fl, off, va, _, fsz, msz = struct.unpack_from('<IIQQQQQ', elf, phoff + i * 56)
    if t == 1: segs.append((va, off, fsz, fl))
text = next(s for s in segs if s[3] & 1)
args = sys.argv[1:]
if args and args[0] == '--archivo':
    targets = []
    for a in args[1:]:
        o = int(a, 16)
        for va, off, fsz, fl in segs:
            if off <= o < off + fsz: targets.append(o - off + va)
else:
    targets = [int(a, 16) for a in args]
want = set(targets)
ins = struct.unpack_from('<%dI' % (text[2] // 4), elf, text[1])
def sx(v, b): return v - (1 << b) if v >> (b - 1) & 1 else v
page = {}
hits = {t: [] for t in want}
for i, w in enumerate(ins):
    pc = text[0] + i * 4
    if (w & 0x9F000000) == 0x90000000:
        page[w & 31] = ((pc & ~0xFFF) + (sx((((w >> 5) & 0x7FFFF) << 2) | ((w >> 29) & 3), 21) << 12), i); continue
    if (w & 0xFF800000) == 0x91000000:
        rn = (w >> 5) & 31
        if rn in page and i - page[rn][1] < 8:
            a = page[rn][0] + (((w >> 10) & 0xFFF) << (12 if (w >> 22) & 1 else 0))
            if a in want: hits[a].append(pc)
    elif (w & 0xFFC00000) == 0xF9400000:
        rn = (w >> 5) & 31
        if rn in page and i - page[rn][1] < 8:
            a = page[rn][0] + ((w >> 10) & 0xFFF) * 8
            if a in want: hits[a].append(pc)
for t in targets:
    print(f'{t:#x}: ' + ' '.join(hex(h) for h in hits[t][:40]) + (f' … ({len(hits[t])})' if len(hits[t]) > 40 else ''))
