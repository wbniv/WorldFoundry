# Plan — ROM-grounded Q*bert walker (closes L4R1 gap, unifies MAME ↔ WF regression)

**Date:** 2026-05-08
**Status:** Phase A done. Phase B done. Phase C: walker captures L1R1 cleanly; multi-round operation hits position drift. Phase D: blocked on RAM-to-visual-round mismatch.

## Context

[`docs/investigations/qbert_cube_face_colors.md`](../investigations/qbert_cube_face_colors.md)
documents per-round cube colors captured from MAME for all 16 rounds. **15 of
16 are confirmed; L4R1 state-1 remains marked `unknown ⚠️`** — Demo AI
(via DIP "Demo Mode (Unlim Lives, Start=Adv (Cheat))") fights us during the
2-hop snap window. Multiple attempts on 2026-05-08 failed:

- **DIP runtime toggle** does not propagate — DIP switches are sampled at
  boot/reset only, not at runtime, so [`qbert_capture_v2.lua`](../../scripts/research/mame/qbert_capture_v2.lua)'s
  cheat-toggle approach silently fails.
- **`qbert_bot.lua` Warnsdorff** (no cheat, RAM unlim-lives at `0x0D00`) never
  actually round-clears in ROM — bot's `cubes_done >= 28` heuristic uses
  dead-reckoned `qrow/qcol` that drifts when hops drop. Verified in
  [`qbert_bot_run.log`](../investigations/qbert_bot_run.log): `[palette]
  unchanged` at every "ROUND COMPLETE L*R*" — palette never advances → ROM
  was on L1R1 the whole run.
- **Burst-snap during L4R1**: with no joystick stimulation Demo AI is frozen
  at apex; with stimulation Demo AI activates but ROM transitions to attract
  mode within ~80 frames (Q*bert dies offscreen).

The same closing-the-gap problem and the WF-port regression problem reduce to
the same primitive: a **ROM-grounded Warnsdorff bot** that actually clears
rounds in the arcade ROM. Once we have that, we can:

1. Capture L4R1 state-1 cleanly (final per-round palette cell).
2. Run the same Warnsdorff sequence against the WF port via the existing
   `mb[430] AUTOPILOT_ON` autopilot
   ([`docs/investigations/2026-05-05-qbert-autopilot.md`](../investigations/2026-05-05-qbert-autopilot.md)),
   producing screenshot pairs we can pixel-diff for regression.

## Goal

A Lua script `scripts/research/mame/qbert_walker.lua` that:

1. Boots Q*bert with **cheat OFF** (no Demo Mode).
2. Pokes RAM `0x0D00 = 9` every frame (unlim lives — works without DIP cheat).
3. Reads Q*bert's **real** position from RAM (not dead-reckoned).
4. Detects **real** round-clear via palette write-tap (signal: `pal_writes`
   delta > threshold, not bot's internal counter).
5. Drives Warnsdorff coverage through all 16 rounds, retrying dropped hops.
6. Emits 3 named screenshots per round: `walker_L{lv}R{rnd}_{state0|state1|state2}.png`.

Same script's *protocol* (DR-first move, snap state-0 at apex, snap state-1
after first hop returns to apex) is used by the WF-side autopilot so the
two engines produce comparable image pairs.

## Plan

### Phase A — find Q*bert's real position byte(s) (1–2 hours)

The qbert ROM almost certainly has a single byte (or pair) holding Q*bert's
current `(row, col)` or cube index. [`qbert_bot.lua`](../../scripts/research/mame/qbert_bot.lua)
notes "0x0081 increments with hops" — that's a *hop counter*, not position.
We need true position.

Strategy: extend the existing
[`qbert_full_diff.lua`](../../scripts/research/mame/qbert_full_diff.lua)
diff-scan tool to capture RAM snapshots at known Q*bert positions:

1. Boot, drive to `(0,0)` apex, snapshot RAM. Tag = `apex`.
2. Inject DR hop, wait for landing, snapshot RAM. Tag = `(1,1)`.
3. Inject UL hop, snapshot. Tag = `apex` again.
4. Inject DL hop, snapshot. Tag = `(1,0)`.
5. Diff: bytes that toggle between `apex` value and `(1,1)` value but stay
   constant during apex repeats are position candidates. Cross-check against
   `(1,0)` snapshot (different value than both).

