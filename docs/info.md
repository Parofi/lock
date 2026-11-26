<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be
smaller than 512 kb, and should be named sequentially (e.g. `info1.png`, `info2.png`).

-->

## How it works

This project implements a programmable 4-digit digital combination lock controlled by a 4x4 matrix keypad, designed as a synchronous Finite State Machine (FSM) running at a 1 MHz system clock.

### Internal Architecture
1. **Input Synchronizer:** A two-stage flip-flop synchronizer samples the 4 asynchronous keypad row inputs (`ui_in[3:0]`) to prevent metastability.
2. **Matrix Scanner & Debouncer:** Continuously scans the 4 keypad columns (`uo_out[3:0]`) using active-low strobes (~1 ms per column) and applies a 10 ms (`10,000` clock cycles at 1 MHz) debounce filter to produce a clean, single-cycle `key_valid` strobe per keypress.
3. **Security & Programming FSM:**
   - **Default Passcode:** After an active-low reset (`rst_n = 0`), the passcode defaults to **`1 - 2 - 3 - 4`**.
   - **Unlock (`uo_out = 1`):** Entering the matching 4-digit sequence asserts `unlock` and clears any previous error flag.
   - **Manual Lock (`*` key):** While unlocked, pressing **`*`** immediately closes the lock (`unlock = 0`) and returns to the idle state without modifying the stored passcode.
   - **Passcode Programming (`#` key):** While unlocked, pressing **`#`** enters programming mode (`prog_mode = 1` on `uo_out`). The next 4 digits entered overwrite the internal passcode registers and automatically return the lock to the closed state.
   - **Error & Lockout (`uo_out` & `uo_out`):** To avoid leaking partial matches, the FSM evaluates complete 4-digit attempts. An incorrect 4-digit sequence asserts `error` (`uo_out`). After **3 consecutive failed attempts**, the system enters a permanent lockout state (`locked = 1` on `uo_out`) that ignores all keypad inputs until `rst_n` is asserted.

### Pinout Summary

| Pin | Direction | Function |
| :--- | :--- | :--- |
| `ui_in[3:0]` | Input | Keypad Rows 0–3 (active-low, external 10 kΩ pull-ups required) |
| `uo_out[3:0]` | Output | Keypad Columns 0–3 (active-low column scan) |
| `uo_out` | Output | `unlock` — High (`1`) when unlocked |
| `uo_out` | Output | `error` — High (`1`) after an incorrect 4-digit attempt |
| `uo_out` | Output | `locked` — High (`1`) after 3 consecutive failed attempts |
| `uo_out` | Output | `prog_mode` — High (`1`) while recording a new 4-digit passcode |

---

## How to test

1. **Power & Clock:** Supply 3.3 V (or nominal I/O voltage for the Tiny Tapeout carrier board), configure the project clock to **1 MHz**, and pulse `rst_n` low (`0`) then high (`1`) to initialize the lock to its default code (`1-2-3-4`).
2. **Unlock Test:** Enter **`1` → `2` → `3` → `4`** on the keypad. Verify that `uo_out` (`unlock`) goes high (`1`).
3. **Manual Lock Test:** While `uo_out` is high, press **`*`**. Verify that `uo_out` returns to `0`. Re-enter **`1` → `2` → `3` → `4`** to confirm it unlocks again.
4. **Programming Test:** While unlocked (`uo_out = 1`), press **`#`**. Verify that `uo_out` (`prog_mode`) goes high (`1`). Enter a new 4-digit code (for example, **`2` → `5` → `8` → `0`**). After the 4th digit, `uo_out` turns off and the lock closes. Verify that `1-2-3-4` triggers `uo_out` (`error`) while `2-5-8-0` asserts `uo_out` (`unlock`).
5. **Lockout Test:** From the locked state, enter any wrong 4-digit sequence three times in a row. On the 3rd failure, verify that `uo_out` (`locked`) asserts high (`1`) and that entering the valid passcode no longer unlocks the system until `rst_n` is toggled low.

---

## External hardware

- **4x4 Matrix Keypad:** Standard 16-key membrane or mechanical matrix keypad (`1-9`, `0`, `A-D`, `*`, `#`) connected to `ui_in[3:0]` (rows) and `uo_out[3:0]` (columns).
- **4 × 10 kΩ Pull-up Resistors:** Connected between 3.3 V (VCC) and each of the 4 row inputs (`ui_in` through `ui_in`), since internal pull-ups are not enabled by default on `ui_in`.
- **4 × Status LEDs (with 330 Ω–1 kΩ current-limiting resistors):** Connected to `uo_out` (Unlock), `uo_out` (Error), `uo_out` (Locked), and `uo_out` (Programming Mode) to observe lock status.
