`ifdef SLOT_1X1

// 74-pad LGA: steal 4 I/O DVDD cells as GPIO (custom PCB; stock COB
// straps those balls to 5 V). Remaining power: 2 DVDD + 8 DVSS + 2 VDD + 2 VSS.
`define NUM_DVDD_PADS 2
`define NUM_DVSS_PADS 8

`define NUM_VDD_PADS 2
`define NUM_VSS_PADS 2

// All non-power balls are bi_24t except clk (in_s). RESET is bidir on rst_n_PAD.
`define NUM_INPUT_PADS 0
`define NUM_BIDIR_PADS 58
`define NUM_ANALOG_PADS 0

`endif

`ifdef SLOT_0P5X1

// Power/ground pads for core and I/O
`define NUM_DVDD_PADS 7
`define NUM_DVSS_PADS 7

`define NUM_VDD_PADS 1
`define NUM_VSS_PADS 1

// Signal pads
`define NUM_INPUT_PADS 4
`define NUM_BIDIR_PADS 44
`define NUM_ANALOG_PADS 6

`endif

`ifdef SLOT_1X0P5

// Power/ground pads for core and I/O
`define NUM_DVDD_PADS 7
`define NUM_DVSS_PADS 7

`define NUM_VDD_PADS 1
`define NUM_VSS_PADS 1

// Signal pads
`define NUM_INPUT_PADS 4
`define NUM_BIDIR_PADS 46
`define NUM_ANALOG_PADS 4

`endif

`ifdef SLOT_0P5X0P5

// Power/ground pads for core and I/O
`define NUM_DVDD_PADS 3
`define NUM_DVSS_PADS 3

`define NUM_VDD_PADS 1
`define NUM_VSS_PADS 1

// Signal pads
`define NUM_INPUT_PADS 4
`define NUM_BIDIR_PADS 38
`define NUM_ANALOG_PADS 4

`endif
