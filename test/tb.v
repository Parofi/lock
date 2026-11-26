`default_nettype none
`timescale 1ns / 1ps

/* Este testbench instancia tt_um_cerradura_fsm y expone los puertos
   para que cocotb los maneje tanto en simulacion RTL como Gate-Level (GLS). */
module tb ();

  // Volcado de ondas para inspeccionar en GTKWave si se ejecuta localmente
  initial begin
    $dumpfile ("tb.vcd");
    $dumpvars (0, tb);
    #1;
  end

  // Senales conectadas al DUT
  reg        clk;
  reg        rst_n;
  reg        ena;
  reg  [7:0] ui_in;
  reg  [7:0] uio_in;
  wire [7:0] uo_out;
  wire [7:0] uio_out;
  wire [7:0] uio_oe;

  // En Gate-Level Simulation (GLS), se incluyen las celdas de GF180MCU y alimentacion
`ifdef GL_TEST
  wire VPWR = 1'b1;
  wire VGND = 1'b0;
`endif

  tt_um_cerradura_fsm user_project (
`ifdef GL_TEST
      .VPWR   (VPWR),
      .VGND   (VGND),
`endif
      .ui_in  (ui_in),
      .uo_out (uo_out),
      .uio_in (uio_in),
      .uio_out(uio_out),
      .uio_oe (uio_oe),
      .ena    (ena),
      .clk    (clk),
      .rst_n  (rst_n)
  );

endmodule

