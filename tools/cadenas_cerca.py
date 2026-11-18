#!/usr/bin/env python3
"""Cadenas (ASCII y UTF-16) a las que hace referencia el código de main en una ventana alrededor de una dirección.

Uso: python3 tools/cadenas_cerca.py <dirección_hex> [radio_hex=0x1000]
Sirve para saber de qué parte del motor es una función: sus nombres de pases, estadísticas y avisos.
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
def rd(va, n):
    for v, o, z, f in segs:
        if v <= va < v + z: return elf[va - v + o: va - v + o + n]
    return b''
def text(va):
    b = rd(va, 160)
    a = b.split(b'\0')[0]
    if len(a) >= 4 and all(32 <= c < 127 for c in a): return a.decode()
    try:
        u = b.decode('utf-16-le', 'ignore').split('\0')[0]
        if len(u) >= 4 and all(32 <= ord(c) < 127 for c in u): return 'L"' + u + '"'
    except Exception: pass
    return None
def sx(v, b): return v - (1 << b) if v >> (b - 1) & 1 else v
center = int(sys.argv[1], 16); radius = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x1000
a0 = (center - radius) & ~3
code = rd(a0, 2 * radius)
ins = struct.unpack_from('<%dI' % (len(code) // 4), code)
page = {}
for i, w in enumerate(ins):
    pc = a0 + i * 4
    if (w & 0x9F000000) == 0x90000000:
        page[w & 31] = (pc & ~0xFFF) + (sx((((w >> 5) & 0x7FFFF) << 2) | ((w >> 29) & 3), 21) << 12)
    elif (w & 0xFF800000) == 0x91000000 and ((w >> 5) & 31) in page:
        s = text(page[(w >> 5) & 31] + (((w >> 10) & 0xFFF) << (12 if (w >> 22) & 1 else 0)))
        if s: print(f'{pc:#x}  {s[:150]}')
