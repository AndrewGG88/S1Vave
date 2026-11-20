/* SPDX-License-Identifier: GPL-3.0-only */
/* Copyright (C) 2026 Kris Bishop (bk40-home) */
/* sh101_vcf.h: the SH-101 VCF (IR3109) in single-precision float. One header, no libm, no division per sample;
 * shared by M-Vsynth2 (filter type 5), S1Vave (OBV_FILTER_SH101) and the Teensy work. On the FM-1 (AC791N FPU)
 * build with -mcpu=r3 -mfprev1 -ffp-contract=off and mask the FP exception traps.
 *
 * The circuit, from the SH-101 service manual (circuit diagram, VCF and panel):
 *   - four IR3109 OTA stages, 68k / 560R input dividers, C47/48/50/51 240p: dy/dt = w tanh(x - y) each;
 *     stage 1 is 2.9 % lower (R113 15k from the resonance path also loads its input);
 *   - RES: VR18 100kB fed from the filter output (connector 75), wiper (76) -> TR26 phase splitter
 *     -> TR27 -> C52 -> R129 5.6k -> D30/D31 (1S2473) to the bias rail -> R113 15k -> stage-1 input;
 *   - output: R130 150k from the filter output + R132 150k from TR26's emitter (the wiper, unclipped) into
 *     the BA662 VCA, so out = y4 (1 + r) = y4 (1 + 0.202 k): the 101's own resonance level compensation.
 * Levels (drive, the diode level and knee, k against the slider) fitted to TAL-BassLine-101 captures with the
 * circuit kept as drawn. The host reference (double, 8x, exact Newton) and the fit live in the sh101-ref kit;
 * its device/compare.py checks this module against the reference.
 *
 * Structure after fm-106's fm106_vcf.h (PatttF/fm-106, GPL-3.0): TPT one-pole stages, a linear cascade
 * prediction resolved per sample, and the BA662/OTA Pade curve x (27 + x^2) / (27 + 9 x^2), here per stage.
 *
 * Solver (explicit, no division per sample, the fm-106 way): per block, each stage's TPT gain G = g/(1+g) and
 * the loop's 1/(1 + A k) (A = the cascade's gain). Per sample: a zero-delay linear prediction of the loop output,
 * the diodes from a table at that level, then the four stages, each with the tanh of its own argument
 * (x - y = (1 - G)(x - s)) by a 5th-order series. Checked against the exact solution (tests: pitch within
 * 4 cents to 8 kHz, levels within 0.05 dB).
 *
 * Interface:
 *   sh101_init()                         once at start: builds the diode and resonance tables
 *   sh101_coef(&c, cut, res)             per control block: cut Q8 semitones (MIDI note << 8, 0..136 << 8, the
 *                                        frequency the filter sings at), res Q8 0..(127 << 8) = slider 0..10
 *   sh101_panel_cut(knob)                the SH-101 FREQ slider: knob 0..127 -> cut (Q8), with the range limits
 *   sh101_panel_res(knob)                the RES slider: knob 0..127 -> res (Q8), up to SH101_RES_MAX, by SH101_RES_TAPER
 *   sh101_knob_cut(knob_q16)             as sh101_panel_cut, for a knob in Q16 (fractions, and beyond 0..127 when
 *                                        an envelope or key follow pushes it): the limits still hold
 *   sh101_reset(&s, seed)                at voice start (optional: the state is always bounded)
 *   y = sh101_process(&c, &s, x)         per sample, float: 1.0 = a full-scale oscillator in and out
 *   y = sh101_step(&c, &s, in)           per sample, int32: +-65536 = a full-scale oscillator (S1Vave's mix units)
 */
#ifndef SH101_VCF_H
#define SH101_VCF_H
#include <stdint.h>

#ifndef OBV_SH101_FS
#define OBV_SH101_FS 44100.0f
#endif

/* fitted parameters (sh101-ref fit_circuit/params.json, 2026-11-16) */
#ifndef SH101_DRIVE
#define SH101_DRIVE      0.19918f      /* stage units (Vs) per full-scale oscillator */
#endif
#ifndef SH101_CLIP
#define SH101_CLIP       0.51447f      /* D30/D31: level they conduct at (stage units) */
#endif
#ifndef SH101_CLIP_SHARP
#define SH101_CLIP_SHARP 8.7977f       /* knee: ln(2 clip / c) */
#endif
#ifndef SH101_FWD
#define SH101_FWD        0.202f        /* R130/R132: out = y4 (1 + fwd k), from the schematic */
#endif
#ifndef SH101_KMAX
#define SH101_KMAX       5.8657f       /* loop gain at RES 10 */
#endif
#ifndef SH101_RES_CURVE
#define SH101_RES_CURVE  1.14896f      /* k = kmax (RES/10)^curve */
#endif
#ifndef SH101_NOISE
#define SH101_NOISE      1.0e-4f       /* rms of the circuit noise at the input (stage units): starts oscillation */
#endif
/* cut -> pole frequency (Q8 semitones): the four poles sing at 0.99298 of the pole frequency; stage 1 is 1.0286x
 * lower (cap[0]) */
