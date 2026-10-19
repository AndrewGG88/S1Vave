/* SPDX-License-Identifier: GPL-3.0-only */
/* The effects after the output stage: a stereo chorus, a ping-pong delay in note values of the tempo, and a
 * plate reverb (J. Dattorro's figure-of-eight tank, 1997). All lines are int16 in one .pool buffer; the
 * signals are Q15 as the output stage leaves them. Integers only.
 * REV_DIV 1: the reverb at the full rate (the sound comes first). 2: at half the rate, if the chip turns out
 * to need it: a dark hall loses little by it and it halves the reverb's time and memory. */
#ifndef REV_DIV
#define REV_DIV 1u
#endif
#define RVL(x) ((uint32_t)((x) * 44100u / 29761u / REV_DIV))   /* the paper's 29761 Hz lengths at our rate */
#define DLY_MAX 32768u                          /* a side of the delay: 743 ms */
#define CHO_N 1024u
#define REV_PRE_N (8192u / REV_DIV)             /* up to 120 ms of pre-delay */
#define RV_IN1 RVL(142)
#define RV_IN2 RVL(107)
#define RV_IN3 RVL(379)
#define RV_IN4 RVL(277)
#define RV_AP1 RVL(672)
#define RV_D1 RVL(4453)
#define RV_AP2 RVL(1800)
#define RV_D2 RVL(3720)
#define RV_AP3 RVL(908)
#define RV_D3 RVL(4217)
#define RV_AP4 RVL(2656)
#define RV_D4 RVL(3163)
#define REV_N (REV_PRE_N + RV_IN1 + RV_IN2 + RV_IN3 + RV_IN4 + RV_AP1 + 16u + RV_D1 + RV_AP2 + RV_D2 + RV_AP3 + 16u + RV_D3 + RV_AP4 + RV_D4)
#define RV_BW (REV_DIV == 2u ? 24000 : 16700)   /* the input's one-pole: ~5 kHz either way */
#define FX_MEM_N (CHO_N + 2u * DLY_MAX + REV_N)

typedef struct { int16_t *b; uint32_t len, w; } line_t;   /* w: where the next sample goes */
static int16_t fx_mem[FX_MEM_N] __attribute__((section(".pool")));
static uint32_t fx_used;

static inline int32_t sat16(int32_t v) { return v > 32767 ? 32767 : v < -32767 ? -32767 : v; }
static void line_init(line_t *l, uint32_t len) { l->b = fx_mem + fx_used; l->len = len; l->w = 0; fx_used += len; }
static inline __attribute__((always_inline)) int32_t line_read(const line_t *l, uint32_t back)   /* 1 <= back <= len */
{
    if (back > l->len) back = l->len;
    if (back < 1u) back = 1u;
    uint32_t i = l->w + l->len - back;
    if (i >= l->len) i -= l->len;
    return l->b[i];
}
static inline __attribute__((always_inline)) void line_write(line_t *l, int32_t v)
{
    l->b[l->w] = (int16_t)sat16(v);
    if (++l->w >= l->len) l->w = 0;
}
/* Dattorro's allpass: the line holds the inner node, the output is tapped from it. g Q15, signed */
static inline __attribute__((always_inline)) int32_t ap_step(line_t *l, int32_t in, int32_t g)
{
    int32_t d = line_read(l, l->len), v = in - ((d * g) >> 15);
    line_write(l, v);
    return d + ((v * g) >> 15);
}
/* the same with the delay swaying by e (Q8 samples, |e| <= 8 << 8) around base; the line is base + 16 long */
static inline __attribute__((always_inline)) int32_t ap_mod(line_t *l, int32_t in, int32_t g, uint32_t base, int32_t e)
{
    uint32_t back = (uint32_t)((int32_t)base + (e >> 8));
    int32_t f = e & 255, a = line_read(l, back), b = line_read(l, back + 1u), d = a + (((b - a) * f) >> 8), v;
    v = in - ((d * g) >> 15);
    line_write(l, v);
    return d + ((v * g) >> 15);
}
static inline int32_t tri_q(uint32_t ph)        /* a triangle -2048..2047 (so Q8 = +-8 samples) */
{
    int32_t t = (int32_t)(ph >> 19);            /* 0..8191 */
    return t < 4096 ? t - 2048 : 6143 - t;
}

