/* neural_forth_test.cc — neural-forth unit tests.
 *
 * Standalone binary; provides the minimal zForth host callbacks needed to
 * run neural-forth outside the game engine.  Link against zforth static lib
 * and the neural-forth C files (see CMakeLists.txt nf_test target).
 *
 * Usage:  ./nf_test          (exit 0 on all pass, 1 on any fail)
 *         ctest -R neural_forth
 */
extern "C" {
#include <zforth.h>
}
#include "neural_forth.h"

#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>

/* ── Minimal zForth host callbacks ─────────────────────────────────────── */

static zf_ctx g_ctx;

zf_input_state zf_host_sys(zf_ctx *ctx, zf_syscall_id id, const char * /*last_word*/)
{
    /* Standard I/O syscalls */
    if (id == ZF_SYSCALL_EMIT) {
        char c = (char)zf_pop(ctx);
        fputc(c, stderr);
        return ZF_INPUT_INTERPRET;
    }
    if (id == ZF_SYSCALL_PRINT) {
        zf_cell v = zf_pop(ctx);
        fprintf(stderr, "%g ", (double)v);
        return ZF_INPUT_INTERPRET;
    }

    /* Neural-forth dispatch gate: syscall 200 = ZF_SYSCALL_USER + 72 */
    int custom = (int)id - (int)ZF_SYSCALL_USER;
    if (custom == 72) {
        int word_id = (int)zf_pop(ctx);
        nf_dispatch(ctx, word_id);
        return ZF_INPUT_INTERPRET;
    }

    fprintf(stderr, "test: unhandled sys %d\n", (int)id);
    return ZF_INPUT_INTERPRET;
}

void zf_host_trace(zf_ctx * /*ctx*/, const char *fmt, va_list va)
{
    vfprintf(stderr, fmt, va);
}

zf_cell zf_host_parse_num(zf_ctx *ctx, const char *buf)
{
    char *end = nullptr;
    float v = strtof(buf, &end);
    if (end && *end == '\0') return (zf_cell)v;
    zf_abort(ctx, ZF_ABORT_NOT_A_WORD);
    return (zf_cell)0;
}

/* ── Test helpers ───────────────────────────────────────────────────────── */

static int g_pass = 0, g_fail = 0;

static void check(const char *name, bool ok)
{
    if (ok) { printf("PASS  %s\n", name); ++g_pass; }
    else     { printf("FAIL  %s\n", name); ++g_fail; }
}

/* Evaluate a Forth snippet and return the result code. */
static zf_result eval(const char *src)
{
    return zf_eval(&g_ctx, src);
}

/* ── Bootstrap (minimal — no kCoreBootstrap needed for Stage 1) ─────────── */

static void bootstrap()
{
    zf_init(&g_ctx, 0 /* no trace */);
    zf_bootstrap(&g_ctx);
    nf_init(&g_ctx);
}

/* ── Stage 1 tests ──────────────────────────────────────────────────────── */

static void test_gate_word_defined()
{
    /* `nf` must be callable without aborting */
    check("gate-word-nf-exists", eval("0 nf") == ZF_OK);
}

static void test_ping()
{
    /* nf-ping: ( -- ) — no stack effect, no abort */
    zf_result r = eval("nf-ping");
    check("nf-ping-no-abort", r == ZF_OK);
}

static void test_unknown_word_id()
{
    /* A word-id beyond NF_WORD_COUNT should print an error but not crash. */
    zf_result r = eval("9999 nf");
    check("unknown-word-id-no-crash", r == ZF_OK);
}

/* ── Stage 2 tests — tensor library ─────────────────────────────────────── */

#include "tensor.h"
#include <cmath>

static void test_tensor_alloc_free()
{
    int h = nf_tensor_alloc(3, 4);
    check("tensor-alloc-valid-handle", h >= 0 && h < NF_MAX_TENSORS);
    NfTensor *t = nf_tensor_get(h);
    check("tensor-alloc-shape-rows", t && t->rows == 3);
    check("tensor-alloc-shape-cols", t && t->cols == 4);
    check("tensor-alloc-zeroed",     t && t->data[0] == 0.0f);
    nf_tensor_release(h);
    check("tensor-free-slot-reuse",  nf_tensor_get(h) == NULL);
}

static void test_tensor_set_get()
{
    int h = nf_tensor_alloc(2, 3);
    NfTensor *t = nf_tensor_get(h);
    t->data[0 * 3 + 1] = 3.14f;  /* row 0, col 1 */
    t->data[1 * 3 + 2] = 2.71f;  /* row 1, col 2 */
    check("t-set-get-[0,1]", fabsf(t->data[0 * 3 + 1] - 3.14f) < 1e-5f);
    check("t-set-get-[1,2]", fabsf(t->data[1 * 3 + 2] - 2.71f) < 1e-5f);
    nf_tensor_release(h);
}

