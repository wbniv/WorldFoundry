# Agent prompt — repair the `.ht` C++ codegen

(Hand this to another agent. Delete when done.)

---

TASK: Repair the broken `.ht` C++ codegen in WorldFoundry so it regenerates
compilable headers, and make the engine-side OAS codegen reproducible + tested.

REPO: /home/will/WorldFoundry.2026-new-level   (branch 2026-new-level)

## Background

The engine's per-actor C struct headers live at `wfsource/source/oas/<stem>.ht`
(e.g. `target.ht` defines `struct _Target { int32 MeshName; ... };`). They are
consumed directly by the engine (`target.cc` does `#include <oas/target.ht>`) and
are GENERATED from `wfsource/source/oas/<stem>.oas` via the template
`wfsource/source/oas/oadtypes.s` using the `prep` macro tool
(`wftools/prep/prep`; built by `wftools/prep/build.sh`; CLI:
`prep {-d<macro>=<val>} <infile> <outfile>`).

## The bug

Regenerating any `.ht` today produces INVALID C. From `wfsource/source/oas`:

    ../../../wftools/prep/prep -dTYPEFILE_OAS=target oadtypes.s /tmp/target.ht
    diff target.ht /tmp/target.ht

yields `struct _"Target" {` and `int32 "Mesh Name";` — i.e. the display names
come out QUOTED and SPACED (invalid identifiers). The committed `target.ht` has
clean identifiers `_Target` / `MeshName`. So a name-canonicalization step
(strip the literal quotes; remove interior spaces so `"Mesh Name"` -> `MeshName`)
that once produced the clean committed `.ht` files has been LOST.

The clean committed `.ht` files date to commit `fe0ffbd` ("claude-identified
fixes", 2026-04-14). `oadtypes.s` itself is unchanged since 2010 (commit
`a2784f6`). In `oadtypes.s` the macros literally wrap names in quotes, e.g.

    @define TYPEHEADER(displayName,variableName=displayName) ... struct _"@+variableName@+" {
    @define TYPEENTRYFILENAME(...) int32 "@+name@+"; /* ... */

The `@+` operator only eats whitespace at the boundary, not the quotes or the
interior space in `"Mesh Name"`. Note the STRUCT name uses `variableName`
(already a clean token like `Target`/`Gold`) so it only needs the quotes
removed; FIELD names use `name` (a display string that may contain spaces) so
they need quotes removed AND interior spaces stripped. Confirm the exact rule
against `actor.inc`.

## Goal (oracle-first; root-cause not symptom)

1. Make the `.ht` codegen reproduce EVERY committed `wfsource/source/oas/*.ht`
   byte-for-byte (modulo trailing blank lines if truly unavoidable — prefer
   exact). The fix most likely lives in `oadtypes.s` (drop the literal quotes;
   strip interior spaces from field names — `prep` has
   `@replace(regex)(repl)(body)` using Henry Spencer regex, plus `@+`/`@-`/`@n`).
   A post-process script is acceptable ONLY if the in-template fix proves
   infeasible; document why. Decide whether the quotes are simply wrong here vs.
   needed by sibling templates `types3ds.s` / `xml.s` (`oadtypes.s` warns
   "update types3ds.s as well") — do not break those.
2. Confirm `objects.{c,e,h}` regenerate byte-identical from `objects.{s,es,hs}`
   (they currently DO: `prep objects.s objects.c` etc. run from the oas dir).
3. Produce a single reproducible regen entrypoint for the engine-side OAS C++
   codegen (a script under `wfsource/source/oas/` or a Taskfile target) covering
   `objects.{c,e,h}` + all `<stem>.ht`. Today only the `.oad` path is scripted
   (`wftools/oas2oad-rs`); the `.ht`/objects path is NOT — that gap is the root
   reason this broke silently.
4. Add an oracle test (mirror `wftools/oas2oad-rs/tests/oas_to_oad.rs`):
   regenerate all `.ht` + `objects.{c,e,h}` and assert byte-identity vs the
   committed files, so this can't silently rot again.

## Context you'll want

- prep feature reference + rebuild story:
  `docs/investigations/2026-05-19-prep-rebuild-or-replace.md`
- prep source: `wftools/prep/` (`source.cc` has the in-source command reference)
- Existing `.oad` oracle test (the pattern to copy):
  `wftools/oas2oad-rs/tests/oas_to_oad.rs`
- prep was just rebuilt self-contained (commit `fa61e96`); binary is gitignored,
  build it with `wftools/prep/build.sh` if absent.

## Conventions (project)

- Plans before implementation: write
  `docs/plans/2026-05-20-ht-codegen-repair.md` first (Status line), get it
  acknowledged, then implement. Keep the plan doc Status and the `wf-status.md`
  row in sync.
- Commit per logical step; do NOT sweep unrelated working-tree edits into your
  commits (the tree has other in-flight work). End commit messages with the
  project's Co-Authored-By trailer.
- "DO NOT MODIFY" headers must remain generated outputs — fix the GENERATOR,
  not the outputs.

## Cross-dependency

A parallel effort is adding a new actor class `Gold` (`gold.oas` already exists;
`gold.{hp,cc}` + `objects.mac` entry being added now). It hand-authors `gold.ht`
as a STOPGAP (= `target.ht` renamed Target->Gold) because of this bug. Once your
fixed codegen lands, regenerate `gold.ht` through it and confirm it matches the
hand-authored stopgap (it should be identical: `gold.oas` is a minimal actor
that just `@include actor.inc`, same shape as `target.oas`).
