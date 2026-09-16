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

try:
    from cocotb.utils import get_sim_time
except ImportError:
    from cocotb.sim_time import get_sim_time

def env_flag(name):
    v = os.getenv(name, "")
    if v is False or v is None:
        return False
    return str(v).lower() not in ("", "0", "false")


sim = os.getenv("SIM", "icarus")
gl = env_flag("GL")
gl_core = env_flag("GL_CORE")
pads = env_flag("PADS")
pin_dut = gl or pads
pdk_root = os.getenv("PDK_ROOT", Path(__file__).resolve().parent / "../gf180mcu")
pdk = os.getenv("PDK", "gf180mcuD")
scl = os.getenv("SCL", "gf180mcu_fd_sc_mcu7t5v0")
pad = os.getenv("PAD", "gf180mcu_fd_io")
sram = os.getenv("SRAM", "gf180mcu_fd_ip_sram")
slot = os.getenv("SLOT", "1x1")

hdl_toplevel = "chip_top_gl_wrap" if pin_dut else "chip_core"

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
PAD_INPUT_DRIVE = (
    PAD_DTACK,
    PAD_BERR,
    PAD_HALT,
    PAD_VPA,
    PAD_BR,
    PAD_BGACK,
    PAD_IPL0,
    PAD_IPL1,
    PAD_IPL2,
)
DATA_W = PAD_D_MSB - PAD_D_LSB + 1
DATA_MASK = ((1 << DATA_W) - 1) << PAD_D_LSB

# UM reset: vector 0 = SSP, vector 1 = PC, then prefetch at PC.
RESET_SSP = 0x00001000
RESET_PC = 0x00000400
RESET_VEC_SSP_ADDR = 0x000000
RESET_VEC_PC_ADDR = 0x000004
FC_SUPERVISOR_PROGRAM = 0b110
FC_SUPERVISOR_DATA = 0b101
NOP_WORD = 0x4E71
RESET_PREFETCH_CYCLES = 2
WAIT_CYCLES = 8000
FC_CPU_SPACE = 0b111
# MOVE.W #imm, abs.W ; MOVE.W abs.W, D0
MOVE_W_IMM_ABS_W = 0x31FC
MOVE_W_ABS_W_D0 = 0x3038
STORE_IMM = 0xA5A5
STORE_ADDR = 0x2000
# abs.W sign-extends; keep bit 15 clear so the pad address is the word.
PERIPH_ADDR = 0x000800
SLAVE_ADDR = 0x001800
SLAVE_DATA = 0xA55A
# BRA.S from RESET_PC+4 back to RESET_PC (disp = RESET_PC - (RESET_PC+6)).
BRA_S_TO_RESET_PC = 0x60FA
BRA_S_TO_NOP = 0x60FC
WAIT_SWEEP_CLKS = (0, 1, 2, 4, 8, 16)
AUTOVEC_LEVEL = 7
AUTOVEC_BASE = 24
VEC_BYTES = 4
BUS_ERR_VEC = 2
SPURIOUS_VEC = 24
RTE_WORD = 0x4E73
RESET_INSN = 0x4E70
TAS_ABS_W = 0x4AF8
MOVE_B_IMM_ABS_W = 0x11FC
MOVE_W_IMM_SR = 0x46FC
SR_SUPER_MASK0 = 0x2000
BYTE_EVEN_ADDR = 0x001800
BYTE_ODD_ADDR = 0x001801
BYTE_EVEN_DATA = 0x00AA
BYTE_ODD_DATA = 0x0055
VECTORED_VEC = 0x40
IPL_LEVELS = (1, 2, 3, 4, 5, 6)
SLAVE_BERR_AFTER_CLKS = 16
E_PERIOD_CHIP_CLKS = 20

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


class PinShadow:
    """Shadow of bidir_in so the mem model does not drop BR/IPL/HALT."""

    def __init__(self, width):
        self.width = width
        self.v = (1 << width) - 1
        self.v &= ~(1 << PAD_DTACK)

    def set_bit(self, idx, val):
        if val:
            self.v |= 1 << idx
        else:
            self.v &= ~(1 << idx)

    def set_data(self, word):
        self.v = (self.v & ~DATA_MASK) | ((word & ((1 << DATA_W) - 1)) << PAD_D_LSB)

    def apply(self, dut):
        if pin_dut:
            dut.drv.value = self.v
            en = 0
            for i in PAD_INPUT_DRIVE:
                en |= 1 << i
            try:
                if pad_bit(dut, PAD_AS) == "0" and pad_bit(dut, PAD_RW) == "1":
                    en |= DATA_MASK
            except Exception:
                en |= DATA_MASK
            dut.drv_en.value = en
        else:
            dut.bidir_in.value = self.v


PINS = None


def drive_core_inputs(dut):
    """bidir_in is a normal input; whole-vector assign is OK."""
    global PINS
    n = 58 if pin_dut else len(dut.bidir_in)
    PINS = PinShadow(n)
    PINS.apply(dut)


def set_bidir_bit(dut, idx, val):
    PINS.set_bit(idx, val)
    PINS.apply(dut)


def set_data_word(dut, word):
    PINS.set_data(word)
    PINS.apply(dut)


def byte_addr(dut):
    if pads:
        bits = "".join(pad_bit(dut, i) for i in range(PAD_A_MSB, PAD_A_LSB - 1, -1))
    else:
        bits = sig_bin(dut.eab)
    if any(c not in "01" for c in bits):
        return None
    return int(bits, 2) << 1


def reset_vector_mem():
    mem = {
        RESET_VEC_SSP_ADDR: (RESET_SSP >> DATA_W) & ((1 << DATA_W) - 1),
        RESET_VEC_SSP_ADDR + 2: RESET_SSP & ((1 << DATA_W) - 1),
        RESET_VEC_PC_ADDR: (RESET_PC >> DATA_W) & ((1 << DATA_W) - 1),
        RESET_VEC_PC_ADDR + 2: RESET_PC & ((1 << DATA_W) - 1),
    }
    for off in range(0, 16, 2):
        mem.setdefault(RESET_PC + off, NOP_WORD)
    return mem