Output: write `docs/investigations/qbert_position_ram.md` with the byte
addresses, valid range, and encoding (likely `(row << 4) | col` or cube index
0..27).

### Phase B — round-clear detection via palette tap (30 min)

Current [`qbert_bot.lua`](../../scripts/research/mame/qbert_bot.lua) installs
a write-tap on `0x5000–0x501F` that increments `pal_writes` per palette write
(line 196–200). At round-clear, the ROM rewrites the palette for the new
round's colors → `pal_writes` jumps by ~32 (16 pens × 2 bytes).

Walker rule: between hops, watch `pal_writes`. If it deltas by ≥ 16 since the
last hop, **round just cleared in ROM** — wait 240 frames for the transition
animation, snap state-0 of the new round, resume Warnsdorff.

This replaces the broken `cubes_done >= 28` heuristic.

### Phase C — verified Warnsdorff (1–2 hours)

Build on `qbert_bot.lua`'s Warnsdorff core but add:

- **Pre-hop snapshot**: capture `pos_addr_value`, `pal_writes` before hop.
- **Post-hop verify**: after `HOP_HOLD + HOP_COOLDOWN` frames, read
  `pos_addr_value` again. If unchanged → hop dropped. **Do not** update
  `qrow/qcol` (no dead-reckoning); retry same direction next iteration.
- **Position resync**: every iteration, snap ROM position into bot's
  `qrow/qcol` (eliminates drift entirely).
- **Death tolerance**: when ROM position resets to apex unexpectedly +
  `pal_writes` did *not* delta, that's a death. Reset bot state, continue.
- **Walker snap injection** (already drafted in
  [`qbert_bot.lua`](../../scripts/research/mame/qbert_bot.lua) lines 161–186,
  368–399): PRE → AFTER_DR → AFTER_UL state machine. Keep as-is; it just
  needs the round-clear signal to reset properly.

### Phase D — closing the L4R1 gap (10 min)