/* ---- the state */
static line_t cho, dl, dr, rv_pre, rv_in[4], rv_ap1, rv_d1, rv_ap2, rv_d2, rv_ap3, rv_d3, rv_ap4, rv_d4;
static uint32_t cho_ph, cho_inc, rv_ph1, rv_ph2, rv_ph_inc1 = 97391u * REV_DIV, rv_ph_inc2 = 68174u * REV_DIV;
static int32_t cho_depth_k, cho_mix, dly_mix, rev_mix, dly_fb, dly_tone_k, rev_decay, rev_damp_k, rev_bw = 16700, rev_mod_scale = 256;
static int32_t dly_time, dly_cur;               /* Q16 samples: the target and where the read is (it slews like a tape) */
static int32_t dly_lpl, dly_lpr, rv_lp_in, rv_lpl, rv_lpr, rv_yl, rv_yr;
#if REV_DIV == 2u
static int32_t rv_hold;
#endif
static uint32_t rev_pre_n = 1, dly_active, rev_active;
#if REV_DIV == 2u
static uint32_t fx_odd;
#endif

static void fx_init(void)
{
    line_init(&cho, CHO_N);
    line_init(&dl, DLY_MAX);
    line_init(&dr, DLY_MAX);
    line_init(&rv_pre, REV_PRE_N);
    line_init(&rv_in[0], RV_IN1); line_init(&rv_in[1], RV_IN2); line_init(&rv_in[2], RV_IN3); line_init(&rv_in[3], RV_IN4);
    line_init(&rv_ap1, RV_AP1 + 16u); line_init(&rv_d1, RV_D1); line_init(&rv_ap2, RV_AP2); line_init(&rv_d2, RV_D2);
    line_init(&rv_ap3, RV_AP3 + 16u); line_init(&rv_d3, RV_D3); line_init(&rv_ap4, RV_AP4); line_init(&rv_d4, RV_D4);
    dly_cur = dly_time = 11025 << 16;
}

