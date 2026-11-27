import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

KEYMAP = {
    '1': (0, 0), '2': (0, 1), '3': (0, 2), 'A': (0, 3),
    '4': (1, 0), '5': (1, 1), '6': (1, 2), 'B': (1, 3),
    '7': (2, 0), '8': (2, 1), '9': (2, 2), 'C': (2, 3),
    '*': (3, 0), '0': (3, 1), '#': (3, 2), 'D': (3, 3),
}


def get_outputs(dut):
    uo = int(dut.uo_out.value)
    return {
        "col":       uo & 0x0F,
        "unlock":    (uo >> 4) & 1,
        "error":     (uo >> 5) & 1,
        "locked":    (uo >> 6) & 1,
        "prog_mode": (uo >> 7) & 1,
    }


async def reset_dut(dut):
    dut.ena.value = 1
    dut.ui_in.value = 0x0F
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)
    assert int(dut.uio_oe.value) == 0, "uio_oe debe mantenerse en 0"


async def press_key(dut, key_char):
    row_idx, col_idx = KEYMAP[key_char]
    target_col_mask = 1 << col_idx

    # 1. Esperar a que la columna este inactiva (1)
    for _ in range(10000):
        await ClockCycles(dut.clk, 1)
        if ((int(dut.uo_out.value) & 0x0F) & target_col_mask) != 0:
            break

    # 2. Esperar a que la columna pase a activa (0)
    for _ in range(10000):
        await ClockCycles(dut.clk, 1)
        if ((int(dut.uo_out.value) & 0x0F) & target_col_mask) == 0:
            break
    else:
        raise TimeoutError(f"Timeout esperando columna {col_idx} para '{key_char}'")

    # Esperar 5 ciclos adentro de la ventana activa de 1,000 ciclos
    await ClockCycles(dut.clk, 5)

    # 3. Presionar fila y sostener > 10,000 ciclos (DEBOUNCE_LIMIT = 10,000)
    dut.ui_in.value = 0x0F & ~(1 << row_idx)
    await ClockCycles(dut.clk, 10_050)

    # 4. Soltar tecla y dar margen al sincronizador de 2 etapas
    dut.ui_in.value = 0x0F
    await ClockCycles(dut.clk, 50)


async def enter_sequence(dut, seq_str):
    for ch in seq_str:
        await press_key(dut, ch)


@cocotb.test()
async def test_cerradura_completa(dut):
    clock = Clock(dut.clk, 1000, units="ns")
    cocotb.start_soon(clock.start())

    await reset_dut(dut)

    # 1. Apertura con 1234
    await enter_sequence(dut, "1234")
    out = get_outputs(dut)
    dut._log.info(f"Tras 1234 -> {out}")
    assert out["unlock"] == 1

    # 2. Cierre con '*'
    await press_key(dut, '*')
    out = get_outputs(dut)
    dut._log.info(f"Tras '*' -> {out}")
    assert out["unlock"] == 0
    assert out["prog_mode"] == 0

    # Reapertura con 1234
    await enter_sequence(dut, "1234")
    out = get_outputs(dut)
    dut._log.info(f"Tras reabrir 1234 -> {out}")
    assert out["unlock"] == 1

    # 3. Programacion con '#' -> 2580
    await press_key(dut, '#')
    out = get_outputs(dut)
    assert out["unlock"] == 0
    assert out["prog_mode"] == 1

    await enter_sequence(dut, "2580")
    out = get_outputs(dut)
    assert out["prog_mode"] == 0
    assert out["unlock"] == 0

    # Clave vieja falla, clave nueva abre
    await enter_sequence(dut, "1234")
    assert get_outputs(dut)["error"] == 1

    await enter_sequence(dut, "2580")
    out = get_outputs(dut)
    assert out["unlock"] == 1
    assert out["error"] == 0

    await press_key(dut, '*')
    assert get_outputs(dut)["unlock"] == 0

    # 4. Bloqueo tras 3 fallos
    for intento in range(1, 4):
        await enter_sequence(dut, "9999")
        out = get_outputs(dut)
        if intento < 3:
            assert out["error"] == 1
            assert out["locked"] == 0
        else:
            assert out["locked"] == 1

    await enter_sequence(dut, "2580")
    assert get_outputs(dut)["unlock"] == 0
    assert get_outputs(dut)["locked"] == 1