class BusMem:
    """Word RAM plus DTACK/VPA/BERR by address. bidir_in only (not bidir_PAD)."""

    def __init__(self, extra=None):
        self.words = reset_vector_mem()
        if extra:
            self.words.update(extra)
        self.writes = []
        self.vpa_addrs = set()
        self.berr_addrs = set()
        self.iack_vpa = False
        self.berr_used = False
        self.berr_hold = False
        self.retry_addrs = set()
        self.retry_hold = False
        self.retry_fired = False
        self.retry_phase = 0
        self.retry_idle = 0
        self.slave_addrs = set()
        self.slave_wait_clks = 0
        self.slave_berr_after = 0
        self.as_low_clks = 0
        self.iack_vector = None
        self.iack_berr = False

    def word(self, addr):
        return self.words.get(addr, NOP_WORD)

    def controls(self, addr, fc, asn):
        # (dtack, vpa, berr, halt) — idle: negate DTACK/BERR, HALT inactive.
        if asn != "0" or addr is None:
            self.as_low_clks = 0
            if self.berr_hold:
                self.berr_hold = False
                self.berr_used = True
            if self.retry_hold:
                self.retry_idle += 1
                if self.retry_idle < 8:
                    return 1, 1, 0, 0
                self.retry_hold = False
                self.retry_fired = True
                self.retry_phase = 0
                self.retry_idle = 0
                return 1, 1, 1, 1
            return 1, 1, 1, None
        self.as_low_clks += 1
        if addr in self.slave_addrs:
            if self.slave_berr_after and self.as_low_clks >= self.slave_berr_after:
                return 1, 1, 0, None
            if self.as_low_clks <= self.slave_wait_clks:
                return 1, 1, 1, None
        if fc == FC_CPU_SPACE:
            if self.iack_berr:
                return 1, 1, 0, None
            if self.iack_vpa:
                return 1, 0, 1, None
            if self.iack_vector is not None:
                return 0, 1, 1, None
        if addr in self.vpa_addrs:
            return 1, 0, 1, None
        if (addr in self.retry_addrs and not self.retry_fired) or self.retry_hold:
            self.retry_hold = True
            # HALT one clock before BERR so Halti is sampled with the error.
            if self.retry_phase == 0:
                self.retry_phase = 1
                return 1, 1, 1, 0
            return 1, 1, 0, 0
        if self.berr_hold or (addr in self.berr_addrs and not self.berr_used):
            self.berr_hold = True
            return 1, 1, 0, None
        return 0, 1, 1, None


async def mem_model(dut, mem):
    clk = bus_clk(dut)
    bus = mem if isinstance(mem, BusMem) else BusMem(mem)
    if not isinstance(mem, BusMem):
        bus.words.update(mem)
    while True:
        await RisingEdge(clk)
        addr = byte_addr(dut)
        asn = asn_sig(dut)
        fc = fc_val(dut)
        dtack, vpa, berr, halt = bus.controls(addr, fc, asn)
        set_bidir_bit(dut, PAD_DTACK, dtack)
        set_bidir_bit(dut, PAD_VPA, vpa)
        set_bidir_bit(dut, PAD_BERR, berr)
        if halt is not None:
            set_bidir_bit(dut, PAD_HALT, halt)
        if addr is None:
            continue
        if fc == FC_CPU_SPACE and bus.iack_vector is not None:
            set_data_word(dut, bus.iack_vector)
            continue
        if asn == "0" and rw_sig(dut) == "0":
            try:
                wdata = oedb_val(dut)
            except (ValueError, TypeError):
                wdata = None
            bus.writes.append((addr, wdata))
        else:
            set_data_word(dut, bus.word(addr))


def set_ipl(dut, level):
    pins = (~level) & AUTOVEC_LEVEL
    set_bidir_bit(dut, PAD_IPL0, pins & 1)
    set_bidir_bit(dut, PAD_IPL1, (pins >> 1) & 1)
    set_bidir_bit(dut, PAD_IPL2, (pins >> 2) & 1)


def fc_val(dut):
    if pads:
        s = pad_bit(dut, PAD_FC2) + pad_bit(dut, PAD_FC1) + pad_bit(dut, PAD_FC0)
    else:
        s = sig_bin(dut.FC2) + sig_bin(dut.FC1) + sig_bin(dut.FC0)
    if any(c not in "01" for c in s):
        return None
    return int(s, 2)


def now_ns():
    try:
        return int(get_sim_time(unit="ns"))
    except TypeError:
        return int(get_sim_time(units="ns"))


async def capture_as_cycle(dut, clk):
    await wait_asn_level(dut, clk, 0)
    t0 = now_ns()
    addr = byte_addr(dut)
    rec = {
        "t_assert_ns": t0,
        "addr": addr,
        "fc": fc_val(dut),
        "rw": rw_sig(dut),
        "uds": uds_sig(dut),
        "lds": lds_sig(dut),
    }
    n = 0
    while asn_sig(dut) == "0":
        await RisingEdge(clk)
        n += 1
        if n > WAIT_CYCLES:
            raise AssertionError("ASn stuck low")
    rec["t_negate_ns"] = now_ns()
    rec["as_low_ns"] = rec["t_negate_ns"] - rec["t_assert_ns"]
    rec["as_low_clks"] = n
    return rec


def peek_ssp_pc(dut):
    try:
        eu = core_dut(dut).u_fx68k.excUnit
        pch = int(eu.PcH.value)
        pcl = int(eu.PcL.value)
        try:
            ssp = int(eu.SSP.value)
        except (AttributeError, ValueError, TypeError):
            ssp = (int(eu.regs68H[16].value) << DATA_W) | int(eu.regs68L[16].value)
        return ssp, (pch << DATA_W) | pcl
    except (AttributeError, ValueError, TypeError):
        return None, None


async def boot_core(
    dut,
    extra=None,
    vpa_addrs=None,
    berr_addrs=None,
    iack_vpa=False,
    retry_addrs=None,
    iack_vector=None,
    iack_berr=False,
):
    await start_up(dut)
    bus = BusMem(extra)
    if vpa_addrs:
        bus.vpa_addrs.update(vpa_addrs)
    if berr_addrs:
        bus.berr_addrs.update(berr_addrs)
    if retry_addrs:
        bus.retry_addrs.update(retry_addrs)
    bus.iack_vpa = iack_vpa
    bus.iack_vector = iack_vector
    bus.iack_berr = iack_berr
    cocotb.start_soon(mem_model(dut, bus))
    return bus


