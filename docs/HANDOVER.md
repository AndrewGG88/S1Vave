# S1Vave Firmware: Technical Handover & Developer Guide

> **Hardware Target**: M-VAVE FM-1 Synthesizer (JieLi AC791N 32-bit RISC MCU)  
> **Reference Instrument**: Roland AIRA Compact S-1 Tweak Synth (Roland SH-101 Heritage)  
> **Base Platform**: OberVave (`obervave-main` / Dinghy platform by zvenson & Leo Kuroshita)  
> **License**: GNU General Public License v3.0 (GPL-3.0-only)

---

## 1. Executive Summary & Project Purpose

The **S1Vave** project converts the inexpensive, portable **M-VAVE FM-1** hardware into an open-source clone of the **Roland AIRA Compact S-1 Tweak Synth**.

The firmware preserves 1:1 acoustic, functional, and MIDI CC parity with the Roland S-1, including:
- 8-Voice polyphony with Mono (legato), Unison (8-voice stacking), Poly (8-voice dynamic allocation), and Chord modes.
- Classic SH-101 oscillator core: Sawtooth, Pulse/Square with dynamic Pulse Width Modulation (PWM), Sub-Oscillator ($-1\text{oc}$, $-2\text{oc}$, $-2\text{o.A}$ asymmetric), and calibrated Pink/White Noise.
- Roland S-1 exclusive features: **OSC DRAW** (Step/Slope wave drawing, 1x–32x multiplier) and **OSC CHOP** (16-step bitmask slicing, 1x–32x comb, 0–200 overtone with $>100$ reverse phase).
- 4-Pole (24 dB/oct) cascaded state-variable filter with analog resonance saturation and self-oscillation.
- ADSR Envelope with Gate, Gate+Trig, and LFO re-triggering.
- LFO with 6 waveforms, audio-rate Fast mode, tempo sync note divisions, and key trigger.
- Roland S-1 FX suite: Chorus (4 types), Tempo-synced Delay (with tape slewing), and Plate Reverb.
- Dual-Track 64-step sequencer with motion recording, probability, and ratchets.

This document provides a comprehensive handover for any incoming firmware developer, audio DSP engineer, or AI coding assistant.

---

## 2. Hardware Architecture & Technical Constraints

The M-VAVE FM-1 is based on the **JieLi AC791N** (`pi32v2` RISC core) microcontroller.

```
+-------------------------------------------------------------------------------+
|                                M-VAVE FM-1 Hardware                           |
|  +--------------------+  +----------------------+  +-----------------------+  |
|  | 4 Push-Encoders    |  | 16 Tactile Step Keys |  | ST7789 240x240 LCD    |  |
|  | (K1, K2, K3, K4)   |  | + Function Buttons   |  | (SPI DMA, RGB565)     |  |
|  +---------+----------+  +----------+-----------+  +-----------+-----------+  |
|            |                        |                          |              |
|            +-------------------+    |    +---------------------+              |
|                                |    |    |                                    |
|  +-----------------------------v----v----v---------------------------------+  |
|  |                     JieLi AC791N RISC Core (pi32v2)                     |  |
|  |  * No Hardware FPU (Pure Integer Fixed-Point Math: Q15, Q13, Q12, Q8)   |  |
|  |  * No 64-Bit Division (__udivdi3 / __divdi3 will fail linker check)     |  |
|  |  * Forbidden ROM Range: 0xFFC00000 - 0xFFCFFFFF (linker trap check)     |  |
|  |  * Internal SRAM: <= 96 KB data, Large Buffers allocated in .pool      |  |
|  +-------------------------------------+-----------------------------------+  |
|                                        |                                      |
|  +-------------------------------------v-----------------------------------+  |
|  |             Audio ISR Engine (44.1 kHz, 256 frames = 5.80 ms)           |  |
|  |  * Processing block: CTL = 16 frames (362.8 us per control block)       |  |
|  |  * Total CPU Budget: < 2.90 ms per ISR call (< 50% CPU load)           |  |
|  +-------------------------------------+-----------------------------------+  |
|                                        |                                      |
|  +-------------------------------------v-----------------------------------+  |
|  |             USB Audio (Felucca UAC 44.1 kHz 16-bit Stereo)              |  |
|  |             USB-MIDI Class-Compliant Device (In / Out)                  |  |
|  +-------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------+
```

