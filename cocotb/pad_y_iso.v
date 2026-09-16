// SPDX-FileCopyrightText: © 2025 Project Template Contributors
// SPDX-License-Identifier: Apache-2.0
//
// Behavioral stand-ins for chip_top pad-Y isolation cells under PADS_RTL.
// LibreLane maps the same instance names to the PDK.

`ifndef USE_POWER_PINS
module gf180mcu_fd_sc_mcu7t5v0__clkbuf_16 (
    input  I,
    output Z
);
    assign Z = I;
endmodule

module gf180mcu_fd_sc_mcu7t5v0__buf_1 (
    input  I,
    output Z
);
    assign Z = I;
endmodule

module gf180mcu_fd_sc_mcu7t5v0__inv_1 (
    input  I,
    output ZN
);
    assign ZN = ~I;
endmodule
`endif