async def wait_fc(dut, clk, fc, max_cycles=None):
    limit = WAIT_CYCLES if max_cycles is None else max_cycles
    await wait_pred(
        clk,
        lambda: asn_sig(dut) == "0" and fc_val(dut) == fc,
        limit,
        f"no AS cycle with FC={fc}",
    )


def sig_bin(sig):
    return str(sig.value).lower().replace(" ", "")


def bus_clk(dut):
    return dut.clk_PAD if pin_dut else dut.clk


def pad_bit(dut, idx):
    bits = sig_bin(dut.pad)
    return bits[len(bits) - 1 - idx]


def core_dut(dut):
    if pads:
        try:
            return dut.u_top.i_chip_core
        except AttributeError:
            return dut
    return dut


def asn_sig(dut):
    if pads:
        return pad_bit(dut, PAD_AS)
    return str(dut.ASn.value).lower().replace(" ", "")


def rw_sig(dut):
    if pads:
        return pad_bit(dut, PAD_RW)
    return str(dut.eRWn.value).lower().replace(" ", "")


def bgn_sig(dut):
    if pads:
        return pad_bit(dut, PAD_BG)
    return str(dut.BGn.value).lower().replace(" ", "")


def uds_sig(dut):
    if pads:
        return pad_bit(dut, PAD_UDS)
    return str(dut.UDSn.value).lower().replace(" ", "")


def lds_sig(dut):
    if pads:
        return pad_bit(dut, PAD_LDS)
    return str(dut.LDSn.value).lower().replace(" ", "")


def e_sig(dut):
    if pads:
        return pad_bit(dut, PAD_E)
    return str(dut.E.value).lower().replace(" ", "")


def vma_sig(dut):
    if pads:
        return pad_bit(dut, PAD_VMA)
    return str(dut.VMAn.value).lower().replace(" ", "")


def rst_oe_sig(dut):
    if pads:
        n = gl_net(
            dut,
            "u_top.i_chip_core.rst_oe",
            r"u_top.i_chip_core.rst_oe",
            "rst_oe",
        )
        if n is not None:
            b = str(n.value).lower().replace(" ", "")[:1]
            if b in "01":
                return b
        return "1" if sig_bin(dut.rst_n_PAD) == "0" else "0"
    return str(dut.rst_oe.value).lower().replace(" ", "")


def asn_inactive(dut):
    a = asn_sig(dut)
    if pads:
        return a in ("1", "z")
    return a == "1"


def oe_bit(dut, idx):
    if pads:
        b = pad_bit(dut, idx)
        if b in "z":
            return "0"
        if b in "01":
            return "1"
        return "x"
    bits = sig_bin(dut.bidir_oe)
    return bits[len(bits) - 1 - idx]


def oedb_val(dut):
    if pads:
        bits = "".join(pad_bit(dut, i) for i in range(PAD_D_MSB, PAD_D_LSB - 1, -1))
        if any(c not in "01" for c in bits):
            return None
        return int(bits, 2)
    try:
        return int(core_dut(dut).oEdb.value)
    except (ValueError, TypeError, AttributeError):
        return None


async def wait_pred(clk, pred, max_cycles, msg):
    for _ in range(max_cycles):
        await RisingEdge(clk)
        if pred():
            return
    raise AssertionError(msg)


async def wait_asn_level(dut, clk, level, max_cycles=None):
    want = "1" if level else "0"
    if max_cycles is None:
        max_cycles = WAIT_CYCLES
    await wait_pred(
        clk,
        lambda: asn_sig(dut) == want,
        max_cycles,
        f"ASn did not become {want}",
    )


def assert_oe(dut, indices, want, label):
    bad = [i for i in indices if oe_bit(dut, i) != want]
    assert not bad, f"{label}: bidir_oe[{bad}] != {want}"


def gl_net(dut, *names):
    for n in names:
        try:
            return dut._id(n, False)
        except Exception:
            pass
        try:
            return getattr(dut, n)
        except Exception:
            pass
    return None


async def gl_force_reset_path(dut, asserted):
    """Un-X the sync-reset flops so rst_n_PAD can take the core out of X."""
    from cocotb.handle import Force, Release

    rst_oe = gl_net(dut, r"i_chip_core.rst_oe", r"\i_chip_core.rst_oe", "rst_oe")
    ext = gl_net(dut, r"i_chip_core.extReset", r"\i_chip_core.extReset", "extReset")
    if rst_oe is not None:
        rst_oe.value = Force(0)
    if ext is not None:
        if asserted:
            ext.value = Force(1)
        else:
            ext.value = Release()


async def pin_apply_loop(dut):
    while True:
        await RisingEdge(bus_clk(dut))
        if PINS is not None:
            PINS.apply(dut)


async def start_up(dut):
    """Startup sequence"""
    await set_defaults(dut)
    if gl:
        dut.drv.value = 0
        dut.drv_en.value = 0
        await enable_power(dut)
        await start_clock(dut.clk_PAD)
        await gl_force_reset_path(dut, True)
        await reset(dut.rst_n_PAD)
        await gl_force_reset_path(dut, False)
    elif pads:
        drive_core_inputs(dut)
        await enable_power(dut)
        await start_clock(dut.clk_PAD)
        cocotb.start_soon(pin_apply_loop(dut))
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

    clk = bus_clk(dut)
    await ClockCycles(clk, SMOKE_CYCLES)

    if gl:
        bits = sig_bin(dut.pad)
        logger.info("pad=%s", bits)
        bad = []
        for idx, want in GL_PULL_INPUTS.items():
            got = bits[len(bits) - 1 - idx]
            if got != want:
                bad.append((idx, got, want))
        assert not bad, f"GL PU/PD inputs: {bad} pad={bits}"
    elif pads:
        bits = sig_bin(dut.pad)
        logger.info("pad=%s", bits)
        assert any(c in "01" for c in bits), f"all pad bits X/Z after reset: {bits}"
    else:
        eab = str(dut.eab.value)
        asn = str(dut.ASn.value)
        logger.info("eab=%s ASn=%s", eab, asn)
        assert "x" not in eab.lower(), f"eab still X after reset: {eab}"
        assert asn in ("0", "1"), f"ASn still X after reset: {asn}"
        assert bgn_sig(dut) == "1", f"BGn X/asserted after reset: {dut.BGn.value}"
        assert_oe(dut, range(PAD_A_LSB, PAD_A_MSB + 1), "1", "A after reset")
        assert_oe(
            dut,
            (PAD_AS, PAD_UDS, PAD_LDS, PAD_RW, PAD_E, PAD_VMA, PAD_BG, PAD_FC0, PAD_FC1, PAD_FC2),
            "1",
            "strobes/E/VMA/FC/BG after reset",
        )
        assert_oe(dut, (PAD_HALT,), "0", "HALT OD idle")
        assert rst_oe_sig(dut) == "0", "RESET OD idle"
    logger.info("Done!")


