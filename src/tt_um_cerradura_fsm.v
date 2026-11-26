`default_nettype none

module tt_um_cerradura_fsm (
    input  wire [7:0] ui_in,    // Entradas dedicadas
    output wire [7:0] uo_out,   // Salidas dedicadas
    input  wire [7:0] uio_in,   // IOs: Ruta de entrada
    output wire [7:0] uio_out,  // IOs: Ruta de salida
    output wire [7:0] uio_oe,   // IOs: Enable
    input  wire       ena,      // Siempre en 1 cuando el diseño está activo
    input  wire       clk,      // Reloj del chip (1 MHz)
    input  wire       rst_n     // Reset activo en bajo
);

    wire [3:0] col_w;
    wire       unlock_w;
    wire       error_w;
    wire       locked_w;
    wire       prog_w;

    asic_cerradura_core u_core (
        .clk       (clk),
        .rst_n     (rst_n),
        .row_async (ui_in[3:0]),
        .col       (col_w),
        .unlock    (unlock_w),
        .error_led (error_w),
        .locked    (locked_w),
        .prog_mode (prog_w)
    );

    // uo_out = prog_mode, uo_out = locked, uo_out = error, uo_out = unlock
    assign uo_out = {prog_w, locked_w, error_w, unlock_w, col_w};

    assign uio_out = 8'b0000_0000;
    assign uio_oe  = 8'b0000_0000;

    wire _unused = &{ena, ui_in[7:4], uio_in, 1'b0};

endmodule
