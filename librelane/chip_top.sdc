# chip_top pad STA: MC68000 asynchronous-bus AC vs clk_PAD.
#
# clk_PAD is 2× 68000 PHI. CLOCK_PERIOD 16.667 ns → 60 MHz die clock →
# 30 MHz 68000-equivalent (enPhi1/enPhi2 divide-by-2 in chip_core). Do
# not treat CLOCK_PERIOD as a PHI period.
#
# Pad delays are UM Ninth Edition §10.10, 10 MHz column
# (fx68k/docs/MC68000UM.txt). Encoded vs clk_PAD so STA checks the same
# nanosecond budget from the launching clk edge (a PHI edge when enPhi* is
# high). Core flop-to-flop / Ir→microAddr/nanoAddr multicycle is sourced
# from fx68k/constraints/fx68k.sdc.
#
# enPhi1/enPhi2 stay data (clock enables). They are not generated clocks.

current_design $::env(DESIGN_NAME)
set_units -time ns

if {![info exists clk_period]} {
    if {[info exists ::env(CLOCK_PERIOD)] && $::env(CLOCK_PERIOD) ne ""} {
        set clk_period $::env(CLOCK_PERIOD)
    } else {
        set clk_period 16.667
    }
}

set clk_name clk_PAD
set clk_port_name clk_PAD
if {[info exists ::env(CLOCK_PORT)] && $::env(CLOCK_PORT) ne ""} {
    set clk_port_name [lindex $::env(CLOCK_PORT) 0]
    set clk_name $clk_port_name
}

# 68000 PHI period is 2× clk. Named so the clk-vs-PHI relationship is a
# current fact, not a buried period.
set phi_period_ns [expr {$clk_period * 2.0}]

set clk_port [get_ports $clk_port_name]
puts "\[INFO] create_clock $clk_name period ${clk_period} ns on port $clk_port_name (2× PHI; PHI ${phi_period_ns} ns)"
create_clock -name $clk_name -period $clk_period $clk_port

# Core SDC: skip create_clock (clk_PAD already exists), apply multicycle.
set _core_sdc ""
set _core_candidates [list]
if {[info exists ::env(DESIGN_DIR)]} {
    lappend _core_candidates [file normalize [file join $::env(DESIGN_DIR) .. fx68k constraints fx68k.sdc]]
    lappend _core_candidates [file normalize [file join $::env(DESIGN_DIR) fx68k constraints fx68k.sdc]]
}
lappend _core_candidates [file normalize [file join [pwd] fx68k constraints fx68k.sdc]]
lappend _core_candidates [file normalize [file join [pwd] .. fx68k constraints fx68k.sdc]]
foreach _cand $_core_candidates {
    if {[file exists $_cand]} {
        set _core_sdc $_cand
        break
    }
}
if {$_core_sdc eq ""} {
    puts "\[ERROR] fx68k/constraints/fx68k.sdc not found (tried: $_core_candidates)"
} else {
    puts "\[INFO] sourcing core SDC $_core_sdc"
    source $_core_sdc
}

if {[info exists ::env(MAX_FANOUT_CONSTRAINT)]} {
    set_max_fanout $::env(MAX_FANOUT_CONSTRAINT) [current_design]
}
if {[info exists ::env(MAX_TRANSITION_CONSTRAINT)]} {
    set_max_transition $::env(MAX_TRANSITION_CONSTRAINT) [current_design]
}
if {[info exists ::env(MAX_CAPACITANCE_CONSTRAINT)]} {
    set_max_capacitance $::env(MAX_CAPACITANCE_CONSTRAINT) [current_design]
}

# ---------------------------------------------------------------------------
# UM §10.10 10 MHz column (ns). Spec numbers vs PHI edges.
# set_output_delay -max (clk_period - tco_max) encodes tco <= tco_max.
# set_input_delay  -max (clk_period - tsu)     encodes tsu >= tsu_min at the pin.
# output_delay max is (clk_period - tco_max) and may be negative when
# tco_max > clk_period (UM ns vs a faster die clock).
# ---------------------------------------------------------------------------

set um_t6_addr_tco_max          50.0
set um_t6a_fc_tco_max           50.0
set um_t8_addr_fc_hold_min       0.0
set um_t9_as_ds_assert_tco_min   3.0
set um_t9_as_ds_assert_tco_max  50.0
set um_t12_as_ds_negate_tco_max 50.0
set um_t18_rw_tco_min            0.0
set um_t18_rw_tco_max           45.0
set um_t20_rw_tco_max           45.0
set um_t23_data_out_tco_max     50.0
set um_t27_data_in_setup_min    10.0
set um_t29_data_in_hold_min      0.0
set um_t33_bg_tco_max           50.0
set um_t34_bg_negate_tco_max    50.0
set um_t40_vma_tco_max          70.0
set um_t41_e_tco_max            45.0
set um_t47_async_setup_min      10.0
set um_t53_data_out_hold_min     0.0

