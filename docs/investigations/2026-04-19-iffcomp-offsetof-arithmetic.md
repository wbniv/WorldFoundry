# `.offsetof` arithmetic in iffcomp — oracle vs current behavior

**Date:** 2026-04-19
**Context:** Reconstructing `wflevels/snowgoons.iff.txt` as a proper
compile-source text-IFF file (mirror-first, deviate-later), chunk-by-chunk, so
iffcomp-rs can produce byte-identical output versus the oracle
`wflevels/snowgoons.iff`. Progress reached the LVAS `TOC` chunk, where the
question of **what `.offsetof` is supposed to return** stopped being academic.

---

## The trigger question

When we got to the LVAS TOC, the initial candidate expression was

```
'ASMP' .offsetof(::'LVAS'::'ASMP', -2048) .sizeof(::'LVAS'::'ASMP')
```

— with a `-2048` addend to back out the `.align(2048)` between the LVAS
header and the ASMP chunk. KTS flagged the `-2048` as almost certainly wrong:
*"is the second parameter in the original iffcomp? the -2048 (which i'm sure is
wrong and you don't need, btw)"*.

This was the right instinct. The oracle TOC stores offsets **relative to the
containing LVAS chunk's header start**, not absolute file offsets — so the
correct expression is not `offsetof(ASMP) + constant`, it's `offsetof(ASMP)
- offsetof(LVAS)`. Which means you need real **subtraction between two
`.offsetof` calls**.

## What the oracle actually contains

`iffdump` on `snowgoons.iff` at the TOC chunk (payload starts at file offset
`0x1010`, size 72 bytes = 6 × 12):

```
  file off.    bytes          fourcc  offset      size
  0x1010   41 53 4D 50 …     'ASMP'  0x00000800  0x0000007c
  0x101c   4C 56 4C 00 …     'LVL'   0x00001000  0x000021b4
  0x1028   50 45 52 4D …     'PERM'  0x00003800  0x00007334
  0x1034   52 4D 30 00 …     'RM0'   0x0000b000  0x000010f0
  0x1040   52 4D 31 00 …     'RM1'   0x0000c800  0x0001b59c
  0x104c   46 41 4B 45 …     'FAKE'  0x00001000  0x0000007c
```

Two load-bearing observations:

1. **Offsets are LVAS-header-relative.** LVAS header is at file offset
   `0x1000`. ASMP's header is at `0x1800` — the TOC stores `0x800`. So the
   TOC emits `absolute(ASMP) - absolute(LVAS)`.
2. **Exactly 72 bytes, not more.** Six entries × (FOURCC + int32 + int32) =
   72 bytes. No extra int32s hanging around.

The second observation is the one that settled the whole argument.

## The argument: does iffcomp really do arithmetic?

Reading the **current** C++ grammar at `wftools/iffcomp/lang.y`, the item
reductions each *emit bytes into the output stream*:

```yacc
item : INTEGER
         { g._iff->out_int32($1.val); $ = $1.val; }
     | OFFSETOF LPAREN chunkSpecifier RPAREN
         { /* emits int32, either immediate or via backpatch */ $ = 0; }
     | SIZEOF   LPAREN chunkSpecifier RPAREN
         { /* emits int32 */                                $ = 0; }
     ;

expr : item
     | expr PLUS  expr { $ = $1 + $3; }
     | expr MINUS expr { $ = $1 - $3; }
     ;
