# Plan — ROM-grounded Q✱bert walker (closes L4R1 gap, unifies MAME ↔ WF regression)

**Date:** 2026-05-08
**Status:**
- **A** ✅ position byte hunt — `0x0D64` works for snap dance triggers (apex check) but collides across cubes; sprite X/Y pair (`0x0D58`, `0x0D59`) has animation transients so unreliable for cube-level tracking
- **B** ✅ palette write-tap delta ≥ 32 = round-clear signal
- **C** ✅ multi-round walker (DIP-cheat-driven, drift-immune) — captures state-0 + state-1 for all 16 rounds in a single run; 15/16 rounds match doc exactly; L4R1 in multi-round mode hits transition timing (state-0 captures L4 zoom screen instead of pristine apex). Standalone `qbert_l4r1_walker.lua` captures L4R1 cleanly.
- **D** ✅ L4R1 state-1 = `#EFDE77` captured and committed
- **E** in progress — WF-side parity scaffolding landed (engine `screenshot` op, mb[432] CAPTURE_TRIGGER in director, host harness + diff tool); end-to-end run pending. See [2026-05-09-qbert-walker-wf-parity.md](2026-05-09-qbert-walker-wf-parity.md).

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
  mode within ~80 frames (Q✱bert dies offscreen).

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

1. Boots Q✱bert with **cheat OFF** (no Demo Mode).
2. Pokes RAM `0x0D00 = 9` every frame (unlim lives — works without DIP cheat).
3. Reads Q✱bert's **real** position from RAM (not dead-reckoned).
4. Detects **real** round-clear via palette write-tap (signal: `pal_writes`
   delta > threshold, not bot's internal counter).
5. Drives Warnsdorff coverage through all 16 rounds, retrying dropped hops.
6. Emits 3 named screenshots per round: `walker_L{lv}R{rnd}_{state0|state1|state2}.png`.

Same script's *protocol* (DR-first move, snap state-0 at apex, snap state-1
after first hop returns to apex) is used by the WF-side autopilot so the
two engines produce comparable image pairs.

## Plan

### Phase A — find Q✱bert's real position byte(s) (1–2 hours)

The qbert ROM almost certainly has a single byte (or pair) holding Q✱bert's
current `(row, col)` or cube index. [`qbert_bot.lua`](../../scripts/research/mame/qbert_bot.lua)
notes "0x0081 increments with hops" — that's a *hop counter*, not position.
We need true position.

Strategy: extend the existing
[`qbert_full_diff.lua`](../../scripts/research/mame/qbert_full_diff.lua)
diff-scan tool to capture RAM snapshots at known Q✱bert positions:

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

Now well-scoped — the MAME-side walker protocol is fully defined:

**Walker protocol** (one round):

1. At round entry, Q✱bert is at apex with all cubes in state-0.
2. Capture frame: `state0` snap. Sample at apex top (`(120, 56)`) and
   target cube top (`(137, 80)` for cube (1,1)).
3. Force DR hop. Cube (1,1) flips state.
4. Force UL hop back to apex.
5. Capture frame: `state1` snap. Cube (1,1) sample now shows state-1 color
   (intermediate for 2-step rounds, state-2 for 1-step).
6. Round-clear via gameplay (or director script for WF side); next round
   begins; loop.

**WF-side implementation:**

1. WF autopilot already exists (`mb[430]` in
   [`wflevels/qbert_practice/blender_create_qbert.py`](../../wflevels/qbert_practice/blender_create_qbert.py)
   `DIRECTOR_SCRIPT`). It currently runs a 32-hop coverage path.
2. Add `mb[431] CAPTURE_TRIGGER` mailbox: director writes `1` at apex
   pre-hop (= state0 snap point), `2` at apex post-DR-UL-dance (= state1
   snap point), `3` at round-clear, `0` otherwise.
3. Wire a debug-bridge `screenshot` op (Phase B-style addition to
   `engine/debug_bridge.cc`) that reads WF framebuffer via
   `glReadPixels` and writes a PNG. Bind to `mb[431]` transitions.
4. Test harness `scripts/test/qbert_wf_walker.py`: connects to debug
   bridge port 7777, watches for `mb[431]` events, captures PNGs as
   `wf_walker_L{lv}R{rnd}_{state}.png`.
