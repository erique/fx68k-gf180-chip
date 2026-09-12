# SPDX-FileCopyrightText: © 2025 Project Template Contributors
# SPDX-License-Identifier: Apache-2.0

import os
import random
import logging
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, Edge, RisingEdge, FallingEdge, ClockCycles
from cocotb_tools.runner import get_runner

sim = os.getenv("SIM", "icarus")
gl = os.getenv("GL", False)
pdk_root = os.getenv("PDK_ROOT", Path(__file__).resolve().parent / "../gf180mcu")
pdk = os.getenv("PDK", "gf180mcuD")
scl = os.getenv("SCL", "gf180mcu_fd_sc_mcu7t5v0")
pad = os.getenv("PAD", "gf180mcu_fd_io")
sram = os.getenv("SRAM", "gf180mcu_fd_ip_sram")
slot = os.getenv("SLOT", "1x1")

hdl_toplevel = "chip_top" if gl else "chip_core"

# bidir_PAD indices (src/chip_core.sv)
PAD_A_LSB = 0
PAD_A_MSB = 22
PAD_D_LSB = 23
PAD_D_MSB = 38
PAD_AS = 39
PAD_UDS = 40
PAD_LDS = 41
PAD_RW = 42
PAD_DTACK = 43
PAD_BERR = 44
PAD_HALT = 45
PAD_VPA = 46
PAD_E = 47
PAD_VMA = 48
PAD_FC0 = 49
PAD_FC1 = 50
PAD_FC2 = 51
PAD_BR = 52
PAD_BG = 53
PAD_BGACK = 54
PAD_IPL0 = 55
PAD_IPL1 = 56
PAD_IPL2 = 57

GRANT_HIZ_PADS = (
    tuple(range(PAD_A_LSB, PAD_A_MSB + 1))
    + tuple(range(PAD_D_LSB, PAD_D_MSB + 1))
    + (PAD_AS, PAD_UDS, PAD_LDS, PAD_RW, PAD_VMA, PAD_FC0, PAD_FC1, PAD_FC2)
)
HALT_HIZ_PADS = tuple(range(PAD_A_LSB, PAD_A_MSB + 1)) + tuple(
    range(PAD_D_LSB, PAD_D_MSB + 1)
)
HALT_DRIVEN_STROBES = (PAD_AS, PAD_UDS, PAD_LDS, PAD_RW, PAD_VMA, PAD_FC0, PAD_FC1, PAD_FC2)

# GL chip_top: PU/PD inputs resolve without the core. CPU-driven pads stay X
# (pnl is dffq / sync reset; RESET and HALT pad OE start X, so bufif1 does
# not pass rst_n_PAD into the core). Do not assign packed bidir_PAD.
GL_PULL_INPUTS = {
    PAD_DTACK: "0",
    PAD_BERR: "1",
    PAD_VPA: "1",
    PAD_BR: "1",
    PAD_BGACK: "1",
    PAD_IPL0: "1",
    PAD_IPL1: "1",
    PAD_IPL2: "1",
}


async def set_defaults(dut):
    pass


# Input levels come from pad PU/PD (DTACK pull-down, others pull-up).
# Do not assign the packed bidir vector from Python: that forces address
# bits and fights the pad output drivers.

async def enable_power(dut):
    dut.VDD.value = 1
    dut.VSS.value = 0

async def start_clock(clock, freq=50):
    """Start the clock @ freq MHz"""
    c = Clock(clock, 1 / freq * 1000, "ns")
    cocotb.start_soon(c.start())


async def reset(reset, active_low=True, time_ns=1000):
    """Reset dut"""
    cocotb.log.info("Reset asserted...")

    reset.value = not active_low
    await Timer(time_ns, "ns")
    reset.value = active_low

    cocotb.log.info("Reset deasserted.")


def drive_core_inputs(dut):
    """bidir_in is a normal input; whole-vector assign is OK."""
    n = len(dut.bidir_in)
    ones = (1 << n) - 1
    dut.bidir_in.value = ones & ~(1 << PAD_DTACK)


