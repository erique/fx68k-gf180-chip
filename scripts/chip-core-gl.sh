#!/usr/bin/env bash
# Pad-less gate netlist of chip_core (fx68k + OE). No foundry pads.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PDK_ROOT="${PDK_ROOT:-$ROOT/gf180mcu}"
PDK="${PDK:-gf180mcuD}"
SCL="${SCL:-gf180mcu_fd_sc_mcu7t5v0}"
LIB="$PDK_ROOT/$PDK/libs.ref/$SCL/lib/${SCL}__tt_025C_5v00.lib"
RTL="$ROOT/build/fx68k-v"
OUT_DIR="$ROOT/build/chip-core-gl"
OUT="$OUT_DIR/chip_core.nl.v"
LOG="$OUT_DIR/yosys.log"

if [[ ! -f "$RTL/fx68k.v" ]]; then
    echo "error: $RTL/fx68k.v missing; run make fx68k-rtl" >&2
    exit 1
fi
if [[ ! -f "$LIB" ]]; then
    echo "error: liberty not found: $LIB (make clone-pdk)" >&2
    exit 1
fi
if ! command -v yosys >/dev/null 2>&1; then
    echo "error: yosys not on PATH" >&2
    exit 1
fi

mkdir -p "$OUT_DIR"

# Keep uRom/nanoRom behavioral: dfflibmap drops RAM initial images, so a
# mapped ROM starts X and the CPU never leaves reset.
yosys -l "$LOG" -p "
read_verilog -sv -I${ROOT}/src ${ROOT}/src/chip_core.sv
read_verilog ${RTL}/fx68k.v
read_verilog -lib ${RTL}/uRom.v ${RTL}/nanoRom.v
hierarchy -check -top chip_core
synth -top chip_core
dfflibmap -liberty ${LIB}
abc -liberty ${LIB}
opt_clean -purge
delete nanoRom uRom
write_verilog -noattr ${OUT}
"

echo "Wrote $OUT"
