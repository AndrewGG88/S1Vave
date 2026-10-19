#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""OberVave's logo: tools/make_logo.py -> assets/logo.svg, assets/logo.png (and the same on a transparent background).
The word in a bold 70s serif as outlines that glow red (the look of a certain small-town title card), the lower half of
the letters crossed by three blue bands (the look of a certain blue synthesizer panel). The letters are paths, so the
SVG needs no fonts. An own drawing: no one's trade dress, two moods.

  python3 tools/make_logo.py [font.otf] [out-dir]
  python3 tools/make_logo.py --splash          -> firmware/gen/obv_splash.h (the boot screen, see obv_ui.h ui_splash)"""
import subprocess, sys
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

HERE = Path(__file__).resolve().parent.parent
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
FONT = ARGS[0] if ARGS else "/run/host/fonts/urw-base35/URWBookman-Demi.otf"
OUT = Path(ARGS[1]) if len(ARGS) > 1 else HERE / "assets"
SUB_FONT = "/run/host/fonts/rsms-inter-fonts/Inter-SemiBold.ttf"

WORD = "OBERVAVE"
CAP = 150                                           # the cap height in user units
TRACK = 0.06                                        # letter spacing, as a fraction of the cap height
BLUE = ["#1e46be", "#3c82eb", "#78beff"]
RED, RED_DEEP, PANEL, CREAM = "#ff2c20", "#7a1410", "#0b0e16", "#e2e8f0"

def word_paths(font_path, text, cap, track, weight=None):
    """the glyphs of `text` as SVG path data, laid out from x = 0, baseline at y = 0, scaled to cap height `cap`"""
    f = TTFont(font_path)
    if weight and "fvar" in f:
        from fontTools.varLib.instancer import instantiateVariableFont
        f = instantiateVariableFont(f, {"wght": weight})
    gs = f.getGlyphSet()
    cmap = f.getBestCmap()
    upm = f["head"].unitsPerEm
    cap_units = f["OS/2"].sCapHeight if getattr(f["OS/2"], "sCapHeight", 0) else upm * 0.7
    s = cap / cap_units
    x, paths, widths = 0.0, [], []
    for ch in text:
        g = gs[cmap[ord(ch)]]
        pen = SVGPathPen(gs)
        g.draw(TransformPen(pen, (s, 0, 0, -s, x, 0)))
        paths.append(pen.getCommands())
        widths.append(g.width * s)
        x += g.width * s + track * cap
    return paths, x - track * cap

def logo_svg(paths, width, background=True, bands=True, sub=None, pad=70, glow=1.0, sub_h=60, pad_y=None):
    """the logo as SVG text. pad: the margin in user units (pad_y above and below, if given); glow: scales the stroke and blur (bigger for small renders);
    sub: (paths, width) of the line under the word or None"""
    if pad_y is None:
        pad_y = pad
    W, H = width + 2 * pad, CAP + 2 * pad_y + (sub_h if sub else 0)
    ox, oy = pad, pad_y + CAP                        # the baseline
    band_y0 = oy - CAP * 0.47                        # the bands: three through the lower half of the letters
    band_h, gap = CAP * 0.11, CAP * 0.05
    letters = "".join(f'<path d="{p}"/>' for p in paths)
    clip_letters = "".join(f'<path d="{p}" transform="translate({ox} {oy})"/>' for p in paths)   # no <g> in a clipPath
    band_rects = "".join(f'<rect x="{ox - 2 * pad}" y="{band_y0 + i * (band_h + gap):.1f}" width="{W + 2 * pad}" height="{band_h:.1f}" fill="{c}"/>'
                         for i, c in enumerate(BLUE))
    bg = f'<rect width="{W:.0f}" height="{H:.0f}" rx="28" fill="{PANEL}"/>' if background else ""
    band_g = f'<g clip-path="url(#letters)">{band_rects}</g>' if bands else ""
    sub_g = ""
    if sub:
        sub_paths, sub_w = sub
        sub_g = f'<g transform="translate({ox + (width - sub_w) / 2:.1f} {oy + 52})" fill="{BLUE[2]}">{"".join(f"<path d=\"{p}\"/>" for p in sub_paths)}</g>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" width="{W:.0f}" height="{H:.0f}">
<defs>
  <filter id="glow" x="-20%" y="-40%" width="140%" height="180%">
    <feGaussianBlur stdDeviation="{7 * glow:.1f}" result="b"/>
    <feColorMatrix in="b" type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 1.6 0" result="g"/>
    <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="soft" x="-20%" y="-40%" width="140%" height="180%"><feGaussianBlur stdDeviation="{2.2 * glow:.1f}"/></filter>
  <clipPath id="letters">{clip_letters}</clipPath>
</defs>
{bg}
<!-- the deep red body of the letters -->
<g transform="translate({ox} {oy})" fill="{RED_DEEP}" fill-opacity="0.55">{letters}</g>
<!-- the three bands, only inside the letters -->
{band_g}
<!-- the glowing outline -->
<g transform="translate({ox} {oy})" fill="none" stroke="{RED}" stroke-width="{7 * glow:.1f}" stroke-linejoin="round" opacity="0.55" filter="url(#soft)">{letters}</g>
<g transform="translate({ox} {oy})" fill="none" stroke="{RED}" stroke-width="{3.2 * glow:.1f}" stroke-linejoin="round" filter="url(#glow)">{letters}</g>
<!-- the line under it -->
{sub_g}
</svg>
'''

def render(svg_text, png, width):
    tmp = png.with_suffix(".svg.tmp")
    tmp.write_text(svg_text)
    subprocess.run(["rsvg-convert", "-w", str(width), "-o", str(png), str(tmp)], check=True)
    tmp.unlink()

def make_splash(paths, width, out_h):
    """the firmware's boot screen: two 240 px wide layers (the glowing letters; the same with the bands) over the
    panel colour, one shared 255-colour palette, run-length coded -> firmware/gen/obv_splash.h"""
    from PIL import Image
    SPLASH_W = 240
    pad = width / 52                                 # the word spans ~222 px, the glow has the rest
    pad_y = CAP * 0.45
    GLOW = 2.8                                       # at ~21 px cap height: ~1 px outline, a 3 px glow
    svgs = []
    for bands in (False, True):
        svgs.append(logo_svg(paths, width, background=False, bands=bands, pad=pad, pad_y=pad_y, glow=GLOW))
    panel = (8, 16, 24)                              # C_PANEL RGB(14, 18, 28) as RGB565 shows it
    layers = []
    for i, s in enumerate(svgs):
        png = out_h.parent / f"splash{i}.png"
        render(s, png, SPLASH_W)
        im = Image.open(png).convert("RGBA")
        bg = Image.new("RGBA", im.size, panel + (255,))
        layers.append(Image.alpha_composite(bg, im).convert("RGB"))
        png.unlink()
    w, h = layers[0].size
    both = Image.new("RGB", (w, 2 * h))
    both.paste(layers[0], (0, 0))
    both.paste(layers[1], (0, h))
    q = both.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = q.getpalette()[:255 * 3]
    idx = list(q.getdata())
    # the panel must be exactly C_PANEL in RGB565: snap the palette entry the background landed on
    bg_i = idx[0]
    pal[3 * bg_i:3 * bg_i + 3] = panel
    def rle(data):
        out, i = [], 0
        while i < len(data):
            j = i
            while j < len(data) and data[j] == data[i] and j - i < 255:
                j += 1
            out += [j - i, data[i]]
            i = j
        return out
    rows = [rle(idx[k * w * h:(k + 1) * w * h]) for k in range(2)]
    def rgb565(r, g, b):
        return (r >> 3) << 11 | (g >> 2) << 5 | b >> 3
    pal565 = [rgb565(*pal[3 * i:3 * i + 3]) for i in range(255)]
    lines = ["/* generated by tools/make_logo.py --splash: the boot screen's logo, 240 px wide, two layers (the glowing",
             " * letters; the same with the three bands), RLE pairs (run, palette index) over one RGB565 palette */",
             f"#define SPLASH_W {w}", f"#define SPLASH_H {h}",
             "static const uint16_t SPLASH_PAL[255] = {" + ", ".join(f"0x{c:04X}" for c in pal565) + "};"]
    for k, r in enumerate(rows):
        lines.append(f"static const uint8_t SPLASH_RLE{k}[{len(r)}] = {{")
        for i in range(0, len(r), 32):
            lines.append("    " + ", ".join(str(v) for v in r[i:i + 32]) + ",")
        lines.append("};")
    out_h.write_text("\n".join(lines) + "\n")
    print(out_h, f"{w}x{h}", "RLE", [len(r) for r in rows], "B")
    # a preview of the two layers for the eye
    both.save(out_h.parent.parent.parent / "build" / "splash-layers.png") if (out_h.parent.parent.parent / "build").exists() else None

def main():
    paths, width = word_paths(FONT, WORD, CAP, TRACK)
    if "--splash" in sys.argv:
        make_splash(paths, width, HERE / "firmware" / "gen" / "obv_splash.h")
        return
    sub = word_paths(SUB_FONT, "8-VOICE ANALOG POLY  ·  M-VAVE FM-1", 22, 0.18)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, background in (("logo", True), ("logo-transparent", False)):
        p = OUT / f"{name}.svg"
        p.write_text(logo_svg(paths, width, background=background, sub=sub))
        subprocess.run(["rsvg-convert", "-w", "1600", "-o", str(OUT / f"{name}.png"), str(p)], check=True)
        print(p, OUT / f"{name}.png")

if __name__ == "__main__":
    main()