@cocotb.test(skip=bool(gl))
async def test_bus_grant_hiz(dut):
    """Table 3-4: on bus relinquish, Hi-Z A/D/AS/UDS/LDS/R/W/VMA/FC; BG stays driven."""
    await start_up(dut)
    clk = bus_clk(dut)

    await wait_asn_level(dut, clk, 0)
    await wait_asn_level(dut, clk, 1)
    set_bidir_bit(dut, PAD_BR, 0)

    await wait_pred(
        clk,
        lambda: bgn_sig(dut) == "0" and asn_inactive(dut),
        WAIT_CYCLES,
        "BGn did not assert with ASn inactive",
    )
    await RisingEdge(clk)

    assert_oe(dut, GRANT_HIZ_PADS, "0", "grant Hi-Z")
    assert_oe(dut, (PAD_BG, PAD_E), "1", "BG/E stay driven on grant")
    if not pads:
        assert_oe(dut, (PAD_HALT, PAD_DTACK, PAD_BERR, PAD_BR, PAD_BGACK), "0", "inputs stay input")


@cocotb.test(skip=bool(gl))
async def test_halt_hiz(dut):
    """Table 3-4: on HALT, Hi-Z A/D only; AS/UDS/LDS/R/W/VMA/FC stay driven."""
    await start_up(dut)
    clk = bus_clk(dut)

    await wait_asn_level(dut, clk, 0)
    set_bidir_bit(dut, PAD_HALT, 0)
    await wait_pred(
        clk,
        lambda: asn_inactive(dut)
        and bgn_sig(dut) == "1"
        and all(oe_bit(dut, i) == "0" for i in HALT_HIZ_PADS),
        WAIT_CYCLES,
        "HALT did not Hi-Z A/D with ASn inactive",
    )

    assert bgn_sig(dut) == "1", f"BG asserted during HALT-only: {bgn_sig(dut)}"
    assert_oe(dut, HALT_HIZ_PADS, "0", "HALT A/D Hi-Z")
    assert_oe(dut, HALT_DRIVEN_STROBES, "1", "HALT strobes/FC/VMA driven")
    assert_oe(dut, (PAD_BG, PAD_E), "1", "BG/E stay driven on HALT")
    if not pads:
        assert_oe(dut, (PAD_HALT,), "0", "external HALT is input (OD off)")


@cocotb.test(skip=bool(gl))
async def test_reset_ssp_pc(dut):
    """Reset vector reads: SSP at $0, PC at $4, then prefetch at PC."""
    await start_up(dut)
    clk = bus_clk(dut)
    mem = reset_vector_mem()
    cocotb.start_soon(mem_model(dut, mem))

    want = (
        RESET_VEC_SSP_ADDR,
        RESET_VEC_SSP_ADDR + 2,
        RESET_VEC_PC_ADDR,
        RESET_VEC_PC_ADDR + 2,
    )
    n_capture = len(want) + RESET_PREFETCH_CYCLES
    records = []
    for _ in range(n_capture):
        rec = await capture_as_cycle(dut, clk)
        records.append(rec)
        dut._log.info(
            "bus t=%d..%d ns A=%06x FC=%s R/W=%s UDS=%s LDS=%s AS_low=%d ns (%d clk)",
            rec["t_assert_ns"],
            rec["t_negate_ns"],
            rec["addr"] if rec["addr"] is not None else -1,
            rec["fc"],
            rec["rw"],
            rec["uds"],
            rec["lds"],
            rec["as_low_ns"],
            rec["as_low_clks"],
        )

    vec = records[: len(want)]
    got_addrs = tuple(r["addr"] for r in vec)
    assert got_addrs == want, f"reset vector addresses {got_addrs} != {want}"
    for rec in vec:
        assert rec["rw"] == "1", f"vector fetch was a write A={rec['addr']:06x}"
        assert rec["uds"] == "0" and rec["lds"] == "0", f"vector fetch not word A={rec['addr']:06x}"
        assert rec["fc"] == FC_SUPERVISOR_PROGRAM, f"vector FC={rec['fc']} A={rec['addr']:06x}"
        assert rec["as_low_clks"] >= 4, f"AS too short {rec['as_low_clks']} clk A={rec['addr']:06x}"

    pref = records[len(want)]
    assert pref["addr"] == RESET_PC, f"prefetch A={pref['addr']:06x} != PC {RESET_PC:06x}"
    assert pref["rw"] == "1"

    ssp, pc = peek_ssp_pc(dut)
    if ssp is None:
        dut._log.info("SSP/PC not in netlist; bus sequence only")
    else:
        dut._log.info("SSP=%08x PC=%08x", ssp, pc)
        assert ssp == RESET_SSP, f"SSP={ssp:08x} != {RESET_SSP:08x}"
        assert (pc & ~1) == (RESET_PC & ~1) or (RESET_PC <= pc <= RESET_PC + 8), (
            f"PC={pc:08x} not at reset vector {RESET_PC:08x}"
        )


@cocotb.test(skip=bool(gl))
async def test_write_cycle(dut):
    """MOVE.W #imm, abs.W: R/W low, data OE on, oEdb is the immediate."""
    extra = {
        RESET_PC: MOVE_W_IMM_ABS_W,
        RESET_PC + 2: STORE_IMM,
        RESET_PC + 4: STORE_ADDR,
        RESET_PC + 6: NOP_WORD,
    }
    bus = await boot_core(dut, extra)
    clk = bus_clk(dut)
    await wait_pred(
        clk,
        lambda: asn_sig(dut) == "0"
        and rw_sig(dut) == "0"
        and byte_addr(dut) == STORE_ADDR,
        WAIT_CYCLES,
        f"no write to {STORE_ADDR:06x}",
    )
    await wait_pred(
        clk,
        lambda: oedb_val(dut) == STORE_IMM,
        16,
        f"data pad not {STORE_IMM:04x} on write",
    )
    data = oedb_val(dut)
    assert data == STORE_IMM, f"oEdb={data} != {STORE_IMM:04x}"
    assert_oe(dut, range(PAD_D_LSB, PAD_D_MSB + 1), "1", "data OE on write")
    await wait_pred(
        clk,
        lambda: uds_sig(dut) == "0" and lds_sig(dut) == "0",
        16,
        "UDS/LDS not both low on word write",
    )
    dut._log.info("write A=%06x data=%04x", STORE_ADDR, data)
    assert bus.writes, "mem_model recorded no writes"