static void test_tensor_forth_roundtrip()
{
    /* Verify t! and t@ via Forth words; use C to arrange the stack correctly
     * (same pattern as test_matmul_identity — >r inside zf_eval is unsafe). */
    int h = nf_tensor_alloc(2, 3);
    /* t!  ( v i j t -- ) */
    zf_push(&g_ctx, (zf_cell)1.0f);
    zf_push(&g_ctx, (zf_cell)0);
    zf_push(&g_ctx, (zf_cell)1);
    zf_push(&g_ctx, (zf_cell)h);
    eval("t!");
    /* t@  ( i j t -- v ) */
    zf_push(&g_ctx, (zf_cell)0);
    zf_push(&g_ctx, (zf_cell)1);
    zf_push(&g_ctx, (zf_cell)h);
    eval("t@");
    zf_cell val = zf_pop(&g_ctx);
    check("forth-t!-t@-roundtrip", fabsf((float)val - 1.0f) < 1e-5f);
    nf_tensor_release(h);
}

static void test_matmul_identity()
{
    /* A = [[1,0],[0,1]] (2×2 identity), B = [[3,4],[5,6]]
     * C = A×B should equal B. */
    int ha = nf_tensor_alloc(2, 2);
    int hb = nf_tensor_alloc(2, 2);
    NfTensor *a = nf_tensor_get(ha);
    NfTensor *b = nf_tensor_get(hb);
    a->data[0] = 1; a->data[1] = 0;
    a->data[2] = 0; a->data[3] = 1;
    b->data[0] = 3; b->data[1] = 4;
    b->data[2] = 5; b->data[3] = 6;

    /* Push handles and call matmul via Forth */
    zf_push(&g_ctx, (zf_cell)ha);
    zf_push(&g_ctx, (zf_cell)hb);
    eval("matmul");
    int hc = (int)zf_pop(&g_ctx);
    NfTensor *c = nf_tensor_get(hc);
    check("matmul-identity-[0,0]", c && fabsf(c->data[0] - 3.0f) < 1e-5f);
    check("matmul-identity-[0,1]", c && fabsf(c->data[1] - 4.0f) < 1e-5f);
    check("matmul-identity-[1,0]", c && fabsf(c->data[2] - 5.0f) < 1e-5f);
    check("matmul-identity-[1,1]", c && fabsf(c->data[3] - 6.0f) < 1e-5f);
    nf_tensor_release(ha); nf_tensor_release(hb); nf_tensor_release(hc);
}

static void test_matmul_2x3_3x2()
{
    /* A(2×3) × B(3×2) → C(2×2)
     * A = [[1,2,3],[4,5,6]], B = [[7,8],[9,10],[11,12]]
     * C[0,0]=1*7+2*9+3*11=58, C[0,1]=1*8+2*10+3*12=64
     * C[1,0]=4*7+5*9+6*11=139, C[1,1]=4*8+5*10+6*12=154 */
    int ha = nf_tensor_alloc(2, 3);
    int hb = nf_tensor_alloc(3, 2);
    NfTensor *a = nf_tensor_get(ha);
    NfTensor *b = nf_tensor_get(hb);
    float ad[] = {1,2,3,4,5,6};
    float bd[] = {7,8,9,10,11,12};
    for (int i=0;i<6;i++) { a->data[i]=ad[i]; b->data[i]=bd[i]; }

    zf_push(&g_ctx, (zf_cell)ha);
    zf_push(&g_ctx, (zf_cell)hb);
    eval("matmul");
    int hc = (int)zf_pop(&g_ctx);
    NfTensor *c = nf_tensor_get(hc);
    check("matmul-2x3x2-[0,0]", c && fabsf(c->data[0] -  58.0f) < 1e-3f);
    check("matmul-2x3x2-[0,1]", c && fabsf(c->data[1] -  64.0f) < 1e-3f);
    check("matmul-2x3x2-[1,0]", c && fabsf(c->data[2] - 139.0f) < 1e-3f);
    check("matmul-2x3x2-[1,1]", c && fabsf(c->data[3] - 154.0f) < 1e-3f);
    nf_tensor_release(ha); nf_tensor_release(hb); nf_tensor_release(hc);
}

static void test_sigmoid_range()
{
    int ha = nf_tensor_alloc(1, 4);
    NfTensor *a = nf_tensor_get(ha);
    a->data[0] = -100.0f; a->data[1] = 0.0f;
    a->data[2] =  100.0f; a->data[3] = 1.0f;
    zf_push(&g_ctx, (zf_cell)ha);
    eval("sigmoid");
    int hb = (int)zf_pop(&g_ctx);
    NfTensor *b = nf_tensor_get(hb);
    check("sigmoid-large-neg-→0", b && fabsf(b->data[0] - 0.0f) < 1e-4f);
    check("sigmoid-zero-→0.5",    b && fabsf(b->data[1] - 0.5f) < 1e-5f);
    check("sigmoid-large-pos-→1", b && fabsf(b->data[2] - 1.0f) < 1e-4f);
    check("sigmoid-output-in-01", b && b->data[3] > 0.0f && b->data[3] < 1.0f);
    nf_tensor_release(ha); nf_tensor_release(hb);
}

static void test_relu()
{
    int ha = nf_tensor_alloc(1, 4);
    NfTensor *a = nf_tensor_get(ha);
    a->data[0] = -3.0f; a->data[1] = 0.0f;
    a->data[2] =  2.5f; a->data[3] = -0.001f;
    zf_push(&g_ctx, (zf_cell)ha);
    eval("relu");
    int hb = (int)zf_pop(&g_ctx);
    NfTensor *b = nf_tensor_get(hb);
    check("relu-neg-→0",   b && b->data[0] == 0.0f);
    check("relu-zero-→0",  b && b->data[1] == 0.0f);
    check("relu-pos-pass", b && fabsf(b->data[2] - 2.5f) < 1e-6f);
    check("relu-small-neg-→0", b && b->data[3] == 0.0f);
    nf_tensor_release(ha); nf_tensor_release(hb);
}

