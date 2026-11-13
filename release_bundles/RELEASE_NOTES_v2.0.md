# S1Vave v2.0 Release Notes

**S1Vave v2.0** focuses on major **visual & UI workflow upgrades** on both the physical M-VAVE FM-1 hardware and the **VIBE FM DAW Plugin (VST3 / CLAP / AU)**, plus full bidirectional patch, sequence, and MIDI import/export.

---

## What's New in v2.0

### VIBE FM VST Custom Editor (Import, Export & Sequencer)
- **Patch & Bank Import / Export (`.fxp` / `.fxb`)**: Save single patches or full 99-patch banks directly into `Music/VIBE FM/s1vave/` (via an in-app filename modal that avoids sandboxed WebView cancellations) and load `.fxp`/`.fxb` files back anytime.
- **Hardware $\leftrightarrow$ VST Sequence Sync (`GRAB SEQ` / `SEND SEQ`) & `.s1seq` Backup**: Transfer dual-track patterns (Tracks A & B) between the physical M-VAVE FM-1 and the VST plugin over SysEx, or export/import `.s1seq` files.
- **Standard MIDI File (`.mid`) Export**: Export your internal Tracks A & B sequencer patterns as standard multi-track `.mid` files for your DAW piano roll.
- **Interactive 64-Step Sequencer Editor**: View and edit Tracks A & B across Bars 1–4, inspect and tweak per-step Note/Chord, Velocity, Gate/Tie, Ratchet, and Chance, fast-clear a track or entire pattern (`CLEAR TRK` / `CLEAR PTN`), and toggle `KEY REC` (`● SEQ REC`) to record notes from the virtual keyboard.
- **Section Color Coding**: Clear visual color hierarchy across panels and rotary knobs (Oscillator Teal, Filter Orange, Envelope Mint, LFO Blue, FX Purple, Arpeggiator Gold).

### Hardware OLED Visuals, Menu Cleanup & Performance
- **`Page X/Y` Indicators Everywhere**: Added page counters (`1/6`, `2/4`, etc.) to every multi-page button view (`EDIT`, `ENV`, `LFO`, `FX`, `ARP`, `SEQ`, `GLO`) and fixed header overlap between `GLOBAL` and the `CPU` usage readout.
- **Category-Colored Outlines**: Synthesis vs. modulation pages use distinct frame outline colors for faster visual orientation.
- **Cleaned-Up Menu Hierarchy**: Promoted Pulse Width Modulation (`OSC PWM`) to its own dedicated `EDIT 2/6` page, trimmed unused/non-functional items (`Riser`, `Phaser`, `Filter Character`, and unused bend entries), and fixed text clipping in `ARP`.
- **Zero-Lag `OSC DRAW` & `OSC CHOP` + Reverb Eco Mode**: Decoupled wavetable rebuilds from encoder interrupts for responsive knob control, and added a toggleable `REV ECO` mode for dense 8-voice polyphonic patches.

---

## Release Downloads & Installation

- **Windows Automatic VST Firmware Installer**: `S1Vave-v2.0-Windows-Setup.exe`
- **macOS / Linux / Drag-and-Drop VIBE VST Package**: `s1vave.zip` (drag directly onto the VIBE FM plugin window)
- **Hardware Firmware (`.fwsc`)**:
  - M-VAVE FM-1: `docs/firmware/s1vave-2.0.fwsc`
  - M-VAVE SMK-37 (Pro / Elite / MKE-P37): `docs/firmware/smk37/`

See `INSTALL_GUIDE.md` (English) or `GUIA_INSTALACION.md` (Español) for step-by-step setup instructions, including the WebView2 troubleshooting tip for Ableton Live 12 on Windows.
