#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""OberVave video 1.4.1 (1920 x 1080, 30 fps, ~115 s): eight OberVaves play one slow dark track (song.py: the real
firmware's host build, all eight screens filmed at 30 fps, their stems; kick and hats share one FM-1, two sounds on
its two tracks). The whole video is a found VHS tape: a cassette
labelled OBERVAVE · DO NOT ERASE goes into the recorder, the picture has the tape's soft colours, a wobble, the head
switching at the bottom and a camcorder's date burned in; the VCR's own letters (PLAY, the chapter, STOP, EJECT) sit
crisp on top. Every section gets its own picture of what you hear, drawn from the real data:

  the cassette goes in, PLAY; the logo strikes through the snow; EIGHT FM-1s / ONE FIRMWARE / ZERO SAMPLES punched in over a macro of the screen
  ARP       the ping-pong delay made visible: echoes of the screen as it was a dotted eighth ago, left, right, left
  BASS      its waveform across the whole frame
  PAD       the chorus as double vision; the notes of the arp and the pad falling onto the keys
  LEAD      six ghosts of the screen drifting apart (unison, VINTAGE); the bend pulls the picture down the hole
  RESO      the bass's waveform wrapped round a circle: the resonance grows spikes
  DOWN      a tunnel of screens, turning with the pitch bend
  KICK      the drums come in after the first minute: its stem as a neon oscilloscope, a filter ringing like a sine
  SEQUENCER a VHS rewind to how the drums were set (SEQ held, a key per step; ALGORITHM: track B), then the TRACKS
            view huge: kick on A (blue), hats on B (orange), one FM-1, two sounds
  UPSIDE    the tape pauses half a bar before the drop; then the second arp's notes rising off the keys
  MORPH     a notch cut through the screen, widening with the filter's morph
  STRINGS   the stereo field as a Lissajous figure (the voices panned across)
  ALL EIGHT the wall of eight, each lit by its own stem; then they fall away, the lead last
  the end card: the logo, thefirmwarehub.com, like & subscribe

  the end: the tape stops (blue screen), the end card rolls in, the cassette beside it, EJECT