5. Compare-tool `scripts/test/qbert_walker_diff.py`: pixel-diff at
   sample points `(120,56)`, `(137,80)`, `(40,55)` between MAME and WF
   captures. Pass = matching colors. Background/sprite differences
   ignored — only cube-top sample points matter for palette regression.

**Determinism**: clear NVRAM before MAME run; WF side has no equivalent
state — director script + autopilot fully replay-deterministic.

**Edge cases**:
- L4R1 multi-round capture has the transition-zoom timing issue. Use
  `qbert_l4r1_walker.lua` standalone for this round, OR accept that WF
  side has no equivalent transition delay so the WF capture's "state-0"
  is automatically clean.
- For 1-step rounds, state-1 = state-2 (no intermediate); the
  `kind=1-step` classifier already handles this in `sample_cube_colors.py`.

## Critical files

| File | Phase | Status |
|---|---|---|
| `scripts/research/mame/qbert_position_hunt.lua` | A | ✅ created |
| `scripts/research/mame/qbert_pos_calibrate.lua` | A | ✅ created (revealed position-byte limits) |
| `scripts/research/mame/qbert_walker.lua` | C | ✅ multi-round walker (DIP-cheat-driven) |
| `scripts/research/mame/qbert_l4r1_walker.lua` | D | ✅ standalone L4R1 capture |
| `scripts/research/mame/qbert_round_byte_hunt.lua` | D | ✅ proved +119 timing |
| `docs/investigations/qbert_cube_face_colors.md` | D | ✅ L4R1 state-1 = `#EFDE77` |
| `docs/investigations/mame-screenshots/qbert_hop_L4R1.png` | D | ✅ replaced with clean capture |
| `engine/debug_bridge.cc` (screenshot op) | E | TODO |
| `wflevels/qbert_practice/blender_create_qbert.py` (mb[431]) | E | TODO |
| `scripts/test/qbert_wf_walker.py` | E | TODO |
| `scripts/test/qbert_walker_diff.py` | E | TODO |

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
  Q✱bert sprite location from sprite RAM at `0x3000` (already partially
  decoded in `qbert_bot.lua` lines 271–282). Slower but always available.
- **Palette doesn't change every round** (e.g. L1R1→L1R2 might keep same
  palette) — fall back to the actual round counter byte if palette-tap is
  insufficient. The `qbert_palette_dump.lua` device-based reader could help
  identify which byte ROM uses internally for round number.
- **Walker takes too long** — 56 hops × 16 rounds × ~50 frames = 45000
  frames = 12.5 minutes at speed=10 = 1.25 minutes wall. Should be fine.

## 2026-05-08 progress notes

### Phase A done — Q✱bert position byte

- Address: `0x0D64`. Apex value `0xB8`. Each cube has a unique value
  (verified across (0,0), (1,1), (2,1), (3,2), (1,0)).
- Tool: [`scripts/research/mame/qbert_position_hunt.lua`](../../scripts/research/mame/qbert_position_hunt.lua).
  Drives Q✱bert through a known position sequence with revisits, finds
  bytes that are stable per-position and distinct between positions.
- Note: byte appears to be a sprite-Y or cube-pixel-Y coordinate, not a
  `(row,col)` encoding. For walker purposes we only need uniqueness, not
  decoding — though Phase C.5 (drift fix) would benefit from a full
  `pos → (row,col)` lookup table built via calibration walk.

### Phase B done — palette-tap round-clear signal

- Install write-tap on `0x5000–0x501F`. Increment `pal_writes` per write.
- ROM rewrites palette on every round-clear (16 pens × 2 bytes = 32
  writes minimum). Threshold `pal_writes - last_round >= 32` reliably
  detects ROM round transition.
- Wired into `qbert_walker.lua`. Replaces the broken `cubes_done >= 28`
  heuristic that `qbert_bot.lua` used.

### Phase C partial — single-round walker works, multi-round drifts

`scripts/research/mame/qbert_walker.lua` produces clean L1R1 state-0 and
state-1 captures via real RAM detection:

