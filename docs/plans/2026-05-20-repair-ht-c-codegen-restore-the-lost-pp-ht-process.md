# Repair `.ht` C++ codegen — restore the lost `.pp → .ht` process stage

**Status:** DONE (commit `268fedb3`) — `regen-headers.sh` restores the prep→.pp→awk pipeline; oracle test added (`task test-codegen`).

## Context

The engine includes per-actor C struct headers `wfsource/source/oas/<stem>.ht`
(e.g. `target.cc` does `#include <oas/target.ht>`). They are generated from
`<stem>.oas` via the `prep` macro tool and the `oadtypes.s` template.

Regenerating any `.ht` today emits **invalid C** — `struct _"Target" {` and
`int32 "Mesh Name";` — i.e. quoted, space-bearing identifiers. The committed
`.ht` files have clean identifiers (`_Target`, `MeshName`). A
name-canonicalization step that once produced the clean files was lost, and
because the `.ht`/objects codegen was never scripted or tested, it rotted
silently (the only scripted codegen today is the `.oad` path in `oas2oad-rs`).

### Root cause (found via git archaeology — *the `.s` templates are NOT wrong*)

The historical `wfsource/source/oas/GNUmakefile` (deleted in `61761e4`
"slash & burn") generated each header in **two stages**:

```make
%.ht : %.oas
	$(PREP) -DTYPEFILE_OAS=$(*F) oadtypes.s $(*F).pp   # raw output -> .pp
	perl cstruct.pl $(*F).pp >$@                        # canonicalize -> .ht
```

`oadtypes.s` *deliberately* wraps names in quotes (`"@+name@+"`) — its siblings
`types3ds.s` (OAD descriptors) and `xml.s` (XSD types) define their **own** copies
of these macros and **need** the quoted, spaced display strings; neither includes
`oadtypes.s`, so the templates are correct and must not change. The C-header path
relied on a final filter, **`cstruct.pl`** (also deleted in `61761e4`), to turn the
raw `prep` output (`.pp`) into the clean `.ht`. That stage is what was lost.

`cstruct.pl` (recovered from commit `a2784f6`) does, per line: skip blanks, strip
trailing whitespace, `split` on `"`, strip every non-`[A-Za-z0-9_]` char from the
inside-quote fields, and rejoin **without** the quotes. So `"Mesh Name"` →
`MeshName`, `_"Target"` → `_Target`; comments/keywords (outside quotes) are
untouched; the ~119-line `.pp` collapses to the ~21-line `.ht`.

### Validation already performed (read-only, into `/tmp`)

- awk re-implementation of `cstruct.pl` reproduces **all 34** committed `.ht`
  byte-for-byte from the committed `.pp`.
- Full pipeline `prep(oadtypes.s) | awk` reproduces **all 34** `.ht`
  byte-for-byte (incl. `gold.ht`, which equals the hand-authored stopgap).
- Plain `prep` reproduces `objects.{c,e,h}` byte-for-byte.
- No `.pp` line is literally `0` (the one perl-truthiness gotcha) — non-issue.
- `common.pp`/`gold.pp` differ from committed by blank-line/whitespace only,
  which the canonicalizer strips — so `.ht` is unaffected. Confirms `.pp` are
  throwaway intermediates that shouldn't be tracked.

## Decision

