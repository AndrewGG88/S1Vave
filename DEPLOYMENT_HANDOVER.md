# S1Vave: Deployment & Web Integration Handover

> **Target Audience**: Web Developer / Backend Agent / Deployment Agent  
> **Repository**: [https://github.com/AndrewGG88/S1Vave.git](https://github.com/AndrewGG88/S1Vave.git) (Branch: `master`)  
> **Local Source Directory**: `s1vave-main/` (inside `g:\S-1 M-Vave Firmware\s1vave-main`)  
> **Firmware Package**: `build/s1vave-1.0.fwsc` (Target ID: `FM-1_950`)  
> **Author & Brand**: Andrew GG (`BY ANDREW GG`)  
> **License**: GNU General Public License v3.0 (`GPL-3.0-only`)

---

## 1. Project Context & Current State

**S1Vave** is an open-source custom firmware for the **M-VAVE FM-1** hardware synthesizer (JieLi AC791N 32-bit RISC core) that achieves 1:1 acoustic, functional, and MIDI CC parity with the **Roland AIRA Compact S-1 Tweak Synth** (heritage of the Roland SH-101).

### Key Accomplishments Completed in this Workspace:
1. **Clean-room DSP Engine**: 8-voice polyphony (Mono, Unison, Poly, Chord), 4-pole 24 dB/oct state-variable filter, analog-calibrated ADSR envelopes, OSC DRAW, OSC CHOP, Riser/Downer, and Roland stereo FX suite.
2. **Visual & Splash Identity**: Custom splash screen integrated into firmware (`firmware/src/splash_s1vave.h`) and web simulator featuring Andrew GG's 3D cyber orb and `BY ANDREW GG` typography in electric cyan (`#0ebafb`).
3. **Hardware Verified**: Compiled and flashed to physical M-VAVE FM-1 hardware over USB-MIDI.
4. **WebAssembly Simulator**: Compiled and verified running in `docs/sim/s1vave.wasm` and `web/sim/s1vave.wasm`.
5. **Sanitization & Repository Sync**: All obsolete temporary files and old scripts purged. Git history committed and pushed cleanly to the private GitHub repository `https://github.com/AndrewGG88/S1Vave.git`.

---

## 2. Firmware Compilation Pipeline (Linux / VPS / Docker)

The firmware is designed to be built on Linux x86_64 (or WSL2 / Docker) due to the proprietary JieLi AC79 SDK compiler.

### Prerequisites (Ubuntu / Debian / Docker)
```bash
sudo apt update
sudo apt install -y python3 python3-pip git build-essential
pip3 install Pillow
```

### Toolchain Setup
```bash
cd s1vave-main
./tools/get_toolchain.sh
```
Or export the environment variables if already installed on the VPS:
```bash
export JIELI_TOOLCHAIN="/path/to/jieli/toolchain"
export AC79_SDK="/path/to/fw-AC79_AIoT_SDK"
```

### Build Commands
```bash
# 1. Compile firmware package:
./build.sh --release 1.0

# Result:
# Output binary: build/s1vave-1.0.fwsc (610 KB)
# Disassembly:   build/s1vave.dis
# Identity:      FM-1_950
```

### Compiler Constraints (Important for any C changes):
- **Integer only**: No `float` or `double`. Uses Q15 fixed-point arithmetic.
- **No 64-bit division**: `int64_t / int64_t` requires `__udivdi3`, which will trigger a linker error.
- **ROM trap**: Addresses in `0xFFC00000..0xFFCFFFFF` trigger build errors.

---

## 3. WebAssembly Simulator Build Pipeline

The web simulator runs the exact C firmware sources in the browser via WebAssembly (compiled with Zig and Binaryen Asyncify).

### Build Command:
```bash
cd s1vave-main
sh web/sim/build.sh
```
- **Output files**: `docs/sim/s1vave.wasm` and `web/sim/s1vave.wasm` (~166 KB).
- **Prerequisites**: `zig` (0.11+) and `wasm-opt` (Binaryen).

### Local Testing:
```bash
python3 -m http.server 8737 -d docs/sim
```
- Virtual Synth URL: `http://localhost:8737/`
- Calibration Studio URL: `http://localhost:8737/editor/`

---

## 4. Web Flasher & Online Installer Implementation

The user plans to host 1-click web flashing directly on their own domain/VPS rather than waiting for third-party firmware hubs.

### How the FM-1 Browser Flasher Works:
The M-VAVE FM-1 update protocol runs entirely in the browser using the standard **WebMIDI API** (or WebUSB via WebHID):
1. **Device Connection**: Request MIDI access via `navigator.requestMIDIAccess({ sysex: true })`.
2. **Identification**: Listen for the FM-1 device name (`M-VAVE FM-1` or `Felucca 5` or `FM-1_950`).
3. **Enter Update Mode**: Send the handshake SysEx message to put the hardware into OTA bootloader mode.
4. **Binary Upload**: Read the `.fwsc` file (`s1vave-1.0.fwsc`) and stream it in 256-byte chunks with CRC32 verification.
5. **Reboot**: Send the reboot SysEx packet; the device automatically restarts with S1Vave.

> **Protocol Reference**: The complete, tested Python implementation is in [`tools/fm1_install.py`](file:///g:/S-1%20M-Vave%20Firmware/s1vave-main/tools/fm1_install.py). Use `fm1_install.py` as the blueprint to write the JavaScript WebMIDI flasher module.

---

## 5. Web Assets & Media Kit

All branding assets are ready to be served by the web backend:

| Asset | Location in Repo | Description |
| :--- | :--- | :--- |
| **Splash Screen (Retina)** | `assets/splash.png` | 480x480 (downscales to 240x240 LCD), deep charcoal `#181a1b`, 3D cyber orb, `BY ANDREW GG` in electric cyan `#0ebafb`. |
| **Screen Capture** | `docs/screen.png` | 240x240 hardware screenshot of the PTN 1-01 PERFORM page with cutoff/resonance/scope/LEDs. |
| **Vector Logos** | `assets/logo.svg`, `docs/sim/logo.svg` | SVG vector logotypes for banners and header badges. |
| **Transparent PNG Logo** | `assets/logo-transparent.png` | High-res transparent PNG logotype for dark backgrounds. |
| **Color Tokens** | — | **Charcoal Background**: `#181a1b`<br>**S-1 Accent Green**: `#00b887`<br>**Filter Amber / Orange**: `#ff6b18`<br>**Cyber Electric Cyan**: `#0ebafb`<br>**7-Segment Red**: `#ff2020` |

---

## 6. GitHub Release & Automation (When Going Public)

The GitHub Actions workflow is already configured at [`.github/workflows/release.yml`](file:///g:/S-1%20M-Vave%20Firmware/s1vave-main/.github/workflows/release.yml).

### Steps for the Launch Agent:
1. **Make Repository Public**:
   - In GitHub: `Settings` $\to$ `Danger Zone` $\to$ `Change repository visibility` $\to$ `Make public`.
2. **Tag and Trigger Automated Release**:
   ```bash
   git tag v1.0
   git push origin v1.0
   ```
3. GitHub Actions will automatically:
   - Check out the repository.
   - Run the JieLi toolchain in a Docker container.
   - Compile `s1vave-1.0.fwsc`.
   - Publish a GitHub Release with the binary attached and checksums generated.
4. **Direct Download Link for Website**:
   Once released, the static download URL for the firmware binary on the user's site can point directly to:
   `https://github.com/AndrewGG88/S1Vave/releases/latest/download/s1vave-1.0.fwsc`

---

## 7. Legal & Trademark Compliance Checklist
- Keep the nominative fair use disclaimer intact on all web pages:
  > *"Roland, AIRA, AIRA Compact, S-1, and SH-101 are trademarks of Roland Corporation. S1Vave is an independent community open-source project and is not affiliated with, sponsored by, or endorsed by Roland Corporation."*
- Keep the GPL-3.0 attribution lines in `LICENSING.md` crediting Andrew GG alongside upstream contributors (zvenson, Leo Kuroshita, isod89).