### Strict AC791N Rules:
1. **Integer Arithmetic Only**:
   - The chip has no floating point unit. All DSP equations must be fixed-point.
   - Phase accumulators: `uint32_t` ($0 \dots 2^{32}-1$).
   - Waveform values: signed 16-bit (`int16_t` range `[-32768, 32767]`) with 32-bit headroom during mixing and filtering.
   - Filter coefficients: Q13 (`8192 = 1.0`).
2. **Strict Prohibition of 64-Bit Division**:
   - 64-bit multiplications (`(int64_t)a * b`) are accelerated by hardware instructions.
   - 64-bit division or modulo (`/` or `%` on `int64_t` or `uint64_t`) requires `__divdi3` / `__udivdi3` software routines, which are **not linked** and will fail the build guard.
   - Always divide by powers of two via bit-shifts (`>> N`) or use 32-bit operands.
3. **ROM Collision Trap**:
   - Memory addresses in `0xFFC00000..0xFFCFFFFF` represent the on-chip boot ROM.
   - Constants, jump tables, and bitmask shifts must never produce values in this range (`tools/build.py` enforces this with an automatic static check).
4. **Memory Layout**:
   - Fast SRAM (`.data` / `.bss`): $\le 96\text{ KB}$ for voice descriptors, UI buffers, and state variables.
   - Delay / Reverb ring buffers are allocated in `.pool` memory ($\le 336\text{ KB}$).

---

## 3. Firmware Codebase Structure (`firmware/src/`)

```
firmware/src/
├── s1vave.c         # Main entry point, event loop, LCD render loop, USB-MIDI I/O, flash storage
├── obv_params.h     # Complete parameter table (PDEF), MIDI CC map, UI page definitions, display strings
├── obv_dsp.h        # Oscillator step algorithms, PolyBLEP edge smoothing, SVF filter, Pink/White noise
├── obv_engine.h     # Voice allocator, ADSR envelopes, LFO generator, PWM modulation, voice rendering
├── obv_seq.h        # Step sequencer, chord memory, ratchet/probability engines, DRAW & CHOP tables
├── obv_fx.h         # 2-tap chorus, tempo-synced ping-pong delay, Dattorro plate reverb
├── obv_ui.h         # ST7789 display rendering, S-1 color palette, 4-digit 7-segment display emulator
├── platform.c       # Hardware abstraction layer (Dinghy HAL) for AC791N
├── usb.c            # USB-MIDI and USB-Audio (UAC) driver with ring-buffer watermarks
├── ota.c            # Firmware update & flash installer routines
└── lcd.c / gfx.c    # SPI DMA display driver & graphic primitives
```

---

## 4. Key DSP Calibrations & Mathematical Parity

### 4.1 Pulse Width Modulation (PWM) & Phase Modulation

#### Roland S-1 Specification:
- **PWM Source (`CC 16`)**:
  - `0` = **ENV** (Envelope sweeps the pulse width)
  - `1` = **MAN** / `NAn` (Manual fixed pulse width set by `CC 15`)
  - `2` = **LFO** (LFO cyclically modulates the pulse width symmetrically)
- **PWM Depth (`CC 15`)**:
  - In Manual mode (`CC 16 = 1`): Sets pulse width from 50% square wave (value 0) down to ~5% needle pulse (value 127).
  - In LFO mode (`CC 16 = 2`): Adjusts the modulation swing from $50\% \pm 0\%$ up to $50\% \pm 45\%$ ($5\% \dots 95\%$ duty cycle).
  - In ENV mode (`CC 16 = 0`): Sweeps pulse width from 50% down to 5% at peak envelope.