def set_bidir_bit(dut, idx, val):
    cur = int(dut.bidir_in.value)
    if val:
        dut.bidir_in.value = cur | (1 << idx)
    else:
        dut.bidir_in.value = cur & ~(1 << idx)


def sig_bin(sig):
    return str(sig.value).lower().replace(" ", "")


def oe_bit(dut, idx):
    bits = sig_bin(dut.bidir_oe)
    return bits[len(bits) - 1 - idx]


async def wait_pred(clk, pred, max_cycles, msg):
    for _ in range(max_cycles):
        await RisingEdge(clk)
        if pred():
            return
    raise AssertionError(msg)


async def wait_asn_level(dut, clk, level, max_cycles=4000):
    want = "1" if level else "0"
    await wait_pred(
        clk,
        lambda: sig_bin(dut.ASn) == want,
        max_cycles,
        f"ASn did not become {want}",
    )


def assert_oe(dut, indices, want, label):
    bad = [i for i in indices if oe_bit(dut, i) != want]
    assert not bad, f"{label}: bidir_oe[{bad}] != {want}"


async def start_up(dut):
    """Startup sequence"""
    await set_defaults(dut)
    if gl:
        await enable_power(dut)
        await start_clock(dut.clk_PAD)
        await reset(dut.rst_n_PAD)
    else:
        drive_core_inputs(dut)
        await start_clock(dut.clk)
        await reset(dut.rst_in)


SMOKE_CYCLES = 32


@cocotb.test()
async def test_reset_smoke(dut):
    """After reset, address pads are driven. Data may be Z on a read."""

    logger = logging.getLogger("fx68k_tb")
    logger.info("Startup sequence...")
    await start_up(dut)

    clk = dut.clk_PAD if gl else dut.clk
    await ClockCycles(clk, SMOKE_CYCLES)

    if gl:
        bits = sig_bin(dut.bidir_PAD)
        logger.info("bidir_PAD=%s", bits)
        bad = []
        for idx, want in GL_PULL_INPUTS.items():
            got = bits[len(bits) - 1 - idx]
            if got != want:
                bad.append((idx, got, want))
        assert not bad, f"GL PU/PD inputs: {bad} bidir_PAD={bits}"
    else:
        eab = str(dut.eab.value)
        asn = str(dut.ASn.value)
        logger.info("eab=%s ASn=%s", eab, asn)
        assert "x" not in eab.lower(), f"eab still X after reset: {eab}"
        assert asn in ("0", "1"), f"ASn still X after reset: {asn}"
        assert sig_bin(dut.BGn) == "1", f"BGn X/asserted after reset: {dut.BGn.value}"
        assert_oe(dut, range(PAD_A_LSB, PAD_A_MSB + 1), "1", "A after reset")
        assert_oe(
            dut,
            (PAD_AS, PAD_UDS, PAD_LDS, PAD_RW, PAD_E, PAD_VMA, PAD_BG, PAD_FC0, PAD_FC1, PAD_FC2),
            "1",
            "strobes/E/VMA/FC/BG after reset",
        )
        assert_oe(dut, (PAD_HALT,), "0", "HALT OD idle")
        assert sig_bin(dut.rst_oe) == "0", "RESET OD idle"
    logger.info("Done!")


WAIT_CYCLES = 4000


@cocotb.test(skip=bool(gl))
async def test_bus_grant_hiz(dut):
    """Table 3-4: on bus relinquish, Hi-Z A/D/AS/UDS/LDS/R/W/VMA/FC; BG stays driven."""
    await start_up(dut)
    clk = dut.clk

    await wait_asn_level(dut, clk, 0)
    await wait_asn_level(dut, clk, 1)
    set_bidir_bit(dut, PAD_BR, 0)

    await wait_pred(
        clk,
        lambda: sig_bin(dut.BGn) == "0" and sig_bin(dut.ASn) == "1",
        WAIT_CYCLES,
        "BGn did not assert with ASn inactive",
    )

    assert_oe(dut, GRANT_HIZ_PADS, "0", "grant Hi-Z")
    assert_oe(dut, (PAD_BG, PAD_E), "1", "BG/E stay driven on grant")
    assert_oe(dut, (PAD_HALT, PAD_DTACK, PAD_BERR, PAD_BR, PAD_BGACK), "0", "inputs stay input")


