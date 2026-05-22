/* fuzzy.c — membership functions, T-norms / T-conorms, COG defuzzification.
 *
 * MF handles are indices into g_mfs[].  Fuzzy truth values (mu) are ordinary
 * floats passed on the Forth stack; they are NOT tensor handles.
 */
#include "fuzzy.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

/* ── MF pool ─────────────────────────────────────────────────────────────── */

typedef enum { NF_MF_TRIANGULAR, NF_MF_TRAPEZOIDAL, NF_MF_GAUSSIAN } NfMfType;

typedef struct {
    NfMfType type;
    float    p[4];  /* triangular: a,b,c; trapezoidal: a,b,c,d; gaussian: mean,std */
    int      active;
} NfMF;

static NfMF g_mfs[NF_MAX_MFS];
static int  g_mf_init = 0;

static int alloc_mf(void)
{
    if (!g_mf_init) { memset(g_mfs, 0, sizeof(g_mfs)); g_mf_init = 1; }
    for (int i = 0; i < NF_MAX_MFS; i++) {
        if (!g_mfs[i].active) { g_mfs[i].active = 1; return i; }
    }
    fprintf(stderr, "fuzzy: MF pool exhausted (max %d)\n", NF_MAX_MFS);
    return -1;
}

/* ── MF evaluation ───────────────────────────────────────────────────────── */

float nf_mf_eval(int mf_h, float x)
{
    if (mf_h < 0 || mf_h >= NF_MAX_MFS || !g_mfs[mf_h].active) return 0.0f;
    NfMF *m = &g_mfs[mf_h];
    float *p = m->p;
    float mu;
    switch (m->type) {
    case NF_MF_TRIANGULAR:
        /* a -- ramp up -- b (peak) -- ramp down -- c */
        if (x <= p[0] || x >= p[2]) { mu = 0.0f; break; }
        if (x <= p[1])
            mu = (p[1] > p[0]) ? (x - p[0]) / (p[1] - p[0]) : 1.0f;
        else
            mu = (p[2] > p[1]) ? (p[2] - x) / (p[2] - p[1]) : 1.0f;
        break;
    case NF_MF_TRAPEZOIDAL:
        /* a -- ramp -- b .. c -- ramp -- d */
        if (x <= p[0] || x >= p[3]) { mu = 0.0f; break; }
        if (x >= p[1] && x <= p[2]) { mu = 1.0f; break; }
        if (x < p[1])
            mu = (p[1] > p[0]) ? (x - p[0]) / (p[1] - p[0]) : 1.0f;
        else
            mu = (p[3] > p[2]) ? (p[3] - x) / (p[3] - p[2]) : 1.0f;
        break;
    case NF_MF_GAUSSIAN:
        /* mean=p[0], std=p[1] */
        if (p[1] <= 0.0f) { mu = (x == p[0]) ? 1.0f : 0.0f; break; }
        { float d = (x - p[0]) / p[1]; mu = expf(-0.5f * d * d); }
        break;
    default:
        mu = 0.0f;
    }
    if (mu < 0.0f) mu = 0.0f;
    if (mu > 1.0f) mu = 1.0f;
    return mu;
}

/* ── MF creation words ───────────────────────────────────────────────────── */

void nf_triangular(zf_ctx *ctx)
{
    float c = (float)zf_pop(ctx);
    float b = (float)zf_pop(ctx);
    float a = (float)zf_pop(ctx);
    int h = alloc_mf();
    if (h < 0) { zf_push(ctx, (zf_cell)-1); return; }
    g_mfs[h].type = NF_MF_TRIANGULAR;
    g_mfs[h].p[0] = a; g_mfs[h].p[1] = b; g_mfs[h].p[2] = c;
    zf_push(ctx, (zf_cell)h);
}

void nf_trapezoidal(zf_ctx *ctx)
{
    float d = (float)zf_pop(ctx);
    float c = (float)zf_pop(ctx);
    float b = (float)zf_pop(ctx);
    float a = (float)zf_pop(ctx);
    int h = alloc_mf();
    if (h < 0) { zf_push(ctx, (zf_cell)-1); return; }
    g_mfs[h].type = NF_MF_TRAPEZOIDAL;
    g_mfs[h].p[0] = a; g_mfs[h].p[1] = b;
    g_mfs[h].p[2] = c; g_mfs[h].p[3] = d;
    zf_push(ctx, (zf_cell)h);
}