1. Wait until `0x0D64 == 0xB8` (true apex, ROM-confirmed).
2. `snap("state0")` — pristine apex, score 0.
3. Force DR hop. Verify via `0x0D64` change to `0xF5` (= (1,1) per Phase A).
   If unchanged, retry same direction.
4. Force UL hop. Wait for `0x0D64 == 0xB8` again.
5. `snap("state1")` — Q✱bert at apex, (1,1) cube flipped exactly once.

**This works perfectly on L1R1.** Score 50, HUD = LEVEL 1 ROUND 1, sample
at (137, 80) gives the documented L1R1 state-1 color.

After the dance, the bot enters normal Warnsdorff to clear the round and
move to L1R2. Multi-round status logs from a 200-second run:

```
frame=1800 at(5,0)  cubes=8/28  fully=2
frame=2400 at(5,5)  cubes=18/28 fully=2
frame=4800 at(1,1)  cubes=28/28 fully=20
frame=6600 at(6,6)  cubes=28/28 fully=28  pal=6336  ← stuck
frame=12000 at(6,6) cubes=28/28 fully=28  pal=6336  ← still stuck
```

`pal=6336` is constant — palette never wrote, ROM never round-cleared.
Bot's `cubes_fully == 28` claim doesn't match reality.

**Root cause: dead-reckoning.** When the bot issues a hop, it updates
`qrow,qcol` to the *expected* destination. The hop-verify step
(`if cur_pos == pos_at_hop_start: retry`) only catches "didn't move at
all" — it misses "moved somewhere unexpected" (edge-of-pyramid no-op,
enemy push, Coily blocks destination). After several mis-tracked hops,
bot's view diverges from ROM. Bot may "visit" a cube twice in its
tracker while ROM never had Q✱bert there. ROM only round-clears when
*all 28* cubes hit state-2; bot's lopsided coverage never satisfies that.

**Phase C.5 fix path** (deferred):

1. **Calibration walk at game start**: drive Q✱bert through every cube
   in a known sequence, build a `pos_byte → (row, col)` lookup table.
   Apex confirmed `0xB8`; (1,1) confirmed `0xF5`; need 26 more.
2. **Replace dead-reckoning**: every iteration, read `0x0D64`, look up
   actual `(row, col)`. Sync `qrow,qcol` from ROM, not from issued
   direction. Drift becomes impossible by construction.
3. **Round-clear via palette tap** (already wired): when `pal_writes`
   delta ≥ 32, transition to next-round state, wait 360 frames for the
   transition animation, resume.

### Phase C.5 done — multi-round walker (architecture pivot)

The original Phase C plan was a Warnsdorff bot that round-clears in ROM via
real position tracking. We tried it. It doesn't work, for two reasons:

1. **The position byte at `0x0D64` collides across cubes.** Phase A's
   strict-uniqueness test missed this because the test sequence only visited
   5 specific cubes. A fuller calibration walk (`qbert_pos_calibrate.lua`)
   visiting all 28 cubes shows e.g. `(6,0)`, `(6,2)`, `(6,4)`, `(6,6)` all
   share `0x26`; `(5,0)`, `(5,2)`, `(5,4)` all share `0x69`. The byte appears
   to encode something like row-Y-coordinate, not unique cube ID.
2. **The 16-bit sprite X/Y pair (`0x0D58`, `0x0D59`) has animation
   transients.** During a run, apex was registered with multiple distinct
   16-bit keys (`0x257D` and `0x917D` both → `(0,0)`). Q✱bert's sprite-X
   shifts between idle/hop frames. So the bot's learned table mis-merges
   cubes and fragments apex across keys.

A real fix would require finding the cube-state RAM array (28 bytes, one per
cube) and using state-change events as the position signal. That's a
deeper hunt than fits in this plan.

**Pivot**: drop Warnsdorff control entirely. Use **DIP cheat** to advance
rounds (the same proven mechanism `qbert_round_byte_hunt.lua` validated for
8 known visual rounds). Per round, inject the same `+119`-frame snap dance
that closed L4R1. Multi-round walker = `qbert_round_byte_hunt.lua` +
state-0/state-1 snap pair per round.

**The NVRAM-determinism finding** (load-bearing):

