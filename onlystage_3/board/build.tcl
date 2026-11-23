# Run: vivado -mode batch -source board/build.tcl
set src [file dirname [file normalize [info script]]]
set out [file join $src build]
file mkdir $out
read_verilog [file join $src nexys_pad.v]
read_xdc [file join $src nexys_pad.xdc]
synth_design -top nexys_pad -part xc7a100tcsg324-1
opt_design
place_design
route_design
report_timing_summary -file [file join $out timing.rpt]
write_bitstream -force [file join $out nexys_pad.bit]
