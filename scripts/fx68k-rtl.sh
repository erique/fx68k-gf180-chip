#!/usr/bin/env bash
# sv2v the fx68k submodule into build/fx68k-v/ (not into the submodule).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$ROOT/fx68k/src"
WORK_DIR="$ROOT/build/fx68k-rtl"
OUT_DIR="$ROOT/build/fx68k-v"

if [[ ! -f "$SRC_DIR/fx68k.sv" ]]; then
    echo "error: fx68k submodule missing; git submodule update --init" >&2
    exit 1
fi

if [[ -z "${SV2V:-}" ]]; then
    if command -v sv2v >/dev/null 2>&1; then
        SV2V="$(command -v sv2v)"
    else
        echo "error: sv2v not on PATH" >&2
        exit 1
    fi
fi

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR" "$OUT_DIR"

cp -a "$SRC_DIR"/fx68k.sv "$SRC_DIR"/fx68kAlu.sv "$SRC_DIR"/uaddrPla.sv \
    "$WORK_DIR/"

python3 - "$WORK_DIR/fx68kAlu.sv" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
text = p.read_text()
old = """\t\t'he:
\t\t\tbegin
\t\t\t\treg [1:0] stype;
\t\t\t\t
\t\t\t\tif( size11)\t\t\t\t\t// memory shift/rotate
\t\t\t\t\tstype = ird[ 10:9];
\t\t\t\telse\t\t\t\t\t\t// register shift/rotate
\t\t\t\t\tstype = ird[ 4:3];

\t\t\t\tcase( {stype, ird[8]})
"""
new = """\t\t'he:
\t\t\tbegin
\t\t\t\t// Shift/rotate type is a purely combinational decode of IRD
\t\t\t\t// (memory form uses ird[10:9], register form uses ird[4:3]).
\t\t\t\tcase( {(size11 ? ird[10:9] : ird[4:3]), ird[8]})
"""
if old not in text:
    raise SystemExit(f"error: stype rewrite pattern not found in {p}")
p.write_text(text.replace(old, new, 1))
print(f"patched {p}")
PY

"$SV2V" \
    --write="$OUT_DIR/fx68k.v" \
    --top=fx68k \
    -I"$WORK_DIR" \
    "$WORK_DIR/fx68k.sv" \
    "$WORK_DIR/fx68kAlu.sv" \
    "$WORK_DIR/uaddrPla.sv"

python3 "$ROOT/fx68k/scripts/mem-to-verilog.py" --src "$SRC_DIR" --out-dir "$OUT_DIR"

python3 - "$OUT_DIR/fx68k.v" <<'PY'
import pathlib, re, sys
p = pathlib.Path(sys.argv[1])
text = p.read_text()
text, n = re.subn(
    r"\nmodule (?:uRom|nanoRom) \([\s\S]*?\nendmodule",
    "",
    text,
)
if n != 2:
    raise SystemExit(f"error: expected to strip 2 ROM modules, stripped {n}")
p.write_text(text)
print(f"stripped $readmemb uRom/nanoRom from {p}")
PY

echo "Wrote $OUT_DIR/fx68k.v $OUT_DIR/uRom.v $OUT_DIR/nanoRom.v"