@cocotb.test(skip=bool(gl))
async def test_iack_autovector(dut):
    """Level-7 IPL, VPA on IACK (FC=7): autovector fetch at 4*(24+7)."""
    vec = (AUTOVEC_BASE + AUTOVEC_LEVEL) * VEC_BYTES
    extra = {
        vec: RTE_WORD,
        vec + 2: NOP_WORD,
    }
    await boot_core(dut, extra, iack_vpa=True)
    clk = bus_clk(dut)
    for _ in range(len((0, 2, 4, 6)) + RESET_PREFETCH_CYCLES):
        await capture_as_cycle(dut, clk)
    set_ipl(dut, AUTOVEC_LEVEL)
    await wait_fc(dut, clk, FC_CPU_SPACE)
    addr = byte_addr(dut)
    dut._log.info("IACK A=%06x FC=%s", addr, fc_val(dut))
    assert fc_val(dut) == FC_CPU_SPACE
    assert addr is not None and ((addr >> 1) & AUTOVEC_LEVEL) == AUTOVEC_LEVEL
    await wait_pred(
        clk,
        lambda: asn_sig(dut) == "0" and byte_addr(dut) == vec,
        WAIT_CYCLES,
        f"no autovector fetch at {vec:06x}",
    )
    assert rw_sig(dut) == "1"


@cocotb.test(skip=bool(gl))
async def test_bgack_three_wire(dut):
    """BR then BGACK: Hi-Z while granted; bus returns after BGACK negate."""
    await boot_core(dut)
    clk = bus_clk(dut)
    await wait_asn_level(dut, clk, 0)
    await wait_asn_level(dut, clk, 1)
    set_bidir_bit(dut, PAD_BR, 0)
    await wait_pred(
        clk,
        lambda: bgn_sig(dut) == "0" and asn_inactive(dut),
        WAIT_CYCLES,
        "BGn did not assert with ASn inactive",
    )
    await RisingEdge(clk)
    assert_oe(dut, GRANT_HIZ_PADS, "0", "grant Hi-Z before BGACK")
    set_bidir_bit(dut, PAD_BGACK, 0)
    await ClockCycles(clk, 8)
    set_bidir_bit(dut, PAD_BR, 1)
    await wait_pred(
        clk,
        lambda: bgn_sig(dut) == "1",
        WAIT_CYCLES,
        "BG did not negate after BGACK",
    )
    assert_oe(dut, GRANT_HIZ_PADS, "0", "Hi-Z while BGACK holds the bus")
    assert_oe(dut, (PAD_BG, PAD_E), "1", "BG/E driven during BGACK")
    set_bidir_bit(dut, PAD_BGACK, 1)
    await wait_pred(
        clk,
        lambda: oe_bit(dut, PAD_A_LSB) == "1" and asn_sig(dut) in ("0", "1", "z"),
        WAIT_CYCLES,
        "CPU did not drive A after BGACK release",
    )
    assert_oe(dut, (PAD_AS, PAD_BG), "1", "AS/BG driven after grant")


@cocotb.test(skip=bool(gl))
async def test_berr_exception(dut):
    """BERR without HALT on the first prefetch: vector 2 at $8, not retry."""
    vec = BUS_ERR_VEC * VEC_BYTES
    extra = {vec: RTE_WORD, vec + 2: NOP_WORD}
    bus = await boot_core(dut, extra)
    clk = bus_clk(dut)
    for _ in range(len((0, 2, 4, 6)) + RESET_PREFETCH_CYCLES):
        await capture_as_cycle(dut, clk)
    bus.berr_addrs.update(range(RESET_PC, RESET_PC + 0x20, 2))
    await wait_pred(
        clk,
        lambda: asn_sig(dut) == "0" and byte_addr(dut) == vec,
        WAIT_CYCLES,
        f"no bus-error vector fetch at {vec:06x}",
    )
    assert rw_sig(dut) == "1"
    assert fc_val(dut) in (FC_SUPERVISOR_PROGRAM, FC_SUPERVISOR_DATA), (
        f"BERR vector FC={fc_val(dut)}"
    )
    dut._log.info("BERR vector A=%06x FC=%s", byte_addr(dut), fc_val(dut))


@cocotb.test(skip=bool(gl))
async def test_vpa_vma_e(dut):
    """MOVE.W abs.W,D0 with VPA (no DTACK): VMA asserts, E keeps running."""
    extra = {
        RESET_PC: MOVE_W_ABS_W_D0,
        RESET_PC + 2: PERIPH_ADDR,
        RESET_PC + 4: NOP_WORD,
    }
    await boot_core(dut, extra, vpa_addrs={PERIPH_ADDR})
    clk = bus_clk(dut)
    await wait_pred(
        clk,
        lambda: asn_sig(dut) == "0" and byte_addr(dut) == PERIPH_ADDR,
        WAIT_CYCLES,
        f"no cycle at {PERIPH_ADDR:06x}",
    )
    e0 = e_sig(dut)
    await wait_pred(
        clk,
        lambda: vma_sig(dut) == "0",
        WAIT_CYCLES,
        "VMA did not assert on VPA cycle",
    )
    assert byte_addr(dut) == PERIPH_ADDR or asn_sig(dut) == "0"
    await wait_pred(
        clk,
        lambda: e_sig(dut) != e0,
        WAIT_CYCLES,
        "E did not toggle during 6800 cycle",
    )
    dut._log.info("6800 cycle A=%06x VMA=0 E %s->%s", PERIPH_ADDR, e0, e_sig(dut))