```

So `.offsetof(A) - .offsetof(B)` in the current C++ grammar means:

1. Reduce `.offsetof(A)` as an item → **emit 4 bytes** for A's offset.
2. See `-`, reduce `.offsetof(B)` as an item → **emit another 4 bytes** for
   B's offset.
3. `expr MINUS expr` fires, computing `0 - 0 = 0` in `$` — a value that
   **nobody reads**. The arithmetic on `$` is dead code; the actual byte
   stream already has both offsets emitted separately.

Under this grammar, the TOC of a level with six entries would be **6 × 12 +
extra-int32-per-arithmetic-expression bytes**, not 72. That does not match
the oracle.

**Conclusion:** the oracle was not produced by this grammar. Either:

- **(A)** The original iffcomp had real arithmetic (item reductions *built a
  value*, the `expr` rules composed values, and `expr` emission happened once
  at the end); an intervening modernization pass rewrote the grammar into its
  current "emit at item time" shape without exercising the TOC case, because
  no test currently covers `.offsetof - .offsetof`.
- **(B)** The original iffcomp had the bug too, but the iff.prp used a
  different formula — hardcoded hex, or a single `.offsetof` with a constant
  addend. But that's not what the iff.prp says (`.offsetof(A) - .offsetof(B)`
  pattern is common in the stored `.iff.txt` reference outputs), and there's
  no way a single `.offsetof` call emits `0x800`, since every `.offsetof` in
  either resolution path (`pos - 4` or `pos - 8`) resolves to an absolute
  file offset, not a relative one.

(A) is overwhelmingly more likely: the current C++ grammar is a regression
that shipped after the oracle and was never exercised against a level that
actually uses TOC arithmetic.

KTS's read: *"you can't reproduce the original iffcomp anyway, it's been
hacked since the original and never fully re-validated."*

## Implication for iffcomp-rs

iffcomp-rs must reproduce **what the oracle produced**, not what the current
C++ grammar produces. That means:

- `parse_item` for `Integer` / `.offsetof` / `.sizeof` must not emit eagerly.
  It should build a term that carries a value or a symbolic reference.
- `parse_expr` must combine terms with `+` / `-` into a single expression.
- The writer must emit the expression as **one int32** (sum of resolved
  terms), falling back to a compound deferred backpatch when any term refers
  to a not-yet-closed chunk.

All three offsetof numbers in a deferred-compound resolution happen to give
the same answer for the *difference* of two offsetofs:

```
diff = (posA - k) - (posB - k) = posA - posB    (k cancels)
```

— so the exact "immediate vs. deferred" 4-byte quirk in the standalone
`.offsetof` path does not matter for arithmetic contexts. Any consistent
reference point works; we use `pos - 8` (= chunk header start) for compound
terms for semantic clarity.

## Implication for the C++ iffcomp

The current grammar is broken in the same way for any level that uses
`.offsetof` arithmetic in its TOC. If we ever rebuild `snowgoons.iff` from
its sources through the C++ path, we'd get a file with bloated TOC and wrong
offsets in the chunk stream that follows.

**Action:** after iffcomp-rs arithmetic lands and is verified byte-identical
against the oracle, port the fix back to `wftools/iffcomp/lang.y`:

- `item` reductions for `INTEGER` / `OFFSETOF` / `SIZEOF` build a `Term`
  instead of calling `out_intN`.
- `expr` reductions combine terms in `$`.
- Add an explicit `expr_emit` point at the top-level `items` rule where the
  accumulated expression is emitted once.

The old "emit at item time" behavior is safe to drop — there is no
test-covered case where a bare item should emit without first passing
through `expr`.

## Entry 5: the `FAKE` oddity

Unrelated to the arithmetic issue, entry 5 in the oracle TOC caught our eye:

```
entry 5:  'FAKE'   offset 0x1000   size 0x007c
```

- Offset `0x1000` matches entry 1 (`LVL`), **not** ASMP.
- Size `0x007c` matches entry 0 (`ASMP`), **not** LVL.

Cross-wired. iff.prp's current template roughly says
`'FAKE' .offsetof(::'LVAS'::'ASMP') .sizeof(::'LVAS'::'ASMP')`, but the
oracle bytes disagree: ASMP is at LVAS-relative `0x800`, not `0x1000`.

Most likely reading: **iff.prp's FAKE template in the repo is stale**; the
formula that produced oracle bytes was different (plausibly
`.offsetof(::'LVAS'::'LVL') .sizeof(::'LVAS'::'ASMP')` — literal
cross-wiring, deliberately chosen as a sentinel the engine can
tombstone-check). FAKE entries aren't loaded as real data, so the specific
values don't matter as long as they're distinguishable.

Action: deferred. Once iffcomp-rs can emit the other five entries
byte-identically, we'll pick FAKE's formula by working backwards from the
oracle bytes and trust the oracle over the template.

## Side investigation: `ASS` and iffdump recursion

While digging into the dump, we tried adding `ASS` to iffdump's wrapper list
(so PERM/RM0/RM1 asset slots would recurse into their inner texture /
palette / mesh sub-chunks). It didn't work — `ASS` turned out to be a data
chunk, not a container: its payload is packed vertex / texture / palette
bytes, not sub-chunks. Reverted.

Final default wrapper list (matches `wftools/iffdump/chunks.txt` plus the
`L4`–`L9` level containers):

```
GAME
L0 L1 L2 L3 L4 L5 L6 L7 L8 L9
LVAS
PERM RM0 RM1 RM2 RM3 RM4
OADL TYPE UDM IFFC
```

PERM and RM0/RM1 recurse into their `ASS` children (visible as chunk
headers), and each `ASS` is a hex-dumped leaf — which matches what the
oracle `chunks.txt` does.

## Summary

- **Oracle bytes prove the original iffcomp did real arithmetic.** 72-byte
  TOC, 6 × 12, no extras.
- **Current C++ grammar has regressed** — it emits bytes at item-reduction
  time, discarding arithmetic on the `$` value. No existing test catches it
  because no current `test.iff.txt` exercises `.offsetof - .offsetof`.
- **iffcomp-rs gained proper arithmetic** — parser builds a Term/Expr,
  writer emits one int32 (resolved now or via compound backpatch).
  `all_features.iff.txt`'s `5l + 3l - 2l` test case and its pinned oracle
  were updated to match the corrected semantics (`6` as one int32, not
  three separate values).
- **FAKE entry** has iff.prp-template drift; source-of-truth is the oracle,
  not the template.
- **ASS is not a wrapper.** Confirmed by attempting to recurse.

## Postscript: the design intent behind the 2nd parameter

KTS pointed out that `.offsetof` has an integer-addend 2nd parameter **for
a reason** — it was the workaround for top-level `+`/`-` never working
correctly. The addend lets you express things like "X's offset relative to
Y" as `.offsetof(X, -Y_position)` without composing two expression items
via broken binary operators.

But — and this is the key insight — the workaround only has real teeth if
the 2nd argument can itself be a *symbolic* expression (another `.offsetof`
call, or a subtraction thereof). If it's restricted to a literal integer,
it's only useful when the target chunk sits at a known fixed offset — which
is the case for this particular level format (LVAS always at `0x1000`) but
doesn't generalize.

So the modernized grammar restricting the 2nd parameter to `INTEGER` broke
both halves of the language's offset-math story:

1. Top-level arithmetic emits bytes at item-reduction time, discarding the
   composition.
2. The designated workaround (`.offsetof(X, <expr>)`) lost its expression
   argument, reducing it to "hardcode a constant".

To restore the original shape you need **at least one** of:

- Fix top-level `+`/`-` composition. (This is the approach taken in the
  iffcomp-rs arithmetic implementation above.)
- Re-admit expressions to the 2nd parameter of `.offsetof`. (Also
  implemented in iffcomp-rs — the int-addend form is preserved as a
  fast-path when the 2nd token after the comma is `INTEGER RPAREN`.)

Both routes end up in the same `emit_expr` compound-backpatch machinery in
the writer.

### The syntactic snag: `-.offsetof` doesn't lex

The obvious expression form for the 2nd parameter is
`.offsetof(X, -.offsetof(Y))`, but iffcomp's lexer eats `-.` as the prefix
of a real-number literal (`-0.5`, `-.25`, etc.) — so `-.offsetof` fails to
tokenize. Fixing that cleanly would mean either:

- Disambiguating `-.` based on what follows the dot (not great — the lexer
  currently doesn't have that kind of context), or
- Requiring whitespace: `.offsetof(X, - .offsetof(Y))`. Works, but looks
  odd.

The path of least surprise turned out to be the top-level arithmetic form
we already wanted working anyway:

```
{ 'TOC'
    'ASMP' .offsetof(::'L4'::'LVAS'::'ASMP') - .offsetof(::'L4'::'LVAS') .sizeof(::'L4'::'LVAS'::'ASMP')
    'LVL'  .offsetof(::'L4'::'LVAS'::'LVL')  - .offsetof(::'L4'::'LVAS') .sizeof(::'L4'::'LVAS'::'LVL')
    'PERM' .offsetof(::'L4'::'LVAS'::'PERM') - .offsetof(::'L4'::'LVAS') .sizeof(::'L4'::'LVAS'::'PERM')
    'RM0'  .offsetof(::'L4'::'LVAS'::'RM0')  - .offsetof(::'L4'::'LVAS') .sizeof(::'L4'::'LVAS'::'RM0')
    'RM1'  .offsetof(::'L4'::'LVAS'::'RM1')  - .offsetof(::'L4'::'LVAS') .sizeof(::'L4'::'LVAS'::'RM1')
    'FAKE' .offsetof(::'L4'::'LVAS'::'LVL')  - .offsetof(::'L4'::'LVAS') .sizeof(::'L4'::'LVAS'::'ASMP')
}
```

Verified byte-identical to the oracle for all six entries. This is what
`wflevels/snowgoons.iff.txt` uses today.

(My earlier proposal of `-2048` as a bare-int addend was wrong for a
different reason — `-2048 = -0x800` is the first ALGN-boundary position,
not LVAS's position. `-4096 = -0x1000` is LVAS. That bare-int form also
compiles byte-identically, but only because LVAS's position happens to be
fixed by the L4 container format.)

### Does C++ iffcomp accept the 2nd-arg expression form today?

No. `wftools/iffcomp/lang.y:300` hard-codes `INTEGER`:
```
| OFFSETOF LPAREN chunkSpecifier T_COMMA INTEGER RPAREN
```
So `.offsetof(X, -.offsetof(Y))` is rejected by the C++ grammar as it
stands. The fix mirrors what iffcomp-rs now does: change that `INTEGER` to
`expr` (or a dedicated addend-expr production that skirts the `-.` lex
snag), and have the `Backpatch` type carry a compound term list instead of
a single integer addend.

---

**Status:** iffcomp-rs arithmetic + 2nd-arg-expression both implemented
and tested (task #12). Oracle TOC reproduced byte-identically using the
top-level `-` arithmetic form (task #13). C++ iffcomp port still open
(task #14) — now a two-sided fix: top-level `+`/`-` composition AND
2nd-param expression acceptance.

## Postscript 2: the `.relative_to` theory

KTS floated an alternative: what if the original DSL had a state-push form
that scoped offset resolution to a base chunk? Something like

```
{ .relative_to(::'L4'::'LVAS')
    'ASMP' .offsetof(::'L4'::'LVAS'::'ASMP') .sizeof(::'L4'::'LVAS'::'ASMP')
    ...
}
```

where every `.offsetof(X)` inside the block would implicitly subtract the
base chunk's position. Clean, readable, no arithmetic required.

**Audited C++ iffcomp for anything like this.** No evidence:

- **Lexer** (`wftools/iffcomp/lang.l`) — the complete list of `.`-directives
  is `.timestamp` `.align` `.offsetof` `.sizeof` `.fillchar` `.start`
  `.length` `.precision`. No `.relative_to`, `.base`, `.scope`, or similar.
- **Parser** (`wftools/iffcomp/lang.y:200`) — `state_push` only has two
  shapes: `{ precision_specifier ... }` and `{ size_specifier ... }`
  (Y/W/L). No third form.
- **Writer** (`wftools/iffcomp/grammar.cc:126`) — backpatch resolution is
  literally `cs->GetPos() - 4 + bp->_offset`. Single absolute position,
  single integer addend. No per-scope base-offset state.

So the `.relative_to` form doesn't exist in any C++ artifact we can see. It
*could* be cleanly added (the writer already has the symbol lookup; all it
needs is a "current base" on the state stack and a subtraction at emit
time), but the oracle wasn't produced by it — because it doesn't exist.

## The real mystery

Putting it all together, we've established:

- The oracle TOC is 72 bytes. ✓
- The bytes are LVAS-header-relative. ✓
- The C++ grammar as it exists today can't produce those bytes via
  `.offsetof - .offsetof` (top-level `+`/`-` discarded), nor via
  `.offsetof(X, -.offsetof(Y))` (2nd param is `INTEGER`), nor via
  `.relative_to(...)` (doesn't exist).

So one of these must be true:

1. The original C++ grammar had either (a) working top-level arithmetic,
   (b) expression-accepting 2nd-parameter `.offsetof`, or (c) a
   `.relative_to` form — and all of them got lost in a modernization pass
   no commit records.
2. The original iff.prp used hardcoded hex literals for the TOC values (or
   a level-specific constant addend like `-0x1000`) and someone has since
   rewritten it with the symbolic forms we see today, hoping they'd work.
3. There was a post-processing tool that filled in the TOC values after
   compile.

No evidence left to disambiguate. **We pick (1) implicitly by making
iffcomp-rs support both (a) and (b)** — it compiles byte-identically, it's
what the syntax *should* have meant, and it doesn't require trusting any
particular theory about what got stripped.

---

**Open questions** (none blocking):

- If anyone ever finds an older iffcomp tarball / archive, compare its
  `lang.y` to the current one to see which of (a)–(c) was the original.
- `.relative_to` as a *new* form would still be a nice ergonomics win —
  even if it wasn't the historical approach, the TOC reads better with
  it than with the `.offsetof - .offsetof` pattern repeated six times.

## Postscript 3: SourceForge CVS resolves the mystery

Fetched `https://sourceforge.net/code-snapshots/cvs/w/wf/wf-gdk.zip` — a
CVS snapshot of the last SourceForge-hosted revision (HEAD = 1.7, dated
2010, marked `state dead` at the point the project moved to GitHub). The
snapshot contains the historical `iffcomp/Attic/lang.y,v` **and** the
original `wfsource/levels.src/Attic/iff.prp,v` that produced the oracle
`.iff` files. Three findings:

