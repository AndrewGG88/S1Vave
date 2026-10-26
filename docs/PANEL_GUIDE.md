# S1Vave — Hardware Panel & Navigation Guide

This guide describes how to operate **S1Vave** directly on the **M-VAVE FM-1** hardware interface.

```
+-----------------------------------------------------------------------------------+
|  [ PRESETS ]            [ SELECT ]              [ ALGORITHM ]           [ VOL ]   |
|  Program Slot           BPM / Value             Track A / B Select      Master    |
|                                                                                   |
|  +--------------------+   +---------------------------------------------------+   |
|  |                    |   |  (K1) FREQ        (K2) RESO        (K3) ENV       |   |
|  |  ST7789 240x240    |   |                                                   |   |
|  |  Color LCD         |   |  (K4) PORTA       [HOME] [EDIT] [ENV] [LFO]       |   |
|  |                    |   |                                                   |   |
|  +--------------------+   |  [FX] [GLO] [ARP] [SEQ] [SAVE] [REC] [PLAY]       |   |
|                           +---------------------------------------------------+   |
|                                                                                   |
|  [OCT-]  [OCT+]    [ C# ] [ D# ]      [ F# ] [ G# ] [ A# ]      [ C# ] [ D# ]     |
|   Octave Down/Up   [ C  ] [ D  ] [ E  ] [ F  ] [ G  ] [ A  ] [ B  ] [ C  ] [ D  ] |
+-----------------------------------------------------------------------------------+
```

---

## 1. Top Knobs & Navigation Controls

| Control | Function | Description |
|:---|:---|:---|
| **PRESETS Knob** | Program / Pattern Select | Turn to browse programs **01–99** (1–64 factory S-1 programs, 65–99 user INIT). In the sequencer, selects patterns 1–8. |
| **SELECT Knob** | Tempo / Value Encoder | Adjusts BPM in 1 BPM increments. Push to confirm or trigger random sound generation when held with SAVE. |
| **ALGORITHM Button** | Track A / B Toggle | Switches between Sequencer Track A (blue) and Track B (orange). |
| **OCT- / OCT+** | Octave Shift | Shifts keyboard ±3 octaves. **Press both simultaneously** to reset octave back to 0. |
| **VOLUME Pot** | Hardware Master Level | Physical analog volume potentiometer. Read immediately upon power-on. |

---

## 2. Page Navigation & Knob Assignments

Tap any function button to open its parameter page. Repeated taps cycle through sub-pages.

### HOME Button (`PERFORM`)
Instant access to the 4 primary live performance parameters:
- **KNOB 1**: Filter Cutoff Frequency (`CUTOFF`) [CC 74]
- **KNOB 2**: Filter Resonance (`RESO`) [CC 71]
- **KNOB 3**: Filter Envelope Depth (`ENV AMT`) [CC 24]
- **KNOB 4**: Portamento Glide Time (`PORTA T`) [CC 5]

---

### EDIT Button (Oscillator & Filter Core)
Cycles through 6 pages:

#### Page 1: `OSC CORE` (SH-101 Waveforms)
- **K1**: Oscillator Range (`64'`, `32'`, `16'`, `8'`, `4'`, `2'`) [CC 14]
- **K2**: Square / Pulse Wave Level (`0–127`) [CC 19]
- **K3**: Sawtooth Wave Level (`0–127`) [CC 20]
- **K4**: Sub-Oscillator Level (`0–127`) [CC 21]

#### Page 2: `OSC PWM` (Pulse Width Modulation)
- **K1**: PWM Source (`ENV`, `MAN`, `LFO`) [CC 16]
- **K2**: Pulse Width / PWM Depth (`0–127`) [CC 15]
- **K3**: Square / Pulse Level (`0–127`) [CC 19]
- **K4**: Sub-Oscillator Type (`-2o.A`, `-2oc`, `-1oc`) [CC 22]

#### Page 3: `SUB / NOISE` (Sub-Oscillator & Noise Generator)
- **K1**: Sub-Oscillator Type (`-2o.A` 25% asymmetric, `-2oc` 50% square, `-1oc` 50% square) [CC 22]
- **K2**: Noise Level (`0–127`) [CC 23]
- **K3**: Noise Color Mode (`PINK` warm analog roll-off, `WHITE` flat spectrum) [CC 78]
- **K4**: Fine Tune (`-64 .. +63` semitones) [CC 76]

#### Page 4: `OSC DRAW` (Roland S-1 Wave Drawing)
- **K1**: Draw Switch (`OFF`, `STEP` 16 steps, `SLOPE` interpolated) [CC 107]
- **K2**: Frequency Multiplier (`1.0x .. 32.0x`) [CC 102]
- **K3**: PWM Source (`ENV`, `MAN`, `LFO`) [CC 16]
- **K4**: Pulse Width / Duty Cycle (`0–127`) [CC 15]

#### Page 5: `OSC CHOP` (Roland S-1 Harmonic Comb Slicing)
- **K1**: Chop Overtone (`0–200`, $>100$ phase inverted) [CC 103]
- **K2**: Comb Repetitions (`1.0 .. 32.0`) [CC 104]

#### Page 6: `FILTER` (4-Pole Cascaded SVF)
- **K1**: Filter Cutoff Frequency (`CUTOFF`) [CC 74]
- **K2**: Filter Resonance (`RESO`) [CC 71]
- **K3**: Filter LFO Modulation Depth (`FLT LFO`) [CC 25]
- **K4**: Keyboard Follow Tracking (`KEY TRK`, 0% to 100%) [CC 26]

---

### ENV Button (Envelopes & Triggers)
Cycles through 2 pages:

