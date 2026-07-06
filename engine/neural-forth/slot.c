/* slot.c — ∂4-style trainable slot sub-VM.
 *
 * Implements the CHOOSE primitive (Bošnjak et al. ICML 2017 §3.1):
 *
 *   p = softmax(logits / temperature)                (learned distribution)
 *   y = Σ_i p_i * op_i(a, b)                        (soft operation mixture)
 *
 * Vocabulary (n_in=2): op_0=a+b, op_1=a-b, op_2=a*b, op_3=min, op_4=max.
 *
 * Backward:
 *   ∂L/∂logits_i = (∂L/∂y) · p_i · (f_i − y)       (through softmax + CHOOSE)
 *   ∂L/∂a        = (∂L/∂y) · Σ_i p_i · ∂f_i/∂a     (through ops to inputs)
 *
 * The three-stage encoder→transform→decoder structure is collapsed here:
 * encoder and decoder are identity (n_in=1, n_out=1 scalar each), and the
 * transform is CHOOSE.  The stage boundaries are preserved in naming so Stage
 * 8 can extend encoder/decoder to full linear layers without a refactor.
 */
#include "slot.h"
#include "tensor.h"
#include "autograd.h"
#include "nn.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ── Slot pool ───────────────────────────────────────────────────────────── */

typedef struct {
    int   active;
    int   n_in, n_out;
    float temperature;
    int   logits_h;  /* 1 × NF_SLOT_VOCAB_SIZE tensor — learnable */
    /* Saved forward context for backward */
    int   last_in_h[NF_SLOT_MAX_IN];  /* input tensor handles */
    float last_a[NF_SLOT_MAX_IN];     /* scalar input values */
    float last_fi[NF_SLOT_VOCAB_SIZE];/* op_i(inputs) */
    float last_p[NF_SLOT_VOCAB_SIZE]; /* softmax(logits/T) */
    float last_y;                      /* final output */
} NfSlot;

static NfSlot g_slots[NF_MAX_SLOTS];
static int    g_slot_init = 0;

/* ── Operation vocabulary ────────────────────────────────────────────────── */

/* Evaluate op_i on n_in scalar inputs.  For n_in=2: a=in[0], b=in[1]. */
static float eval_op(int op, const float *in, int n)
{
    float a = (n > 0) ? in[0] : 0.0f;
    float b = (n > 1) ? in[1] : 0.0f;
    float r = 0.0f;
    switch (op) {
    case 0:  /* + */
        r = a + b;
        for (int i = 2; i < n; i++) r += in[i];
        break;
    case 1:  /* - (first minus rest) */
        r = a - b;
        for (int i = 2; i < n; i++) r -= in[i];
        break;
    case 2:  /* * */
        r = a * b;
        for (int i = 2; i < n; i++) r *= in[i];
        break;
    case 3:  /* min */
        r = a < b ? a : b;
        for (int i = 2; i < n; i++) if (in[i] < r) r = in[i];
        break;
    case 4:  /* max */
        r = a > b ? a : b;
        for (int i = 2; i < n; i++) if (in[i] > r) r = in[i];
        break;
    default: r = 0.0f;
    }
    return r;
}

/* Partial derivative of op_i w.r.t. input[j]. */
static float dop_dinput(int op, const float *in, int n, int j)
{
    float a = (n > 0) ? in[0] : 0.0f;
    float b = (n > 1) ? in[1] : 0.0f;
    switch (op) {
    case 0:  return 1.0f;                                          /* + */
    case 1:  return (j == 0) ? 1.0f : -1.0f;                      /* - */
    case 2:  return (j == 0) ? b : a;                              /* * */
    case 3:  { /* min: 1 for argmin, 0 otherwise (split equally on tie) */
        float mn = eval_op(3, in, n);
        return (in[j] == mn) ? 1.0f : 0.0f;
    }
    case 4:  { /* max: 1 for argmax */
        float mx = eval_op(4, in, n);
        return (in[j] == mx) ? 1.0f : 0.0f;
    }
    default: return 0.0f;
    }
}

/* ── Slot lifecycle ──────────────────────────────────────────────────────── */

