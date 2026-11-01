# S1Vave on the M-Vave SMK-37

S1Vave also runs on the **M-Vave SMK-37** keyboards: the **SMK-37 Pro**, the **SMK-37 Elite**, and the **MKE-P37** (and the Donner Starrykey 37 Play, using the Pro package). 

They share the same JieLi AC791N MCU as the FM-1; only the panel and interface are wired differently. The SMK-37 build runs the exact same Roland S-1 virtual analog sound engine, resonant filter, ADSR envelopes, LFO, and effects, with the SMK-37's full hardware interface put to work: the **16 velocity pads** drive the 16-step sequencer, the **4 faders** provide immediate hands-on control over the filter and effects, the **wheels** handle pitch bend and LFO vibrato, and the **37 velocity keys** play with expressive dynamics.

---

## Packages and Models

| Your Keyboard | Firmware Package | USB Identity |
| :--- | :--- | :--- |
| **SMK-37 Pro**, **Starrykey 37 Play** | `s1vave-<version>-smk37.fwsc` | `SMK-37 Pro_95XY` |
| **SMK-37 Elite** | `s1vave-<version>-smk37-elite.fwsc` | `SMK-37 Elite_95XY` |
| **MKE-P37** | `s1vave-<version>-smk37-mke.fwsc` | `MKE-P37_95XY` |

*`XY` encodes the version (e.g. `1.11` is `_9511`). Each package reports its own model name, so M-VAVE's factory updater still accepts that model's factory firmware afterwards.*

---

## Safety & Flash Protection

The SMK-37 stores factory key, pad, and wheel calibration data unique to your individual unit at flash offset `0xC1000`. 

**S1Vave never writes to this protected calibration sector.** S1Vave's flash driver strictly enforces a protected range allow-list:
- S1Vave only writes to its dedicated settings and pattern storage sectors.
- S1Vave **reads** your unit's factory calibration table to apply the manufacturer's calibrated velocity response curves across all 37 keys and 16 pads.
- **Factory Reset / Return to Stock**: You can return to factory firmware at any time by installing your model's factory `.fwsc` package using M-VAVE's M-UPGRADE utility. Because your calibration area is untouched, factory playability is completely preserved.

---

## Installation

Connect the SMK-37 via USB to your computer:

```bash
# For SMK-37 Pro (or Donner Starrykey 37 Play):
python3 tools/fm1_install.py s1vave-<version>-smk37.fwsc

# For SMK-37 Elite:
python3 tools/fm1_install.py s1vave-<version>-smk37-elite.fwsc

# For MKE-P37:
python3 tools/fm1_install.py s1vave-<version>-smk37-mke.fwsc
```