#define SH101_SING_Q8    31
#define SH101_STAGE1_Q8  125

/* panel (the SH-101's sliders, measured on TAL-BassLine-101: 1.2464 octaves per slider unit, singing at 268.4 Hz at
 * FREQ 5). Limits as in the Teensy VAFilterCore: the cutoff range and the highest resonance the knob reaches */
#ifndef SH101_CUT_MIN_HZ
#define SH101_CUT_MIN_HZ 7.0f          /* TAL-BassLine-101 sings down to ~7 Hz (FREQ 0: 7.2 Hz, FREQ 1: 8.5) */
#endif
#ifndef SH101_CUT_MAX_HZ
#define SH101_CUT_MAX_HZ 11550.0f      /* TAL at FREQ 10 */
#endif
#ifndef SH101_RES_MAX
#define SH101_RES_MAX    10.0f         /* the RES slider at knob 127 (10 = the 101's top; < 7.2 never self-oscillates) */
#endif
#ifndef SH101_RES_TAPER
#define SH101_RES_TAPER  1.0f          /* the RES knob's curve: slider = RES_MAX (knob/127)^taper. 1: the 101's linear
                                          slider (sings from knob 92 of 127); 2: from knob 108, more of the knob below */
#endif
#ifndef SH101_SING_TRIM
#define SH101_SING_TRIM  1.0f          /* output gain at full RES, eased in from where it starts to sing (k > SH101_KCRIT):
                                          1 = the circuit (it sings +5.6 dB over a full oscillator: right for a mono synth,
                                          hot for 8 voices); M-Vsynth2 uses 0.4 (-8 dB), level with Synth1's LP24 */
#endif
#define SH101_KCRIT      4.0006f       /* the loop gain where the four poles (stage 1 2.9 % lower) start to sing */
#define SH101_CUT_OCT    1.2464f
#define SH101_CUT_HZ5    268.4f

#define SH101_DTAB_N     256           /* diode table: v/w for |w| in [0, SH101_DTAB_W] */
#define SH101_DTAB_W     8.0f

typedef struct { float g[4], G[4], h[4], A, inv, k, outg; int32_t cut, res; uint32_t valid; } sh101_coef_t;  /* h = 1 - G */
typedef struct { float s[4]; uint32_t rng; } sh101_state_t;

static float SH101_DTAB[SH101_DTAB_N + 2];   /* v / w */
static float SH101_KTAB[129];                /* k at res = i (0..127), [128] = [127] */
static int32_t SH101_RTAB[128];              /* the RES knob 0..127 -> res (Q8), SH101_RES_MAX and SH101_RES_TAPER */

/* ---- float helpers (init time only: no libm on the device) */
static inline float sh101_exp2f(float x)            /* 2^x, |x| < 126, rel. error ~2e-7 */
{
    union { float f; int32_t i; } u;
    int32_t n = (int32_t)(x >= 0.0f ? x : x - 1.0f);
    float f = x - (float)n, p;
    p = 1.0f + f * (0.693147181f + f * (0.240226507f + f * (0.0555041087f + f * (0.00961812911f
        + f * (0.00133335581f + f * 0.000154035304f)))));
    u.i = (n + 127) << 23;
    return p * u.f;
}

static inline float sh101_log2f(float x)            /* x > 0, abs. error ~1e-6 */
{
    union { float f; int32_t i; } u = { x };
    float e = (float)(((u.i >> 23) & 255) - 127), m, t, t2;
    u.i = (u.i & 0x007FFFFF) | 0x3F800000;   /* m in [1, 2) */
    m = u.f;
    t = (m - 1.0f) / (m + 1.0f);
    t2 = t * t;
    return e + 2.885390082f * t * (1.0f + t2 * (0.333333333f + t2 * (0.2f + t2 * (0.142857143f + t2 * 0.111111111f))));
}

/* tan(pi f / fs) at Q8 semitones, f capped at 0.45 fs (as SVF_G): a float table would be 137 entries; computed
 * per block from sin/cos series instead, since it only runs once per block per voice */