**1. The historical grammar has the same "emit at item time" behavior
as the current grammar.** The `expr` rule includes an arithmetic action —

```yacc
expr :
    item                { $$ = $1; }
  | expr PLUS expr      { $$ = $1 + $3; printf( "%ld + %ld = %ld\n", $1, $3, $$ ); }
  | expr MINUS expr
  ;
```

— but the computed `$$` is never emitted anywhere in the output stream.
Item reductions for `INTEGER` / `OFFSETOF` / `SIZEOF` all call
`out_intN` or `out_int32` directly, same as the modernized grammar.
**Binary `+`/`-` has literally never worked to compose an emitted
expression in C++ iffcomp.** It was a no-op (or a `printf` trace for `+`,
empty action for `-`) for the whole life of the tool. Our theory that
the arithmetic regressed is wrong — there was never anything to regress.

**2. The 2nd parameter of `.offsetof` has always been `INTEGER`.** Same
grammar rule, same binding to `$5.val` as an `unsigned long`, same
behavior. No expression-accepting historical form ever existed.

**3. The historical `iff.prp` template uses `.offsetof(X, -2048)`.**
Extracted verbatim:

```
{ 'LVAS'
    { 'TOC'
        'ASMP'  .offsetof( ::'LVAS'::'ASMP', -2048 )  .sizeof( ::'LVAS'::'ASMP' )
        'LVL'   .offsetof( ::'LVAS'::'LVL',  -2048 )  .sizeof( ::'LVAS'::'LVL' )
        …
        'FAKE'  .offsetof( ::'LVAS'::'ASMP' )         .sizeof( ::'LVAS'::'ASMP' )
```

