# Plan — Repair `.ht` C++ header codegen

**Date:** 2026-05-20
**Status:** **Done 2026-05-20.**

---

## Context

Per-actor C++ struct headers (`wfsource/source/oas/<stem>.ht`) are consumed directly by the engine (`target.cc` does `#include <oas/target.ht>`). They are generated from `<stem>.oas` + the `oadtypes.s` template via the `prep` macro tool. Regenerating any `.ht` today produces invalid C — `struct _"Target" {`, `int32 "Mesh Name";` — quoted, spaced identifiers that won't compile.

The root cause was found via git archaeology (not template bugs or a new prep quirk): the historical `wfsource/source/oas/GNUmakefile` (deleted in `61761e4` "slash & burn") generated headers in **two stages**:

```make
%.ht : %.oas
	$(PREP) -DTYPEFILE_OAS=$(*F) oadtypes.s $(*F).pp   # prep -> raw .pp
	perl cstruct.pl $(*F).pp >$@                        # cstruct.pl -> clean .ht
```

`oadtypes.s` deliberately wraps names in quotes (`"@+name@+"`) — its sibling templates `types3ds.s` and `xml.s` each define their own copies of these macros and **need** the quoted display strings for OAD property-sheet descriptors / XSD types. The template is correct and untouched. The canonicalization filter (`cstruct.pl`, also deleted in `61761e4`) was the lost stage. Because this codegen path was never scripted or tested, it rotted silently.

`cstruct.pl` (recovered from `a2784f6`): per line — skip blanks, strip trailing whitespace, `split` on `"`, strip non-`[A-Za-z0-9_]` from inside-quote fields (so `"Mesh Name"` → `MeshName`), rejoin without the quotes. The 119-line raw `.pp` becomes the 21-line clean `.ht`.

**Validation:** awk re-implementation reproduces all 34 committed `.ht` byte-for-byte from the committed `.pp`; full pipeline `prep | awk` also produces all 34 byte-for-byte (including `gold.ht`, matching the hand-authored stopgap); `objects.{c,e,h}` reproduce byte-for-byte via plain `prep`.

---

## Decisions

| Decision | Choice | Reason |
|---|---|---|
| Canonicalizer language | awk (inline in regen script) | User declined perl dep; awk is POSIX/always-present, near-verbatim port of `cstruct.pl`, zero new dependency |
| Template changes | None — `oadtypes.s` untouched | `.s` template was never wrong; fix the process, not the template |
| `.ht` in VCS | Stay committed artifacts | Matches the proven `.oad` model (commit goldens, guard with oracle test); avoids `prep`+`awk` as hard engine build deps |
| `.pp` committed intermediates | Remove (separate commit) | Throwaway intermediates that have drifted (`common`/`gold`); canonicalizer's blank-line stripping makes `.ht` robust to the drift, but stale intermediates in VCS are confusing |

---

## What shipped

1. **`wfsource/source/oas/regen-headers.sh`** — restored two-stage pipeline as a self-contained bash script: builds `prep` if absent (via `wftools/prep/build.sh`), runs `prep -dTYPEFILE_OAS=<stem> oadtypes.s` → scratch `.pp`, then awk canonicalizer → `<stem>.ht` for each committed `.ht` stem; plain `prep` for `objects.{c,e,h}`. Usage: `regen-headers.sh [OUTDIR]` (default = oas dir, in-place).

2. **`Taskfile.yml` targets** — `gen-oas-headers` (run `regen-headers.sh` in place) and `test-codegen` (`cargo test` in `wftools/oas2oad-rs/`). Developer flow: edit `.oas` → `task gen-oas-headers` → `task test-codegen` → commit.

3. **`wftools/oas2oad-rs/tests/ht_codegen.rs`** — oracle test mirroring `oas_to_oad.rs`; runs `regen-headers.sh` into a temp dir and asserts byte-identity for all 34 `.ht` + `objects.{c,e,h}`. Drives the real process; self-builds `prep` on first run; needs only `bash`/`awk`/`g++`/`cargo`.

4. **Remove `wfsource/source/oas/*.pp`** (33 files) — stale intermediates cleaned up.

---

## Files changed

- `docs/plans/2026-05-20-ht-codegen-repair.md` (this file)
- `wf-status.md` (new row)
- `wfsource/source/oas/regen-headers.sh` (new)
- `Taskfile.yml` (two new tasks)
- `wftools/oas2oad-rs/tests/ht_codegen.rs` (new)
- `wfsource/source/oas/*.pp` (33 removed)
