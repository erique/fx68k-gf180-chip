// SPDX-FileCopyrightText: © 2025 Project Template Contributors
// SPDX-FileCopyrightText: © 2026 fx68k-gf180 contributors
// SPDX-License-Identifier: Apache-2.0

`default_nettype none
`timescale 1ns / 1ns

`include "generated_defines.svh"
`include "slot_defines.svh"

// 1x1 74-pad LGA: clk_PAD = CLK (in_s), rst_n_PAD = RESET (bi_24t OD),
// bidir_PAD[57:0] = remaining 68000 signals (all bi_24t).
//
// bidir_PAD:
//   [22:0]  A1–A23 (eab[23:1])
//   [38:23] D0–D15
//   [39] AS  [40] UDS  [41] LDS  [42] R/W
//   [43] DTACK  [44] BERR  [45] HALT
//   [46] VPA  [47] E  [48] VMA
//   [49] FC0  [50] FC1  [51] FC2
//   [52] BR  [53] BG  [54] BGACK
//   [55] IPL0  [56] IPL1  [57] IPL2

module chip_core #(
    parameter NUM_BIDIR_PADS = `NUM_BIDIR_PADS
    )(
    `ifdef USE_POWER_PINS
    inout  wire VDD,
    inout  wire VSS,
    `endif

    input  wire clk,
    input  wire rst_in,
    output wire rst_out,
    output wire rst_oe,
    output wire rst_ie,
    output wire rst_pu,
    output wire rst_pd,
    output wire rst_cs,
    output wire rst_sl,

    input  wire [NUM_BIDIR_PADS-1:0] bidir_in,
    output wire [NUM_BIDIR_PADS-1:0] bidir_out,
    output wire [NUM_BIDIR_PADS-1:0] bidir_oe,
    output wire [NUM_BIDIR_PADS-1:0] bidir_cs,
    output wire [NUM_BIDIR_PADS-1:0] bidir_sl,
    output wire [NUM_BIDIR_PADS-1:0] bidir_ie,
    output wire [NUM_BIDIR_PADS-1:0] bidir_pu,
    output wire [NUM_BIDIR_PADS-1:0] bidir_pd
);

    localparam PAD_A_LSB = 0;
    localparam PAD_A_MSB = 22;
    localparam PAD_D_LSB = 23;
    localparam PAD_D_MSB = 38;
    localparam PAD_AS = 39;
    localparam PAD_UDS = 40;
    localparam PAD_LDS = 41;
    localparam PAD_RW = 42;
    localparam PAD_DTACK = 43;
    localparam PAD_BERR = 44;
    localparam PAD_HALT = 45;
    localparam PAD_VPA = 46;
    localparam PAD_E = 47;
    localparam PAD_VMA = 48;
    localparam PAD_FC0 = 49;
    localparam PAD_FC1 = 50;
    localparam PAD_FC2 = 51;
    localparam PAD_BR = 52;
    localparam PAD_BG = 53;
    localparam PAD_BGACK = 54;
    localparam PAD_IPL0 = 55;
    localparam PAD_IPL1 = 56;
    localparam PAD_IPL2 = 57;
    localparam ADDR_W = PAD_A_MSB - PAD_A_LSB + 1;
    localparam DATA_W = PAD_D_MSB - PAD_D_LSB + 1;

    assign bidir_cs = '0;
    assign bidir_sl = '0;

    // RESET (rst_n_PAD): pull-up, CPU drives 0 when oRESETn is low.
    assign rst_cs = 1'b0;
    assign rst_sl = 1'b0;
    assign rst_out = 1'b0;
    assign rst_pd = 1'b0;
    assign rst_pu = 1'b1;

    logic rst_sync_0, rst_sync_1;
    always_ff @(posedge clk) begin
        rst_sync_0 <= ~rst_in;
        rst_sync_1 <= rst_sync_0;
    end
    wire extReset = rst_sync_1;
    wire pwrUp    = rst_sync_1;

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

    wire eRWn, ASn, LDSn, UDSn, E, VMAn;
    wire FC0, FC1, FC2, BGn, oRESETn, oHALTEDn;
    wire [15:0] oEdb;
    wire [23:1] eab;

    wire HALTn  = bidir_in[PAD_HALT];
    wire DTACKn = bidir_in[PAD_DTACK];
    wire BERRn  = bidir_in[PAD_BERR];
    wire VPAn   = bidir_in[PAD_VPA];
    wire BRn    = bidir_in[PAD_BR];
    wire BGACKn = bidir_in[PAD_BGACK];
    wire IPL0n  = bidir_in[PAD_IPL0];
    wire IPL1n  = bidir_in[PAD_IPL1];
    wire IPL2n  = bidir_in[PAD_IPL2];
    wire [15:0] iEdb = bidir_in[PAD_D_MSB:PAD_D_LSB];

    // Only pull RESET/HALT low when the CPU output is 0. X would otherwise
    // fight the pad driver in RTL sim.
    assign rst_oe = (oRESETn === 1'b0);
    assign rst_ie = ~rst_oe;

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

    // Packed concatenations (MSB=IPL2 … LSB=A1). Icarus does not drive
    // pad A from always_comb into output wires.
    assign bidir_out = {
        3'b000,
        1'b0,
        BGn,
        1'b0,
        FC2, FC1, FC0,
        VMAn, E,
        1'b0,
        1'b0,
        2'b00,
        eRWn, LDSn, UDSn, ASn,
        oEdb,
        eab[23:1]
    };
    assign bidir_oe = {
        3'b000,
        1'b0,
        1'b1,
        1'b0,
        3'b111,
        2'b11,
        1'b0,
        (oHALTEDn === 1'b0),
        2'b00,
        4'b1111,
        {DATA_W{~eRWn}},
        {ADDR_W{1'b1}}
    };
    assign bidir_ie = ~bidir_oe;
    assign bidir_pu = {
        3'b111,
        1'b1,
        1'b0,
        1'b1,
        3'b000,
        2'b00,
        1'b1,
        1'b1,
        1'b1, 1'b0,
        4'b0000,
        {DATA_W{1'b0}},
        {ADDR_W{1'b0}}
    };
    assign bidir_pd = {
        {14{1'b0}},
        1'b1,
        {4{1'b0}},
        {DATA_W{1'b0}},
        {ADDR_W{1'b0}}
    };

endmodule

`default_nettype wire
