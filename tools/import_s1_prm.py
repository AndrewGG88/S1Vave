#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""
Roland AIRA Compact S-1 .PRM Preset & Pattern Importer for S-Vave.
Parses original Roland S-1 backup files (.PRM) and converts them into:
1. firmware/src/obv_patches.h (authentic factory sound presets)
2. Sequencer patterns with custom 16-step draw tables and chop masks.
"""

import sys
import os
import glob
import re

# Mapping from PRM keys to S-Vave parameter enum names
PRM_TO_PARAM = {
    "VCO_RANGE": "P_RANGE",
    "VCO_PWM_LEVEL": "P_PULSE_LVL",
    "VCO_SAW_LEVEL": "P_SAW_LVL",
    "VCO_SUB_LEVEL": "P_SUB_LVL",
    "VCO_SUB_TYPE": "P_SUB_TYPE",
    "VCO_NOISE_LEVEL": "P_NOISE_LVL",
    "NOISE_MODE": "P_NOISE_MODE",
    "FINE_TUNE": "P_FINE_TUNE",
    "VCO_PWM_SOURCE": "P_PWM_SRC",
    "VCO_PULSE_WIDTH": "P_PWM_DEPTH",
    "OSC_DRAW_SW": "P_DRAW_SW",
    "OSC_DRAW_MULT": "P_DRAW_MULT",
    "OSC_CHOP_OVERTONE": "P_CHOP_OVTN",
    "OSC_CHOP_COMB": "P_CHOP_COMB",
    "VCF_CUTOFF": "P_CUTOFF",
    "VCF_RESONANCE": "P_RESO",
    "VCF_ENV_DEPTH": "P_FENV_AMT",
    "VCF_MOD_DEPTH": "P_FLFO_AMT",
    "VCF_KEY_FOLLOW": "P_KEYTRK",
    "VCF_BEND_SENS": "P_FLT_BEND",
    "ENV_ATTACK": "P_ATTACK",
    "ENV_DECAY": "P_DECAY",
    "ENV_SUSTAIN": "P_SUSTAIN",
    "ENV_RELEASE": "P_RELEASE",
    "VCA_ENV_MODE": "P_AMP_MODE",
    "ENV_TRG_MODE": "P_ENV_TRG",
    "LFO_RATE": "P_LFO_RATE",
    "LFO_WAVE_FORM": "P_LFO_WAVE",
    "LFO_SYNC": "P_LFO_SYNC",
    "LFO_KEY_TRIG": "P_LFO_TRIG",
    "LFO_MODE": "P_LFO_MODE",
    "VCO_MOD_DEPTH": "P_LFO_PITCH",
    "LFO_MOD_DEPTH": "P_MOD_DEPTH",
    "VCO_BEND_SENS": "P_OSC_BEND",
    "RISER_MODE": "P_RISER_MODE",
    "RISER_RESO": "P_RISER_RESO",
    "RISER_SHAPE": "P_RISER_SHAPE",
    "RISER_LEVEL": "P_RISER_LVL",
    "DELAY_LEVEL": "P_DLY_LVL",
    "DELAY_TIME": "P_DLY_TIME",
    "DELAY_FEEDBACK": "P_DLY_FB",
    "DELAY_SW": "P_DLY_SYNC",
    "REVERB_LEVEL": "P_REV_LVL",
    "REVERB_TIME": "P_REV_TIME",
    "REVERB_TYPE": "P_REV_TYPE",
    "REVERB_PRE_DELAY": "P_REV_PRE",
    "CHORUS": "P_CHO_MODE",
    "ASSIGN_MODE": "P_POLY_MODE",
    "PORTAMENTO_MODE": "P_PORTA_MODE",
    "PORTAMENTO_TIME": "P_PORTA_TIME",
    "PORTAMENTO": "P_PORTA_SW",
    "TRANSPOSE": "P_TRANSPOSE",
    "LEVEL": "P_VOLUME",
    "CHORD_VOICE2_SW": "P_CHORD_SW2",
    "CHORD_VOICE3_SW": "P_CHORD_SW3",
    "CHORD_VOICE4_SW": "P_CHORD_SW4",
    "CHORD_VOICE2_KEY_SHIFT": "P_CHORD_KS2",
    "CHORD_VOICE3_KEY_SHIFT": "P_CHORD_KS3",
    "CHORD_VOICE4_KEY_SHIFT": "P_CHORD_KS4",
}

# Default values for S-Vave parameters (matching PDEF in obv_params.h)
DEFAULTS = {
    "P_RANGE": 3,
    "P_PULSE_LVL": 100,
    "P_SAW_LVL": 110,
    "P_SUB_LVL": 80,
    "P_SUB_TYPE": 2,
    "P_NOISE_LVL": 0,
    "P_NOISE_MODE": 0, # Pink
    "P_FINE_TUNE": 64,
    "P_PWM_SRC": 1,    # Manual
    "P_PWM_DEPTH": 64,
    "P_DRAW_SW": 0,
    "P_DRAW_MULT": 0,
    "P_CHOP_OVTN": 0,
    "P_CHOP_COMB": 0,
    "P_CUTOFF": 85,
    "P_RESO": 25,
    "P_FENV_AMT": 85,
    "P_FLFO_AMT": 0,
    "P_KEYTRK": 64,
    "P_FLT_BEND": 2,
    "P_ATTACK": 5,
    "P_DECAY": 65,
    "P_SUSTAIN": 80,
    "P_RELEASE": 45,
    "P_AMP_MODE": 1,
    "P_ENV_TRG": 2,    # Gate+Trig (triG)
    "P_LFO_RATE": 60,
    "P_LFO_WAVE": 2,
    "P_LFO_SYNC": 0,
    "P_LFO_TRIG": 0,
    "P_LFO_MODE": 0,
    "P_LFO_PITCH": 0,
    "P_MOD_DEPTH": 0,
    "P_OSC_BEND": 2,
    "P_RISER_MODE": 0,
    "P_RISER_RESO": 30,
    "P_RISER_SHAPE": 0,
    "P_RISER_LVL": 80,
    "P_DLY_LVL": 0,
    "P_DLY_TIME": 50,
    "P_DLY_FB": 50,
    "P_DLY_SYNC": 1,
    "P_REV_LVL": 0,
    "P_REV_TIME": 75,
    "P_REV_TYPE": 2,
    "P_REV_PRE": 20,
    "P_CHO_MODE": 0,
    "P_POLY_MODE": 2,
    "P_PORTA_MODE": 0,
    "P_PORTA_TIME": 30,
    "P_PORTA_SW": 0,
    "P_TRANSPOSE": 60,
    "P_VOLUME": 100,
    "P_CHORD_SW2": 1,
    "P_CHORD_SW3": 1,
    "P_CHORD_SW4": 1,
    "P_CHORD_KS2": 12,
    "P_CHORD_KS3": 12,
    "P_CHORD_KS4": 12,
}

def scale_value(p_name, raw_str):
    v = int(raw_str)
    if p_name in ["P_OSC_BEND", "P_FLT_BEND"]:
        # Roland PRM: 10 units = 1 semitone (20 -> 2 semi, 240 -> 24 semi)
        return max(0, min(24, round(v / 10)))
    # Linear 0..255 -> 0..127
    elif p_name in [
        "P_PULSE_LVL", "P_SAW_LVL", "P_SUB_LVL", "P_NOISE_LVL",
        "P_FINE_TUNE", "P_PWM_DEPTH", "P_CUTOFF", "P_RESO",
        "P_FENV_AMT", "P_FLFO_AMT", "P_KEYTRK",
        "P_ATTACK", "P_DECAY", "P_SUSTAIN", "P_RELEASE",
        "P_LFO_RATE", "P_LFO_PITCH", "P_MOD_DEPTH",
        "P_DLY_LVL", "P_DLY_TIME", "P_DLY_FB", "P_REV_LVL", "P_REV_TIME"
    ]:
        return round(v * 127 / 255)
    elif p_name in ["P_DRAW_MULT", "P_CHOP_COMB"]:
        # Anchored: PRM 7..255 -> 0..31
        norm = max(0.0, min(1.0, (v - 7) / (255.0 - 7.0)))
        return round(norm * 31)
    elif p_name == "P_CHOP_OVTN":
        # PRM 0..255 -> 0..200
        return min(200, v)
    elif p_name in ["P_CHORD_KS2", "P_CHORD_KS3", "P_CHORD_KS4"]:
        # PRM signed semitones (-12..+12) -> firmware 0..24 centered at 12
        return max(0, min(24, v + 12))
    elif p_name in ["P_CHORD_SW2", "P_CHORD_SW3", "P_CHORD_SW4", "P_LFO_SYNC", "P_LFO_TRIG", "P_LFO_MODE", "P_DLY_SYNC", "P_PORTA_SW"]:
        return 1 if v > 0 else 0
    elif p_name == "P_TRANSPOSE":
        return max(0, min(120, v + 60))
    elif p_name == "P_VOLUME":
        return min(127, v)
    return v

def parse_prm_file(path):
    prms = {}
    step_notes = {}
    step_motions = {}
    draw_points = [0] * 8
    chop_masks = [0xFFFF] * 4

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(";") or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip().upper()
            v = v.strip()

            if k.startswith("STEP_NOTE "):
                try:
                    step_num = int(k[10:])
                    step_notes[step_num] = v
                except ValueError:
                    pass
            elif k.startswith("STEP_MOTION "):
                try:
                    encoded = int(k[12:])
                    tens = encoded // 10
                    ones = encoded % 10
                    if 1 <= tens <= 8 and 1 <= ones <= 8:
                        step_motions[(tens - 1) * 8 + (ones - 1)] = v
                except ValueError:
                    pass
            elif k.startswith("OSC_DRAW_P") and len(k) == 11:
                try:
                    p_idx = int(k[10]) - 1
                    raw_val = int(v)
                    # Signed 16-bit (-32768..+32767 centered at 32768)
                    signed_val = max(-32767, min(32767, raw_val - 32768))
                    draw_points[p_idx] = signed_val
                except ValueError:
                    pass
            elif k == "OSC_CHOP_PWM":
                chop_masks[0] = int(v) & 0xFFFF
            elif k == "OSC_CHOP_SAW":
                chop_masks[1] = int(v) & 0xFFFF
            elif k == "OSC_CHOP_SUB":
                chop_masks[2] = int(v) & 0xFFFF
            elif k == "OSC_CHOP_NOISE":
                chop_masks[3] = int(v) & 0xFFFF
            else:
                prms[k] = v

    # Expand 8 draw points to 16-step wavetable with linear interpolation
    draw_table_16 = [0] * 16
    for i in range(16):
        p0 = draw_points[i // 2]
        p1 = draw_points[(i // 2 + 1) % 8]
        if i % 2 == 0:
            draw_table_16[i] = p0
        else:
            draw_table_16[i] = (p0 + p1) // 2

    return {
        "prms": prms,
        "step_notes": step_notes,
        "step_motions": step_motions,
        "draw_table": draw_table_16,
        "chop_masks": chop_masks,
    }

def clean_patch_name(filename):
    base = os.path.splitext(os.path.basename(filename))[0]
    m = re.search(r'PTN(\d)[-_](\d+)', base, re.IGNORECASE)
    if m:
        return f"PTN {m.group(1)}-{int(m.group(2)):02d}"
    base = re.sub(r'^(S1_|PTN_?|S-1_?)', '', base, flags=re.IGNORECASE)
    base = re.sub(r'[_\-\.]+', ' ', base).strip().upper()
    if not base:
        base = "S-1 SOUND"
    return base[:9]

def generate_c_patches(prm_files, output_h):
    patches = []
    names = []
    waves = []

    for idx, fpath in enumerate(prm_files[:64]):
        parsed = parse_prm_file(fpath)
        name = clean_patch_name(fpath)
        names.append(name)
        waves.append((parsed["draw_table"], parsed["chop_masks"]))

        deltas = []
        for prm_key, p_name in PRM_TO_PARAM.items():
            if prm_key in parsed["prms"]:
                raw_val = parsed["prms"][prm_key]
                if p_name == "P_LFO_RATE" and parsed["prms"].get("LFO_SYNC", "0") != "0":
                    val = max(0, min(30, int(raw_val) - 1))
                else:
                    val = scale_value(p_name, raw_val)
                def_val = DEFAULTS.get(p_name, 0)
                if val != def_val:
                    deltas.append(f"{p_name}, {val}")

        patches.append(deltas)

    # Pad to 64 if fewer
    while len(patches) < 64:
        idx = len(patches) + 1
        patches.append([])
        names.append(f"INIT {idx}")
        default_draw = [int((i - 7) * 4096) for i in range(16)]
        default_chop = [0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF]
        waves.append((default_draw, default_chop))

    lines = []
    lines.append("/* SPDX-License-Identifier: GPL-3.0-only */")
    lines.append("/* Authentic Roland AIRA Compact S-1 Factory Presets for S-Vave */")
    lines.append("#ifndef OBV_PATCHES_H")
    lines.append("#define OBV_PATCHES_H\n")
    lines.append("#define X 255u\n")

    for i, p in enumerate(patches):
        num_str = f"{i + 1:02d}"
        body = ", ".join(p) + (", " if p else "") + "X"
        lines.append(f"static const uint8_t PF_{num_str}[] = {{{body}}};")

    lines.append("\nstatic const uint8_t PF_INIT[] = {X};")
    lines.append("#undef X\n")

    lines.append("static const factory_t FACT_INIT = {\"INIT\", PF_INIT};")
    lines.append("static const factory_t FACTORY[NFACT] = {")
    for i in range(64):
        num_str = f"{i + 1:02d}"
        lines.append(f'    {{"{names[i]}", PF_{num_str}}},')
    lines.append("};\n")

    lines.append("typedef struct {")
    lines.append("    int16_t draw[16];")
    lines.append("    uint16_t chop[4];")
    lines.append("} fact_wave_t;\n")

    lines.append("static const fact_wave_t FACT_WAVE[NFACT] = {")
    for i in range(64):
        draw_arr, chop_arr = waves[i]
        d_str = ", ".join(f"{v}" for v in draw_arr)
        c_str = ", ".join(f"{v}u" for v in chop_arr)
        lines.append(f"    /* {i+1:02d}: {names[i]} */")
        lines.append(f"    {{ {{{d_str}}}, {{{c_str}}} }},")
    lines.append("};\n")
    lines.append("#endif /* OBV_PATCHES_H */\n")

    with open(output_h, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Generated {output_h} with {len(patches)} authentic S-1 sound patches.")

def main():
    backup_dir = None
    if len(sys.argv) > 1:
        backup_dir = sys.argv[1]
    else:
        candidates = [
            "/run/media/andrewgg/S-1/BACKUP",
            "/media/andrewgg/S-1/BACKUP",
            "s1_backup",
            "obervave-main/s1_backup",
            "../s1_backup"
        ]
        for c in candidates:
            if os.path.isdir(c):
                backup_dir = c
                break

    if not backup_dir or not os.path.exists(backup_dir):
        print("Usage: import_s1_prm.py [BACKUP_DIR or *.PRM files]")
        print("Waiting for S-1 USB Mass Storage or specify PRM directory.")
        return 1

    if os.path.isfile(backup_dir):
        files = [backup_dir]
    else:
        files = sorted(glob.glob(os.path.join(backup_dir, "**/*.PRM"), recursive=True))
        if not files:
            files = sorted(glob.glob(os.path.join(backup_dir, "**/*.prm"), recursive=True))

    print(f"Found {len(files)} PRM files in {backup_dir}")
    if not files:
        return 1

    out_h = "firmware/src/obv_patches.h" if os.path.exists("firmware/src") else "obervave-main/firmware/src/obv_patches.h"
    generate_c_patches(files, out_h)
    return 0

if __name__ == '__main__':
    sys.exit(main())
