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
PAD_DTACK = 43
PAD_BERR = 44
PAD_HALT = 45
PAD_VPA = 46
PAD_BR = 52
PAD_BGACK = 54
PAD_IPL0 = 55
PAD_IPL1 = 56
PAD_IPL2 = 57
PAD_A_MSB = 22
PAD_D_LSB = 23
PAD_D_MSB = 38


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
        bits = str(dut.bidir_PAD.value)
        logger.info("bidir_PAD=%s", bits)
        assert "x" not in bits.lower(), f"bidir_PAD has X after reset: {bits}"
    else:
        eab = str(dut.eab.value)
        asn = str(dut.ASn.value)
        logger.info("eab=%s ASn=%s", eab, asn)
        assert "x" not in eab.lower(), f"eab still X after reset: {eab}"
        assert asn in ("0", "1"), f"ASn still X after reset: {asn}"
    logger.info("Done!")


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

    sources += [
        Path(pdk_root) / pdk / f"libs.ref/{sram}/verilog/{sram}__sram512x8m8wm1.v",
    ]
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