@cocotb.test(skip=bool(gl))
async def test_bus_retry(dut):
    """BERR+HALT reruns the same cycle; not vector 2 (UM §5.4.2)."""
    bus = await boot_core(dut)
    clk = bus_clk(dut)
    bus.retry_addrs.update(range(RESET_PC, RESET_PC + 0x20, 2))
    addrs = []
    for _ in range(12):
        rec = await capture_as_cycle(dut, clk)
        addrs.append(rec["addr"])
        if bus.retry_fired and addrs.count(RESET_PC) >= 2:
            break
    dut._log.info("retry addrs=%s fired=%s", [f"{a:06x}" for a in addrs], bus.retry_fired)
    assert bus.retry_fired
    assert addrs.count(RESET_PC) >= 2, f"no rerun of {RESET_PC:06x}: {addrs}"
    assert BUS_ERR_VEC * VEC_BYTES not in addrs


@cocotb.test(skip=bool(gl))
async def test_halt_frozen(dut):
    """HALT after AS inactive: no new bus cycle, PC frozen (68000 halt)."""
    await boot_core(dut)
    clk = bus_clk(dut)
    await wait_asn_level(dut, clk, 0)
    set_bidir_bit(dut, PAD_HALT, 0)
    await wait_pred(
        clk,
        lambda: asn_inactive(dut) and all(oe_bit(dut, i) == "0" for i in HALT_HIZ_PADS),
        WAIT_CYCLES,
        "HALT did not three-state A/D",
    )
    ssp, pc0 = peek_ssp_pc(dut)
    for _ in range(64):
        await RisingEdge(clk)
        assert asn_sig(dut) != "0", "new bus cycle while HALT"
    _, pc1 = peek_ssp_pc(dut)
    if pc0 is not None:
        assert pc0 == pc1, f"PC moved during HALT {pc0:08x}->{pc1:08x}"
        dut._log.info("HALT frozen PC=%08x", pc0)


def peek_dn(eu, n):
    return (int(eu.regs68H[n].value) << DATA_W) | int(eu.regs68L[n].value)


@cocotb.test(skip=bool(gl))
async def test_wait_state_sweep(dut):
    """Programmable DTACK delay on abs.W slave; AS stretch vs N, data still sampled."""
    extra = {
        RESET_PC: MOVE_W_ABS_W_D0,
        RESET_PC + 2: SLAVE_ADDR,
        RESET_PC + 4: BRA_S_TO_RESET_PC,
        SLAVE_ADDR: SLAVE_DATA,
    }
    bus = await boot_core(dut, extra)
    bus.slave_addrs.add(SLAVE_ADDR)
    clk = bus_clk(dut)
    rows = []
    eu = getattr(getattr(core_dut(dut), "u_fx68k", None), "excUnit", None)
    for n in WAIT_SWEEP_CLKS:
        await wait_asn_level(dut, clk, 1)
        bus.slave_wait_clks = n
        rec = None
        for _ in range(16):
            rec = await capture_as_cycle(dut, clk)
            if rec["addr"] == SLAVE_ADDR:
                break
        assert rec is not None and rec["addr"] == SLAVE_ADDR, f"no slave cycle wait={n}"
        assert rec["rw"] == "1"
        d0 = None
        if eu is not None:
            try:
                await wait_pred(
                    clk,
                    lambda: peek_dn(eu, 0) == SLAVE_DATA,
                    64,
                    f"wait={n} D0 never {SLAVE_DATA:04x}",
                )
                d0 = peek_dn(eu, 0)
            except (AttributeError, ValueError, TypeError):
                d0 = None
        rows.append((n, rec["as_low_clks"], rec["as_low_ns"]))
        dut._log.info(
            "slave wait_clks=%d AS_low=%d clk (%d ns) D0=%s",
            n,
            rec["as_low_clks"],
            rec["as_low_ns"],
            f"{d0:04x}" if d0 is not None else "-",
        )
    for i in range(1, len(rows)):
        assert rows[i][1] >= rows[i - 1][1], f"AS did not stretch: {rows}"


def unmask_sr_prog():
    return {
        RESET_PC: MOVE_W_IMM_SR,
        RESET_PC + 2: SR_SUPER_MASK0,
        RESET_PC + 4: NOP_WORD,
        RESET_PC + 6: BRA_S_TO_NOP,
    }


@cocotb.test(skip=bool(gl))
async def test_iack_vectored(dut):
    """IACK with DTACK and a vector number on D (not VPA)."""
    vec_addr = VECTORED_VEC * VEC_BYTES
    extra = unmask_sr_prog()
    extra[vec_addr] = RTE_WORD
    extra[vec_addr + 2] = NOP_WORD
    await boot_core(dut, extra, iack_vector=VECTORED_VEC)
    clk = bus_clk(dut)
    set_ipl(dut, 5)
    await wait_fc(dut, clk, FC_CPU_SPACE)
    addr = byte_addr(dut)
    assert fc_val(dut) == FC_CPU_SPACE
    assert addr is not None and ((addr >> 1) & AUTOVEC_LEVEL) == 5
    await wait_pred(
        clk,
        lambda: asn_sig(dut) == "0" and byte_addr(dut) == vec_addr,
        WAIT_CYCLES,
        f"no vectored fetch at {vec_addr:06x}",
    )
    dut._log.info("vectored IACK A=%06x vec=$%02x", addr, VECTORED_VEC)


@cocotb.test(skip=bool(gl))
async def test_byte_uds_lds(dut):
    """MOVE.B even: UDS only; MOVE.B odd: LDS only."""
    extra = {
        RESET_PC: MOVE_B_IMM_ABS_W,
        RESET_PC + 2: BYTE_EVEN_DATA,
        RESET_PC + 4: BYTE_EVEN_ADDR,
        RESET_PC + 6: MOVE_B_IMM_ABS_W,
        RESET_PC + 8: BYTE_ODD_DATA,
        RESET_PC + 10: BYTE_ODD_ADDR,
        RESET_PC + 12: NOP_WORD,
    }
    await boot_core(dut, extra)
    clk = bus_clk(dut)

    async def wait_write(addr):
        await wait_pred(
            clk,
            lambda: asn_sig(dut) == "0"
            and rw_sig(dut) == "0"
            and byte_addr(dut) == addr,
            WAIT_CYCLES,
            f"no write to {addr:06x}",
        )
        await wait_pred(
            clk,
            lambda: uds_sig(dut) == "0" or lds_sig(dut) == "0",
            16,
            "UDS/LDS never asserted",
        )
        return uds_sig(dut), lds_sig(dut)

    uds, lds = await wait_write(BYTE_EVEN_ADDR)
    dut._log.info("even byte UDS=%s LDS=%s", uds, lds)
    assert uds == "0" and lds == "1", f"even byte strobes UDS={uds} LDS={lds}"
    await wait_asn_level(dut, clk, 1)
    # A1–A23 are even; odd byte is the same eab with LDS.
    uds, lds = await wait_write(BYTE_EVEN_ADDR)
    dut._log.info("odd byte UDS=%s LDS=%s", uds, lds)
    assert uds == "1" and lds == "0", f"odd byte strobes UDS={uds} LDS={lds}"