#### Page 1: `ENVELOPE` (Calibrated ADSR)
- **K1**: Attack Time ($0.5\text{ ms} \dots 10\text{ s}$) [CC 73]
- **K2**: Decay Time ($1\text{ ms} \dots 10\text{ s}$) [CC 75]
- **K3**: Sustain Level ($0\% \dots 100\%$) [CC 30]
- **K4**: Release Time ($1\text{ ms} \dots 10\text{ s}$) [CC 72]

#### Page 2: `ENV / PWM` (Envelope Trigger & Modulation Config)
- **K1**: Envelope Trigger Mode (`GATE`, `G+TRG` legato re-trig, `LFO` periodic) [CC 29]
- **K2**: Amp Envelope Mode (`GATE` organ gate, `ENV` shaped by ADSR) [CC 28]
- **K3**: PWM Source (`ENV`, `MAN`, `LFO`) [CC 16]
- **K4**: PWM Depth / Pulse Width (`0–127`) [CC 15]

---

### LFO Button (Modulation & Riser)
Cycles through 3 pages:

#### Page 1: `LFO` (Low Frequency Oscillator)
- **K1**: LFO Rate ($0.05 \dots 30\text{ Hz}$ or tempo note division) [CC 3]
- **K2**: Waveform (`SAW`, `IN.SAW`, `TRI`, `SQR`, `RND` S&H, `NOISE`) [CC 12]
- **K3**: Tempo Sync (`OFF`, `ON` across 31 musical note divisions) [CC 106]
- **K4**: LFO Speed Mode (`NORM` standard, `FAST` audio-rate up to $\sim 100\text{ Hz}$) [CC 79]

#### Page 2: `LFO MOD` (Routing & Triggering)
- **K1**: Pitch Modulation Vibrato Depth (`PITCH`) [CC 13]
- **K2**: Filter Cutoff Modulation Depth (`FLT LFO`) [CC 25]
- **K3**: Pulse Width Modulation Depth (`PW/DUTY`) [CC 15]
- **K4**: Key Trigger (`OFF` free-running, `ON` phase resets on key press) [CC 105]

#### Page 3: `RISER` (S-1 Performance Sweep Effect)
- **K1**: Riser Mode (`OFF`, `SYNC`, `QUIV`, `QV.PAN`) [CC 78]
- **K2**: Riser Resonance (`0–100`)
- **K3**: Riser Shape (`0–100`, saw to square)
- **K4**: Riser Level (`0–100`)

---

### FX Button (Effects Section)
Cycles through 3 pages:

#### Page 1: `FX MIX` (Quick Overview)
- **K1**: Chorus Mode (`OFF`, `TYPE 1`, `TYPE 2`, `TYPE 3`, `TYPE 4`) [CC 93]
- **K2**: Delay Wet Level (`0–127`) [CC 92]
- **K3**: Reverb Wet Level (`0–127`) [CC 91]
- **K4**: Delay Time (`0–127`) [CC 90]

#### Page 2: `DELAY` (Tempo-Synced Ping-Pong Delay)
- **K1**: Delay Wet Level (`0–127`) [CC 92]
- **K2**: Delay Time ($1 \dots 740\text{ ms}$ or 16 note lengths) [CC 90]
- **K3**: Delay Feedback (`0–127`)
- **K4**: Delay Tempo Sync (`OFF`, `ON`)

#### Page 3: `REV / CHO` (Dattorro Plate Reverb & Stereo Chorus)
- **K1**: Reverb Wet Level (`0–127`) [CC 91]
- **K2**: Reverb Time / Tank Size (`0–127`) [CC 89]
- **K3**: Reverb Type (`AMB`, `ROOM`, `HALL 1`, `HALL 2`, `PLATE`, `SPRING`, `MOD`)
- **K4**: Chorus Type (`OFF`, `TYPE 1`, `TYPE 2`, `TYPE 3`, `TYPE 4`) [CC 93]

---

### GLO Button (Global & Voicing)
Cycles through 2 pages:

#### Page 1: `VOICE` (Voicing Configuration)
- **K1**: Voicing Mode (`MONO`, `UNISON` 8-voice stacked, `POLY` 8-voice dynamic, `CHORD`) [CC 80]
- **K2**: Portamento Mode (`OFF`, `ON`, `AUTO` legato glide) [CC 31]
- **K3**: Key Transpose ($-60 \dots +60$ semitones) [CC 77]
- **K4**: Master Volume (`0–127`) [CC 7]

#### Page 2: `GLOBAL` (System & MIDI)
- **K1**: Master Tempo (BPM)
- **K2**: Metronome Click Mode (`OFF`, `REC`, `ON`, `COUNT-IN`)
- **K3**: MIDI Channel (`1–16` or `OMNI`)
- **K4**: Master Probability ($-100\% \dots +100\%$)

---

## 3. Sequencer & Layer Hold Combinations

The M-VAVE FM-1 keys support **layer combinations** when holding a function button:

| Hold Button | Action |
|:---|:---|
| **Hold SEQ** | Keys 1–16 toggle step triggers. Black keys F#3..A#4 select sequencer pages 1–8. Knobs adjust Step Note, Div, Swing, and Length. |
| **Hold EDIT** | Key presses erase notes. Knobs adjust Shift, Length x2/half, Transpose. |
| **Hold GLO** | Key 1/2 mutes Track A/B. Key 5/6 solos Track A/B. Key G5 taps tempo. |
| **Hold SAVE** | Keys 1–8 select pattern slots. Black keys 1–8 copy pattern. Press SELECT knob while held for a random preset. |
| **Hold FX** | Quick-adjusts wet levels for Chorus, Delay, and Reverb directly from knobs. |
| **Tap SAVE twice** | Saves the current sound into the active program slot in flash memory. |
