# Plan-status sweep — reconcile every plan doc with the code

**Date:** 2026-05-25
**Status:** DONE 2026-05-25 — all 225 plan docs carry an accurate Status; `TODO.md`,
[`wf-status.md`](../../wf-status.md), and [`wf-edit-manual.md`](../wf-edit-manual.md) reconciled.

## Context

Across several sessions, the question "what's left to do?" kept resolving to "it's already
done — the docs are stale." In one day: the co-editing roadmap row, the wf-edit capability
table, and editor item "#2" ("only ~15 fields render live" → actually 77) were all stale.
The root cause isn't a missing feature; it's that plan docs' `Status:` lines had drifted
out of sync with the code, so finished work masqueraded as open work and a handful of
genuinely-open items hid in the noise.

This sweep verified every plan's true state against git/code — **never** trusting the
plan's own `Status:` line — and rewrote the stale ones, then reconciled `TODO.md`,
[`wf-status.md`](../../wf-status.md), and [`wf-edit-manual.md`](../wf-edit-manual.md).

## Method

Three (then four) Explore sub-agents each took a batch of plans and, per plan,
`git log`-ed / grepped the actual deliverable rather than reading the `Status:` line.
Verdicts were spot-checked — the no-status batch agent had a strong **false-negative**
bias (it searched for wrong filenames/symbols), so ~10 of its "OPEN" verdicts were
corrected to DONE after direct checks (e.g. voice/video calling, Android Phase 2, the
[Blender version test matrix](2026-05-21-blender-version-test-matrix.md),
`--debug-print-actors`, the 16-round palette, the camera pull-back, `marble-madness-2`).

## Results

- **225** plan docs scanned; **57** had no `Status:` line; **~35** claimed
  "Not started / In progress / Planning / Ready to implement" while shipped.
- **~50 plans flipped to DONE** with verifying commits — the source of the false
  "nothing to do." Engine: [yrs C-ABI binding](2026-05-18-yrs-c-abi-binding-v1-collaborative-editor-sub-task-1.md),
  [SpawnActor live sync](2026-05-21-confirm-spawnactor-live-structural-sync-oad-kpropmap.md),
  [77-field bridge](2026-05-21-widen-the-editor-bridge-to-use-the-generated-map.md),
  [wfmut CTest](2026-05-19-wfmut-test-completion-ctest-integration-coverage.md),
  [LMalloc canary](2026-05-17-engine-caps-lmalloc-debug-canary.md),
  [LP64 long audit](2026-05-20-runtime-long-audit.md), dir reorg, collision-pointer,
  window-close. Game: [SMB coin/Gold](2026-05-19-smb-block-coin-block-is-generator-collectible-gold.md),
  [Mario tuning](2026-05-17-smb-mario-speed-jump-tuning.md),
  [collision mailboxes](2026-05-17-per-actor-collision-mailboxes.md),
  [scrolling camera](2026-05-17-smb-scrolling-camera.md), Q✱bert
  [enemy meshes](2026-05-11-distinct-enemy-meshes-slick-sam-ugg-wrong-way-coily.md) /
  [death anim](2026-05-11-qbert-player-death-animation.md) /
  [difficulty](2026-05-15-qbert-per-round-difficulty-scaling.md) /
  [diamond layout](2026-05-08-apply-qbert-diamond-layout-to-the-level-generator.md). Tooling:
  [iffcomp-rs](2026-04-15-iffcomp-rs-rewrite.md),
  [apt.worldfoundry.org](2026-05-17-apt-worldfoundry-org-bootstrap.md) (verified live, HTTP 200).
- **The genuine backlog** got accurate PARTIAL/OPEN text (not "Not started"):
  [mpeg4 capture](2026-05-01-frame-capture-mpeg4-video.md) /
  [FBO capture](2026-05-11-record-video-fbo-capture.md),
  [Steam SDK](2026-04-17-steam.md), [Lua-default-on](2026-05-10-lua-default-on-linux-debug.md),
  [neural-forth examples](2026-05-22-neural-forth.md),
  [pure-Python asset provider](2026-04-28-wf-asset-provider-pure-python.md),
  [Codemagic budget monitor](2026-05-12-codemagic-budget-monitor.md),
  [Chromecast/TV](2026-04-23-chromecast-google-tv-port.md),
  [rapid-raccoon migration](2026-04-23-rapid-raccoon-cloudflare-migration.md),
  [do-cd-iff flag](2026-05-10-promote-do-cd-iff-to-a-togglable-build-flag.md),
  [UV-repeat fix](2026-05-18-fix-texture-uv-repeat-preserve-float-uvs-through-the.md).
- **0** plans now lack a `Status:` line.

### `TODO.md` corrections
- **Editor Phase 0a** (`libwfengine.a` split) — DONE; `add_library(wfengine STATIC …)`
  at `CMakeLists.txt:604`.
- **Eliminate RTTI** — DONE; all `dynamic_cast` calls gone (only comments remain in
  [`baseobject.hp`](../../wfsource/source/baseobject/baseobject.hp)), `-fno-rtti` engine-wide.
- **Relay persistence** — DONE in [`wf-relay`](../../wftools/wf_collab/src/bin/relay.rs);
  only the BYOK `wrap: bytes → bytes` seam remains.
- **Chat sidebar** — ships plaintext; only the
  [`imgui_markdown`](https://github.com/juliettef/imgui_markdown) rendering upgrade remains.

### `wf-edit-manual.md` corrections
- "Live viewport preview … ~15 movement fields" → all 77 common/movebloc/mesh fields live;
  only mesh-geometry (Model Type / Tiles / Map) needs a reload to be *seen*.
- "No undo for any edit" → native Ctrl+Z / Ctrl+Y via the Yrs `UndoManager`.

## Deferred by this sweep

The original ask — implement editor **#2** (full live-viewport coverage) and **#3** (gizmo
G/R keys + snap) — was set aside for this reconciliation. #2 turned out ~done (the 77 fields
already propagate; only the deliberately-out-of-scope mesh-rebuild and a doc fix remained,
the doc fix folded in here). **#3 (gizmo G/R + snap)** is the real remaining editor polish
item and is still open — see [the viewport-gizmo plan](2026-05-22-viewport-gizmo.md) § Phase 4.

## Verification

- `for f in docs/plans/*.md docs/qbert/plans/*.md; do head -30 "$f" | grep -qiE '^#{0,4} *\**[Ss]tatus' || echo NOSTATUS:$f; done`
  → **0**.
- The "not done/closed" grep returns only genuine OPEN / PARTIAL / PARKED / DEFERRED /
  SUPERSEDED / REFERENCE plans — the real backlog.
- Spot-checks: `git log` confirmed the cited commits touch each flipped plan's deliverable;
  `curl -sI https://apt.worldfoundry.org/` → HTTP 200.
