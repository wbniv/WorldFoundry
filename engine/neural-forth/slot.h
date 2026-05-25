/* slot.h — ∂4-style trainable slot sub-VM.
 *
 * Each slot is a typed hole in a Forth script that executes a soft mixture over
 * a fixed operation vocabulary (Bošnjak et al. ICML 2017, §3 CHOOSE primitive).
 *
 * Three-stage structure: encoder → transform → decoder
 *   encoder:   input tensor handles → latent scalar values
 *   transform: CHOOSE (soft op mixture over vocabulary)
 *   decoder:   latent → output tensor
 *
 * Current implementation (Stage 7): 2-input, 1-output slots.
 * Vocabulary (n_in=2): {a+b, a-b, a*b, min(a,b), max(a,b)}.
 * Logit parameters are learnable tensors; softmax temperature is annealed.
 */
#pragma once
#include <zforth.h>

#define NF_MAX_SLOTS       16
#define NF_SLOT_VOCAB_SIZE  5  /* +, -, *, min, max */
#define NF_SLOT_MAX_IN      8

#ifdef __cplusplus
extern "C" {
#endif

/* ── Slot lifecycle ──────────────────────────────────────────────────────── */

void nf_slot_declare (zf_ctx *ctx); /* ( n_in n_out -- slot_h )  create slot */
void nf_slot_run     (zf_ctx *ctx); /* ( t_1..t_N slot_h -- result_h )       */
void nf_slot_params  (zf_ctx *ctx); /* ( slot_h -- logits_h )                */
void nf_slot_temp    (zf_ctx *ctx); /* ( temp slot_h -- )  softmax temp      */

/* Called by autograd.c backward to accumulate slot logit gradients. */
void nf_slot_backward(int slot_id, int logits_h, int result_h);

/* Called from nf_init() to register SLOT: / PERMUTE-SLOT: parsing words. */
void nf_slot_register_parsing_words(zf_ctx *ctx);

#ifdef __cplusplus
}
#endif