1. Run `mame qbert -video none -seconds_to_run 1500 -speed 10 \`
   `-rompath assets/arcade-roms -autoboot_script scripts/research/mame/qbert_walker.lua`.
2. The walker emits `walker_L4R1_state1.png` directly — copy to
   `docs/investigations/mame-screenshots/qbert_hop_L4R1.png`.
3. Run `python3 scripts/research/mame/sample_cube_colors.py` — verify L4R1
   row shows `kind = 2-step` and `state0 ≠ post-hop ≠ state2`.
4. Update `docs/investigations/qbert_cube_face_colors.md`: replace L4R1's
   `**unknown** ⚠️` with the captured hex; delete the ⚠️ paragraph at lines
   120–127 and the trailing caveat at lines 142–145.

### Phase E — WF-side parity (separate follow-up; ~half day)

Out of scope for this plan but enabled by it:

1. WF-side autopilot already exists (`mb[430]` in
   [`wflevels/qbert_practice/blender_create_qbert.py`](../../wflevels/qbert_practice/blender_create_qbert.py)
   `DIRECTOR_SCRIPT`).
2. Add `mb[431] CAPTURE_TRIGGER` mailbox; director writes 1/2/3 at the same
   moments the MAME walker snaps.
3. Wire a debug-bridge `screenshot` op (Phase B-style addition) that reads
   the WF framebuffer and writes a PNG.
4. Run `wf_walker.py` (a thin pytest harness) that drives the WF level
   through all 16 rounds, captures `wf_walker_L{lv}R{rnd}_{state}.png`.
5. Compare-tool: pixel-diff `walker_L*R*_*.png` (MAME) vs `wf_walker_*.png`
   (WF) at the cube-top sample points. Pass = matching colors at sample
   points; visual diff acceptable elsewhere (different sprites, same palette).

## Critical files

| File | Phase | Action |
|---|---|---|
| `scripts/research/mame/qbert_full_diff.lua` | A | Adapt for position-byte hunt |
| `scripts/research/mame/qbert_bot.lua` | C | Refactor: real position read, palette-tap round-clear |
| `scripts/research/mame/qbert_walker.lua` | C | New file (or rename qbert_bot.lua) |
| `docs/investigations/qbert_position_ram.md` | A | New file documenting the position byte(s) |
| `docs/investigations/qbert_cube_face_colors.md` | D | Update L4R1 state-1 cell |
| `docs/investigations/mame-screenshots/qbert_hop_L4R1.png` | D | Replace with walker-captured frame |

## Verification

End-to-end pass:

1. `python3 scripts/research/mame/sample_cube_colors.py` reports L4R1 with
   `state0 ≠ post-hop ≠ state2` and `kind = 2-step`.
2. The 15 currently-working rounds are unchanged.
3. `grep -ni "unknown\|⚠️\|unconfirmed" docs/investigations/qbert_cube_face_colors.md`
   returns no L4R1 hits.
4. `qbert_bot_run.log` shows `[palette] CHANGED` (not `unchanged`) at
   each round transition — proves ROM actually advanced.

## Risks

- **Position byte hunt finds nothing** — fall back to reading the on-screen
  Q*bert sprite location from sprite RAM at `0x3000` (already partially
  decoded in `qbert_bot.lua` lines 271–282). Slower but always available.
- **Palette doesn't change every round** (e.g. L1R1→L1R2 might keep same
  palette) — fall back to the actual round counter byte if palette-tap is
  insufficient. The `qbert_palette_dump.lua` device-based reader could help
  identify which byte ROM uses internally for round number.
- **Walker takes too long** — 56 hops × 16 rounds × ~50 frames = 45000
  frames = 12.5 minutes at speed=10 = 1.25 minutes wall. Should be fine.

## 2026-05-08 progress notes (during initial Phase 2 attempt)

- **Phase A done**: position byte found at `0x0D64`. Apex value = `0xB8`.
  Each cube position has a unique value (verified in
  `scripts/research/mame/position_hunt.txt`). Tool:
  `scripts/research/mame/qbert_position_hunt.lua`.
- **Phase B done**: palette-tap round-clear detection works. Threshold
  `pal_writes` delta ≥ 32 since last round.
- **Phase C partial**: `scripts/research/mame/qbert_walker.lua` captures
  L1R1 state-0 + state-1 cleanly. But multi-round operation accumulates
  position drift — bot tracks `qrow=6,qcol=6` while ROM has Q*bert at
  `pos=0xF5` (= (1,1)). Result: bot's `cubes_fully=28` doesn't correspond
  to ROM having all 28 cubes at state-2, so ROM never round-clears.
  - **Drift cause**: dead-reckoning `qrow,qcol` from issued direction is
    incorrect when ROM rejects a hop (e.g. enemy push, edge of pyramid).
    Hop-verify catches "didn't move" cases but not "moved somewhere
    unexpected".
  - **Drift fix path** (Phase C.5, deferred): build a `pos_byte → (row,col)`
    lookup table during a calibration walk, then on each iteration sync
    `qrow,qcol` from the real ROM position rather than dead-reckoning.
- **Phase D blocked**: hybrid `qbert_l4r1_walker.lua` (DIP cheat advances
  to L4R1 + walker snap-dance) reaches `round_num=16` (= ram `0x13`) but
  ROM HUD shows L3R4 at the snap moment, not L4R1. Tried settle delays
  of 0/30/60/90/180 frames — short delays show L3R4, longer delays show
  L1R1 (Demo AI restarts). The doc's
  [`docs/investigations/qbert_cube_face_colors.md`](../investigations/qbert_cube_face_colors.md)
  ram-to-round table (line 184) does not match observed behavior under
  cheat-driven advance.
  - **Phase D fix path**: find the *visual* round counter byte (different
    from `0x0081`). Likely the byte the HUD actually reads. Use
    `qbert_full_diff.lua` style snapshot-diff with known visual rounds.

### Useful artifacts left in repo

- `scripts/research/mame/qbert_position_hunt.lua` — Phase A tool
- `scripts/research/mame/qbert_walker.lua` — Phase C walker (L1R1 works)
- `scripts/research/mame/qbert_l4r1_walker.lua` — Phase D hybrid attempt
- `scripts/research/mame/walker_snaps.txt` — snap log format
- `docs/investigations/qbert_walker_run.log` — Phase C run log

The L1R1 capture from `qbert_walker.lua` is **proof the walker mechanism
is sound** — Q*bert lands at apex via real RAM detection, dance produces
clean state-0 / state-1 / state-2 captures with score advancing in ROM
exactly as expected.
