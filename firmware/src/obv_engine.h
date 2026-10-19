/* SPDX-License-Identifier: GPL-3.0-only */
/* S-Vave Voice Architecture & Sound Engine: 4-Voice Polyphonic Roland S-1 Emulation.
 * Audio ISR (44.1 kHz, 256 frames). Fixed-point integer DSP for JieLi AC791N RISC MCU. */

#ifndef OBV_ENGINE_H
#define OBV_ENGINE_H

#ifndef RING_PUBLISH
#define RING_PUBLISH() __asm__ volatile("" ::: "memory")
#endif

#define NV 8u                                   /* 8-voice polyphony matching extended architecture */
#define NHELD 16u
#define ENV_ONE (1 << 24)
#define LEVEL_FLOOR 2048                        /* -78 dB: frees releasing voice */

enum { E_IDLE, E_ATT, E_DEC, E_SUS, E_REL };
typedef struct { uint32_t stage; int32_t level; } env_t;   /* level Q24 */

typedef struct {
    osc_t o_sqr;                                /* Square / Pulse / DRAW oscillator */
    osc_t o_saw;                                /* Sawtooth oscillator */
    osc_t o_sub;                                /* Sub-oscillator */
    pink_noise_t pn;                            /* Pink noise state */
    uint32_t noise;                             /* PRNG seed per voice */
    env_t fe, ae;                               /* Filter and amp envelopes */
    svf_state_t f1, f2;                         /* 4-pole cascaded SVF stages */
    svf_coef_t c1, c2;
    uint32_t inc, pw;                           /* Phase step & pulse width */
    int32_t amp0, amp1;                         /* Q15 amplitude slew */
    int32_t pitch16, target16;                  /* Q16 semitones: glide */
    int32_t det8;                               /* Unison / chord offset in Q8 */
    int32_t gl, gr;                             /* Stereo pan gains Q12 */
    int32_t drift;                              /* Analog vintage drift */
    int32_t bass_lp;                            /* 1-pole analog low-end warmth tracker */
    uint32_t lfo_blk;                           /* Blocks since note-on */
    int32_t lfo_fade;                           /* Q15 */
    uint32_t seq;                               /* Allocation age */
    uint8_t note, vel, gate;
    uint8_t part;                               /* 0: Sound A, 1: Track B sound */
    uint8_t chord_idx;                          /* 0=Voice 1, 1=Voice 2, 2=Voice 3, 3=Voice 4 */
} voice_t;

/* Two sounds: Sound A (main) and Track B's sound */
static patch_t live, live_b, live_bq;
static volatile uint32_t ctl_bq_swap;
static uint32_t b_own;
static voice_t vc[NV];
static uint32_t vseq, rr;

/* Sequencer accessor forward declarations */
static uint32_t seq_b_own(void);
static uint32_t seq_b_dry(void);
static void seq_tick(void);
static inline const int16_t *seq_draw_table(void);
static inline const uint16_t *seq_chop_masks(void);

/* Note Event FIFO */
typedef struct { uint8_t type, note, vel, part; } nev_t;
#define NQ 64u
static nev_t nq[NQ];
static volatile uint32_t nq_w, nq_r;

static void note_event_p(uint32_t part, uint32_t on, uint32_t note, uint32_t vel)
{
    if (nq_w - nq_r >= NQ) return;
    nq[nq_w % NQ].part = (uint8_t)part;
    nq[nq_w % NQ].type = (uint8_t)on;
    nq[nq_w % NQ].note = (uint8_t)note;
    nq[nq_w % NQ].vel = (uint8_t)vel;
    RING_PUBLISH();
    nq_w++;
}
static void note_event(uint32_t on, uint32_t note, uint32_t vel) { note_event_p(0, on, note, vel); }

/* Realtime Controllers */
static volatile int32_t ctl_bend;               /* -8192..8191 */
static volatile uint32_t ctl_sustain, ctl_hold, ctl_cc7 = 127;
#if BOARD_SMK37
static volatile int32_t ctl_vib;
#endif
static volatile int32_t ctl_tune8;              /* Master tune, Q8 */
static volatile uint32_t ctl_tempo = 120, ctl_ext_quarter;
static volatile uint32_t ctl_arp_restart, ctl_panic;
static volatile uint32_t ctl_arp_on;
static volatile uint32_t ctl_arp_type;
static volatile uint32_t ctl_arp_rate = 2;      /* 1/16 */
static volatile uint32_t ctl_note_pri;          /* 0=Last, 1=Low */

/* UI Telemetry (ISR -> Main Loop) */
static volatile int32_t ui_vlevel[NV];
static volatile uint8_t ui_vnote[NV];
static volatile uint32_t ui_render_us, ui_arp_step;
#define SCOPE_N 240u
static int16_t scope[SCOPE_N];
static volatile uint32_t scope_state, scope_stride = 4;

/* Held Notes List */
static struct { uint8_t note, vel, phys; } held[2][NHELD];
static uint32_t nheld[2];
static uint32_t rnd_state = 0x9E3779B9u;

/* Synthesis Part State */
typedef struct {
    const patch_t *p;
    uint32_t lfo_ph, lfo_rnd_a, lfo_rnd_b;
    int32_t lfo_val;
    int32_t last_pitch16;
    int32_t fenv_amt, keytrk, lfo_pd, lfo_fd, wheel_q, bend8, flt_bend8;
    int32_t lvl_sqr, lvl_saw, lvl_sub, lvl_noi, reso_k, vint, sus_f, sus_a, gain_q12;
    int32_t cut_sm, reso_sm;
    uint32_t pw_base, pwm_src, sub_type, noise_mode, draw_sw, draw_mult_q8;
    uint32_t chop_ovtn, chop_comb_q8;
    int32_t g_chop_masked;
    uint32_t poly_mode, porta_mode, glide_k;
    int32_t fine_tune8, range_semi8;
    /* Riser effect state */
    int32_t riser_sm, riser_reso_k, riser_shape, riser_lvl;
    uint32_t riser_mode, riser_ph;
} part_t;

