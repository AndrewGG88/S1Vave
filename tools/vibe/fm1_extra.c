/* SPDX-License-Identifier: GPL-3.0-only */
/* S1Vave VST Editor & DAW Parameter Bridge (SDK 8 & 9)
 * Maps all 59 sound parameters + Patch/Preset selector + Arpeggiator +
 * Sequencer + System + OSC DRAW & CHOP single controls to DAW automation
 * and builds the compact 3-tab Editor layout. */

#include "vibe.h"
#include "vibe_gfx.h"

#define S1_SOUND_PARAMS   NPARAM
#define PARAM_PRESET      (NPARAM + 0)
#define PARAM_ARP_SW      (NPARAM + 1)
#define PARAM_ARP_HOLD    (NPARAM + 2)
#define PARAM_ARP_TYPE    (NPARAM + 3)
#define PARAM_ARP_RATE    (NPARAM + 4)
#define PARAM_ARP_PRI     (NPARAM + 5)
#define PARAM_TEMPO       (NPARAM + 6)
#define PARAM_MASTER_TUNE (NPARAM + 7)
#define PARAM_MIDI_CH     (NPARAM + 8)
#define PARAM_SEQ_PLAY    (NPARAM + 9)
#define PARAM_MASTER_PROB (NPARAM + 10)
#define PARAM_SWING       (NPARAM + 11)
#define PARAM_CHOP_TGT    (NPARAM + 12)
#define PARAM_CHOP_MASK   (NPARAM + 13)
#define PARAM_DRAW_STEP   (NPARAM + 14)
#define PARAM_DRAW_VAL    (NPARAM + 15)
#define S1_TOTAL_PARAMS   (NPARAM + 16)

#define NUM_PRESETS 99

static char preset_choice_buf[NUM_PRESETS][24];
static const char *PRESET_CHOICES[NUM_PRESETS + 1];
static char s1_help_buf[S1_TOTAL_PARAMS][64];
static uint8_t syx_buf[128];