/* the patch's numbers, once per ISR call. quarter: frames per quarter note (the arp's clock) */
static void fx_block(const patch_t *p, uint32_t quarter)
{
    int32_t d;
    uint32_t div = p->v[P_DLY_TIME] % NDDIV, samples;
    uint32_t cho_m = p->v[P_CHO_MODE];

    /* Chorus 4 modes */
    switch (cho_m) {
    case CHO_TYPE1:
        cho_mix = 70;
        cho_inc = 50u * 974u;   /* ~0.5 Hz */
        cho_depth_k = 35 * 67;
        break;
    case CHO_TYPE2:
        cho_mix = 85;
        cho_inc = 120u * 974u;  /* ~1.2 Hz */
        cho_depth_k = 50 * 67;
        break;
    case CHO_TYPE3:
        cho_mix = 95;
        cho_inc = 400u * 974u;  /* ~4.0 Hz */
        cho_depth_k = 25 * 67;
        break;
    case CHO_TYPE4:
        cho_mix = 80;
        cho_inc = 30u * 974u;   /* ~0.3 Hz */
        cho_depth_k = 65 * 67;
        break;
    default:
        cho_mix = 0;
        cho_inc = 0;
        cho_depth_k = 0;
        break;
    }

    dly_mix = (p->v[P_DLY_LVL] * 180) >> 7;     /* wet up to 0.7 of the dry (Q8): the sum stays in range */
    rev_mix = (p->v[P_REV_LVL] * 150) >> 7;
    dly_fb = p->v[P_DLY_FB] * 250;              /* up to 0.97 */
    dly_tone_k = 128;                           /* tone damping */

    /* Roland S-1 Reverb Profiles: Amb, Room, Hall1, Hall2, Plate, Spring, Mod */
    {
        uint32_t rev_m = p->v[P_REV_TYPE];
        int32_t bw, damp, dec_base, dec_range, mod_scale;
        uint32_t inc1, inc2;

        switch (rev_m) {
        case REV_AMB:    /* 0: Ambience - tight small space, heavy damping, fast decay */
            bw = (REV_DIV == 2u ? 20000 : 13500);  /* ~3.8 kHz */
            damp = 85;                             /* heavy high-cut */
            dec_base = 5600; dec_range = 11200;    /* 80% of original (max ~16800) */
            mod_scale = 180;
            inc1 = 70000u * REV_DIV; inc2 = 50000u * REV_DIV;
            break;
        case REV_ROOM:   /* 1: Room - natural room acoustic */
            bw = (REV_DIV == 2u ? 24000 : 16700);  /* ~5.0 kHz */
            damp = 65;                             /* moderate natural damping */
            dec_base = 8000; dec_range = 14000;    /* 80% of original (max ~22000) */
            mod_scale = 220;
            inc1 = 90000u * REV_DIV; inc2 = 64000u * REV_DIV;
            break;
        case REV_HALL1:  /* 2: Hall 1 - warm concert hall, smooth decay */
        default:
            bw = (REV_DIV == 2u ? 26000 : 18500);  /* ~6.0 kHz */
            damp = 50;                             /* gentle warm damping */
            dec_base = 9600; dec_range = 15600;    /* 80% of original (max ~25200) */
            mod_scale = 240;
            inc1 = 97391u * REV_DIV; inc2 = 68174u * REV_DIV;
            break;
        case REV_HALL2:  /* 3: Hall 2 - bright cavernous arena, expansive tail */
            bw = (REV_DIV == 2u ? 29000 : 22000);  /* ~8.0 kHz */
            damp = 36;                             /* low damping, airy */
            dec_base = 10000; dec_range = 15600;   /* 80% of original (max ~25600) */
            mod_scale = 240;
            inc1 = 97391u * REV_DIV; inc2 = 68174u * REV_DIV;
            break;
        case REV_PLATE:  /* 4: Plate - dense metallic plate, sparkling highs */
            bw = (REV_DIV == 2u ? 31500 : 25500);  /* ~11 kHz, wide open */
            damp = 26;                             /* metallic brightness */
            dec_base = 10400; dec_range = 15200;   /* 80% of original (max ~25600) */
            mod_scale = 160;                       /* subtle flutter */
            inc1 = 120000u * REV_DIV; inc2 = 85000u * REV_DIV;
            break;
        case REV_SPRING: /* 5: Spring - boomy lows, dark treble, fast flutter bounce */
            bw = (REV_DIV == 2u ? 16000 : 10500);  /* ~2.8 kHz, dark spring */
            damp = 92;                             /* very heavy damping */
            dec_base = 7200; dec_range = 13200;    /* 80% of original (max ~20400) */
            mod_scale = 200;
            inc1 = 280000u * REV_DIV; inc2 = 205000u * REV_DIV; /* fast flutter chirp */
            break;
        case REV_MOD:    /* 6: Modulated - Roland signature lush chorused shimmer */
            bw = (REV_DIV == 2u ? 27000 : 19500);  /* ~6.5 kHz */
            damp = 40;                             /* clear luminous highs */
            dec_base = 11200; dec_range = 14000;   /* 80% of original, max ~25200 ~2.5s lush tail, no runaway */
            mod_scale = 280;                       /* chorused pitch swirl */
            inc1 = 52000u * REV_DIV; inc2 = 37000u * REV_DIV;   /* slow undulating sweep */
            break;
        }

        rev_bw = bw;
        rev_mod_scale = mod_scale;
        rv_ph_inc1 = inc1;
        rv_ph_inc2 = inc2;

        d = p->v[P_REV_TIME];
        rev_decay = dec_base + ((d * d * dec_range) >> 14);
        rev_damp_k = 32768 - damp * damp * 2;
        if (REV_DIV == 1u) {                        /* the same corner at the full rate: k' = 1 - sqrt(1 - k) */
            uint32_t x = (uint32_t)(32768 - rev_damp_k) << 15, r = 0, bit = 1u << 15;
            for (; bit; bit >>= 1)
                if ((r + bit) * (r + bit) <= x) r += bit;
            rev_damp_k = 32768 - (int32_t)r;
        }
    }
    rev_pre_n = 1u + (uint32_t)p->v[P_REV_PRE] * (41u / REV_DIV);
    if (rev_pre_n >= REV_PRE_N) rev_pre_n = REV_PRE_N - 1u;
    if (p->v[P_DLY_SYNC]) {
        samples = quarter * DDIV_NUM[div] / DDIV_DEN[div];
    } else {
        samples = (uint32_t)p->v[P_DLY_TIME] * (DLY_MAX / 128u);
    }
    if (samples > DLY_MAX - 4u) samples = DLY_MAX - 4u;
    if (samples < 64u) samples = 64u;
    dly_time = (int32_t)(samples << 16);
    if (dly_mix) dly_active = 12u * FS; else if (dly_active > HALF_FRAMES) dly_active -= HALF_FRAMES; else dly_active = 0;
    if (rev_mix) rev_active = 24u * FS; else if (rev_active > HALF_FRAMES) rev_active -= HALF_FRAMES; else rev_active = 0;
}

