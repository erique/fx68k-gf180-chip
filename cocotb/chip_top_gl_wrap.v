`timescale 1ns / 1ns

// Per-bit drive of chip_top bidir_PAD for GL (cocotb must not assign the
// packed inout). drv_en=1 drives drv onto that pad; else Z (PU/PD / CPU).
module chip_top_gl_wrap (
    inout  wire        clk_PAD,
    inout  wire        rst_n_PAD,
    inout  wire        VDD,
    inout  wire        VSS,
    output wire [57:0] pad,
    input  wire [57:0] drv,
    input  wire [57:0] drv_en
);

    genvar i;
    generate
        for (i = 0; i < 58; i = i + 1) begin : bits
            assign pad[i] = drv_en[i] ? drv[i] : 1'bz;
        end
    endgenerate

    chip_top u_top (
`ifdef USE_POWER_PINS
        .VDD      (VDD),
        .VSS      (VSS),
`ifdef PADS_RTL
        .DVDD     (VDD),
        .DVSS     (VSS),
`endif
`endif
        .clk_PAD  (clk_PAD),
        .rst_n_PAD(rst_n_PAD),
        .bidir_PAD(pad)
    );

    // Pad-ring GL: rst_oe is a dffq (X at t=0) and fights rst_n_PAD.
    // Force OE off. extReset can be forced, but eab still X until PHI/T-states
    // run; this pnl does not toggle enPhi2 after POR. Functional balls: sim-pads.
`ifdef GL_PNL
    initial begin
        force u_top.\i_chip_core.rst_oe = 1'b0;
    end
`endif

endmodule
