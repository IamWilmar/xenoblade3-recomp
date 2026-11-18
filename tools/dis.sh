#!/usr/bin/env bash
# Desensambla un rango de un ELF de work/scope. Uso: tools/dis.sh <módulo> <inicio_hex> <fin_hex | +bytes>
NDK="$HOME/Library/Android/sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/darwin-x86_64/bin"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
start=$(($2)); end=$3
case "$end" in +*) end=$((start + ${end#+}));; *) end=$((end));; esac
"$NDK/llvm-objdump" -d --no-show-raw-insn --start-address=$start --stop-address=$end "$ROOT/work/scope/$1.elf" \
  | awk '/^ *[0-9a-f]+:/' | cut -c1-96
