# S1Vave — Roland S-1 MIDI Implementation Chart

This document lists the complete MIDI Control Change (CC) mapping for **S1Vave** running on the M-VAVE FM-1. The mapping follows the official **Roland AIRA Compact S-1 Tweak Synth** MIDI specification 1:1.

---

## 1. Controller & Performance

| CC # | Parameter | Range | Values / Description |
|:---:|:---|:---:|:---|
| **1** | Modulation Wheel | `0–127` | LFO pitch & filter modulation depth |
| **5** | Portamento Time | `0–127` | Glide speed between notes (0 = fastest, 127 = slowest) |
| **7** | Master Volume | `0–127` | Master output level (audio taper) |
| **18** | Pitch Bend Sensitivity | `0–24` | Pitch bend wheel range in semitones |
| **31** | Portamento Mode | `0–2` | `0 = OFF`, `1 = ON`, `2 = AUTO` (legato glide) |
| **64** | Sustain / Damper Pedal | `0–127` | $\ge 64$ holds notes |
| **65** | Portamento Switch | `0–127` | $\ge 64$ enables portamento |
| **76** | Fine Tune | `0–127` | Master pitch fine tune ($-64 \dots +63$, center = 64) |
| **77** | Key Transpose | `0–120` | Transpose ($-60 \dots +60$ semitones, center = 60) |
| **80** | Polyphony Mode | `0–3` | `0 = MONO`, `1 = UNISON` (8-voice stacked), `2 = POLY` (8-voice dynamic), `3 = CHORD` |
| **120** | All Sound Off | `0` | Immediately mutes all voices |
| **123** | All Notes Off | `0` | Releases all held notes |

---

## 2. Oscillator Section (SH-101 Core, DRAW & CHOP)

| CC # | Parameter | Range | Values / Description |
|:---:|:---|:---:|:---|
| **14** | Range (Octave) | `0–5` | `0 = 64'`, `1 = 32'`, `2 = 16'`, `3 = 8'`, `4 = 4'`, `5 = 2'` |
| **15** | Pulse Width / PWM Depth | `0–127` | In Manual mode: 50% square down to ~5% needle pulse. In LFO/ENV mode: modulation swing depth |
| **16** | PWM Modulation Source | `0–2` | `0 = ENV`, `1 = MANUAL` (`NAn`), `2 = LFO` |
| **19** | Square / Pulse Level | `0–127` | Level of the pulse / square / draw oscillator in the mix |
| **20** | Sawtooth Level | `0–127` | Level of the classic sawtooth oscillator |
| **21** | Sub-Oscillator Level | `0–127` | Level of the sub-oscillator |
| **22** | Sub-Oscillator Type | `0–2` | `0 = -2o.A` (2-octave lower 25% asymmetric pulse)<br>`1 = -2oc` (2-octave lower 50% square)<br>`2 = -1oc` (1-octave lower 50% square) |
| **23** | Noise Level | `0–127` | Level of the noise generator |
| **78** | Noise Mode | `0–1` | `0 = PINK` (analog warm 12 dB roll-off), `1 = WHITE` |
| **102** | OSC DRAW Multiply | `0–31` | Wavetable frequency multiplier ($1.0\text{x} \dots 32.0\text{x}$) |
| **103** | OSC CHOP Overtone | `0–200` | $0 = \text{dry}$, $100 = \text{fundamental mute}$, $>100 = \text{reverse phase}$ |
| **104** | OSC CHOP Comb | `0–31` | Comb slicing repetition frequency ($1.0\text{x} \dots 32.0\text{x}$) |
| **107** | OSC DRAW Switch | `0–2` | `0 = OFF`, `1 = STEP` (16 discrete steps), `2 = SLOPE` (interpolated) |

---

## 3. Filter Section (4-Pole Cascaded SVF)

| CC # | Parameter | Range | Values / Description |
|:---:|:---|:---:|:---|
| **74** | Filter Cutoff (FREQ) | `0–127` | 24 dB/oct lowpass cutoff frequency ($20\text{ Hz} \dots 20\text{ kHz}$) |
| **71** | Filter Resonance (RESO) | `0–127` | Resonance amount with bounded analog self-oscillation |
| **24** | Filter Env Depth (ENV) | `0–127` | Bipolar/unipolar envelope sweep depth on cutoff |
| **25** | Filter LFO Depth | `0–127` | LFO modulation intensity on filter cutoff |
| **26** | Keyboard Follow (KEY TRK)| `0–127` | Cutoff tracking relative to note pitch ($0\% \dots 100\%$) |
| **27** | Filter Bend Sensitivity | `0–24` | Pitch bend wheel modulation on cutoff in semitones |
| **108** | Filter Character Model | `0–1` | `0 = S-1 Clean` (Roland ACB), `1 = Warm Midnight` (soft-knee drive) |
| **109** | Overall Tone Tilt | `0–127` | Tone tilt equalizer ($-64 \dots +63$, center = 64) |
| **110** | Analog Warmth | `0–127` | Resonance bass retention and saturation ($0\% \dots 100\%$) |