static int32_t lfo_shape(const part_t *g, uint32_t ph, uint32_t shape);
static part_t pt[2] = {{&live, 0, 0, 0, 0, 60 << 16}, {&live, 0, 0, 0, 0, 60 << 16}};

static void parts_point(void)
{
    uint32_t was = b_own;
    b_own = seq_b_own();
    pt[1].p = b_own ? &live_b : &live;
    if (b_own && !was) {
        pt[1].cut_sm = live_b.v[P_CUTOFF] << 8;
        pt[1].reso_sm = live_b.v[P_RESO] << 8;
    }
}

static void held_remove(uint32_t p, uint32_t note)
{
    uint32_t i, j;
    for (i = j = 0; i < nheld[p]; i++)
        if (held[p][i].note != note) held[p][j++] = held[p][i];
    nheld[p] = j;
}

/* Vintage card offsets for 8 voices */
static const int16_t VINT_TUNE8[NV] = {-15, 12, -8, 14, -12, 10, -6, 16};
static const int16_t VINT_CUT8[NV]  = {-250, 200, -180, 220, -210, 190, -150, 240};
static const int8_t  VINT_ENV[NV]   = {8, -6, 10, -8, 6, -5, 9, -7};
static const int8_t  PAN_CARD[NV]   = {-54, 54, -28, 28, -42, 42, -14, 14};
static const int8_t  RANGE_SEMITONES[6] = {-24, -12, 0, 12, 24, 36};

static void voice_pan(voice_t *v, int32_t pan)
{
    uint32_t pos = (uint32_t)(clampi(pan, -64, 64) + 64);
    v->gl = PAN_Q12[128u - pos];
    v->gr = PAN_Q12[pos];
}

static void voice_start(voice_t *v, uint32_t part, uint32_t note, uint32_t vel, int32_t det8, int32_t pan, uint8_t c_idx)
{
    const uint8_t *pv = pt[part].p->v;
    v->part = (uint8_t)part;
    v->note = (uint8_t)note;
    v->vel = (uint8_t)vel;
    v->gate = 1;
    v->seq = ++vseq;
    v->det8 = det8;
    v->chord_idx = c_idx;
    v->target16 = (int32_t)note << 16;
    v->pitch16 = (pv[P_PORTA_MODE] == PORTA_ON && pv[P_PORTA_TIME]) ? pt[part].last_pitch16 : v->target16;
    v->fe.stage = E_ATT;
    v->ae.stage = E_ATT;
    v->bass_lp = 0;
    v->lfo_blk = 0;
    v->lfo_fade = 32767;
    voice_pan(v, pan);
}

/* Voice allocation for 4 polyphonic voices */
static uint32_t voice_alloc(uint32_t part)
{
    uint32_t i, v, pick = 0, best = 0xFFFFFFFFu;
    (void)part;
    /* 1. Prefer completely idle voices */
    for (i = 0; i < NV; i++) {
        v = (rr + i) % NV;
        if (vc[v].ae.stage == E_IDLE) { rr = (v + 1u) % NV; return v; }
    }
    /* 2. Prefer released voices */
    for (v = 0; v < NV; v++) {
        if (!vc[v].gate && vc[v].seq < best) { best = vc[v].seq; pick = v; }
    }
    /* 3. Steal oldest active voice */
    if (best == 0xFFFFFFFFu) {
        for (v = 0; v < NV; v++) {
            if (vc[v].seq < best) { best = vc[v].seq; pick = v; }
        }
    }
    rr = (pick + 1u) % NV;
    return pick;
}

/* Pair allocation for DUO mode (4 stereo pairs across 8 voices) */
static uint32_t pair_alloc(void)
{
    uint32_t p, best_seq = 0xFFFFFFFFu, pick = 0;
    /* 1. Prefer completely idle pair (both voices idle) */
    for (p = 0; p < 4; p++) {
        uint32_t v0 = p * 2;
        uint32_t v1 = v0 + 1;
        if (vc[v0].ae.stage == E_IDLE && vc[v1].ae.stage == E_IDLE) {
            return p;
        }
    }
    /* 2. Prefer released pair (both gates off) */
    for (p = 0; p < 4; p++) {
        uint32_t v0 = p * 2;
        uint32_t v1 = v0 + 1;
        if (!vc[v0].gate && !vc[v1].gate) {
            uint32_t s = (vc[v0].seq > vc[v1].seq) ? vc[v0].seq : vc[v1].seq;
            if (s < best_seq) {
                best_seq = s;
                pick = p;
            }
        }
    }
    if (best_seq != 0xFFFFFFFFu) return pick;

    /* 3. Steal oldest active pair */
    for (p = 0; p < 4; p++) {
        uint32_t v0 = p * 2;
        uint32_t v1 = v0 + 1;
        uint32_t s = (vc[v0].seq < vc[v1].seq) ? vc[v0].seq : vc[v1].seq;
        if (s < best_seq) {
            best_seq = s;
            pick = p;
        }
    }
    return pick;
}

