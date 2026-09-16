// SPDX-FileCopyrightText: © 2025 Project Template Contributors
// SPDX-License-Identifier: Apache-2.0

`default_nettype none

`include "generated_defines.svh"
`include "slot_defines.svh"

`ifdef PAD_gf180mcu_ocd_io
`define gf180mcu_xxx_io__vdd gf180mcu_ocd_io__vdd
`define gf180mcu_xxx_io__vss gf180mcu_ocd_io__vss
`define gf180mcu_xxx_io__dvdd gf180mcu_ocd_io__dvdd
`define gf180mcu_xxx_io__dvss gf180mcu_ocd_io__dvss
`define gf180mcu_xxx_io__in_s gf180mcu_ocd_io__in_s
`define gf180mcu_xxx_io__in_c gf180mcu_ocd_io__in_c
`define gf180mcu_xxx_io__bi_24t gf180mcu_ocd_io__bi_24t
`define gf180mcu_xxx_io__asig_5p0 gf180mcu_ocd_io__asig_5p0
`else
`define gf180mcu_xxx_io__vdd gf180mcu_fd_io__dvdd
`define gf180mcu_xxx_io__vss gf180mcu_fd_io__dvss
`define gf180mcu_xxx_io__dvdd gf180mcu_fd_io__dvdd
`define gf180mcu_xxx_io__dvss gf180mcu_fd_io__dvss
`define gf180mcu_xxx_io__in_s gf180mcu_fd_io__in_s
`define gf180mcu_xxx_io__in_c gf180mcu_fd_io__in_c
`define gf180mcu_xxx_io__bi_24t gf180mcu_fd_io__bi_24t
`define gf180mcu_xxx_io__asig_5p0 gf180mcu_fd_io__asig_5p0
`endif

module chip_top #(
    // Power/ground pads for I/O
    parameter NUM_DVDD_PADS = `NUM_DVDD_PADS,
    parameter NUM_DVSS_PADS = `NUM_DVSS_PADS,

    // Power/ground pads for core
    parameter NUM_VDD_PADS = `NUM_VDD_PADS,
    parameter NUM_VSS_PADS = `NUM_VSS_PADS,

    // Signal pads
    parameter NUM_INPUT_PADS = `NUM_INPUT_PADS,
    parameter NUM_BIDIR_PADS = `NUM_BIDIR_PADS,
    parameter NUM_ANALOG_PADS = `NUM_ANALOG_PADS
    )(
    `ifdef USE_POWER_PINS
    inout  wire VDD,
    inout  wire VSS,
    inout  wire DVDD,
    inout  wire DVSS,
    `endif

    inout  wire clk_PAD,
    inout  wire rst_n_PAD,

    inout  wire [NUM_BIDIR_PADS-1:0] bidir_PAD
`ifndef SLOT_1X1
    ,
    inout  wire [NUM_INPUT_PADS-1:0] input_PAD,
    inout  wire [NUM_ANALOG_PADS-1:0] analog_PAD
`endif
);

    // gf180 IO liberty default_max_fanout 1 on pad Y. Isolation buf so
    // pad/Y fans out to one pin; PAD2CORE (Z) is free for CTS/resizer.
    (* keep *) wire clk_PAD2CORE_y;
    wire clk_PAD2CORE;
    (* keep *) wire rst_PAD2CORE_y;
    wire rst_PAD2CORE;
    wire rst_CORE2PAD;
    wire rst_CORE2PAD_OE;
    wire rst_CORE2PAD_IE;
    wire rst_CORE2PAD_PU;
    wire rst_CORE2PAD_PD;
    wire rst_CORE2PAD_CS;
    wire rst_CORE2PAD_SL;

`ifndef SLOT_1X1
    wire [NUM_INPUT_PADS-1:0] input_PAD2CORE;
    wire [NUM_INPUT_PADS-1:0] input_CORE2PAD_PU;
    wire [NUM_INPUT_PADS-1:0] input_CORE2PAD_PD;