static void test_softmax_sums_to_one()
{
    int ha = nf_tensor_alloc(1, 5);
    NfTensor *a = nf_tensor_get(ha);
    a->data[0]=1.0f; a->data[1]=2.0f; a->data[2]=3.0f; a->data[3]=4.0f; a->data[4]=5.0f;
    zf_push(&g_ctx, (zf_cell)ha);
    eval("softmax");
    int hb = (int)zf_pop(&g_ctx);
    NfTensor *b = nf_tensor_get(hb);
    float sum = 0.0f;
    if (b) for (int i=0; i<5; i++) sum += b->data[i];
    check("softmax-sums-to-1", fabsf(sum - 1.0f) < 1e-5f);
    check("softmax-monotone",  b && b->data[4] > b->data[3] && b->data[3] > b->data[2]);
    nf_tensor_release(ha); nf_tensor_release(hb);
}

/* ── Stage 3 tests — autograd tape ──────────────────────────────────────── */

#include "autograd.h"

static void test_autograd_sigmoid_grad()
{
    int ha = nf_tensor_alloc(1, 1);
    nf_tensor_get(ha)->data[0] = 2.0f;

    nf_with_tape(&g_ctx);
    zf_push(&g_ctx, (zf_cell)ha);
    eval("sigmoid");
    int hb = (int)zf_pop(&g_ctx);
    zf_push(&g_ctx, (zf_cell)hb);
    nf_backward(&g_ctx);
    nf_end_tape(&g_ctx);

    float y    = nf_tensor_get(hb)->data[0];
    float anal = nf_tensor_get(ha)->grad[0];
    float expt = y * (1.0f - y);
    check("sigmoid-backward-analytical", fabsf(anal - expt) < 1e-6f);

    /* Finite-difference check (tape inactive during FD calls) */
    float eps = 1e-3f;
    int hp = nf_tensor_alloc(1, 1), hm = nf_tensor_alloc(1, 1);
    nf_tensor_get(hp)->data[0] = 2.0f + eps;
    nf_tensor_get(hm)->data[0] = 2.0f - eps;
    zf_push(&g_ctx, (zf_cell)hp); eval("sigmoid");
    int hbp = (int)zf_pop(&g_ctx);
    zf_push(&g_ctx, (zf_cell)hm); eval("sigmoid");
    int hbm = (int)zf_pop(&g_ctx);
    float fd = (nf_tensor_get(hbp)->data[0] - nf_tensor_get(hbm)->data[0]) / (2.0f * eps);
    check("sigmoid-backward-fd-match", fabsf(anal - fd) < 1e-4f);

    nf_tensor_release(ha); nf_tensor_release(hb);
    nf_tensor_release(hp);  nf_tensor_release(hm);
    nf_tensor_release(hbp); nf_tensor_release(hbm);
}

static void test_autograd_matmul_grad()
{
    /* C = A @ B, A=[[3]], B=[[5]] → dL/dA=5, dL/dB=3 */
    int ha = nf_tensor_alloc(1, 1), hb = nf_tensor_alloc(1, 1);
    nf_tensor_get(ha)->data[0] = 3.0f;
    nf_tensor_get(hb)->data[0] = 5.0f;

    nf_with_tape(&g_ctx);
    zf_push(&g_ctx, (zf_cell)ha);
    zf_push(&g_ctx, (zf_cell)hb);
    eval("matmul");
    int hc = (int)zf_pop(&g_ctx);
    zf_push(&g_ctx, (zf_cell)hc);
    nf_backward(&g_ctx);
    nf_end_tape(&g_ctx);

    check("matmul-grad-A", fabsf(nf_tensor_get(ha)->grad[0] - 5.0f) < 1e-5f);
    check("matmul-grad-B", fabsf(nf_tensor_get(hb)->grad[0] - 3.0f) < 1e-5f);
    nf_tensor_release(ha); nf_tensor_release(hb); nf_tensor_release(hc);
}

static void test_autograd_relu_grad()
{
    /* relu([−1, 0, 2]) → grad_x = [0, 0, 1] (dL/dx_i = 1 for x_i>0) */
    int ha = nf_tensor_alloc(1, 3);
    nf_tensor_get(ha)->data[0] = -1.0f;
    nf_tensor_get(ha)->data[1] =  0.0f;
    nf_tensor_get(ha)->data[2] =  2.0f;

    nf_with_tape(&g_ctx);
    zf_push(&g_ctx, (zf_cell)ha);
    eval("relu");
    int hb = (int)zf_pop(&g_ctx);
    zf_push(&g_ctx, (zf_cell)hb);
    nf_backward(&g_ctx);
    nf_end_tape(&g_ctx);

    NfTensor *a = nf_tensor_get(ha);
    check("relu-grad-neg-→0",  fabsf(a->grad[0] - 0.0f) < 1e-6f);
    check("relu-grad-zero-→0", fabsf(a->grad[1] - 0.0f) < 1e-6f);
    check("relu-grad-pos-→1",  fabsf(a->grad[2] - 1.0f) < 1e-6f);
    nf_tensor_release(ha); nf_tensor_release(hb);
}