@cocotb.test(skip=bool(gl))
async def test_halt_hiz(dut):
    """Table 3-4: on HALT, Hi-Z A/D only; AS/UDS/LDS/R/W/VMA/FC stay driven."""
    await start_up(dut)
    clk = dut.clk

    await wait_asn_level(dut, clk, 0)
    set_bidir_bit(dut, PAD_HALT, 0)
    await wait_pred(
        clk,
        lambda: sig_bin(dut.ASn) == "1"
        and sig_bin(dut.BGn) == "1"
        and all(oe_bit(dut, i) == "0" for i in HALT_HIZ_PADS),
        WAIT_CYCLES,
        "HALT did not Hi-Z A/D with ASn inactive",
    )

    assert sig_bin(dut.BGn) == "1", f"BG asserted during HALT-only: {dut.BGn.value}"
    assert_oe(dut, HALT_HIZ_PADS, "0", "HALT A/D Hi-Z")
    assert_oe(dut, HALT_DRIVEN_STROBES, "1", "HALT strobes/FC/VMA driven")
    assert_oe(dut, (PAD_BG, PAD_E), "1", "BG/E stay driven on HALT")
    assert_oe(dut, (PAD_HALT,), "0", "external HALT is input (OD off)")


def chip_top_runner():

    proj_path = Path(__file__).resolve().parent

    sources = []
    defines = {f"SLOT_{slot.upper()}": True}
    includes = [proj_path / "../src/"]

    # Set the LibreLane PDK/SCL/PAD defines
    defines[f"PDK_{pdk.replace('-','_')}"] = True
    defines[f"SCL_{scl}"] = True
    defines[f"PAD_{pad}"] = True
    defines[f"SRAM_{sram}"] = True

    if gl:
        # SCL models
        sources.append(Path(pdk_root) / pdk / "libs.ref" / scl / "verilog" / f"{scl}.v")
        if scl != "gf180mcu_as_sc_mcu7t3v3":
            sources.append(Path(pdk_root) / pdk / "libs.ref" / scl / "verilog" / "primitives.v")

        # We use the powered netlist
        sources.append(proj_path / f"../final/pnl/{hdl_toplevel}.pnl.v")

        defines.update({"FUNCTIONAL": True, "USE_POWER_PINS": True})
    else:
        sources.append(proj_path / "../src/chip_core.sv")
        sources.append(proj_path / "../build/fx68k-v/fx68k.v")
        sources.append(proj_path / "../build/fx68k-v/uRom.v")
        sources.append(proj_path / "../build/fx68k-v/nanoRom.v")

    if gl:
        sources += [
            Path(pdk_root) / pdk / f"libs.ref/{pad}/verilog/{pad}.v",
            proj_path / "../ip/gf180mcu_ws_ip__logo/vh/gf180mcu_ws_ip__logo.v",
            proj_path / "../ip/gf180mcu_ws_ip__marker/vh/gf180mcu_ws_ip__marker.v",
            proj_path / "../ip/gf180mcu_ws_ip__qrcode_id/vh/gf180mcu_ws_ip__qrcode_id.v",
            proj_path / "../ip/gf180mcu_ws_ip__shuttle_id/vh/gf180mcu_ws_ip__shuttle_id.v",
            proj_path / "../ip/gf180mcu_ws_ip__project_id/vh/gf180mcu_ws_ip__project_id.v",
        ]

    build_args = []

    if sim == "icarus":
        # For debugging
        # build_args = ["-Winfloop", "-pfileline=1"]
        pass

    if sim == "verilator":
        build_args = ["--timing", "--trace", "--trace-fst", "--trace-structs"]

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel=hdl_toplevel,
        defines=defines,
        always=True,
        includes=includes,
        build_args=build_args,
        waves=True,
    )

    plusargs = []

    runner.test(
        hdl_toplevel=hdl_toplevel,
        test_module="chip_top_tb,",
        plusargs=plusargs,
        waves=True,
    )


if __name__ == "__main__":
    chip_top_runner()