static void voice_trigger(uint32_t part, uint32_t note, uint32_t vel)
{
    const uint8_t *pv = pt[part].p->v;
    uint32_t mode = pv[P_POLY_MODE];

    if (mode == POLY_POLY) {
        uint32_t v = voice_alloc(part);
        voice_start(&vc[v], part, note, vel, 0, PAN_CARD[v], 0);
    } else if (mode == POLY_PAN_NOTE) {
        uint32_t v = voice_alloc(part);
        int32_t pan = clampi(((int32_t)note - 60) * 2, -50, 50);
        voice_start(&vc[v], part, note, vel, 0, pan, 0);
    } else if (mode == POLY_MONO) {
        voice_t *v = &vc[0];
        int legato = v->gate;
        if (legato) {
            v->note = (uint8_t)note;
            v->target16 = (int32_t)note << 16;
            if (pv[P_PORTA_MODE] == PORTA_OFF) v->pitch16 = v->target16;
            if (pv[P_ENV_TRG] == TRIG_GATE_TRIG) {
                v->fe.stage = E_ATT;
                v->ae.stage = E_ATT;
            }
        } else {
            voice_start(v, part, note, vel, 0, 0, 0);
        }
    } else if (mode >= POLY_DUO && mode <= POLY_DUO_3) {
        /* Duo mode: 2 voices per note with wide stereo detune, allowing up to 4-note chords */
        static const int32_t DUO_DET[4] = {4, 10, 18, 30};
        uint32_t d_idx = mode - POLY_DUO;
        int32_t det = DUO_DET[d_idx];
        uint32_t p = pair_alloc();
        uint32_t v0 = p * 2;
        uint32_t v1 = v0 + 1;
        int32_t pan0 = (p & 1) ? 60 : -60;
        int32_t pan1 = (p & 1) ? -60 : 60;
        int32_t d0 = (p & 1) ? det : -det;
        int32_t d1 = (p & 1) ? -det : det;
        voice_start(&vc[v0], part, note, vel, d0, pan0, (uint8_t)v0);
        voice_start(&vc[v1], part, note, vel, d1, pan1, (uint8_t)v1);
        /* Phase offset for instant stereo chorusing */
        uint32_t u_ph = vc[v0].o_sqr.ph + 0x40000000u;
        vc[v1].o_sqr.ph = u_ph;
        vc[v1].o_saw.ph = u_ph;
        uint32_t u_sub = (pv[P_SUB_TYPE] % 3u == SUB_1OC) ? (u_ph >> 1) : (u_ph >> 2);
        vc[v1].o_sub.ph = u_sub + 0x40000000u;
    } else if (mode == POLY_UNISON) {
        /* 4 voices stacked with symmetric detuning & wide stereo spread (authentic Roland S-1) */
        int32_t det = 22;
        int32_t det_offsets[4] = {-det, -det / 3, det / 3, det};
        int32_t pan_offsets[4] = {-50, -18, 18, 50};
        uint32_t base_ph = vc[0].o_sqr.ph;
        for (uint32_t i = 0; i < 4; i++) {
            voice_start(&vc[i], part, note, vel, det_offsets[i], pan_offsets[i], (uint8_t)i);
            uint32_t u_ph = base_ph + i * 0x40000000u;
            vc[i].o_sqr.ph = u_ph;
            vc[i].o_saw.ph = u_ph;
            uint32_t u_sub = (pv[P_SUB_TYPE] % 3u == SUB_1OC) ? (u_ph >> 1) : (u_ph >> 2);
            vc[i].o_sub.ph = u_sub + i * 0x40000000u;
        }
        for (uint32_t i = 4; i < NV; i++) {
            vc[i].gate = 0;
        }
    } else if (mode == POLY_CHORD) {
        /* Chord mode: Voices 0..3 base chords, Voices 4..7 detuned stereo double */
        voice_start(&vc[0], part, note, vel, -3, PAN_CARD[0], 0);
        voice_start(&vc[4], part, note, vel,  3, PAN_CARD[4], 0);
        
        if (pv[P_CHORD_SW2]) {
            int32_t shift = (int32_t)pv[P_CHORD_KS2] - 12;
            uint32_t cn = (uint32_t)clampi((int32_t)note + shift, 0, 127);
            voice_start(&vc[1], part, cn, vel, -3, PAN_CARD[1], 1);
            voice_start(&vc[5], part, cn, vel,  3, PAN_CARD[5], 1);
        } else { vc[1].gate = 0; vc[5].gate = 0; }

        if (pv[P_CHORD_SW3]) {
            int32_t shift = (int32_t)pv[P_CHORD_KS3] - 12;
            uint32_t cn = (uint32_t)clampi((int32_t)note + shift, 0, 127);
            voice_start(&vc[2], part, cn, vel, -3, PAN_CARD[2], 2);
            voice_start(&vc[6], part, cn, vel,  3, PAN_CARD[6], 2);
        } else { vc[2].gate = 0; vc[6].gate = 0; }

        if (pv[P_CHORD_SW4]) {
            int32_t shift = (int32_t)pv[P_CHORD_KS4] - 12;
            uint32_t cn = (uint32_t)clampi((int32_t)note + shift, 0, 127);
            voice_start(&vc[3], part, cn, vel, -3, PAN_CARD[3], 3);
            voice_start(&vc[7], part, cn, vel,  3, PAN_CARD[7], 3);
        } else { vc[3].gate = 0; vc[7].gate = 0; }
    }
    pt[part].last_pitch16 = (int32_t)note << 16;
    if (pv[P_LFO_TRIG]) {
        pt[part].lfo_ph = 0;
        pt[part].lfo_val = lfo_shape(&pt[part], 0, pv[P_LFO_WAVE]);
    }
}

static void voice_release(uint32_t part, uint32_t note, uint32_t from_arp)
{
    const uint8_t *pv = pt[part].p->v;
    uint32_t v, mode = pv[P_POLY_MODE];

    if (mode == POLY_MONO && !from_arp) {
        if (nheld[part]) {
            /* Mono fallback to lowest held note (Lo-pri) or last note (Last-pri) */
            uint8_t fallback = held[part][0].note;
            if (ctl_note_pri == 1) {
                for (uint32_t i = 1; i < nheld[part]; i++) {
                    if (held[part][i].note < fallback) fallback = held[part][i].note;
                }
            } else {
                fallback = held[part][nheld[part] - 1u].note;
            }
            vc[0].note = fallback;
            vc[0].target16 = (int32_t)vc[0].note << 16;
            if (pv[P_PORTA_MODE] == PORTA_OFF) vc[0].pitch16 = vc[0].target16;
            pt[part].last_pitch16 = vc[0].target16;
        } else {
            vc[0].gate = 0;
        }
        return;
    }
    if (mode == POLY_UNISON || mode == POLY_CHORD) {
        for (v = 0; v < NV; v++) vc[v].gate = 0;
        return;
    }
    for (v = 0; v < NV; v++) {
        if (vc[v].gate && vc[v].note == note && vc[v].part == part) vc[v].gate = 0;
    }
}

