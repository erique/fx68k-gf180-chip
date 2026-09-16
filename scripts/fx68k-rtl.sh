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

python3 - "$WORK_DIR/fx68k.sv" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
text = p.read_text()
subs = [
    (
        "\twire BusRetry = 1'b0;\n",
        "\twire BusRetry;\n",
    ),
    (
        "\tassign wClk = waitBusCycle | ~BeI | iAddrErr | Err6591;\n",
        "\tassign wClk = waitBusCycle | ~BeI | iAddrErr | Err6591 | (~Halti & ~addrOe);\n",
    ),
    (
        """\tbusControl busControl( .Clks, .enT1, .enT4, .permStart( Nanod.permStart), .permStop( Nanod.waitBusFinish), .iStop,
		.aob0, .isWrite( Nanod.isWrite), .isRmc( Nanod.isRmc), .isByte( busIsByte), .busAvail,
		.bciWrite, .addrOe, .bgBlock, .waitBusCycle, .busStarting, .busAddrErr,
		.rDtack, .BeDebounced, .Vpai,
		.ASn, .LDSn, .UDSn, .eRWn);
""",
        """\tbusControl busControl( .Clks, .enT1, .enT4, .permStart( Nanod.permStart), .permStop( Nanod.waitBusFinish), .iStop,
		.aob0, .isWrite( Nanod.isWrite), .isRmc( Nanod.isRmc), .isByte( busIsByte), .busAvail,
		.bciWrite, .addrOe, .bgBlock, .waitBusCycle, .busStarting, .busAddrErr,
		.rDtack, .BeDebounced, .Vpai, .Halti, .busRetry( BusRetry),
		.ASn, .LDSn, .UDSn, .eRWn);
""",
    ),
    (
        """		input rDtack, BeDebounced, Vpai,
		output ASn, output LDSn, output UDSn, eRWn);
""",
        """		input rDtack, BeDebounced, Vpai, Halti,
		output busRetry,
		output ASn, output LDSn, output UDSn, eRWn);
""",
    ),
    (
        """	// Bus retry not really supported.
	// It's BERR and HALT and not address error, and not read-modify cycle.
	wire busRetry = ~busAddrErr & 1'b0;
""",
        """	// Retry: BERR and HALT, not address error, not RMW (UM §5.4.2).
	wire busRetry = ~busAddrErr & ~isRmcReg & BeDebounced & ~Halti;
""",
    ),
    (
        "\tassign bcReset = Clks.extReset | (addrOeDelay & BeDebounced & Vpai);\n",
        "\tassign bcReset = Clks.extReset | (addrOeDelay & BeDebounced & Vpai & Halti);\n",
    ),
    (
        "\tassign bgBlock = ((busPhase == S0) & ASn) | (busPhase == SRMC_RES);\n",
        "\tassign bgBlock = ((busPhase == S0) & ASn) | (busPhase == SRMC_RES) | isRmcReg;\n",
    ),
    (
        """		if( Clks.pwrUp) begin
			rBerr <= 1'b0;
			BeI <= 1'b0;
		end
""",
        """		if( Clks.pwrUp) begin
			rBerr <= 1'b0;
			BeI <= 1'b0;
			BeiDelay <= 1'b0;
			rDtack <= 1'b1;
			Halti <= 1'b1;
			BRi <= 1'b1;
			BgackI <= 1'b1;
			Vpai <= 1'b1;
		end
""",
    ),
]
for old, new in subs:
    if old not in text:
        raise SystemExit(f"error: retry/halt pattern not found in {p}: {old[:60]!r}")
    text = text.replace(old, new, 1)
p.write_text(text)
print(f"patched retry/halt in {p}")
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