Early attempts at the multi-round walker showed L4R1 producing the wrong
visual round (HUD said L1R1 with score 50) — even though `qbert_l4r1_walker.lua`
standalone had captured L4R1 cleanly. Hours of debugging suggested
non-determinism between MAME runs. The cause: **MAME persists NVRAM at
`~/.mame/nvram/qbert/nvram` across runs**, and the saved state subtly
shifts demo-mode timing. Coin counter, high-score table, and DIP defaults
all live there.

Fix: clear NVRAM and config before each walker run:

```bash
rm -f ~/.mame/nvram/qbert/nvram ~/.mame/cfg/qbert.cfg
```

After the clear, walker is fully deterministic — same run produces same
captures bit-for-bit. **This applies to all MAME-Q✱bert scripts; every
research script in this plan should preface its run with the cleanup.**

Per-round results from `qbert_walker.lua` after NVRAM clear (sample at
`(137, 80)` on each state-1 snap):

```
L1R1 state1=#DEDE00 (= state-2, 1-step round)  ✓
L1R2 state1=#0046DE (= state-2, 1-step)        ✓
L1R3 state1=#464646 (= state-2, 1-step)        ✓
L1R4 state1=#A9B910 (= state-2, 1-step)        ✓
L2R1 state1=#EFDE77 (intermediate, 2-step)     ✓ matches doc
L2R2 state1=#0066EF                            ✓ matches doc
L2R3 state1=#5646EF                            ✓ matches doc
L2R4 state1=#0046EF                            ✓ matches doc
L3R1 state1=#003199 (= state-2, 1-step)        ✓
L3R2 state1=#B9CECE                            ✓
L3R3 state1=#EFDE77                            ✓
L3R4 state1=#5646EF                            ✓
L4R1 state1=#21B931  ← state-0 green (Demo AI active during multi-round dance)
L4R2 state1=#FF6666                            ✓ matches doc
L4R3 state1=#FF6666                            ✓ matches doc
L4R4 state1=#0066EF                            ✓ matches doc
```

15/16 rounds match the doc canonical values. L4R1 in multi-round mode hits
a known edge case: the L4-entry transition zoom animation eats ~120 frames,
during which Demo AI plays L4R1 ahead of our scripted dance. Standalone
`qbert_l4r1_walker.lua` (which exits after L4R1) doesn't have this issue
because it doesn't progress further; the snap-dance timing perfectly
captures the moment HUD updates to L4R1 with cube (1,1) freshly flipped.

For Phase E (WF parity) the L4R1 case is moot — WF's autopilot directly
controls the level/round transition with no Demo AI to fight, and no
HUD-update lag to time around. Both engines can converge on the same
"snap state-0 at apex; force DR; snap state-1 after UL back" protocol
trivially.

### Phase D done — L4R1 captured

#### How it closed

The breakthrough was [`qbert_round_byte_hunt.lua`](../../scripts/research/mame/qbert_round_byte_hunt.lua)
— it snapped RAM **and a screenshot** at the same `+119`-frame moment
for 8 known visual rounds (L1R1, L1R4, L2R1, L2R4, L3R1, L3R4, **L4R1**,
L4R4). Snap 6 of that run visually showed `LEVEL 4 ROUND 1` with score
520 — proof that the [`qbert_round_shots.lua`](../../scripts/research/mame/qbert_round_shots.lua)
timing window (`hop_snap_at = ram_change + HOP_DELAY + HOP_HOLD +
INTER_HOP + HOP_HOLD + POST_HOP_WAIT = ram_change + 119`) is exactly
when the HUD has updated to L4R1 under DIP-cheat-driven advance.

That hunt was originally written to find the *visual round counter byte*
— bytes that match `(1,1,2,2,3,3,4,4)` for level or `(1,4,1,4,1,4,1,4)`
for round-within-level. **No byte matched those patterns.** The HUD
digits aren't stored as integers in RAM (they're tile indices, or
computed on the fly from `0x0081`). But the *screenshot* at the snap
moment unambiguously showed L4R1 — so even though we never decoded "what
byte represents the visual round," we proved the timing window
empirically.

#### Why the earlier walker was failing

Two compounding bugs that obscured the +119 window:

