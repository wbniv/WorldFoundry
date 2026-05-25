/* fuzzy.h — membership functions, T-norms / T-conorms, COG defuzzification.
 *
 * Membership functions (MFs) are stored in a global pool and referenced by
 * integer handles (same pattern as tensors).  Fuzzy truth values (mu) are
 * passed as plain zf_cell floats on the Forth stack.
 *
 * Defuzzification uses an accumulator pattern: call fuzzy-reset, then
 * fuzzy-add for each fired rule, then defuzz-cog to get the crisp output.
 */
#pragma once
#include <zforth.h>

#define NF_MAX_MFS 64

#ifdef __cplusplus
extern "C" {
#endif

/* ── MF creation ─────────────────────────────────────────────────────────── */

void nf_triangular  (zf_ctx *ctx); /* ( a b c -- mf )      triangular MF     */
void nf_trapezoidal (zf_ctx *ctx); /* ( a b c d -- mf )    trapezoidal MF    */
void nf_gaussian    (zf_ctx *ctx); /* ( mean std -- mf )   gaussian MF       */

/* ── MF evaluation ───────────────────────────────────────────────────────── */

void nf_mu_get      (zf_ctx *ctx); /* ( x mf -- mu )       membership [0,1]  */

/* ── Defuzzification accumulator ─────────────────────────────────────────── */

void nf_fuzzy_reset (zf_ctx *ctx); /* ( -- )               clear accumulator */
void nf_fuzzy_add   (zf_ctx *ctx); /* ( mu mf -- )         add rule output   */
void nf_defuzz_cog  (zf_ctx *ctx); /* ( -- x )             COG, universe [0,1] */

/* ── Fuzzy logic operators ───────────────────────────────────────────────── */

void nf_fand        (zf_ctx *ctx); /* ( a b -- c )  T-norm                   */
void nf_for_logic   (zf_ctx *ctx); /* ( a b -- c )  S-norm                   */
void nf_fnot        (zf_ctx *ctx); /* ( a -- b )    complement: 1 - a        */
void nf_fimplies    (zf_ctx *ctx); /* ( a b -- c )  Mamdani: min(a, b)       */

/* ── T-norm / S-norm selection ───────────────────────────────────────────── */

void nf_t_norm_set  (zf_ctx *ctx); /* ( idx -- ) 0=Zadeh 1=Lukasiewicz 2=product */
void nf_s_norm_set  (zf_ctx *ctx); /* ( idx -- ) 0=Zadeh 1=Lukasiewicz 2=product */

/* Internal C accessor (used by example scripts and tests) */
float nf_mf_eval(int mf_h, float x);

#ifdef __cplusplus
}
#endif
