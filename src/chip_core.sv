// SPDX-FileCopyrightText: © 2025 Project Template Contributors
// SPDX-FileCopyrightText: © 2026 fx68k-gf180 contributors
// SPDX-License-Identifier: Apache-2.0

`default_nettype none

`include "generated_defines.svh"

`ifdef SRAM_gf180mcu_ocd_ip_sram
`define gf180mcu_xxx_ip_sram__sram512x8m8wm1 gf180mcu_ocd_ip_sram__sram512x8m8wm1
`else
`define gf180mcu_xxx_ip_sram__sram512x8m8wm1 gf180mcu_fd_ip_sram__sram512x8m8wm1
`endif

// 1x1 slot pad map (clk_PAD / rst_n_PAD are in chip_top):
//
// input_PAD[11:0]
//   [0] HALTn   [1] DTACKn  [2] BERRn   [3] VPAn
//   [4] IPL0n   [5] IPL1n   [6] IPL2n   [7] BRn
//   [8] BGACKn  [9:11] unused (pulled up)
//
// bidir_PAD[39:0]
//   [17:0]  eab[18:1]   output
//   [33:18] data[15:0]  bidir (OE low when eRWn=0 / write)
//   [34] ASn  [35] LDSn  [36] UDSn  [37] eRWn
//   [38] oRESETn  [39] oHALTEDn
//
// Not bonded: eab[23:19], E, VMAn, FC0-2, BGn.
// enPhi1/enPhi2 are generated from clk (divide by 2).

module chip_core #(
    parameter NUM_INPUT_PADS,
    parameter NUM_BIDIR_PADS,
    parameter NUM_ANALOG_PADS
    )(
    `ifdef USE_POWER_PINS
    inout  wire VDD,
    inout  wire VSS,
    `endif

    input  wire clk,
    input  wire rst_n,

    input  wire [NUM_INPUT_PADS-1:0] input_in,
    output wire [NUM_INPUT_PADS-1:0] input_pu,
    output wire [NUM_INPUT_PADS-1:0] input_pd,

    input  wire [NUM_BIDIR_PADS-1:0] bidir_in,
    output wire [NUM_BIDIR_PADS-1:0] bidir_out,
    output wire [NUM_BIDIR_PADS-1:0] bidir_oe,
    output wire [NUM_BIDIR_PADS-1:0] bidir_cs,
    output wire [NUM_BIDIR_PADS-1:0] bidir_sl,
    output wire [NUM_BIDIR_PADS-1:0] bidir_ie,
    output wire [NUM_BIDIR_PADS-1:0] bidir_pu,
    output wire [NUM_BIDIR_PADS-1:0] bidir_pd,

    inout  wire [NUM_ANALOG_PADS-1:0] analog
);

    // Unused analog
    logic _unused_analog;
    assign _unused_analog = &analog;

    // DTACKn (input[1]) pulled down so an unconnected pad still acknowledges.
    // Remaining inputs pulled up (inactive-high 68000 levels).
    assign input_pu = {{(NUM_INPUT_PADS-2){1'b1}}, 1'b0, 1'b1};
    assign input_pd = {{(NUM_INPUT_PADS-2){1'b0}}, 1'b1, 1'b0};

    assign bidir_cs = '0;
    assign bidir_sl = '0;
    assign bidir_pu = '0;
    assign bidir_pd = '0;

    // Synchronize pad reset into fx68k's synchronous extReset/pwrUp.
    logic rst_sync_0, rst_sync_1;
    always_ff @(posedge clk) begin
        rst_sync_0 <= ~rst_n;
        rst_sync_1 <= rst_sync_0;
    end
    wire extReset = rst_sync_1;
    wire pwrUp    = rst_sync_1;

    // 2x clock enables: one-cycle pulses, never consecutive.
    logic phi;
    always_ff @(posedge clk) begin
        if (extReset) begin
            phi <= 1'b0;
        end else begin
            phi <= ~phi;
        end
    end
    wire enPhi1 = ~phi;
    wire enPhi2 =  phi;

    wire HALTn  = input_in[0];
    wire DTACKn = input_in[1];
    wire BERRn  = input_in[2];
    wire VPAn   = input_in[3];
    wire IPL0n  = input_in[4];
    wire IPL1n  = input_in[5];
    wire IPL2n  = input_in[6];
    wire BRn    = input_in[7];
    wire BGACKn = input_in[8];

    wire eRWn, ASn, LDSn, UDSn, E, VMAn;
    wire FC0, FC1, FC2, BGn, oRESETn, oHALTEDn;
    wire [15:0] oEdb;
    wire [23:1] eab;
    wire [15:0] iEdb = bidir_in[33:18];

    fx68k u_fx68k (
        .clk      (clk),
        .HALTn    (HALTn),
        .extReset (extReset),
        .pwrUp    (pwrUp),
        .enPhi1   (enPhi1),
        .enPhi2   (enPhi2),
        .eRWn     (eRWn),
        .ASn      (ASn),
        .LDSn     (LDSn),
        .UDSn     (UDSn),
        .E        (E),
        .VMAn     (VMAn),
        .FC0      (FC0),
        .FC1      (FC1),
        .FC2      (FC2),
        .BGn      (BGn),
        .oRESETn  (oRESETn),
        .oHALTEDn (oHALTEDn),
        .DTACKn   (DTACKn),
        .VPAn     (VPAn),
        .BERRn    (BERRn),
        .BRn      (BRn),
        .BGACKn   (BGACKn),
        .IPL0n    (IPL0n),
        .IPL1n    (IPL1n),
        .IPL2n    (IPL2n),
        .iEdb     (iEdb),
        .oEdb     (oEdb),
        .eab      (eab)
    );

    logic _unused_unbonded;
    assign _unused_unbonded = &{E, VMAn, FC0, FC1, FC2, BGn, eab[23:19],
                                input_in[NUM_INPUT_PADS-1:9]};

    // Data bus drives pads only on writes (eRWn low). Address/control always out.
    assign bidir_oe[17:0]  = {18{1'b1}};
    assign bidir_oe[33:18] = {16{~eRWn}};
    assign bidir_oe[39:34] = {6{1'b1}};
    assign bidir_ie        = ~bidir_oe;

    assign bidir_out[17:0]  = eab[18:1];
    assign bidir_out[33:18] = oEdb;
    assign bidir_out[34]    = ASn;
    assign bidir_out[35]    = LDSn;
    assign bidir_out[36]    = UDSn;
    assign bidir_out[37]    = eRWn;
    assign bidir_out[38]    = oRESETn;
    assign bidir_out[39]    = oHALTEDn;

    // Template SRAM macros: required by the default PDN grid.
    logic [7:0] sram_0_out;
    logic [7:0] sram_1_out;

    (* keep *)
    `gf180mcu_xxx_ip_sram__sram512x8m8wm1 sram_0 (
        `ifdef USE_POWER_PINS
        .VDD  (VDD),
        .VSS  (VSS),
        `endif
        .CLK  (clk),
        .CEN  (1'b1),
        .GWEN (1'b0),
        .WEN  (8'b0),
        .A    ('0),
        .D    ('0),
        .Q    (sram_0_out)
    );

    (* keep *)
    `gf180mcu_xxx_ip_sram__sram512x8m8wm1 sram_1 (
        `ifdef USE_POWER_PINS
        .VDD  (VDD),
        .VSS  (VSS),
        `endif
        .CLK  (clk),
        .CEN  (1'b1),
        .GWEN (1'b0),
        .WEN  (8'b0),
        .A    ('0),
        .D    ('0),
        .Q    (sram_1_out)
    );

    (* keep *) wire [15:0] sram_mix = {sram_1_out, sram_0_out};

endmodule

`default_nettype wire