1. **Settle-delay misuse.** I was waiting a settle delay (tried
   0 / 30 / 60 / 90 / 180 frames) *before* starting the dance, then
   doing a 60-frame dance on top. Total snap moment landed at
   `ram_change + 90` through `+240`. Short timings caught L3R4 (HUD
   hadn't updated yet); long timings caught L1R1 (Demo AI had played
   L4R1 fast, died, and the game had restarted to attract mode). The
   `+119` window is *narrow* — Demo AI in L4R1 specifically dies within
   ~150-200 frames, so anything past `+200` is gone.
2. **Boot Start press never released.** This one was sneaky:
   ```lua
   if frame >= 700 and frame < 740 then set("1 Player Start", true) end
   ```
   No else branch — `set()` only fires when the condition is true, so
   Start *stays asserted* after frame 740 forever. Caused subtle ROM
   state divergence vs [`qbert_round_byte_hunt.lua`](../../scripts/research/mame/qbert_round_byte_hunt.lua)
   which used the proper conditional-set pattern (sets to 0 outside the
   window). Once I matched that, behavior aligned.

Compare round_byte_hunt's pattern (correct):

```lua
fields["1 Player Start"]:set_value(frame >= 700 and frame < 760 and 1 or 0)
```

vs my walker's broken version:

```lua
if frame >= 700 and frame < 740 then set("1 Player Start", true) end
-- (no else branch — held true forever after frame 740)
```

#### The fix

Time the dance to *end* at `+119` (matching `qbert_round_shots`'s
`hop_snap_at`), explicit Start release, no settle delay:

```
ram-change frame X     → snap("state0")        ← apex pristine, score 0
X + 30                 → DR hop input on
X + 42                 → DR hop input off
X + 77                 → UL hop input on
X + 89                 → UL hop input off
X + 119                → snap("state1")        ← HUD = LEVEL 4 ROUND 1
```

Both snaps captured with `pos=0xB8` (apex) confirmed via the position
byte found in Phase A. Score at state-1 snap = 30 (apex flipped from
green→state-1 yellow + (1,1) flipped). Sampled colors:

| | hex | name |
|---|---|---|
| state 0 | `#21B931` | green |
| state 1 | `#EFDE77` | golden yellow ⭐ NEW |
| state 2 | `#0046DE` | blue |

Three distinct values → 2-step round confirmed via
`sample_cube_colors.py`. Doc updated; ⚠️ markers gone.

#### What was almost but not quite the right idea

A few false starts worth noting so we don't repeat them:

- **Wait for "stable apex" before snapping.** I added a counter that
  required `pos == 0xB8` for 30 consecutive frames before starting the
  dance. The intent was "let Demo AI's queued actions settle." In
  practice Demo AI in L4R1 might never give us 30 stable frames at
  apex, or by the time it does we're past the +119 window.
- **`TARGET_ROUND = 17` instead of 16.** When `round_num=16` HUD showed
  L3R4, I assumed the script was off-by-one and tried bumping to 17.
  That gave L1R1 (game restarted). The off-by-one suspicion was
  reasonable but wrong — `round_num=16` *is* L4R1 ram-wise; it's just
  that the HUD lags the ram by ~119 frames.
- **Decode the position byte to (row, col).** Spent some time trying
  to figure out what `0x0D64`'s values mean (apex=`0xB8`, (1,1)=`0xF5`,
  (2,1)=`0xB2`, etc — not a clean encoding). Turned out we don't need
  to decode it for the L4R1 capture; uniqueness alone is enough.
- **`0x0D64` as a unique cube identifier (Phase C original plan).**
  Phase A's strict-uniqueness test only visited 5 cubes — `qbert_pos_calibrate.lua`
  later revealed collisions: `(6,0)=(6,2)=(6,4)=(6,6)=0x26`. The byte
  encodes something like row-Y, not unique cube ID.
- **16-bit X/Y key (`0x0D58`, `0x0D59`) as unique identifier.** Sprite
  X/Y are unique per cube *at rest* but have animation transients —
  apex registered with both `0x257D` and `0x917D` keys during a single
  run. Bot's learned table fragments cubes across keys.
