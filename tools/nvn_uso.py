"""Uso: python3 tools/nvn_uso.py work/analysis/main.elf work/analysis/nvn_missing.txt work/analysis/nvn_uso.tsv
Uso estático de NVN: nombre -> ranura global que llena el cargador -> lecturas de esa ranura en el resto del código."""
import re, struct, sys, collections
elf = open(sys.argv[1], 'rb').read()
phoff, = struct.unpack_from('<Q', elf, 0x20); nph, = struct.unpack_from('<H', elf, 0x38)
segs = []
for i in range(nph):
    t, fl, off, va, _, fsz, msz = struct.unpack_from('<IIQQQQQ', elf, phoff + i * 56)
    if t == 1: segs.append((va, off, fsz, fl))
text = next(s for s in segs if s[3] & 1)
ro = next(s for s in segs if s[3] == 4)
def blob(s): return elf[s[1]:s[1] + s[2]]
rob = blob(ro)
strs = {}
for m in re.finditer(rb'(?<![A-Za-z0-9_])(nvn[A-Z][A-Za-z0-9]+)\0', rob):
    strs[ro[0] + m.start(1)] = m.group(1).decode()
tb = blob(text); base = text[0]; N = len(tb) // 4
ins = struct.unpack_from('<%dI' % N, tb)
def sx(v, b): return v - (1 << b) if v >> (b - 1) & 1 else v
page = {}   # reg -> (page, pc idx)
name_site = {}  # name -> list of idx
slot_of = collections.defaultdict(set)
loads = collections.Counter(); load_sites = collections.defaultdict(list)
for i, w in enumerate(ins):
    pc = base + i * 4
    if (w & 0x9F000000) == 0x90000000:
        imm = sx((((w >> 5) & 0x7FFFF) << 2) | ((w >> 29) & 3), 21) << 12
        page[w & 31] = ((pc & ~0xFFF) + imm, i); continue
    if (w & 0xFF800000) == 0x91000000:
        rn = (w >> 5) & 31; rd = w & 31
        if rn in page and i - page[rn][1] < 32:
            a = page[rn][0] + (((w >> 10) & 0xFFF) << (12 if (w >> 22) & 1 else 0))
            if a in strs:
                name_site.setdefault(strs[a], []).append(i)
        page.pop(rd, None); continue
    if (w & 0xFFC00000) in (0xF9400000, 0xF9000000):
        rn = (w >> 5) & 31
        if rn in page and i - page[rn][1] < 64:
            a = page[rn][0] + ((w >> 10) & 0xFFF) * 8
            if (w & 0xFFC00000) == 0xF9400000:
                loads[a] += 1; load_sites[a].append(i)
                slot_of[i].add(a)
            page.pop(w & 31, None)  # el destino ya no es una página (también si es la misma base: ldr x9, [x9])
        elif (w & 0xFFC00000) == 0xF9400000: page.pop(w & 31, None)
# ranura: la primera carga de una ranura global tras el blr a GetProcAddress que sigue al nombre. Hay que esperar
# al blr: el compilador puede adelantar el nombre siguiente antes de guardar el resultado del anterior (Unity 2022 en
# Castlevania: adrp/add x1 nombre_k; ldr x8, ranura_k-1; str x0, [x8]; blr), y sin eso cada nombre se queda con la
# ranura del anterior.
slots = {}
for n, sites in name_site.items():
    for s in sites:
        blr = next((j for j in range(s, min(s + 24, N)) if (ins[j] & 0xFFFFFC1F) == 0xD63F0000), None)
        if blr is None: continue
        for j in range(blr, min(blr + 24, N)):
            if j in slot_of:
                slots.setdefault(n, set()).update(slot_of[j]); break
used = {}
for n in strs.values():
    c = sum(loads[a] - 1 for a in slots.get(n, ()))
    used[n] = c
names = sorted(set(strs.values()))
miss = set(open(sys.argv[2]).read().split())
print('nombres', len(names), 'con ranura', len(slots))
print('# faltantes con lecturas (usados):')
for n in sorted(miss, key=lambda n: -used.get(n, 0)):
    if used.get(n, 0):
        sitios = [hex(base + 4 * i) for a in slots.get(n, ()) for i in load_sites[a]]
        print(f'{used[n]:5d} {n}  lecturas: {" ".join(sitios)}')
print('# faltantes sin ranura:', [n for n in miss if n not in slots])
open(sys.argv[3], 'w').write(''.join(f'{used.get(n,0)}\t{n}\n' for n in names))
