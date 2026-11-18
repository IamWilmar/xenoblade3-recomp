#!/usr/bin/env python3
"""Sitios de main que llaman (bl/b) a un import por su PLT.

Uso: python3 tools/llamadas.py <trozo del nombre mangled o demangled>...   (necesita work/scope/plt.txt y main.elf)
"""
import struct, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
NDK = Path.home() / 'Library/Android/sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/darwin-x86_64/bin'
plt = {}
for line in (ROOT / 'work/scope/plt.txt').read_text().splitlines():
    q = line.split()
    if len(q) >= 2:
        try: plt[int(q[0], 16)] = q[1]
        except ValueError: pass
elf = (ROOT / 'work/scope/main.elf').read_bytes()
phoff, = struct.unpack_from('<Q', elf, 0x20); nph, = struct.unpack_from('<H', elf, 0x38)
for i in range(nph):
    t, fl, off, va, _, fsz, msz = struct.unpack_from('<IIQQQQQ', elf, phoff + i * 56)
    if t == 1 and fl & 1: text_off, text_va, text_sz = off, va, fsz
ins = struct.unpack_from('<%dI' % (text_sz // 4), elf, text_off)
dem = subprocess.run([str(NDK / 'llvm-cxxfilt')], input='\n'.join(plt.values()), capture_output=True, text=True).stdout.splitlines()
names = dict(zip(plt.keys(), zip(plt.values(), dem)))
want = {a: n for a, n in names.items() if any(w in n[0] or w in n[1] for w in sys.argv[1:])}
sites = {a: [] for a in want}
for i, w in enumerate(ins):
    if (w & 0x7C000000) == 0x14000000:
        d = w & 0x3FFFFFF
        if d & 0x2000000: d -= 0x4000000
        t = text_va + i * 4 + d * 4
        if t in sites: sites[t].append(text_va + i * 4)
for a, s in sites.items():
    print(f"{names[a][1]}  [plt {a:#x}]  {len(s)} sitios: {' '.join(hex(x) for x in s[:24])}")
