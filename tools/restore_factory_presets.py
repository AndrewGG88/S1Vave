#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""
S1Vave & Roland S-1 Factory Preset Restorer.
Loads original factory sound presets from `s1_factory_backup/` (.PRM)
and restores/transmits them to:
  1. The physical Roland AIRA Compact S-1 (over USB-MIDI)
  2. The M-VAVE FM-1 synthesizer hardware (over USB-MIDI)
  3. The firmware source header (`firmware/src/obv_patches.h`)
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

# Import helper modules
sys.path.append(os.path.join(os.path.dirname(__file__)))
import import_s1_prm
import s1_drift_reader

def find_ports():
    in_names = mido.get_input_names()
    out_names = mido.get_output_names()
    fm1 = [p for p in out_names if "Felucca" in p or "M-Vave" in p]
    s1 = [p for p in out_names if "S-1" in p]
    return {
        "fm1": fm1[0] if fm1 else None,
        "s1": s1[0] if s1 else None,
    }

def restore_preset(num, ports, target="both", verbose=True):
    """Restores an authentic Roland S-1 factory preset over MIDI."""
    num = max(1, min(64, num))
    prm_path, prms = s1_drift_reader.get_prm_for_preset(num)
    if not prms:
        print(f"Error: Could not locate PRM file for Preset {num:02d}!")
        return False

    prog_idx = num - 1
    msg_pc = mido.Message('program_change', program=prog_idx)

    # Open MIDI outputs
    out_fm1 = mido.open_output(ports["fm1"]) if ports["fm1"] and target in ["both", "fm1"] else None
    out_s1 = mido.open_output(ports["s1"]) if ports["s1"] and target in ["both", "s1"] else None

    if not out_fm1 and not out_s1:
        print("Error: No MIDI output ports available!")
        return False

    # 1. Send Program Change so on-screen pattern updates
    if out_fm1: out_fm1.send(msg_pc)
    if out_s1: out_s1.send(msg_pc)
    time.sleep(0.05)

    # 2. Push all 59 parameter CC values from the factory PRM
    sent_count = 0
    for idx, name, cc, max_val, desc in s1_drift_reader.PARAMS:
        if name in prms:
            val = prms[name]
            msg_cc = mido.Message('control_change', control=cc, value=val)
            if out_fm1: out_fm1.send(msg_cc)
            if out_s1: out_s1.send(msg_cc)
            sent_count += 1

    if out_fm1: out_fm1.close()
    if out_s1: out_s1.close()

    if verbose:
        pname = os.path.basename(prm_path)
        print(f"  [✓] Preset {num:02d} ({pname}): Transmitted {sent_count} parameter CCs to {target.upper()}")
    return True

def sync_firmware_header():
    """Regenerates firmware/src/obv_patches.h from s1_factory_backup."""
    backup_dirs = ["../s1_factory_backup", "s1_factory_backup"]
    chosen = None
    for b in backup_dirs:
        if os.path.isdir(b):
            chosen = b
            break
    if not chosen:
        print("Error: s1_factory_backup directory not found!")
        return False

    files = sorted(glob.glob(os.path.join(chosen, "*.PRM")))
    if len(files) < 64:
        print(f"Error: Found only {len(files)} PRM files in {chosen} (expected 64)!")
        return False

    out_h = "firmware/src/obv_patches.h"
    import_s1_prm.generate_c_patches(files, out_h)
    print(f"  [✓] Successfully updated {out_h} with all {len(files)} factory sound presets.")
    return True

def main():
    parser = argparse.ArgumentParser(description="Restore & Import Authentic Roland S-1 Factory Presets")
    parser.add_argument("-p", "--preset", type=int, default=None, help="Preset number to restore (1..64). Default: all")
    parser.add_argument("-t", "--target", choices=["both", "s1", "fm1"], default="both", help="Target synth device")
    parser.add_argument("--sync-header", action="store_true", help="Regenerate firmware/src/obv_patches.h from PRM backup")
    parser.add_argument("--all", action="store_true", help="Send all 64 presets sequentially to synths")
    args = parser.parse_args()

    print("=" * 70)
    print("      S1VAVE & ROLAND S-1 FACTORY PRESET RESTORER")
    print("=" * 70)

    if args.sync_header:
        sync_firmware_header()
        return

    ports = find_ports()
    print(f"Detected FM-1 MIDI Out: {ports['fm1']}")
    print(f"Detected S-1  MIDI Out: {ports['s1']}")

    if args.preset:
        print(f"\nRestoring Factory Preset {args.preset:02d} to {args.target.upper()}...")
        restore_preset(args.preset, ports, target=args.target)
    elif args.all:
        print(f"\nRestoring ALL 64 Factory Presets to {args.target.upper()}...")
        for p in range(1, 65):
            restore_preset(p, ports, target=args.target, verbose=False)
            print(f"  [✓] Preset {p:02d}/64 sent", end="\r", flush=True)
            time.sleep(0.04)
        print("\nAll 64 Factory Presets successfully transmitted!")
    else:
        # Default: restore current preset 1 and ensure header is synced
        print("\nSyncing firmware header and restoring Preset 01...")
        sync_firmware_header()
        restore_preset(1, ports, target=args.target)

    print("\nRestore operation complete.")

if __name__ == "__main__":
    main()