You can also flash directly in the browser via Web MIDI at [https://andrewgg.one/s1vave/](https://andrewgg.one/s1vave/).

- **USB Rescue Mode**: Hold **OCTAVE-** while switching the keyboard on. S1Vave boots directly into the update loader without starting the audio engine, allowing you to reinstall cleanly.
- **Check Status**: `python3 tools/fm1_install.py --info` reports the active firmware identity and version.

---

## Hardware Controls

| SMK-37 Control | S1Vave Function | Notes |
| :--- | :--- | :--- |
| **Keys F3 .. G5** | Core 27 Keys | Play notes; with SEQ held, white keys select steps |
| **Outer Keys** | Extended Range | `C3 .. E3` (lower) and `G#5 .. C6` (higher) with full velocity |
| **16 Velocity Pads** | 16-Step Sequencer | Step entry, hold-to-edit parameter locks, ratchets, gates |
| **< / > Buttons** | Step Pages (1–8) | Turn 16-step pages across the pattern |
| **Faders 1–4** | Dual Fader Banks | Filter & performance controls (Bank A / B) |
| **FADER BANK** | Bank Toggle | Switches between Bank A and Bank B (LED lit on Bank B) |
| **Pitch Wheel** | Pitch Bend | Smooth hardware pitch bend (±2 semitones) |
| **Mod Wheel** | LFO Vibrato (CC 1) | LFO modulation to pitch (0 to ±1/2 semitone) |
| **K1** | Master Volume | Endless encoder; turns master output level |
| **K2** | Tempo | BPM adjustment |
| **K3** | Track Select | Track A / Track B |
| **K4** | Presets & Patterns | Preset select; in sequencer, selects active pattern |
| **K5 · K6 · K7 · K8** | Knobs 1 · 2 · 3 · 4 | Four page knobs matching the on-screen display |
| **PATCH** | HOME / PERFORM | Filter Cutoff, Resonance, Env Depth, Portamento |
| **PARA** | EDIT | Cycles Oscillator Core, Sub/Noise, Draw, Chop, Filter |
| **CHORD** | ENV | Cycles ADSR Envelope & Modulation / Trigger Config |
| **NOTE REPEAT** | LFO | Cycles LFO Generator, Riser/Downer pages |
| **SCALE** | SEL | Advanced Sound / Randomizer layer |
| **GLOBE** | GLO | Global Voice Mode, Portamento, Master Tuning |
| **BT** | SAVE | Tap twice to save program / pattern to flash |
| **ARP / FX / SEQ** | Arp, FX, Sequencer | Dedicated shortcuts to Arpeggiator, Effects, Sequencer |
| **SEQ PLAY / REC** | Play / Record | Start/stop sequencer; record step notes |
| **OCTAVE- / OCTAVE+** | Octave Shift | Transpose keyboard octaves |
| **KNOB BANK** | Panel Check | **Hold to view hardware diagnostic screen** |

---

### The 16 Pads (Step Sequencer)

The 16 velocity-sensitive pads represent the 16 steps of the active pattern page (steps 1–8 on the top row, 9–16 on the bottom row):

- **Set a Step**: Tap an empty pad to enter the last-played note or chord at the pad's struck velocity.
- **Clear a Step**: Tap a lit pad to clear that step.
- **Edit Step Details**: Hold a pad to view its step parameters on screen; use **K5–K8** to tweak **NOTE**, **LEVEL**, **RATCHET**, and **GATE**.
- **Tied / Legato Notes**: Hold the starting pad and tap a subsequent pad to create a tied note.
- **Live Pad Playing (REC on)**: When recording, striking pads plays notes live with velocity directly into the sequencer.
- **Pad LEDs**: Active steps illuminate in the track accent color (Cyan for Track A, White for Track B), the running playhead flashes brightly, and held steps glow red.

---

### The 4 Faders

Faders take over smoothly once moved (soft takeover), preventing sudden parameter jumps:

| Fader | Bank A (Performance) | Bank B (Effects & Master) |
| :---: | :--- | :--- |
| **1** | Filter Cutoff Frequency | Chorus Mix / Mode |
| **2** | Filter Resonance | Delay Mix Level |
| **3** | Filter Envelope Depth | Reverb Mix Level |
| **4** | Envelope Release Time | Master Volume Level |

---

### Hardware Panel Diagnostic

Hold **KNOB BANK** at any time to open the built-in diagnostic test display:
- Verifies JEDEC Flash ID and factory calibration status (`TRIM OK`).
- Displays live raw ADC values for all 4 faders, pitch/mod wheels, and battery voltage.
- Shows key velocity readings and individual pad baseline calibration offsets.

---

## Web Editor & Documentation

- **Web Editor**: Connect your SMK-37 via USB Chrome/Edge at [https://andrewgg.one/s1vave/editor/](https://andrewgg.one/s1vave/editor/)
- **Browser Simulator**: Test the engine online at [https://andrewgg.one/s1vave/sim/](https://andrewgg.one/s1vave/sim/)
- **Source Code**: [https://github.com/AndrewGG88/S1Vave](https://github.com/AndrewGG88/S1Vave)
