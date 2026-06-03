# Add tier 1+2 standard Forth words to the WF zForth bootstrap

## Context

The WF zForth bootstrap (`engine/stubs/scripting_zforth.cc` `kCoreBootstrap`) ships a deliberately
minimal subset of standard Forth. On 2026-05-17, while implementing the SMB scrolling-camera Director,
`0=` — an ANS CORE word used in essentially every Forth — turned out to be missing as a single token,
producing `zforth compile error 7 (ZF_ABORT_NOT_A_WORD)`; it was worked around with `not`. TODO item
#14 captured this plus a list of other likely-missing standard CORE words to audit.

The review on 2026-06-02 (`/home/will/tmp/zforth-missing-standard-words-review.html`) confirmed the gap
against the current source and concluded:
- **Add** the load-bearing + cheap-completeness words (tiers 1+2) — ~15 one-line defs, no engine-API
  change, negligible dictionary cost (`ZF_DICT_SIZE = 65536`, `zfconf.h:37`).
- **`mod`**: `zf_cell` is `float` (`zfconf.h:24`), so `/` is floating-point division and the usual
  `: mod over over / * - ;` is wrong (no integer truncation). The review first recommended omitting it,
  then a syscall was floated — but implementation turned up that **zForth already has a native integer
  `mod` primitive, exposed under the name `%`** (`zforth.c` `PRIM_MOD` → `prim_names` `"%"`, doing
  `(int)a % (int)b` with a divide-by-zero abort). It was only ever "missing" because of the rename, like
  `&`=and / `|`=or / `<0`=0<. So `mod` is just a one-line alias `: mod % ;` — no engine C, no syscall.

This plan implements the additions and squares away the TODO follow-ups the user asked for.

## Scope

Active repo only: **`/home/will/WorldFoundry.2026-new-level`** (origin `wbniv/WorldFoundry`). Sibling
working copies (`WorldFoundry`, `WorldFoundry.party-games-platform`, `WorldFoundry.2026-ios`) each have
their own `scripting_zforth.cc` but pick this up through normal git sync — not edited here.

## Changes

### 1 · Append tier 1+2 words to `kCoreBootstrap`

File: `engine/stubs/scripting_zforth.cc`, immediately after the `loop` definition (currently line 268,
just before the closing `;` of the string literal at line 269). Same adjacent-string-literal style as
the surrounding lines. **Order matters** — later defs reuse earlier ones, and all rely on words already
defined above (`over`, `<`, `>`, `if`, `then`, `=`, `<0`, `@`, `!`, `rot`, `>r`, `r>`).

```c
    // --- Standard ANS CORE words (tiers 1+2 + mod) ---
    ": 0=     0 = ; "
    ": 0<     <0 ; "
    ": 0>     0 > ; "
    ": negate 0 swap - ; "
    ": abs    dup 0< if negate then ; "
    ": min    over over > if swap then drop ; "
    ": max    over over < if swap then drop ; "
    ": ?dup   dup if dup then ; "
    ": nip    swap drop ; "
    ": tuck   swap over ; "
    ": -rot   rot rot ; "
    ": 2dup   over over ; "
    ": 2drop  drop drop ; "
    ": 2swap  >r -rot r> -rot ; "
    ": +!     dup @ rot + swap ! ; "
    ": mod    % ; "                 // alias to native % primitive (integer remainder)
```

Notes:
- `rot` is **not** added — it is already a zForth built-in primitive (the TODO list included it, but it
  is present). `<0` is the primitive zForth uses for "n<0"; `0<` is its ANS-named alias.