static void voices_release_all(void)
{
    for (uint32_t v = 0; v < NV; v++) vc[v].gate = 0;
}

static void voices_release_part(uint32_t part)
{
    for (uint32_t v = 0; v < NV; v++)
        if (vc[v].part == part) vc[v].gate = 0;
}

/* Metronome Click */
static volatile uint32_t ctl_click, ctl_count, ui_seq_count;
static int32_t click_amp;
static uint32_t click_ph, click_inc;
static void click_start(uint32_t accent)
{
    click_amp = accent ? 9000 : 6000;
    click_ph = 0;
    click_inc = accent ? 233739600u : 155826400u;
}

/* Arpeggiator (Roland S-1 Arpeggio engine) */
typedef struct { uint32_t cnt, period, gate_at, pos, dir, sounding, note, was_on; } arp_t;
static arp_t arp[2];

#define AQ 32u
static uint8_t arp_q[AQ][3];
static volatile uint32_t arp_qw, arp_qr;
static void arp_post(uint32_t p, uint32_t on, uint32_t note)
{
    if (arp_qw - arp_qr >= AQ) return;
    arp_q[arp_qw % AQ][0] = (uint8_t)on;
    arp_q[arp_qw % AQ][1] = (uint8_t)note;
    arp_q[arp_qw % AQ][2] = (uint8_t)p;
    RING_PUBLISH();
    arp_qw++;
}

static void arp_stop_note(uint32_t p)
{
    arp_t *a = &arp[p];
    if (a->sounding) { voice_release(p, a->note, 1); a->sounding = 0; arp_post(p, 0, a->note); }
}

static void arp_step(uint32_t p)
{
    arp_t *a = &arp[p];
    uint8_t sorted[NHELD];
    uint32_t i, j, n = nheld[p];
    if (!n) return;
    for (i = 0; i < n; i++) sorted[i] = held[p][i].note;
    for (i = 1; i < n; i++) {
        uint8_t t = sorted[i];
        for (j = i; j && sorted[j - 1u] > t; j--) sorted[j] = sorted[j - 1u];
        sorted[j] = t;
    }
    uint32_t type = ctl_arp_type % NARP_TYPE;
    uint32_t oct = (type == ARP_UP_2OCT || type == ARP_DOWN_2OCT || type == ARP_UP_DOWN_2OCT || type == ARP_RANDOM_2OCT) ? 2u : 1u;
    uint32_t total = n * oct;
    uint32_t k;

    if (type == ARP_RANDOM || type == ARP_RANDOM_2OCT) {
        rnd_state = rnd_state * 1664525u + 1013904223u;
        k = (rnd_state >> 16) % total;
    } else if (type == ARP_UP || type == ARP_UP_2OCT) {
        k = a->pos % total;
        a->pos++;
    } else if (type == ARP_DOWN || type == ARP_DOWN_2OCT) {
        k = (total - 1u) - (a->pos % total);
        a->pos++;
    } else { /* ARP_UP_DOWN or ARP_UP_DOWN_2OCT */
        uint32_t cycle = total > 1u ? (total * 2u - 2u) : 1u;
        uint32_t step = a->pos % cycle;
        if (step < total) k = step;
        else k = total - 2u - (step - total);
        a->pos++;
    }

    uint32_t idx = k % n;
    uint32_t oct_shift = k / n;
    a->note = (uint32_t)clampi((int32_t)sorted[idx] + 12 * (int32_t)oct_shift, 0, 127);
    for (i = 0; i < n; i++)
        if (held[p][i].note == sorted[idx]) break;
    voice_trigger(p, a->note, i < n ? held[p][i].vel : 100u);
    arp_post(p, 1, a->note);
    a->sounding = 1;
    ui_arp_step++;
}

static void arp_tick(uint32_t p)
{
    if (!ctl_arp_on) return;
    arp_t *a = &arp[p];
    uint32_t q = ctl_ext_quarter ? ctl_ext_quarter : 60u * FS / clampi(ctl_tempo, 40, 240);
    if (!nheld[p]) { arp_stop_note(p); a->pos = 0; a->cnt = 0xFFFFFFFFu; return; }
    static const uint8_t ARP_DIV[7] = {1, 2, 4, 8, 3, 6, 12};
    uint32_t div = ARP_DIV[ctl_arp_rate < 7u ? ctl_arp_rate : 2u];
    a->period = q / div;
    if (a->period < CTL) a->period = CTL;
    a->gate_at = (a->period * 64u) >> 7;
    if (a->cnt == 0xFFFFFFFFu || a->cnt + CTL >= a->period) {
        a->cnt = a->cnt == 0xFFFFFFFFu ? 0 : a->cnt + CTL - a->period;
        arp_stop_note(p);
        arp_step(p);
    } else {
        a->cnt += CTL;
        if (a->sounding && a->cnt >= a->gate_at) arp_stop_note(p);
    }
}

/* Event processing */
static uint32_t sus_was;
static inline uint32_t part_sus(uint32_t p) { return ctl_sustain || (ctl_hold >> p & 1u); }