`-2048` wasn't a magic number — it was correct **for the original file
layout**, which had no `L4` wrapper. The iff.prp emitted `RAM` at file
offset 0 (via `include "ram.iff.txt"`), an ALGN pad to 0x800, and LVAS
at 0x800. So `.offsetof(ASMP, -2048)` = `ASMP.pos - 0x800` = ASMP's
LVAS-relative offset. The FAKE entry used unaddended `.offsetof(ASMP)`
deliberately: it stored ASMP's *absolute* file position (0x1000 under
the pre-L4 layout, which coincidentally equals LVL's LVAS-relative
offset — the "cross-wired" look is a layout accident, not a template
bug).

### Why the modern oracle `snowgoons.iff` has L4 wrapping

The oracle we have in the repo today starts with `L4` at file offset 0,
which shifts LVAS from 0x800 to 0x1000. Modernized structure:

```
0x0000  L4 header
0x0008  ALGN pad → 0x0800
0x0800  RAM
0x082C  ALGN pad → 0x1000
0x1000  LVAS ← was at 0x0800 pre-L4-wrap
```

Under the L4-wrapped layout, the historical `.offsetof(X, -2048)` would
produce **wrong** bytes: `0x1800 - 2048 = 0x1000` (= LVL's entry value),
not ASMP's `0x800`. So the oracle in the repo was NOT built by the
historical iff.prp applied to the L4-wrapped layout — it was either:

- Built by the historical iff.prp on the pre-L4 layout, then **wrapped
  in L4 after the fact** (TOC bytes copied through verbatim; LVAS-
  relative offsets remain correct because they're layout-invariant).
- Built by a later iff.prp variant with `-4096` or arithmetic, that
  isn't in the current repo.

The first is more likely given zero evidence of an updated iff.prp.

### What this changes

- **iffcomp-rs arithmetic fix (`+/-`)** — still correct and still
  valuable, but no longer "restoring original behavior". It's a *new*
  feature iffcomp-rs adds that C++ iffcomp never had.
- **iffcomp-rs 2nd-arg expression fix** — same story: a *new* extension,
  not a restoration.
- **The "right" TOC expression for the modern oracle layout** — either
  `.offsetof(X, -4096)` (integer-addend form, one byte nudge from the
  historical `-2048`) or the arithmetic form. Both compile
  byte-identically.

The previous "Status" section's "port the arithmetic fix back to C++
iffcomp" is now **not a regression fix** — it's a forward-looking
improvement. Decision on whether to actually port it can wait.
  Park as a future-nice-to-have.
