/* nn.c — linear layer, losses, Adam optimizer.
 *
 * Linear layers store weights (W: out×in) and bias (b: out×1) as regular
 * NfTensor handles registered as trainable parameters.  nf_forward calls
 * nf_matmul + nf_t_add so all tape recording happens automatically.
 *
 * Adam maintains per-parameter first/second moment arrays lazily allocated on
 * first step.  Parameters are tracked in a global list; nf_linear appends to
 * it automatically.
 */
#include "nn.h"
#include "tensor.h"
#include "autograd.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ── Parameter registry ──────────────────────────────────────────────────── */

#define NF_MAX_PARAMS 128

static int g_params[NF_MAX_PARAMS];
static int g_n_params = 0;

static void register_param(int h)
{
    if (g_n_params < NF_MAX_PARAMS) g_params[g_n_params++] = h;
}

void nf_param_register(int h) { register_param(h); }

/* ── Linear layer pool ───────────────────────────────────────────────────── */

typedef struct { int w_h, b_h; } NfLayer;

static NfLayer g_layers[NF_MAX_LAYERS];
static int     g_layer_init = 0;

/* LCG for weight initialization (reproducible, no global state pollution) */
static unsigned g_lcg_state = 0x12345678u;
static float lcg_randf(void)
{
    g_lcg_state = g_lcg_state * 1664525u + 1013904223u;
    return (float)((int)(g_lcg_state >> 8) % 20000) / 20000.0f - 0.5f;
}

void nf_linear(zf_ctx *ctx)
{
    if (!g_layer_init) {
        for (int i = 0; i < NF_MAX_LAYERS; i++) g_layers[i].w_h = -1;
        g_layer_init = 1;
    }
    int out_size = (int)zf_pop(ctx);
    int in_size  = (int)zf_pop(ctx);
    if (in_size <= 0 || out_size <= 0) {
        fprintf(stderr, "linear: invalid dims %d->%d\n", in_size, out_size);
        zf_push(ctx, (zf_cell)-1);
        return;
    }

    int lid = -1;
    for (int i = 0; i < NF_MAX_LAYERS; i++) {
        if (g_layers[i].w_h == -1) { lid = i; break; }
    }
    if (lid < 0) {
        fprintf(stderr, "linear: layer pool exhausted (max %d)\n", NF_MAX_LAYERS);
        zf_push(ctx, (zf_cell)-1);
        return;
    }

    int w_h = nf_tensor_alloc(out_size, in_size);
    int b_h = nf_tensor_alloc(out_size, 1);
    if (w_h == NF_INVALID_TENSOR || b_h == NF_INVALID_TENSOR) {
        if (w_h != NF_INVALID_TENSOR) nf_tensor_release(w_h);
        if (b_h != NF_INVALID_TENSOR) nf_tensor_release(b_h);
        zf_push(ctx, (zf_cell)-1);
        return;
    }

    /* Xavier init: U(-scale, +scale), scale = sqrt(6/(in+out)) */
    float scale = sqrtf(6.0f / (float)(in_size + out_size));
    NfTensor *w = nf_tensor_get(w_h);
    int n = out_size * in_size;
    for (int i = 0; i < n; i++) w->data[i] = lcg_randf() * 2.0f * scale;

    g_layers[lid].w_h = w_h;
    g_layers[lid].b_h = b_h;
    register_param(w_h);
    register_param(b_h);

    zf_push(ctx, (zf_cell)lid);
}

void nf_forward(zf_ctx *ctx)
{
    int lid = (int)zf_pop(ctx);
    int x_h = (int)zf_pop(ctx);
    if (lid < 0 || lid >= NF_MAX_LAYERS || g_layers[lid].w_h < 0) {
        fprintf(stderr, "forward: invalid layer %d\n", lid);
        zf_push(ctx, (zf_cell)NF_INVALID_TENSOR);
        return;
    }
    int w_h = g_layers[lid].w_h;
    int b_h = g_layers[lid].b_h;

    /* wy = W @ x  (nf_matmul: pops top=x, second=W → computes W@x) */
    zf_push(ctx, (zf_cell)w_h);
    zf_push(ctx, (zf_cell)x_h);
    nf_matmul(ctx);
    /* stack: [wy] */

    /* y = wy + b  (nf_t_add: pops top=b, second=wy) */
    zf_push(ctx, (zf_cell)b_h);
    nf_t_add(ctx);
    /* stack: [y] — leave y on stack for caller */
}

/* ── Losses ──────────────────────────────────────────────────────────────── */

