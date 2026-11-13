# S1Vave Installation Guide (DAW Plugin)

S1Vave runs natively inside your DAW via the free VIBE FM host plugin (VST3, CLAP, AU).

---

## Step 1: Install the Free VIBE FM Host Plugin

Download and run the official installer for your operating system by Sven Trogus (zvenson):

* **Windows (10 / 11)**: [Download VIBE FM Windows Setup (.exe)](https://thefirmwarehub.com/fw/vibe/VIBE-FM-VST-0.7.9-Windows-Setup.exe)
* **macOS (11+, Apple Silicon and Intel)**: [Download VIBE FM macOS Package (.pkg)](https://thefirmwarehub.com/fw/vibe/VIBE-FM-0.7.9-macOS.pkg)
* **Linux (Ubuntu / Debian x86_64)**: [Download .deb package](https://thefirmwarehub.com/fw/vibe/vibe-fm-vst_0.7.9-1_amd64.deb)
* **Linux (Fedora x86_64)**: [Download .rpm package](https://thefirmwarehub.com/fw/vibe/vibe-fm-vst-0.7.9-1.x86_64.rpm)
* **Linux (Generic / Any distribution)**: [Download .tar.gz with install.sh](https://thefirmwarehub.com/fw/vibe/VIBE-FM-VST-0.7.9-Linux.tar.gz)
* **Raspberry Pi / ARM64 (Debian / Pi OS)**: [Download ARM64 .deb](https://thefirmwarehub.com/fw/vibe/vibe-fm-vst_0.7.9-1_arm64.deb)
* **Raspberry Pi / ARM64 (Fedora)**: [Download ARM64 .rpm](https://thefirmwarehub.com/fw/vibe/vibe-fm-vst-0.7.9-1.aarch64.rpm)
* **Raspberry Pi / ARM64 (Generic)**: [Download ARM64 .tar.gz](https://thefirmwarehub.com/fw/vibe/VIBE-FM-VST-0.7.9-Linux-arm64.tar.gz)

---

## Step 2: Install S1Vave

### Option A: Windows (Automatic Installer)
Run `S1Vave-v2.0-Windows-Setup.exe`.
This automatically installs the engine, metadata, icon, and custom web interface into the VIBE FM firmware directories:
* User folder: `%APPDATA%\VIBE FM\Firmware`
* System folder: `C:\ProgramData\VIBE FM\Firmware`

### Option B: macOS, Linux, and Windows (Drag and Drop)
1. Open your DAW (Ableton Live, FL Studio, Reaper, Bitwig, Cubase, Logic Pro).
2. Insert **VIBE FM VST** (or AU / CLAP) onto a MIDI track.
3. Drag the downloaded `s1vave.zip` file directly onto the VIBE FM plugin window (do not unzip it).
4. S1Vave will immediately unpack, install, and start playing.

### Option C: Manual File Placement
Extract `s1vave.zip` and place `s1vave.wasm`, `s1vave.json`, `s1vave.png`, and the `s1vave.editor` folder into:
* **macOS**: `~/Library/Application Support/VIBE FM/Firmware` (In Finder: Go -> Go to Folder...)
* **Windows**: `%APPDATA%\VIBE FM\Firmware`
* **Linux**: `~/.local/share/VIBE FM/Firmware`

---

## Step 3: Play and Automate

1. Select **S1VAVE** from the top firmware dropdown menu in the plugin window.
2. The custom S1Vave web editor will open showing all synth controls.
3. All parameters are exposed to your DAW for automation and MIDI hardware controller mapping.

---

## Troubleshooting (Blank White Screen on Windows / Ableton Live 12)

If the VIBE FM plugin window opens as a blank white screen in Ableton Live 12 or another Windows DAW:
1. Install or repair the **Microsoft Edge WebView2 Runtime** (Evergreen Bootstrapper) and restart your DAW.
2. Right-click the plugin in Ableton's browser to toggle **Auto-Scale Plugin Window**, or set environment variable `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--disable-gpu` if GPU compositing conflicts with your graphics driver.

---

## Credits and Licenses

* S1Vave Synthesizer: Andrew GG (GNU General Public License v3.0)
* VIBE FM Plugin and OberVave: Sven Trogus (zvenson, https://thefirmwarehub.com/vibe/)