static inline __attribute__((always_inline)) int32_t line_read_q16(const line_t *l, int32_t back_q16)
{
    if (back_q16 < 0) back_q16 = 0;
    uint32_t b = (uint32_t)back_q16 >> 16;
    int32_t f = (back_q16 >> 8) & 255, a = line_read(l, b), c = line_read(l, b + 1u);
    return a + (((c - a) * f) >> 8);
}
/* 4-point Hermite for a tap that is always moving (the chorus): no treble loss between the samples */
static inline __attribute__((always_inline)) int32_t line_read_q16_h(const line_t *l, int32_t back_q16)
{
    if (back_q16 < (1 << 16)) back_q16 = 1 << 16;
    uint32_t b = (uint32_t)back_q16 >> 16;
    if (b + 2u >= l->len) b = l->len - 3u;
    int32_t f = (back_q16 >> 8) & 255, p0 = line_read(l, b - 1u), p1 = line_read(l, b), p2 = line_read(l, b + 1u), p3 = line_read(l, b + 2u);
    int32_t c1 = (p2 - p0) >> 1, c2 = p0 - ((5 * p1) >> 1) + 2 * p2 - (p3 >> 1), c3 = ((p3 - p0) >> 1) + ((3 * (p1 - p2)) >> 1);
    return p1 + ((f * (c1 + ((f * (c2 + ((f * c3) >> 8))) >> 8))) >> 8);
}

/* one reverb sample at the half rate: in -> pre-delay -> bandwidth -> 4 diffusers -> the two tank halves */
static inline void rev_tick(int32_t in)
{
    int32_t x, a, b;
    int32_t e1 = (tri_q(rv_ph1) * rev_mod_scale) >> 8;
    int32_t e2 = (tri_q(rv_ph2) * rev_mod_scale) >> 8;
    int32_t dec = rev_decay, dk = rev_damp_k;
    rv_ph1 += rv_ph_inc1;
    rv_ph2 += rv_ph_inc2;
    line_write(&rv_pre, in);
    x = line_read(&rv_pre, rev_pre_n);
    rv_lp_in += ((x - rv_lp_in) * rev_bw) >> 15;
    x = ap_step(&rv_in[0], rv_lp_in, 24576);
    x = ap_step(&rv_in[1], x, 24576);
    x = ap_step(&rv_in[2], x, 20480);
    x = ap_step(&rv_in[3], x, 20480);
    /* left half, fed by the right's end */
    a = x + ((line_read(&rv_d4, RV_D4) * dec) >> 15);
    a = ap_mod(&rv_ap1, a, -22938, RV_AP1, e1);
    line_write(&rv_d1, a);
    b = line_read(&rv_d1, RV_D1);
    rv_lpl += ((b - rv_lpl) * dk) >> 15;
    b = ap_step(&rv_ap2, (rv_lpl * dec) >> 15, 16384);
    line_write(&rv_d2, b);
    /* right half, fed by the left's end */
    a = x + ((line_read(&rv_d2, RV_D2) * dec) >> 15);
    a = ap_mod(&rv_ap3, a, -22938, RV_AP3, e2);
    line_write(&rv_d3, a);
    b = line_read(&rv_d3, RV_D3);
    rv_lpr += ((b - rv_lpr) * dk) >> 15;
    b = ap_step(&rv_ap4, (rv_lpr * dec) >> 15, 16384);
    line_write(&rv_d4, b);
    /* the output taps (the paper's), x 0.6 */
    a = line_read(&rv_d3, RVL(266)) + line_read(&rv_d3, RVL(2974)) - line_read(&rv_ap4, RVL(1913)) + line_read(&rv_d4, RVL(1996))
      - line_read(&rv_d1, RVL(1990)) - line_read(&rv_ap2, RVL(187)) - line_read(&rv_d2, RVL(1066));
    b = line_read(&rv_d1, RVL(353)) + line_read(&rv_d1, RVL(3627)) - line_read(&rv_ap2, RVL(1228)) + line_read(&rv_d2, RVL(2673))
      - line_read(&rv_d3, RVL(2111)) - line_read(&rv_ap4, RVL(335)) - line_read(&rv_d4, RVL(121));
    rv_yl = (a * 19661) >> 15;
    rv_yr = (b * 19661) >> 15;
}

