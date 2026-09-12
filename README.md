# fx68k wafer.space chip (GF180MCU)

[gf180mcu-project-template](https://github.com/wafer-space/gf180mcu-project-template)
with [fx68k](https://github.com/ijor/fx68k) in `chip_core`. The core ASIC flow
lives in the `fx68k/` submodule (`https://github.com/erique/fx68k-gf180`).

## Dependencies

Docker matches `.github/workflows/ci.yml`: Ubuntu 24.04, Determinate Nix,
fossi cache, then `nix develop --command make …`.

```sh
git submodule update --init
./docker.sh build
./docker.sh make clone-pdk
./docker.sh make librelane-condensed
```

Host Nix: same commands without Docker (`nix develop --command make clone-pdk`).

## Pad map (1x1, 74-ball LGA)

CLK = `clk_PAD`. RESET = `rst_n_PAD` (bidir, CPU may pull low).

`bidir_PAD[57:0]`: A1–A23 `[22:0]`, D0–D15 `[38:23]`, AS/UDS/LDS/R/W `[39:42]`,
DTACK/BERR/HALT `[43:45]`, VPA/E/VMA `[46:48]`, FC0–2 `[49:51]`,
BR/BG/BGACK `[52:54]`, IPL0–2 `[55:57]`.

Four former I/O DVDD sites are GPIO. The stock wafer.space COB straps those
balls to 5 V; a full 68000 pinout needs a carrier that does not.

Pad OE (`chip_core` `bidir_oe`) follows MC68000UM Table 3-4 (68000 pins, not
68008 A0/DS/MODE). Socket 5 V / UM AC ns is not this block.

| Mnemonic | RTL | Pad OE vs Table 3-4 | Test |
| --- | --- | --- | --- |
| A1–A23 | `eab` | Hi-Z on HALT (AS negated) and on bus grant (`BGn` & AS negated) | reset smoke; halt; grant |
| D0–D15 | `oEdb` / `iEdb` | Write-only (`~eRWn`) plus same Hi-Z as A | reset smoke; halt; grant |
| AS, R/W, UDS, LDS | `ASn` `eRWn` `UDSn` `LDSn` | Driven on HALT; Hi-Z on bus grant | halt; grant |
| VMA, FC0–2 | `VMAn` `FC*` | Driven on HALT; Hi-Z on bus grant | halt; grant |
| BG | `BGn` | Driven (not Hi-Z on grant) | grant |
| E | `E` | Driven (not Hi-Z) | grant; halt |
| RESET, HALT | `oRESETn` `oHALTEDn` | Open-drain: drive 0 only (`=== 1'b0` OE) | reset smoke; halt |
| DTACK, BR, BGACK, IPL, BERR, VPA, CLK | inputs / CLK | Input or clock; no Hi-Z columns | driven as inputs in TB |

`fx68k` HALTn is single-step: new bus cycles are blocked (`busAvail` includes
Halti). It is not a full 68000 halt of the execution unit. Pad A/D Hi-Z when
Halti or `oHALTEDn` is low and AS is negated.

Not on this die as 68000-complete:

- Bus retry (`BERR`+`HALT`, not address error, not RMW): fx68k ties
  `busRetry` to 0.
- fx68k `addrOe` / `dataOe` are internal only; pad data OE is `~eRWn` when
  not Hi-Z.
- 6800 `E`/`VMA`/`VPA` (and autovector on VPA during IACK) exist in the
  core; no cocotb for that protocol.

Grant/halt three-state is extra OE on A, D, AS, UDS, LDS, R/W, VMA, FC.
`librelane/chip_top.sdc` uses UM output_delay on those pads; Hi-Z delay is
not in that file.

## Timing

`clk_PAD` is 50 ns (20 MHz die clock) = 2× 68000 PHI = 10 MHz
68000-equivalent (`enPhi1`/`enPhi2` /2 in `chip_core`). Slack at 50 ns is
not Fmax.

Sign-off SDC is `librelane/chip_top.sdc`: UM Ninth Edition §10.10 10 MHz
column pad AC vs `clk_PAD` / `bidir_PAD` / `rst_n_PAD`, plus core
Ir→microAddr/nanoAddr multicycle from `fx68k/constraints/fx68k.sdc`.
Typical-only quit policy (`TIMING_VIOLATION_CORNERS` `*tt*`); SS setup can
fail while the run is green. That is not SS sign-off and not a claim that
the 68000 bus is closed.

## Prerequisites

The project template uses the open_pdks gf180mcuD variant of the PDK.
To clone the latest PDK version via [Ciel](https://github.com/fossi-foundation/ciel), run `make clone-pdk`.

## Implement the Design

With the Nix shell enabled, run the implementation:

```
make librelane
```

You can find all output artifacts in the `librelane/runs/<timestamp>/` directory.

## View the Design

After completion, you can view the design using the OpenROAD GUI:

```
make librelane-openroad
```

Or using KLayout:

```
make librelane-klayout
```

## Verification and Simulation

For the verification of the chip we use [cocotb](https://www.cocotb.org/). Cocotb is a Python-based testbench environment. The simulator that is used by the project template is [Icarus Verilog](https://github.com/steveicarus/iverilog).

The testbench is located in `cocotb/chip_top_tb.py`. To run the RTL simulation, run the following command:

```
make sim
```

To run the GL (gate-level) simulation, run the following command:

```
make sim-gl
```

> [!NOTE]
> You need to have the latest implementation of your design in the `final/` folder. After a run has completed without errors, the final views will be copied to `final/`.

In both cases, a waveform file will be generated under `cocotb/sim_build/chip_top.fst`.
You can view it using a waveform viewer, for example, [GTKWave](https://gtkwave.github.io/gtkwave/).

```
make sim-view
```

You can now update the testbench according to your design.

## Implementing Your Own Design

The source files for this template can be found in the `src/` directory. `chip_top.sv` defines the top-level ports and instantiates `chip_core`, chip ID (QR code) and the wafer.space logo. To allow for the default bonding setup, do not change the number of pads in order to keep the original bondpad positions. To be compatible with the default breakout PCB, do not change any of the power or ground pads. However, you can change the type of the signal pads, e.g. to bidirectional, input-only or e.g. analog pads. The template provides the `NUM_INPUT` and `NUM_BIDIR` parameters for this purpose.

The actual pad positions are defined in the LibreLane configuration file under `librelane/config.yaml`. The variables `PAD_SOUTH`/`PAD_EAST`/`PAD_NORTH`/`PAD_WEST` determine the respective pad placement. The LibreLane configuration also allows you to customize the flow (enable or disable steps), specify the source files, set various variables for the steps, and instantiate macros. For more information about the configuration, please refer to the LibreLane documentation: https://librelane.readthedocs.io/en/latest/

To implement your own design, simply edit `chip_core.sv`. The `chip_core` module receives the clock and reset, as well as the signals from the pads defined in `chip_top`. As an example, a 42-bit wide counter is implemented.

> [!NOTE]
> For more comprehensive SystemVerilog support, enable the `USE_SLANG` variable in the LibreLane configuration.

## Choosing a Different Slot Size

The template supports the following slot sizes: `1x1`, `0p5x1`, `1x0p5`, `0p5x0p5`.
By default, the design is implemented using the `1x1` slot definition.

To select a different slot size, simply set the `SLOT` environment variable.
This can be done when invoking a make target:

```
SLOT=0p5x0p5 make librelane
```

Alternatively, you can export the slot size:

```
export SLOT=0p5x0p5
```

You can change the slot that is selected by default in the Makefile by editing the value of `DEFAULT_SLOT`.

## Select Different IP Libraries

The project template has support for selecting libraries with the below environment variables:

| Env  | Available Values                                                          | Description                |
|------|---------------------------------------------------------------------------|----------------------------|
| SCL  | gf180mcu_fd_sc_mcu7t5v0, gf180mcu_fd_sc_mcu9t5v0, gf180mcu_as_sc_mcu7t3v3 | The standard cell library. |
| PAD  | gf180mcu_fd_io, gf180mcu_ocd_io                                           | The I/O pad library.       |
| SRAM | gf180mcu_fd_ip_sram, gf180mcu_ocd_ip_sram                                 | The SRAM library.          |

For example, to build the 0p5x0p5 chip with 3v3 libraries:

```
SLOT=0p5x0p5 SCL=gf180mcu_as_sc_mcu7t3v3 PAD=gf180mcu_ocd_io SRAM=gf180mcu_ocd_ip_sram make librelane
```

The default values can be changed in the Makefile.

> [!NOTE]
> Not all of the community-created IPs have been tested yet, so support for them is experimental!

## Building a Standalone Padring for Analog Design

To build just the padring without any standard cell rows, digital routing or filler cells, run the following command:

```
make librelane-padring
```

It is also possible to build the padring for other slot sizes:

```
SLOT=0p5x0p5 make librelane-padring
```

## Precheck

To check whether your design is suitable for manufacturing, run the [gf180mcu-precheck](https://github.com/wafer-space/gf180mcu-precheck) with your layout.
