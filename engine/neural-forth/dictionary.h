/* dictionary.h — word ID constants for the neural-forth dispatch table.
 *
 * Each NF Forth word has a unique integer ID.  The Forth word definition is:
 *   : <name>  <ID> nf ;
 * which pushes ID on the stack then calls `nf` (the gate to syscall 200).
 * nf_dispatch() pops the ID and routes to the handler.
 *
 * Add new words at the END of the list; never reorder existing IDs (that would
 * invalidate compiled scripts that cache them).
 */
#pragma once

/* ── Stage 1: diagnostics ───────────────────────────────────────────────── */
#define NF_WORD_PING            0

/* ── Stage 2: tensors ──────────────────────────────────────────────────── */
#define NF_WORD_TENSOR_NEW      1
#define NF_WORD_TENSOR_FREE     2
#define NF_WORD_T_GET           3   /* T@ */
#define NF_WORD_T_SET           4   /* T! */
#define NF_WORD_MATMUL          5
#define NF_WORD_T_ADD           6
#define NF_WORD_T_MUL           7
#define NF_WORD_SIGMOID         8
#define NF_WORD_RELU            9
#define NF_WORD_TANH_W          10  /* avoid clash with C's tanh */
#define NF_WORD_SOFTMAX         11

/* ── Stage 3: autograd ─────────────────────────────────────────────────── */
#define NF_WORD_WITH_TAPE       12
#define NF_WORD_END_TAPE        13
#define NF_WORD_BACKWARD        14
#define NF_WORD_ZERO_GRAD       15

/* ── Stage 4: NN primitives ────────────────────────────────────────────── */
#define NF_WORD_LINEAR          16
#define NF_WORD_FORWARD         17
#define NF_WORD_LOSS_CE         18
#define NF_WORD_LOSS_MSE        19
#define NF_WORD_ADAM_NEW        20
#define NF_WORD_ADAM_STEP       21

/* ── Stage 5: fuzzy ────────────────────────────────────────────────────── */
#define NF_WORD_TRIANGULAR      22
#define NF_WORD_TRAPEZOIDAL     23
#define NF_WORD_GAUSSIAN        24
#define NF_WORD_MU_GET          25  /* MU@ */
#define NF_WORD_DEFUZZ_COG      26
#define NF_WORD_FAND            27
#define NF_WORD_FOR_LOGIC       28
#define NF_WORD_FNOT            29
#define NF_WORD_FIMPLIES        30
#define NF_WORD_T_NORM_SET      31  /* T-NORM! */
#define NF_WORD_S_NORM_SET      32  /* S-NORM! */

/* ── Stage 5 extras: fuzzy accumulator ─────────────────────────────────── */
#define NF_WORD_FUZZY_RESET     33
#define NF_WORD_FUZZY_ADD       34

/* ── Stage 7: ∂4 slots ─────────────────────────────────────────────────── */
#define NF_WORD_SLOT_DECLARE    35
#define NF_WORD_SLOT_RUN        36
#define NF_WORD_SLOT_PARAMS     37  /* .PARAMS */
#define NF_WORD_SLOT_TEMP       38  /* TEMPERATURE! */

#define NF_WORD_COUNT           39
