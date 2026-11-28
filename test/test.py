import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

# Mapa físico del teclado 4x4: tecla -> (valor_columna_activa, valor_fila_resultante)
KEYPAD_MAP = {
    '1': (0b1110, 0b1110), '4': (0b1110, 0b1101), '7': (0b1110, 0b1011), '*': (0b1110, 0b0111),
    '2': (0b1101, 0b1110), '5': (0b1101, 0b1101), '8': (0b1101, 0b1011), '0': (0b1101, 0b0111),
    '3': (0b1011, 0b1110), '6': (0b1011, 0b1101), '9': (0b1011, 0b1011), '#': (0b1011, 0b0111),
    'A': (0b0111, 0b1110), 'B': (0b0111, 0b1101), 'C': (0b0111, 0b1011), 'D': (0b0111, 0b0111),
}

def set_inputs(dut, row_val, key_switch):
    """Combina las 4 filas del teclado y el interruptor de llave en ui_in."""
    dut.ui_in.value = ((key_switch & 0x1) << 4) | (row_val & 0xF)

async def press_key(dut, key_char, key_switch=0):
    """Simula la pulsación física sincronizada con el barrido y antirrebote (10 ms)."""
    target_col, target_row = KEYPAD_MAP[key_char]
    set_inputs(dut, 0b1111, key_switch)

    # Esperar hasta que el barrido del chip (uo_out[3:0]) active la columna de esta tecla
    for _ in range(5000):
        await RisingEdge(dut.clk)
        col_now = int(dut.uo_out.value) & 0xF
        if col_now == target_col:
            set_inputs(dut, target_row, key_switch)
            break

    # Mantener presionada por 10,500 ciclos (10.5 ms a 1 MHz) para superar DEBOUNCE_LIMIT (10,000)
    await ClockCycles(dut.clk, 10500)

    # Soltar la tecla (filas vuelven a pull-up 1111) y esperar 100 ciclos
    set_inputs(dut, 0b1111, key_switch)
    await ClockCycles(dut.clk, 100)

async def enter_code(dut, code_str, key_switch=0):
    for ch in code_str:
        await press_key(dut, ch, key_switch)

@cocotb.test()
async def test_cerradura_fsm(dut):
    dut._log.info("Iniciando simulación Cocotb para Tiny Tapeout")

    # Reloj de 1 MHz (periodo = 1 us)
    clock = Clock(dut.clk, 1, units="us")
    cocotb.start_soon(clock.start())

    # Reset inicial
    dut.ena.value = 1
    dut.uio_in.value = 0
    set_inputs(dut, 0b1111, 0)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    # Verificar estado inicial: ready=1 (uio_out[0:0]), uio_oe=1
    assert (int(dut.uio_oe.value) & 0x1) == 1, "uio_oe[0:0] debe ser 1 (salida)"
    assert (int(dut.uio_out.value) & 0x1) == 1, "ready debe iniciar en 1 tras reset"

    # 1. Ignorar '*' y '#' en reposo (S_IDLE)
    await press_key(dut, '*', key_switch=0)
    await press_key(dut, '#', key_switch=0)
    assert (int(dut.uio_out.value) & 0x1) == 1, "ready debe seguir en 1 tras '*' o '#' en S_IDLE"

    # 2. Apertura con contraseña por defecto '1234'
    await enter_code(dut, "1234", key_switch=0)
    uo = int(dut.uo_out.value)
    assert ((uo >> 4) & 0x1) == 1, "unlock (uo_out[4:4]) debe activarse con 1234"
    assert (int(dut.uio_out.value) & 0x1) == 0, "ready debe apagarse cuando esta abierta"

    # 3. Intentar programar SIN llave (key_switch=0) -> debe ignorarse
    await press_key(dut, '#', key_switch=0)
    uo = int(dut.uo_out.value)
    assert ((uo >> 7) & 0x1) == 0, "prog_mode no debe activarse sin interruptor de llave"

    # 4. Programar nueva clave '9876' CON llave (key_switch=1) e inyectando '#' y '*' en medio
    await press_key(dut, '#', key_switch=1)
    uo = int(dut.uo_out.value)
    assert ((uo >> 7) & 0x1) == 1, "prog_mode (uo_out[7:7]) debe activarse con llave + '#'"

    await press_key(dut, '9', key_switch=1)
    await press_key(dut, '#', key_switch=1) # Debe ignorarse
    await press_key(dut, '8', key_switch=1)
    await press_key(dut, '*', key_switch=1) # Debe ignorarse
    await press_key(dut, '7', key_switch=1)
    await press_key(dut, '6', key_switch=1)

    uo = int(dut.uo_out.value)
    assert ((uo >> 7) & 0x1) == 0, "prog_mode debe apagarse al completar los 4 digitos"

    # Si quedó abierta tras programar, cerramos con '*'
    if ((uo >> 4) & 0x1) == 1:
        await press_key(dut, '*', key_switch=0)

    # 5. Probar apertura con nueva clave '9876'
    await enter_code(dut, "9876", key_switch=0)
    uo = int(dut.uo_out.value)
    assert ((uo >> 4) & 0x1) == 1, "Debe abrir con la nueva clave 9876"

    # Cerrar nuevamente
    await press_key(dut, '*', key_switch=0)

    # 6. Provocar 3 fallos para activar bloqueo (locked = uo_out[6:6])
    await enter_code(dut, "1234", key_switch=0) # Fallo 1 (clave vieja)
    await enter_code(dut, "0000", key_switch=0) # Fallo 2
    await enter_code(dut, "ABCD", key_switch=0) # Fallo 3
    uo = int(dut.uo_out.value)
    assert ((uo >> 6) & 0x1) == 1, "locked (uo_out[6:6]) debe activarse tras 3 fallos"

    # 7. Desbloqueo maestro activando llave (key_switch=1)
    set_inputs(dut, 0b1111, 1)
    await ClockCycles(dut.clk, 5)
    set_inputs(dut, 0b1111, 0)
    await ClockCycles(dut.clk, 5)

    uo = int(dut.uo_out.value)
    assert ((uo >> 6) & 0x1) == 0, "locked debe apagarse tras desbloqueo con llave"
    assert (int(dut.uio_out.value) & 0x1) == 1, "ready debe volver a 1 tras desbloqueo"

    dut._log.info("¡Todas las pruebas de Tiny Tapeout pasaron correctamente!")