static int hex_nibble(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static void pack_slot_sysex(uint32_t slot, uint8_t *pkt)
{
    uint32_t s = (slot % NPROG) / PS_N;
    uint32_t idx = (slot % NPROG) % PS_N;
    patch_t pt;
    if (slot == prog) pt = live;
    else prog_get(slot % NPROG, &pt);
    pkt[0] = (uint8_t)(slot % NPROG);
    pkt[1] = psect[s].used[idx];
    for (uint32_t i = 0; i < 80u; i++) pkt[2u + i] = pt.v[i];
    for (uint32_t i = 0; i < 16u; i++) {
        uint16_t u = (uint16_t)pat.draw_table[i];
        pkt[82u + i * 2u] = (uint8_t)(u & 0xFFu);
        pkt[83u + i * 2u] = (uint8_t)((u >> 8) & 0xFFu);
    }
    for (uint32_t i = 0; i < 4u; i++) {
        uint16_t m = pat.chop_mask[i];
        pkt[114u + i * 2u] = (uint8_t)(m & 0xFFu);
        pkt[115u + i * 2u] = (uint8_t)((m >> 8) & 0xFFu);
    }
}

static void populate_preset_names(void);

static const char *const CHOP_TGTS[5] = {
    "SQUARE", "SAW", "SUB", "NOISE", 0
};

static const char *const CHOP_MASKS[5] = {
    "ALL ON", "OFF", "EVEN", "ODD", 0
};

static const char *const ARP_TYPES[NARP_TYPE + 1] = {
    "UP", "DOWN", "UP / DOWN", "UP (2 Oct)", "DOWN (2 Oct)", "UP / DOWN (2 Oct)", "RANDOM", "RANDOM (2 Oct)", 0
};

static const char *const ARP_RATES[NARP_RATE + 1] = {
    "1/4", "1/8", "1/16", "1/32", "1/8 Triplet", "1/16 Triplet", "1/32 Triplet", 0
};

static const char *const ARP_PRI_CHOICES[3] = {
    "Last Note", "Lowest Note", 0
};

static const char *const MIDI_CH_CHOICES[18] = {
    "OMNI",
    "CH 1", "CH 2", "CH 3", "CH 4",
    "CH 5", "CH 6", "CH 7", "CH 8",
    "CH 9", "CH 10", "CH 11", "CH 12",
    "CH 13", "CH 14", "CH 15", "CH 16",
    0
};

static const char *const SEQ_PLAY_CHOICES[3] = {
    "STOP", "PLAY", 0
};

static vibe_param s1_param_list[S1_TOTAL_PARAMS];
static const char *s1_param_groups_list[S1_TOTAL_PARAMS];
static char s1_ids[S1_TOTAL_PARAMS][24];
static char s1_names[S1_TOTAL_PARAMS][28];

static const char *const ONOFF_CHOICES[3] = {"OFF", "ON", 0};

static const char *const *param_choices(uint32_t p)
{
    switch (PDEF[p].kind) {
    case K_RANGE:   return RANGE_NAME;
    case K_SUBTYPE: return SUB_NAME;
    case K_PWMS:    return PWMS_NAME;
    case K_DRAWSW:  return DRAWSW_NAME;
    case K_NOISEM:  return NOISEM_NAME;
    case K_ENVTRG:  return ENVTRG_NAME;
    case K_AMP:     return AMP_NAME;
    case K_LFOWAVE: return LFOWAVE_NAME;
    case K_RISERM:  return RISER_NAME;
    case K_CHOM:    return CHORUS_NAME;
    case K_REVM:    return REVERB_NAME;
    case K_PMODE:   return POLY_NAME;
    case K_PORTAM:  return PORTA_NAME;
    case K_FLTCOL:  return FLTCOL_NAME;
    case K_ONOFF:   return ONOFF_CHOICES;
    default:        return 0;
    }
}

static int is_bipolar(uint32_t p)
{
    return PDEF[p].kind == K_BIP || p == P_FINE_TUNE || p == P_TONE || p == P_TRANSPOSE;
}

static float param_offset(uint32_t p)
{
    if (p == P_TRANSPOSE) return 60.0f;
    if (p == P_FINE_TUNE || p == P_TONE || PDEF[p].kind == K_BIP) return 64.0f;
    return 0.0f;
}

static float param_to_daw(uint32_t p, uint8_t v)
{
    return (float)v - param_offset(p);
}

static uint8_t daw_to_param(uint32_t p, float v)
{
    int32_t val = (int32_t)(v + param_offset(p) + 0.5f);
    return (uint8_t)clampi(val, 0, PDEF[p].max);
}

/* Category Groups for the 3-Tab Hierarchy */
static const char *param_group_name(uint32_t p)
{
    if (p == PARAM_PRESET)
        return "SYNTH \xc2\xb7 PRESET";

    /* TAB 1: SYNTH */
    if (p >= P_RANGE && p <= P_FINE_TUNE)
        return "SYNTH \xc2\xb7 OSCILLATOR";
    if (p == P_PWM_SRC || p == P_PWM_DEPTH)
        return "SYNTH \xc2\xb7 PWM";
    if (p == P_DRAW_SW || p == P_DRAW_MULT || p == PARAM_DRAW_STEP || p == PARAM_DRAW_VAL)
        return "SYNTH \xc2\xb7 OSC DRAW";
    if (p == P_CHOP_OVTN || p == P_CHOP_COMB || p == PARAM_CHOP_TGT || p == PARAM_CHOP_MASK)
        return "SYNTH \xc2\xb7 OSC CHOP";
    if (p >= P_CUTOFF && p <= P_WARMTH)
        return "SYNTH \xc2\xb7 FILTER";
    if (p >= P_ATTACK && p <= P_ENV_TRG)
        return "SYNTH \xc2\xb7 ENVELOPE";

    /* TAB 2: MOD & FX */
    if (p >= P_LFO_RATE && p <= P_OSC_BEND)
        return "MOD & FX \xc2\xb7 LFO";
    if (p >= P_RISER_MODE && p <= P_RISER_LVL)
        return "MOD & FX \xc2\xb7 RISER";
    if (p >= P_DLY_LVL && p <= P_DLY_SYNC)
        return "MOD & FX \xc2\xb7 DELAY";
    if (p >= P_REV_LVL && p <= P_CHO_MODE)
        return "MOD & FX \xc2\xb7 REVERB & CHO";

    /* TAB 3: VOICE */
    if (p >= P_POLY_MODE && p <= P_VOLUME)
        return "VOICE \xc2\xb7 VOICING";
    if (p >= P_CHORD_SW2 && p <= P_CHORD_KS4)
        return "VOICE \xc2\xb7 CHORD ENGINE";
    if (p >= PARAM_ARP_SW && p <= PARAM_ARP_PRI)
        return "VOICE \xc2\xb7 ARPEGGIATOR";
    if (p == PARAM_SEQ_PLAY || p == PARAM_TEMPO || p == PARAM_MASTER_PROB || p == PARAM_SWING)
        return "VOICE \xc2\xb7 SEQUENCER";
    if (p == PARAM_MASTER_TUNE || p == PARAM_MIDI_CH)
        return "VOICE \xc2\xb7 SYSTEM";

    return "SYNTH \xc2\xb7 OSCILLATOR";
}

/* ADSR Curve for the Editor */
static int s1_env_curve(const char *tab, const char *card, float *pts, int max)
{
    (void)tab; (void)card;
    const uint8_t *v = live.v;
    float a = v[P_ATTACK] / 127.0f * 0.35f + 0.02f;
    float d = v[P_DECAY] / 127.0f * 0.35f + 0.02f;
    float s = v[P_SUSTAIN] / 127.0f;
    float r = v[P_RELEASE] / 127.0f * 0.35f + 0.02f;
    float h = 0.15f, tot = a + d + h + r;
    int n = max < 48 ? max : 48;
    for (int i = 0; i < n; i++) {
        float x = (float)i / (float)(n - 1) * tot, y;
        if (x < a) y = x / a;
        else if (x < a + d) y = 1.0f - (1.0f - s) * (x - a) / d;
        else if (x < a + d + h) y = s;
        else y = s * (1.0f - (x - a - d - h) / r);
        pts[i] = y < 0.0f ? 0.0f : y > 1.0f ? 1.0f : y;
    }
    return n;
}

/* LFO Waveform Shape for the Editor */
static int s1_lfo_curve(const char *tab, const char *card, float *pts, int max)
{
    (void)tab; (void)card;
    uint32_t shape = live.v[P_LFO_WAVE];
    int n = max < 32 ? max : 32;
    for (int i = 0; i < n; i++) {
        float x = (float)i / (float)n, y;
        switch (shape) {
        case LFO_SAW: y = 1.0f - x; break;
        case LFO_INV_SAW: y = x; break;
        case LFO_SQR: y = x < 0.5f ? 1.0f : 0.0f; break;
        case LFO_RND: case LFO_NOISE:
            y = ((float)((i * 13 + 7) % 31)) / 31.0f;
            break;
        default: /* LFO_TRI */
            y = x < 0.5f ? x * 2.0f : 2.0f - x * 2.0f;
            break;
        }
        pts[i] = y < 0.0f ? 0.0f : y > 1.0f ? 1.0f : y;
    }
    return n;
}

/* Riser Sweep Curve for the Editor */
static int s1_riser_curve(const char *tab, const char *card, float *pts, int max)
{
    (void)tab; (void)card;
    uint32_t mode = live.v[P_RISER_MODE];
    float shape = live.v[P_RISER_SHAPE] / 100.0f;
    float lvl = live.v[P_RISER_LVL] / 100.0f;
    int n = max < 32 ? max : 32;
    for (int i = 0; i < n; i++) {
        float x = (float)i / (float)(n - 1);
        float ramp = x * x * (1.0f - 0.4f * shape) + x * 0.4f * shape;
        float quiv = (mode >= RISER_QUIV) ? (((i & 1) ? 0.12f : -0.12f) * (0.3f + 0.7f * x)) : 0.0f;
        float y = (mode == RISER_OFF) ? 0.15f : (0.1f + (ramp + quiv) * 0.8f * lvl);
        pts[i] = y < 0.05f ? 0.05f : y > 0.95f ? 0.95f : y;
    }
    return n;
}

/* OSC DRAW Curve for the Editor (also handles R0/R1/W0..W8/WC SysEx binary bridge) */
static int s1_draw_curve(const char *tab, const char *card, float *pts, int max)
{
    (void)card;
    if (tab && tab[0] == 'R' && (tab[1] == '0' || tab[1] == '1') && tab[2] == ':') {
        uint32_t slot = 0, k = 3u;
        while (tab[k] >= '0' && tab[k] <= '9') {
            slot = slot * 10u + (uint32_t)(tab[k] - '0');
            k++;
        }
        uint8_t pkt[122];
        pack_slot_sysex(slot, pkt);
        uint32_t off = (tab[1] == '1') ? 61u : 0u;
        int cnt = max < 61 ? max : 61;
        for (int i = 0; i < cnt; i++) {
            pts[i] = (float)pkt[off + (uint32_t)i] / 255.0f;
        }
        return cnt;
    }
    if (tab && tab[0] == 'W') {
        if (tab[1] >= '0' && tab[1] <= '8' && tab[2] == ':') {
            uint32_t chunk = (uint32_t)(tab[1] - '0');
            uint32_t base = chunk * 14u;
            const char *hex = tab + 3;
            for (uint32_t i = 0; i < 14u && base + i < 128u; i++) {
                int hi = hex_nibble(hex[i * 2u]);
                int lo = hex_nibble(hex[i * 2u + 1u]);
                if (hi < 0 || lo < 0) break;
                syx_buf[base + i] = (uint8_t)((hi << 4) | lo);
            }
            pts[0] = 1.0f;
            return 1;
        }
        if (tab[1] == 'C') {
            app_sysex(0x21u, syx_buf, 122u);
            populate_preset_names();
            pts[0] = 1.0f;
            return 1;
        }
    }
    uint32_t sw = live.v[P_DRAW_SW];
    uint32_t mult = (uint32_t)live.v[P_DRAW_MULT] + 1u;
    int n = max < 48 ? max : 48;
    if (sw == DSW_OFF) {
        float duty = live.v[P_PWM_DEPTH] / 127.0f * 0.9f + 0.05f;
        for (int i = 0; i < n; i++) {
            float x = (float)i / (float)n;
            pts[i] = (x < duty) ? 0.85f : 0.15f;
        }
        return n;
    }
    uint32_t mult_q8 = mult << 8;
    for (int i = 0; i < n; i++) {
        uint32_t ph = (uint32_t)(((uint64_t)i * 65536u) / (uint32_t)n);
        int32_t s = osc_draw_sample(pat.draw_table, ph, mult_q8, sw);
        float y = (float)s / 75000.0f + 0.50f;
        pts[i] = y < 0.05f ? 0.05f : y > 0.95f ? 0.95f : y;
    }
    return n;
}

/* OSC CHOP Curve for the Editor */
static int s1_chop_curve(const char *tab, const char *card, float *pts, int max)
{
    (void)tab; (void)card;
    uint16_t mask = pat.chop_mask[chop_cur_target & 3u];
    uint32_t ovtn = live.v[P_CHOP_OVTN];
    uint32_t comb = (uint32_t)live.v[P_CHOP_COMB] + 1u;
    int n = max < 48 ? max : 48;
    float depth = (float)ovtn / 200.0f;
    for (int i = 0; i < n; i++) {
        int step = (i * 16) / n;
        int active = (mask & (1u << step)) != 0;
        int comb_len = n / comb > 0 ? n / comb : 1;
        float saw = (float)(i % comb_len) / (float)comb_len;
        float carrier = (saw < 0.5f ? saw * 2.0f : 2.0f - saw * 2.0f) * 0.7f + 0.15f;
        float y = active ? carrier : (carrier * (1.0f - depth * 0.85f));
        pts[i] = y < 0.05f ? 0.05f : y > 0.95f ? 0.95f : y;
    }
    return n;
}

/* Filter Frequency Response Curve for the Editor */
static int s1_filter_curve(const char *tab, const char *card, float *pts, int max)
{
    (void)tab; (void)card;
    float cut = live.v[P_CUTOFF] / 127.0f;
    float res = live.v[P_RESO] / 127.0f;
    int n = max < 48 ? max : 48;
    float fc = cut * (float)(n - 8) + 4.0f;
    for (int i = 0; i < n; i++) {
        float x = (float)i;
        float diff = x - fc;
        float y;
        if (diff < -2.0f) {
            y = 0.75f;
        } else if (diff <= 2.0f) {
            float bump = (1.0f - (diff * diff) / 4.0f) * res * 0.40f;
            y = 0.75f + bump;
        } else {
            y = 0.75f / (1.0f + (diff - 2.0f) * 0.6f * (diff - 2.0f));
        }
        pts[i] = y < 0.05f ? 0.05f : y > 0.98f ? 0.98f : y;
    }
    return n;
}

/* Compact 12-column Editor Cards Setup */
#define S1_NUM_CARDS 16
static vibe_card s1_cards[S1_NUM_CARDS] = {
    {"PRESET",       3, "99 patches (01..64 factory, 65..99 user)"},
    {"OSCILLATOR",   6, "Range, square, saw, sub & noise"},
    {"PWM",          3, "Pulse width & mod source"},
    {"FILTER",       4, "Roland ACB lowpass & XY pad"},
    {"ENVELOPE",     4, "ADSR envelope & trigger mode"},
    {"OSC DRAW",     2, "Step wavetable"},
    {"OSC CHOP",     2, "Harmonic comb"},
    {"LFO",          3, "Waveform, rate & sync"},
    {"RISER",        3, "Build/drop riser"},
    {"DELAY",        3, "Tempo-synced delay"},
    {"REVERB & CHO", 3, "Reverb & chorus"},
    {"VOICING",      4, "Poly, portamento & volume"},
    {"CHORD ENGINE", 4, "4-voice chord shifts"},
    {"ARPEGGIATOR",  4, "Arpeggiator & priority"},
    {"SEQUENCER",    6, "Transport, tempo & swing"},
    {"SYSTEM",       6, "Master tune & MIDI channel"},
};

static void build_cc_help(uint32_t p, uint8_t cc, const char *desc)
{
    char *dst = s1_help_buf[p];
    dst[0] = '['; dst[1] = 'C'; dst[2] = 'C'; dst[3] = ' ';
    int k = 4;
    if (cc >= 100) dst[k++] = (char)('0' + (cc / 100));
    if (cc >= 10)  dst[k++] = (char)('0' + ((cc / 10) % 10));
    dst[k++] = (char)('0' + (cc % 10));
    dst[k++] = ']';
    if (desc && desc[0]) {
        dst[k++] = ' ';
        int j = 0;
        while (desc[j] && k < 62) dst[k++] = desc[j++];
    }
    dst[k] = 0;
    vibe_param_help(p, dst);
}

static void setup_editor_layout(void)
{
    vibe_editor_cards(s1_cards, S1_NUM_CARDS);

    /* Control types for sound parameters */
    for (uint32_t p = 0; p < S1_SOUND_PARAMS; p++) {
        uint32_t kind = PDEF[p].kind;
        if (is_bipolar(p)) {
            vibe_editor_control(p, VIBE_CTL_BIPOLAR);
        } else if (kind == K_ONOFF) {
            vibe_editor_control(p, VIBE_CTL_TOGGLE);
        }

        /* Cutoff & Resonance touch pad */
        if (p == P_CUTOFF) vibe_editor_control(p, VIBE_CTL_XY_X);
        if (p == P_RESO)   vibe_editor_control(p, VIBE_CTL_XY_Y);

        /* Tooltip help + CC tag for bidirectional hardware sync */
        const char *desc = PDEF[p].name;
        switch (p) {
        case P_RANGE:     desc = "Master oscillator octave range (64' bass to 2' lead)"; break;
        case P_SUB_TYPE:  desc = "Sub-oscillator division: -2 oct asymmetric, -2 oct pulse, -1 oct pulse"; break;
        case P_DRAW_SW:   desc = "Unique S-1 custom wavetable drawing: Step or Smooth Slope"; break;
        case P_CHOP_OVTN: desc = "Chop overtone harmonic intensity and phase"; break;
        case P_CHOP_COMB: desc = "Chop comb frequency repetitions across waveform"; break;
        case P_FLT_COLOR: desc = "0 = Roland S-1 clean ACB, 1 = Warm Midnight soft-knee saturation"; break;
        case P_TONE:      desc = "Global filter cutoff tilt (-8 to +8 semitones)"; break;
        case P_WARMTH:    desc = "Analog drive and resonance bass retention (0 to 100%)"; break;
        default: break;
        }
        uint8_t cc = param_to_cc(p);
        if (cc) build_cc_help(p, cc, desc);
        else vibe_param_help(p, desc);
    }

    /* Preset selector dropdown */
    vibe_editor_control(PARAM_PRESET, VIBE_CTL_MENU);
    vibe_param_help(PARAM_PRESET, "Select from 99 patches (01..64 Factory, 65..99 User/Init)");

    /* Arpeggiator controls */
    vibe_editor_control(PARAM_ARP_SW, VIBE_CTL_TOGGLE);
    build_cc_help(PARAM_ARP_SW, 111, "Arpeggiator on/off");
    vibe_editor_control(PARAM_ARP_HOLD, VIBE_CTL_TOGGLE);
    build_cc_help(PARAM_ARP_HOLD, 114, "Key hold latch");
    vibe_editor_control(PARAM_ARP_TYPE, VIBE_CTL_MENU);
    build_cc_help(PARAM_ARP_TYPE, 112, "Arpeggiator direction");
    vibe_editor_control(PARAM_ARP_RATE, VIBE_CTL_MENU);
    build_cc_help(PARAM_ARP_RATE, 113, "Arpeggiator rate division");
    vibe_editor_control(PARAM_ARP_PRI, VIBE_CTL_TOGGLE);
    build_cc_help(PARAM_ARP_PRI, 116, "Note priority");

    /* Sequencer & System controls */
    vibe_editor_control(PARAM_SEQ_PLAY, VIBE_CTL_TOGGLE);
    build_cc_help(PARAM_SEQ_PLAY, 117, "Sequencer play/stop");
    build_cc_help(PARAM_TEMPO, 115, "Internal tempo BPM");
    vibe_editor_control(PARAM_MASTER_TUNE, VIBE_CTL_BIPOLAR);
    vibe_editor_control(PARAM_MIDI_CH, VIBE_CTL_MENU);
    vibe_editor_control(PARAM_MASTER_PROB, VIBE_CTL_BIPOLAR);

    /* OSC CHOP & OSC DRAW controls */
    vibe_editor_control(PARAM_CHOP_TGT, VIBE_CTL_MENU);
    vibe_param_help(PARAM_CHOP_TGT, "[SYX] Target waveform for Chop mask");
    vibe_editor_control(PARAM_CHOP_MASK, VIBE_CTL_MENU);
    vibe_param_help(PARAM_CHOP_MASK, "[SYX] 16-step Chop mask preset");
    vibe_param_help(PARAM_DRAW_STEP, "[SYX] Active step (1..16) or drag directly on curve");
    vibe_editor_control(PARAM_DRAW_VAL, VIBE_CTL_BIPOLAR);
    vibe_param_help(PARAM_DRAW_VAL, "[SYX] Step amplitude (-100..+100%) or drag on curve");

    /* Roland S-1 Aesthetic Accents */
    vibe_editor_accent(0x00B887); /* S-1 Emerald Teal */
    vibe_editor_tab_color("SYNTH", 0x00B887);
    vibe_editor_tab_color("MOD & FX", 0xFF6B18); /* S-1 Filter Orange */
    vibe_editor_tab_color("VOICE", 0x3FA9F5);

    /* Interactive Curves */
    vibe_editor_curve("OSC DRAW", s1_draw_curve);
    vibe_editor_curve("OSC CHOP", s1_chop_curve);
    vibe_editor_curve("FILTER", s1_filter_curve);
    vibe_editor_curve("ENVELOPE", s1_env_curve);
    vibe_editor_curve("LFO", s1_lfo_curve);
    vibe_editor_curve("RISER", s1_riser_curve);
}

static void make_id_and_name(uint32_t p)
{
    const char *raw = PDEF[p].name;
    char *id = s1_ids[p];
    char *nm = s1_names[p];
    int i = 0, k = 0;

    while (raw[i] && k < 22) {
        char c = raw[i++];
        if (c >= 'A' && c <= 'Z') id[k++] = (char)(c | 0x20);
        else if ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')) id[k++] = c;
        else if (k > 0 && id[k - 1] != '_') id[k++] = '_';
    }
    if (k > 0 && id[k - 1] == '_') k--;
    id[k] = 0;

    i = 0;
    while (raw[i] && i < 27) {
        nm[i] = raw[i];
        i++;
    }
    nm[i] = 0;
}

static void populate_preset_names(void)
{
    for (uint32_t i = 0; i < NUM_PRESETS; i++) {
        uint32_t pnum = i + 1u;
        uint32_t s = i / PS_N;
        uint32_t idx = i % PS_N;
        char *dst = preset_choice_buf[i];
        dst[0] = (char)('0' + (pnum / 10u));
        dst[1] = (char)('0' + (pnum % 10u));
        dst[2] = ':';
        dst[3] = ' ';
        const char *src = (i < NFACT && FACTORY[i].name[0]) ? FACTORY[i].name : "[INIT]";
        char user_nm[12];
        if (psect[s].used[idx] == 1u) {
            const uint8_t *nm = psect[s].p[idx].v + NPARAM;
            int ulen = 0;
            while (ulen < 10 && nm[ulen] >= 32 && nm[ulen] < 127) {
                user_nm[ulen] = (char)nm[ulen];
                ulen++;
            }
            user_nm[ulen] = 0;
            if (ulen > 0) src = user_nm;
            else if (i >= NFACT) src = "[USER]";
        }
        int k = 0;
        while (src[k] && k < 18) {
            dst[4 + k] = src[k];
            k++;
        }
        dst[4 + k] = '\0';
        PRESET_CHOICES[i] = dst;
    }
    PRESET_CHOICES[NUM_PRESETS] = 0;
}

static void extra_init(void)
{
    for (uint32_t p = 0; p < S1_SOUND_PARAMS; p++) {
        make_id_and_name(p);
        const char *const *ch = param_choices(p);
        float off = param_offset(p);
        s1_param_list[p].id = s1_ids[p];
        s1_param_list[p].name = s1_names[p];
        s1_param_list[p].min = -off;
        s1_param_list[p].max = (float)PDEF[p].max - off;
        s1_param_list[p].def = param_to_daw(p, live.v[p]);
        s1_param_list[p].unit = (p == P_TRANSPOSE || PDEF[p].kind == K_BIP) ? "st" :
                                (p == P_WARMTH || p == P_RISER_RESO || p == P_RISER_SHAPE || p == P_RISER_LVL) ? "%" : "";
        s1_param_list[p].steps = (int)PDEF[p].max + 1;
        s1_param_list[p].choices = ch;
        s1_param_groups_list[p] = param_group_name(p);
    }

    populate_preset_names();

    /* Register Preset Selector */
    s1_param_list[PARAM_PRESET].id = "preset";
    s1_param_list[PARAM_PRESET].name = "Patch";
    s1_param_list[PARAM_PRESET].min = 0.0f;
    s1_param_list[PARAM_PRESET].max = (float)(NUM_PRESETS - 1);
    s1_param_list[PARAM_PRESET].def = (float)prog;
    s1_param_list[PARAM_PRESET].unit = "";
    s1_param_list[PARAM_PRESET].steps = NUM_PRESETS;
    s1_param_list[PARAM_PRESET].choices = PRESET_CHOICES;
    s1_param_groups_list[PARAM_PRESET] = param_group_name(PARAM_PRESET);

    /* Register Arpeggiator parameters */
    s1_param_list[PARAM_ARP_SW].id = "arp_on";
    s1_param_list[PARAM_ARP_SW].name = "Arp Switch";
    s1_param_list[PARAM_ARP_SW].min = 0.0f;
    s1_param_list[PARAM_ARP_SW].max = 1.0f;
    s1_param_list[PARAM_ARP_SW].def = (float)ctl_arp_on;
    s1_param_list[PARAM_ARP_SW].unit = "";
    s1_param_list[PARAM_ARP_SW].steps = 2;
    s1_param_list[PARAM_ARP_SW].choices = ONOFF_CHOICES;
    s1_param_groups_list[PARAM_ARP_SW] = param_group_name(PARAM_ARP_SW);

    s1_param_list[PARAM_ARP_HOLD].id = "arp_hold";
    s1_param_list[PARAM_ARP_HOLD].name = "Key Hold";
    s1_param_list[PARAM_ARP_HOLD].min = 0.0f;
    s1_param_list[PARAM_ARP_HOLD].max = 1.0f;
    s1_param_list[PARAM_ARP_HOLD].def = 0.0f;
    s1_param_list[PARAM_ARP_HOLD].unit = "";
    s1_param_list[PARAM_ARP_HOLD].steps = 2;
    s1_param_list[PARAM_ARP_HOLD].choices = ONOFF_CHOICES;
    s1_param_groups_list[PARAM_ARP_HOLD] = param_group_name(PARAM_ARP_HOLD);

    s1_param_list[PARAM_ARP_TYPE].id = "arp_mode";
    s1_param_list[PARAM_ARP_TYPE].name = "Arp Mode";
    s1_param_list[PARAM_ARP_TYPE].min = 0.0f;
    s1_param_list[PARAM_ARP_TYPE].max = (float)(NARP_TYPE - 1);
    s1_param_list[PARAM_ARP_TYPE].def = (float)(ctl_arp_type % NARP_TYPE);
    s1_param_list[PARAM_ARP_TYPE].unit = "";
    s1_param_list[PARAM_ARP_TYPE].steps = NARP_TYPE;
    s1_param_list[PARAM_ARP_TYPE].choices = ARP_TYPES;
    s1_param_groups_list[PARAM_ARP_TYPE] = param_group_name(PARAM_ARP_TYPE);

    s1_param_list[PARAM_ARP_RATE].id = "arp_rate";
    s1_param_list[PARAM_ARP_RATE].name = "Arp Rate";
    s1_param_list[PARAM_ARP_RATE].min = 0.0f;
    s1_param_list[PARAM_ARP_RATE].max = (float)(NARP_RATE - 1);
    s1_param_list[PARAM_ARP_RATE].def = (float)(ctl_arp_rate % NARP_RATE);
    s1_param_list[PARAM_ARP_RATE].unit = "";
    s1_param_list[PARAM_ARP_RATE].steps = NARP_RATE;
    s1_param_list[PARAM_ARP_RATE].choices = ARP_RATES;
    s1_param_groups_list[PARAM_ARP_RATE] = param_group_name(PARAM_ARP_RATE);

    s1_param_list[PARAM_ARP_PRI].id = "note_priority";
    s1_param_list[PARAM_ARP_PRI].name = "Priority";
    s1_param_list[PARAM_ARP_PRI].min = 0.0f;
    s1_param_list[PARAM_ARP_PRI].max = 1.0f;
    s1_param_list[PARAM_ARP_PRI].def = (float)ctl_note_pri;
    s1_param_list[PARAM_ARP_PRI].unit = "";
    s1_param_list[PARAM_ARP_PRI].steps = 2;
    s1_param_list[PARAM_ARP_PRI].choices = ARP_PRI_CHOICES;
    s1_param_groups_list[PARAM_ARP_PRI] = param_group_name(PARAM_ARP_PRI);

    /* Register Sequencer & System parameters */
    s1_param_list[PARAM_TEMPO].id = "tempo";
    s1_param_list[PARAM_TEMPO].name = "Tempo";
    s1_param_list[PARAM_TEMPO].min = 40.0f;
    s1_param_list[PARAM_TEMPO].max = 240.0f;
    s1_param_list[PARAM_TEMPO].def = (float)(set.tempo >= 40 && set.tempo <= 240 ? set.tempo : 120);
    s1_param_list[PARAM_TEMPO].unit = "BPM";
    s1_param_list[PARAM_TEMPO].steps = 201;
    s1_param_list[PARAM_TEMPO].choices = 0;
    s1_param_groups_list[PARAM_TEMPO] = param_group_name(PARAM_TEMPO);

    s1_param_list[PARAM_MASTER_TUNE].id = "master_tune";
    s1_param_list[PARAM_MASTER_TUNE].name = "Master Tune";
    s1_param_list[PARAM_MASTER_TUNE].min = -50.0f;
    s1_param_list[PARAM_MASTER_TUNE].max = 50.0f;
    s1_param_list[PARAM_MASTER_TUNE].def = (float)set.tune;
    s1_param_list[PARAM_MASTER_TUNE].unit = "ct";
    s1_param_list[PARAM_MASTER_TUNE].steps = 101;
    s1_param_list[PARAM_MASTER_TUNE].choices = 0;
    s1_param_groups_list[PARAM_MASTER_TUNE] = param_group_name(PARAM_MASTER_TUNE);

    s1_param_list[PARAM_MIDI_CH].id = "midi_channel";
    s1_param_list[PARAM_MIDI_CH].name = "MIDI Channel";
    s1_param_list[PARAM_MIDI_CH].min = 0.0f;
    s1_param_list[PARAM_MIDI_CH].max = 16.0f;
    s1_param_list[PARAM_MIDI_CH].def = (float)(set.midi_ch <= 16 ? set.midi_ch : 0);
    s1_param_list[PARAM_MIDI_CH].unit = "";
    s1_param_list[PARAM_MIDI_CH].steps = 17;
    s1_param_list[PARAM_MIDI_CH].choices = MIDI_CH_CHOICES;
    s1_param_groups_list[PARAM_MIDI_CH] = param_group_name(PARAM_MIDI_CH);

    s1_param_list[PARAM_SEQ_PLAY].id = "seq_transport";
    s1_param_list[PARAM_SEQ_PLAY].name = "Sequencer";
    s1_param_list[PARAM_SEQ_PLAY].min = 0.0f;
    s1_param_list[PARAM_SEQ_PLAY].max = 1.0f;
    s1_param_list[PARAM_SEQ_PLAY].def = (float)ctl_seq_run;
    s1_param_list[PARAM_SEQ_PLAY].unit = "";
    s1_param_list[PARAM_SEQ_PLAY].steps = 2;
    s1_param_list[PARAM_SEQ_PLAY].choices = SEQ_PLAY_CHOICES;
    s1_param_groups_list[PARAM_SEQ_PLAY] = param_group_name(PARAM_SEQ_PLAY);

    s1_param_list[PARAM_MASTER_PROB].id = "seq_prob";
    s1_param_list[PARAM_MASTER_PROB].name = "Probability";
    s1_param_list[PARAM_MASTER_PROB].min = -100.0f;
    s1_param_list[PARAM_MASTER_PROB].max = 100.0f;
    s1_param_list[PARAM_MASTER_PROB].def = (float)pat.master_prob;
    s1_param_list[PARAM_MASTER_PROB].unit = "%";
    s1_param_list[PARAM_MASTER_PROB].steps = 201;
    s1_param_list[PARAM_MASTER_PROB].choices = 0;
    s1_param_groups_list[PARAM_MASTER_PROB] = param_group_name(PARAM_MASTER_PROB);

    s1_param_list[PARAM_SWING].id = "seq_swing";
    s1_param_list[PARAM_SWING].name = "Swing";
    s1_param_list[PARAM_SWING].min = 50.0f;
    s1_param_list[PARAM_SWING].max = 75.0f;
    s1_param_list[PARAM_SWING].def = 50.0f;
    s1_param_list[PARAM_SWING].unit = "%";
    s1_param_list[PARAM_SWING].steps = 26;
    s1_param_list[PARAM_SWING].choices = 0;
    s1_param_groups_list[PARAM_SWING] = param_group_name(PARAM_SWING);

    /* Register OSC CHOP single controls */
    s1_param_list[PARAM_CHOP_TGT].id = "chop_target";
    s1_param_list[PARAM_CHOP_TGT].name = "Target";
    s1_param_list[PARAM_CHOP_TGT].min = 0.0f;
    s1_param_list[PARAM_CHOP_TGT].max = 3.0f;
    s1_param_list[PARAM_CHOP_TGT].def = 0.0f;
    s1_param_list[PARAM_CHOP_TGT].unit = "";
    s1_param_list[PARAM_CHOP_TGT].steps = 4;
    s1_param_list[PARAM_CHOP_TGT].choices = CHOP_TGTS;
    s1_param_groups_list[PARAM_CHOP_TGT] = param_group_name(PARAM_CHOP_TGT);

    s1_param_list[PARAM_CHOP_MASK].id = "chop_mask";
    s1_param_list[PARAM_CHOP_MASK].name = "Mask";
    s1_param_list[PARAM_CHOP_MASK].min = 0.0f;
    s1_param_list[PARAM_CHOP_MASK].max = 3.0f;
    s1_param_list[PARAM_CHOP_MASK].def = 0.0f;
    s1_param_list[PARAM_CHOP_MASK].unit = "";
    s1_param_list[PARAM_CHOP_MASK].steps = 4;
    s1_param_list[PARAM_CHOP_MASK].choices = CHOP_MASKS;
    s1_param_groups_list[PARAM_CHOP_MASK] = param_group_name(PARAM_CHOP_MASK);

    /* Register OSC DRAW single controls */
    s1_param_list[PARAM_DRAW_STEP].id = "draw_step";
    s1_param_list[PARAM_DRAW_STEP].name = "Step";
    s1_param_list[PARAM_DRAW_STEP].min = 1.0f;
    s1_param_list[PARAM_DRAW_STEP].max = 16.0f;
    s1_param_list[PARAM_DRAW_STEP].def = 1.0f;
    s1_param_list[PARAM_DRAW_STEP].unit = "";
    s1_param_list[PARAM_DRAW_STEP].steps = 16;
    s1_param_list[PARAM_DRAW_STEP].choices = 0;
    s1_param_groups_list[PARAM_DRAW_STEP] = param_group_name(PARAM_DRAW_STEP);

    s1_param_list[PARAM_DRAW_VAL].id = "draw_value";
    s1_param_list[PARAM_DRAW_VAL].name = "Amp";
    s1_param_list[PARAM_DRAW_VAL].min = -100.0f;
    s1_param_list[PARAM_DRAW_VAL].max = 100.0f;
    s1_param_list[PARAM_DRAW_VAL].def = 0.0f;
    s1_param_list[PARAM_DRAW_VAL].unit = "%";
    s1_param_list[PARAM_DRAW_VAL].steps = 201;
    s1_param_list[PARAM_DRAW_VAL].choices = 0;
    s1_param_groups_list[PARAM_DRAW_VAL] = param_group_name(PARAM_DRAW_VAL);

    vibe_params(s1_param_list, S1_TOTAL_PARAMS);
    vibe_param_groups(s1_param_groups_list);
    setup_editor_layout();
}

/* extra_event: mouse knob turns, DAW automation, and host transport arrive here */
static int extra_event(const vibe_event *e)
{
    if (e->type == VIBE_EV_TRANSPORT) {
        if (e->id == VIBE_TRANSPORT_TEMPO) {
            float bpm = e->value;
            if (bpm >= 20.0f && bpm <= 400.0f) {
                ctl_tempo = (uint32_t)(bpm + 0.5f);
                set.tempo = (uint8_t)clampi(ctl_tempo, 40, 240);
                pat.tempo = set.tempo;
                ctl_ext_quarter = (uint32_t)(44100.0f * 60.0f / bpm + 0.5f);
                dirty_hdr = 1;
            } else {
                ctl_ext_quarter = 0;
            }
            return 1;
        }
        if (e->id == VIBE_TRANSPORT_PLAY) {
            uint32_t run = e->down ? 1u : 0u;
            if (run && !ctl_seq_run) {
                ctl_arp_restart = 1;
                ctl_seq_restart = 1;
                ctl_seq_run = 1;
            } else if (!run && ctl_seq_run) {
                ctl_seq_run = 0;
                rec = REC_OFF;
                ctl_panic = 1;
            }
            dirty_hdr = dirty_tags = 1;
            return 1;
        }
    }
    if (e->type == VIBE_EV_PARAM) {
        uint32_t p = e->id;
        if (p == PARAM_PRESET) {
            uint32_t new_prog = (uint32_t)(e->value + 0.5f);
            if (new_prog < NUM_PRESETS && new_prog != prog) {
                load_program(new_prog);
                if (new_prog >= NFACT) {
                    for (uint32_t i = 0; i < 16u; i++) pat.draw_table[i] = 0;
                    for (uint32_t i = 0; i < 4u; i++) pat.chop_mask[i] = 0xFFFFu;
                }
                set.prog = (uint8_t)prog;
                dirty_hdr = dirty_page = dirty_tags = 1;
            }
            return 1;
        }
        if (p == PARAM_ARP_SW) {
            ctl_arp_on = (uint32_t)(e->value + 0.5f) ? 1u : 0u;
            ctl_arp_restart = 1u;
            dirty_tags = 1;
            return 1;
        }
        if (p == PARAM_ARP_HOLD) {
            uint32_t on = (uint32_t)(e->value + 0.5f) ? 1u : 0u;
            if (on) ctl_hold |= (1u << ed_b());
            else    ctl_hold &= ~(1u << ed_b());
            hold = ctl_hold;
            dirty_tags = 1;
            return 1;
        }
        if (p == PARAM_ARP_TYPE) {
            ctl_arp_type = (uint32_t)(e->value + 0.5f) % NARP_TYPE;
            dirty_hdr = dirty_tags = 1;
            return 1;
        }
        if (p == PARAM_ARP_RATE) {
            ctl_arp_rate = (uint32_t)(e->value + 0.5f) % NARP_RATE;
            dirty_hdr = dirty_tags = 1;
            return 1;
        }
        if (p == PARAM_ARP_PRI) {
            ctl_note_pri = (uint32_t)(e->value + 0.5f) & 1u;
            dirty_hdr = dirty_tags = 1;
            return 1;
        }
        if (p == PARAM_TEMPO) {
            uint32_t t = (uint32_t)(e->value + 0.5f);
            t = clampi(t, 40, 240);
            set.tempo = (uint8_t)t;
            ctl_tempo = t;
            set_dirty = 1;
            set_t = fm1_ms;
            dirty_hdr = 1;
            return 1;
        }
        if (p == PARAM_MASTER_TUNE) {
            int32_t t = (int32_t)(e->value + (e->value < 0 ? -0.5f : 0.5f));
            set.tune = (int8_t)clampi(t, -50, 50);
            set_dirty = 1;
            set_t = fm1_ms;
            dirty_page = 1;
            return 1;
        }
        if (p == PARAM_MIDI_CH) {
            uint32_t ch = (uint32_t)(e->value + 0.5f);
            set.midi_ch = (uint8_t)clampi(ch, 0, 16);
            set_dirty = 1;
            set_t = fm1_ms;
            dirty_page = 1;
            return 1;
        }
        if (p == PARAM_SEQ_PLAY) {
            uint32_t run = (uint32_t)(e->value + 0.5f) ? 1u : 0u;
            if (run && !ctl_seq_run) {
                ctl_seq_restart = 1;
                ctl_seq_run = 1;
            } else if (!run && ctl_seq_run) {
                ctl_seq_run = 0;
                rec = REC_OFF;
                ctl_panic = 1;
            }
            dirty_hdr = dirty_tags = 1;
            return 1;
        }
        if (p == PARAM_MASTER_PROB) {
            int32_t prob = (int32_t)(e->value + (e->value < 0 ? -0.5f : 0.5f));
            pat.master_prob = (int8_t)clampi(prob, -100, 100);
            pat_dirty = 1;
            return 1;
        }
        if (p == PARAM_SWING) {
            uint32_t sw = (uint32_t)(e->value + 0.5f);
            pat.trk[0].swing = (uint8_t)clampi(sw, 50, 75);
            pat.trk[1].swing = pat.trk[0].swing;
            pat_dirty = 1;
            return 1;
        }
        if (p == PARAM_CHOP_TGT) {
            chop_cur_target = (uint8_t)clampi((int32_t)(e->value + 0.5f), 0, 3);
            dirty_page = 1;
            return 1;
        }
        if (p == PARAM_CHOP_MASK) {
            uint32_t m = (uint32_t)(e->value + 0.5f) % 4u;
            static const uint16_t MASK_VALUES[4] = {0xFFFFu, 0x0000u, 0xAAAAu, 0x5555u};
            pat.chop_mask[chop_cur_target & 3u] = MASK_VALUES[m];
            pat_edited = 1;
            dirty_page = 1;
            return 1;
        }
        if (p == PARAM_DRAW_STEP) {
            draw_cur_step = (uint8_t)clampi((int32_t)(e->value + 0.5f) - 1, 0, 15);
            dirty_page = 1;
            return 1;
        }
        if (p == PARAM_DRAW_VAL) {
            int32_t a = clampi((int32_t)(e->value + (e->value < 0 ? -0.5f : 0.5f)), -100, 100);
            pat.draw_table[draw_cur_step & 15u] = (int16_t)(a * 256);
            pat_edited = 1;
            dirty_page = 1;
            return 1;
        }
        if (p < S1_SOUND_PARAMS) {
            uint8_t val = daw_to_param(p, e->value);
            if (live.v[p] != val) {
                set_param(p, val);
            }
            return 1;
        }
    }
    return 0;
}

/* extra_draw: sync internal parameter changes back to DAW host */
static void extra_draw(uint16_t *out)
{
    (void)out;
    static uint32_t names_synced;
    if (!names_synced || ps_dirty) {
        populate_preset_names();
        names_synced = 1;
    }
    for (uint32_t p = 0; p < S1_SOUND_PARAMS; p++) {
        float expected = param_to_daw(p, live.v[p]);
        if (vibe_param_get(p) != expected) {
            vibe_param_set(p, expected);
        }
    }
    if (vibe_param_get(PARAM_PRESET) != (float)prog) {
        vibe_param_set(PARAM_PRESET, (float)prog);
    }
    if (vibe_param_get(PARAM_ARP_SW) != (float)ctl_arp_on) {
        vibe_param_set(PARAM_ARP_SW, (float)ctl_arp_on);
    }
    uint32_t h = (ctl_hold >> ed_b()) & 1u;
    if (vibe_param_get(PARAM_ARP_HOLD) != (float)h) {
        vibe_param_set(PARAM_ARP_HOLD, (float)h);
    }
    if (vibe_param_get(PARAM_ARP_TYPE) != (float)(ctl_arp_type % NARP_TYPE)) {
        vibe_param_set(PARAM_ARP_TYPE, (float)(ctl_arp_type % NARP_TYPE));
    }
    if (vibe_param_get(PARAM_ARP_RATE) != (float)(ctl_arp_rate % NARP_RATE)) {
        vibe_param_set(PARAM_ARP_RATE, (float)(ctl_arp_rate % NARP_RATE));
    }
    if (vibe_param_get(PARAM_ARP_PRI) != (float)(ctl_note_pri & 1u)) {
        vibe_param_set(PARAM_ARP_PRI, (float)(ctl_note_pri & 1u));
    }
    if (vibe_param_get(PARAM_TEMPO) != (float)set.tempo) {
        vibe_param_set(PARAM_TEMPO, (float)set.tempo);
    }
    if (vibe_param_get(PARAM_MASTER_TUNE) != (float)set.tune) {
        vibe_param_set(PARAM_MASTER_TUNE, (float)set.tune);
    }
    if (vibe_param_get(PARAM_MIDI_CH) != (float)set.midi_ch) {
        vibe_param_set(PARAM_MIDI_CH, (float)set.midi_ch);
    }
    if (vibe_param_get(PARAM_SEQ_PLAY) != (float)ctl_seq_run) {
        vibe_param_set(PARAM_SEQ_PLAY, (float)ctl_seq_run);
    }
    if (vibe_param_get(PARAM_MASTER_PROB) != (float)pat.master_prob) {
        vibe_param_set(PARAM_MASTER_PROB, (float)pat.master_prob);
    }
    if (vibe_param_get(PARAM_SWING) != (float)pat.trk[0].swing) {
        vibe_param_set(PARAM_SWING, (float)pat.trk[0].swing);
    }
    if (vibe_param_get(PARAM_CHOP_TGT) != (float)chop_cur_target) {
        vibe_param_set(PARAM_CHOP_TGT, (float)chop_cur_target);
    }
    if (vibe_param_get(PARAM_DRAW_STEP) != (float)(draw_cur_step + 1)) {
        vibe_param_set(PARAM_DRAW_STEP, (float)(draw_cur_step + 1));
    }
    float cur_draw_val = (float)((int32_t)pat.draw_table[draw_cur_step & 15u] / 256);
    if (vibe_param_get(PARAM_DRAW_VAL) != cur_draw_val) {
        vibe_param_set(PARAM_DRAW_VAL, cur_draw_val);
    }
}

static void extra_leds(void) {}
