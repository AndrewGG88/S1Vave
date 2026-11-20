# SH-101 filter (optional): `OBV_FILTER_SH101`

An optional second filter beside the S-1 SVF cascade: a model of the Roland SH-101's VCF (IR3109) and its resonance circuit, in single-precision float on the AC791N's FPU. **It's off by default: the normal build is unchanged** (the host render is bit-identical to v2.0.1).

```sh
OBV_DEFS=-DOBV_FILTER_SH101=1 ./build.sh
```

That build has both filters. Choose one on the screen: **SEL**, page 1 (STEREO/VCF), **knob 4 VCF: S-1 / SH-101**, or CC 49 (0–63 S-1, 64–127 SH-101). The choice is a global setting, kept with the settings over a power-off (bit 6 of the stored click byte: no new settings version, and a default build ignores it). It is not stored in patches, so patches, SysEx and the editor are unchanged. With VCF on S-1 the SH-101 build sounds exactly as the default build (bit-identical on the host).

| What | Where |
|:---|:---|
| The filter | `firmware/src/sh101_vcf.h`: one header, no libm, no division per sample. Maintained at [github.com/bk40-home/sh101-vcf](https://github.com/bk40-home/sh101-vcf), with its reference model, calibration and test kit. The same file is M-Vsynth2's FILTER TYPE 5 |
| The hook | `firmware/src/obv_engine.h`, all behind `OBV_FILTER_SH101`: `ctl_vcf` (the UI's choice), taken by the audio at the top of a buffer (`vcf_take`: both filters restart from rest). `s1vave.c`: the VCF knob, CC 49, the setting, the cutoff display. `obv_params.h`: the page title |
| FPU | `tools/build.py` adds `-mcpu=r3 -mfprev1 -ffp-contract=off -Werror=double-promotion` (the SDK's flags, as fm-106 and Melodee) **only when OBV_FILTER_SH101=1**, so the default firmware is built exactly as before. `firmware/hal/fm1_irq.h` masks the FPU's IEEE-flag traps (`EMU_CON` bits 16–20), as the SDK, fm-106 and Melodee. In M-Vsynth2, the FPU flags on the whole unity build (USB code included) coincided with the FM-1 dropping off USB now and then; there they are now on the DSP file only. S1Vave builds as one file, so an SH-101 build still has them throughout: if you see USB-MIDI drop out, that is the first suspect |

## What is modelled

From the SH-101 service manual (VCF board and panel):

| Part | Circuit | Model |
|:---|:---|:---|
| Four poles | IR3109 OTA stages, C47/48/50/51 240p | TPT stages, each with the tanh of its own input. Stage 1 sits 2.9% lower (R113 loads it) |
| Resonance | VR18 → TR26/TR27 → R129 → D30/D31 → R113 → stage 1 | Loop gain from RESO; the diode pair sets the oscillation level |
| Output | R130 (filter output) + R132 (the RES wiper) into the BA662 | `y4 (1 + 0.202 k)`: the 101's own level compensation, so the bass holds up as resonance rises |

The levels the schematic leaves open are fitted to TAL-BassLine-101. On an FM-1 (in M-Vsynth2), against TAL:
- the same corner and slope (124 Hz, −20.6 dB/oct);
- self-oscillation in tune within about ±60 cents from 20 Hz to 3.6 kHz;
- 0.6% THD;
- tracking 1 octave per octave.

## In S1Vave

| | |
|:---|:---|
| Cutoff | `cut` is where the filter sings, the same meaning as the SVF's: envelope, key follow, LFO and bend move it as before. The CUTOFF knob uses the SH-101's FREQ slider (exponential, 7 Hz to 11.55 kHz) instead of the S-1 taper. The screen shows the same Hz |
| Resonance | RESO 0..127 = the SH-101 slider 0..10, curved by `SH101_RES_TAPER` 2.0: it self-oscillates from about RESO 108 |
| Singing level | `SH101_SING_TRIM` 0.7: −3 dB at full RESO once it sings. The circuit sings +5.6 dB over a full oscillator, so chords would clip |
| Start of oscillation | The circuit's own noise (1e-4 rms) instead of the note-on kick into `f2` |
| Headroom | Singing peaks reach ~1.5 × a full oscillator, so in this build the voice's amp product is 64-bit and the filter output is bounded to ±120000 |
| CPU (FM-1, init patch, 8 voices) | 5000 µs per half buffer with VCF SH-101, against 3100 for the SVF (budget 5800) |
| Switching | Takes effect at the next buffer. A note sounding at the switch restarts its filter (a small click); CUTOFF moves to the new filter's taper within a few ms |

Settings are build defines, e.g. `OBV_DEFS="-DOBV_FILTER_SH101=1 -DSH101_SING_TRIM=0.85f" ./build.sh`:

| Setting | Default | |
|:---|:---|:---|
| `SH101_SING_TRIM` | `0.7f` | Level when self-oscillating (`1.0f` = the circuit, for mono lines) |
| `SH101_RES_TAPER` | `2.0f` | RESO's curve (`1.0f` = the 101's linear slider: sings from RESO 92) |
| `SH101_RES_MAX` | `10.0f` | RESO at 127, on the 101's 0..10 (below `7.2f` it never self-oscillates) |
| `SH101_CUT_MIN_HZ` / `SH101_CUT_MAX_HZ` | `7.0f` / `11550.0f` | CUTOFF's range |

## Tests

- **Host:** both builds compile cleanly. The default build's render is bit-identical to v2.0.1 (`tests/host.c`), and so is the SH-101 build's with VCF on S-1. `tests/sh101_ab.txt` plays resonance steps, a singing cutoff sweep and a chord; it starts with CC 49 127, so the SH-101 build renders it on the SH-101 filter (a default build ignores the CC). `tests/sh101_switch.txt` switches the VCF three times under a held chord: no level jump or blow-up, the S-1 part identical to the default build.
- **The module itself:** checked against a double-precision, 8× oversampled reference of the same circuit, in the sh101-vcf repo:
  - response within 0.25 dB;
  - pitch within 4.2 cents;
  - level within 0.04 dB;
  - aliasing −62 dB at 1×.
- **FM-1:** flashed and played in this fork (CPU above); in M-Vsynth2, the full A/B against TAL-BassLine-101.