static void ev_note_on(uint32_t p, uint32_t note, uint32_t vel)
{
    held_remove(p, note);
    if (nheld[p] == NHELD) {
        for (uint32_t i = 1; i < NHELD; i++) held[p][i - 1u] = held[p][i];
        nheld[p]--;
    }
    held[p][nheld[p]].note = (uint8_t)note;
    held[p][nheld[p]].vel = (uint8_t)vel;
    held[p][nheld[p]].phys = 1;
    nheld[p]++;
    if (!ctl_arp_on) {
        uint32_t pn = note;
        if (ctl_note_pri == 1) { /* Low note priority */
            for (uint32_t i = 0; i < nheld[p]; i++)
                if (held[p][i].note < pn) pn = held[p][i].note;
        }
        voice_trigger(p, pn, vel);
    }
}

static void ev_note_off(uint32_t p, uint32_t note)
{
    for (uint32_t i = 0; i < nheld[p]; i++)
        if (held[p][i].note == note) held[p][i].phys = 0;
    if (part_sus(p)) return;
    held_remove(p, note);
    if (!ctl_arp_on) voice_release(p, note, 0);
}

static void ev_sustain_up(uint32_t p)
{
    uint8_t gone[NHELD];
    uint32_t ng = 0, j = 0;
    for (uint32_t i = 0; i < nheld[p]; i++) {
        if (held[p][i].phys) held[p][j++] = held[p][i];
        else gone[ng++] = held[p][i].note;
    }
    nheld[p] = j;
    for (uint32_t i = 0; i < ng; i++) voice_release(p, gone[i], 0);
}

static void parts_off(uint32_t p)
{
    nheld[p] = 0;
    arp_stop_note(p);
    voices_release_part(p);
}

static void engine_events(void)
{
    uint32_t sus = part_sus(0) | (part_sus(1) << 1);
    if (ctl_panic) { ctl_panic = 0; parts_off(0); parts_off(1); voices_release_all(); }
    if (sus_was & ~sus & 1u) ev_sustain_up(0);
    if (sus_was & ~sus & 2u) ev_sustain_up(1);
    sus_was = sus;
    while (nq_r != nq_w) {
        nev_t e = nq[nq_r % NQ];
        uint32_t p = e.part && b_own;
        nq_r++;
        if (e.type) ev_note_on(p, e.note, e.vel);
        else ev_note_off(p, e.note);
    }
}

/* ADSR Envelope Progression */
static inline void env_tick(env_t *e, uint32_t a, uint32_t d, int32_t sus, uint32_t r, int32_t gate, int32_t vint)
{
    int32_t k, target;
    if (gate && e->stage >= E_REL) e->stage = E_ATT;
    if (!gate && e->stage && e->stage < E_REL) e->stage = E_REL;
    switch (e->stage) {
    case E_ATT:
        k = (int32_t)ENV_K_ATT[a & 127u];
        k += (int32_t)(((int64_t)k * vint) >> 7);
        target = ENV_ONE + (ENV_ONE * 3 >> 3);
        e->level += (int32_t)(((int64_t)(target - e->level) * k) >> 24);
        if (e->level >= ENV_ONE) { e->level = ENV_ONE; e->stage = E_DEC; }
        break;
    case E_DEC:
        k = (int32_t)ENV_K_DEC[d & 127u];
        k += (int32_t)(((int64_t)k * vint) >> 7);
        e->level += (int32_t)(((int64_t)(sus - e->level) * k) >> 24) - 16;
        if (e->level <= sus + 64) { e->level = sus; e->stage = E_SUS; }
        break;
    case E_SUS:
        e->level = sus;
        break;
    case E_REL:
        k = (int32_t)ENV_K_REL[r & 127u];
        k += (int32_t)(((int64_t)k * vint) >> 7);
        e->level += (int32_t)(((int64_t)(0 - e->level) * k) >> 24) - 32;
        if (e->level < LEVEL_FLOOR) { e->level = 0; e->stage = E_IDLE; }
        break;
    default:
        e->level = 0;
    }
}

/* LFO Waveform Generator */
static int32_t lfo_shape(const part_t *g, uint32_t ph, uint32_t shape)
{
    switch (shape) {
    case LFO_TRI: {
        int32_t p = (int32_t)((ph + 0x40000000u) >> 15);
        return p < 65536 ? p - 32768 : 98303 - p;
    }
    case LFO_SAW:     return 32767 - (int32_t)(ph >> 16);
    case LFO_INV_SAW: return (int32_t)(ph >> 16) - 32768;
    case LFO_SQR:     return ph < 0x80000000u ? 32767 : -32767;
    case LFO_RND:     return (int32_t)(g->lfo_rnd_b >> 16) - 32768;
    default: {        /* LFO_NOISE */
        int32_t a = (int32_t)(g->lfo_rnd_a >> 16) - 32768;
        int32_t b = (int32_t)(g->lfo_rnd_b >> 16) - 32768;
        return a + (int32_t)(((int64_t)(b - a) * (ph >> 8)) >> 24);
    }
    }
}

static void lfo_tick(part_t *g)
{
    uint32_t inc;
    if (g->p->v[P_LFO_SYNC]) {
        uint32_t slot = g->p->v[P_LFO_RATE];
        if (slot >= 31u) slot = (slot * 30u) / 127u;
        uint32_t num = LFO_SYNC_RATIO[slot][0];
        uint32_t den = LFO_SYNC_RATIO[slot][1];
        inc = (uint32_t)((ctl_tempo * (25971u * den)) / num);
    } else {
        uint32_t rate = g->p->v[P_LFO_RATE];
        inc = LFO_INC[rate & 127u];
        if (g->p->v[P_LFO_MODE]) inc <<= 4; /* Fast mode extends into audio rate */
    }
    uint32_t old = g->lfo_ph;
    g->lfo_ph += inc;
    if (g->lfo_ph < old) {
        g->lfo_rnd_a = g->lfo_rnd_b;
        g->lfo_rnd_b = xorshift(&rnd_state);
        /* Roland S-1 ENV TRG = LFO: retrigger attack phase at each LFO cycle */
        if (g->p->v[P_ENV_TRG] == TRIG_LFO) {
            uint32_t part_idx = (g == &pt[1]) ? 1u : 0u;
            for (uint32_t v = 0; v < NV; v++) {
                if (vc[v].gate && vc[v].part == part_idx) {
                    vc[v].fe.stage = E_ATT;
                    vc[v].ae.stage = E_ATT;
                }
            }
        }
    }
    g->lfo_val = lfo_shape(g, g->lfo_ph, g->p->v[P_LFO_WAVE]);
}

