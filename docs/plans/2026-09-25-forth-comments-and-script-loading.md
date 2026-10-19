# Shared Forth comments and safe semicolon scanning

Status: implemented and verified, using the reduced scope agreed with Will. Engine changes are
explicitly authorized for this fix, separate from the Forth-only camera feature.

## Scope

Add backslash line comments to the shared Forth bootstrap, make the existing
last-semicolon scan ignore comments and supported string literals, and remove
the condo camera's local comment stripping. Normal loading and hot reload use
the same small source helper. Preserve the current definitions-then-body contract,
script caching, mailbox interface and camera behavior.

This is a focused compatibility fix, not a new parser or source format.

## Implementation

- [x] Define the immediate backslash comment word once in shared initialization,
  as a small immediate VM primitive alongside parenthesised comments. A
  key-based word cannot detect a newline already consumed as its delimiter;
  handle empty line comments as well as end-of-source.
- [x] Add a shared, token-aware scan that skips backslash and parenthesised
  comments and the existing plain quoted-string forms (`s"`, `."`). Semicolons
  inside these must not be mistaken for definition terminators. Respect quoted
  word names and definitions of the string/comment words themselves.
- [x] Use the helper in initial loading and hot reload. Recognize only the exact
  optional `\ wf` marker; preserve the first code line when absent. Ensure a
  trailing line comment cannot consume the generated wrapper terminator.
- [x] Add focused tests against the actual VM/shared helper: comment forms,
  delimiters in comments/strings, EOF without newline, CRLF, optional marker,
  multiple definitions followed by a body, and repeated execution.
- [x] Remove the camera packager/test comment stripping and rebuild the levels.
- [x] Build the engine and run loader/reload and existing camera regressions.

## Deferred to TODO

A parser/compiler API redesign, transactional hot-reload dictionary rollback,
a diagnostic overhaul, arbitrary defining-word/source-layout support, and
hot-reload dictionary reclamation are separate work. This change retains the
existing definitions-before-body convention and append-only reload allocation.
It does not claim atomic rollback when compilation has already changed shared
Forth definitions, or a general lexer for user-defined parsing words.

## Acceptance

The commented camera Forth source reaches the engine unchanged and works.
Normal loading and hot reload agree on script splitting. Comment/string
semicolons do not affect the selected boundary; repeated execution reuses the
compiled entry. Existing camera, touch, door and teleport behavior is preserved.

## Files

- `engine/stubs/scripting_zforth.cc`: bootstrap and both loading paths.
- Shared source helper and focused tests added alongside this implementation.
- `wflevels/condo_639_640/blender_create_condo.py` and
  `tests/verify_condo_camera_forth.py`: remove local comment preprocessing.
- [Camera implementation](2026-09-25-condo-camera-controls.md).

## Validation results

- `task test-forth-source`: passed 10,105 checks, including 10,000 repeated
  calls without dictionary or stack growth. Tests use the actual shared helper
  and VM, including string delimiters and empty/EOF line comments.
- `task build`: built the updated engine. The immediate backslash primitive
  is appended to the primitive table, preserving existing opcode numbering.
- Desktop and touch condo packages rebuilt with source comments preserved.
- `verify_forth_reload.py`: initial commented camera load, four hot-reload
  cases, and restoration of the original actor script all passed.
- Camera, touch, apartment teleport and full door regressions passed on the
  rebuilt engine. The 10,082-frame camera VM test also passed without stripping
  comments.

The engine change is limited to the shared source helper, both existing loading
paths, and the immediate comment primitive plus its current-delimiter state.
No general parser API or reload transaction was introduced. Authoring behavior
is documented in [Forth script loading](../forth-script-loading.md).
