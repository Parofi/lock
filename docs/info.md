<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be
smaller than 512 kb, and should be named sequentially (e.g. `info1.png`, `info2.png`).

-->

## How it works

This project implements a **digital electronic lock based on a Finite State Machine (FSM)** designed to operate with a 4x4 matrix keypad and a physical security key switch, operating at a clock frequency of **1 MHz**.

### Internal Architecture
1. **Matrix Synchronization and Scanning:**
   * The 4 row lines on the keyboard ('ui_in[3:0]') pass through double Flip-Flop synchronizers to avoid metastability.
   * The controller performs an active low-scan across the 4 columns ('uo_out[3:0]') at a rate of **1 ms per column** ('1,000' cycles at 1 MHz). When a keystroke is detected, the scan freezes to stabilize the reading.
2. **Debouncer Filter:**
   * Includes a **10 ms** timer ('10,000' cycles) plus a clean edge detector that generates a validation pulse of 1 cycle ('key_valid') per physical press, preventing multiple readings when holding down a key.
3. **Security States Machine (13 States):**
   * **Default key:** After a reset ('rst_n = 0'), the initial password set is **'1-2-3-4'**.
   * **Availability indicator ('ready' in 'uio_out'):** Remains at '1' only when the lock is at rest ('S_IDLE') waiting for the first digit, turning off as soon as a sequence begins.
   * **Control key filtering:** The '*' (close) and '#' (programming) keys are ignored at rest ('S_IDLE') and during key changes ('S_PROG1.. 4') to avoid false errors or invalid passwords.
   * **Physical key-protected reprogramming:** With the lock open ('unlock = 1'), pressing '#' along with the active key switch ('ui_in = 1', logical AND function) enables programming mode ('prog_mode = 1') to write 4 new digits ('0'–'9', 'A'–'D').
   * **Master lock and recovery:** After **3 consecutive failed attempts**, the system enters a locked state ('locked = 1'), ignoring the keyboard until it receives a 'rst_n' or activates the physical key ('ui_in = 1').

---

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

1. **Clock Setup and Reset:**
   * Set the clock on the Tiny Tapeout card to **1 MHz** ('1,000,000 Hz').
   * Make sure the key switch ('ui_in') is set to **'0' (GND)** and press the **Reset ('rst_n')** button.
   * Verify that the **'ready' ('uio_out')** LED lights up ('1') and the other LEDs are off.

2. **Default Key Opening and Manual Closing:**
   * Enter the sequence **'1' - '2' - '3' - '4'** on the matrix keyboard. Pressing '1' will turn off 'ready'; completing '4' will turn off the **'unlock' ('uo_out')** LED.
   * Press **'*'** to manually close the lock ('unlock' turns off and 'ready' turns back on).

3. **Password Change Protected:**
   * Opens the lock with '1-2-3-4'.
   * Try pressing **'#'** with 'ui_in[4] = 0': the system will ignore it without activating 'prog_mode'.
   * Activate the key switch (**'ui_in[4] = 1'**) and press **'#'**: the LED **'prog_mode' ('uo_out')** will light up.
   * Enter 4 new valid digits (for example, **'9' - '8' - '7' - '6'**). At the fourth digit, 'prog_mode' will turn off.
   * Return the key switch to **'0'**, close the lock with **'*'** and check that it now opens with '9-8-7-6'.

4. **Block for 3 Bugs and Master Unlock:**
   * With the lock closed, enter three incorrect 4-digit passwords (for example, '1-2-3-4', '0-0-0-0', 'A-B-C-D').
   * On the first two failures, **'error' ('uo_out')** will be on; on the third failure, **'locked' ('uo_out')** will be turned on and 'ready' will be turned off.
   * To release the lock without resetting the saved password, briefly activate the key switch (**'ui_in = 1'**) and set it back to **'0'**: 'locked' and 'error' will turn off and 'ready' will return to '1'.

---


## External hardware

To operate the ASIC on real hardware, the following external components connected to the Tiny Tapeout headers (logic levels of **3.3 V**) are required:

* **Passive 4x4 Matrix Keyboard:**
  * **Columns (ASIC Outputs):** Connect 'uo_out[3:0]' to the 4 keyboard columns ('Col0' = 'uo_out', 'Col1' = 'uo_out', 'Col2' = 'uo_out', 'Col3' = 'uo_out'). *(Optional: place 1N5819 Schottky diodes in series for protection against simultaneous keys).*
  * **Rows (ASIC Inputs):** Connect 'ui_in[3:0]' to the 4 rows of the keyboard ('Row0' = 'ui_in', 'Row1' = 'ui_in', 'Row2' = 'ui_in', 'Row3' = 'ui_in') with **4 external Pull-up resistors of 10 kΩ connected to 3.3 V**.
* **Physical Key Switch (or SPST Switch):**
  * Connected between **3.3 V** and pin **'ui_in'**, accompanied by a **10 kΩ GND Pull-down resistor** to ensure a stable logical '0' when the key is removed.
* **5 Status Indicator LEDs (with limiting resistors from 330 Ω to GND):**
  * **'uo_out' ('unlock'):** Green LED (Open lock / control signal to power stage for solenoid).
  * **'uo_out' ('error'):** Amber/Yellow LED (Incorrect password).
  * **'uo_out' ('locked'):** Red LED (Security lock after 3 failures).
  * **'uo_out' ('prog_mode'):** Blue LED (Active programming mode).
  * **'uio_out' ('ready'):** White/Light Green LED (Lock ready at rest).
