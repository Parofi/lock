`default_nettype none

module asic_cerradura_core (
    input  wire       clk,        // Reloj principal del ASIC (1 MHz)
    input  wire       rst_n,      // Reset global activo en bajo
    input  wire [3:0] row_async,  // Entradas físicas del teclado (asíncronas)
    input  wire       prog_en,    // Interruptor de llave físico
    output reg  [3:0] col,        // Salidas de barrido hacia los pads del chip
    output wire       unlock,     // Pin de salida: Cerradura abierta
    output wire       error_led,  // Pin de salida: Error en clave
    output wire       locked,     // Pin de salida: Bloqueo por seguridad
    output wire       prog_mode,  // Pin de salida: Modo programación activo
    output wire       ready       // NUEVO: 1 = Lista para recibir clave
);

	 localparam [15:0] DEBOUNCE_LIMIT = 16'd10_000; // 10 ms a 1 MHz
    localparam [15:0] SCAN_LIMIT     = 16'd1_000;  // 1 ms por columna a 1 MHz
    localparam [3:0]  KEY_LOCK       = 4'hE;       // Tecla '*' para cerrar manualmente
    localparam [3:0]  KEY_PROG       = 4'hF;       // Tecla '#' para programar

	 // ------------------------------------------------------------------------
    // Sincronizador para el interruptor de llave
	 // ------------------------------------------------------------------------
    reg prog_sync_1, prog_sync;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            prog_sync_1 <= 1'b0;
            prog_sync   <= 1'b0;
        end else begin
            prog_sync_1 <= prog_en;
            prog_sync   <= prog_sync_1;
        end
    end
	 
	 
	 
	 
    // ------------------------------------------------------------------------
    // 1. Sincronizador de doble Flip-Flop
    // ------------------------------------------------------------------------
    reg [3:0] row_sync_1, row_sync;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            row_sync_1 <= 4'b1111;
            row_sync   <= 4'b1111;
        end else begin
            row_sync_1 <= row_async;
            row_sync   <= row_sync_1;
        end
    end

    // ------------------------------------------------------------------------
    // 2. Barrido de columnas y Antirrebote
    // ------------------------------------------------------------------------
    reg [1:0]  col_idx;
    reg [15:0] scan_cnt;
    reg [15:0] deb_cnt;
    reg [3:0]  raw_key;
    reg [3:0]  key_code;
    reg        key_valid;
    reg        key_pressed_prev;

    wire key_pressed = (row_sync != 4'b1111);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            scan_cnt <= 16'd0;
            col_idx  <= 2'd0;
        end else if (!key_pressed) begin
            if (scan_cnt >= SCAN_LIMIT) begin
                scan_cnt <= 16'd0;
                col_idx  <= col_idx + 2'd1;
            end else begin
                scan_cnt <= scan_cnt + 16'd1;
            end
        end
    end

    always @(*) begin
        case (col_idx)
            2'd0: col = 4'b1110;
            2'd1: col = 4'b1101;
            2'd2: col = 4'b1011;
            2'd3: col = 4'b0111;
        endcase
    end

    always @(*) begin
        case ({col, row_sync})
            8'b1110_1110: raw_key = 4'h1;
            8'b1110_1101: raw_key = 4'h4;
            8'b1110_1011: raw_key = 4'h7;
            8'b1110_0111: raw_key = 4'hE; // '*'
            8'b1101_1110: raw_key = 4'h2;
            8'b1101_1101: raw_key = 4'h5;
            8'b1101_1011: raw_key = 4'h8;
            8'b1101_0111: raw_key = 4'h0;
            8'b1011_1110: raw_key = 4'h3;
            8'b1011_1101: raw_key = 4'h6;
            8'b1011_1011: raw_key = 4'h9;
            8'b1011_0111: raw_key = 4'hF; // '#'
            8'b0111_1110: raw_key = 4'hA;
            8'b0111_1101: raw_key = 4'hB;
            8'b0111_1011: raw_key = 4'hC;
            8'b0111_0111: raw_key = 4'hD;
            default:      raw_key = 4'h0;
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            deb_cnt          <= 16'd0;
            key_code         <= 4'd0;
            key_valid        <= 1'b0;
            key_pressed_prev <= 1'b0;
        end else begin
            key_valid <= 1'b0;
            if (key_pressed) begin
                if (deb_cnt < DEBOUNCE_LIMIT) begin
                    deb_cnt <= deb_cnt + 16'd1;
                end else if (!key_pressed_prev) begin
                    key_code         <= raw_key;
                    key_valid        <= 1'b1;
                    key_pressed_prev <= 1'b1;
                end
            end else begin
                deb_cnt          <= 16'd0;
                key_pressed_prev <= 1'b0;
            end
        end
    end

    // ------------------------------------------------------------------------
    // 3. FSM con Clave Programable y Bloqueo tras 3 Fallos
    // ------------------------------------------------------------------------
    localparam [3:0] S_IDLE   = 4'd0,
                     S_OK1    = 4'd1,
                     S_OK2    = 4'd2,
                     S_OK3    = 4'd3,
                     S_ERR1   = 4'd4,
                     S_ERR2   = 4'd5,
                     S_ERR3   = 4'd6,
                     S_UNLOCK = 4'd7,
                     S_LOCKED = 4'd8,
                     S_PROG1  = 4'd9,  // Esperando nuevo 1er dígito
                     S_PROG2  = 4'd10, // Esperando nuevo 2do dígito
                     S_PROG3  = 4'd11, // Esperando nuevo 3er dígito
                     S_PROG4  = 4'd12; // Esperando nuevo 4to dígito

    reg [3:0] estado_actual, estado_siguiente;
    reg [1:0] intentos;
    reg       intento_fallido;
    reg       error_reg;

    // Registros de la contraseña actual (Valor por defecto en reset: 1-2-3-4)
    reg [3:0] pass_d1, pass_d2, pass_d3, pass_d4;
	 
	 wire es_digito_valido = (key_code != KEY_LOCK) && (key_code != KEY_PROG);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            estado_actual <= S_IDLE;
            intentos      <= 2'd0;
            error_reg     <= 1'b0;
            pass_d1       <= 4'h1;
            pass_d2       <= 4'h2;
            pass_d3       <= 4'h3;
            pass_d4       <= 4'h4;
        end else begin
            estado_actual <= estado_siguiente;

            // Manejo de contador de errores
            if (intento_fallido) begin
                intentos  <= intentos + 2'd1;
                error_reg <= 1'b1;
            end else if ((estado_siguiente == S_UNLOCK) || 
                         ((estado_actual == S_LOCKED) && (estado_siguiente == S_IDLE))) begin
                intentos  <= 2'd0;
                error_reg <= 1'b0;
            end

 		      // Guardado secuencial de la nueva clave (ignora '*' y '#')
            if (key_valid && es_digito_valido) begin
                case (estado_actual)
                    S_PROG1: pass_d1 <= key_code;
                    S_PROG2: pass_d2 <= key_code;
                    S_PROG3: pass_d3 <= key_code;
                    S_PROG4: pass_d4 <= key_code;
                    default: ; // Mantiene los valores guardados
                endcase
            end

				
        end
    end
	 
    
    always @(*) begin
        estado_siguiente = estado_actual;
        intento_fallido  = 1'b0;

        case (estado_actual)
          	// --- Validación de clave (ignora '*' y '#' en reposo) ---
            S_IDLE: begin
                if (key_valid && es_digito_valido) begin
                    estado_siguiente = (key_code == pass_d1) ? S_OK1 : S_ERR1;
                end
            end

				
            S_OK1:    if (key_valid) estado_siguiente = (key_code == pass_d2) ? S_OK2 : S_ERR2;
            S_OK2:    if (key_valid) estado_siguiente = (key_code == pass_d3) ? S_OK3 : S_ERR3;
            S_OK3:    if (key_valid) begin
                if (key_code == pass_d4) begin
                    estado_siguiente = S_UNLOCK;
                end else begin
                    intento_fallido  = 1'b1;
                    estado_siguiente = (intentos == 2'd2) ? S_LOCKED : S_IDLE;
                end
            end

            // --- Camino de error ---
            S_ERR1:   if (key_valid) estado_siguiente = S_ERR2;
            S_ERR2:   if (key_valid) estado_siguiente = S_ERR3;
            S_ERR3:   if (key_valid) begin
                intento_fallido  = 1'b1;
                estado_siguiente = (intentos == 2'd2) ? S_LOCKED : S_IDLE;
            end
							
				// --- Cerradura abierta: '*' cierra, ('#' AND llave) entra a programar ---
            S_UNLOCK: begin
                if (key_valid) begin
                    if (key_code == KEY_LOCK)
                        estado_siguiente = S_IDLE;
                    else if ((key_code == KEY_PROG) && prog_sync)
                        estado_siguiente = S_PROG1;
                    else if (key_code == KEY_PROG)
                        estado_siguiente = S_UNLOCK; // Ignora '#' si la llave no está activada
                    else
                        estado_siguiente = (key_code == pass_d1) ? S_OK1 : S_ERR1;
                end
            end
				      
            // --- Estados de programación de 4 dígitos (ignoran '*' y '#') ---
            S_PROG1: if (key_valid && es_digito_valido) estado_siguiente = S_PROG2;
            S_PROG2: if (key_valid && es_digito_valido) estado_siguiente = S_PROG3;
            S_PROG3: if (key_valid && es_digito_valido) estado_siguiente = S_PROG4;
            S_PROG4: if (key_valid && es_digito_valido) estado_siguiente = S_IDLE; // Guarda el 4to y cierra
	
	
            // --- Bloqueo permanente ---
            //S_LOCKED: estado_siguiente = S_LOCKED;
				// --- Bloqueo por 3 fallos: se libera con Reset o girando la llave (prog_sync) ---
            S_LOCKED: begin
                if (prog_sync)
                    estado_siguiente = S_IDLE;
            end
				
            default:  estado_siguiente = S_IDLE;
        endcase
    end

    assign unlock    = (estado_actual == S_UNLOCK);
    assign locked    = (estado_actual == S_LOCKED);
    assign error_led = error_reg;
    assign prog_mode = (estado_actual == S_PROG1) || (estado_actual == S_PROG2) ||
                       (estado_actual == S_PROG3) || (estado_actual == S_PROG4);
	 assign ready     = (estado_actual == S_IDLE); // <-- NUEVO: Activa solo en estado inicial

endmodule