static void test_autograd_zero_grad()
{
    int ha = nf_tensor_alloc(1, 2);
    nf_with_tape(&g_ctx);
    zf_push(&g_ctx, (zf_cell)ha);
    eval("sigmoid");
    int hb = (int)zf_pop(&g_ctx);
    zf_push(&g_ctx, (zf_cell)hb);
    nf_backward(&g_ctx);
    nf_end_tape(&g_ctx);
    nf_zero_grad(&g_ctx);
    NfTensor *a = nf_tensor_get(ha);
    check("zero-grad-clears", a && a->grad &&
          a->grad[0] == 0.0f && a->grad[1] == 0.0f);
    nf_tensor_release(ha); nf_tensor_release(hb);
}

/* ── Stage 4 tests — NN primitives ──────────────────────────────────────── */

#include "nn.h"

static void test_xor_mlp()
{
    /* 2→4 ReLU → 1 sigmoid, trained on XOR for 3000 steps with Adam (lr=0.1).
     * Stochastic: one sample per step, cycling through all 4 XOR pairs.
     * Final average MSE over all 4 pairs must be < 0.05. */

    static const float xs[4][2] = {{0,0},{0,1},{1,0},{1,1}};
    static const float yt[4]    = {0.0f, 1.0f, 1.0f, 0.0f};

    /* Network architecture */
    zf_push(&g_ctx, (zf_cell)2); zf_push(&g_ctx, (zf_cell)4);
    nf_linear(&g_ctx);
    int l1 = (int)zf_pop(&g_ctx);

    zf_push(&g_ctx, (zf_cell)4); zf_push(&g_ctx, (zf_cell)1);
    nf_linear(&g_ctx);
    int l2 = (int)zf_pop(&g_ctx);

    /* Allocate persistent input and target tensors */
    int x_h      = nf_tensor_alloc(2, 1);
    int target_h = nf_tensor_alloc(1, 1);

    /* Adam with lr=0.1 */
    zf_push(&g_ctx, (zf_cell)0.1f);
    nf_adam_new(&g_ctx);
    int opt = (int)zf_pop(&g_ctx);

    float last_loss = 1e9f;
    for (int step = 0; step < 3000; step++) {
        int s = step % 4;
        nf_tensor_get(x_h)->data[0] = xs[s][0];
        nf_tensor_get(x_h)->data[1] = xs[s][1];
        nf_tensor_get(target_h)->data[0] = yt[s];

        /* Forward pass inside tape scope */
        nf_with_tape(&g_ctx);

        zf_push(&g_ctx, (zf_cell)x_h);
        zf_push(&g_ctx, (zf_cell)l1);
        nf_forward(&g_ctx);            /* stack: [h1_pre] */
        nf_relu(&g_ctx);               /* stack: [h1] */
        zf_push(&g_ctx, (zf_cell)l2);
        nf_forward(&g_ctx);            /* stack: [h2_pre] */
        nf_sigmoid(&g_ctx);            /* stack: [pred] */

        zf_push(&g_ctx, (zf_cell)target_h);
        nf_loss_mse(&g_ctx);           /* stack: [loss] */
        int loss_h = (int)zf_pop(&g_ctx);
        last_loss = nf_tensor_get(loss_h)->data[0];

        zf_push(&g_ctx, (zf_cell)loss_h);
        nf_backward(&g_ctx);

        nf_tape_free_outputs();        /* free all tape-created intermediates */
        nf_end_tape(&g_ctx);

        zf_push(&g_ctx, (zf_cell)opt);
        nf_adam_step(&g_ctx);
        nf_zero_grad(&g_ctx);
    }

    /* Evaluate all 4 XOR samples — average MSE */
    float total_mse = 0.0f;
    for (int s = 0; s < 4; s++) {
        nf_tensor_get(x_h)->data[0] = xs[s][0];
        nf_tensor_get(x_h)->data[1] = xs[s][1];
        nf_tensor_get(target_h)->data[0] = yt[s];

        zf_push(&g_ctx, (zf_cell)x_h);
        zf_push(&g_ctx, (zf_cell)l1);
        nf_forward(&g_ctx);
        nf_relu(&g_ctx);
        zf_push(&g_ctx, (zf_cell)l2);
        nf_forward(&g_ctx);
        nf_sigmoid(&g_ctx);
        int pred_h = (int)zf_pop(&g_ctx);

        float d = nf_tensor_get(pred_h)->data[0] - yt[s];
        total_mse += d * d;
        nf_tensor_release(pred_h);
    }
    (void)last_loss;
    total_mse /= 4.0f;
    check("xor-mlp-converges", total_mse < 0.05f);

    nf_tensor_release(x_h);
    nf_tensor_release(target_h);
}

/* ── Stage 5 tests — fuzzy primitives ───────────────────────────────────── */

#include "fuzzy.h"