static void fx_process(int32_t *out, uint32_t n)
{
    uint32_t i, do_dly = dly_active != 0, do_rev = rev_active != 0;
    int32_t cm = cho_mix, dm = dly_mix, rm = rev_mix;
    for (i = 0; i < n; i++) {
        int32_t l = out[2u * i], r = out[2u * i + 1u];
        if (cm) {                               /* two taps a quarter turn apart on one line, around 12 ms */
            int32_t bl = (529 << 16) + tri_q(cho_ph) * cho_depth_k, br = (529 << 16) + tri_q(cho_ph + 0x40000000u) * cho_depth_k;
            cho_ph += cho_inc;
            line_write(&cho, (l + r) >> 1);
            l += ((line_read_q16_h(&cho, bl) - l) * cm) >> 8;
            r += ((line_read_q16_h(&cho, br) - r) * cm) >> 8;
        }
        if (do_dly) {                           /* ping-pong: the input enters left, the feedback crosses */
            int32_t wl, wr;
            if (dly_cur < dly_time) { dly_cur += 1 << 15; if (dly_cur > dly_time) dly_cur = dly_time; }
            else if (dly_cur > dly_time) { dly_cur -= 1 << 15; if (dly_cur < dly_time) dly_cur = dly_time; }
            wl = line_read_q16(&dl, dly_cur);
            wr = line_read_q16(&dr, dly_cur);
            dly_lpl += ((wr - dly_lpl) * dly_tone_k) >> 8;
            dly_lpr += ((wl - dly_lpr) * dly_tone_k) >> 8;
            line_write(&dl, ((l + r) >> 1) + ((dly_lpl * dly_fb) >> 15));
            line_write(&dr, (dly_lpr * dly_fb) >> 15);
            l += (wl * dm) >> 8;
            r += (wr * dm) >> 8;
        }
        if (do_rev) {
#if REV_DIV == 2u                               /* half rate: a pair in, the output interpolated between ticks */
            int32_t pl = rv_yl, pr = rv_yr, din = l + r;
            if (!(fx_odd ^= 1u)) {
                rev_tick((rv_hold + din) >> 2);
                l += (((pl + rv_yl) >> 1) * rm) >> 8;
                r += (((pr + rv_yr) >> 1) * rm) >> 8;
            } else {
                l += (rv_yl * rm) >> 8;
                r += (rv_yr * rm) >> 8;
            }
            rv_hold = din;
#else
            rev_tick((l + r) >> 1);
            l += (rv_yl * rm) >> 8;
            r += (rv_yr * rm) >> 8;
#endif
        }
        out[2u * i] = sat16(l);
        out[2u * i + 1u] = sat16(r);
    }
}