void nf_gaussian(zf_ctx *ctx)
{
    float std  = (float)zf_pop(ctx);
    float mean = (float)zf_pop(ctx);
    int h = alloc_mf();
    if (h < 0) { zf_push(ctx, (zf_cell)-1); return; }
    g_mfs[h].type = NF_MF_GAUSSIAN;
    g_mfs[h].p[0] = mean; g_mfs[h].p[1] = std;
    zf_push(ctx, (zf_cell)h);
}

void nf_mu_get(zf_ctx *ctx)
{
    int   mf_h = (int)zf_pop(ctx);
    float x    = (float)zf_pop(ctx);
    zf_push(ctx, (zf_cell)nf_mf_eval(mf_h, x));
}

/* ── Defuzzification accumulator ─────────────────────────────────────────── */

#define NF_MAX_RULES 32

typedef struct { float mu; int mf_h; } NfRule;
static NfRule g_rules[NF_MAX_RULES];
static int    g_n_rules = 0;

void nf_fuzzy_reset(zf_ctx *ctx)
{
    (void)ctx;
    g_n_rules = 0;
}

void nf_fuzzy_add(zf_ctx *ctx)
{
    int   mf_h = (int)zf_pop(ctx);
    float mu   = (float)zf_pop(ctx);
    if (g_n_rules >= NF_MAX_RULES) {
        fprintf(stderr, "fuzzy-add: rule accumulator full (max %d)\n", NF_MAX_RULES);
        return;
    }
    g_rules[g_n_rules].mu   = mu;
    g_rules[g_n_rules].mf_h = mf_h;
    g_n_rules++;
}

/* COG over universe [0,1] with 200 steps using Mamdani clip. */
void nf_defuzz_cog(zf_ctx *ctx)
{
    if (g_n_rules == 0) { zf_push(ctx, (zf_cell)0.5f); return; }
    float num = 0.0f, den = 0.0f;
    int steps = 200;
    for (int si = 0; si <= steps; si++) {
        float x = (float)si / (float)steps;
        /* Aggregate: max over all clipped MF evaluations */
        float agg = 0.0f;
        for (int ri = 0; ri < g_n_rules; ri++) {
            float clipped = g_rules[ri].mu;
            if (nf_mf_eval(g_rules[ri].mf_h, x) < clipped)
                clipped = nf_mf_eval(g_rules[ri].mf_h, x);
            if (clipped > agg) agg = clipped;
        }
        num += x * agg;
        den += agg;
    }
    float result = (den > 0.0f) ? num / den : 0.5f;
    zf_push(ctx, (zf_cell)result);
}

/* ── T-norm / S-norm ─────────────────────────────────────────────────────── */

static int g_t_norm = 0;  /* 0=Zadeh(min) 1=Lukasiewicz 2=product */
static int g_s_norm = 0;  /* 0=Zadeh(max) 1=Lukasiewicz 2=product */

void nf_t_norm_set(zf_ctx *ctx) { g_t_norm = (int)zf_pop(ctx) & 3; }
void nf_s_norm_set(zf_ctx *ctx) { g_s_norm = (int)zf_pop(ctx) & 3; }

static float t_norm(float a, float b)
{
    switch (g_t_norm) {
    case 1: { float v = a + b - 1.0f; return v > 0.0f ? v : 0.0f; }  /* Lukasiewicz */
    case 2: return a * b;                                               /* product */
    default: return a < b ? a : b;                                      /* Zadeh min */
    }
}

static float s_norm(float a, float b)
{
    switch (g_s_norm) {
    case 1: { float v = a + b; return v < 1.0f ? v : 1.0f; }   /* Lukasiewicz */
    case 2: return a + b - a * b;                                 /* product */
    default: return a > b ? a : b;                                /* Zadeh max */
    }
}

void nf_fand(zf_ctx *ctx)
{
    float b = (float)zf_pop(ctx);
    float a = (float)zf_pop(ctx);
    zf_push(ctx, (zf_cell)t_norm(a, b));
}

void nf_for_logic(zf_ctx *ctx)
{
    float b = (float)zf_pop(ctx);
    float a = (float)zf_pop(ctx);
    zf_push(ctx, (zf_cell)s_norm(a, b));
}

void nf_fnot(zf_ctx *ctx)
{
    float a = (float)zf_pop(ctx);
    float r = 1.0f - a;
    zf_push(ctx, (zf_cell)(r < 0.0f ? 0.0f : r));
}

/* Mamdani implication: min(a, b) */
void nf_fimplies(zf_ctx *ctx)
{
    float b = (float)zf_pop(ctx);
    float a = (float)zf_pop(ctx);
    zf_push(ctx, (zf_cell)(a < b ? a : b));
}