void nf_loss_mse(zf_ctx *ctx)
{
    int target_h = (int)zf_pop(ctx);
    int pred_h   = (int)zf_pop(ctx);
    NfTensor *pred   = nf_tensor_get(pred_h);
    NfTensor *target = nf_tensor_get(target_h);
    if (!pred || !target ||
        pred->rows != target->rows || pred->cols != target->cols) {
        fprintf(stderr, "loss-mse: shape mismatch or invalid handle\n");
        zf_push(ctx, (zf_cell)NF_INVALID_TENSOR);
        return;
    }
    int n = pred->rows * pred->cols;
    int loss_h = nf_tensor_alloc(1, 1);
    if (loss_h == NF_INVALID_TENSOR) { zf_push(ctx, (zf_cell)NF_INVALID_TENSOR); return; }
    float sum = 0.0f;
    for (int i = 0; i < n; i++) {
        float d = pred->data[i] - target->data[i];
        sum += d * d;
    }
    nf_tensor_get(loss_h)->data[0] = sum / (float)n;
    zf_push(ctx, (zf_cell)loss_h);
    if (nf_tape_is_active())
        nf_tape_record(NF_OP_LOSS_MSE, pred_h, target_h, loss_h);
}

void nf_loss_ce(zf_ctx *ctx)
{
    int target_h = (int)zf_pop(ctx);
    int pred_h   = (int)zf_pop(ctx);
    NfTensor *pred   = nf_tensor_get(pred_h);
    NfTensor *target = nf_tensor_get(target_h);
    if (!pred || !target ||
        pred->rows != target->rows || pred->cols != target->cols) {
        fprintf(stderr, "loss-ce: shape mismatch or invalid handle\n");
        zf_push(ctx, (zf_cell)NF_INVALID_TENSOR);
        return;
    }
    int n = pred->rows * pred->cols;
    int loss_h = nf_tensor_alloc(1, 1);
    if (loss_h == NF_INVALID_TENSOR) { zf_push(ctx, (zf_cell)NF_INVALID_TENSOR); return; }
    float eps = 1e-7f;
    float sum = 0.0f;
    for (int i = 0; i < n; i++)
        sum -= target->data[i] * logf(pred->data[i] + eps);
    nf_tensor_get(loss_h)->data[0] = sum / (float)n;
    zf_push(ctx, (zf_cell)loss_h);
    if (nf_tape_is_active())
        nf_tape_record(NF_OP_LOSS_CE, pred_h, target_h, loss_h);
}

/* ── Adam optimizer ──────────────────────────────────────────────────────── */

typedef struct {
    float  lr, beta1, beta2, eps;
    int    step;
    int    active;
    float *m[NF_MAX_PARAMS];
    float *v[NF_MAX_PARAMS];
} NfAdam;

static NfAdam g_opts[NF_MAX_OPTS];
static int    g_opt_init = 0;

void nf_adam_new(zf_ctx *ctx)
{
    if (!g_opt_init) { memset(g_opts, 0, sizeof(g_opts)); g_opt_init = 1; }
    float lr = (float)zf_pop(ctx);
    int oid = -1;
    for (int i = 0; i < NF_MAX_OPTS; i++) {
        if (!g_opts[i].active) { oid = i; break; }
    }
    if (oid < 0) {
        fprintf(stderr, "adam-new: optimizer pool exhausted\n");
        zf_push(ctx, (zf_cell)-1);
        return;
    }
    g_opts[oid].lr     = lr;
    g_opts[oid].beta1  = 0.9f;
    g_opts[oid].beta2  = 0.999f;
    g_opts[oid].eps    = 1e-8f;
    g_opts[oid].step   = 0;
    g_opts[oid].active = 1;
    memset(g_opts[oid].m, 0, sizeof(g_opts[oid].m));
    memset(g_opts[oid].v, 0, sizeof(g_opts[oid].v));
    zf_push(ctx, (zf_cell)oid);
}

void nf_adam_step(zf_ctx *ctx)
{
    int oid = (int)zf_pop(ctx);
    if (oid < 0 || oid >= NF_MAX_OPTS || !g_opts[oid].active) {
        fprintf(stderr, "adam-step: invalid optimizer %d\n", oid);
        return;
    }
    NfAdam *opt = &g_opts[oid];
    opt->step++;
    float bc1 = 1.0f - powf(opt->beta1, (float)opt->step);
    float bc2 = 1.0f - powf(opt->beta2, (float)opt->step);

    for (int pi = 0; pi < g_n_params; pi++) {
        int h = g_params[pi];
        NfTensor *t = nf_tensor_get(h);
        if (!t || !t->grad) continue;

        int n = t->rows * t->cols;
        if (!opt->m[pi]) {
            opt->m[pi] = (float *)calloc((size_t)n, sizeof(float));
            opt->v[pi] = (float *)calloc((size_t)n, sizeof(float));
            if (!opt->m[pi] || !opt->v[pi]) {
                fprintf(stderr, "adam-step: moment alloc failed for param %d\n", pi);
                continue;
            }
        }
        for (int i = 0; i < n; i++) {
            float g = t->grad[i];
            opt->m[pi][i] = opt->beta1 * opt->m[pi][i] + (1.0f - opt->beta1) * g;
            opt->v[pi][i] = opt->beta2 * opt->v[pi][i] + (1.0f - opt->beta2) * g * g;
            float m_hat = opt->m[pi][i] / bc1;
            float v_hat = opt->v[pi][i] / bc2;
            t->data[i] -= opt->lr * m_hat / (sqrtf(v_hat) + opt->eps);
        }
    }
}