static int32_t vol_q12;

/* Derive parameter values once per 16-frame block */
static void block_globals(part_t *g)
{
    const uint8_t *pv = g->p->v;
    int32_t d;

    g->range_semi8 = (int32_t)RANGE_SEMITONES[pv[P_RANGE] % 6u] << 8;
    g->fine_tune8 = ((int32_t)pv[P_FINE_TUNE] - 64) * 48;

    d = pv[P_PULSE_LVL]; g->lvl_sqr = (d * d) >> 7;
    d = pv[P_SAW_LVL];   g->lvl_saw = (d * d) >> 7;
    d = pv[P_SUB_LVL];   g->lvl_sub = (d * d) >> 7;
    d = pv[P_NOISE_LVL]; g->lvl_noi = (d * d) >> 7;

    g->sub_type = pv[P_SUB_TYPE] % 3u;
    g->noise_mode = pv[P_NOISE_MODE] % 2u;

    g->pwm_src = pv[P_PWM_SRC];
    g->pw_base = ((uint32_t)pv[P_PWM_DEPTH] << 25) + (1u << 24);

    g->draw_sw = pv[P_DRAW_SW];
    g->draw_mult_q8 = ((uint32_t)pv[P_DRAW_MULT] + 1u) << 8;

    g->chop_ovtn = pv[P_CHOP_OVTN];
    g->chop_comb_q8 = ((uint32_t)pv[P_CHOP_COMB] + 1u) << 8;
    g->g_chop_masked = chop_calc_masked_gain(g->chop_ovtn);

    g->fenv_amt = (int32_t)pv[P_FENV_AMT] - 64;
    g->keytrk = pv[P_KEYTRK];

    d = pv[P_LFO_PITCH]; g->lfo_pd = (d * 180 + d * d) >> 7;
    d = pv[P_FLFO_AMT];  g->lfo_fd = (d * 38) + ((d * d * 70) >> 7);
    g->wheel_q = pv[P_MOD_DEPTH];

    g->bend8 = (ctl_bend * pv[P_OSC_BEND] * 256) >> 13;
    g->flt_bend8 = (ctl_bend * pv[P_FLT_BEND] * 256) >> 13;

    g->cut_sm += ((pv[P_CUTOFF] << 8) - g->cut_sm) >> 6;
    g->reso_sm += ((pv[P_RESO] << 8) - g->reso_sm) >> 6;
    g->reso_k = 8192 - g->reso_sm * 8400 / (127 * 256);

    g->sus_f = pv[P_SUSTAIN] * (ENV_ONE / 127);
    g->sus_a = pv[P_SUSTAIN] * (ENV_ONE / 127);

    d = pv[P_VOLUME];
    g->gain_q12 = (d * d) >> 2;

    g->poly_mode = pv[P_POLY_MODE] % NPOLY_MODE;
    g->porta_mode = pv[P_PORTA_MODE] % 3u;
    g->glide_k = GLIDE_K[pv[P_PORTA_TIME] & 127u];
}

static inline uint32_t pw_mod(uint32_t base, int32_t mod)
{
    int64_t p = (int64_t)base + ((int64_t)mod << 8);
    if (p < (1 << 26)) p = 1 << 26;
    if (p > (int64_t)0xFFFFFFFFu - (1 << 26)) p = (int64_t)0xFFFFFFFFu - (1 << 26);
    return (uint32_t)p;
}