Restore the **process**, not the template. Re-implement `cstruct.pl` as **awk**
(user's choice — no perl dependency) inlined in a self-contained regen script.
Do **not** edit `oadtypes.s`, `types3ds.s`, `xml.s`, or any `.oas`/`.inc` source.

## Changes

### 1. `wfsource/source/oas/regen-headers.sh` (new) — the restored pipeline
- `set -euo pipefail`. Replaces the deleted `GNUmakefile` `.ht`/objects rules
  (same spirit as `wftools/prep/build.sh` replacing the old make-tool system).
- Usage: `regen-headers.sh [OUTDIR]` (default `OUTDIR` = the oas dir, so devs
  can regenerate in place; the test passes a temp dir).
- Ensures `prep` exists, building it via `wftools/prep/build.sh` if absent
  (mirrors `oas_to_oad.rs::ensure_prep`).
- `cd`s to the oas dir so `prep`'s relative `@include`s resolve
  (`oadtypes.s`→`types.h`/`<stem>.oas`; `objects.s`→`objects.mac`).
- For each `*.ht` stem: `prep -dTYPEFILE_OAS=<stem> oadtypes.s <tmp>.pp`, then the
  awk canonicalizer `<tmp>.pp` → `OUTDIR/<stem>.ht`. `.pp` goes to a scratch
  temp, not the tree.
- Regenerates `objects.c|e|h` via plain `prep objects.{s,es,hs}` → `OUTDIR`.
- A header comment credits `cstruct.pl` (commit `a2784f6`) as the awk's origin.

Canonicalizer (faithful awk port, validated byte-identical):
```awk
{ sub(/[ \t\r]*$/,"") }            # strip trailing whitespace
length($0) {                        # skip blank lines
  n=split($0,f,"\"")
  for(i=2;i<=n;i+=2) gsub(/[^A-Za-z0-9_]/,"",f[i])   # inside-quote -> bare identifier
  s=""; for(i=1;i<=n;i++) s=s f[i]                    # rejoin, quotes dropped
  print s
}
```

### 2. `wftools/oas2oad-rs/tests/ht_codegen.rs` (new) — oracle test
- Mirrors `tests/oas_to_oad.rs`: locates repo root via `CARGO_MANIFEST_DIR`,
  runs `regen-headers.sh <tempdir>` (the script builds `prep` if missing), then
  byte-compares every committed `wfsource/source/oas/*.ht` and
  `objects.{c,e,h}` against the regenerated copies; collects all mismatches and
  asserts none. (Drives the *real* process; needs only `bash`+`awk`+`g++`, which
  the existing `.oad` test already requires.)
- Helpers (`repo_root`, `oas_dir`) duplicated locally to avoid touching
  `oas_to_oad.rs` (Rust integration tests are separate crates).

### 3. `wf-status.md` + `docs/plans/2026-05-20-ht-codegen-repair.md` (new)
- Write the project plan doc with a `**Status:**` line; keep it in sync with a
  new `wf-status.md` summary row (one-sentence, prepended).

### 4. Build pipeline wiring (how it should be updated)

The engine build stays as-is: `.ht` and `objects.{c,e,h}` remain **committed
generated artifacts** that the C++ build `#include`s directly. This matches the
proven `.oad` model (commit goldens, guard with an oracle test) and avoids making
`prep`+`awk` hard build-time dependencies / a source of nondeterminism. Do **not**
regenerate headers inside the CMake build.

Instead, close the "not scripted, not tested" gap with two Taskfile targets in
`Taskfile.yml` (today it has only `build*` targets; the `.oad`/`.ht` codegen and
`cargo test` are invoked by hand):

- `gen-oas-headers` — runs `wfsource/source/oas/regen-headers.sh` in place. The
  canonical "I edited a `.oas`/`.inc`/`oadtypes.s`, now regenerate the headers"
  command; pairs with `task build`.
- `test-codegen` — `cd wftools/oas2oad-rs && cargo test`. Now covers **both** the
  existing `.oad` oracle **and** the new `.ht`/objects oracle, so a drift between
  committed artifacts and their sources fails fast.

CI: there are currently **no `.github/workflows/`** in this branch, so the honest
wiring is "the oracle test is the guard; run it wherever tests run." `task
test-codegen` is the single entrypoint a future GitHub Actions / Codemagic job (or
a local pre-commit) calls. Adding a CI workflow file is out of scope here (no CI
exists to extend) but the test is written to be CI-ready (self-builds `prep`,
needs only `bash`/`awk`/`g++`/`cargo`).

Developer flow after this lands: edit `.oas`/`oadtypes.s` → `task gen-oas-headers`
→ `task test-codegen` → commit the regenerated `.ht`/objects with the sources.

### 5. Remove stale committed intermediates (recommended, separate commit)
- `git rm wfsource/source/oas/*.pp` (33 files). They are throwaway `prep`
  intermediates (already drifted for `common`/`gold`) that don't belong in VCS;
  the restored pipeline writes them to scratch. Skippable if you'd rather keep
  them.

## Files (reference)
- Generator template (UNCHANGED): `wfsource/source/oas/oadtypes.s`
- Recovered canonicalizer: `cstruct.pl` @ `a2784f6` (re-implemented as awk)
- Pattern to mirror (test): `wftools/oas2oad-rs/tests/oas_to_oad.rs`
- prep build: `wftools/prep/build.sh` (binary gitignored)
- prep feature ref: `docs/investigations/2026-05-19-prep-rebuild-or-replace.md`

## Verification
1. `bash wfsource/source/oas/regen-headers.sh /tmp/oasout` then
   `for f in /tmp/oasout/*.ht objects.{c,e,h}; do cmp "$f" "wfsource/source/oas/$(basename $f)"; done`
   → all identical (already confirmed end-to-end).
2. Run regen in place; `git status wfsource/source/oas/*.ht` shows **no changes**
   (proves the committed `.ht` are exactly what the restored process emits).
3. `cd wftools/oas2oad-rs && cargo test` → both the existing `.oad` oracle and the
   new `ht_codegen` oracle pass.
4. `gold.ht` regen equals committed stopgap (already confirmed: MATCH).

## Commits (only my files; don't sweep the in-flight tree)
1. plan doc + `wf-status.md` row.
2. `regen-headers.sh` + `Taskfile.yml` `gen-oas-headers`/`test-codegen` targets.
3. `ht_codegen.rs` oracle test.
4. (optional) remove `*.pp` intermediates.

End commit messages with: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