Titles are the logo's red neon serif (tools/make_logo.py), struck on like a tube. Cuts: a search (>>) through the tape,
the noise bars running, the colour planes tear; the pitch bend stretches the tape.
  python3 song.py (once: films + stems) && python3 make_video.py [--stills BAR ...]"""
import math, multiprocessing, subprocess, sys, wave
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

HERE = Path(__file__).resolve().parent
A = HERE
OUT = HERE / "obervave-1.4.1.mp4"
W, H, FPS, SR = 1920, 1080, 30, 44100
BPM, T0 = 94, 10.0                                     # the music starts at T0 in the films (song.py): the video starts there
BAR = 4 * 60 / BPM
BEAT = BAR / 4
F0 = int(T0 * FPS)
BG = (8, 10, 18)
CREAM, DIM, BLUE, RED = (226, 232, 240), (120, 142, 172), (96, 176, 255), (255, 44, 32)
STRIPES = [(30, 70, 190), (60, 130, 235), (120, 190, 255)]
IF = "/run/host/fonts/rsms-inter-fonts/"
def font(n, s): return ImageFont.truetype(IF + n, int(s))
F_BLACK = lambda s: font("InterDisplay-Black.ttf", s)
F_BOLD = lambda s: font("InterDisplay-Bold.ttf", s)
F_LIGHT = lambda s: font("InterDisplay-Light.ttf", s)
F_REG = lambda s: font("Inter-Regular.ttf", s)
F_SEMI = lambda s: font("Inter-SemiBold.ttf", s)
F_VHS = lambda s: ImageFont.truetype("/run/host/fonts/dejavu-sans-mono-fonts/DejaVuSansMono-Bold.ttf", int(s))
F_OSD = lambda s: ImageFont.truetype(str(A / "fonts" / "VT323-Regular.ttf"), int(s))              # the VCR's letters (OFL)
F_MARK = lambda s: ImageFont.truetype(str(A / "fonts" / "PermanentMarker-Regular.ttf"), int(s))   # the label, by hand (Apache-2.0)

PARTS = ["arp", "bass", "pad", "lead", "arp2", "strings", "drums", "clap"]   # the eight filmed FM-1s
LIGHT = PARTS + ["kick", "hat"]                      # + the drums' two tracks alone (song.py: not filmed, not mixed): their light
COL = {"arp": (255, 52, 40), "arp2": (255, 130, 60), "bass": (60, 130, 235), "pad": (70, 140, 255), "lead": (255, 70, 140),
       "strings": (170, 140, 255), "drums": (255, 44, 32), "kick": (255, 44, 32), "clap": (230, 235, 255), "hat": (150, 200, 255)}
TRK_A, TRK_B = (110, 190, 255), (255, 150, 40)        # the firmware's track colours

# ---------------------------------------------------------------- the data: logs, stems, the bend
LOG = {p: [tuple(int(x) for x in l.split()) for l in open(A / "f" / f"{p}-log.txt")] for p in PARTS}   # ms, keys, key LEDs, btn LEDs, enc x7
NF = min(len(v) for v in LOG.values())

def stem_map(name):                                   # int16 stereo, mapped (the workers share the page cache)
    raw = (A / "stems" / f"{name}.wav").read_bytes()[:4096]
    off = raw.index(b"data") + 8
    with wave.open(str(A / "stems" / f"{name}.wav")) as w:
        n = w.getnframes()
    return np.memmap(A / "stems" / f"{name}.wav", np.int16, "r", off, (n, 2))
STEM = {p: stem_map(p) for p in LIGHT}

def stem_env(p):                                      # loudness per film frame, 0..1
    m = np.abs(np.asarray(STEM[p], dtype=np.float32)).max(1) / 32768
    n = SR // FPS
    e = np.array([m[i * n:(i + 1) * n].max() if i * n < len(m) else 0 for i in range(NF)])
    return e / max(e.max(), 1e-6), float(m.max())
ENV, PEAK = {}, {}
for _p in LIGHT:
    ENV[_p], PEAK[_p] = stem_env(_p)

BEND = []                                             # (film ms, -1..1) from the lead's script
for l in open(A / "scripts" / "lead.txt"):
    s = l.split()
    if len(s) >= 5 and s[1] == "midi" and s[2] == "0xE0":
        BEND.append((int(s[0]), (int(s[3]) + 128 * int(s[4]) - 8192) / 8192))
def bend_at(fi):
    ms, v = fi * 1000 / FPS, 0.0
    for t, b in BEND:
        if t > ms: break
        v = b
    return v

KEYS = []                                             # the FM-1's 27 keys: (index, black, white index / black slot)
_nb = _nw = 0
for _k in range(27):
    if (53 + _k) % 12 in {1, 3, 6, 8, 10}: KEYS.append((_k, 1, _nw)); _nb += 1
    else: KEYS.append((_k, 0, _nw)); _nw += 1

def lane(k, x0, width):                               # a key's x span on a drawn keyboard of 16 white keys
    ww = width / 16
    _, black, i = KEYS[k]
    if black:
        bw = ww * 0.62
        return x0 + i * ww - bw / 2, x0 + i * ww + bw / 2
    return x0 + i * ww + 2, x0 + (i + 1) * ww - 2

# ---------------------------------------------------------------- pictures
def radial_bg():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((x - W / 2) / W) ** 2 + ((y - H * 0.45) / H) ** 2)
    k = np.clip(1.0 - r * 1.4, 0, 1)[..., None]
    a = np.array(BG, np.float32) + k * np.array((14, 20, 40), np.float32)
    return Image.fromarray(a.astype(np.uint8))
BGIMG = radial_bg()
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = (1.0 - 0.38 * np.clip(((_xx - W / 2) / (W / 2)) ** 2 + ((_yy - H / 2) / (H / 2)) ** 2 - 0.25, 0, 1.5) / 1.5)[..., None]
VIG = VIG * np.where(np.arange(H) % 2, 0.9, 1.0)[:, None, None]                  # the tape's lines
GRAIN = [np.random.RandomState(i).randint(-4, 5, (H, W, 1)).astype(np.int16) for i in range(6)]
del _yy, _xx

def screen_raw(part, fi):
    return Image.open(A / "f" / part / f"{max(0, min(fi, NF - 1)):05d}.png").convert("RGB")

def scanlines(s, every=3):
    a = np.asarray(s, dtype=np.float32).copy()
    a[every - 1::every] *= 0.8
    return Image.fromarray(a.astype(np.uint8))

def device(part, fi, scale, glow=0.0, col=None):      # the screen in its bezel, RGBA
    s = scanlines(screen_raw(part, fi).resize((int(240 * scale), int(240 * scale)), Image.NEAREST))
    pad = int(8 * scale)
    b = Image.new("RGBA", (s.width + 2 * pad, s.height + 2 * pad), (0, 0, 0, 0))
    col = col or BLUE
    edge = tuple(int(c0 + (c1 - c0) * min(1, glow)) for c0, c1 in zip((60, 62, 70), col))
    ImageDraw.Draw(b).rounded_rectangle([0, 0, b.width - 1, b.height - 1], radius=int(9 * scale), fill=(12, 12, 15), outline=edge, width=2 + int(glow * 3))
    b.paste(s, (pad, pad))
    return b

def halo(im, obj, xy, col, k):                        # a coloured light behind an object
    if k <= 0.02: return
    w, h = obj.size
    lay = Image.new("RGB", (W // 4, H // 4), (0, 0, 0))
    ImageDraw.Draw(lay).rounded_rectangle([(xy[0] - 30) // 4, (xy[1] - 30) // 4, (xy[0] + w + 30) // 4, (xy[1] + h + 30) // 4], radius=20,
                                          fill=tuple(int(c * 0.55 * k) for c in col))
    lay = lay.filter(ImageFilter.GaussianBlur(14)).resize((W, H), Image.BILINEAR)
    im.paste(ImageChops.add(im, lay))

def shadow_paste(im, obj, xy, alpha=170):
    sh = Image.new("RGBA", (obj.width + 80, obj.height + 80), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([40, 50, obj.width + 40, obj.height + 40], radius=30, fill=(0, 0, 0, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(22))
    im.paste(sh, (xy[0] - 40, xy[1] - 40), sh)
    im.paste(obj, xy, obj)

def fade(obj, a):                                     # an RGBA object at alpha a
    if a >= 0.999: return obj
    o = obj.copy()
    o.putalpha(o.split()[3].point(lambda v: int(v * max(0.0, a))))
    return o

def bloom(im, k=0.5, r=6):                            # light spills: a blurred copy added (at a quarter size: cheap)
    if k <= 0.01: return im
    sm = im.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(r))
    sm = sm.point(lambda v: int(v * k)).resize((W, H), Image.BILINEAR)
    return ImageChops.add(im, sm)

def neon_lines(im, polys, col, width=4, glow=1.4):    # glowing lines (scopes): the core and its blurred light, added
    lay = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(lay)
    for pts in polys:
        if len(pts) > 1: d.line(pts, fill=col, width=width, joint="curve")
    sm = lay.resize((W // 2, H // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(7))
    sm = sm.point(lambda v: min(255, int(v * glow))).resize((W, H), Image.BILINEAR)
    core = lay.point(lambda v: min(255, v + (v > 0) * 60))
    im.paste(ImageChops.add(ImageChops.add(im, sm), core))

def ease(x): x = min(1.0, max(0.0, x)); return 1 - (1 - x) ** 3

def text(im, xy, s, f, col, a=1.0, anchor="la"):
    if a <= 0: return
    if a >= 0.999:
        ImageDraw.Draw(im).text(xy, s, font=f, fill=col, anchor=anchor); return
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).text(xy, s, font=f, fill=col + (int(255 * a),), anchor=anchor)
    im.paste(lay, (0, 0), lay)

# ---- the neon titles: the logo's serif, red glowing outlines (struck on like a tube)
sys.path.insert(0, str(HERE.parent / "tools"))
_argv, sys.argv = sys.argv, sys.argv[:1]          # (make_logo reads its own arguments on import)
import make_logo
sys.argv = _argv
WORDS = ["KICK", "ARP", "BASS", "SEQUENCER", "PAD", "LEAD", "RESO", "DOWN", "REVERB", "UPSIDE", "MORPH", "STRINGS", "ALL EIGHT"]
NEON = {}
for _wd in WORDS + ["OBERVAVE"]:
    _png = A / "f" / f"neon-{_wd.replace(' ', '_')}.png"
    if not _png.exists():
        _p, _w = make_logo.word_paths(make_logo.FONT, _wd, make_logo.CAP, make_logo.TRACK)
        make_logo.render(make_logo.logo_svg(_p, _w, background=False, bands=_wd == "OBERVAVE", pad=70), _png, int((_w + 140) * 0.9))
    NEON[_wd] = Image.open(_png).convert("RGBA")
_sub = make_logo.word_paths(make_logo.SUB_FONT, "8-VOICE ANALOG POLY  ·  M-VAVE FM-1", 22, 0.18)
LOGO = {}
for _name, _bands in (("letters", False), ("full", True)):
    _png = A / "f" / f"logo-{_name}.png"
    if not _png.exists():
        make_logo.render(make_logo.logo_svg(_lp := make_logo.word_paths(make_logo.FONT, make_logo.WORD, make_logo.CAP, make_logo.TRACK)[0],
                                            make_logo.word_paths(make_logo.FONT, make_logo.WORD, make_logo.CAP, make_logo.TRACK)[1],
                                            background=False, bands=_bands, sub=_sub), _png, 1500)
    LOGO[_name] = Image.open(_png).convert("RGBA")

@lru_cache(maxsize=64)
def neon(word, cap):                                  # the word with its cap height = cap px; (image, x offset of the letters)
    im = NEON[word]
    k = cap / (150 * 0.9)
    return im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS), int(70 * 0.9 * k)

FLICK = [0, 0.9, 0.15, 0, 0, 1.0, 0.45, 0.2, 1.0, 0.7, 1.0, 0.85, 1.0]
def flicker(n):                                       # frames since the title came: the tube fights, then holds (a dip now and then)
    if n < len(FLICK): return FLICK[n]
    return 0.82 if n % 37 == 0 else 1.0

def title(im, word, line, x, y, n, cap=110, kicker=None):
    img, ox = neon(word, cap)
    a = flicker(n)
    if a > 0:
        dx = np.random.RandomState(n).randint(-3, 4) if n < 9 else 0
        im.paste(fade(img, a), (x - ox + dx, y - int(img.height * 0.31)), fade(img, a))
    if kicker:
        text(im, (x + 4, y - 40), kicker.upper(), F_SEMI(26), BLUE, ease((n - 4) / 8))
    if line:
        yy = y + int(cap * 1.12)
        for i, ln in enumerate(line.split("\n")):
            text(im, (x + 4, yy + i * 46), ln, F_REG(34), CREAM, ease((n - 8 - 4 * i) / 10))

def keyboard(im, x0, y0, width, lit, col=(255, 120, 60)):
    d = ImageDraw.Draw(im)
    ww = width / 16; hh = ww * 3.2; bw = ww * 0.62; bh = hh * 0.6
    for k, black, i in KEYS:
        if black: continue
        on = (lit >> k) & 1
        x = x0 + i * ww
        d.rounded_rectangle([x + 2, y0 + (4 if on else 0), x + ww - 2, y0 + hh], radius=6, fill=col if on else (226, 222, 210))
    for k, black, i in KEYS:
        if not black: continue
        on = (lit >> k) & 1
        x = x0 + i * ww - bw / 2
        d.rounded_rectangle([x - 2, y0, x + bw + 2, y0 + bh + 2], radius=6, fill=(10, 10, 12))
        d.rounded_rectangle([x, y0 + (3 if on else 0), x + bw, y0 + bh], radius=5, fill=col if on else (30, 30, 34))
    return y0 + hh

def notes(im, x0, width, ykb, height, parts, fi, span=60, rising=False):
    """the notes as light: falling onto the keys (the next `span` frames), or rising off them (the last ones)"""
    lay = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(lay)
    hpf = height / span
    for p in parts:
        col = COL[p]
        rng = range(fi - span, fi + 1) if rising else range(fi, fi + span)
        bits = [LOG[p][max(0, min(g, NF - 1))][2] for g in rng]
        for k in range(27):
            xl, xr = lane(k, x0, width)
            run = None
            for j, b in enumerate(bits + [0]):
                on = (b >> k) & 1
                if on and run is None: run = j
                if not on and run is not None:
                    if rising: ya, yb = ykb - (len(bits) - run) * hpf, ykb - (len(bits) - j) * hpf
                    else: ya, yb = ykb - j * hpf, ykb - run * hpf
                    d.rounded_rectangle([xl + 1, ya + 1, xr - 1, yb - 1], radius=4, fill=col)
                    run = None
    sm = lay.resize((W // 2, H // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)
    im.paste(ImageChops.add(ImageChops.add(im, sm), lay.point(lambda v: int(v * 0.6))))

# ---- scopes from the stems (the film's time = the stem's time)
def window(p, fi, n, trigger=True, search=3000):
    s = int(fi / FPS * SR)
    a = np.asarray(STEM[p][max(0, s - n - search):s], dtype=np.float32) / 32768 / max(PEAK[p], 1e-4)
    if len(a) < n + 2: return np.zeros((n, 2), np.float32)
    if trigger:
        m = a.mean(1)
        z = np.nonzero((m[:-1] < 0) & (m[1:] >= 0))[0]
        z = z[z + n <= len(a)]
        i = z[-1] if len(z) else len(a) - n
        return a[i:i + n]
    return a[-n:]

def scope_line(p, fi, n, x0, x1, yc, amp, pts=900):
    y = window(p, fi, n).mean(1)
    idx = np.linspace(0, n - 1, pts).astype(int)
    return [(x0 + (x1 - x0) * j / (pts - 1), yc - amp * float(y[i])) for j, i in enumerate(idx)]

# ---- the lightning (the intro; the claps in the breakdown)
def bolt(im, seed, strength=1.0):
    lay = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = np.random.RandomState(seed)
    x, y, pts = rnd.randint(300, 1600), 0, []
    while y < H:
        pts.append((x, y)); x += rnd.randint(-90, 90); y += rnd.randint(40, 120)
    d.line(pts, fill=(150, 180, 255), width=9)
    d.line(pts, fill=(255, 255, 255), width=3)
    lay = lay.filter(ImageFilter.GaussianBlur(1.5)).point(lambda v: int(v * strength))
    im.paste(ImageChops.add(im, lay))

def tear(im, k):
    r, g, b = im.split()
    return Image.merge("RGB", (ImageChops.offset(r, int(12 * k), 0), g, ImageChops.offset(b, -int(12 * k), 0)))

# ---------------------------------------------------------------- the tape: the cassette, its look, the VCR's letters
def cassette(w, label, sub, sub_col=(200, 30, 36)):
    """a VHS cassette from above (RGBA): the body, the window with the two reels, a paper label written by hand"""
    h = int(w * 0.56)
    c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=int(w * 0.022), fill=(20, 20, 23, 255), outline=(52, 52, 58, 255), width=3)
    for y in range(int(h * 0.79), h - 10, 7):                                        # the grip's ribs
        d.line([(int(w * 0.05), y), (int(w * 0.95), y)], fill=(31, 31, 35, 255), width=2)
    for x in (int(w * 0.03), int(w * 0.97)):                                       # the screws
        d.ellipse([x - 7, h * 0.85 - 7, x + 7, h * 0.85 + 7], fill=(60, 60, 64, 255))
    wx0, wy0, wx1, wy1 = int(w * 0.22), int(h * 0.42), int(w * 0.78), int(h * 0.74)
    d.rounded_rectangle([wx0, wy0, wx1, wy1], radius=int(h * 0.05), fill=(34, 28, 27, 255), outline=(78, 78, 86, 255), width=3)
    cy = (wy0 + wy1) / 2
    for cx, rr in ((w * 0.335, h * 0.145), (w * 0.665, h * 0.095)):              # the reels: most of the tape still on the left
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(66, 44, 34, 255))
        hub = h * 0.068
        d.ellipse([cx - hub, cy - hub, cx + hub, cy + hub], fill=(226, 226, 220, 255))
        for k in range(6):
            a = k * math.pi / 3
            d.line([(cx + hub * 0.35 * math.cos(a), cy + hub * 0.35 * math.sin(a)), (cx + hub * 0.9 * math.cos(a), cy + hub * 0.9 * math.sin(a))],
                   fill=(130, 130, 130, 255), width=4)
        d.ellipse([cx - hub * 0.3, cy - hub * 0.3, cx + hub * 0.3, cy + hub * 0.3], fill=(26, 26, 26, 255))
    d.line([(w * 0.335 + h * 0.145, cy + h * 0.1), (w * 0.665 - h * 0.095, cy + h * 0.1)], fill=(52, 36, 28, 255), width=3)
    lx0, ly0, lx1, ly1 = int(w * 0.07), int(h * 0.06), int(w * 0.93), int(h * 0.36)
    lab = Image.new("RGBA", (lx1 - lx0, ly1 - ly0), (238, 232, 212, 255))           # the label: ruled paper, a red line on top
    dl = ImageDraw.Draw(lab)
    dl.rectangle([0, 0, lab.width, int(lab.height * 0.1)], fill=(196, 40, 40, 255))
    for y in range(int(lab.height * 0.36), lab.height, int(lab.height * 0.22)):
        dl.line([(8, y), (lab.width - 8, y)], fill=(150, 170, 210, 255), width=2)
    pen = Image.new("RGBA", lab.size, (0, 0, 0, 0))
    dp = ImageDraw.Draw(pen)
    dp.text((int(lab.width * 0.05), int(lab.height * 0.53)), label, font=F_MARK(lab.height * 0.42), fill=(24, 26, 60, 255), anchor="ls")
    dp.text((int(lab.width * 0.95), int(lab.height * 0.9)), sub, font=F_MARK(lab.height * 0.24), fill=sub_col + (255,), anchor="rs")
    pen = pen.rotate(1.6, Image.BICUBIC)
    lab.paste(pen, (0, 0), pen)
    c.paste(lab, (lx0, ly0))
    return c

_ROWS = np.arange(H)[:, None]
_COLS = np.arange(W)[None, :]
def vhs_look(im, f, amount=0.0, search=0.0):
    """the picture as a tape plays it: soft luma, the colour smeared to the right, rows that wobble, the head switching
    at the bottom, a tracking band crawling up; amount: the tape under stress, search: the noise bars of >>"""
    y, cb, cr = im.convert("YCbCr").split()
    y = y.resize((W * 2 // 3, H), Image.BILINEAR).resize((W, H), Image.BILINEAR)
    cb = ImageChops.offset(cb.resize((W // 7, H // 2), Image.BILINEAR).resize((W, H), Image.BILINEAR), 6, 0)
    cr = ImageChops.offset(cr.resize((W // 7, H // 2), Image.BILINEAR).resize((W, H), Image.BILINEAR), 6, 0)
    a = np.asarray(Image.merge("YCbCr", (y, cb, cr)).convert("RGB")).astype(np.int16)
    rnd = np.random.RandomState(f * 13 + 5)
    off = (1.0 + 7 * amount) * np.sin(np.arange(H) * 0.019 + f * 0.9) + rnd.randn(H // 6 + 1).repeat(6)[:H] * (0.4 + 4 * amount)
    hs = 18
    off[-hs:] += np.linspace(4, 34 + rnd.randint(0, 40), hs)                           # the head switching
    bands = [(int(H + 120 - (f * 5) % (H + 240)), 26, 0.22 + 0.7 * amount)]          # the tracking band, crawling up
    if search > 0:                                                                   # >>: two bars of noise running down
        for k in (0, 1):
            bands.append((int((f * 97 + k * H // 2) % (H + 120)) - 60, 70, 0.95 * search))
    for y0, bh, k in bands:
        y0, y1 = max(0, y0), min(H, y0 + bh)
        if y1 <= y0: continue
        off[y0:y1] += rnd.randint(-60, 60) * k
    off = np.round(off).astype(np.int32)
    a = a[_ROWS, (_COLS - off[:, None]) % W]
    for y0, bh, k in bands + [(H - hs, hs, 0.5)]:
        y0, y1 = max(0, y0), min(H, y0 + bh)
        if y1 <= y0: continue
        sn = rnd.randint(0, 255, (y1 - y0, W // 3, 1)).repeat(3, 1).astype(np.int16)
        line = (rnd.rand(y1 - y0, 1, 1) < 0.5)                                       # (white streaks, like the real thing)
        a[y0:y1] = a[y0:y1] * (1 - k * 0.6) + sn * k * (0.5 + 0.5 * line)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

def osd_text(im, xy, s, size=64, anchor="la", col=(255, 255, 255)):
    d = ImageDraw.Draw(im)
    f = F_OSD(size)
    d.text((xy[0] + 3, xy[1] + 3), s, font=f, fill=(0, 0, 0), anchor=anchor)
    d.text(xy, s, font=f, fill=col, anchor=anchor)

def osd_sym(im, x, y, sym, s=40):                    # the VCR's symbols, drawn (the font has none)
    d = ImageDraw.Draw(im)
    for dx, col in ((3, (0, 0, 0)), (0, (255, 255, 255))):
        X, Y = x + dx, y + dx
        if sym == "play": d.polygon([(X, Y), (X, Y + s), (X + s * 0.85, Y + s / 2)], fill=col)
        elif sym == "ff":
            for i in (0, 1): d.polygon([(X + i * s * 0.6, Y), (X + i * s * 0.6, Y + s), (X + i * s * 0.6 + s * 0.6, Y + s / 2)], fill=col)
        elif sym == "rew":
            for i in (0, 1): d.polygon([(X + s * 0.6 + i * s * 0.6, Y), (X + s * 0.6 + i * s * 0.6, Y + s), (X + i * s * 0.6, Y + s / 2)], fill=col)
        elif sym == "pause":
            for i in (0, 1): d.rectangle([X + i * s * 0.5, Y, X + i * s * 0.5 + s * 0.3, Y + s], fill=col)
        elif sym == "stop": d.rectangle([X, Y, X + s * 0.9, Y + s * 0.9], fill=col)
        elif sym == "eject":
            d.polygon([(X, Y + s * 0.6), (X + s * 0.9, Y + s * 0.6), (X + s * 0.45, Y)], fill=col)
            d.rectangle([X, Y + s * 0.75, X + s * 0.9, Y + s * 0.95], fill=col)

def osd(im, sym, label, right=None):
    """the VCR's own letters, crisp over the tape's picture: a symbol and a word top left, the chapter top right"""
    osd_sym(im, 70, 52, sym)
    osd_text(im, (70 + (90 if sym in ("ff", "rew") else 62), 46), label)
    if right: osd_text(im, (W - 70, 46), right, anchor="ra")

def camdate(im, t):                                  # the camcorder's date, burned into the picture (the tape smears it too)
    m = 47 + int(t // 60)
    osd_text(im, (W - 80, H - 46), f"PM 11:{m:02d}  OCT.16 1983", 50, "rs", (255, 238, 205))

# ---------------------------------------------------------------- the scenes (t: seconds into the scene, n: its frames, fi: the films' frame)
LOGO_XY = ((W - LOGO["full"].width) // 2, (H - LOGO["full"].height) // 2 - 20)
STRIKE = {10: (0.12, 0), 11: (0.0, 0), 17: (1.0, 0.9), 18: (0.35, 0.2), 19: (0.0, 0), 26: (1.0, 1.0), 27: (1.0, 0.4), 28: (0.15, 0),
          29: (0.0, 0), 34: (0.6, 0.3), 35: (0.2, 0), 36: (0.75, 0), 37: (0.5, 0), 38: (0.85, 0), 39: (0.6, 0), 40: (0.95, 0.5),
          41: (0.8, 0), 42: (1.0, 0), 43: (0.9, 0), 44: (1.0, 0)}
WORDS_OPEN = [(2.2, "EIGHT FM-1s."), (2.6, "ONE FIRMWARE."), (3.0, "ZERO SAMPLES."), (3.4, "LIGHTS OFF.")]
IN, LOGO_OUT = 40, 160                                # the cassette's frames; the logo leaves into the screen there
TAPE = cassette(1100, "OBERVAVE", "DO NOT ERASE!")

def s_open(t, n, fi, b):
    if n < IN:                                        # the cassette, its label in the lamp's light, then into the slot
        im = BGIMG.copy()
        fog(im, t, 0.5, (120, 100, 80))
        z = 1.0 + 0.05 * n / IN
        u = max(0.0, (n - 24) / (IN - 24))
        c = TAPE.resize((int(TAPE.width * z * (1 - 0.25 * u)), int(TAPE.height * z * (1 - 0.25 * u))), Image.BILINEAR)
        x, y = (W - c.width) // 2, (H - c.height) // 2 - 30 + int(1300 * u * u)
        halo(im, c, (x, y), (255, 190, 120), 0.5)
        shadow_paste(im, c, (x, y), 200)
        return im
    n -= IN
    if n < LOGO_OUT - IN:                             # the logo strikes: flashes, a flicker, the bands sweep in
        if n < 10:                                    # (the tape starts: snow, then the picture)
            sn = np.random.RandomState(n).randint(0, 200, (H // 3, W // 3, 1)).repeat(3, 0).repeat(3, 1).repeat(3, 2)
            return Image.fromarray(sn.astype(np.uint8))
        k, flash = STRIKE.get(n, (0.0, 0.0) if n < 44 else (1.0, 0.0))
        if n >= 44 and n % 23 == 0: k = 0.86
        im = BGIMG.copy()
        if flash > 0:
            im = Image.blend(im, Image.new("RGB", (W, H), (62, 80, 124)), flash)
        if flash > 0.5: bolt(im, n)
        if k > 0:
            u = max(0.0, min(1.0, (n - 60) / 24))
            logo = LOGO["letters"].copy()
            xt = int(logo.width * u * u)
            if xt: logo.paste(LOGO["full"].crop((0, 0, xt, logo.height)), (0, 0))
            z = 1.0 + 0.04 * max(0, n - 44) / 76                                 # it comes slowly closer
            if z > 1: logo = logo.resize((int(logo.width * z), int(logo.height * z)), Image.BILINEAR)
            dx = np.random.RandomState(n).randint(-3, 4) if k < 0.9 else 0
            im.paste(fade(logo, k), ((W - logo.width) // 2 + dx, (H - logo.height) // 2 - 20), fade(logo, k))
        if n > LOGO_OUT - IN - 20:                    # and it goes, into the screen
            im = Image.blend(im, BGIMG, (n - (LOGO_OUT - IN - 20)) / 20)
        im = bloom(im, 0.35)
        return tear(im, flash) if flash > 0.6 else im
    # a macro of the arp's screen, drifting across its pixels; the words punched in on the half bars
    u = (t - LOGO_OUT / FPS) / (4 * BAR - LOGO_OUT / FPS)
    sc = 6.5
    s = scanlines(screen_raw("arp", fi).resize((int(240 * sc), int(240 * sc)), Image.NEAREST), 4)
    ox, oy = int(-80 - u * (s.width - W - 160)), int(-120 - u * 380)
    im = BGIMG.copy()
    im.paste(s, (ox, oy))
    im = Image.blend(BGIMG, im, 0.42 + 0.1 * math.sin(t * 3))
    cur = [w for w in WORDS_OPEN if w[0] <= b]
    if cur:
        tb, wd = cur[-1]
        k = ease((b - tb) * BAR / 0.18)
        f = F_BLACK(int(170 * (1.12 - 0.12 * k)))
        lay = Image.new("RGB", (W, H), (0, 0, 0))
        ImageDraw.Draw(lay).text((W // 2, H // 2), wd, font=f, fill=(255, 255, 255), anchor="mm")
        glow = lay.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(8)).resize((W, H), Image.BILINEAR)
        glow = Image.merge("RGB", (glow.split()[0], glow.split()[1].point(lambda v: v // 4), glow.split()[2].point(lambda v: v // 4)))
        im = ImageChops.add(ImageChops.add(im, glow), lay)
        if k < 0.6: im = tear(im, 1 - k)
    text(im, (W // 2, H - 90), "D PHRYGIAN  ·  94 BPM  ·  ONE SLOW DARK TRACK", F_SEMI(26), DIM, ease((b - 2.0) * 2), "mm")
    return im

def last_hit(p, fi, n):                              # the last hit's waveform, from its onset (a kick is over before a frame's window)
    s = int(fi / FPS * SR)
    look = int(SR * BEAT * 1.2)
    a = np.asarray(STEM[p][max(0, s - look):s], dtype=np.float32).mean(1) / 32768 / max(PEAK[p], 1e-4)
    idx = np.nonzero(np.abs(a) > 0.2)[0]
    if not len(idx): return None, 0
    j = len(idx) - 1
    while j > 0 and idx[j] - idx[j - 1] < 1500: j -= 1
    o = max(0, s - look) + idx[j] - 60
    w = np.asarray(STEM[p][o:o + n], dtype=np.float32).mean(1) / 32768 / max(PEAK[p], 1e-4)
    return w, (s - o) / SR

def s_kick(t, n, fi, b):
    im = BGIMG.copy()
    kk = float(ENV["kick"][fi])
    w, age = last_hit("kick", fi, 5200)
    if w is not None and len(w) > 10:
        k = math.exp(-age / 0.35)
        idx = np.linspace(0, len(w) - 1, 1000).astype(int)
        pts = [(W * j / 999, 560 - 330 * float(w[i])) for j, i in enumerate(idx)]
        neon_lines(im, [pts], tuple(int(c * (0.35 + 0.65 * k)) for c in (255, 60, 44)), 5, 1.0 + 1.2 * k)
        text(im, (W - 90, 760), "one hit, 120 ms: the pitch falls as the wave widens", F_REG(26), DIM, 1.0, "ra")
    dv = device("drums", fi, 1.5, kk, COL["kick"])
    shadow_paste(im, dv, (W - dv.width - 90, 90))
    title(im, "KICK", "is a filter at full resonance, ringing like a sine.\nIts envelope drops the pitch. No drum machine.", 110, 820, n)
    return im

ECHO = int(round(0.75 * BEAT * FPS))                  # the delay: a dotted eighth, in frames
def s_arp(t, n, fi, b):
    im = BGIMG.copy()
    lv = float(ENV["arp"][fi])
    cx, y = W // 2, 70
    for k in (4, 3, 2, 1):                            # the echoes: the screen as it was k dotted eighths ago, ping-pong
        sc = 2.5 * 0.86 ** k
        dv = device("arp", fi - k * ECHO, sc, 0, COL["arp"])
        side = -1 if k % 2 else 1
        x = cx + side * (330 + 150 * (k - 1)) - dv.width // 2
        yy = y + (device("arp", fi, 2.5).height - dv.height) // 2
        g = Image.new("RGBA", dv.size, (255, 60, 40, 0) if side < 0 else (60, 120, 255, 0))
        ech = Image.blend(dv, Image.merge("RGBA", (*g.split()[:3], dv.split()[3])), 0.35)
        im.paste(fade(ech, 0.62 * 0.7 ** (k - 1)), (x, yy), fade(ech, 0.62 * 0.7 ** (k - 1)))
    dv = device("arp", fi, 2.5, lv, COL["arp"])
    halo(im, dv, (cx - dv.width // 2, y), COL["arp"], lv)
    shadow_paste(im, dv, (cx - dv.width // 2, y))
    title(im, "ARP", "A four-note chord, climbed in 16ths. The ghosts are its delay:\na dotted eighth, ping-pong, left, right, left.", 110, 790, n, cap=100, kicker="program 01 · DARK ARP")
    return im

def s_bass(t, n, fi, b):
    im = BGIMG.copy()
    lv = float(ENV["bass"][fi])
    neon_lines(im, [scope_line("bass", fi, 4200, 0, W, 640, 260)], COL["bass"], 6, 1.5 + lv)
    dv = device("bass", fi, 1.5, lv, COL["bass"])
    shadow_paste(im, dv, (W - dv.width - 90, 70))
    title(im, "BASS", "A saw and a pulse an octave below it, drive, glide.\nRoot, octave, root, octave. The filter stays shut.", 110, 160, n, kicker="program 07 · FAT BASS")
    return im

PROG0, PROG1 = int(3.65 * FPS), int(8.75 * FPS)       # the drums' film: the kick set by hand, ALGORITHM, then the hats
def vhs(im, n, amount):                               # tracking noise: bands of rows slipping, a little snow
    a = np.asarray(im).copy()
    rnd = np.random.RandomState(n * 7 + 1)
    for _ in range(int(3 + 6 * amount)):
        y0 = rnd.randint(0, H - 40); h = rnd.randint(4, 40)
        a[y0:y0 + h] = np.roll(a[y0:y0 + h], rnd.randint(-80, 80) * amount, axis=1)
    snow = rnd.randint(0, 255, (H // 4, W // 4, 1)).repeat(4, 0).repeat(4, 1)
    a = np.clip(a.astype(np.int16) + ((snow - 128) * 0.25 * amount).astype(np.int16), 0, 255).astype(np.uint8)
    return Image.fromarray(a)

OSD = {}                                              # what a scene asks of the VCR's letters this frame (drawn after the tape's look)
def s_seq(t, n, fi, b):
    im = BGIMG.copy()
    REW, PLAY = 0.7, 2.2
    if t < REW + PLAY:                                # the tape: rewind to the setting of the steps, then play it fast
        spd = (PROG1 - PROG0) / (PLAY * FPS)
        if t < REW:
            src = int(fi + (PROG0 - fi) * ease(t / REW))
            amount = 1.0
        else:
            src = int(PROG0 + (t - REW) * FPS * spd)
            amount = 0.25
        dv = device("drums", src, 2.4)
        x = (W - dv.width) // 2 - 260
        shadow_paste(im, dv, (x, 120))
        keys = LOG["drums"][max(0, min(src, NF - 1))][1]
        keyboard(im, x, 120 + dv.height + 26, dv.width, keys, COL["drums"])
        on_b = src * 1000 / FPS > 5303                # (song.py: ALGORITHM to track B once the kick is set)
        text(im, (x + dv.width + 70, 300), "KICK" if not on_b else "HATS", F_BLACK(72), TRK_B if on_b else TRK_A, 1.0)
        text(im, (x + dv.width + 70, 390), "track A" if not on_b else "track B, its own sound", F_SEMI(32), CREAM, 1.0)
        im = vhs(im, n, amount)
        OSD.update(sym="rew" if t < REW else "play", label="REW" if t < REW else f"PLAY x{spd:.0f}", stress=amount)
        if t >= REW:
            text(im, (W // 2 - 140, H - 150), "SEQ held · a key per step · ALGORITHM: track B", F_OSD(46), (255, 255, 255), 1.0, "mm")
        return im
    # live: the TRACKS view, huge (the screen's own pixels): kick on A, hats on B, the playheads running
    n2 = n - int((REW + PLAY) * FPS)
    s = screen_raw("drums", fi).crop((0, 24, 240, 168))
    s = scanlines(s.resize((s.width * 4, s.height * 4), Image.NEAREST), 4)
    lay = Image.new("RGB", (W, H), (0, 0, 0))
    lay.paste(s, (110, 330))
    lv = max(float(ENV["kick"][fi]), 0.6 * float(ENV["hat"][fi]))
    im.paste(ImageChops.add(im, bloom(lay, 0.35 + 0.5 * lv, 5)))
    for y, lab, c, p in ((330 + 8, "KICK", TRK_A, "kick"), (330 + 296, "HATS", TRK_B, "hat")):
        k = float(ENV[p][fi])
        text(im, (110 + 960 + 40, y + 70), lab, F_BLACK(56), tuple(int(v * (0.55 + 0.45 * k)) for v in c), 1.0)
    title(im, "SEQUENCER", None, 110, 100, n2, cap=90)
    for i, ln in enumerate(("New in 1.4: track B plays a sound", "of its own. Kick on A, hats on B:",
                            "one FM-1, two sounds, two arps,", "the tracks one under the other.")):
        text(im, (1290, 330 + 140 + 46 * i), ln, F_REG(34), CREAM, ease((n2 - 6 - 4 * i) / 10))
    return im

def s_pad(t, n, fi, b):
    im = BGIMG.copy()
    lv = float(ENV["pad"][fi])
    depth = 4 + 14 * ease(t / (3 * BAR)) * (0.6 + 0.4 * math.sin(t * 2.2))
    dv = device("pad", fi, 2.2, lv, COL["pad"])
    x, y = 110, 120
    halo(im, dv, (x, y), COL["pad"], lv)
    r, g, bb, a = dv.split()                          # the chorus: two voices of the same picture, a little apart
    dl = Image.merge("RGBA", (ImageChops.offset(r, int(depth), 0), g, ImageChops.offset(bb, -int(depth), int(depth * 0.3)), a))
    shadow_paste(im, dl, (x, y))
    kx, kw, ky = 1120, 700, 860
    notes(im, kx, kw, ky, 640, ["pad", "arp"], fi)
    keyboard(im, kx, ky, kw, LOG["pad"][fi][2] | LOG["arp"][fi][2], (255, 120, 90))
    text(im, (kx, 150), "● ARP", F_SEMI(26), COL["arp"]); text(im, (kx + 150, 150), "● PAD", F_SEMI(26), COL["pad"])
    title(im, "PAD", "Pulse waves, every voice its own LFO phase.\nThe chorus doubles the picture,\nas it doubles the sound.", 110, 760, n, cap=90, kicker="program 29 · NEON PAD")
    return im

def s_lead(t, n, fi, b):
    im = BGIMG.copy()
    lv = float(ENV["lead"][fi])
    bd = bend_at(fi)
    dv = device("lead", fi, 2.4, lv, COL["lead"])
    cx, cy = W // 2 + 220, 420 - int(bd * 260)
    ghosts = []
    for i in range(5):                                # six voices, apart: five ghosts drifting at their own slow rates
        ph = t * (0.35 + 0.13 * i) + i * 1.7
        gx = int(math.sin(ph) * (60 + 22 * i)); gy = int(math.cos(ph * 0.8) * (18 + 6 * i))
        rot = math.sin(ph * 0.6) * 3.0
        gimg = dv.rotate(rot, Image.BILINEAR, expand=True)
        ghosts.append((gimg, gx, gy))
    for gimg, gx, gy in ghosts:
        r_, g_, b_, a_ = gimg.split()
        gimg = Image.merge("RGBA", (r_, g_.point(lambda v: v // 2), b_, a_)) if i % 2 else Image.merge("RGBA", (r_.point(lambda v: v // 2), g_, b_, a_))
        im.paste(fade(gimg, 0.3), (cx - gimg.width // 2 + gx, cy - gimg.height // 2 + gy), fade(gimg, 0.3))
    if bd < -0.02:                                    # the dive: the picture smears downward
        for j in range(1, 6):
            o = fade(dv, 0.12 * -bd)
            im.paste(o, (cx - dv.width // 2, cy - dv.height // 2 - int(j * 40 * -bd)), o)
    halo(im, dv, (cx - dv.width // 2, cy - dv.height // 2), COL["lead"], lv)
    shadow_paste(im, dv, (cx - dv.width // 2, cy - dv.height // 2))
    title(im, "LEAD", "Six voices in unison,\nVINTAGE all the way up:\nthey drift. BEND: an octave,\ndown the hole.", 110, 300, n, cap=100, kicker="program 04 · UNISON LD")
    if bd < -0.02:
        k = -bd
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(lay).rectangle([0, int(H * (1 - 0.5 * k)), W, H], fill=(0, 0, 0, int(200 * k)))
        im.paste(lay, (0, 0), lay.filter(ImageFilter.GaussianBlur(60)))
    return im

def s_reso(t, n, fi, b):
    im = BGIMG.copy()
    lv = float(ENV["bass"][fi])
    y = window("bass", fi, 2600).mean(1)
    cx, cy, R = W // 2 + 300, H // 2, 250
    rot = t * 0.6
    idx = np.linspace(0, len(y) - 1, 720).astype(int)
    pts = [(cx + (R + 230 * float(y[i])) * math.cos(rot + 2 * math.pi * j / 719), cy + (R + 230 * float(y[i])) * math.sin(rot + 2 * math.pi * j / 719)) for j, i in enumerate(idx)]
    neon_lines(im, [pts], COL["bass"], 5, 1.5 + lv)
    dv = device("bass", fi, 1.5, lv, COL["bass"])
    shadow_paste(im, dv, (110, 70))
    title(im, "RESO", "climbs on knob 1 of the FILTER page:\nthe bass starts to whistle. Its waveform,\nwrapped round a circle, grows spikes.", 110, 650, n, cap=90)
    return im

def tunnel(im, part, fi, cx, cy, depth, spin, glow, col, layers=8, front=4.2):
    """screens inside screens: the biggest in front, each next one 0.7 of it, all growing with depth (falling in)"""
    fr = depth % 1.0
    for j in range(layers):
        sc = front * 0.7 ** (j - fr)
        if sc * 256 > 2.6 * W or sc < 0.08: continue
        dv = device(part, fi - j * 2, sc, glow if j == 2 else 0, col)
        k = min(1.0, 0.35 + 0.22 * j) * (1 - 0.06 * j)                   # the ones in front dim (out of focus)
        if k < 1: dv = Image.merge("RGBA", (*[c.point(lambda v, k=k: int(v * k)) for c in dv.split()[:3]], dv.split()[3]))
        dv = dv.rotate(spin * (j - fr), Image.BILINEAR, expand=True)
        im.paste(dv, (cx - dv.width // 2, cy - dv.height // 2), dv)

def s_down(t, n, fi, b):
    im = BGIMG.copy()
    bd = bend_at(fi)
    depth = t * 0.35 + sum(-bend_at(g) for g in range(fi - n, fi + 1)) / FPS * 1.6   # it falls faster while the pitch falls
    tunnel(im, "lead", fi, W // 2 + 200, H // 2, depth, -bd * 6 + math.sin(t * 0.7) * 2, float(ENV["lead"][fi]), COL["lead"])
    title(im, "DOWN", "The bend comes over MIDI:\nthe whole stack slides\nan octave down. The echoes\nfollow, in time.", 110, 640, n, cap=90)
    return im

FOG = [(np.random.RandomState(i).rand(5)) for i in range(70)]
def fog(im, t, k, col=(90, 120, 200)):
    lay = Image.new("RGB", (W // 4, H // 4), (0, 0, 0))
    d = ImageDraw.Draw(lay)
    for x, y, r, sp, ph in FOG:
        px = (x * W / 4 + t * (6 + 10 * sp)) % (W / 4); py = (y * H / 4 - t * (3 + 5 * sp)) % (H / 4)
        rr = 10 + 30 * r
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=tuple(int(c * (0.25 + 0.2 * math.sin(t + ph * 6))) for c in col))
    lay = lay.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * k)).resize((W, H), Image.BILINEAR)
    im.paste(ImageChops.add(im, lay))

def s_reverb(t, n, fi, b):
    im = BGIMG.copy()
    u = t / (4 * BAR)
    fog(im, t, 0.4 + 1.6 * u)
    for p, x, sc in (("pad", 1080, 1.9), ("arp", 150, 2.6)):
        lv = float(ENV[p][fi])
        dv = device(p, fi, sc, lv, COL[p])
        y = 110 if p == "arp" else 300
        halo(im, dv, (x, y), COL[p], lv)
        shadow_paste(im, dv, (x, y))
    title(im, "REVERB", "Drums out. The arp's filter opens all the way\nwhile its plate MIX goes up on the knob.", 1080, 110, n, cap=80, kicker="breakdown")
    im = bloom(im, 0.3 + 0.9 * u, 6 + 6 * u)
    cl = float(ENV["clap"][fi])
    if cl > 0.55 and float(ENV["clap"][fi - 1]) <= 0.55: bolt(im, fi, 1.0)
    return im

def s_upside(t, n, fi, b):
    im = BGIMG.copy()
    lv = float(ENV["arp2"][fi])
    kx, kw, ky = 860, 960, 830
    notes(im, kx, kw, ky, 700, ["arp2"], fi, span=45, rising=True)
    keyboard(im, kx, ky, kw, LOG["arp2"][fi][2], COL["arp2"])
    dv = device("arp2", fi, 1.9, lv, COL["arp2"])
    halo(im, dv, (110, 110), COL["arp2"], lv)
    shadow_paste(im, dv, (110, 110))
    title(im, "UPSIDE", "A second arp, up and down over two octaves\nabove the chord, through the 12 dB SEM-style\nfilter. Its notes rise off the keys.", 110, 700, n, cap=90, kicker="the drop · program 26")
    if t < 0.25: im = Image.blend(im, Image.new("RGB", (W, H), (255, 255, 255)), 0.8 * (1 - t / 0.25))
    return im

def s_morph(t, n, fi, b):
    im = BGIMG.copy()
    u = ease(t / (2 * BAR))
    for p, x in (("arp2", 110), ("arp", 1000)):
        lv = float(ENV[p][fi])
        dv = device(p, fi, 2.6 if p == "arp2" else 1.6, lv, COL[p])
        y = 110 if p == "arp2" else 140
        if p == "arp2":                               # the notch: a band cut out of the middle, widening
            a = np.asarray(dv).copy()
            hh = a.shape[0]
            c, w = int(hh * 0.52), int(6 + 150 * u)
            a[c - w // 2:c + w // 2, :, :3] = (a[c - w // 2:c + w // 2, :, :3] * 0.12).astype(np.uint8)
            dv = Image.fromarray(a)
            halo(im, dv, (x, y), COL[p], lv)
        shadow_paste(im, dv, (x, y))
    title(im, "MORPH", "Knob 4 on FILTER + turns the SEM filter\nfrom lowpass toward the notch: the second\narp hollows out. The first keeps climbing.", 1000, 640, n, cap=90)
    return im

def s_strings(t, n, fi, b):
    im = BGIMG.copy()
    lv = float(ENV["strings"][fi])
    a = window("strings", fi, 1800, trigger=False)
    cx, cy, sc = W // 2 + 380, H // 2 - 10, 560
    pts = [(cx + sc * 0.75 * float(l - r), cy - sc * 0.75 * float(l + r)) for l, r in a[::2]]
    d = ImageDraw.Draw(im)
    d.line([(cx - 420, cy), (cx + 420, cy)], fill=(30, 36, 56), width=1)
    d.line([(cx, cy - 420), (cx, cy + 420)], fill=(30, 36, 56), width=1)
    text(im, (cx - 430, cy - 30), "L", F_VHS(30), DIM); text(im, (cx + 410, cy - 30), "R", F_VHS(30), DIM)
    neon_lines(im, [pts], COL["strings"], 2, 1.8 + lv)
    dv = device("strings", fi, 1.5, lv, COL["strings"])
    shadow_paste(im, dv, (110, 70))
    title(im, "STRINGS", "PWM, every voice its own LFO phase,\npanned across the field. That figure\nis their stereo width, live.", 110, 650, n, cap=90, kicker="program 05 · PWM STRINGS")
    return im

GRID = ["arp", "bass", "pad", "lead", "arp2", "strings", "drums", "clap"]   # 4 x 2
FALL = {"drums": 38.0, "clap": 38.05, "arp2": 38.3, "bass": 38.5, "arp": 38.7, "strings": 39.4, "pad": 39.6}
def s_all(t, n, fi, b):
    im = BGIMG.copy()
    z = 1.0 + 0.06 * min(1.0, (b - 34) / 4)
    tile = int(370 * z)
    gx0, gy0 = W // 2 - int(2 * tile + 45 * z), H // 2 - int(tile + 15 * z) - 30
    dvs = []
    for i, p in enumerate(GRID):
        lv = float(ENV[p][fi])
        x, y = gx0 + (i % 4) * int(tile + 30 * z), gy0 + (i // 4) * int(tile + 30 * z)
        if b >= 38:                                   # the last fall: one by one they drop away
            tf = FALL.get(p)
            if tf is not None and b > tf:
                dt = (b - tf) * BAR
                y += int(0.5 * 2600 * dt * dt)
            if p == "lead":                           # the lead moves to the middle and falls into its tunnel
                u = ease((b - 38) / 1.2)
                x = int(x + (W // 2 - tile // 2 - x) * u); y = int(y + (H // 2 - tile // 2 - 40 - y) * u)
        if y > H: continue
        dv = device(p, fi, tile / 256, lv, COL[p])
        halo(im, dv, (x, y), COL[p], lv * 0.8)
        dvs.append((dv, x, y, p))
    for dv, x, y, p in dvs:
        if p != "lead": shadow_paste(im, dv, (x, y))
    for dv, x, y, p in dvs:
        if p == "lead":
            if b >= 39.2:
                tunnel(im, "lead", fi, x + dv.width // 2, y + dv.height // 2, (b - 39.2) * 1.6, -bend_at(fi) * 8, float(ENV["lead"][fi]), COL["lead"],
                       front=1.2 * 0.7 ** -min(2.0, (b - 39.2) * 2.5))
            else:
                shadow_paste(im, dv, (x, y))
    if b < 36:
        k = flicker(n)
        img, ox = neon("ALL EIGHT", 120)
        lay = Image.new("RGB", (W, H), (0, 0, 0))
        lay.paste(img, ((W - img.width) // 2, H // 2 - img.height // 2), img)
        a = k * (1 - ease((b - 35.2) / 0.8))
        im = Image.blend(im, ImageChops.lighter(Image.blend(im, Image.new("RGB", (W, H), BG), 0.55), lay), max(0.0, a))
    if 36 <= b < 38:
        text(im, (W // 2, H - 50), "8 FM-1s  ·  1 FIRMWARE  ·  0 SAMPLES", F_SEMI(32), CREAM, ease((b - 36) * 2), "mm")
    return im

STOP_T, ROLL_T = 0.8, 1.0                              # the end: the blue screen, then the card rolls in
END_TAPE = cassette(820, "OBERVAVE 1.4.1", "thefirmwarehub.com", (40, 90, 200))
def s_end(t, n, fi, b):
    if t < STOP_T:                                    # the tape stops: the recorder's blue, STOP
        OSD.update(sym="stop", label="STOP", clean=True)
        return Image.new("RGB", (W, H), (16, 32, 170))
    t2, n2 = t - STOP_T, n - int(STOP_T * FPS)
    im = BGIMG.copy()
    fog(im, t + 40, 0.8)
    c = END_TAPE.rotate(-7, Image.BICUBIC, expand=True)   # the left half: the cassette (YouTube's end screen lies over it)
    cx, cy = 110 + int(14 * math.sin(t * 0.8)), 330 + int(10 * math.sin(t * 0.6))
    halo(im, c, (cx, cy), (255, 190, 120), 0.35)
    shadow_paste(im, c, (cx, cy), 200)
    x = 1010                                          # the right half: the logo, the hub, like & subscribe
    logo = LOGO["full"]
    sc = 0.56
    lg = logo.resize((int(logo.width * sc), int(logo.height * sc)), Image.LANCZOS)
    a = flicker(n2)
    im.paste(fade(lg, a), (x - 90, 40), fade(lg, a))
    text(im, (x, 360), "Free firmware for the M-VAVE FM-1.", F_LIGHT(38), CREAM, ease((n2 - 10) / 12))
    text(im, (x, 408), "Install it in a minute:", F_LIGHT(38), CREAM, ease((n2 - 12) / 12))
    text(im, (x, 466), "thefirmwarehub.com", F_BLACK(76), BLUE, ease((n2 - 14) / 12))
    text(im, (x, 586), "Please always check the latest firmware version!", F_SEMI(30), (230, 209, 185), ease((n2 - 24) / 12))
    a2 = ease((n2 - 34) / 12)
    if a2 > 0:
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        dl = ImageDraw.Draw(lay)
        dl.rounded_rectangle([x, 660, x + 520, 740], radius=40, outline=(255, 70, 60, int(255 * a2)), width=3)
        dl.text((x + 260, 700), "Like & subscribe", font=F_BOLD(44), fill=CREAM + (int(255 * a2),), anchor="mm")
        dl.text((x + 560, 700), "@sonzven", font=F_SEMI(40), fill=(255, 110, 80, int(255 * a2)), anchor="lm")
        im.paste(lay, (0, 0), lay)
    y = 800
    for ln in ("OberVave 1.4.1: free firmware, GPL-3.0. Built on Dinghy,",
               "SLOOP 2.3 (isod89) and Felucca (Hügelton Instruments).",
               "Inspired by the classic 8-voice poly synths of 1979-84",
               "(trademarks of their owners, no affiliation).",
               "Every sound: OberVave on the FM-1, eight of them. No samples were harmed."):
        text(im, (x, y), ln, F_REG(22), DIM, ease((n2 - 44) / 12)); y += 32
    im = bloom(im, 0.25)
    if t2 < ROLL_T:                                   # the picture rolls until the recorder finds its sync
        u = 1 - ease(t2 / ROLL_T)
        roll = int((H + 40) * 1.6 * u) % (H + 40)
        lay = Image.new("RGB", (W, H + 40), (0, 0, 0))
        lay.paste(im, (0, 0))
        lay = ImageChops.offset(lay, 0, roll)
        im = lay.crop((0, 0, W, H))
        OSD.update(stress=0.9 * u)
    if total_frames - (n + int(b0_end * BAR * FPS)) < 50:
        OSD.update(sym="eject", label="EJECT")
    else:
        OSD.update(sym="play", label="PLAY", hide=t2 > 3.0)
    return im

SCENES = [(0, 4, s_open), (4, 8, s_arp), (8, 12, s_bass), (12, 16, s_pad), (16, 20, s_lead),     # the first minute: no drums
          (20, 22, s_reso), (22, 24, s_down), (24, 25, s_kick), (25, 28, s_seq), (28, 30, s_upside), (30, 32, s_morph),
          (32, 34, s_strings), (34, 40, s_all), (40, 99, s_end)]
END_BAR = b0_end = 40
PAUSE = 27.5
NAMES = {"kick": "KICK", "arp": "ARP", "bass": "BASS", "seq": "SEQUENCER", "pad": "PAD", "lead": "LEAD", "reso": "RESO",
         "down": "DOWN", "reverb": "REVERB", "upside": "UPSIDE", "morph": "MORPH", "strings": "STRINGS", "all": "ALL EIGHT"}
CHAPTER = {int(round(b0 * BAR * FPS)): f"CH {i + 1:02d}  {NAMES[fn.__name__[2:]]}" for i, (b0, _, fn) in enumerate(SCENES[1:-1])}
total_frames = min(NF - F0, int(((END_BAR + 4) * BAR + 3.0) * FPS))
CUTS = sorted(CHAPTER) + [LOGO_OUT]

def frame(f):
    t = f / FPS
    b = t / BAR
    fi = F0 + f
    for b0, b1, fn in SCENES:
        if b0 <= b < b1: break
    f0 = int(round(b0 * BAR * FPS))
    OSD.clear()
    if PAUSE <= b < 28:                               # before the drop the tape pauses: the picture freezes and shakes
        fp = int(PAUSE * BAR * FPS)
        im = fn(fp / FPS - b0 * BAR, fp - f0, F0 + fp, PAUSE)
        im = ImageChops.offset(im, 0, int(np.random.RandomState(f).randint(-6, 7)))
        OSD.update(sym="pause", label="PAUSE", stress=0.55)
    else:
        im = fn(t - b0 * BAR, f - f0, fi, b)
    kick = float(ENV["kick"][min(fi, NF - 1)]) if 4 <= b < 38 else 0.0
    clap = float(ENV["clap"][min(fi, NF - 1)]) if 8 <= b < 40 else 0.0
    if kick > 0.05:                                   # the kick pushes the whole picture toward you
        z = 1 + 0.022 * kick
        big = im.resize((int(W * z), int(H * z)), Image.BILINEAR)
        im = big.crop(((big.width - W) // 2, (big.height - H) // 2, (big.width - W) // 2 + W, (big.height - H) // 2 + H))
    if clap > 0.2:
        im = Image.blend(im, Image.new("RGB", (W, H), (60, 80, 130)), 0.28 * clap)
    sc = min((f - c for c in CUTS if c <= f), default=99)
    search = max(0.0, 1 - sc / 6) if sc < 6 else 0.0  # the cut: a search through the tape, the noise bars running
    if sc < 3: im = tear(im, 1 - sc / 3)
    stress = OSD.get("stress", 0.0) + (max(0.0, -bend_at(fi)) * 0.5 if 16 <= b < 40 else 0.0)   # the bend stretches the tape
    if f >= LOGO_OUT and b < 40: camdate(im, t)
    if b < 40 and f >= IN: stress += max(0.0, 1 - (f - IN) / 40) * 0.8     # (the tape finds its track after PLAY)
    if not OSD.get("clean") and f >= IN:
        im = vhs_look(im, f, min(1.0, stress), search)
    # the VCR's letters
    chap = max((c for c in CHAPTER if c <= f), default=None)
    if "sym" in OSD:
        if not OSD.get("hide"): osd(im, OSD["sym"], OSD["label"])
    elif IN <= f < IN + 90:
        osd(im, "play", "PLAY")
    elif chap is not None and f - chap < 6:
        osd(im, "ff", "", CHAPTER[chap])
    elif chap is not None and f - chap < 60:
        osd(im, "play", "PLAY", CHAPTER[chap])
    a = np.asarray(im, dtype=np.float32) * VIG + GRAIN[f % 6]
    k = min(1.0, (total_frames - f) / FPS / 1.5)
    if k < 1: a *= max(0.0, k)
    return np.clip(a, 0, 255).astype(np.uint8).tobytes()

if __name__ == "__main__":
    if "--thumb" in sys.argv:                        # the thumbnail: the cassette, the dark arp's screen, the logo, PLAY
        OSD.clear()
        im = BGIMG.copy()
        fog(im, 3.0, 1.0)
        fi = F0 + int(6 * BAR * FPS)
        dv = device("arp", fi, 2.9, 1.0, COL["arp"])
        halo(im, dv, (1060, 300), COL["arp"], 1.0)
        shadow_paste(im, dv, (1060, 300))
        c = cassette(1000, "OBERVAVE", "DO NOT ERASE!").rotate(8, Image.BICUBIC, expand=True)
        shadow_paste(im, c, (40, 420), 220)
        lg = LOGO["full"].resize((int(LOGO["full"].width * 1.05), int(LOGO["full"].height * 1.05)), Image.LANCZOS)
        im.paste(lg, ((W - lg.width) // 2, -60), lg)
        im = vhs_look(bloom(im, 0.4), 7, 0.1)
        osd(im, "play", "PLAY")
        camdate(im, 0)
        im.resize((1280, 720), Image.LANCZOS).save(A / "thumb.jpg", quality=92)
        print(A / "thumb.jpg")
        sys.exit(0)
    if "--stills" in sys.argv:
        bars = [float(x) for x in sys.argv[sys.argv.index("--stills") + 1:]]
        for bb in bars:
            f = int(bb * BAR * FPS)
            Image.frombytes("RGB", (W, H), frame(f)).save(A / f"still-{bb:g}.png")
            print(A / f"still-{bb:g}.png")
        sys.exit(0)
    ff = subprocess.Popen(["nice", "-n", "15", "ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-i", str(A / "track.wav"),   # track.wav starts at T0 already: sound from the first frame
                           "-af", "volume=5dB,alimiter=limit=0.89:attack=3:release=60:level=false",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-maxrate", "16M", "-bufsize", "32M", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-shortest", str(OUT)], stdin=subprocess.PIPE)
    with multiprocessing.get_context("fork").Pool(14) as pool:
        for i, buf in enumerate(pool.imap(frame, range(total_frames), chunksize=4)):
            ff.stdin.write(buf)
            if i % 300 == 0: print(f"{i}/{total_frames}", file=sys.stderr, flush=True)
    ff.stdin.close(); ff.wait()
    print(OUT)
