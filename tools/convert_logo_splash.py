#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Convert user logo 'Logo Final - Copy.png' into firmware/gen/obv_splash.h for S1-Vave boot screen."""
import os
import sys
from PIL import Image

def generate_splash(logo_path, out_h):
    logo = Image.open(logo_path)
    # Target width 220 px (out of 240 px display)
    target_w = 220
    target_h = int(round(logo.size[1] * target_w / logo.size[0]))

    resized = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)

    splash_w = 240
    splash_h = target_h + 8
    ox = (splash_w - target_w) // 2
    oy = 4

    panel_rgb = (24, 26, 27) # C_PANEL

    # Layer 0: Clean logo over panel
    im0 = Image.new('RGBA', (splash_w, splash_h), panel_rgb + (255,))
    im0.alpha_composite(resized, (ox, oy))

    # Layer 1: Banded logo with Roland S-1 emerald/teal stripes across lower half
    im1 = Image.new('RGBA', (splash_w, splash_h), panel_rgb + (255,))
    im1.alpha_composite(resized, (ox, oy))

    band_y0 = oy + int(target_h * 0.48)
    band_h = 3
    band_gap = 2
    stripes = [(0, 120, 85), (0, 184, 135), (30, 220, 160)]

    px1 = im1.load()
    px_res = resized.load()
    for b, col in enumerate(stripes):
        y_start = band_y0 + b * (band_h + band_gap)
        for y in range(y_start, y_start + band_h):
            if 0 <= y - oy < target_h:
                for x in range(target_w):
                    if px_res[x, y - oy][3] > 40:
                        px1[ox + x, y] = col + (255,)

    im0_rgb = im0.convert('RGB')
    im1_rgb = im1.convert('RGB')

    both = Image.new('RGB', (splash_w, 2 * splash_h))
    both.paste(im0_rgb, (0, 0))
    both.paste(im1_rgb, (0, splash_h))

    q = both.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = q.getpalette()[:255 * 3]
    try:
        idx = list(q.get_flattened_data())
    except AttributeError:
        idx = list(q.getdata())

    # Snap panel background
    bg_i = idx[0]
    pal[3 * bg_i : 3 * bg_i + 3] = panel_rgb

    def rle(data):
        out = []
        i = 0
        while i < len(data):
            j = i
            while j < len(data) and data[j] == data[i] and j - i < 255:
                j += 1
            out += [j - i, data[i]]
            i = j
        return out

    rows = [rle(idx[k * splash_w * splash_h : (k + 1) * splash_w * splash_h]) for k in range(2)]

    def rgb565(r, g, b):
        return (r >> 3) << 11 | (g >> 2) << 5 | b >> 3

    pal565 = [rgb565(*pal[3 * i : 3 * i + 3]) for i in range(255)]

    lines = [
        "/* Generated from Logo Final - Copy.png for S1-Vave boot screen: 240 px wide, two layers, RLE pairs over RGB565 palette */",
        f"#define SPLASH_W {splash_w}",
        f"#define SPLASH_H {splash_h}",
        "static const uint16_t SPLASH_PAL[255] = {" + ", ".join(f"0x{c:04X}" for c in pal565) + "};"
    ]
    for k, r in enumerate(rows):
        lines.append(f"static const uint8_t SPLASH_RLE{k}[{len(r)}] = {{")
        for i in range(0, len(r), 32):
            lines.append("    " + ", ".join(str(v) for v in r[i:i + 32]) + ",")
        lines.append("};")

    with open(out_h, 'w') as f:
        f.write("\n".join(lines) + "\n")
    print(f"Generated {out_h} ({splash_w}x{splash_h}, RLE {len(rows[0])} + {len(rows[1])} B)")

    # Also update docs/sim/logo.png for the web simulator
    sim_logo = "docs/sim/logo.png"
    if os.path.exists("docs/sim"):
        logo.resize((target_w * 2, target_h * 2), Image.Resampling.LANCZOS).save(sim_logo)
        print(f"Updated {sim_logo}")

if __name__ == '__main__':
    logo_file = "/run/media/andrewgg/SSD Data N/S-1 M-Vave Firmware/Logo Final - Copy.png"
    out_file = "firmware/gen/obv_splash.h"
    generate_splash(logo_file, out_file)
