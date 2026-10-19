#!/usr/bin/env python3
"""The OberVave video's music: eight OberVaves (the real firmware's host build, firmware/src/obervave.c), each with a
script of notes, CCs, button presses and knob turns. D minor, 94 BPM, 40 bars: slow dark disco, a four-note arpeggio
climbing all the way through, a rolling octave bass, four on the floor, a woozy lead, everything through delay and plate.
Writes scripts/<part>.txt, runs the host build (tests/run_host.sh builds it) filmed at 30 fps (f/<part>/NNNNN.png +
f/<part>-log.txt), mixes stems/*.wav into track.wav.

  python3 song.py [--scripts-only | --mix-only | --parts kick,hat,clap]"""
import subprocess, sys, wave, shutil
from pathlib import Path
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
OBV = HERE.parent
HOST = OBV / "build" / "host" / "obervave"
BPM, T0 = 94, 10000                                   # splash 2.4 s, the tempo dialled in, the drums' steps set; music at T0
BEAT = 60000 / BPM
BARS = 44                                             # 40 and the last chord's tail
END = T0 + int(BARS * 4 * BEAT) + 15000                 # the plates ring out under the end card (4 bars + 3 s in make_video)
DEVICE_TEMPO = 120                                    # what the firmware starts with (its settings): the arp and the
                                                      # delay run on it, so every part dials the song's tempo in first

PARAMS = ("O1_WAVE O1_PW O1_LVL NOISE O2_WAVE O2_PW O2_LVL O2_SEMI SYNC XMOD ENV_O2 O2_FINE CUTOFF RESO FENV_AMT KEYTRK "
          "FTYPE DRIVE VEL_FLT VEL_AMP FA FD FS FR AA AD AS AR LFO_SHAPE LFO_RATE LFO_DELAY LFO_PHASE LFO_PITCH LFO_PWM "
          "LFO_FLT LFO_AMP LFO_PITCH_TO LFO_PWM_TO MODE UNI_N UNI_DET GLIDE VINTAGE SPREAD BEND VOLUME MOD_DEPTH "
          "ARP_MODE ARP_DIV ARP_OCT ARP_GATE FMORPH CHO_RATE CHO_DEPTH CHO_MIX DLY_TIME DLY_FB DLY_TONE DLY_MIX "
          "REV_SIZE REV_DAMP REV_PRE REV_MIX").split()
PMAX = {"O1_WAVE": 3, "O2_WAVE": 3, "O2_SEMI": 48, "SYNC": 1, "FTYPE": 5, "LFO_SHAPE": 5, "LFO_PHASE": 2, "LFO_PITCH_TO": 2,
        "LFO_PWM_TO": 2, "MODE": 3, "UNI_N": 8, "BEND": 24, "ARP_MODE": 5, "ARP_DIV": 6, "ARP_OCT": 4, "DLY_TIME": 6}
FIXED = {"CUTOFF": 74, "RESO": 71, "AA": 73, "AR": 72, "GLIDE": 5, "MOD_DEPTH": 1}
CC = dict((n, c) for n, c in FIXED.items())
nxt = 20
for n in PARAMS:
    if n in FIXED: continue
    while nxt in CC.values() or nxt == 64: nxt += 1
    CC[n] = nxt; nxt += 1
PROG = {"DARKARP": 0, "SYNCLEAD": 2, "UNISON": 3, "PWM": 4, "FATBASS": 6, "SWEEPPAD": 8, "SQUARELD": 15, "SUBBASS": 16,
        "UPSIDEARP": 25, "NEONPAD": 28, "INIT": 31}
BTN = {"OCT-": 0, "OCT+": 1, "FX": 2, "SEL": 3, "ENV": 4, "LFO": 5, "EDIT": 6, "GLO": 7, "HOME": 8, "SAVE": 9, "ARP": 10,
       "SEQ": 11, "PLAY": 12, "REC": 13}
ENC = {"SELECT": 0, "CUTOFF": 1, "K1": 2, "K2": 3, "K3": 4, "K4": 5, "PRESETS": 6}

def ccval(name, v):                                   # the CC that sets parameter `name` to v (the app scales by max)
    m = PMAX.get(name, 127)
    if m == 127: return v
    d = (127 * v) // m
    while (d * m + 63) // 127 < v: d += 1
    assert (d * m + 63) // 127 == v
    return d

