#!/usr/bin/env python3
"""Resumen del flujo de un rango de main: llamadas a imports (por PLT), llamadas virtuales (offset del vtable) y cadenas.

Uso: python3 tools/flujo.py <inicio_hex> <fin_hex> [módulo=main]
"""
import struct, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
NDK = Path.home() / 'Library/Android/sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/darwin-x86_64/bin'
mod = sys.argv[3] if len(sys.argv) > 3 else 'main'
plt = {}
if mod == 'main':
    for line in (ROOT / 'work/scope/plt.txt').read_text().splitlines():
        q = line.split(None, 1)
        if len(q) == 2:
            try: plt[int(q[0], 16)] = q[1]
            except ValueError: pass
elf = (ROOT / f'work/scope/{mod}.elf').read_bytes()
phoff, = struct.unpack_from('<Q', elf, 0x20); nph, = struct.unpack_from('<H', elf, 0x38)
segs = []
for i in range(nph):
    t, fl, off, va, _, fsz, msz = struct.unpack_from('<IIQQQQQ', elf, phoff + i * 56)
    if t == 1: segs.append((va, off, fsz, fl))
def rd(va, n):
    for v, o, z, f in segs:
        if v <= va < v + z: return elf[va - v + o: va - v + o + n]
    return b''
def cstr(va):
    b = rd(va, 80).split(b'\0')[0]
    try:
        s = b.decode()
        return s if len(s) >= 2 and all(32 <= ord(c) < 127 for c in s) else None
    except UnicodeDecodeError: return None
def sx(v, b): return v - (1 << b) if v >> (b - 1) & 1 else v
a0, a1 = int(sys.argv[1], 16), int(sys.argv[2], 16)
code = rd(a0, a1 - a0)
ins = struct.unpack_from('<%dI' % (len(code) // 4), code)
page = {}; lastld = {}
for i, w in enumerate(ins):
    pc = a0 + i * 4
    if (w & 0x9F000000) == 0x90000000:
        page[w & 31] = (pc & ~0xFFF) + (sx((((w >> 5) & 0x7FFFF) << 2) | ((w >> 29) & 3), 21) << 12); continue
    if (w & 0xFF800000) == 0x91000000:
        rn, rd_ = (w >> 5) & 31, w & 31
        if rn in page:
            a = page[rn] + (((w >> 10) & 0xFFF) << (12 if (w >> 22) & 1 else 0))
            s = cstr(a)
            if s: print(f'{pc:#x}  "{s}"')
            page.pop(rn, None)
        continue
    if (w & 0xFFC00000) == 0xF9400000:  # ldr x
        lastld[w & 31] = ((w >> 5) & 31, ((w >> 10) & 0xFFF) * 8)
        continue
    if (w & 0xFC000000) == 0x94000000 or (w & 0xFC000000) == 0x14000000:
        t = pc + sx(w & 0x3FFFFFF, 26) * 4
        kind = 'bl' if w >> 31 else 'b '
        if t in plt: print(f'{pc:#x}  {kind} {plt[t]}')
        elif kind == 'bl' and not (a0 <= t < a1): print(f'{pc:#x}  bl {mod}+{t:#x}')
        continue
    if (w & 0xFFFFFC1F) == 0xD63F0000 or (w & 0xFFFFFC1F) == 0xD61F0000:
        r = (w >> 5) & 31
        if r in lastld: print(f'{pc:#x}  {"blr" if w & 0x200000 else "br "} [x{lastld[r][0]}+{lastld[r][1]:#x}]')
        else: print(f'{pc:#x}  blr x{r}')
    if (w & 0xFFFFFC1F) == 0xD65F0000: print(f'{pc:#x}  ret')
