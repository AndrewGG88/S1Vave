#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""
Unified Build & Deploy script for S1Vave & S2Vave:
1. Builds hardware firmware (.fwsc)
2. Builds browser simulator WebAssembly (.wasm)
3. Builds VIBE FM VST WebAssembly packages (.wasm + .zip + .editor)
4. Deploys all artifacts to local folders and %APPDATA%/VIBE FM/Firmware/
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
S1VAVE = ROOT / "s1vave-main"
S2VAVE = ROOT / "s2vave"
VIBE_SDK = ROOT / "vibe-fm-sdk-main"
APPDATA_VIBE = Path(os.environ.get("APPDATA", "")) / "VIBE FM" / "Firmware"

def run_wsl(cmd, cwd=None):
    c = f"cd '{cwd}' && {cmd}" if cwd else cmd
    full_cmd = ["wsl", "-d", "Ubuntu", "-e", "bash", "-lic", c]
    print(f"--> [WSL] {c}")
    res = subprocess.run(full_cmd, text=True)
    if res.returncode != 0:
        print(f"Error: command failed with code {res.returncode}")
        sys.exit(res.returncode)

def main():
    # 1. Read version
    version_file = S1VAVE / "VERSION"
    version = version_file.read_text().strip() if version_file.exists() else "1.11"
    print(f"=== S1VAVE / S2VAVE BUILD PIPELINE (Version {version}) ===")

    # 2. Build hardware firmware
    print("\n[1/4] Building hardware firmware (.fwsc)...")
    run_wsl(f"./build.sh --release {version}", cwd="/mnt/g/S-1 M-Vave Firmware/s1vave-main")

    # 3. Build browser simulator WASM
    print("\n[2/4] Building simulator WebAssembly (docs/sim/s1vave.wasm)...")
    run_wsl("sh web/sim/build.sh", cwd="/mnt/g/S-1 M-Vave Firmware/s1vave-main")

    # 4. Build VIBE VST targets
    print("\n[3/4] Building VIBE VST WASM packages (s1vave & s2vave)...")
    run_wsl("sh firmware/s1vave/build.sh && sh firmware/s2vave/build.sh", cwd="/mnt/g/S-1 M-Vave Firmware/vibe-fm-sdk-main")

    # 5. Deploy all artifacts
    print("\n[4/4] Deploying to local folders...")

    # Root workspace
    fwsc_src = S1VAVE / "build" / f"s1vave-{version}.fwsc"
    if not fwsc_src.exists():
        fwsc_src = S1VAVE / "build" / "s1vave.fwsc"
    if fwsc_src.exists():
        shutil.copy2(fwsc_src, ROOT / "s1vave.fwsc")
        print(f"  [OK] Copied {fwsc_src.name} -> ROOT/s1vave.fwsc")

    sim_wasm = S1VAVE / "docs" / "sim" / "s1vave.wasm"
    if sim_wasm.exists():
        shutil.copy2(sim_wasm, ROOT / "s1vave-sim.wasm")
        print(f"  [OK] Copied docs/sim/s1vave.wasm -> ROOT/s1vave-sim.wasm")

    s1_vst_wasm = VIBE_SDK / "build" / "s1vave.wasm"
    s1_vst_zip = VIBE_SDK / "build" / "s1vave.zip"
    s2_vst_wasm = VIBE_SDK / "build" / "s2vave.wasm"
    s2_vst_zip = VIBE_SDK / "build" / "s2vave.zip"

    if s1_vst_wasm.exists():
        shutil.copy2(s1_vst_wasm, ROOT / "s1vave.wasm")
        shutil.copy2(s1_vst_zip, ROOT / "s1vave-vibe.zip")
        print("  [OK] Copied s1vave VST wasm & zip -> ROOT")

    if s2_vst_wasm.exists():
        shutil.copy2(s2_vst_wasm, ROOT / "s2vave.wasm")
        shutil.copy2(s2_vst_zip, ROOT / "s2vave.zip")
        print("  [OK] Copied s2vave VST wasm & zip -> ROOT")

    # VST folder in APPDATA
    if APPDATA_VIBE.exists():
        for fw in ["s1vave", "s2vave"]:
            for ext in [".wasm", ".json", ".zip"]:
                p = VIBE_SDK / "build" / f"{fw}{ext}"
                if p.exists():
                    shutil.copy2(p, APPDATA_VIBE / f"{fw}{ext}")
            ed_src = VIBE_SDK / "build" / f"{fw}.editor"
            ed_dst = APPDATA_VIBE / f"{fw}.editor"
            if ed_src.exists():
                if ed_dst.exists():
                    shutil.rmtree(ed_dst)
                shutil.copytree(ed_src, ed_dst)
        print(f"  [OK] Deployed s1vave & s2vave -> {APPDATA_VIBE}")

    # Web zip bundles
    sim_dir = S1VAVE / "docs" / "sim"
    if sim_dir.exists():
        zip_path = ROOT / "s1vave-sim-web.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sim_dir.glob("*"):
                if f.is_file():
                    z.write(f, f.name)
        print(f"  [OK] Created web bundle: ROOT/s1vave-sim-web.zip")

    ed_dir = S1VAVE / "web" / "editor"
    if ed_dir.exists():
        zip_path = ROOT / "s1vave-editor-web.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in ed_dir.glob("*"):
                if f.is_file():
                    z.write(f, f.name)
        print(f"  [OK] Created web bundle: ROOT/s1vave-editor-web.zip")

    print("\n=== ALL BUILDS & DEPLOYMENTS COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()