static inline float sh101_g_q8(int32_t q8)
{
    float f = 440.0f * sh101_exp2f(((float)q8 * (1.0f / 256.0f) - 69.0f) * (1.0f / 12.0f));
    float x, x2, s, c;
    if (f > 0.45f * OBV_SH101_FS) f = 0.45f * OBV_SH101_FS;
    x = 3.14159265f * f / OBV_SH101_FS;      /* <= 1.414 */
    x2 = x * x;
    s = x * (1.0f - x2 * (1.0f / 6.0f - x2 * (1.0f / 120.0f - x2 * (1.0f / 5040.0f - x2 * (1.0f / 362880.0f)))));
    c = 1.0f - x2 * (0.5f - x2 * (1.0f / 24.0f - x2 * (1.0f / 720.0f - x2 * (1.0f / 40320.0f - x2 * (1.0f / 3628800.0f)))));
    return s / c;
}

static inline void sh101_init(void)
{
    const float vd = SH101_CLIP / SH101_CLIP_SHARP;
    const float c = 2.0f * SH101_CLIP * sh101_exp2f(-SH101_CLIP_SHARP * 1.442695041f);
    int32_t i, it;
    float v = 0.0f;
    /* D30/D31: v + c sinh(v / vd) = w (Newton, continued from the previous point) */
    for (i = 0; i <= SH101_DTAB_N + 1; i++) {
        float w = (float)i * (SH101_DTAB_W / SH101_DTAB_N);
        for (it = 0; it < 40; it++) {
            float ex = sh101_exp2f(v / vd * 1.442695041f), ix = 1.0f / ex;
            float r = v + c * 0.5f * (ex - ix) - w, d = 1.0f + c / vd * 0.5f * (ex + ix);
            float dv = r / d;
            if (dv > 0.05f) dv = 0.05f;
            v -= dv;
            if (dv < 1e-7f && dv > -1e-7f) break;
        }
        SH101_DTAB[i] = i ? v / w : 1.0f / (1.0f + c / vd);
    }
    /* RES slider 0..127 -> k */
    SH101_KTAB[0] = 0.0f;
    for (i = 1; i < 128; i++)
        SH101_KTAB[i] = SH101_KMAX * sh101_exp2f(SH101_RES_CURVE * sh101_log2f((float)i / 127.0f));
    SH101_KTAB[128] = SH101_KTAB[127];
    /* the RES knob: slider 0..RES_MAX by its taper, on the 0..127 (= 0..10) res scale */
    SH101_RTAB[0] = 0;
    for (i = 1; i < 128; i++)
        SH101_RTAB[i] = (int32_t)(127.0f * 256.0f * (SH101_RES_MAX / 10.0f)
                                  * sh101_exp2f(SH101_RES_TAPER * sh101_log2f((float)i / 127.0f)));
}

/* per control block. cut: Q8 semitones (0..136 << 8) where the filter sings; res: Q8 slider (0..127 << 8) */
static inline void sh101_coef(sh101_coef_t *c, int32_t cut, int32_t res)
{
    int32_t i, q = cut + SH101_SING_Q8;
    float t, k;
    if (res < 0) res = 0;
    if (res > (127 << 8)) res = 127 << 8;
    if (c->valid && cut == c->cut && res == c->res) return;   /* unchanged since the last block */
    c->valid = 1;
    c->cut = cut;
    c->res = res;
    c->g[0] = sh101_g_q8(q - SH101_STAGE1_Q8);
    c->g[1] = c->g[2] = c->g[3] = sh101_g_q8(q);
    c->A = 1.0f;
    for (i = 0; i < 4; i++) {
        c->G[i] = c->g[i] / (1.0f + c->g[i]);
        c->h[i] = 1.0f - c->G[i];
        c->A *= c->G[i];
    }
    i = res >> 8;
    t = (float)(res & 255) * (1.0f / 256.0f);
    k = SH101_KTAB[i] + (SH101_KTAB[i + 1] - SH101_KTAB[i]) * t;
    c->k = k;
    c->inv = 1.0f / (1.0f + c->A * k);
    c->outg = (1.0f + SH101_FWD * k) * (1.0f / SH101_DRIVE);
    if (SH101_SING_TRIM != 1.0f && k > SH101_KCRIT) {           /* singing: ease the output to the trim at full RES */
        t = (k - SH101_KCRIT) / (SH101_KTAB[127] - SH101_KCRIT);
        c->outg *= 1.0f - (1.0f - SH101_SING_TRIM) * (t > 1.0f ? 1.0f : t);
    }
}