# UM §10.10 note 1: tabulated tco_max is for C_L > 50 pF.
set um_cl_pf 50.0

# Pad map: src/chip_core.sv (1x1 bidir_PAD).
set pad_a_lsb   0
set pad_a_msb  22
set pad_d_lsb  23
set pad_d_msb  38
set pad_as     39
set pad_uds    40
set pad_lds    41
set pad_rw     42
set pad_dtack  43
set pad_berr   44
set pad_halt   45
set pad_vpa    46
set pad_e      47
set pad_vma    48
set pad_fc0    49
set pad_fc1    50
set pad_fc2    51
set pad_br     52
set pad_bg     53
set pad_bgack  54
set pad_ipl0   55
set pad_ipl1   56
set pad_ipl2   57

proc um_out_delay_max {tco_max} {
    global clk_period
    return [expr {$clk_period - $tco_max}]
}

proc um_in_delay_max {tsu} {
    global clk_period
    set d [expr {$clk_period - $tsu}]
    if {$d < 0.0} {
        puts "\[WARNING] tsu ${tsu} ns > clk_period ${clk_period} ns; clamping input_delay max to 0"
        set d 0.0
    }
    return $d
}

proc um_bidir {idx} {
    return [get_ports -quiet [format {bidir_PAD[%s]} $idx]]
}

proc um_bidir_list {indices} {
    set names {}
    foreach idx $indices {
        lappend names [format {bidir_PAD[%s]} $idx]
    }
    return [get_ports -quiet $names]
}

proc um_bidir_range {lsb msb} {
    set ports [get_ports -quiet [format {bidir_PAD[%s:%s]} $msb $lsb]]
    if {[llength $ports] == 0} {
        set indices {}
        for {set i $lsb} {$i <= $msb} {incr i} {
            lappend indices $i
        }
        return [um_bidir_list $indices]
    }
    return $ports
}

proc um_set_output {spec ports tco_max tco_min} {
    global clk_name
    if {[llength $ports] == 0} {
        puts "\[WARNING] $spec: no ports"
        return
    }
    set dmax [um_out_delay_max $tco_max]
    set_output_delay -clock $clk_name -max $dmax $ports
    set_output_delay -clock $clk_name -min $tco_min $ports
    puts "\[INFO] $spec output_delay max=$dmax min=$tco_min"
}

proc um_set_input {spec ports tsu thold} {
    global clk_name
    if {[llength $ports] == 0} {
        puts "\[WARNING] $spec: no ports"
        return
    }
    set dmax [um_in_delay_max $tsu]
    set_input_delay -clock $clk_name -max $dmax $ports
    set_input_delay -clock $clk_name -min $thold $ports
    puts "\[INFO] $spec input_delay max=$dmax min=$thold"
}

set clocks [get_clocks $clk_name]

set ports_addr    [um_bidir_range $pad_a_lsb $pad_a_msb]
set ports_data    [um_bidir_range $pad_d_lsb $pad_d_msb]
set ports_strobes [um_bidir_list [list $pad_as $pad_uds $pad_lds]]
set ports_rw      [um_bidir $pad_rw]
set ports_dtack   [um_bidir $pad_dtack]
set ports_berr    [um_bidir $pad_berr]
set ports_halt    [um_bidir $pad_halt]
set ports_vpa     [um_bidir $pad_vpa]
set ports_e       [um_bidir $pad_e]
set ports_vma     [um_bidir $pad_vma]
set ports_fc      [um_bidir_list [list $pad_fc0 $pad_fc1 $pad_fc2]]
set ports_br      [um_bidir $pad_br]
set ports_bg      [um_bidir $pad_bg]
set ports_bgack   [um_bidir $pad_bgack]
set ports_ipl     [um_bidir_list [list $pad_ipl0 $pad_ipl1 $pad_ipl2]]
set ports_reset   [get_ports -quiet rst_n_PAD]

# Outputs
um_set_output "spec 6 Address A1-A23 bidir_PAD\[22:0\]" \
    $ports_addr $um_t6_addr_tco_max $um_t8_addr_fc_hold_min
um_set_output "spec 6A FC bidir_PAD\[51:49\]" \
    $ports_fc $um_t6a_fc_tco_max $um_t8_addr_fc_hold_min
# Spec 9 (assert max 50 / min 3) and spec 12 (negate max 50) share AS/UDS/LDS.
um_set_output "spec 9/12 AS/UDS/LDS bidir_PAD\[41:39\]" \
    $ports_strobes $um_t9_as_ds_assert_tco_max $um_t9_as_ds_assert_tco_min
um_set_output "spec 18/20 R/W bidir_PAD\[42\]" \
    $ports_rw $um_t18_rw_tco_max $um_t18_rw_tco_min
um_set_output "spec 23 Data-out D0-D15 bidir_PAD\[38:23\]" \
    $ports_data $um_t23_data_out_tco_max $um_t53_data_out_hold_min
um_set_output "spec 33/34 BG bidir_PAD\[53\]" \
    $ports_bg $um_t33_bg_tco_max $um_t8_addr_fc_hold_min