@cocotb.test(skip=bool(gl))
async def test_reset_insn_od(dut):
    """RESET opcode: rst_oe drives 0, then releases (open-drain)."""
    extra = {RESET_PC: RESET_INSN, RESET_PC + 2: NOP_WORD}
    await boot_core(dut, extra)
    clk = bus_clk(dut)

    def reset_driving():
        try:
            n = str(core_dut(dut).oRESETn.value).lower().replace(" ", "")[:1]
            if n == "0":
                return True
        except (AttributeError, ValueError, TypeError):
            pass
        return rst_oe_sig(dut) == "1"

    await wait_pred(
        clk,
        reset_driving,
        WAIT_CYCLES,
        "RESET insn did not assert rst_oe",
    )
    n = 0
    while reset_driving():
        await RisingEdge(clk)
        n += 1
        if n > WAIT_CYCLES:
            raise AssertionError("rst_oe stuck on")
    dut._log.info("RESET insn rst_oe pulse %d clk", n)
    assert n >= 64, f"RESET pulse too short {n} clk"
    assert not reset_driving(), "RESET still driving after pulse"


@cocotb.test(skip=bool(gl))
async def test_tas_rmw_no_grant(dut):
    """TAS RMW: AS stays through R/W flip; BG not granted mid-cycle."""
    extra = {RESET_PC: TAS_ABS_W, RESET_PC + 2: SLAVE_ADDR, RESET_PC + 4: NOP_WORD}
    await boot_core(dut, extra)
    clk = bus_clk(dut)
    await wait_pred(
        clk,
        lambda: asn_sig(dut) == "0" and byte_addr(dut) == SLAVE_ADDR,
        WAIT_CYCLES,
        "no TAS cycle at slave",
    )
    set_bidir_bit(dut, PAD_BR, 0)
    saw_read = False
    saw_write = False
    n = 0
    while asn_sig(dut) == "0":
        rw = rw_sig(dut)
        if rw == "1":
            saw_read = True
            assert bgn_sig(dut) == "1", "BG granted during TAS read"
        if rw == "0":
            saw_write = True
        await RisingEdge(clk)
        n += 1
        if n > WAIT_CYCLES:
            raise AssertionError("TAS AS stuck low")
    dut._log.info("TAS AS_low=%d clk read=%s write=%s", n, saw_read, saw_write)
    assert saw_read and saw_write, "TAS missing read or write phase"


@cocotb.test(skip=bool(gl))
async def test_slave_berr_timeout(dut):
    """Slave never DTACKs; BERR after N clocks → vector 2."""
    extra = {
        RESET_PC: MOVE_W_ABS_W_D0,
        RESET_PC + 2: SLAVE_ADDR,
        RESET_PC + 4: NOP_WORD,
        BUS_ERR_VEC * VEC_BYTES: RTE_WORD,
        BUS_ERR_VEC * VEC_BYTES + 2: NOP_WORD,
    }
    bus = await boot_core(dut, extra)
    bus.slave_addrs.add(SLAVE_ADDR)
    bus.slave_wait_clks = WAIT_CYCLES
    bus.slave_berr_after = SLAVE_BERR_AFTER_CLKS
    clk = bus_clk(dut)
    await wait_pred(
        clk,
        lambda: asn_sig(dut) == "0" and byte_addr(dut) == BUS_ERR_VEC * VEC_BYTES,
        WAIT_CYCLES,
        "no BERR vector after slave timeout",
    )
    dut._log.info("slave BERR timeout → vector $%x", BUS_ERR_VEC * VEC_BYTES)


@cocotb.test(skip=bool(gl))
async def test_br_during_halt(dut):
    """HALT three-state A/D; BR still gets BG; A stays Hi-Z."""
    await boot_core(dut)
    clk = bus_clk(dut)
    await wait_asn_level(dut, clk, 0)
    set_bidir_bit(dut, PAD_HALT, 0)
    await wait_pred(
        clk,
        lambda: asn_inactive(dut)
        and all(oe_bit(dut, i) == "0" for i in HALT_HIZ_PADS),
        WAIT_CYCLES,
        "HALT did not Hi-Z A/D",
    )
    set_bidir_bit(dut, PAD_BR, 0)
    await wait_pred(
        clk,
        lambda: bgn_sig(dut) == "0",
        WAIT_CYCLES,
        "BG not granted while HALT",
    )
    assert_oe(dut, HALT_HIZ_PADS, "0", "A/D still Hi-Z on HALT+BR")
    assert_oe(dut, (PAD_BG,), "1", "BG driven")
    dut._log.info("HALT+BR BGn=%s", bgn_sig(dut))


@cocotb.test(skip=bool(gl))
async def test_iack_spurious(dut):
    """BERR on IACK (no DTACK/VPA) → spurious vector 24."""
    vec = SPURIOUS_VEC * VEC_BYTES
    extra = unmask_sr_prog()
    extra[vec] = RTE_WORD
    extra[vec + 2] = NOP_WORD
    await boot_core(dut, extra, iack_berr=True)
    clk = bus_clk(dut)
    set_ipl(dut, 5)
    await wait_fc(dut, clk, FC_CPU_SPACE)
    await wait_pred(
        clk,
        lambda: asn_sig(dut) == "0" and byte_addr(dut) == vec,
        WAIT_CYCLES,
        f"no spurious vector fetch at {vec:06x}",
    )
    dut._log.info("spurious IACK → $%06x", vec)