`endif

    (* keep *) wire [NUM_BIDIR_PADS-1:0] bidir_PAD2CORE_y;
    wire [NUM_BIDIR_PADS-1:0] bidir_PAD2CORE;
    // UM t29 data-in hold is 0 at the pin. Pad-Y min-delay is shorter than
    // clk_PAD CTS insertion. Delay cells are buffers to the resizer and
    // get sized to buf_*; even inv_1 chain on D0-D15 (chip_core pad map).
    localparam PAD_D_LSB = 23;
    localparam PAD_D_MSB = 38;
    localparam PAD_Y_HOLD_INV_STAGES = 64;
    wire [NUM_BIDIR_PADS-1:0] bidir_CORE2PAD;
    wire [NUM_BIDIR_PADS-1:0] bidir_CORE2PAD_OE;
    wire [NUM_BIDIR_PADS-1:0] bidir_CORE2PAD_CS;
    wire [NUM_BIDIR_PADS-1:0] bidir_CORE2PAD_SL;
    wire [NUM_BIDIR_PADS-1:0] bidir_CORE2PAD_IE;
    wire [NUM_BIDIR_PADS-1:0] bidir_CORE2PAD_PU;
    wire [NUM_BIDIR_PADS-1:0] bidir_CORE2PAD_PD;

    // In the foundry pads, the I/O and
    // core voltage domains are shorted
    `ifdef USE_POWER_PINS
    `ifdef PAD_gf180mcu_fd_io
    assign VDD = DVDD;
    assign VSS = DVSS;
    `endif
    `endif

    // Power/ground pad instances
    generate
    for (genvar i=0; i<NUM_DVDD_PADS; i++) begin : dvdd_pads
        (* keep *)
        `gf180mcu_xxx_io__dvdd pad (
            `ifdef USE_POWER_PINS
            .DVDD   (DVDD),
            .DVSS   (DVSS),
            .VDD    (VDD),
            .VSS    (VSS)
            `endif
        );
    end
    for (genvar i=0; i<NUM_DVSS_PADS; i++) begin : dvss_pads
        (* keep *)
        `gf180mcu_xxx_io__dvss pad (
            `ifdef USE_POWER_PINS
            .DVDD   (DVDD),
            .DVSS   (DVSS),
            .VDD    (VDD),
            .VSS    (VSS)
            `endif
        );
    end
    for (genvar i=0; i<NUM_VDD_PADS; i++) begin : vdd_pads
        (* keep *)
        `gf180mcu_xxx_io__vdd pad (
            `ifdef USE_POWER_PINS
            .DVDD   (DVDD),
            .DVSS   (DVSS),
            .VDD    (VDD),
            .VSS    (VSS)
            `endif
        );
    end
    for (genvar i=0; i<NUM_VSS_PADS; i++) begin : vss_pads
        (* keep *)
        `gf180mcu_xxx_io__vss pad (
            `ifdef USE_POWER_PINS
            .DVDD   (DVDD),
            .DVSS   (DVSS),
            .VDD    (VDD),
            .VSS    (VSS)
            `endif
        );
    end
    endgenerate

    // Signal IO pad instances

    // Schmitt trigger
    `gf180mcu_xxx_io__in_s clk_pad (
        `ifdef USE_POWER_PINS
        .DVDD   (DVDD),
        .DVSS   (DVSS),
        .VDD    (VDD),
        .VSS    (VSS),
        `endif
    
        .Y      (clk_PAD2CORE_y),
        .PAD    (clk_PAD),
        
        .PU     (1'b0),
        .PD     (1'b0)
    );
    (* keep *)
    gf180mcu_fd_sc_mcu7t5v0__clkbuf_16 clk_ybuf (
        `ifdef USE_POWER_PINS
        .VDD (VDD),
        .VSS (VSS),
        .VNW (VDD),
        .VPW (VSS),
        `endif
        .I   (clk_PAD2CORE_y),
        .Z   (clk_PAD2CORE)
    );
    
    // 68000 RESET: open-drain style bidir (CPU can pull low).
    `gf180mcu_xxx_io__bi_24t rst_n_pad (
        `ifdef USE_POWER_PINS
        .DVDD   (DVDD),
        .DVSS   (DVSS),
        .VDD    (VDD),
        .VSS    (VSS),
        `endif

        .A      (rst_CORE2PAD),
        .OE     (rst_CORE2PAD_OE),
        .Y      (rst_PAD2CORE_y),
        .PAD    (rst_n_PAD),

        .CS     (rst_CORE2PAD_CS),
        .SL     (rst_CORE2PAD_SL),
        .IE     (rst_CORE2PAD_IE),
        .PU     (rst_CORE2PAD_PU),
        .PD     (rst_CORE2PAD_PD)
    );
    (* keep *)
    gf180mcu_fd_sc_mcu7t5v0__buf_1 rst_ybuf (
        `ifdef USE_POWER_PINS
        .VDD (VDD),
        .VSS (VSS),
        .VNW (VDD),
        .VPW (VSS),
        `endif
        .I   (rst_PAD2CORE_y),
        .Z   (rst_PAD2CORE)
    );

`ifndef SLOT_1X1
    generate
    for (genvar i=0; i<NUM_INPUT_PADS; i++) begin : inputs
        (* keep *)
        `gf180mcu_xxx_io__in_c pad (
            `ifdef USE_POWER_PINS
            .DVDD   (DVDD),
            .DVSS   (DVSS),
            .VDD    (VDD),
            .VSS    (VSS),
            `endif

            .Y      (input_PAD2CORE[i]),
            .PAD    (input_PAD[i]),

            .PU     (input_CORE2PAD_PU[i]),
            .PD     (input_CORE2PAD_PD[i])
        );
    end
    endgenerate
`endif

    generate
    for (genvar i=0; i<NUM_BIDIR_PADS; i++) begin : bidir
        (* keep *)
        `gf180mcu_xxx_io__bi_24t pad (
            `ifdef USE_POWER_PINS
            .DVDD   (DVDD),
            .DVSS   (DVSS),
            .VDD    (VDD),
            .VSS    (VSS),
            `endif
        
            .A      (bidir_CORE2PAD[i]),
            .OE     (bidir_CORE2PAD_OE[i]),
            .Y      (bidir_PAD2CORE_y[i]),
            .PAD    (bidir_PAD[i]),
            
            .CS     (bidir_CORE2PAD_CS[i]),
            .SL     (bidir_CORE2PAD_SL[i]),
            .IE     (bidir_CORE2PAD_IE[i]),

            .PU     (bidir_CORE2PAD_PU[i]),
            .PD     (bidir_CORE2PAD_PD[i])
        );
        wire ybuf_z;
        (* keep *)
        gf180mcu_fd_sc_mcu7t5v0__buf_1 ybuf (
            `ifdef USE_POWER_PINS
            .VDD (VDD),
            .VSS (VSS),
            .VNW (VDD),
            .VPW (VSS),
            `endif
            .I   (bidir_PAD2CORE_y[i]),
            .Z   (ybuf_z)
        );
        if ((i >= PAD_D_LSB) && (i <= PAD_D_MSB)) begin : hinv
            wire [PAD_Y_HOLD_INV_STAGES:0] net;
            assign net[0] = ybuf_z;
            for (genvar s = 0; s < PAD_Y_HOLD_INV_STAGES; s++) begin : invs
                (* keep *)
                gf180mcu_fd_sc_mcu7t5v0__inv_1 inv (
                    `ifdef USE_POWER_PINS
                    .VDD (VDD),
                    .VSS (VSS),
                    .VNW (VDD),
                    .VPW (VSS),
                    `endif
                    .I   (net[s]),
                    .ZN  (net[s + 1])
                );
            end
            assign bidir_PAD2CORE[i] = net[PAD_Y_HOLD_INV_STAGES];
        end else begin : no_hinv
            assign bidir_PAD2CORE[i] = ybuf_z;
        end
    end
    endgenerate

`ifndef SLOT_1X1
    generate
    for (genvar i=0; i<NUM_ANALOG_PADS; i++) begin : analog
        (* keep *)
        `gf180mcu_xxx_io__asig_5p0 pad (
            `ifdef USE_POWER_PINS
            .DVDD   (DVDD),
            .DVSS   (DVSS),
            .VDD    (VDD),
            .VSS    (VSS),
            `endif
            .ASIG5V (analog_PAD[i])
        );
    end
    endgenerate
`endif

    // Core design

    chip_core #(
        .NUM_BIDIR_PADS  (NUM_BIDIR_PADS)
    ) i_chip_core (
        `ifdef USE_POWER_PINS
        .VDD        (VDD),
        .VSS        (VSS),
        `endif

        .clk        (clk_PAD2CORE),
        // RESET insn drives the pad low; keep extReset clear while OE is on.
        .rst_in     (rst_PAD2CORE | rst_CORE2PAD_OE),
        .rst_out    (rst_CORE2PAD),
        .rst_oe     (rst_CORE2PAD_OE),
        .rst_ie     (rst_CORE2PAD_IE),
        .rst_pu     (rst_CORE2PAD_PU),
        .rst_pd     (rst_CORE2PAD_PD),
        .rst_cs     (rst_CORE2PAD_CS),
        .rst_sl     (rst_CORE2PAD_SL),

        .bidir_in   (bidir_PAD2CORE),
        .bidir_out  (bidir_CORE2PAD),
        .bidir_oe   (bidir_CORE2PAD_OE),
        .bidir_cs   (bidir_CORE2PAD_CS),
        .bidir_sl   (bidir_CORE2PAD_SL),
        .bidir_ie   (bidir_CORE2PAD_IE),
        .bidir_pu   (bidir_CORE2PAD_PU),
        .bidir_pd   (bidir_CORE2PAD_PD)
    );
    
    // Do not remove, necessary for tapeout
    (* keep *) gf180mcu_ws_ip__qrcode_id qrcode_id ();
    (* keep *) gf180mcu_ws_ip__shuttle_id shuttle_id ();
    (* keep *) gf180mcu_ws_ip__project_id project_id ();
    (* keep *) gf180mcu_ws_ip__marker marker ();
    
    // wafer.space logo - can be removed if desired
    (* keep *) gf180mcu_ws_ip__logo wafer_space_logo ();

endmodule

`default_nettype wire