---

## 4. Envelope Section (ADSR)

| CC # | Parameter | Range | Values / Description |
|:---:|:---|:---:|:---|
| **73** | Attack Time | `0–127` | Envelope attack time ($0.5\text{ ms} \dots 10\text{ s}$) |
| **75** | Decay Time | `0–127` | Envelope decay time ($1\text{ ms} \dots 10\text{ s}$) |
| **30** | Sustain Level | `0–127` | Envelope sustain level ($0\% \dots 100\%$) |
| **72** | Release Time | `0–127` | Envelope release time ($1\text{ ms} \dots 10\text{ s}$) |
| **28** | Amp Envelope Switch | `0–1` | `0 = GATE` (instant organ gate), `1 = ENV` (shaped by ADSR) |
| **29** | Envelope Trigger Mode | `0–2` | `0 = LFO` (LFO re-triggers envelope)<br>`1 = GATE` (note on)<br>`2 = GATE+TRIG` (legato re-triggers) |

---

## 5. LFO & Riser Section

| CC # | Parameter | Range | Values / Description |
|:---:|:---|:---:|:---|
| **3** | LFO Rate | `0–127` | LFO speed in Hz ($0.05 \dots 30\text{ Hz}$) or tempo note divisions |
| **12** | LFO Waveform | `0–5` | `0 = SAW`, `1 = INV SAW`, `2 = TRIANGLE`, `3 = SQUARE`, `4 = RANDOM (S&H)`, `5 = NOISE` |
| **13** | OSC Pitch LFO Depth | `0–127` | Vibrato depth on oscillator pitch |
| **17** | LFO Mod Depth | `0–127` | General modulation depth |
| **79** | LFO Mode | `0–1` | `0 = NORMAL` ($0.05 \dots 30\text{ Hz}$), `1 = FAST` (audio-rate up to $\sim 100\text{ Hz}$) |
| **105** | LFO Key Trigger | `0–1` | `0 = OFF` (free-running phase), `1 = ON` (phase resets on Note On) |
| **106** | LFO Tempo Sync | `0–1` | `0 = OFF`, `1 = ON` (synced to 31 musical note divisions) |
| **78** | Riser Mode (when active) | `0–3` | `0 = OFF`, `1 = SYNC`, `2 = QUIV`, `3 = QV.PAN` |

---

## 6. Effects Section (Delay, Reverb, Chorus)

| CC # | Parameter | Range | Values / Description |
|:---:|:---|:---:|:---|
| **89** | Reverb Time | `0–127` | Reverb decay length (Dattorro figure-of-8 tank) |
| **90** | Delay Time | `0–127` | Delay time ($1 \dots 740\text{ ms}$ or 16 synced note divisions) |
| **91** | Reverb Level | `0–127` | Reverb wet/dry mix |
| **92** | Delay Level | `0–127` | Delay wet/dry mix |
| **93** | Chorus Mode | `0–4` | `0 = OFF`, `1 = TYPE 1`, `2 = TYPE 2`, `3 = TYPE 3`, `4 = TYPE 4` |

---

## 7. Chord Memory

| CC # | Parameter | Range | Values / Description |
|:---:|:---|:---:|:---|
| **81** | Chord Voice 2 Switch | `0–1` | `0 = OFF`, `1 = ON` |
| **82** | Chord Voice 3 Switch | `0–1` | `0 = OFF`, `1 = ON` |
| **83** | Chord Voice 4 Switch | `0–1` | `0 = OFF`, `1 = ON` |
| **85** | Chord Voice 2 Key Shift | `0–24` | Pitch offset in semitones ($-12 \dots +12$, center = 12) |
| **86** | Chord Voice 3 Key Shift | `0–24` | Pitch offset in semitones ($-12 \dots +12$, center = 12) |
| **87** | Chord Voice 4 Key Shift | `0–24` | Pitch offset in semitones ($-12 \dots +12$, center = 12) |