static void test_triangular_mf()
{
    /* triangular(0, 0.5, 1): μ(0)=0, μ(0.5)=1, μ(0.25)=0.5, μ(1)=0 */
    zf_push(&g_ctx, (zf_cell)0.0f);
    zf_push(&g_ctx, (zf_cell)0.5f);
    zf_push(&g_ctx, (zf_cell)1.0f);
    nf_triangular(&g_ctx);
    int mf = (int)zf_pop(&g_ctx);

    check("tri-mu-at-left-boundary",  fabsf(nf_mf_eval(mf, 0.0f)  - 0.0f) < 1e-5f);
    check("tri-mu-at-peak",           fabsf(nf_mf_eval(mf, 0.5f)  - 1.0f) < 1e-5f);
    check("tri-mu-at-midpoint",       fabsf(nf_mf_eval(mf, 0.25f) - 0.5f) < 1e-5f);
    check("tri-mu-at-right-boundary", fabsf(nf_mf_eval(mf, 1.0f)  - 0.0f) < 1e-5f);
    check("tri-mu-outside",           fabsf(nf_mf_eval(mf, 1.5f)  - 0.0f) < 1e-5f);
}

static void test_trapezoidal_mf()
{
    /* trapezoidal(0, 0.25, 0.75, 1): flat top between 0.25 and 0.75 */
    zf_push(&g_ctx, (zf_cell)0.0f);
    zf_push(&g_ctx, (zf_cell)0.25f);
    zf_push(&g_ctx, (zf_cell)0.75f);
    zf_push(&g_ctx, (zf_cell)1.0f);
    nf_trapezoidal(&g_ctx);
    int mf = (int)zf_pop(&g_ctx);

    check("trap-mu-flat-top",   fabsf(nf_mf_eval(mf, 0.5f)  - 1.0f) < 1e-5f);
    check("trap-mu-left-ramp",  fabsf(nf_mf_eval(mf, 0.125f)- 0.5f) < 1e-5f);
    check("trap-mu-right-ramp", fabsf(nf_mf_eval(mf, 0.875f)- 0.5f) < 1e-5f);
    check("trap-mu-outside",    fabsf(nf_mf_eval(mf, -0.5f) - 0.0f) < 1e-5f);
}

static void test_t_norms()
{
    /* Zadeh min: T(0.3, 0.7) = 0.3 */
    zf_push(&g_ctx, (zf_cell)0); nf_t_norm_set(&g_ctx);
    zf_push(&g_ctx, (zf_cell)0.3f);
    zf_push(&g_ctx, (zf_cell)0.7f);
    nf_fand(&g_ctx);
    float r = (float)zf_pop(&g_ctx);
    check("zadeh-T-min", fabsf(r - 0.3f) < 1e-5f);

    /* Lukasiewicz: T(0.4, 0.8) = max(0, 0.4+0.8-1) = 0.2 */
    zf_push(&g_ctx, (zf_cell)1); nf_t_norm_set(&g_ctx);
    zf_push(&g_ctx, (zf_cell)0.4f);
    zf_push(&g_ctx, (zf_cell)0.8f);
    nf_fand(&g_ctx);
    r = (float)zf_pop(&g_ctx);
    check("lukasiewicz-T", fabsf(r - 0.2f) < 1e-5f);

    /* Product: T(0.5, 0.6) = 0.3 */
    zf_push(&g_ctx, (zf_cell)2); nf_t_norm_set(&g_ctx);
    zf_push(&g_ctx, (zf_cell)0.5f);
    zf_push(&g_ctx, (zf_cell)0.6f);
    nf_fand(&g_ctx);
    r = (float)zf_pop(&g_ctx);
    check("product-T", fabsf(r - 0.3f) < 1e-5f);

    zf_push(&g_ctx, (zf_cell)0); nf_t_norm_set(&g_ctx); /* reset to Zadeh */
}

static void test_fnot_fimplies()
{
    zf_push(&g_ctx, (zf_cell)0.3f); nf_fnot(&g_ctx);
    check("fnot-0.3", fabsf((float)zf_pop(&g_ctx) - 0.7f) < 1e-5f);

    /* fimplies = Mamdani min(a,b) */
    zf_push(&g_ctx, (zf_cell)0.6f);
    zf_push(&g_ctx, (zf_cell)0.4f);
    nf_fimplies(&g_ctx);
    check("fimplies-min", fabsf((float)zf_pop(&g_ctx) - 0.4f) < 1e-5f);
}

static void test_defuzz_cog()
{
    /* Single triangular MF centred at 0.5, clipped at mu=1.0.
     * COG should be very close to 0.5. */
    zf_push(&g_ctx, (zf_cell)0.0f);
    zf_push(&g_ctx, (zf_cell)0.5f);
    zf_push(&g_ctx, (zf_cell)1.0f);
    nf_triangular(&g_ctx);
    int mf = (int)zf_pop(&g_ctx);

    nf_fuzzy_reset(&g_ctx);
    zf_push(&g_ctx, (zf_cell)1.0f);  /* mu = 1 (full clip) */
    zf_push(&g_ctx, (zf_cell)mf);
    nf_fuzzy_add(&g_ctx);
    nf_defuzz_cog(&g_ctx);
    float cog = (float)zf_pop(&g_ctx);
    check("defuzz-cog-symmetric", fabsf(cog - 0.5f) < 0.01f);

    /* Two opposing MFs: triangular at 0.25 and 0.75, equal mu.
     * COG should be ≈ 0.5. */
    zf_push(&g_ctx, (zf_cell)0.0f); zf_push(&g_ctx, (zf_cell)0.25f); zf_push(&g_ctx, (zf_cell)0.5f);
    nf_triangular(&g_ctx);
    int mfL = (int)zf_pop(&g_ctx);
    zf_push(&g_ctx, (zf_cell)0.5f); zf_push(&g_ctx, (zf_cell)0.75f); zf_push(&g_ctx, (zf_cell)1.0f);
    nf_triangular(&g_ctx);
    int mfR = (int)zf_pop(&g_ctx);

    nf_fuzzy_reset(&g_ctx);
    zf_push(&g_ctx, (zf_cell)0.8f); zf_push(&g_ctx, (zf_cell)mfL); nf_fuzzy_add(&g_ctx);
    zf_push(&g_ctx, (zf_cell)0.8f); zf_push(&g_ctx, (zf_cell)mfR); nf_fuzzy_add(&g_ctx);
    nf_defuzz_cog(&g_ctx);
    cog = (float)zf_pop(&g_ctx);
    check("defuzz-cog-balanced-pair", fabsf(cog - 0.5f) < 0.02f);
}