void nf_slot_declare(zf_ctx *ctx)
{
    if (!g_slot_init) { memset(g_slots, 0, sizeof(g_slots)); g_slot_init = 1; }
    int n_out = (int)zf_pop(ctx);
    int n_in  = (int)zf_pop(ctx);
    if (n_in < 1 || n_in > NF_SLOT_MAX_IN || n_out != 1) {
        fprintf(stderr, "slot-declare: unsupported dims %d→%d\n", n_in, n_out);
        zf_push(ctx, (zf_cell)-1);
        return;
    }

    int sid = -1;
    for (int i = 0; i < NF_MAX_SLOTS; i++) {
        if (!g_slots[i].active) { sid = i; break; }
    }
    if (sid < 0) {
        fprintf(stderr, "slot-declare: slot pool exhausted\n");
        zf_push(ctx, (zf_cell)-1);
        return;
    }

    int logits_h = nf_tensor_alloc(1, NF_SLOT_VOCAB_SIZE);
    if (logits_h == NF_INVALID_TENSOR) {
        zf_push(ctx, (zf_cell)-1);
        return;
    }
    /* Init logits to zero (uniform softmax at temperature=1) */
    nf_tensor_zero(logits_h);

    g_slots[sid].active      = 1;
    g_slots[sid].n_in        = n_in;
    g_slots[sid].n_out       = n_out;
    g_slots[sid].temperature = 1.0f;
    g_slots[sid].logits_h    = logits_h;
    nf_param_register(logits_h);

    zf_push(ctx, (zf_cell)sid);
}

/* ── Forward pass ────────────────────────────────────────────────────────── */

void nf_slot_run(zf_ctx *ctx)
{
    int sid  = (int)zf_pop(ctx);
    if (sid < 0 || sid >= NF_MAX_SLOTS || !g_slots[sid].active) {
        fprintf(stderr, "slot-run: invalid slot %d\n", sid);
        zf_push(ctx, (zf_cell)NF_INVALID_TENSOR);
        return;
    }
    NfSlot *s = &g_slots[sid];

    /* Read n_in tensor handles from the stack (deepest first after pop order) */
    int in_h[NF_SLOT_MAX_IN];
    float in_v[NF_SLOT_MAX_IN];
    /* Stack has: t_1 t_2 ... t_N sid — after popping sid, top is t_N */
    for (int i = s->n_in - 1; i >= 0; i--) {
        in_h[i] = (int)zf_pop(ctx);
        NfTensor *t = nf_tensor_get(in_h[i]);
        in_v[i] = t ? t->data[0] : 0.0f;
    }

    /* ── Encoder (identity for Stage 7) ── */
    /* latent[i] = in_v[i] */

    /* ── Transform: CHOOSE ── */
    NfTensor *logits = nf_tensor_get(s->logits_h);
    float p[NF_SLOT_VOCAB_SIZE], fi[NF_SLOT_VOCAB_SIZE];
    float T = (s->temperature > 1e-6f) ? s->temperature : 1e-6f;

    /* softmax(logits / T) */
    float mx = logits->data[0] / T;
    for (int i = 1; i < NF_SLOT_VOCAB_SIZE; i++)
        if (logits->data[i] / T > mx) mx = logits->data[i] / T;
    float sum_exp = 0.0f;
    for (int i = 0; i < NF_SLOT_VOCAB_SIZE; i++) {
        p[i] = expf(logits->data[i] / T - mx);
        sum_exp += p[i];
    }
    for (int i = 0; i < NF_SLOT_VOCAB_SIZE; i++) p[i] /= sum_exp;

    /* op results and soft mixture */
    float y = 0.0f;
    for (int i = 0; i < NF_SLOT_VOCAB_SIZE; i++) {
        fi[i] = eval_op(i, in_v, s->n_in);
        y += p[i] * fi[i];
    }

    /* ── Decoder (identity) ── */
    /* output = y */

    /* Save forward context */
    for (int i = 0; i < s->n_in; i++) {
        s->last_in_h[i] = in_h[i];
        s->last_a[i]    = in_v[i];
    }
    for (int i = 0; i < NF_SLOT_VOCAB_SIZE; i++) {
        s->last_fi[i] = fi[i];
        s->last_p[i]  = p[i];
    }
    s->last_y = y;

    /* Create 1×1 output tensor */
    int result_h = nf_tensor_alloc(1, 1);
    if (result_h == NF_INVALID_TENSOR) {
        zf_push(ctx, (zf_cell)NF_INVALID_TENSOR);
        return;
    }
    nf_tensor_get(result_h)->data[0] = y;
    zf_push(ctx, (zf_cell)result_h);

    if (nf_tape_is_active())
        nf_tape_record(NF_OP_SLOT_RUN, s->logits_h, sid, result_h);
}

