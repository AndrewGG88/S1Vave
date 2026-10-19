#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""
S-Vave / Roland S-1 Parameter Drift Reader & Tuner.
Reads live parameter values from the M-VAVE FM-1 over USB-MIDI,
compares them against authentic Roland S-1 factory .PRM files,
and calculates the exact drift / delta for calibration.
"""

import sys
import os
import time
import argparse
import glob

try:
    import mido
except ImportError:
    print("Error: mido is required. Install with: pip install mido python-rtmidi")
    sys.exit(1)

# Import the PRM parser from import_s1_prm
sys.path.append(os.path.join(os.path.dirname(__file__)))
try:
    import import_s1_prm
except ImportError:
    import_s1_prm = None

# Parameter definitions: index, name, CC, max, description
PARAMS = [
    # 0..10: OSC CORE & SUB/NOISE
    (0,  "P_RANGE",      14,  5,   "VCO Range (64',32',16',8',4',2')"),
    (1,  "P_PULSE_LVL",  19,  127, "Square/Pulse Level"),
    (2,  "P_SAW_LVL",    20,  127, "Sawtooth Level"),
    (3,  "P_SUB_LVL",    21,  127, "Sub Oscillator Level"),
    (4,  "P_SUB_TYPE",   22,  2,   "Sub Osc Type (-2o.A, -2oc, -1oc)"),
    (5,  "P_NOISE_LVL",  23,  127, "Noise Level"),
    (6,  "P_NOISE_MODE", 78,  1,   "Noise Mode (Pink, White)"),
    (7,  "P_FINE_TUNE",  76,  127, "Fine Tune (center 64)"),
    (8,  "P_PWM_SRC",    16,  2,   "PWM Source (Env, Man, LFO)"),
    (9,  "P_PWM_DEPTH",  15,  127, "PWM Depth / Pulse Width"),
    (10, "P_DRAW_SW",    107, 2,   "OSC Draw Switch (Off, Step, Slope)"),
    (11, "P_DRAW_MULT",  102, 31,  "OSC Draw Multiply (1x..32x)"),
    (12, "P_CHOP_OVTN",  103, 200, "OSC Chop Overtone (0..200)"),
    (13, "P_CHOP_COMB",  104, 31,  "OSC Chop Comb (1x..32x)"),

    # 14..18: FILTER
    (14, "P_CUTOFF",     74,  127, "VCF Cutoff Frequency"),
    (15, "P_RESO",       71,  127, "VCF Resonance"),
    (16, "P_FENV_AMT",   24,  127, "VCF Env Depth (center 64)"),
    (17, "P_FLFO_AMT",   25,  127, "VCF LFO Mod Depth"),
    (18, "P_KEYTRK",     26,  127, "VCF Keyboard Tracking"),
    (19, "P_FLT_BEND",   27,  24,  "VCF Pitch Bend Sens"),

    # 20..25: ENVELOPES
    (20, "P_ATTACK",     73,  127, "Env Attack Time"),
    (21, "P_DECAY",      75,  127, "Env Decay Time"),
    (22, "P_SUSTAIN",    30,  127, "Env Sustain Level"),
    (23, "P_RELEASE",    72,  127, "Env Release Time"),
    (24, "P_AMP_MODE",   28,  1,   "Amp Mode (Gate, Env)"),
    (25, "P_ENV_TRG",    29,  2,   "Env Trigger (LFO, Gate, Gate+Trig)"),

    # 26..33: LFO
    (26, "P_LFO_RATE",   3,   127, "LFO Rate"),
    (27, "P_LFO_WAVE",   12,  5,   "LFO Waveform"),
    (28, "P_LFO_SYNC",   106, 1,   "LFO Sync (Off, On)"),
    (29, "P_LFO_TRIG",   105, 1,   "LFO Key Trigger (Off, On)"),
    (30, "P_LFO_MODE",   79,  1,   "LFO Mode (Norm, Fast)"),
    (31, "P_LFO_PITCH",  13,  127, "VCO Pitch LFO Depth"),
    (32, "P_MOD_DEPTH",  1,   127, "LFO Mod Wheel Depth"),
    (33, "P_OSC_BEND",   18,  24,  "OSC Pitch Bend Sens"),

    # 34..37: RISER
    (34, "P_RISER_MODE", 32,  3,   "Riser Mode (Off, Sync, Quiv, QvPn)"),
    (35, "P_RISER_RESO", 33,  100, "Riser Resonance"),
    (36, "P_RISER_SHAPE",34,  100, "Riser Shape"),
    (37, "P_RISER_LVL",  35,  100, "Riser Level"),

    # 38..41: DELAY
    (38, "P_DLY_LVL",    92,  127, "Delay Level"),
    (39, "P_DLY_TIME",   90,  127, "Delay Time"),
    (40, "P_DLY_FB",     36,  127, "Delay Feedback"),
    (41, "P_DLY_SYNC",   37,  1,   "Delay Sync (Off, On)"),

    # 42..46: REVERB & CHORUS
    (42, "P_REV_LVL",    91,  127, "Reverb Level"),
    (43, "P_REV_TIME",   89,  127, "Reverb Time"),
    (44, "P_REV_TYPE",   38,  6,   "Reverb Type (Amb..Mod)"),
    (45, "P_REV_PRE",    39,  100, "Reverb Pre-Delay"),
    (46, "P_CHO_MODE",   93,  4,   "Chorus Mode (Off, Type 1..4)"),

    # 47..52: VOICE & SYSTEM
    (47, "P_POLY_MODE",  80,  8,   "Poly Mode (Mono, Unison, Poly, Chord, Pan.N, Duo, Duo 1..3)"),
    (48, "P_PORTA_MODE", 31,  2,   "Portamento Mode (Off, On, Auto)"),
    (49, "P_PORTA_TIME", 5,   127, "Portamento Time"),
    (50, "P_PORTA_SW",   65,  1,   "Portamento Switch (Off, On)"),
    (51, "P_TRANSPOSE",  77,  120, "Transpose (-60..+60)"),
    (52, "P_VOLUME",     7,   127, "Volume"),

    # 53..58: CHORD
    (53, "P_CHORD_SW2",  81,  1,   "Chord Voice 2 Switch"),
    (54, "P_CHORD_SW3",  82,  1,   "Chord Voice 3 Switch"),
    (55, "P_CHORD_SW4",  83,  1,   "Chord Voice 4 Switch"),
    (56, "P_CHORD_KS2",  85,  24,  "Chord Voice 2 Shift"),
    (57, "P_CHORD_KS3",  86,  24,  "Chord Voice 3 Shift"),
    (58, "P_CHORD_KS4",  87,  24,  "Chord Voice 4 Shift"),
]

CC_TO_PARAM = {p[2]: p for p in PARAMS}
PARAM_BY_NAME = {p[1]: p for p in PARAMS}

# Find ports
def find_ports():
    in_names = [n for n in mido.get_input_names() if "Felucca" in n or "M-Vave" in n]
    out_names = [n for n in mido.get_output_names() if "Felucca" in n or "M-Vave" in n]
    if not in_names or not out_names:
        raise RuntimeError("FM-1 device not found on USB-MIDI ports! Available inputs: " + str(mido.get_input_names()))
    return in_names[0], out_names[0]

def dump_active_sound(in_port, out_port):
    """Sends CC 119 and reads back all 59 parameter values."""
    # Flush pending
    for _ in in_port.iter_pending(): pass
    
    # Send CC 119
    out_port.send(mido.Message("control_change", control=119, value=127))
    
    values = {}
    start_t = time.time()
    while time.time() - start_t < 1.2:
        for msg in in_port.iter_pending():
            if msg.type == "control_change":
                cc = msg.control
                val = msg.value
                if cc in CC_TO_PARAM:
                    p_info = CC_TO_PARAM[cc]
                    # Scale back to native parameter range if needed
                    p_max = p_info[3]
                    native_val = val if p_max == 127 else round(val * p_max / 127)
                    values[p_info[1]] = native_val
        time.sleep(0.01)
        if len(values) >= len(PARAMS):
            break
            
    return values

def get_prm_for_preset(preset_num):
    """Finds and parses the Roland factory PRM file for preset 1..64."""
    # Pattern numbering: Bank 1-4, Pattern 1-16
    bank = (preset_num - 1) // 16 + 1
    pat = (preset_num - 1) % 16 + 1
    pattern_name = f"S1_PTN{bank}-{pat:02d}.PRM"
    
    # Search in s1_factory_backup or s1_backup
    paths = glob.glob(f"../s1_factory_backup/{pattern_name}") + glob.glob(f"s1_factory_backup/{pattern_name}")
    if not paths:
        paths = glob.glob(f"../obervave-main/s1_backup/{pattern_name}") + glob.glob(f"s1_backup/{pattern_name}")
    if not paths:
        return None, None
        
    prm_path = paths[0]
    res = import_s1_prm.parse_prm_file(prm_path)
    prms = res["prms"]
    
    # Scale PRM values to our parameter enums (with factory defaults as baseline)
    scaled_prms = dict(import_s1_prm.DEFAULT_PARAMS) if hasattr(import_s1_prm, "DEFAULT_PARAMS") else {}
    for k, v in prms.items():
        if k in import_s1_prm.PRM_TO_PARAM:
            p_name = import_s1_prm.PRM_TO_PARAM[k]
            scaled_prms[p_name] = import_s1_prm.scale_value(p_name, v)
            
    return prm_path, scaled_prms

def print_drift_table(preset_num, fm1_vals, prm_vals, prm_path):
    print("\n" + "=" * 80)
    print(f"  S-VAVE / ROLAND S-1 PARAMETER DRIFT REPORT - PRESET {preset_num:02d}")
    if prm_path:
        print(f"  Reference PRM: {os.path.basename(prm_path)}")
    print("=" * 80)
    print(f"{'PARAMETER':<18} {'CC':>4}  {'ROLAND S-1':>10}  {'FM-1 LIVE':>10}  {'DRIFT (Δ)':>10}  {'DESCRIPTION'}")
    print("-" * 80)

    drifts = {}
    critical_params = ["P_CUTOFF", "P_RESO", "P_FENV_AMT", "P_FLFO_AMT", "P_ATTACK", "P_DECAY", "P_SUSTAIN", "P_RELEASE", "P_SAW_LVL", "P_PULSE_LVL", "P_SUB_LVL", "P_NOISE_LVL", "P_PWM_DEPTH", "P_LFO_RATE", "P_REV_TIME", "P_REV_LVL"]

    for idx, name, cc, max_val, desc in PARAMS:
        fm1_v = fm1_vals.get(name, "-")
        prm_v = prm_vals.get(name, "-") if prm_vals else "-"
        
        drift_str = "-"
        if isinstance(fm1_v, int) and isinstance(prm_v, int):
            delta = fm1_v - prm_v
            drifts[name] = delta
            if delta > 0:
                drift_str = f"+{delta}"
            elif delta < 0:
                drift_str = f"{delta}"
            else:
                drift_str = "0"
                
        # Highlight non-zero drift
        hl_start = "\033[1;33m" if drift_str not in ["-", "0"] else ""
        hl_end = "\033[0m" if hl_start else ""
        
        print(f"{hl_start}{name:<18} {cc:>4}  {str(prm_v):>10}  {str(fm1_v):>10}  {drift_str:>10}  {desc}{hl_end}")

    print("=" * 80)
    print("\n--- ACOUSTIC CALIBRATION SUMMARY ---")
    
    tuned_count = sum(1 for d in drifts.values() if d != 0)
    print(f"Total parameters tuned from factory PRM: {tuned_count}")
    
    if "P_CUTOFF" in drifts and drifts["P_CUTOFF"] != 0:
        print(f"  • Filter Cutoff Drift:     {drifts['P_CUTOFF']:+d} semitones")
    if "P_RESO" in drifts and drifts["P_RESO"] != 0:
        print(f"  • Filter Resonance Drift:  {drifts['P_RESO']:+d} units")
    if "P_FENV_AMT" in drifts and drifts["P_FENV_AMT"] != 0:
        print(f"  • Filter Env Depth Drift:  {drifts['P_FENV_AMT']:+d} units")
    if "P_ATTACK" in drifts and drifts["P_ATTACK"] != 0:
        print(f"  • Envelope Attack Drift:   {drifts['P_ATTACK']:+d} units")
    if "P_DECAY" in drifts and drifts["P_DECAY"] != 0:
        print(f"  • Envelope Decay Drift:    {drifts['P_DECAY']:+d} units")
    if "P_REV_TIME" in drifts and drifts["P_REV_TIME"] != 0:
        print(f"  • Reverb Time Drift:       {drifts['P_REV_TIME']:+d} units")
        
    print("-" * 80)

def monitor_live_knobs(in_port, preset_num):
    print("\n" + "=" * 80)
    print(f"  LIVE KNOB MONITORING ACTIVE (Listening on USB-MIDI)")
    print(f"  Turn any knob on the FM-1 to see live value and drift against Preset {preset_num:02d}.")
    print("  Press Ctrl+C to stop.")
    print("=" * 80 + "\n")
    
    _, prm_vals = get_prm_for_preset(preset_num)
    
    try:
        for msg in in_port:
            if msg.type == "control_change":
                cc = msg.control
                raw_v = msg.value
                if cc in CC_TO_PARAM:
                    p_info = CC_TO_PARAM[cc]
                    p_name = p_info[1]
                    p_max = p_info[3]
                    p_desc = p_info[4]
                    native_v = raw_v if p_max == 127 else round(raw_v * p_max / 127)
                    
                    prm_v = prm_vals.get(p_name, None) if prm_vals else None
                    if prm_v is not None:
                        delta = native_v - prm_v
                        delta_str = f"Δ {delta:+d}" if delta != 0 else "MATCH (Δ 0)"
                        color = "\033[1;32m" if delta == 0 else "\033[1;33m"
                        print(f"{color}[KNOB] {p_name:<16} (CC {cc:>3}) -> {native_v:>3} | Roland S-1 was: {prm_v:>3} | {delta_str:<10} ({p_desc})\033[0m")
                    else:
                        print(f"[KNOB] {p_name:<16} (CC {cc:>3}) -> {native_v:>3} ({p_desc})")
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

def main():
    parser = argparse.ArgumentParser(description="Read FM-1 parameters and deduce drift from Roland S-1 PRMs")
    parser.add_argument("--preset", type=int, default=1, help="Preset number to compare against (1..64, default: 1)")
    parser.add_argument("--monitor", action="store_true", help="Monitor live knob turns on the FM-1 in real-time")
    args = parser.parse_args()

    in_name, out_name = find_ports()
    print(f"Connecting to FM-1 on {in_name}...")

    with mido.open_input(in_name) as in_p, mido.open_output(out_name) as out_p:
        if args.monitor:
            monitor_live_knobs(in_p, args.preset)
        else:
            print(f"Dumping live patch from FM-1...")
            fm1_vals = dump_active_sound(in_p, out_p)
            print(f"Retrieved {len(fm1_vals)} parameters from FM-1.")
            
            prm_path, prm_vals = get_prm_for_preset(args.preset)
            print_drift_table(args.preset, fm1_vals, prm_vals, prm_path)

if __name__ == "__main__":
    main()