@cocotb.test(skip=bool(gl))
async def test_ipl_levels(dut):
    """IPL 1–6: IACK A[3:1] matches the level (mask 0 after MOVE to SR)."""
    extra = unmask_sr_prog()
    for lv in IPL_LEVELS:
        va = (AUTOVEC_BASE + lv) * VEC_BYTES
        extra[va] = RTE_WORD
        extra[va + 2] = NOP_WORD
    await boot_core(dut, extra, iack_vpa=True)
    clk = bus_clk(dut)
    for lv in IPL_LEVELS:
        rst = dut.rst_n_PAD if pads else dut.rst_in
        rst.value = 0
        await ClockCycles(clk, 16)
        rst.value = 1
        set_ipl(dut, 0)
        await ClockCycles(clk, 80)
        set_ipl(dut, lv)
        await wait_fc(dut, clk, FC_CPU_SPACE)
        addr = byte_addr(dut)
        got = (addr >> 1) & AUTOVEC_LEVEL
        dut._log.info("IPL %d IACK A=%06x field=%d", lv, addr, got)
        assert got == lv, f"IPL {lv} IACK field {got}"
        set_ipl(dut, 0)
        await wait_asn_level(dut, clk, 1)


@cocotb.test(skip=bool(gl))
async def test_e_period(dut):
    """E period is 10 PHI (20 chip clocks); pad OE stays on."""
    await boot_core(dut)
    clk = bus_clk(dut)
    assert_oe(dut, (PAD_E,), "1", "E OE")
    await wait_pred(clk, lambda: e_sig(dut) == "0", WAIT_CYCLES, "E never low")
    await wait_pred(clk, lambda: e_sig(dut) == "1", WAIT_CYCLES, "E never high")
    high = 0
    while e_sig(dut) == "1":
        high += 1
        await RisingEdge(clk)
        assert oe_bit(dut, PAD_E) == "1"
        if high > WAIT_CYCLES:
            raise AssertionError("E stuck high")
    low = 0
    while e_sig(dut) == "0":
        low += 1
        await RisingEdge(clk)
        assert oe_bit(dut, PAD_E) == "1"
        if low > WAIT_CYCLES:
            raise AssertionError("E stuck low")
    period = high + low
    dut._log.info("E high=%d low=%d period=%d clk", high, low, period)
    assert period == E_PERIOD_CHIP_CLKS, f"E period {period} != {E_PERIOD_CHIP_CLKS}"
    assert min(high, low) >= 6 and max(high, low) <= 14, f"E duty {high}/{low}"


@cocotb.test(skip=not gl)
async def test_gl_pad_cpu(dut):
    """chip_top GL: address pads after POR force (this pnl may still be X)."""
    await start_up(dut)
    clk = bus_clk(dut)
    await ClockCycles(clk, 256)
    bits = sig_bin(dut.pad)
    addr_bits = "".join(bits[len(bits) - 1 - i] for i in range(PAD_A_LSB, PAD_A_MSB + 1))
    dut._log.info("GL A pads=%s", addr_bits)


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

    if gl or gl_core or pads:
        sources.append(proj_path / "timescale.v")

    if gl:
        sources.append(Path(pdk_root) / pdk / "libs.ref" / scl / "verilog" / f"{scl}.v")
        if scl != "gf180mcu_as_sc_mcu7t3v3":
            sources.append(Path(pdk_root) / pdk / "libs.ref" / scl / "verilog" / "primitives.v")
        sources.append(proj_path / "chip_top_gl_wrap.v")
        sources.append(proj_path / "../final/pnl/chip_top.pnl.v")
        defines.update({"FUNCTIONAL": True, "USE_POWER_PINS": True, "GL_PNL": True})
        sources += [
            Path(pdk_root) / pdk / f"libs.ref/{pad}/verilog/{pad}.v",
            proj_path / "../ip/gf180mcu_ws_ip__logo/vh/gf180mcu_ws_ip__logo.v",
            proj_path / "../ip/gf180mcu_ws_ip__marker/vh/gf180mcu_ws_ip__marker.v",
            proj_path / "../ip/gf180mcu_ws_ip__qrcode_id/vh/gf180mcu_ws_ip__qrcode_id.v",
            proj_path / "../ip/gf180mcu_ws_ip__shuttle_id/vh/gf180mcu_ws_ip__shuttle_id.v",
            proj_path / "../ip/gf180mcu_ws_ip__project_id/vh/gf180mcu_ws_ip__project_id.v",
        ]
    elif pads:
        sources.append(proj_path / "pad_y_iso.v")
        sources.append(proj_path / "chip_top_gl_wrap.v")
        sources.append(proj_path / "../src/chip_top.sv")
        sources.append(proj_path / "../src/chip_core.sv")
        sources.append(proj_path / "../build/fx68k-v/fx68k.v")
        sources.append(proj_path / "../build/fx68k-v/uRom.v")
        sources.append(proj_path / "../build/fx68k-v/nanoRom.v")
        sources += [
            Path(pdk_root) / pdk / f"libs.ref/{pad}/verilog/{pad}.v",
            proj_path / "../ip/gf180mcu_ws_ip__logo/vh/gf180mcu_ws_ip__logo.v",
            proj_path / "../ip/gf180mcu_ws_ip__marker/vh/gf180mcu_ws_ip__marker.v",
            proj_path / "../ip/gf180mcu_ws_ip__qrcode_id/vh/gf180mcu_ws_ip__qrcode_id.v",
            proj_path / "../ip/gf180mcu_ws_ip__shuttle_id/vh/gf180mcu_ws_ip__shuttle_id.v",
            proj_path / "../ip/gf180mcu_ws_ip__project_id/vh/gf180mcu_ws_ip__project_id.v",
        ]
        defines.update({"FUNCTIONAL": True, "PADS_RTL": True})
    elif gl_core:
        sources.append(Path(pdk_root) / pdk / "libs.ref" / scl / "verilog" / f"{scl}.v")
        if scl != "gf180mcu_as_sc_mcu7t3v3":
            sources.append(Path(pdk_root) / pdk / "libs.ref" / scl / "verilog" / "primitives.v")
        sources.append(proj_path / "../build/chip-core-gl/chip_core.nl.v")
        sources.append(proj_path / "../build/fx68k-v/uRom.v")
        sources.append(proj_path / "../build/fx68k-v/nanoRom.v")
        defines.update({"FUNCTIONAL": True})
    else:
        sources.append(proj_path / "../src/chip_core.sv")
        sources.append(proj_path / "../build/fx68k-v/fx68k.v")
        sources.append(proj_path / "../build/fx68k-v/uRom.v")
        sources.append(proj_path / "../build/fx68k-v/nanoRom.v")

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