static void voice_block(voice_t *v, uint32_t card)
{
    const part_t *g = &pt[v->part];
    const uint8_t *pv = g->p->v;
    int32_t lfo = g->lfo_val, p8, cut, fenv, a;
    uint32_t glide_k = g->glide_k;

    /* Glide / Portamento slew */
    if (v->pitch16 != v->target16) {
        if (!glide_k || g->porta_mode == PORTA_OFF) {
            v->pitch16 = v->target16;
        } else {
            int32_t diff = v->target16 - v->pitch16;
            v->pitch16 += (int32_t)(((int64_t)diff * glide_k) >> 16);
            if (diff > -64 && diff < 64) v->pitch16 = v->target16;
        }
    }

    /* Envelopes */
    env_tick(&v->fe, pv[P_ATTACK], pv[P_DECAY], g->sus_f, pv[P_RELEASE], v->gate, VINT_ENV[card]);
    env_tick(&v->ae, pv[P_ATTACK], pv[P_DECAY], g->sus_a, pv[P_RELEASE], v->gate, VINT_ENV[card]);
    fenv = v->fe.level >> 9;

    /* Pitch calculation with analog card detuning */
    p8 = (v->pitch16 >> 8) + g->range_semi8 + g->fine_tune8 + g->bend8 + ctl_tune8 + v->det8 + VINT_TUNE8[card];
    p8 += (lfo * g->lfo_pd) >> 15;
#if BOARD_SMK37
    p8 += (lfo * ctl_vib) >> 15;
#endif
    v->inc = pitch_inc(p8);

    /* PWM / Square Wave Duty Cycle (Phase) Calculation */
    if (g->pwm_src == PWM_LFO) {
        /* LFO modulates pulse width symmetrically around 50% square wave (0x80000000u) */
        int64_t p = (int64_t)0x80000000u + (((int64_t)lfo * (int32_t)pv[P_PWM_DEPTH]) << 9);
        if (p < (1 << 26)) p = 1 << 26;
        if (p > (int64_t)0xFFFFFFFFu - (1 << 26)) p = (int64_t)0xFFFFFFFFu - (1 << 26);
        v->pw = (uint32_t)p;
    } else if (g->pwm_src == PWM_ENV) {
        /* Envelope modulates pulse width symmetrically around 50% square wave */
        int64_t p = (int64_t)0x80000000u + (((int64_t)(fenv - 32) * (int32_t)pv[P_PWM_DEPTH]) << 19);
        if (p < (1 << 26)) p = 1 << 26;
        if (p > (int64_t)0xFFFFFFFFu - (1 << 26)) p = (int64_t)0xFFFFFFFFu - (1 << 26);
        v->pw = (uint32_t)p;
    } else {
        /* Manual Duty Cycle: 0 = ~5% narrow pulse, 64 = 50% square, 127 = ~95% wide pulse */
        v->pw = 0x0C000000u + ((uint32_t)pv[P_PWM_DEPTH] * 0x01D00000u);
    }

    /* Filter cutoff calculation (calibrated to Roland S-1 curve & 9.9-octave max env range) */
    cut = g->cut_sm + ((fenv * g->fenv_amt * 482) >> 15)
        + ((int32_t)v->note - 60) * g->keytrk * 2 + ((lfo * g->lfo_fd) >> 15)
        + g->flt_bend8 + VINT_CUT8[card];
    svf_coef(&v->c1, cut, g->reso_k);
    svf_coef(&v->c2, cut, 5793); /* Butterworth damping on 2nd stage */

    /* Amplitude calculation */
    v->amp0 = v->amp1;
    if (pv[P_AMP_MODE] == AMP_GATE) {
        a = v->gate ? 32767 : 0;
    } else {
        a = v->ae.level >> 9;
    }
    v->amp1 = (a * g->gain_q12) >> 12;
    ui_vlevel[card] = a;
    ui_vnote[card] = v->note;
}

/* Render audio samples of one voice */
static void voice_render(voice_t *v, int32_t *out)
{
    uint32_t i, inc = v->inc, pw = v->pw, d = inc >> 15;
    int32_t amp0 = v->amp0, da = v->amp1 - v->amp0, gl = v->gl, gr = v->gr;
    const part_t *g = &pt[v->part];
    const uint8_t *pv = g->p->v;
    int32_t l_sqr = g->lvl_sqr, l_saw = g->lvl_saw, l_sub = g->lvl_sub, l_noi = g->lvl_noi;
    uint32_t sub_t = g->sub_type, draw_sw = g->draw_sw, draw_mult = g->draw_mult_q8;
    uint32_t comb_q8 = g->chop_comb_q8;
    int32_t g_masked = g->g_chop_masked;
    const int16_t *draw_table = seq_draw_table();
    const uint16_t *chop_mask = seq_chop_masks();

    for (i = 0; i < CTL; i++) {
        int32_t s_sqr, s_saw, s_sub, s_noi, mix, lp, bp, hp, y, amp;

        /* 1. Square / Pulse / DRAW */
        if (draw_sw != DSW_OFF) {
            v->o_sqr.ph += inc;
            s_sqr = osc_draw_sample(draw_table, v->o_sqr.ph, draw_mult, draw_sw);
        } else {
            s_sqr = osc_step(&v->o_sqr, inc, d, pw, OSC_PLS, -65536, -1);
        }

        /* 2. Sawtooth */
        s_saw = osc_step(&v->o_saw, inc, d, 0, OSC_SAW, -65536, -1);

        /* 3. Sub-Oscillator: -1oc (50% sqr), -2oc (50% sqr), -2o.A (25% pulse) */
        uint32_t inc_sub = (sub_t == SUB_1OC) ? (inc >> 1) : (inc >> 2);
        uint32_t d_sub = inc_sub >> 15;
        uint32_t pw_sub = (sub_t == SUB_2OA) ? 0x40000000u : 0x80000000u;
        s_sub = osc_step(&v->o_sub, inc_sub, d_sub, pw_sub, OSC_PLS, -65536, -1);

        /* 4. Noise */
        if (g->noise_mode == NOISE_PINK) {
            s_noi = pink_noise_step(&v->pn, (int32_t)(xorshift(&v->noise) >> 16) - 32768);
        } else {
            s_noi = (int32_t)(xorshift(&v->noise) >> 16) - 32768;
        }

        /* 5. OSC CHOP Slicing */
        if (g_masked != 32767) {
            s_sqr = osc_chop_sample(s_sqr, v->o_sqr.ph, chop_mask[0], comb_q8, g_masked);
            s_saw = osc_chop_sample(s_saw, v->o_saw.ph, chop_mask[1], comb_q8, g_masked);
            s_sub = osc_chop_sample(s_sub, v->o_sub.ph, chop_mask[2], comb_q8, g_masked);
            s_noi = osc_chop_sample(s_noi, v->o_saw.ph, chop_mask[3], comb_q8, g_masked);
        }

        /* 6. Composite Voice Mixer */
        mix = (s_sqr * l_sqr + s_saw * l_saw + s_sub * l_sub + s_noi * l_noi) >> 7;
        mix = clampi(mix, -65535, 65535);

        /* 7. Roland 4-Pole Cascaded SVF with analog OTA saturation */
        int32_t drive_in = softclip(mix >> 1) << 1;
        svf_step(&v->c1, &v->f1, drive_in, &lp, &bp, &hp);
        y = svf_lp(&v->c2, &v->f2, lp);

        /* Analog Low-End Emphasis & Resonance Bass Retention (Roland IR3109) */
        v->bass_lp += (mix - v->bass_lp) >> 5;  /* ~200 Hz low-pass warmth tracker */
        int32_t bass_comp = (v->bass_lp * (int32_t)(pv[P_RESO] + 48)) >> 9;
        y = clampi(y + bass_comp, -65000, 65000);

        /* 8. Amplifier Envelope and Panning */
        amp = amp0 + ((da * (int32_t)i) >> 4);
        y = (y * amp) >> 16;
        out[2u * i]      += (y * gl) >> 12;
        out[2u * i + 1u] += (y * gr) >> 12;
    }
}