class Part:
    def __init__(self, name, film, mix=True):
        self.name, self.film, self.mix, self.ev = name, film, mix, []
    def at(self, bar, beat=0.0): return T0 + int((bar * 4 + beat) * BEAT)
    def note(self, bar, beat, n, vel, dur_beats):
        t = self.at(bar, beat)
        self.ev.append((t, f"midi 0x90 {n} {vel}"))
        self.ev.append((t + int(dur_beats * BEAT) - 2, f"midi 0x80 {n} 0"))
    def chord(self, bar, beat, notes, vel, dur): [self.note(bar, beat, n, vel, dur) for n in notes]
    def cc(self, t, name, v, ch=0): self.ev.append((t, f"midi {0xB0 + ch:#x} {CC[name]} {ccval(name, v)}"))
    def set(self, t, ch=0, **kv):
        for k, v in kv.items(): self.cc(t, k, v, ch); t += 1
    def pc(self, t, prog, ch=0): self.ev.append((t, f"midi {0xC0 + ch:#x} {prog} 0"))
    def btn(self, t, b): self.ev.append((t, f"btn {BTN[b] if isinstance(b, str) else b}"))
    def btns(self, t, *names):                        # presses 50 ms apart
        for i, b in enumerate(names): self.btn(t + 50 * i, b)
    def hold(self, t0, t1, b):                        # a button held from t0 to t1 (a layer)
        self.ev.append((t0, f"btndown {BTN[b]}")); self.ev.append((t1, f"btnup {BTN[b]}"))
    def keys(self, t, mask): self.ev.append((t, f"keys {mask:#x}"))
    def program_steps(self, t, note, div_turn, len_turn, steps):
        """the step sequencer, by hand: a note played (the pen), SEQ held: DIV and LENGTH turned, then each step pressed
        (an empty step is set with the pen at once) with its knobs turned while it is held: (step, level, gate)"""
        WK = [0, 2, 4, 6, 7, 9, 11, 12, 14, 16, 18, 19, 21, 23, 24, 26]
        self.ev.append((t, f"midi 0x90 {note} 60")); self.ev.append((t + 30, f"midi 0x80 {note} 0"))
        t += 100
        t_seq = t
        t += 60
        for i in range(abs(div_turn)): self.enc(t, "K2", 1 if div_turn > 0 else -1); t += 25
        for i in range(abs(len_turn)): self.enc(t, "K4", 1 if len_turn > 0 else -1); t += 25
        for step, level, gate in steps:
            self.keys(t, 1 << WK[step]); t += 40
            for i in range(abs(level)): self.enc(t, "K2", 1 if level > 0 else -1); t += 20
            for i in range(abs(gate)): self.enc(t, "K4", 1 if gate > 0 else -1); t += 12
            self.keys(t, 0); t += 40
        self.hold(t_seq, t + 20, "SEQ")
        return t + 40
    def glo_key(self, t, step):                        # GLO held, a white key (1 / 2: mute A / B)
        WK = [0, 2, 4, 6, 7, 9, 11, 12, 14, 16, 18, 19, 21, 23, 24, 26]
        self.ev.append((t, f"btndown {BTN['GLO']}")); self.keys(t + 8, 1 << WK[step]); self.keys(t + 14, 0)
        self.ev.append((t + 20, f"btnup {BTN['GLO']}"))
    def enc(self, t, e, n): self.ev.append((t, f"enc {ENC[e] if isinstance(e, str) else e} {n}"))
    def turn(self, t0, t1, e, detents):               # a knob turned `detents` (signed) between t0 and t1, a detent a step
        n = abs(detents)
        for i in range(n): self.enc(t0 + (t1 - t0) * i // max(1, n - 1), e, 1 if detents > 0 else -1)
    def sweep(self, t0, t1, name, v0, v1, step_ms=40):   # a CC ramp (the engine slews the cutoff: 40 ms steps are smooth)
        n = max(1, (t1 - t0) // step_ms)
        for i in range(n + 1): self.cc(t0 + i * step_ms, name, int(round(v0 + (v1 - v0) * i / n)))
    def bend(self, t0, t1, b0, b1, step_ms=15):           # pitch bend ramp, -8192..8191
        n = max(1, (t1 - t0) // step_ms)
        for i in range(n + 1):
            b = int(round(b0 + (b1 - b0) * i / n)) + 8192
            self.ev.append((t0 + i * step_ms, f"midi 0xE0 {b & 127} {b >> 7}"))
    def setup(self, prog, oct=0, **params):           # after the splash: the tempo on the GLO page, the program, its tweaks
        t = 2500
        self.btn(t, "GLO")
        self.turn(t + 60, t + 60 + 25 * abs(BPM - DEVICE_TEMPO), "K1", BPM - DEVICE_TEMPO)   # done by ~3.2 s
        t = T0 - 700
        self.pc(t, prog)
        if params: self.set(t + 10, **params)
        for i in range(abs(oct)): self.btn(t + 100 + 50 * i, "OCT+" if oct > 0 else "OCT-")
        self.btn(t + 400, "HOME")
    def write(self):
        self.ev.sort(key=lambda e: e[0])
        p = HERE / "scripts" / f"{self.name}.txt"
        p.parent.mkdir(exist_ok=True)
        p.write_text("\n".join(f"{t} {s}" for t, s in self.ev) + f"\n{END} end\n")
        return p

# ---- the music. D Phrygian over a D pedal, four bars round and round: | Dm(add9) | Dm(add9) | Ebmaj7 | C#m7 |:
# the flat second leans on the tonic, the minor chord a half step below pulls it back. Hypnotic, never resolving.
DM, EB, CS = [50, 53, 57, 64], [51, 55, 58, 62], [49, 52, 56, 59]
PROGRESSION = [DM, DM, EB, CS]
ROOT = [26, 26, 27, 25]                                # D1 D1 Eb1 C#1
def chord_of(bar): return PROGRESSION[bar % 4]
def root_of(bar): return ROOT[bar % 4]

parts = {}
def P(name, film=True, mix=True): parts[name] = Part(name, film, mix); return parts[name]

# ARP: DARK ARP, the backbone all 40 bars: the chord held a bar, climbed in 16ths. The filter opens over the first
# half, all the way in the breakdown, drops shut at the drop (bar 28) and opens once more
arp = P("arp")
arp.setup(PROG["DARKARP"], oct=-1, CUTOFF=34, VOLUME=105, REV_MIX=55)
for bar in range(0, 40):
    arp.chord(bar, 0, chord_of(bar), 100, 3.98)
arp.chord(40, 0, DM, 100, 0.98)
arp.sweep(arp.at(0), arp.at(16), "CUTOFF", 34, 56)
arp.sweep(arp.at(24), arp.at(28), "CUTOFF", 56, 84)
arp.cc(arp.at(28) - 10, "CUTOFF", 40)
arp.sweep(arp.at(28), arp.at(36), "CUTOFF", 40, 62)
arp.sweep(arp.at(38), arp.at(40), "CUTOFF", 62, 28)
arp.btn(T0 - 200, "ARP")                              # the ARP page
arp.btns(arp.at(24) - 200, "FX", "FX", "FX")          # the REVERB page for the breakdown
arp.turn(arp.at(25), arp.at(27), "K4", 10)            # REV MIX up for the breakdown (and back after the drop)
arp.turn(arp.at(29), arp.at(30), "K4", -10)

# BASS: FAT BASS, disco: root and octave in eighths from bar 8, whole notes in the breakdown, the glide dives at bar 36
bass = P("bass")
bass.setup(PROG["FATBASS"], oct=-2, VOLUME=112, CUTOFF=36, DRIVE=40, GLIDE=6, RESO=24, AR=30, DLY_MIX=0, REV_MIX=0)
for bar in range(8, 40):
    r = root_of(bar)
    if 24 <= bar < 28:
        bass.note(bar, 0, r, 100, 3.9)
    else:
        for i in range(8):
            up = i in (1, 3, 5, 7)
            bass.note(bar, i * .5, r + (12 if up else 0), 108 if not up else 90, .42)
bass.note(40, 0, 26, 112, 4.0)
bass.btns(T0 - 200, "EDIT", "EDIT", "EDIT", "EDIT")   # the FILTER page
bass.turn(bass.at(20), bass.at(22), "K1", 16)         # RESO up over two bars, then back
bass.turn(bass.at(22), bass.at(23), "K1", -16)
bass.sweep(bass.at(34), bass.at(36), "CUTOFF", 36, 66)
bass.cc(bass.at(36), "CUTOFF", 36)

# PAD: NEON PAD, swells from bar 12, carries the breakdown, rings out at the end
pad = P("pad")
pad.setup(PROG["NEONPAD"], VOLUME=74, CUTOFF=46, AA=95)
for bar in range(12, 40):
    pad.chord(bar, 0, [n + 12 for n in chord_of(bar)], 88, 4.0)
pad.chord(40, 0, [n + 12 for n in DM], 92, 12.0)
pad.sweep(pad.at(24), pad.at(28), "CUTOFF", 46, 70)
pad.cc(pad.at(28), "CUTOFF", 46)
pad.btns(T0 - 200, "FX")                              # the CHORUS page
pad.turn(pad.at(16), pad.at(18), "K2", 10)            # chorus DEPTH up

# LEAD: UNISON LD, woozy: six voices wide apart, slow glide, vintage drift, a pitch dive at the end of each phrase
lead = P("lead")
lead.setup(PROG["UNISON"], oct=1, VOLUME=92, CUTOFF=58, UNI_N=6, UNI_DET=70, GLIDE=38, VINTAGE=110, AA=25, AR=70, BEND=12,
           DLY_TIME=4, DLY_FB=45, DLY_MIX=40, REV_SIZE=105, REV_MIX=40, LFO_PITCH=14, LFO_RATE=30, LFO_DELAY=40)
MEL = [(0, 0, 62, 2.5), (0, 3, 63, 1.0), (1, 0, 65, 1.5), (1, 2, 62, 2.0), (2, 0, 63, 2.0), (2, 2.5, 60, 1.5),
       (3, 0, 61, 4.0), (4, 0, 62, 1.0), (4, 1.5, 65, 1.0), (4, 3, 69, 1.0), (5, 0, 70, 2.0), (5, 2, 69, 2.0),
       (6, 0, 67, 1.5), (6, 2, 63, 2.0), (7, 0, 61, 4.0)]                 # D Phrygian: the Eb, and C# under the last chord
for b, beat, n, dur in MEL:
    lead.note(16 + b, beat, n, 104, dur * .95)
lead.bend(lead.at(19, 2), lead.at(19, 3.9), 0, -8192)            # the dive: an octave down (BEND 12)
lead.bend(lead.at(20) - 60, lead.at(20) - 10, -8192, 0)
lead.bend(lead.at(23, 1.5), lead.at(23, 3.9), 0, -8192)
lead.bend(lead.at(24) - 60, lead.at(24) - 10, -8192, 0)
for b, beat, n, dur in MEL:
    lead.note(32 + b, beat, n + (12 if b >= 4 else 0), 108, dur * .95)
lead.bend(lead.at(39, 1), lead.at(39, 3.9), 0, -8192)
lead.bend(lead.at(40) - 60, lead.at(40) - 10, -8192, 0)
lead.note(40, 0, 62, 100, 3.0)
lead.bend(lead.at(40, 1.5), lead.at(40, 3), 0, -8192)
lead.btns(T0 - 200, "GLO", "GLO")                     # the VOICE page: UNISON, 6 voices
lead.btns(lead.at(32) - 300, "FX", "FX")              # the DELAY page the second time

# ARP2: UPSIDE ARP, up and down two octaves above, bars 28-36 (the drop), MORPH turned LP -> notch across it
arp2 = P("arp2")
arp2.setup(PROG["UPSIDEARP"], VOLUME=76, CUTOFF=34, REV_MIX=60)
for bar in range(28, 36):
    arp2.chord(bar, 0, [n + 12 for n in chord_of(bar)], 90, 3.98)
arp2.btns(T0 - 200, "EDIT", "EDIT", "EDIT", "EDIT", "EDIT")   # FILTER +
arp2.turn(arp2.at(30), arp2.at(34), "K4", 22)         # MORPH toward the notch

# STRINGS: PWM STRING two octaves up, bars 32-40, the last chord long
strings = P("strings")
strings.setup(PROG["PWM"], oct=1, VOLUME=80, CUTOFF=60, AA=70, REV_MIX=50, REV_SIZE=115)
for bar in range(32, 40):
    strings.chord(bar, 0, [n + 24 for n in chord_of(bar)], 85, 4.0)
strings.chord(40, 0, [n + 24 for n in DM], 85, 12.0)
strings.btns(T0 - 200, "LFO")                         # the LFO page (the PWM)

# DRUMS: three OberVaves from INIT. Kick: the resonant 12 dB filter rings like a sine, the envelope drops its pitch.
# Clap: noise through the band-pass, four quick hits, a long plate. Hats: noise through the high-pass, open on the offbeat.
KICK = dict(MODE=3, O1_WAVE=1, O1_LVL=55, O2_WAVE=0, NOISE=0, FTYPE=0, CUTOFF=22, RESO=125, FENV_AMT=64 + 50,
            FA=0, FD=66, FS=0, AA=0, AD=90, AS=0, AR=40, KEYTRK=0, VEL_FLT=0, VEL_AMP=30, DRIVE=45, VINTAGE=0, SPREAD=0, VOLUME=127, GLIDE=0)
HAT = dict(MODE=3, O1_WAVE=0, O2_WAVE=0, NOISE=127, FTYPE=1, CUTOFF=116, RESO=20, FENV_AMT=64,
           FA=0, AA=0, AD=50, AS=70, AR=60, KEYTRK=0, VEL_AMP=90, VINTAGE=0, SPREAD=0,
           VOLUME=60)                         # (95 on its own FM-1 at a stem gain of 1.1; here under the kick's 2.8: 95 x sqrt(1.1 / 2.8))
DRUMS_IN = 24
def drums_part(name, film=True, mix=True, mute=None):
    """kick and hats on ONE OberVave (1.4: track B has a sound of its own): the kick is sound A on track A, the hats
    are track B's own sound, set from MIDI channel 2. Both programmed by hand on the step sequencer before the music
    (SEQ held, the keys as steps; ALGORITHM picks track B): kick 4 quarters (1 3 HARD, 2 4 NORM, half-beat gates),
    hats 8 eighths (closed SOFT and short, open NORM and long). mute: 0 / 1 mutes track A / B (GLO + key 1 / 2): the
    video's light for the kick and for the hats alone, not filmed, not mixed"""
    d = P(name, film, mix)
    d.setup(PROG["INIT"], oct=-2, **KICK)
    d.turn(3260, 3260, "K3", 1)                       # GLOBAL, MIDI CH: OMNI -> 1, so channel 2 plays track B's sound
    t = d.program_steps(3600, 36, -3, -12, [(0, 1, -16), (1, 0, -16), (2, 1, -16), (3, 0, -16)])
    d.enc(t, "CUTOFF", 1)                             # ALGORITHM: track B
    t = d.program_steps(t + 60, 70, -2, 8, [(k, -1 if k % 2 == 0 else 0, -35 if k % 2 == 0 else 6) for k in range(8)])
    d.enc(t, "CUTOFF", -1)                            # back to A: the kick's sound comes on channel 1 next
    assert t < T0 - 800, t
    d.pc(T0 - 600, PROG["INIT"], ch=1)                # track B's own sound: INIT, then the hats' settings
    d.set(T0 - 590, ch=1, **HAT)
    if mute is not None: d.glo_key(T0 - 450, mute)
    d.btn(T0 - 200, "SEQ")                            # TRACKS: kick on A (blue), hats on B (orange)
    d.btn(d.at(DRUMS_IN) - 2, "PLAY")
    d.btn(d.at(38) - 10, "PLAY")
    return d
kick = drums_part("drums")
drums_part("kick", film=False, mix=False, mute=1)
drums_part("hat", film=False, mix=False, mute=0)
clap = P("clap")
clap.setup(PROG["INIT"], MODE=3, O1_WAVE=0, O2_WAVE=0, NOISE=127, FTYPE=2, CUTOFF=74, RESO=45, FENV_AMT=64 + 10,
           FA=0, FD=50, FS=0, AA=0, AD=62, AS=0, AR=50, KEYTRK=0, VEL_FLT=30, VEL_AMP=50, DRIVE=20, VINTAGE=0, SPREAD=0, VOLUME=120,
           REV_SIZE=112, REV_DAMP=65, REV_PRE=15, REV_MIX=70)
# no drums for the first minute (the synths alone): PLAY starts both tracks on bar 24, a clap roll leads in; PLAY stops them at bar 38
for bar in range(DRUMS_IN, 38):
    for beat in (1, 3):
        for k in range(3): clap.note(bar, beat + k * 0.04, 60, 100 + k * 8, .25)   # the flam of a clap
for i in range(8): clap.note(27, 2 + i * .25, 60, 70 + i * 7, .15)   # a clap roll into the drop
for i in range(4): clap.note(DRUMS_IN - 1, 2 + i * .5, 60, 85 + i * 10, .2)   # and one that brings the drums in
kick.note(40, 0, 36, 120, .5); clap.note(40, 0, 60, 110, .25)   # (the last kick from MIDI: sound A)
parts["kick"].note(40, 0, 36, 120, .5)                # (and in the kick's light)

GAIN = {"arp": 3.6, "bass": 1.5, "pad": 1.1, "lead": 1.4, "arp2": 2.4, "strings": 1.0, "drums": 2.8, "clap": 4.2}

def run(part):
    script = part.write()
    out = HERE / "stems" / part.name
    args = [str(HOST), str(out), str(script)] + (["30"] if part.film else [])
    subprocess.run(["nice", "-n", "15"] + args, check=True, stdout=subprocess.DEVNULL)
    if part.film:                                     # ppm -> png, the log beside them
        fd = HERE / "f" / part.name
        if fd.exists(): shutil.rmtree(fd)
        fd.mkdir(parents=True)
        for i, p in enumerate(sorted((HERE / "stems").glob(f"{part.name}-*.ppm"))):
            Image.open(p).save(fd / f"{i:05d}.png"); p.unlink()
        shutil.move(str(out) + "-log.txt", HERE / "f" / f"{part.name}-log.txt")
    with wave.open(str(out) + ".wav") as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, 2).astype(np.float32) / 32768
    return a

def main():
    for p in parts.values(): p.write()
    if "--scripts-only" in sys.argv: return
    from concurrent.futures import ThreadPoolExecutor
    if "--mix-only" in sys.argv:                      # the stems as they are, only the gains and the sum
        stems = {}
        for name in [p for p in parts if parts[p].mix]:
            with wave.open(str(HERE / "stems" / f"{name}.wav")) as w:
                stems[name] = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, 2).astype(np.float32) / 32768
    else:                                             # --parts a,b: film only those again, the other stems as they are
        only = sys.argv[sys.argv.index("--parts") + 1].split(",") if "--parts" in sys.argv else list(parts)
        with ThreadPoolExecutor(3) as ex:
            stems = dict(zip(only, ex.map(run, [parts[p] for p in only])))
        for name in parts:
            if name not in stems:
                with wave.open(str(HERE / "stems" / f"{name}.wav")) as w:
                    stems[name] = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, 2).astype(np.float32) / 32768
        stems = {p: stems[p] for p in parts if parts[p].mix}
    n = max(len(a) for a in stems.values())
    mix = np.zeros((n, 2), np.float32)
    for name, a in stems.items():
        rms = float(np.sqrt((a ** 2).mean())); pk = float(np.abs(a).max())
        print(f"{name:8s} rms {20 * np.log10(rms + 1e-9):6.1f} dB  peak {20 * np.log10(pk + 1e-9):6.1f} dB  gain {GAIN[name]}")
        mix[:len(a)] += a * GAIN[name]
    mix = mix[int(T0 * 44.1):]                        # the music starts at T0
    pk = float(np.abs(mix).max())
    print(f"mix peak {20 * np.log10(pk):.1f} dB before the master")
    mix *= 0.7 / max(pk, 1e-9)                      # -3 dB peak; the video's ffmpeg limiter does the rest
    with wave.open(str(HERE / "track.wav"), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    print("track.wav", len(mix) / 44100, "s")

if __name__ == "__main__":
    main()
