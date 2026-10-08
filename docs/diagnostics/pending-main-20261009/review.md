# Pending main-checkout work — commit review, 2026-10-09

Will authorized committing and pushing the entire pending set, plus the two
existing local-only commits. Review covers coordinator extraction and producer
wrappers, opt-in runtime diagnostics, runtime settings, Android touch controls,
aquarium assets/controllers, posters/research, and retained diagnostic evidence.

- [x] Inventory: 129 changed/deleted tracked paths and 2,829 initially untracked
  files. Seven unchanged PDFs are detected as renames by Git.
- [x] Preserve the generated 82 MB `texture_atlas_address_test` executable in
  ignored `engine/build-pending-artifacts/`, excluding it from the commit.
- [x] Retain the requested evidence, including baseline captures and transcripts.
- [x] Scan 2,420 pending text files for private keys, AWS keys, GitHub/OpenAI
  tokens and bearer credentials: no matching patterns found. This is a scoped
  pattern scan, not a guarantee that arbitrary sensitive data cannot exist.
- [x] Initial targeted suite: 127 pass; two phone tests initially blocked by a
  missing Playwright executable. Install the required Chromium headless shell.
- [x] Update one stale phone test from the old native colour input to the existing
  custom palette/RGB panel; retain colour, text, cancellation and persistence
  assertions. No product code changes were needed for this test correction.
- [x] Phone and runtime-property UI suite: 4/4 pass after the test correction.
- [x] Android touch behavior executable: 157 checks pass.
- [x] Authored code whitespace check passes. Retain raw logs and generated level
  text bytes, including their pre-existing trailing whitespace.
- [x] Integrate with remote `2026-new-level` at `be053e6a`, preserving teleport
  fixes, both local-only commits, and the pending-work commit `ef99d415`.
- [x] Build the combined native engine with assertions and room-transition UBSan.
- [x] Integrated Python coverage: 129 tests pass in the full targeted run; the
  two runtime-property tests then pass after supplying the fresh checkout's
  missing catalog executable. The unchanged Rust source permits reuse of the
  main checkout's local library and catalog. Total: 131 passing tests.
- [x] Combined native suite: 24/24 pass, including script and mutation-API
  cross-room teleports and unloaded-actor teleports; Android touch: 157 checks.

Publication and final local/remote hash synchronization are checked after the
integration commit and reported in the session result. Build and integrated
test transcripts are retained here; the initial sandbox run was blocked by
loopback/browser access and missing local test dependencies, which were resolved.

The existing local-only commits are `514e642e` (balcony plan B) and `8da671d1`
(release Jolt logging). They remain in branch history and are included in the
integration. Evidence from the current checks is retained alongside this review.