um_set_output "spec 40 VMA bidir_PAD\[48\]" \
    $ports_vma $um_t40_vma_tco_max $um_t8_addr_fc_hold_min
um_set_output "spec 41 E bidir_PAD\[47\]" \
    $ports_e $um_t41_e_tco_max $um_t8_addr_fc_hold_min

# Inputs. Data OE is write (~eRWn); read uses input_delay on the same pads.
# HALT/RESET as outputs have no UM tco; only the input sense is constrained.
um_set_input "spec 27 Data-in D0-D15 bidir_PAD\[38:23\]" \
    $ports_data $um_t27_data_in_setup_min $um_t29_data_in_hold_min
um_set_input "spec 47 DTACK bidir_PAD\[43\]" \
    $ports_dtack $um_t47_async_setup_min $um_t8_addr_fc_hold_min
um_set_input "spec 47 BERR bidir_PAD\[44\]" \
    $ports_berr $um_t47_async_setup_min $um_t8_addr_fc_hold_min
um_set_input "spec 47 HALT (input) bidir_PAD\[45\]" \
    $ports_halt $um_t47_async_setup_min $um_t8_addr_fc_hold_min
um_set_input "spec 47 VPA bidir_PAD\[46\]" \
    $ports_vpa $um_t47_async_setup_min $um_t8_addr_fc_hold_min
um_set_input "spec 47 BR bidir_PAD\[52\]" \
    $ports_br $um_t47_async_setup_min $um_t8_addr_fc_hold_min
um_set_input "spec 47 BGACK bidir_PAD\[54\]" \
    $ports_bgack $um_t47_async_setup_min $um_t8_addr_fc_hold_min
um_set_input "spec 47 IPL bidir_PAD\[57:55\]" \
    $ports_ipl $um_t47_async_setup_min $um_t8_addr_fc_hold_min
# RESET is not in the spec 47 list; the same async-input setup is used when
# rst_n_PAD is an input. Pulse width is spec 56 (10 PHI clocks), not STA setup.
um_set_input "spec 47 RESET (input) rst_n_PAD" \
    $ports_reset $um_t47_async_setup_min $um_t8_addr_fc_hold_min

# UM §10.10 note 1 is package-pin C_L on CPU outputs, not clk_PAD.
foreach _um_out [list $ports_addr $ports_fc $ports_strobes $ports_rw \
                      $ports_data $ports_bg $ports_vma $ports_e] {
    if {[llength $_um_out]} {
        set_load $um_cl_pf $_um_out
    }
}
puts "\[INFO] load ${um_cl_pf} pF on 68000 outputs (UM §10.10 note 1)"

# Clocked I/O uses input_delay / output_delay. Combinational pad-to-pad
# (BGACK → OE/IE) is not a UM same-edge check. OpenSTA has no
# remove_from_collection; name the inout pads (not clk_PAD).
set _io_pads [get_ports -quiet {rst_n_PAD bidir_PAD[*]}]
if {[llength $_io_pads]} {
    set_false_path -from $_io_pads -to $_io_pads
    puts "\[INFO] false_path combinational pad-to-pad"
}

# IE->Y is not a 68000 data path (BGACK changing data-pad IE must not
# time through the data-in hold chain to the capture flop). PAD->Y stays.
set _pad_cells [concat [get_cells -quiet {bidir[*].pad}] [get_cells -quiet {rst_n_pad}]]
if {[llength $_pad_cells]} {
    set_disable_timing -from IE -to Y $_pad_cells
    puts "\[INFO] disable_timing IE->Y on [llength $_pad_cells] pads"
}

if {[info exists ::env(CLOCK_UNCERTAINTY_CONSTRAINT)]} {
    puts "\[INFO] Setting clock uncertainty to: $::env(CLOCK_UNCERTAINTY_CONSTRAINT)"
    set_clock_uncertainty $::env(CLOCK_UNCERTAINTY_CONSTRAINT) $clocks
}
if {[info exists ::env(CLOCK_TRANSITION_CONSTRAINT)]} {
    puts "\[INFO] Setting clock transition to: $::env(CLOCK_TRANSITION_CONSTRAINT)"
    set_clock_transition $::env(CLOCK_TRANSITION_CONSTRAINT) $clocks
}
if {[info exists ::env(TIME_DERATING_CONSTRAINT)]} {
    puts "\[INFO] Setting timing derate to: $::env(TIME_DERATING_CONSTRAINT)%"
    set_timing_derate -early [expr 1-[expr $::env(TIME_DERATING_CONSTRAINT) / 100]]
    set_timing_derate -late [expr 1+[expr $::env(TIME_DERATING_CONSTRAINT) / 100]]
}

if {[info exists ::env(OPENLANE_SDC_IDEAL_CLOCKS)] && $::env(OPENLANE_SDC_IDEAL_CLOCKS)} {
    unset_propagated_clock [all_clocks]
} else {
    set_propagated_clock [all_clocks]
}
