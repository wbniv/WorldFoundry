# Plan — Q✱bert player death animation

**Date:** 2026-05-11
**Status:** DONE (commits `e5ebb01d`, `c481b368`) — curse-bubble death animation + UV-mapped "@!#?@!" texture.

## Context

The arcade-fidelity TODO ([TODO.md:100](../../home/will/WorldFoundry.2026-new-level/TODO.md)) flags the current player death as a placeholder: a flat 30-tick Z-ramp followed by an instant teleport back to the apex. No tumble, no splat, no acknowledgement that the player died — the silhouette just slides downward and reappears. The arcade has a discrete fall with the player tumbling, then a brief flattened "splat" on impact before respawn.

This plan keeps the death event small, fun, and self-contained: same 30-tick budget, same scale/rotation mailboxes, no engine changes. Only the Forth fall handler in the player script and one new pre-placed bubble actor change.

Bundled: the curse-bubble overlay — [TODO.md:95](../../home/will/WorldFoundry.2026-new-level/TODO.md), `"@!#?*"` speech-bubble visual — because it shares the death trigger and is the most iconic single Q✱bert visual gag. SFX for both items remains deferred (audio subsystem is a separate sibling TODO).

## Approach — tumble + splat, reusing existing mailboxes

The existing death state machine lives in [blender_create_qbert.py:542–557](../../home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py) and runs over `FALL_PHASE ∈ [1, 30]`. The hop stretch-and-squash code at [blender_create_qbert.py:624–648](../../home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py) already shows the idiom for writing per-frame scale to mailboxes 3040/3041/3042. The hop-rotation block at [blender_create_qbert.py:583–594](../../home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py) drives DELTA_YAW (mb 3034) the same way. Reuse both during the fall.

Three additive behaviours, layered onto the existing Z-decrement (no removal of current code):

### 1. Tumble while falling — frames 1..27

Drive a constant DELTA_PITCH (front-flip tumble) and a smaller DELTA_YAW (lazy spin) during the fall.
- `DELTA_PITCH (mb 3035)` ← e.g. `0.05` rev/tick (one full flip over 20 frames; ~1.5 flips across the fall)
- `DELTA_YAW (mb 3034)` ← e.g. `0.02` rev/tick (half-spin over the fall)

Verify the DELTA_PITCH mailbox index against [wflevels/qbert_practice/mailbox.inc](../../home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/mailbox.inc) before authoring — if there isn't one, fall back to yaw-only spin (still reads as a tumble for a small low-poly silhouette).

### 2. Air-stretch while falling — frames 1..27

Slight prolate stretch so the player visually "streaks" downward as he falls:
- `Z_SCALE (mb 3042)` ← `1.20`
- `X_SCALE (mb 3040)` ← `0.85`
- `Y_SCALE (mb 3041)` ← `0.85`

Constant scale (not per-frame interpolated) — minimal Forth and feels intentional.

### 3. Splat on impact — frames 28..30

Override scales to a wide, flat pancake for the last 3 frames before the apex teleport:
- `Z_SCALE` ← `0.20`
- `X_SCALE` ← `1.80`
- `Y_SCALE` ← `1.80`
- Tumble rates → `0` (player has stopped rotating at the bottom of his fall)

### 4. Curse-bubble overlay — frames 1..27

A pre-placed `curse_bubble` actor sits parked off-screen by default (Z = -100). When the player dies, the player script repositions the bubble to hover just above the player's current XYZ for the duration of the fall, then parks it again on respawn.

**Arcade reference:**

