# Plan: Adopt the new zForth words in existing Forth scripts

**Date:** 2026-06-02
**Status:** Deferred (parked)
**Depends on:** [`docs/plans/2026-05-17-add-tier-1-2-standard-forth-words-to-the-wf-zforth.md`](../2026-05-17-add-tier-1-2-standard-forth-words-to-the-wf-zforth.md) — the bootstrap must already define the new words.

## Context

Phase 1 added the tier 1+2 CORE words plus `mod` to `kCoreBootstrap`
(`engine/stubs/scripting_zforth.cc`): `0=`, `0<`, `0>`, `negate`, `abs`, `min`, `max`, `?dup`, `nip`,
`tuck`, `-rot`, `2dup`, `2drop`, `2swap`, `+!`, `mod`.

**Already done (2026-06-02):** `docs/scripting-languages.md` — all Forth example scripts updated to use
`0=`, `?dup if … then`, `1+`, `read-mailbox if` (direct non-zero), and the Rules note was expanded.
The scope below is the live level scripts only.

Remaining live level scripts (`wflevels/*/blender_*.py`, `.lev`, `.aib`) still use the verbose
workarounds. **Pure cleanup — the workarounds work fine**, so this is parked until there's reason to
touch these levels (or a quiet moment to do it carefully); it is not blocking anything.

This must follow Phase 1 — scripts can't reference words the bootstrap doesn't yet define.

## Source-of-truth rule

Most `.lev` files are *generated* from `wflevels/*/blender_*.py` (e.g. `qbert_practice.lev` ←
`blender_create_qbert.py`); edit the **source** (`blender_*.py`, the one `.aib`, or a hand-authored
`.lev`), then **re-export** the level — never hand-edit a generated `.lev`. Confirm provenance per file
before touching it (snowgoons `.lev` provenance differs — check).

## Three passes, safest first

**Pass A — context-free stack-op collapses (mechanical, low risk).** Pure stack reshuffles, identical
regardless of surroundings:

| Replace | With | Sites (source) |
|---|---|---|
| `over over` | `2dup` | 6 |
| `drop drop` | `2drop` | 8 |
| `swap drop` | `nip` | 11 |
| `swap over` | `tuck` | 0 |

Watch the `over over > if drop drop` / `over over < if …` compare-idioms (e.g.
`blender_create_qbert.py:2516`): collapse the stack ops mechanically, or rewrite with `min`/`max` in
Pass C — don't do both blindly.

**Pass B — zero-test collapses (boundary-aware; low risk, high count).** `: 0= 0 = ;` / `: 0< <0 ;`
are exact aliases, so these are pure readability:

| Replace | With | Sites (source) |
|---|---|---|
| `0 =` | `0=` | ~49 |
| `0 <` | `0<` | ~14 |

Must be word-boundary-aware — do **not** match inside numerics (`10 swap -`, `1.0 =`, `30 <`). Use a
regex like `(^\|[^0-9.])0 = ` and eyeball each hit; a blind `sed` will corrupt literals. `0 swap -`
→ `negate` has ~0 real source sites (skip). Leave existing `not` usages alone — `not` *is* `0=`, so
churning them adds risk for zero gain.

Also in this pass: `read-mailbox 0 <> if` → `read-mailbox if` **when the value is not used after the
branch** (value consumed by `if` alone). Three patterns — pick by need:
- **Value not needed:** `read-mailbox if … then` — direct, idiomatic
- **Value on true branch:** `read-mailbox ?dup if … then` — `?dup` copies non-zero, leaves 0 alone
- **Value on both branches:** `read-mailbox dup 0= if drop … else … then` — keep `dup`

`0 <>` before `if` is never needed just to branch; `if` treats any non-zero as true. All existing
`read-mailbox 0 <> if` sites in the level sources are test-only (confirmed by grep: the value is not
used inside the branch body), so replacement is safe there.

**Pass C — opportunistic semantic adoption (manual, per-site).** Where a script hand-rolls
`abs`/`min`/`max`/`+!`/`2swap`/`mod` inline, swap in the new word. NOT a sweep — each is a judgement
call; do it only where it clearly reads better. (Note: any `over over / * -` "mod" is a latent bug, not
just verbose — `/` is float division; replace those with `mod`.)

**Land level-by-level, not one big diff.**

## Verification

These are live gameplay scripts, so behavior must be byte-for-byte preserved. Per touched level:

1. **Re-export** from source (Blender export / `levcomp`), not hand-edited `.lev`.
2. **Diff the re-exported `.lev`** against the pre-change artifact — confirm *only* the intended Forth
   tokens changed (a noisy diff means the export is picking up something else; stop and investigate).
3. **Re-run the level's existing headless/bridge test** and compare: qbert `tests/` screenshots, SMB
   brick/coin tests, snowgoons smoke test, etc. Identical gameplay = pass.
4. Roll up only levels that pass all three; never batch-commit unverified levels.