/* the FREQ slider: knob (Q16, 0..127 << 16) -> cut (Q8 semitones where it sings), exponential, within the limits */
static inline int32_t sh101_knob_cut(int32_t knob_q16)
{
    /* semitones = 69 + 12 log2(268.4/440) + 12 * 1.2464 * (10 knob/127 - 5): linear in the knob */
    const float s0 = 69.0f - 8.55696f - 12.0f * SH101_CUT_OCT * 5.0f;
    const float ds = 12.0f * SH101_CUT_OCT * 10.0f / 127.0f;
    float st = s0 + ds * (float)knob_q16 * (1.0f / 65536.0f);
    float lo = 69.0f + 12.0f * sh101_log2f(SH101_CUT_MIN_HZ / 440.0f);
    float hi = 69.0f + 12.0f * sh101_log2f(SH101_CUT_MAX_HZ / 440.0f);
    if (st < lo) st = lo;
    if (st > hi) st = hi;
    return (int32_t)(st * 256.0f);
}

/* the FREQ slider: knob 0..127 -> cut (Q8 semitones where it sings) */
static inline int32_t sh101_panel_cut(int32_t knob)
{
    return sh101_knob_cut(knob << 16);
}

/* the RES knob 0..127 -> res (Q8 on the 0..127 = 0..10 scale): up to SH101_RES_MAX, curved by SH101_RES_TAPER */
static inline int32_t sh101_panel_res(int32_t knob)
{
    return SH101_RTAB[knob < 0 ? 0 : knob > 127 ? 127 : knob];
}

static inline void sh101_reset(sh101_state_t *s, uint32_t seed)
{
    int32_t i;
    for (i = 0; i < 4; i++) s->s[i] = 0.0f;
    s->rng = seed | 1u;
}

static inline __attribute__((always_inline)) float sh101_diode_v(float w)   /* the diodes' voltage at loop level w */
{
    float a = w < 0.0f ? -w : w, p, v;
    int32_t i;
    if (a >= SH101_DTAB_W) {
        v = SH101_DTAB[SH101_DTAB_N] * SH101_DTAB_W;   /* beyond the table: held (the diodes' log rise is tiny) */
    } else {
        p = a * (SH101_DTAB_N / SH101_DTAB_W);
        i = (int32_t)p;
        v = a * (SH101_DTAB[i] + (SH101_DTAB[i + 1] - SH101_DTAB[i]) * (p - (float)i));
    }
    return w < 0.0f ? -v : v;
}

/* tanh(t) for |t| <= 1 (5th order), held at |t| = 1 beyond: the stages' OTA curve at this drive */
static inline __attribute__((always_inline)) float sh101_tanh5(float t)
{
    float t2;
    if (t > 1.0f) t = 1.0f;
    if (t < -1.0f) t = -1.0f;
    t2 = t * t;
    return t * (1.0f - t2 * (1.0f / 3.0f - t2 * (2.0f / 15.0f)));
}

/* one sample, float: x and the result in oscillator units (1.0 = a full-scale oscillator) */
static inline __attribute__((always_inline)) float sh101_process(const sh101_coef_t *c, sh101_state_t *s, float x)
{
    float B, y4, u, d, y;   /* (no division per sample) */
    int32_t i;
    s->rng = s->rng * 1664525u + 1013904223u;      /* uniform noise, rms SH101_NOISE */
    x = x * SH101_DRIVE + (float)(int32_t)s->rng * (SH101_NOISE * 1.7320508f / 2147483648.0f);
    /* linear stages: y_i = G x_i + (1 - G) s_i, so the cascade is y4 = A x1 + B */
    B = ((c->h[0] * s->s[0] * c->G[1] + c->h[1] * s->s[1]) * c->G[2] + c->h[2] * s->s[2]) * c->G[3] + c->h[3] * s->s[3];
    y4 = (c->A * x + B) * c->inv;                   /* zero-delay prediction of the loop (diodes not conducting) */
    u = x - sh101_diode_v(c->k * y4);               /* the feedback through the diodes */
    for (i = 0; i < 4; i++) {
        /* TPT stage: y = s + G d, d = tanh(x - y) / (1 - G), x - y = (1 - G)(x - s); G / (1 - G) = g */
        d = c->g[i] * sh101_tanh5(c->h[i] * (u - s->s[i]));
        y = s->s[i] + d;
        s->s[i] = y + d;
        u = y;
    }
    return u * c->outg;
}

/* one sample, int32: in and the result in mix units (+-65536 = a full-scale oscillator) */
static inline __attribute__((always_inline)) int32_t sh101_step(const sh101_coef_t *c, sh101_state_t *s, int32_t in)
{
    float y = sh101_process(c, s, (float)in * (1.0f / 65536.0f)) * 65536.0f;
    if (y > 2147483520.0f) y = 2147483520.0f;
    if (y < -2147483520.0f) y = -2147483520.0f;
    return (int32_t)y;
}

#endif