/* ── Stage 6 tests — Mamdani NPC smoke test ─────────────────────────────── */

static void test_mamdani_npc_600_ticks()
{
    /* Build MFs (same rule base as mamdani-npc.fth, evaluated via C API to
     * avoid relying on zForth `variable` which needs kCoreBootstrap). */
    auto push = [](float v){ zf_push(&g_ctx, (zf_cell)v); };

    push(0.0f); push(0.0f); push(0.35f); push(0.6f);  nf_trapezoidal(&g_ctx);
    int mfd_close = (int)zf_pop(&g_ctx);
    push(0.4f); push(0.65f); push(1.0f); push(1.0f);  nf_trapezoidal(&g_ctx);
    int mfd_far   = (int)zf_pop(&g_ctx);
    push(0.0f); push(0.0f); push(0.35f); push(0.6f);  nf_trapezoidal(&g_ctx);
    int mfh_low   = (int)zf_pop(&g_ctx);
    push(0.4f); push(0.65f); push(1.0f); push(1.0f);  nf_trapezoidal(&g_ctx);
    int mfh_high  = (int)zf_pop(&g_ctx);
    push(0.0f); push(0.0f); push(0.35f); push(0.6f);  nf_trapezoidal(&g_ctx);
    int mff_low   = (int)zf_pop(&g_ctx);
    push(0.4f); push(0.65f); push(1.0f); push(1.0f);  nf_trapezoidal(&g_ctx);
    int mff_high  = (int)zf_pop(&g_ctx);

    int all_bounded = 1;
    for (int tick = 0; tick < 600; tick++) {
        float dist   = (float)(tick % 100) / 99.0f;
        float health = (float)((tick / 100) % 6) / 5.0f;

        float mu_close = nf_mf_eval(mfd_close, dist);
        float mu_far   = nf_mf_eval(mfd_far,   dist);
        float mu_low   = nf_mf_eval(mfh_low,   health);
        float mu_high  = nf_mf_eval(mfh_high,  health);
        float r1 = mu_close < mu_low  ? mu_close : mu_low;
        float r2 = mu_far   < mu_high ? mu_far   : mu_high;

        nf_fuzzy_reset(&g_ctx);
        push(r1); push((float)mff_high); nf_fuzzy_add(&g_ctx);
        push(r2); push((float)mff_low);  nf_fuzzy_add(&g_ctx);
        nf_defuzz_cog(&g_ctx);
        float flee = (float)zf_pop(&g_ctx);

        if (flee < 0.0f || flee > 1.0f) { all_bounded = 0; break; }
    }
    check("npc-flee-bounded-600-ticks", all_bounded);

    /* Monotone: fixed close distance, more-critical health → higher flee */
    float dist_close = 0.1f;
    float flee_critical, flee_full;

    nf_fuzzy_reset(&g_ctx);
    push(nf_mf_eval(mfd_close, dist_close) < nf_mf_eval(mfh_low,  0.1f) ?
         nf_mf_eval(mfd_close, dist_close) : nf_mf_eval(mfh_low,  0.1f));
    push((float)mff_high); nf_fuzzy_add(&g_ctx);
    push(nf_mf_eval(mfd_far, dist_close) < nf_mf_eval(mfh_high, 0.1f) ?
         nf_mf_eval(mfd_far, dist_close) : nf_mf_eval(mfh_high, 0.1f));
    push((float)mff_low); nf_fuzzy_add(&g_ctx);
    nf_defuzz_cog(&g_ctx);
    flee_critical = (float)zf_pop(&g_ctx);

    nf_fuzzy_reset(&g_ctx);
    push(nf_mf_eval(mfd_close, dist_close) < nf_mf_eval(mfh_low,  0.9f) ?
         nf_mf_eval(mfd_close, dist_close) : nf_mf_eval(mfh_low,  0.9f));
    push((float)mff_high); nf_fuzzy_add(&g_ctx);
    push(nf_mf_eval(mfd_far, dist_close) < nf_mf_eval(mfh_high, 0.9f) ?
         nf_mf_eval(mfd_far, dist_close) : nf_mf_eval(mfh_high, 0.9f));
    push((float)mff_low); nf_fuzzy_add(&g_ctx);
    nf_defuzz_cog(&g_ctx);
    flee_full = (float)zf_pop(&g_ctx);

    check("npc-flee-monotone-health", flee_critical > flee_full);
}

/* ── Stage 7: ∂4 trainable slot ────────────────────────────────────────── */

