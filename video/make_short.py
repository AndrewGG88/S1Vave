#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""OberVave 1.2.1: the Short (1080 x 1920, 30 fps, ~45 s), the same found VHS tape as the long video (make_video.py),
cut to the end of the track: the breakdown, the pause, the drop, the morph, the strings, all nine, STOP.
Upright: the neon logo on top, thefirmwarehub.com right under it the whole time (the Shorts' buttons and title cover
the lower part), the real FM-1 screen big in the middle, pixel for pixel; the end card says the domain once more, big.
  python3 make_short.py [--stills S ...]"""
import math, multiprocessing, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops

import make_video as MV
from make_video import BAR, FPS, COL, ENV, LOG, NF, F0, CREAM, DIM, BLUE, ease, fade, flicker, F_OSD, F_BLACK, F_SEMI, F_BOLD

SW, SH = 1080, 1920
OUT = MV.A / "obervave-1.2.1-short.mp4"
B0 = 24.0                                             # the song's bar the Short starts on (the breakdown)
END_B = 40.0                                          # the music's end; then STOP and the card
STOP_T, CARD_LEN = 0.6, 4.8
T_MUSIC = (END_B - B0) * BAR
TOTAL = int((T_MUSIC + STOP_T + CARD_LEN) * FPS)
DOMAIN = "thefirmwarehub.com"
SC = 840                                              # the screen, on the phone (240 px -> 840: 3.5 x, kept sharp)
SX, SY = (SW - SC) // 2, 640

_yy, _xx = np.mgrid[0:SH, 0:SW].astype(np.float32)
VIG = (1.0 - 0.35 * np.clip(((_xx - SW / 2) / (SW / 2)) ** 2 + ((_yy - SH / 2) / (SH / 2)) ** 2 - 0.3, 0, 1.4) / 1.4)[..., None]
VIG = VIG * np.where(np.arange(SH) % 2, 0.9, 1.0)[:, None, None]
GRAIN = [np.random.RandomState(50 + i).randint(-4, 5, (SH, SW, 1)).astype(np.int16) for i in range(6)]
_y = np.arange(SH, dtype=np.float32)[:, None] / SH
BGS = Image.fromarray((np.array(MV.BG, np.float32) + np.clip(1 - np.abs(_y - 0.45) * 1.8, 0, 1)[..., None].repeat(SW, 1)
                       * np.array((14, 20, 42), np.float32)).astype(np.uint8))
del _yy, _xx, _y
_ROWS, _COLS = np.arange(SH)[:, None], np.arange(SW)[None, :]


def vhs_look(im, f, amount=0.0, search=0.0):          # as make_video's, upright
    y, cb, cr = im.convert("YCbCr").split()
    y = y.resize((SW * 2 // 3, SH), Image.BILINEAR).resize((SW, SH), Image.BILINEAR)
    cb = ImageChops.offset(cb.resize((SW // 7, SH // 2), Image.BILINEAR).resize((SW, SH), Image.BILINEAR), 5, 0)
    cr = ImageChops.offset(cr.resize((SW // 7, SH // 2), Image.BILINEAR).resize((SW, SH), Image.BILINEAR), 5, 0)
    a = np.asarray(Image.merge("YCbCr", (y, cb, cr)).convert("RGB")).astype(np.int16)
    rnd = np.random.RandomState(f * 13 + 5)
    off = (1.0 + 7 * amount) * np.sin(np.arange(SH) * 0.019 + f * 0.9) + rnd.randn(SH // 6 + 1).repeat(6)[:SH] * (0.4 + 4 * amount)
    hs = 22
    off[-hs:] += np.linspace(4, 30 + rnd.randint(0, 30), hs)
    bands = [(int(SH + 120 - (f * 7) % (SH + 240)), 28, 0.22 + 0.7 * amount)]
    if search > 0:
        for k in (0, 1): bands.append((int((f * 151 + k * SH // 2) % (SH + 120)) - 60, 80, 0.95 * search))
    for y0, bh, k in bands:
        y0, y1 = max(0, y0), min(SH, y0 + bh)
        if y1 > y0: off[y0:y1] += rnd.randint(-60, 60) * k
    a = a[_ROWS, (_COLS - np.round(off).astype(np.int32)[:, None]) % SW]
    for y0, bh, k in bands + [(SH - hs, hs, 0.5)]:
        y0, y1 = max(0, y0), min(SH, y0 + bh)
        if y1 <= y0: continue
        sn = rnd.randint(0, 255, (y1 - y0, SW // 3, 1)).repeat(3, 1).astype(np.int16)
        a[y0:y1] = a[y0:y1] * (1 - k * 0.6) + sn * k * (0.5 + 0.5 * (rnd.rand(y1 - y0, 1, 1) < 0.5))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def osd_text(im, xy, s, size=64, anchor="la", col=(255, 255, 255)):
    d = ImageDraw.Draw(im)
    d.text((xy[0] + 3, xy[1] + 3), s, font=F_OSD(size), fill=(0, 0, 0), anchor=anchor)
    d.text(xy, s, font=F_OSD(size), fill=col, anchor=anchor)


def osd(im, sym, label, right=None):                  # the VCR's letters, top (inside the Shorts' safe area)
    MV.osd_sym(im, 60, 150, sym, 40)
    osd_text(im, (60 + (90 if sym in ("ff", "rew") else 62), 144), label)
    if right: osd_text(im, (SW - 60, 144), right, anchor="ra")


def fog(im, t, k, col=(90, 120, 200)):
    lay = Image.new("RGB", (SW // 4, SH // 4), (0, 0, 0))
    d = ImageDraw.Draw(lay)
    for x, y, r, sp, ph in MV.FOG:
        px = (x * SW / 4 + t * (6 + 10 * sp)) % (SW / 4); py = (y * SH / 4 - t * (3 + 5 * sp)) % (SH / 4)
        rr = 12 + 34 * r
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=tuple(int(c * (0.25 + 0.2 * math.sin(t + ph * 6))) for c in col))
    lay = lay.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * k)).resize((SW, SH), Image.BILINEAR)
    im.paste(ImageChops.add(im, lay))


def halo(im, box, col, k):
    if k <= 0.02: return
    lay = Image.new("RGB", (SW // 4, SH // 4), (0, 0, 0))
    x0, y0, x1, y1 = box
    ImageDraw.Draw(lay).rounded_rectangle([(x0 - 40) / 4, (y0 - 40) / 4, (x1 + 40) / 4, (y1 + 40) / 4], radius=24, fill=tuple(int(c * 0.6 * k) for c in col))
    im.paste(ImageChops.add(im, lay.filter(ImageFilter.GaussianBlur(16)).resize((SW, SH), Image.BILINEAR)))


def screen(part, fi, size, notch=0.0):
    """the real screen in its bezel, nearest-neighbour (the pixels stay pixels), RGBA"""
    s = MV.scanlines(MV.screen_raw(part, fi).resize((size, size), Image.NEAREST), 4)
    if notch > 0:                                     # the filter's morph toward the notch: a band cut out of the middle
        a = np.asarray(s).copy()
        c, w = int(size * 0.52), int(4 + size * 0.5 * notch)
        a[c - w // 2:c + w // 2] = (a[c - w // 2:c + w // 2] * 0.12).astype(np.uint8)
        s = Image.fromarray(a)
    pad = max(8, size // 30)
    b = Image.new("RGBA", (size + 2 * pad, size + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(b).rounded_rectangle([0, 0, b.width - 1, b.height - 1], radius=pad * 2, fill=(12, 12, 15), outline=(70, 74, 90), width=3)
    b.paste(s, (pad, pad))
    return b


def header(im, n):
    """the logo and the domain under it: always there (the reason for the Short)"""
    lg = MV.LOGO["full"]
    k = 980 / lg.width
    lg = lg.resize((980, int(lg.height * k)), Image.LANCZOS)
    a = flicker(n)
    im.paste(fade(lg, a), ((SW - lg.width) // 2, 200), fade(lg, a))
    d = ImageDraw.Draw(im)
    d.text((SW // 2, 470), "FREE FIRMWARE FOR THE M-VAVE FM-1", font=F_SEMI(32), fill=CREAM, anchor="mm")
    d.text((SW // 2, 548), DOMAIN, font=F_BLACK(92), fill=BLUE, anchor="mm")


# (song bar from, to, part, chapter, caption)
SCENES = [(25.0, 28.0, "arp", "REVERB", "drums out: the arp's filter opens, the plate's mix goes up"),
          (28.0, 30.0, "arp2", "UPSIDE", "the drop: a second arp, through the SEM-style filter"),
          (30.0, 32.0, "arp2", "MORPH", "knob 4 turns the filter toward the notch"),
          (32.0, 34.0, "strings", "STRINGS", "PWM strings, every voice its own LFO phase"),
          (34.0, 40.0, None, "ALL NINE", "nine FM-1s, one firmware, zero samples")]
GRID = ["arp", "bass", "pad", "lead", "arp2", "strings", "kick", "clap", "hat"]
CASS = MV.cassette(940, "OBERVAVE", "DO NOT ERASE!")
IN = 36


def frame(f):
    t = f / FPS
    b = B0 + t / BAR
    fi = F0 + int(round(B0 * BAR * FPS)) + f
    im = BGS.copy()
    osd_req, stress, search, clean = None, 0.0, 0.0, False
    if f < IN:                                        # the cassette, into the slot
        fog(im, t, 0.5, (120, 100, 80))
        u = max(0.0, (f - 20) / (IN - 20))
        c = CASS.resize((int(CASS.width * (1 - 0.25 * u)), int(CASS.height * (1 - 0.25 * u))), Image.BILINEAR)
        x, y = (SW - c.width) // 2, 820 + int(1500 * u * u)
        MV.shadow_paste(im, c, (x, y), 200)
        header(im, f)
        d = ImageDraw.Draw(im)
        d.text((SW // 2, 1500), "found in a basement:", font=F_SEMI(40), fill=DIM, anchor="mm")
        d.text((SW // 2, 1560), "one FM-1 firmware", font=F_BOLD(56), fill=CREAM, anchor="mm")
        clean = True
    elif b < END_B:
        n_scene = 0
        if b < 25.0:                                  # PLAY: snow, then the breakdown's arp
            part, chap, cap = "arp", "REVERB", SCENES[0][4]
            n_scene = f - IN
            stress = max(0.0, 1 - (f - IN) / 30)
        else:
            sc = next(s for s in SCENES if s[0] <= b < s[1])
            part, chap, cap = sc[2], sc[3], sc[4]
            n_scene = int((b - sc[0]) * BAR * FPS)
        fb = fi
        if 27.5 <= b < 28.0:                          # the pause before the drop: frozen, shaking
            fb = F0 + int(round(27.5 * BAR * FPS))
            osd_req = ("pause", "PAUSE")
            stress = 0.55
        if b < 28.0:
            fog(im, t, 0.4 + 1.4 * (b - 24) / 4)
        kick = float(ENV["kick"][min(fi, NF - 1)]) if 28 <= b < 38 else 0.0
        if part:
            lv = float(ENV[part][min(fb, NF - 1)])
            size = int(SC * (1 + 0.03 * kick))
            dv = screen(part, fb, size, notch=ease((b - 30) / 2) if chap == "MORPH" else 0.0)
            x, y = (SW - dv.width) // 2, SY + (SC - size) // 2
            halo(im, (x, y, x + dv.width, y + dv.height), COL[part], 0.4 + 0.6 * lv)
            MV.shadow_paste(im, dv, (x, y))
        else:                                         # all nine: a 3 x 3 wall; from bar 38 they fall away
            tile = 268
            for i, p in enumerate(GRID):
                x = (SW - 3 * tile - 2 * 18) // 2 + (i % 3) * (tile + 18)
                y = SY + 20 + (i // 3) * (tile + 18)
                tf = MV.FALL.get(p)
                if tf is not None and b > tf:
                    dt = (b - tf) * BAR
                    y += int(0.5 * 2600 * dt * dt)
                if y > SH: continue
                lv = float(ENV[p][min(fi, NF - 1)])
                dv = screen(p, fi, tile - 16)
                halo(im, (x, y, x + dv.width, y + dv.height), COL[p], lv * 0.8)
                im.paste(dv, (x, y), dv)
        header(im, f)
        d = ImageDraw.Draw(im)
        img, ox = MV.neon(chap, 84)
        a = flicker(n_scene)
        if a > 0: im.paste(fade(img, a), ((SW - img.width) // 2, 1625 - img.height // 2), fade(img, a))
        d.text((SW // 2, 1722), cap, font=F_SEMI(32), fill=CREAM, anchor="mm")
        cl = float(ENV["clap"][min(fi, NF - 1)])
        if 25 <= b < 28 and cl > 0.55 and float(ENV["clap"][min(fi - 1, NF - 1)]) <= 0.55:
            bolt(im, fi)
        if 28.0 <= b < 28.1:
            im = Image.blend(im, Image.new("RGB", (SW, SH), (255, 255, 255)), 0.8 * (1 - (b - 28.0) / 0.1))
        stress += max(0.0, -MV.bend_at(fi)) * 0.5
        if osd_req is None:
            if f < IN + 75: osd_req = ("play", "PLAY")
            elif n_scene < 6 and b >= 25: osd_req = ("ff", ""); search = 1 - n_scene / 6
            elif n_scene < 60: osd_req = ("play", "PLAY")
        if f < IN + 8:                                # (the tape starts: snow first)
            sn = np.random.RandomState(f).randint(0, 200, (SH // 3, SW // 3, 1)).repeat(3, 0).repeat(3, 1).repeat(3, 2)
            im = Image.fromarray(sn.astype(np.uint8))
        osd_text(im, (SW - 60, SH - 110), "PM 11:52  OCT.13 1983", 44, "rs", (255, 238, 205))   # (the camcorder's date)
    else:
        u = t - T_MUSIC
        if u < STOP_T:
            im = Image.new("RGB", (SW, SH), (16, 32, 170))
            clean = True
            osd_req = ("stop", "STOP")
        else:                                         # the card: the domain, big
            n = int((u - STOP_T) * FPS)
            fog(im, t, 0.8)
            c = MV.cassette(820, "OBERVAVE 1.2.1", DOMAIN, (40, 90, 200)).rotate(-6, Image.BICUBIC, expand=True)
            MV.shadow_paste(im, c, ((SW - c.width) // 2, 1080), 200)
            header(im, n)
            d = ImageDraw.Draw(im)
            a = ease((n - 6) / 10)
            MV.text(im, (SW // 2, 700), "Install it in a minute,", F_SEMI(46), CREAM, a, "mm")
            MV.text(im, (SW // 2, 760), "free, from the browser:", F_SEMI(46), CREAM, a, "mm")
            k = 1 + 0.04 * math.sin(n * 0.25)
            MV.text(im, (SW // 2, 880), DOMAIN, F_BLACK(int(90 * k)), BLUE, ease((n - 10) / 8), "mm")
            MV.text(im, (SW // 2, 980), "Please always check the latest firmware version!", F_SEMI(30), (230, 209, 185), ease((n - 18) / 10), "mm")
            if n < 40: osd_req = ("play", "PLAY")
            stress = max(0.0, 1 - n / 20) * 0.8
    if not clean:
        im = vhs_look(im, f, min(1.0, stress), search)
    if osd_req: osd(im, *osd_req)
    a = np.asarray(im, dtype=np.float32) * VIG + GRAIN[f % 6]
    k = min(1.0, (TOTAL - f) / FPS / 0.8)
    if k < 1: a *= max(0.0, k)
    return np.clip(a, 0, 255).astype(np.uint8).tobytes()


def bolt(im, seed):                                   # the clap's lightning, upright
    lay = Image.new("RGB", (SW, SH), (0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = np.random.RandomState(seed)
    x, y, pts = rnd.randint(150, SW - 150), 0, []
    while y < SH:
        pts.append((x, y)); x += rnd.randint(-80, 80); y += rnd.randint(50, 140)
    d.line(pts, fill=(150, 180, 255), width=9)
    d.line(pts, fill=(255, 255, 255), width=3)
    im.paste(ImageChops.add(im, lay.filter(ImageFilter.GaussianBlur(1.5))))


if __name__ == "__main__":
    if "--stills" in sys.argv:
        for x in sys.argv[sys.argv.index("--stills") + 1:]:
            f = int(float(x) * FPS)
            Image.frombytes("RGB", (SW, SH), frame(f)).save(MV.A / f"short-{x}.png")
            print(MV.A / f"short-{x}.png")
        sys.exit(0)
    t0 = B0 * BAR                                      # track.wav starts at the music (T0)
    host = ["flatpak-spawn", "--host"] if Path("/.flatpak-info").exists() else []   # (the sandbox's ffmpeg has no libx264)
    ff = subprocess.Popen(host + ["nice", "-n", "15", "ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{SW}x{SH}",
                           "-r", str(FPS), "-i", "-", "-ss", f"{t0:.3f}", "-i", str(MV.A / "track.wav"),
                           "-af", f"volume=5dB,alimiter=limit=0.89:attack=3:release=60:level=false,apad,"
                                  f"afade=t=out:st={T_MUSIC + STOP_T + CARD_LEN - 2.5:.2f}:d=2.5",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-maxrate", "14M", "-bufsize", "28M", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-shortest", str(OUT)], stdin=subprocess.PIPE)
    with multiprocessing.get_context("fork").Pool(14) as pool:
        for i, buf in enumerate(pool.imap(frame, range(TOTAL), chunksize=4)):
            ff.stdin.write(buf)
            if i % 300 == 0: print(f"{i}/{TOTAL}", file=sys.stderr, flush=True)
    ff.stdin.close(); ff.wait()
    print(OUT)
