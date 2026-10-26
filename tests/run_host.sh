#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# Run firmware/src/s1vave.c on this computer (tests/host.c): build/host/s1vave.wav and the screens as PNG.
#   BOARD=smk37 tests/run_host.sh [script]: the SMK-37 build (pads, faders, wheels, outer keys; build/host/s1vave-smk37*)
set -e
cd "$(dirname "$0")/.."
mkdir -p build/host
N=s1vave; D=
if [ "${BOARD:-fm1}" = smk37 ]; then N=s1vave-smk37; D=-DBOARD_SMK37=1; fi
cc -O2 -Wall -Wno-unused-function -DOBV_HOST $D -DAPP_VER="\"${APP_VER:-dev}\"" -Ifirmware/src -Ifirmware/gen -o build/host/$N firmware/src/s1vave.c
build/host/$N build/host/$N ${1:+"$1"}
python3 - <<'PY'
from pathlib import Path
from PIL import Image
for p in sorted(Path("build/host").glob("s1vave-*.ppm")):   # (the SMK build's too: s1vave-smk37-*.ppm)
    Image.open(p).resize((480, 480), Image.NEAREST).save(p.with_suffix(".png"))
    p.unlink()
    print("screen ->", p.with_suffix(".png"))
PY
