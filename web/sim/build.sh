#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# S1Vave in the browser: the firmware's sources (unchanged) + web/sim/sim.c -> WebAssembly, plus the page.
#   sh web/sim/build.sh   ->  docs/sim/{index.html, sim.js, sim.css, worklet.js, s1vave.wasm, logo.png}
#   then: python3 -m http.server -d docs/sim 8737   and open http://localhost:8737
# Tools (once, nothing system-wide; the paths can be overridden with ZIG= / WASM_OPT=):
#   zig cc (wasm32-freestanding, as winampFM's firmware/build-wasm.sh):
#     python3 -m venv ~/.local/share/s1vave-wasm && ~/.local/share/s1vave-wasm/bin/pip install ziglang
#   Binaryen's wasm-opt (Asyncify: the main loop never returns, so it runs as a coroutine; see sim.c):
#     https://github.com/WebAssembly/binaryen/releases (binaryen-version_133-x86_64-linux.tar.gz),
#     unpacked into ~/.local/share/s1vave-wasm/
set -e
cd "$(dirname "$0")/../.."
T="$HOME/.local/share/s1vave-wasm"
if [ -z "$ZIG" ]; then
    if [ -x "$T/bin/python" ] && "$T/bin/python" -c "import ziglang" 2>/dev/null; then ZIG="$T/bin/python -m ziglang"
    elif python3 -c "import ziglang" 2>/dev/null; then ZIG="python3 -m ziglang"
    elif command -v zig >/dev/null 2>&1; then ZIG=zig
    else echo "sim: no zig (see the top of web/sim/build.sh)"; exit 1; fi
fi
if [ -z "$WASM_OPT" ]; then
    WASM_OPT=$(ls -d "$T"/binaryen-*/bin/wasm-opt 2>/dev/null | sort | tail -n 1)
    [ -n "$WASM_OPT" ] || WASM_OPT=$(command -v wasm-opt || true)
    [ -n "$WASM_OPT" ] || { echo "sim: no wasm-opt (see the top of web/sim/build.sh)"; exit 1; }
fi
mkdir -p build/sim docs/sim
nice -n 15 $ZIG cc --target=wasm32-freestanding -mcpu=generic+bulk_memory -O2 -fno-builtin -ffreestanding -nostdlib \
    -Wall -Wno-unused-function -Wno-unused-variable -Wno-unused-but-set-variable \
    -Ifirmware/src -Ifirmware/gen \
    -Wl,--no-entry -Wl,--export-memory -Wl,--export-dynamic -Wl,-z,stack-size=262144 \
    -o build/sim/raw.wasm web/sim/sim.c
nice -n 15 "$WASM_OPT" build/sim/raw.wasm --enable-bulk-memory --asyncify -O2 --strip-debug --strip-producers \
    -o docs/sim/s1vave.wasm
cp web/sim/index.html web/sim/sim.js web/sim/sim.css web/sim/worklet.js docs/sim/
python3 - <<'PY' || cp assets/logo-transparent.png docs/sim/logo.png
from PIL import Image                           # the logo at page size (the 1600 px original is 290 KB)
im = Image.open("assets/logo-transparent.png")
im.resize((640, im.height * 640 // im.width), Image.LANCZOS).save("docs/sim/logo.png", optimize=True)
PY
echo "sim: docs/sim ($(wc -c < docs/sim/s1vave.wasm | tr -d ' ') B wasm)"