- Each def's stack effect was hand-traced (see review page); e.g. `2swap`: `a b c d → >r(d) -rot(c a b)
  r>(c a b d) -rot → c d a b`.

### 2 · `mod` (alias to the native `%` primitive)

Included in the bootstrap block above as `: mod % ;`. zForth's VM already implements integer mod
(`zforth.c` `PRIM_MOD`, `(int)a % (int)b`, aborts `ZF_ABORT_DIVISION_BY_ZERO` on divisor 0) and the
bootstrap registers it under the name `%` (`prim_names`: `- * / %`). So no engine C and no syscall id —
the alias just gives it its standard name. Verified: `7 3 mod`→1, `17 5 mod`→2, `10 5 mod`→0,
`7 0 mod`→clean div-by-zero abort. (An earlier draft of this plan added a `133 sys` syscall for `mod`;
that was removed once the `%` primitive was found.)

### 3 · Fix the stale dictionary-size note (TODO #12)

File: `TODO.md`, line 12. `ZF_DICT_SIZE` is `65536` (`engine/stubs/zfconf.h:37`), not 32 KB.
Change `(32 KB in \`zfconf.h\`)` → `(64 KB in \`zfconf.h\`)`.

### 4 · Update TODO #14 + the `mod` entry

File: `TODO.md`, item #14. Mark the tier 1+2 additions and `mod` as done. Rewrite #14 to:
- Note that `0=` plus tiers 1+2 (`0<`, `0>`, `negate`, `abs`, `min`, `max`, `?dup`, `nip`, `tuck`,
  `-rot`, `2dup`, `2drop`, `2swap`, `+!`) are now in `kCoreBootstrap`; `rot` was already a primitive.
- Note **`mod`** is now defined as `: mod % ;` — an alias to zForth's native `%` (integer-mod)
  primitive; it was never actually missing, just renamed (like `&`/`|`/`<0`).
- Add a **Phase 2** bullet pointing to the split-out parked plan (see §5).

### 5 · (Split out, PARKED) Adopt the new words in existing scripts

Moved to its own deferred plan —
[`docs/plans/deferred/2026-06-02-adopt-new-forth-words-in-existing-scripts.md`](deferred/2026-06-02-adopt-new-forth-words-in-existing-scripts.md).
Pure readability cleanup of existing scripts (collapse `over over`→`2dup`, `swap drop`→`nip`,
boundary-aware `0 =`→`0=`, etc.), gated on re-export + per-level gameplay verification. Not blocking
Phase 1; parked until there's reason to touch those levels.

## Verification

**Status: DONE 2026-06-02.** Verified with a standalone harness, not a new committed test — the bootstrap
has no existing unit harness (`neural_forth_test.cc` only mentions `kCoreBootstrap` in comments and uses
its own minimal bootstrap), and adding one was out of scope.

1. **Bootstrap evals clean (definitive).** `Init()` runs `zf_eval(&g_ctx, kCoreBootstrap)` as one
   all-or-nothing pass and logs `zforth: core bootstrap failed: N` on any error (`scripting_zforth.cc`).
   The harness evaled the real bootstrap string and `zf_eval` returned **`ZF_OK`** → all 16 new defs
   compile. (Equivalent in-engine check: launch on any level, confirm no `core bootstrap failed` on
   stderr.)

2. **Functional check (every word) — ALL PASS.** `/tmp/wf_zforth_verify.c` compiled the vendored
   `engine/vendor/zforth-41db72d1/src/zforth/zforth.c` against the **production** `engine/stubs/zfconf.h`
   (float cells, 64 KB dict), evaled the actual bootstrap, and asserted each word via `zf_pop`:
   - `3 5 min`→3, `5 3 max`→5, `7 abs`→7, `0 7 - abs`→7, `5 negate`→-5
   - `0 0=`→-1, `4 0=`→0, `3 0<`→0, `5 negate 0<`→-1, `3 0>`→-1  *(zForth true = -1, like std Forth)*
   - `9 ?dup`→`9 9`, `0 ?dup`→`0`, `8 4 nip`→4, `8 4 tuck`→`4 8 4`, `1 2 3 -rot`→`3 1 2`
   - `7 8 2dup`→`7 8 7 8`, `7 8 2drop`→(empty), `1 2 3 4 2swap`→`3 4 1 2`, `5 100 ! 3 100 +! 100 @`→8
   - `7 3 mod`→1, `17 5 mod`→2, `10 5 mod`→0; `7 0 mod`→clean `ZF_ABORT_DIVISION_BY_ZERO`

3. **Optional end-to-end.** Build the engine and run any level once to confirm `Init` is clean in the
   real binary. The standalone harness already exercises the identical bootstrap + config, so this is
   confirmatory, not required.