static int32_t bus_b[2u * HALF_FRAMES];

static void engine_audio(int32_t *out, uint32_t n)
{
    uint32_t b, v, i, was_own = b_own, dry, bus = b_own;
    static int32_t sc_prev;
    static uint32_t sc_i, sc_sub;

    fx_block(&live, ctl_ext_quarter ? ctl_ext_quarter : 60u * FS / clampi(ctl_tempo, 40, 240));
    vol_q12 = (int32_t)((ctl_cc7 * ctl_cc7) >> 2);

    for (v = 0; v < NV; v++)
        if (vc[v].part && vc[v].ae.stage != E_IDLE) bus = 1;
    if (bus)
        for (i = 0; i < 2u * n; i++) bus_b[i] = 0;

    for (b = 0; b < n; b += CTL) {
        parts_point();
        if (was_own && !b_own) parts_off(1);
        engine_events();
        if (ctl_arp_restart) {
            ctl_arp_restart = 0;
            arp[0].pos = arp[1].pos = 0;
            arp[0].cnt = arp[1].cnt = 0xFFFFFFFFu;
        }
        arp_tick(0);
        if (b_own) arp_tick(1);
        seq_tick();
        parts_point();
        if (was_own && !b_own) parts_off(1);
        was_own = b_own;
        lfo_tick(&pt[0]);
        if (b_own) lfo_tick(&pt[1]);
        block_globals(&pt[0]);
        if (b_own) block_globals(&pt[1]);

        for (v = 0; v < NV; v++) {
            if (vc[v].ae.stage == E_IDLE && !vc[v].gate) {
                if (ui_vlevel[v]) { ui_vlevel[v] = 0; vc[v].amp0 = vc[v].amp1 = 0; }
                /* Free-running oscillator phase advance */
                uint32_t step = vc[v].inc * CTL;
                vc[v].o_sqr.ph += step;
                vc[v].o_saw.ph = vc[v].o_sqr.ph;
                uint32_t step_sub = (pt[vc[v].part].sub_type == SUB_1OC) ? (step >> 1) : (step >> 2);
                vc[v].o_sub.ph += step_sub;
                continue;
            }
            voice_block(&vc[v], v);
            voice_render(&vc[v], (vc[v].part && bus ? bus_b : out) + 2u * b);
        }
    }

    dry = bus ? seq_b_dry() : 0u;
    for (i = 0; bus && i < 2u * n; i++) {
        int32_t x = bus_b[i], d = (x * (int32_t)dry) >> 7;
        out[i] += x - d;
        bus_b[i] = d;
    }

    /* Output Stage with soft saturation */
    for (i = 0; i < n; i++) {
        int32_t l = softclip((clampi(out[2u * i], -262144, 262143) >> 2) * vol_q12 >> 10);
        int32_t r = softclip((clampi(out[2u * i + 1u], -262144, 262143) >> 2) * vol_q12 >> 10);
        int32_t m = (l + r) >> 1;
        out[2u * i] = l;
        out[2u * i + 1u] = r;

        if (scope_state == 1u) {
            if (sc_prev < 0 && m >= 0) { scope_state = 2; sc_i = 0; sc_sub = 0; }
        } else if (scope_state == 2u) {
            if (!sc_sub++) scope[sc_i++] = (int16_t)m;
            if (sc_sub >= scope_stride) sc_sub = 0;
            if (sc_i >= SCOPE_N) scope_state = 3;
        }
        sc_prev = m;
    }

    fx_process(out, n);

    if (dry) {
        for (i = 0; i < 2u * n; i++)
            out[i] = sat16(out[i] + softclip((clampi(bus_b[i], -262144, 262143) >> 2) * vol_q12 >> 10));
    }

    /* Metronome click */
    for (i = 0; i < n && click_amp; i++) {
        int32_t c;
        click_ph += click_inc;
        c = (click_ph & 0x80000000u) ? click_amp : -click_amp;
        out[2u * i]      += c;
        out[2u * i + 1u] += c;
        click_amp -= (click_amp >> 8) + 1;
        if (click_amp < 64) click_amp = 0;
    }
}

static int engine_quiet(void)
{
    for (uint32_t v = 0; v < NV; v++)
        if (vc[v].ae.stage != E_IDLE || vc[v].gate) return 0;
    return nq_r == nq_w;
}

static void engine_init(void)
{
    for (uint32_t v = 0; v < NV; v++) {
        vc[v].noise = 0x12345678u * (v + 1u) + 0x9E3779B9u;
        uint32_t ph = xorshift(&vc[v].noise) + v * 0x40000000u;
        vc[v].o_sqr.ph = ph;
        vc[v].o_saw.ph = ph;
        vc[v].o_sub.ph = ph >> 1;
        vc[v].o_sub.prev = 0;
        vc[v].inc = pitch_inc((60 + (int32_t)v * 3) << 8);
        vc[v].pn.b0 = vc[v].pn.b1 = vc[v].pn.b2 = 0;
        vc[v].gl = vc[v].gr = 2896;
    }
    pt[0].lfo_rnd_a = xorshift(&rnd_state);
    pt[0].lfo_rnd_b = xorshift(&rnd_state);
    pt[1].lfo_rnd_a = 0x6A09E667u;
    pt[1].lfo_rnd_b = 0xBB67AE85u;
    fx_init();
}

#endif /* OBV_ENGINE_H */
