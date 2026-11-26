# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

# Mapeo físico de cada tecla a (fila, columna) según la matriz 4x4:
# Col 0: 1, 4, 7, *
# Col 1: 2, 5, 8, 0
# Col 2: 3, 6, 9, #
# Col 3: A, B, C, D
KEYMAP = {
    '1': (0, 0), '2': (0, 1), '3': (0, 2), 'A': (0, 3),
    '4': (1, 0), '5': (1, 1), '6': (1, 2), 'B': (1, 3),
    '7': (2, 0), '8': (2, 1), '9': (2, 2), 'C': (2, 3),
    '*': (3, 0), '0': (3, 1), '#': (3, 2), 'D': (3, 3),
}


def get_outputs(dut):
    """Extrae las señales individuales del bus uo_out."""
    uo = int(dut.uo_out.value)
    return {
        "col":       uo & 0x0F,
        "unlock":    (uo >> 4) & 1,
        "error":     (uo >> 5) & 1,
        "locked":    (uo >> 6) & 1,
        "prog_mode": (uo >> 7) & 1,
    }


async def reset_dut(dut):
    """Reinicia el ASIC y verifica estado inicial."""
    dut.ena.value = 1
    dut.ui_in.value = 0x0F  # Todas las filas en alto (pull-up, sin teclas)
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)


async def press_key(dut, key_char):
    """Simula la pulsación física en la matriz 4x4 respetando barrido y antirrebote."""
    row_idx, col_idx = KEYMAP[key_char]
    target_col_mask = 1 << col_idx

    # 1. Esperar a que el ASIC active la columna correspondiente (activo en bajo)
    for _ in range(6000):
        await RisingEdge(dut.clk)
        col_val = int(dut.uo_out.value) & 0x0F
        if (col_val & target_col_mask) == 0:
            break
    else:
        raise TimeoutError(f"Timeout esperando barrido de columna {col_idx} para tecla '{key_char}'")

    # 2. Bajar la fila correspondiente para simular contacto físico
    dut.ui_in.value = 0x0F & ~(1 << row_idx)

    # 3. Mantener presionada por > 10,000 ciclos (DEBOUNCE_LIMIT = 10,000 + margen sincronizador)
    await ClockCycles(dut.clk, 10_050)

     # 4. Soltar la tecla (volver filas a alto) y dar tiempo a que avance el barrido
    dut.ui_in.value = 0x0F
    await ClockCycles(dut.clk, 1500)
    
    # 4. Soltar la tecla (volver filas a alto) y esperar estabilización
    #dut.ui_in.value = 0x0F
    #await ClockCycles(dut.clk, 50)


async def enter_sequence(dut, seq_str):
    """Ingresa una cadena de teclas secuencialmente."""
    for ch in seq_str:
        await press_key(dut, ch)


@cocotb.test()
async def test_cerradura_completa(dut):
    """Prueba integral: apertura, cierre con '*', programación con '#' y bloqueo por 3 fallos."""
    # Reloj de 1 MHz (1000 ns) configurado en info.yaml
    clock = Clock(dut.clk, 1000, units="ns")
    cocotb.start_soon(clock.start())

    await reset_dut(dut)

    # Verificar que uio_oe permanece en 0
    assert int(dut.uio_oe.value) == 0, "uio_oe debe mantenerse en 0"

    # ------------------------------------------------------------------------
    # PRUEBA 1: Apertura con clave por defecto (1-2-3-4)
    # ------------------------------------------------------------------------
    dut._log.info("Prueba 1: Abriendo con clave por defecto 1234...")
    await enter_sequence(dut, "1234")
    out = get_outputs(dut)
    assert out["unlock"] == 1, "FALLO: unlock debe ser 1 tras ingresar 1234"
    assert out["error"] == 0, "FALLO: error debe ser 0"
    assert out["locked"] == 0, "FALLO: locked debe ser 0"

    # ------------------------------------------------------------------------
    # PRUEBA 2: Cierre manual con '*' y reapertura
    # ------------------------------------------------------------------------
    dut._log.info("Prueba 2: Cerrando manualmente con '*'...")
    await press_key(dut, '*')
    out = get_outputs(dut)
    assert out["unlock"] == 0, "FALLO: unlock debe apagarse al presionar '*'"
    assert out["prog_mode"] == 0, "FALLO: prog_mode no debe activarse con '*'"

    dut._log.info("Reabriendo con 1234 para verificar que la clave no cambio...")
    await enter_sequence(dut, "1234")
    assert get_outputs(dut)["unlock"] == 1, "FALLO: debe reabrir con 1234"

    # ------------------------------------------------------------------------
    # PRUEBA 3: Programación de nueva clave con '#' (Nueva clave: 2580)
    # ------------------------------------------------------------------------
    dut._log.info("Prueba 3: Entrando a modo programacion con '#'...")
    await press_key(dut, '#')
    out = get_outputs(dut)
    assert out["unlock"] == 0, "FALLO: unlock debe apagarse al entrar a programar"
    assert out["prog_mode"] == 1, "FALLO: prog_mode debe encenderse tras '#'"

    dut._log.info("Grabando nueva clave 2580...")
    await enter_sequence(dut, "2580")
    out = get_outputs(dut)
    assert out["prog_mode"] == 0, "FALLO: prog_mode debe apagarse tras el 4to digito"
    assert out["unlock"] == 0, "FALLO: cerradura debe quedar cerrada tras programar"

    # Verificar que la clave anterior (1234) ya no abre (cuenta como 1er fallo)
    dut._log.info("Verificando que la clave anterior 1234 falla...")
    await enter_sequence(dut, "1234")
    out = get_outputs(dut)
    assert out["unlock"] == 0, "FALLO: la clave vieja 1234 no debe abrir"
    assert out["error"] == 1, "FALLO: error debe encenderse tras clave vieja"

    # Verificar que la nueva clave (2580) sí abre y limpia el error
    dut._log.info("Abriendo con la nueva clave 2580...")
    await enter_sequence(dut, "2580")
    out = get_outputs(dut)
    assert out["unlock"] == 1, "FALLO: la nueva clave 2580 debe abrir"
    assert out["error"] == 0, "FALLO: error debe limpiarse al abrir"

    # Cerrar con '*' antes de probar el bloqueo
    await press_key(dut, '*')
    assert get_outputs(dut)["unlock"] == 0

    # ------------------------------------------------------------------------
    # PRUEBA 4: Bloqueo de seguridad tras 3 intentos fallidos
    # ------------------------------------------------------------------------
    dut._log.info("Prueba 4: Probando bloqueo tras 3 intentos fallidos...")
    for intento in range(1, 4):
        await enter_sequence(dut, "9999")
        out = get_outputs(dut)
        if intento < 3:
            assert out["error"] == 1, f"FALLO: error debe activarse en fallo {intento}"
            assert out["locked"] == 0, f"FALLO: no debe bloquearse en fallo {intento}"
        else:
            assert out["locked"] == 1, "FALLO: locked debe activarse en el 3er fallo"

    # Intentar abrir con la clave correcta (2580) estando bloqueado
    dut._log.info("Verificando que el bloqueo ignora la clave correcta 2580...")
    await enter_sequence(dut, "2580")
    out = get_outputs(dut)
    assert out["unlock"] == 0, "FALLO: no debe abrir estando bloqueado"
    assert out["locked"] == 1, "FALLO: locked debe mantenerse activo hasta reset"

    dut._log.info("TODAS LAS PRUEBAS PASARON EXITOSAMENTE.")