#include "slot.h"

static void test_slot_forward()
{
    /* With uniform logits (all 0) and inputs a=3.0, b=2.0:
     *   f_0 = 3+2 = 5,  f_1 = 3-2 = 1,  f_2 = 3*2 = 6,
     *   f_3 = min = 2,  f_4 = max = 3
     *   p = [0.2]*5,  y = 0.2*(5+1+6+2+3) = 3.4 */
    zf_push(&g_ctx, (zf_cell)2);
    zf_push(&g_ctx, (zf_cell)1);
    nf_slot_declare(&g_ctx);
    int sid = (int)zf_pop(&g_ctx);
    check("slot-declare-returns-valid-id", sid >= 0);
    if (sid < 0) return;

    int ha = nf_tensor_alloc(1, 1);
    int hb = nf_tensor_alloc(1, 1);
    nf_tensor_get(ha)->data[0] = 3.0f;
    nf_tensor_get(hb)->data[0] = 2.0f;

    /* stack: ha hb sid — slot_run pops sid then (deepest-first) ha, hb */
    zf_push(&g_ctx, (zf_cell)ha);
    zf_push(&g_ctx, (zf_cell)hb);
    zf_push(&g_ctx, (zf_cell)sid);
    nf_slot_run(&g_ctx);
    int res_h = (int)zf_pop(&g_ctx);

    NfTensor *res = nf_tensor_get(res_h);
    check("slot-forward-result-valid", res != NULL);
    if (res)
        check("slot-forward-uniform-logits-avg", fabsf(res->data[0] - 3.4f) < 1e-4f);

    nf_tensor_release(res_h);
    nf_tensor_release(ha);
    nf_tensor_release(hb);
}

static void test_slot_backward_fd()
{
    /* Numerical gradient check: compare analytical grad_logits from backward
     * against finite-difference estimate.  Loss = y^2 (target=0 MSE). */
    zf_push(&g_ctx, (zf_cell)2);
    zf_push(&g_ctx, (zf_cell)1);
    nf_slot_declare(&g_ctx);
    int sid = (int)zf_pop(&g_ctx);
    if (sid < 0) { check("slot-backward-fd-skipped-bad-declare", 0); return; }

    zf_push(&g_ctx, (zf_cell)sid);
    nf_slot_params(&g_ctx);
    int logits_h = (int)zf_pop(&g_ctx);
    NfTensor *logits = nf_tensor_get(logits_h);

    /* Non-uniform logits so softmax isn't trivially flat */
    logits->data[0] = 1.0f; logits->data[1] = 0.5f;
    logits->data[2] = 0.0f; logits->data[3] = -0.5f; logits->data[4] = -1.0f;

    int ha  = nf_tensor_alloc(1, 1); nf_tensor_get(ha)->data[0]  = 3.0f;
    int hb  = nf_tensor_alloc(1, 1); nf_tensor_get(hb)->data[0]  = 2.0f;
    int tgt = nf_tensor_alloc(1, 1); nf_tensor_get(tgt)->data[0] = 0.0f;

    /* ── Analytical gradient ── */
    nf_with_tape(&g_ctx);
    zf_push(&g_ctx, (zf_cell)ha); zf_push(&g_ctx, (zf_cell)hb);
    zf_push(&g_ctx, (zf_cell)sid);
    nf_slot_run(&g_ctx);
    int res_h  = (int)zf_pop(&g_ctx);
    zf_push(&g_ctx, (zf_cell)res_h); zf_push(&g_ctx, (zf_cell)tgt);
    nf_loss_mse(&g_ctx);
    int loss_h = (int)zf_pop(&g_ctx);
    zf_push(&g_ctx, (zf_cell)loss_h);
    nf_backward(&g_ctx);

    float ag[NF_SLOT_VOCAB_SIZE];
    for (int i = 0; i < NF_SLOT_VOCAB_SIZE; i++) ag[i] = logits->grad[i];

    nf_tape_free_outputs();
    nf_end_tape(&g_ctx);
    nf_zero_grad(&g_ctx);

    /* ── Numerical gradient (finite differences, no tape) ── */
    float eps = 1e-3f;
    float ng[NF_SLOT_VOCAB_SIZE];
    for (int i = 0; i < NF_SLOT_VOCAB_SIZE; i++) {
        logits->data[i] += eps;
        zf_push(&g_ctx, (zf_cell)ha); zf_push(&g_ctx, (zf_cell)hb);
        zf_push(&g_ctx, (zf_cell)sid);
        nf_slot_run(&g_ctx);
        int rp = (int)zf_pop(&g_ctx);
        float yp = nf_tensor_get(rp)->data[0];
        nf_tensor_release(rp);

        logits->data[i] -= 2.0f * eps;
        zf_push(&g_ctx, (zf_cell)ha); zf_push(&g_ctx, (zf_cell)hb);
        zf_push(&g_ctx, (zf_cell)sid);
        nf_slot_run(&g_ctx);
        int rm = (int)zf_pop(&g_ctx);
        float ym = nf_tensor_get(rm)->data[0];
        nf_tensor_release(rm);

        logits->data[i] += eps;
        /* MSE vs target=0: loss = y^2 / 1 */
        ng[i] = (yp * yp - ym * ym) / (2.0f * eps);
    }

    int ok = 1;
    for (int i = 0; i < NF_SLOT_VOCAB_SIZE; i++) {
        float diff  = fabsf(ag[i] - ng[i]);
        float scale = fabsf(ag[i]) + fabsf(ng[i]) + 1e-6f;
        if (diff / scale > 0.02f) ok = 0; /* 2% relative tolerance */
    }
    check("slot-backward-fd-gradient-check", ok);

    nf_tensor_release(ha);
    nf_tensor_release(hb);
    nf_tensor_release(tgt);
}

