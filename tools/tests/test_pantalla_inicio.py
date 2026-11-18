#!/usr/bin/env python3
"""Prueba la búsqueda de la pantalla de inicio (android/java/.../DumpScanner.java) sin dispositivo: compila
DumpScanner.java y Game.java con javac, monta carpetas falsas con archivos marca vacíos (un ExeFS con las cabeceras
mínimas de main y main.npdm, la RomFS del juego y la de cada DLC) y comprueba lo que encuentra el escáner.

Casos: los cuatro DLC con su id de título en el nombre de la carpeta (como los nombran las herramientas de extracción),
los cuatro como aoc/1 .. aoc/4, solo el juego, y un DLC sin id ni aoc/<índice> (se cuenta como desconocido).
Necesita un JDK (javac y java en el PATH). Uso: tools/tests/test_dumpscanner.py
"""
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JAVA = ROOT / "android" / "java"


def game_constants():
    src = next(JAVA.rglob("Game.java")).read_text()
    pkg = re.search(r"^package ([\w.]+);", src, re.M).group(1)
    app_id = int(re.search(r"APP_ID = (0x[0-9A-Fa-f]+)L", src).group(1), 16)
    known = re.search(r'KNOWN_BUILDS = \{\{"([0-9a-f]{40})", "([^"]+)", (null|"(\d+)")', src)
    romfs = re.search(r'ROMFS_MARKER = "([^"]+)"', src).group(1)
    version_file = re.search(r'VERSION_FILE = (null|"([^"]+)")', src).group(2)
    return pkg, app_id, known.group(1), known.group(2), known.group(4), romfs, version_file


def touch(path, size=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        if size:
            f.truncate(size)  # disperso: no ocupa disco


def fake_exefs(d, app_id, build):
    nso = bytearray(0x100)
    nso[0:4] = b"NSO0"
    nso[0x40:0x54] = bytes.fromhex(build)
    npdm = bytearray(0x100)
    npdm[0:4] = b"META"
    struct.pack_into("<I", npdm, 0x70, 0x80)  # posición de la ACI0
    npdm[0x80:0x84] = b"ACI0"
    struct.pack_into("<Q", npdm, 0x90, app_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "main").write_bytes(nso)
    (d / "main.npdm").write_bytes(npdm)


def fake_game(root, app_id, build, romfs, version_file, version_size):
    base = root / f"Xenoblade Chronicles 3 ({app_id:016X})"
    fake_exefs(base / "exefs", app_id, build)
    touch(base / "romfs" / romfs)
    if version_file:
        touch(base / "romfs" / version_file, int(version_size) if version_size else 0)


def fake_dlc(d, n):
    # La raíz de la RomFS de cada DLC: bf3_dlc0N.ard / .arh; del 2 al 4 también subcarpetas.
    touch(d / f"bf3_dlc0{n}.ard")
    touch(d / f"bf3_dlc0{n}.arh")
    if n > 1:
        touch(d / "sub" / "dato.bin")


def run(classes, pkg, root):
    out = subprocess.run(["java", "-cp", str(classes), f"{pkg}.DumpScanner", str(root)], capture_output=True, text=True,
                         check=True).stdout
    dlc = re.search(r"dlc: (\d+)(?: \((\d+)\.\.(\d+)\))?, unknown: (\d+), ready: (\w+)", out)
    return out, dict(count=int(dlc.group(1)), first=dlc.group(2) and int(dlc.group(2)),
                     last=dlc.group(3) and int(dlc.group(3)), unknown=int(dlc.group(4)), ready=dlc.group(5) == "true")


def main():
    pkg, app_id, build, version, version_size, romfs, version_file = game_constants()
    tmp = Path(tempfile.mkdtemp(prefix="escaner_"))
    failures = 0
    try:
        classes = tmp / "classes"
        sources = [str(p) for p in JAVA.rglob("*.java") if p.name in ("DumpScanner.java", "Game.java")]
        subprocess.run(["javac", "-Xlint:-options", "--release", "11", "-d", str(classes), *sources], check=True)

        cases = {}
        t = tmp / "con_id"
        fake_game(t, app_id, build, romfs, version_file, version_size)
        for n in range(1, 5):
            fake_dlc(t / f"Xenoblade Chronicles 3 DLC {n} ({app_id + 0x1000 + n:016X}) (RomFS)", n)
        cases["DLC con id de título"] = (t, dict(count=4, first=1, last=4, unknown=0, ready=True))

        t = tmp / "aoc"
        fake_game(t, app_id, build, romfs, version_file, version_size)
        for n in range(1, 5):
            fake_dlc(t / "aoc" / str(n), n)
        cases["DLC en aoc/<índice>"] = (t, dict(count=4, first=1, last=4, unknown=0, ready=True))

        t = tmp / "solo_juego"
        fake_game(t, app_id, build, romfs, version_file, version_size)
        cases["solo el juego"] = (t, dict(count=0, first=None, last=None, unknown=0, ready=True))

        t = tmp / "dlc_sin_id"
        fake_game(t, app_id, build, romfs, version_file, version_size)
        fake_dlc(t / "mis_dlc" / "uno", 1)
        cases["DLC sin id ni aoc/<índice>"] = (t, dict(count=0, first=None, last=None, unknown=1, ready=True))

        for name, (t, want) in cases.items():
            out, got = run(classes, pkg, t)
            ok = got == want and f"versión: {version}" in out
            failures += not ok
            print(("ok   " if ok else "FALLA") + f" {name}: {got}" + ("" if ok else f"\n      quería {want}\n{out}"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