![Q✱bert death curse bubble — white speech balloon with black @!#?@! glyphs](/home/will/WorldFoundry.2026-new-level/docs/plans/screenshots/qbert-curse-bubble-arcade-ref.png)

*Captured from MAME demo-mode death, qbert ROM, frame 1280 of `qbert_curse_capture.lua` AVI extract. White bubble, black outline, single-colour black glyphs `@!#?@!`.*


Mesh — fully 3D speech balloon, authored in Blender alongside the other procedural mesh helpers in [blender_create_qbert.py](../../home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py):
- **Bubble body** — squashed UV sphere (subdiv-2 or `primitive_uv_sphere_add` segments=20 rings=12), scaled `(1.2, 1.2, 0.7)` so it reads as a rounded lozenge with real depth from any camera angle, not a flat disc. Same idiom as the Coily-egg elongated sphere.
- **Tail** — small cone (`primitive_cone_add` vertices=8, depth=0.4) joined to the underside, pointing down-and-toward-camera so it visually connects to the falling player. Cone not triangle: keeps the 3D read when the iso camera moves.
- Bubble + tail joined via `bpy.ops.object.join()`, matching the enemy-mesh pattern.
- **Text glyphs `@!#?*`** — five small 3D extruded primitives stuck to the +X face of the bubble (asterisks = short cylinder + 4 thin cuboids in a cross; `!` = small cylinder + sphere dot; `?` = bent-extrusion or just curved cylinder; `#` = 4 thin cuboids; `@` skipped or replaced with a swirled cylinder if vert budget tight). Extruded so they cast a tiny shadow and don't look painted.
- Materials (arcade-faithful, verified against MAME capture — see `docs/plans/screenshots/qbert-curse-bubble-arcade-ref.png`, frame 1280 of a 60-second qbert demo death):
  - Bubble fill: **white** `(0.95, 0.95, 0.95)` — the arcade bubble is a flat white speech balloon, not coloured
  - Glyph colour: **black** `(0.05, 0.05, 0.05)` — all glyphs share one colour; the arcade does NOT use multi-colour symbols
  - Outline ring: **black** `(0.05, 0.05, 0.05)`, ~1-pixel-equivalent thickness around the bubble silhouette
  - Glyph string: `@!#?@!` (six characters — the arcade repeats `@!` rather than ending on `*`; verify against the reference PNG when authoring)
  - Capture method: `scripts/research/mame/qbert_curse_capture.lua` runs MAME demo mode for ~60 s with `-aviwrite`; `ffmpeg -i ... fps=30` extracts frames; the bubble window is roughly frame 1278–1290 of the 30-fps extract. Q✱bert during the death is red `(~0.85, 0.15, 0.10)` rather than his usual orange — a separate per-state palette swap we can add later if desired (out of scope here).
- Vert budget: ≤ 150 verts (well under the 206-vert player reference; bubble body ~80, tail ~17, glyphs ~50).
- Faces +X so the glyphs read from the iso camera; the 3D body still has volume from every angle.

Actor — single `actor3d`-class actor (`wf_Mesh Name = 'curse_bubble.iff'`), no script of its own, no physics, `Mobility = Anchored`. Lives in the player's mailbox space so the player script can write its position directly via `write-actor-mailbox` (same pattern the director uses for cube colour writes per [blender_create_qbert.py:18](../../home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py)).

Forth driver in the death state-machine — inside the existing `dup 30 <` branch, alongside the tumble/stretch writes:
- Read player X/Y/Z and write them (+2.0 to Z, to float above the player's head) to the curse-bubble actor's INDEXOF_X_POS / Y_POS / Z_POS mailboxes
- Optional flourish: gentle yaw spin on the bubble itself via its DELTA_YAW (`0.01` rev/tick)

In the respawn (`else`) branch — park the bubble back at Z = -100 so it disappears.

### 5. Cleanup on respawn (existing line 547–553)

Already snaps Z to 15 and clears FALL_PHASE. Add four more writes:
- `1.0 3040 write-mailbox 1.0 3041 write-mailbox 1.0 3042 write-mailbox` — identity scale on respawn
- `0 3034 write-mailbox 0 3035 write-mailbox` — zero rotation rates
- `-100 <curse-bubble-Z-mailbox> write-actor-mailbox` — park the curse bubble

So the player reappears at apex with natural shape, no residual spin, and the bubble disappears.

## Critical files

| File | Change |
|------|--------|
| [wflevels/qbert_practice/blender_create_qbert.py](../../home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py) (death state machine, ~lines 542–557) | Add tumble + air-stretch + curse-bubble-position writes inside the `dup 30 <` branch; add splat-override writes in a new `dup 27 >` sub-branch; add scale/rotation reset + bubble-park writes in the respawn (`else`) branch. |
| [wflevels/qbert_practice/blender_create_qbert.py](../../home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py) (new builder) | Add `_build_curse_bubble_actor()` + mesh helper, modelled on the existing enemy builders. Emits `curse_bubble.iff` mesh and one `actor3d` instance parked at Z = -100. |

**No changes** to:
- `enemy.oad` / `player.oad` / any `.oas` (curse bubble reuses the existing `actor3d` class — same class used by the existing static-mesh enemies)
- Engine source (`wfsource/source/...`)
- Mailbox layout (writes to existing 3034/3035/3040/3041/3042 + the curse-bubble actor's standard position mailboxes via `write-actor-mailbox`)

## Verification

1. **Build pipeline** — Standard 4-stage rebuild:
   ```
   blender -b wflevels/qbert_practice/qbert_practice.blend -P wflevels/qbert_practice/blender_create_qbert.py
   wflevels/qbert_practice/build_level_binary.sh
   wftools/iffcomp-rs/target/release/iffcomp-rs wflevels/qbert_practice-standalone.iff.txt
   engine/build_game.sh && (cd wfsource/source/game && ./wf_game)
   ```
2. **Trigger death** — Drive the player off the pyramid edge (hop south from a row-6 cube). Watch in the engine viewport.
3. **Expected** —
   - Player tumbles head-over-feet (or spins, if pitch mailbox absent) for ~27 frames while Z drops.
   - Player is visibly stretched downward during the fall (prolate, ~20% taller, ~15% narrower).
   - Curse bubble pops into existence ~2 units above the player on frame 1, tracks the falling player, and disappears on respawn.
   - For the last 3 frames the player flattens to a pancake at the bottom of his fall.
   - On apex respawn, the player is back to identity scale and zero rotation rate — no residual spin carrying into the next round, and no bubble visible.
4. **Regression check** — Do a normal pyramid hop afterward; confirm the stretch-and-squash hop animation still plays correctly (the death-respawn cleanup writes shouldn't survive into the next hop because the hop block at lines 624–648 unconditionally overwrites the scale mailboxes per-frame).
5. **Capture** — Save a short `qbert-death-anim.mp4` to the repo root via the FBO-capture path ([2026-05-11-record-video-fbo-capture.md](../../home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-11-record-video-fbo-capture.md)) and link from the commit message.

## Out of scope

- Explosion / debris particles (would need `Generator` + `Explosion` actor wiring — bigger plan)
- Death SFX + curse-bubble SFX (audio system is a separate sibling TODO)
- Camera reaction (cs_death already pans to the player; sufficient)