/* ── Backward pass ───────────────────────────────────────────────────────── */

void nf_slot_backward(int slot_id, int logits_h, int result_h)
{
    if (slot_id < 0 || slot_id >= NF_MAX_SLOTS || !g_slots[slot_id].active) return;
    NfSlot *s = &g_slots[slot_id];

    NfTensor *result = nf_tensor_get(result_h);
    NfTensor *logits = nf_tensor_get(logits_h);
    if (!result || !result->grad || !logits) return;

    float grad_y = result->grad[0];
    float T = (s->temperature > 1e-6f) ? s->temperature : 1e-6f;

    /* Ensure gradient storage for logits */
    if (!logits->grad) {
        logits->grad = (float *)calloc((size_t)NF_SLOT_VOCAB_SIZE, sizeof(float));
        if (!logits->grad) return;
    }

    /* grad_logits[i] += grad_y * p[i] * (f_i - y) / T
     * The /T factor comes from differentiating softmax(logits/T) */
    for (int i = 0; i < NF_SLOT_VOCAB_SIZE; i++)
        logits->grad[i] += grad_y * s->last_p[i] * (s->last_fi[i] - s->last_y) / T;

    /* grad_input[j] += grad_y * Σ_i p_i * d(f_i)/d(input_j) */
    for (int j = 0; j < s->n_in; j++) {
        NfTensor *in_t = nf_tensor_get(s->last_in_h[j]);
        if (!in_t) continue;
        if (!in_t->grad) {
            in_t->grad = (float *)calloc((size_t)(in_t->rows * in_t->cols), sizeof(float));
            if (!in_t->grad) continue;
        }
        float g = 0.0f;
        for (int i = 0; i < NF_SLOT_VOCAB_SIZE; i++)
            g += s->last_p[i] * dop_dinput(i, s->last_a, s->n_in, j);
        in_t->grad[0] += grad_y * g;
    }
}

/* ── Accessors ───────────────────────────────────────────────────────────── */

void nf_slot_params(zf_ctx *ctx)
{
    int sid = (int)zf_pop(ctx);
    if (sid < 0 || sid >= NF_MAX_SLOTS || !g_slots[sid].active) {
        fprintf(stderr, ".params: invalid slot %d\n", sid);
        zf_push(ctx, (zf_cell)-1);
        return;
    }
    zf_push(ctx, (zf_cell)g_slots[sid].logits_h);
}

void nf_slot_temp(zf_ctx *ctx)
{
    int   sid  = (int)zf_pop(ctx);
    float temp = (float)zf_pop(ctx);
    if (sid < 0 || sid >= NF_MAX_SLOTS || !g_slots[sid].active) {
        fprintf(stderr, "temperature!: invalid slot %d\n", sid);
        return;
    }
    g_slots[sid].temperature = (temp > 1e-6f) ? temp : 1e-6f;
}

/* ── Parsing words ───────────────────────────────────────────────────────── */

void nf_slot_register_parsing_words(zf_ctx *ctx)
{
    /* SLOT: n_in n_out -- creates a slot and defines the Forth word.
     * Full parsing-word implementation requires kCoreBootstrap (postpone, etc.).
     * This stub lets nf_init() compile.  Real SLOT: support needs Stage 8 engine
     * integration with the WF kCoreBootstrap.
     */
    zf_result r = zf_eval(ctx, ": slot: ;");
    if (r != ZF_OK)
        fprintf(stderr, "neural-forth: failed to stub SLOT: (err %d)\n", r);
    r = zf_eval(ctx, ": permute-slot: ;");
    if (r != ZF_OK)
        fprintf(stderr, "neural-forth: failed to stub PERMUTE-SLOT: (err %d)\n", r);
}