- **Dynamic-learned `pos_to_cube` table.** Walker started with apex
  seeded and learned other cubes via dead-reckoning. Early
  registrations (during the snap dance) are correct, but later hops
  with edge no-ops or enemy interference register wrong (cube X
  mapped to key Y, but actual cube at key Y was something else).
  Table corruption propagates.
- **`cubes_fully >= 28` as round-clear heuristic.** Bot's view of
  visit counts diverges from ROM's view due to drift. Bot reports
  "all 28 visited 2x" while ROM has some cubes still at state-0.
  Palette-write-tap is the only reliable round-clear signal.

#### NVRAM persistence — the silent non-determinism gotcha

After the architecture pivot to DIP-cheat-driven walker, the multi-round
script worked once, then started capturing wrong rounds on subsequent
runs. Same script, same MAME version, same ROM, *different output*.

Cause: MAME persists `~/.mame/nvram/qbert/nvram` across runs (high-score
table, coin counter — `qbert.cfg` shows `coins index="0" number="58"`
after a few runs). The persisted state subtly shifts demo-mode timing
on subsequent boots.

Always preface MAME research scripts with:

```bash
rm -f ~/.mame/nvram/qbert/nvram ~/.mame/cfg/qbert.cfg
```

Or pass `-nvram_directory /tmp/empty_nvram` to MAME for a per-run
ephemeral location. Cleared NVRAM = fully deterministic walker output
across runs.

### Useful artifacts in repo

- [`scripts/research/mame/qbert_position_hunt.lua`](../../scripts/research/mame/qbert_position_hunt.lua) — Phase A position-byte tool (5-cube subset)
- [`scripts/research/mame/qbert_pos_calibrate.lua`](../../scripts/research/mame/qbert_pos_calibrate.lua) — full 28-cube calibration walk (revealed `0x0D64` collisions and X/Y transients)
- [`scripts/research/mame/qbert_walker.lua`](../../scripts/research/mame/qbert_walker.lua) — final multi-round walker (DIP-cheat-driven, 15/16 rounds clean)
- [`scripts/research/mame/qbert_round_byte_hunt.lua`](../../scripts/research/mame/qbert_round_byte_hunt.lua) — diagnostic that proved the +119 timing
- [`scripts/research/mame/qbert_l4r1_walker.lua`](../../scripts/research/mame/qbert_l4r1_walker.lua) — standalone L4R1 capture (cheat-advance + fixed-timing dance)
- [`scripts/research/mame/walker_snaps.txt`](../../scripts/research/mame/walker_snaps.txt) — snap log per run (idx → round/label/frame)
- [`docs/investigations/qbert_walker_run.log`](../investigations/qbert_walker_run.log) — multi-round walker run log
- [`scripts/research/mame/round_byte_hunt.txt`](../../scripts/research/mame/round_byte_hunt.txt), [`l4r1_walker.txt`](../../scripts/research/mame/l4r1_walker.txt), [`position_hunt.txt`](../../scripts/research/mame/position_hunt.txt), [`pos_calibrate.txt`](../../scripts/research/mame/pos_calibrate.txt) — log artifacts

### Things that turned out to be dead ends

- **DIP runtime toggle** doesn't work — DIP switches are sampled at
  boot/reset only. `qbert_capture_v2.lua`'s cheat-toggle approach was
  silently a no-op.
- **`qbert_bot.lua`'s `cubes_done >= 28` round-clear heuristic** is
  internal narrative, not ROM truth — the bot has *never* actually
  advanced ROM rounds. `qbert_bot_run.log` shows `[palette] unchanged`
  for all 16 supposed round-clears. Bot's "ROUND COMPLETE L4R1" lines
  meant "bot's internal counter hit 28", not "ROM transitioned to L4R2".
- **Burst-snap during L4R1** (snap every 4 frames for 200-400 frames):
  with no joystick stimulation, Demo AI is frozen at apex; with
  stimulation, ROM transitions to attract mode within ~80 frames.
  Catching the L4R1 visual window via burst is unreliable.

### What this enables

L4R1 closure unblocks the per-round palette swap work for the WF Q✱bert
port — `wflevels/qbert_practice/gen_cube.py` and
`wflevels/qbert_practice/blender_create_qbert.py` now have a complete
table to consume. Phase E (WF parity) is the natural follow-up.