#### Firmware Implementation in `obv_params.h` and `obv_engine.h`:
```c
/* obv_params.h */
enum { PWM_ENV, PWM_MANUAL, PWM_LFO }; /* 0=ENV, 1=MAN, 2=LFO */
static const char *const PWMS_NAME[3] = {"ENV", "MAN", "LFO"};

/* obv_engine.h - Block calculation (CTL = 16 frames) */
if (g->pwm_src == PWM_LFO) {
    /* LFO modulates pulse width symmetrically around 50% square wave (0x80000000u) */
    int64_t p = (int64_t)0x80000000u + (((int64_t)lfo * (int32_t)pv[P_PWM_DEPTH]) * 464);
    if (p < (1 << 26)) p = 1 << 26;
    if (p > (int64_t)0xFFFFFFFFu - (1 << 26)) p = (int64_t)0xFFFFFFFFu - (1 << 26);
    v->pw = (uint32_t)p;
} else if (g->pwm_src == PWM_ENV) {
    /* Envelope sweeps pulse width symmetrically from 50% square wave */
    int64_t p = (int64_t)0x80000000u - (((int64_t)fenv * (int32_t)pv[P_PWM_DEPTH]) * 464);
    if (p < (1 << 26)) p = 1 << 26;
    if (p > (int64_t)0xFFFFFFFFu - (1 << 26)) p = (int64_t)0xFFFFFFFFu - (1 << 26);
    v->pw = (uint32_t)p;
} else {
    /* Manual Duty Cycle: 0 = 50% square wave, 127 = ~5% narrow pulse */
    uint32_t delta = (uint32_t)pv[P_PWM_DEPTH] * 0x00E80000u;
    v->pw = 0x80000000u - delta;
}
```

- **PolyBLEP Anti-Aliased Pulse Generator (`obv_dsp.h`)**:
  The pulse is synthesized via `saw(ph) - saw(ph + pw)` with PolyBLEP polynomial edge correction triggered when `ph + pw < inc`. Clamping limits to $[1\ll 26, 2^{32} - (1\ll 26)]$ guarantee that pulses never collapse to 0% or 100%, preventing edge glitches.

---

### 4.2 Pink Noise Generator & Warmth Filter

#### Issue Discovered:
In earlier revisions, `pink_noise_step` used an unattenuated 3-pole Gardner filter clamped against $\pm 32767$, hard-clipping ~24.4% of all generated noise samples and causing harsh high-frequency digital fizz.

#### Solution in `obv_dsp.h`:
1. Re-scaled Gardner pole coefficients:
   $$b_0 = 1228, \quad b_1 = 1638, \quad b_2 = 3276$$
2. Added a 2-pole analog warmer lowpass filter ($k_1=11000, k_2=18000$):
   $$w_1 += \frac{(raw - w_1) \cdot 11000}{32768}, \quad w_2 += \frac{(w_1 - w_2) \cdot 18000}{32768}$$
3. Result: **0 clipped samples**, with an exact 12 dB/oct roll-off above 1.8 kHz ($-30\text{ dB}$ attenuation at 12.8 kHz), matching the Roland S-1 hardware noise spectrum.

---

### 4.3 Voice Allocation & Mono Centering

- Standardized `P_POLY_MODE` (`CC 80`) to 4 modes:
  - `0` = **MONO** (Single voice, legato glide)
  - `1` = **UNISON** (Stacked 8-voice massive unison)
  - `2` = **POLY** (8-voice dynamic polyphonic allocation)
  - `3` = **CHORD** (Chord memory using Voice shifts)
- Removed legacy voice-card detune (`VINT_TUNE8`, `VINT_PW8`, `VINT_ENV` set to 0) and card pan spread (`PAN_CARD`). All dry voice outputs are 100% center mono ($|L - R| = 0.0$), ensuring identical dry behavior to the Roland S-1.

---

### 4.4 Volume Level Calibration (+10.2 dB Dynamics Match)

When comparing the initial port against the physical Roland S-1, the M-Vave output was observed to be ~10 dB lower in volume. Investigation revealed three distinct bottlenecks:
1. **Q15 Amplitude Scaling**: In `obv_engine.h:909`, voice render mixed `y = (y * amp) >> 16`. Since `amp` is a Q15 envelope value ($32767 = 1.0$), shifting by 16 halved the output amplitude ($-6.02\text{ dB}$). Correcting to `>> 15` fully restored the 6 dB headroom.
2. **Master Volume Audio Taper**: The previous `P_VOLUME` implementation used a quadratic power curve `(d * d) >> 2`, which attenuated default preset volumes (at value 100) by an additional $-4.2\text{ dB}$. Replaced with a smooth audio taper `(int32_t)d * 24 + ((int32_t)d * d >> 4)`.
3. **Hardware Volume Pot Boot**: Added immediate physical potentiometer reading in `platform.c` upon startup (`master_boot()`) so the master amplifier initializes immediately to the knob position without requiring physical motion.
4. **Soft-Clipping Saturation**: Replaced hard integer clipping (`sat16()`) at the FX output stage with smooth polynomial soft-clipping in `obv_fx.h:360`, allowing saturated chord transients to compress naturally without harsh digital folding.

