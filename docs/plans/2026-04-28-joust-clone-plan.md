# Plan: Joust clone for 3D World Foundry

## Summary of decisions

- **Scope:** Solid 1-player. Player + 3 enemy classes (Bounder, Hunter, Shadow Lord), eggs, wave progression, on-screen HUD, basic SFX. Pterodactyl, lava troll, 2-player co-op are out of scope.
- **Visual style:** All three art modes implemented — colored boxes, pixel-art sprite billboards, low-poly 3D birds — with a runtime switch (CLI `-L wflevels/joust_<mode>.iff` or wrapper `run_joust.sh --art=<mode>`). Shared scripts and physics across modes; only mesh/material refs differ.
- **Scripting:** zForth (`\ wf`). Snowgoons embedded scripts and the engine shell (`wfsource/source/game/shell.fth`) are already on this path — this brief follows the established convention.
- **Combat resolution:** dedicated `Referee` actor running an O(N) AABB sweep each tick (engine collision callbacks don't expose the second-actor index to scripts).
- **Edge-wrap:** per-actor script-side X-position modulo (cheaper than an engine-level wrap concept).

## Engine extensions (~1070 LOC C++, no breaking changes)

- **EXT-1: Bitmap-font HUD overlay** — text rendering doesn't exist today; required for score / lives / wave indicator.
- **EXT-2: WAV SFX trigger from scripts** — `SoundBuffer::play()` exists, just needs a script-visible mailbox shim.
- **EXT-3 (sprite mode only): Camera-facing billboard helper** — pixel-art frames need to face the camera regardless of camera angle.
- **Cross-actor mailbox bridge for zForth (~30 LOC):** add `read-mailbox-of` / `write-mailbox-of` as `ZF_SYSCALL_USER+2/+3`. Parity with the Lua plug.

## Files to create

See the in-repo doc for the full list. Headlines:

- `wflevels/joust/joust.fth` + `joust_constants.fth` — shared script source.
- `wflevels/joust_boxes/`, `wflevels/joust_sprites/`, `wflevels/joust_lowpoly/` — three sibling level builds.
- `wfsource/source/gfx/text.{hp,cc}` + `wfsource/source/gfx/glpipeline/hud_overlay.cc` — EXT-1.
- `wfsource/source/audio/wav_dispatch.{hp,cc}` — EXT-2.
- `wfsource/source/gfx/billboard.{hp,cc}` — EXT-3.

## Verification

End-to-end smoke checks defined in the doc — boot, tap-to-flap, glide, edge-wrap, lava death, joust win/lose, egg pickup vs. hatch, wave progression, HUD, SFX, art-mode parity (run all checks across boxes / sprites / lowpoly).

## Phasing

~3.5 weeks of focused work split across four phases (engine extensions → boxes-mode game → full enemy roster + sprites → low-poly + polish).