static void test_slot_learns_add()
{
    /* Train a 2-input slot to approximate f(a,b)=a+b for random inputs.
     * After 200 Adam steps the dominant logit should be op_0 (+). */
    zf_push(&g_ctx, (zf_cell)2);
    zf_push(&g_ctx, (zf_cell)1);
    nf_slot_declare(&g_ctx);
    int sid = (int)zf_pop(&g_ctx);
    if (sid < 0) { check("slot-learns-add-skipped", 0); return; }

    float opt_lr = 0.05f;
    zf_push(&g_ctx, (zf_cell)opt_lr);
    nf_adam_new(&g_ctx);
    int opt = (int)zf_pop(&g_ctx);

    /* deterministic pseudo-random inputs */
    unsigned rng = 0xDEADBEEFu;
    float init_loss = -1.0f;
    float final_loss = 0.0f;

    for (int step = 0; step < 300; step++) {
        rng = rng * 1664525u + 1013904223u;
        float a = (float)((rng >> 16) & 0xFF) / 255.0f * 2.0f - 1.0f;
        rng = rng * 1664525u + 1013904223u;
        float b = (float)((rng >> 16) & 0xFF) / 255.0f * 2.0f - 1.0f;

        int ha  = nf_tensor_alloc(1, 1); nf_tensor_get(ha)->data[0]  = a;
        int hb  = nf_tensor_alloc(1, 1); nf_tensor_get(hb)->data[0]  = b;
        int tgt = nf_tensor_alloc(1, 1); nf_tensor_get(tgt)->data[0] = a + b;

        nf_with_tape(&g_ctx);
        zf_push(&g_ctx, (zf_cell)ha); zf_push(&g_ctx, (zf_cell)hb);
        zf_push(&g_ctx, (zf_cell)sid);
        nf_slot_run(&g_ctx);
        int res_h  = (int)zf_pop(&g_ctx);
        zf_push(&g_ctx, (zf_cell)res_h); zf_push(&g_ctx, (zf_cell)tgt);
        nf_loss_mse(&g_ctx);
        int loss_h = (int)zf_pop(&g_ctx);

        float loss_val = nf_tensor_get(loss_h)->data[0];
        if (step == 0)   init_loss  = loss_val;
        if (step == 299) final_loss = loss_val;

        zf_push(&g_ctx, (zf_cell)loss_h);
        nf_backward(&g_ctx);
        nf_tape_free_outputs();
        nf_end_tape(&g_ctx);

        zf_push(&g_ctx, (zf_cell)opt);
        nf_adam_step(&g_ctx);
        nf_zero_grad(&g_ctx);

        nf_tensor_release(ha);
        nf_tensor_release(hb);
        nf_tensor_release(tgt);
    }

    check("slot-learns-add-loss-decreases", final_loss < init_loss * 0.5f);

    /* The + operation (op_0) should have the largest logit */
    zf_push(&g_ctx, (zf_cell)sid);
    nf_slot_params(&g_ctx);
    int logits_h = (int)zf_pop(&g_ctx);
    NfTensor *logits = nf_tensor_get(logits_h);
    int argmax = 0;
    for (int i = 1; i < NF_SLOT_VOCAB_SIZE; i++)
        if (logits->data[i] > logits->data[argmax]) argmax = i;
    check("slot-learns-add-op0-dominant", argmax == 0);
}

/* ── Entry point ────────────────────────────────────────────────────────── */

int main()
{
    bootstrap();

    printf("=== neural-forth unit tests ===\n\n");

    printf("-- Stage 1: diagnostics --\n");
    test_gate_word_defined();
    test_ping();
    test_unknown_word_id();

    printf("\n-- Stage 2: tensor library --\n");
    test_tensor_alloc_free();
    test_tensor_set_get();
    test_tensor_forth_roundtrip();
    test_matmul_identity();
    test_matmul_2x3_3x2();
    test_sigmoid_range();
    test_relu();
    test_softmax_sums_to_one();

    printf("\n-- Stage 3: autograd tape --\n");
    test_autograd_sigmoid_grad();
    test_autograd_matmul_grad();
    test_autograd_relu_grad();
    test_autograd_zero_grad();

    printf("\n-- Stage 4: NN primitives --\n");
    test_xor_mlp();

    printf("\n-- Stage 5: fuzzy primitives --\n");
    test_triangular_mf();
    test_trapezoidal_mf();
    test_t_norms();
    test_fnot_fimplies();
    test_defuzz_cog();

    printf("\n-- Stage 6: Mamdani NPC --\n");
    test_mamdani_npc_600_ticks();

    printf("\n-- Stage 7: ∂4 trainable slot --\n");
    test_slot_forward();
    test_slot_backward_fd();
    test_slot_learns_add();

    printf("\n%d passed, %d failed\n", g_pass, g_fail);
    return g_fail ? 1 : 0;
}