---

### 4.5 USB Audio Ring Buffer & Underrun Elimination

#### Root Cause:
- The audio ISR renders blocks of **256 frames** (5.80 ms at 44.1 kHz).
- Computing 4 voices with cascaded SVF filters, envelopes, chorus, and reverb takes ~3.5 ms of CPU time. The firmware only calls `uac_tap()` to push audio into the USB ring buffer after the 256-frame render completes.
- USB Host isochronous transfers pull packets every **1.0 ms** (~44–48 frames/ms). Over 3.5 ms, the host drains ~154–168 frames.
- The previous buffer settings were hardcoded for 128-frame renders: `UA_PRIME = 104`, `UA_LO = 80`, `UA_HI = 128`, `UA_N = 512`.
- Because $154 > 104$, the USB buffer ran completely dry (underrun) on every single audio block (172 times/second), resulting in severe robotic stuttering.

#### Solution in `usb.c`:
- Increased ring buffer size `UA_N` to **1024 frames** (4 KB RAM).
- Re-calibrated 44.1 kHz watermarks: `UA_PRIME = 240u`, `UA_LO = 200u`, `UA_HI = 280u`.
- Re-calibrated 48.0 kHz watermarks: `UA_PRIME48 = 260u`, `UA_LO48 = 220u`, `UA_HI48 = 300u`.
- Verified 0 underruns and 0 overruns under maximum polyphonic CPU load.

---

## 5. Build, Simulation & Flashing Instructions

### Prerequisites (Linux x86_64 or WSL2)
```bash
sudo apt update
sudo apt install -y python3 python3-pip git build-essential pipewire alsa-utils
pip3 install Pillow mido python-rtmidi
```

### 1. Build Hardware Firmware Package
```bash
cd s1vave-main
./build.sh --release 1.0
```
- Compiles with JieLi `pi32v2-clang` and AC79 SDK.
- Output binary: `build/s1vave-1.0.fwsc` (packaged with bootloader header, identity `FM-1_950`).

### 2. Flash to M-VAVE FM-1 Hardware
Connect the FM-1 via USB-C (in normal operational mode or bootloader mode):
```bash
python3 tools/fm1_install.py build/s1vave-1.0.fwsc --yes
```
The script uploads the binary via USB HID, checks CRC, and automatically restarts the FM-1 into the new firmware.

### 3. Build & Run WebAssembly Simulation
```bash
cd s1vave-main
sh web/sim/build.sh
python3 -m http.server 8737 -d docs/sim
```
Open `http://localhost:8737/` in any browser to test the full firmware compiled to WebAssembly, or open `http://localhost:8737/editor/index.html` for the Dual Synth Calibration Studio.

---

## 6. Open Source Heritage & Attribution

This firmware is distributed under the **GNU General Public License v3.0 (GPL-3.0-only)**.
- **Base Platform**: [Dinghy](https://github.com/zvenson/dinghy) by zvenson.
- **Hardware Integration**: [Felucca](https://github.com/hugelton/Felucca) by Leo Kuroshita (@kurogedelic), Hügelton Instruments, and [SLOOP](https://github.com/isod89/sloop-fm1) by isod89.
- **SMK-37 Port**: M. Geisler (genkigenki/makkuro).
- **Roland S-1 Parity Engine & Calibration**: Andrew GG.
- **Trademarks Notice**: Roland, AIRA, AIRA Compact, S-1, and SH-101 are registered trademarks of Roland Corporation. This project is an independent open-source clean-room implementation created for educational and preservation purposes. Not affiliated with or endorsed by Roland Corporation.
