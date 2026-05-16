# Capturing Q✱bert's per-round cube palette — the path to 16×3 ROM-grounded colors

**Date:** 2026-05-08

This is the trip report. We needed the exact RGB values for every cube top
state (0/1/2) across all 16 of Q✱bert's rounds (L1R1–L4R4), to drive the
WF port's per-round palette swap in
[`wflevels/qbert_practice/`](../../wflevels/qbert_practice/). Final result:
all 48 cube-top color cells filled in
[`docs/investigations/qbert_cube_face_colors.md`](qbert_cube_face_colors.md);
side-face colors for all 16 rounds; a deterministic multi-round walker that
captures the canonical state-0 / state-1 frames per round in a single
run; a standalone walker that closes the L4R1 edge case.

The straight-line story is simple. The road wasn't.

---

## The problem

Our pre-2026-05-04 cube palette was based on JPG eyeball samples of
arcade-museum.com screenshots. JPEG compression drifts the colors —
`#52A9A3` "teal" was actually `#5646EF` purple. We needed ROM-authoritative
RGB, the exact bytes Gottlieb's hardware writes to the framebuffer.

---

## Step 1 — The ROM is the source of truth

[Plan 2026-05-04-qbert-cube-palette.md](../plans/2026-05-04-qbert-cube-palette.md)
established the rule: lossless MAME PNGs of the vendored
`assets/arcade-roms/qbert.zip` ROM are the only authoritative source.
JPEGs lie. arcade-museum.com lies. We sample pixels from a 240×256
framebuffer dump, period.

For L1R1 this was straightforward. Boot MAME with the ROM, capture a
gameplay screenshot, sample three points per cube:

- **Top face:** `(120, 56)` — apex cube top diamond center
- **Lit face:** `(107, 65)` — left parallelogram
- **Shadow face:** `(135, 65)` — right parallelogram

Histogram of the screenshot's 13 unique colors gave us the L1R1 palette
directly: top `#5646EF` purple, lit `#56A999` teal, shadow `#314646`
dark teal, target (state-2) `#DEDE00` yellow.

Insight from the user that pinned the architecture: the arcade fakes 3D
via two pre-shaded side colors (lit + shadow) but our WF engine has
real geometry and dynamic lighting, so we use the LIT teal as the cube
material color and let the engine darken shadowed faces naturally.

---

## Step 2 — Advancing through rounds: the DIP cheat

L1 is one round palette across all four sub-rounds (R1–R4 differ only in
enemies). L2/L3/L4 each have four DISTINCT palettes (R1–R4 within a level
differ in cube colors). To capture all 16, we needed to make ROM advance
through them — one MAME run can't sit at L1R1 forever.

The Q✱bert ROM has a documented DIP switch:
`"Demo Mode (Unlim Lives, Start=Adv (Cheat)"` — when active, every
1P-Start press advances to the next round. Demo Mode also makes the ROM
auto-play (Demo AI hops Q✱bert), and Unlim Lives prevents game-over.

[`scripts/research/mame/qbert_round_shots.lua`](../../scripts/research/mame/qbert_round_shots.lua)
is the script that uses this:

1. Boot, set the cheat DIP to 1.
2. Insert coin + Start at boot windows.
3. Watch RAM `0x0081` (a counter that increments on each Start-press +
   each Demo-AI round-clear).
4. Each time `0x0081` changes, snap state-0 (apex pristine), inject a
   2-hop dance (DR to (1,1), UL back to apex) over 119 frames, snap
   state-1 (cube (1,1) flipped exactly once, Q✱bert clear of (137,80)),
   then press Start to advance to the next round.

This produced 15 of 16 visually-correct round captures
([`qbert_hop_L*R*.png`](mame-screenshots/) under `mame-screenshots/`),
with the file→visual-round mapping off-by-one due to L2/L3/L4 transition
zoom screens consuming snap slots. The off-by-one is documented in
[`sample_cube_colors.py`'s `FILE_MAP`](../../scripts/research/mame/sample_cube_colors.py).

Sampling the post-hop snaps at `(137, 80)` gave state-1 for 2-step rounds
(L2/L4) and state-2 for 1-step rounds (L1/L3). The HUD's "CHANGE TO"
indicator at `(40, 55)` always gives state-2 directly.

L4R1 stayed unknown. ⚠️

---

## Step 3 — L4R1: the +119 frame window

L4R1 was the holdout. Demo AI in L4R1 plays aggressively — Q✱bert is off
the pyramid within a few hundred frames, often dying. By the time
`qbert_round_shots.lua`'s 119-frame snap window closed, Demo AI had
already hopped many cubes; the (137, 80) sample showed multi-state
contamination.

The breakthrough came from
[`scripts/research/mame/qbert_round_byte_hunt.lua`](../../scripts/research/mame/qbert_round_byte_hunt.lua).
That script was originally written to hunt for the visual-round counter
byte (which doesn't exist in usable form — see footnote\^[#dead-end-2]).
It snapshotted RAM **and a screenshot** at the same `+119`-frame moment
for 8 known visual rounds. Looking at snap 6 of that run — visually
showing `LEVEL 4 ROUND 1` with score 520 — proved that **the HUD reliably
updates to L4R1 by frame `ram_change + 119`** under DIP-cheat advance.

The RAM/visual relationship is subtle. When `ram[0x0081]` changes from
`0x12` to `0x13`, the ROM has *internally* entered round 16 (= L4R1 per
the file_map), but the on-screen HUD still shows L3R4 because the L4
zoom transition animation hasn't completed. At about 90–120 frames in,
the transition completes, the HUD updates, and Q✱bert is at apex with
all cubes in L4R1's state-0 green.

[`scripts/research/mame/qbert_l4r1_walker.lua`](../../scripts/research/mame/qbert_l4r1_walker.lua)
combines this insight with the 2-hop dance, exiting after L4R1:

```
ram-change frame X     → snap("state0")        ← apex, score 0
X + 30                 → DR hop input on
X + 42                 → DR hop input off
X + 77                 → UL hop input on
X + 89                 → UL hop input off
X + 119                → snap("state1")        ← HUD = LEVEL 4 ROUND 1
```

Position byte at `0x0D64` reads `0xB8` at both snaps, confirming Q✱bert
was at apex. Score at state-1 is 30 (apex flipped + (1,1) flipped, two
cubes worth at L4's 25-points-per-cube rate, plus a small bonus).

Sampled colors:

| | hex | name |
|---|---|---|
| state 0 | `#21B931` | green |
| state 1 | **`#EFDE77`** | golden yellow ⭐ NEW |
| state 2 | `#0046DE` | blue |

Three distinct values → 2-step round confirmed. Doc updated. 16/16 rounds
complete. Time elapsed from "L4R1 unknown ⚠️" to "L4R1 captured": ~30 minutes
once the +119 timing was understood (after considerably more than 30 minutes
of dead ends — see footnotes).

---

## Step 4 — Multi-round walker: one run, all 16 rounds

The L4R1 closure unblocked
[plan 2026-05-08-qbert-walker-rom-grounded.md](../plans/2026-05-08-qbert-walker-rom-grounded.md),
which set out to build a unified MAME-side walker for the regression
suite. Same protocol on both engines (MAME for arcade reference, WF for
port output), pixel-diff at sample points = palette regression test.

[`scripts/research/mame/qbert_walker.lua`](../../scripts/research/mame/qbert_walker.lua)
is the result. It's structurally `qbert_round_byte_hunt.lua` plus the
state-0/state-1 snap pair at every round, skipping the three transition
screens (L2/L3/L4 zoom-ins which have no usable cube state).

Per-round sample at `(137, 80)` after a single 200-second MAME run:

```
L1R1 state1=#DEDE00 (= state-2, 1-step round)  ✓ matches doc
L1R2 state1=#0046DE (= state-2, 1-step)        ✓
L1R3 state1=#464646                            ✓
L1R4 state1=#A9B910                            ✓
L2R1 state1=#EFDE77 (intermediate, 2-step)     ✓
L2R2 state1=#0066EF                            ✓
L2R3 state1=#5646EF                            ✓
L2R4 state1=#0046EF                            ✓
L3R1 state1=#003199                            ✓
L3R2 state1=#B9CECE                            ✓
L3R3 state1=#EFDE77                            ✓
L3R4 state1=#5646EF                            ✓
L4R1 state1=#21B931  ← state-0 leak (multi-round transition timing)
L4R2 state1=#FF6666                            ✓
L4R3 state1=#FF6666                            ✓
L4R4 state1=#0066EF                            ✓
```

15/16 of the multi-round walker's state-1 samples match the doc's
canonical values exactly. L4R1 in multi-round mode hits a known edge
case: by the time the L4 transition zoom completes, Demo AI is already
mid-play and our snap dance overlaps with its hops. The standalone
[`qbert_l4r1_walker.lua`](../../scripts/research/mame/qbert_l4r1_walker.lua)
remains the canonical L4R1 capture path because it exits after L4R1 and
its dance perfectly aligns with the post-transition window.

---

## Step 5 — NVRAM determinism (the silent-non-determinism gotcha)

Hours of debugging in Phase C kept hitting "this script worked yesterday
but not today, same code, same MAME, same ROM." The walker would
sometimes capture L4R1 cleanly and sometimes capture L1R1 with score 50
where L4R1 should be.

Root cause: **MAME persists `~/.mame/nvram/qbert/nvram` across runs.**
The persisted state — high-score table, coin counter, DIP defaults —
subtly shifts demo-mode timing. We watched the coin counter accumulate
across runs:

```xml
<system name="qbert">
    <counters>
        <coins index="0" number="58" />
    </counters>
</system>
```

After enough boots, the ROM's internal state diverged enough that demo
advancement frames shifted by tens of frames. Walker scripts that worked
the first time stopped working on the third or fourth run.

Fix is one line at the top of every MAME research command:

```bash
rm -f ~/.mame/nvram/qbert/nvram ~/.mame/cfg/qbert.cfg
```

(Or pass `-nvram_directory /tmp/empty_nvram` for a per-run ephemeral
location.) After the clear, walker output is bit-for-bit deterministic
across runs.

This applies to **every** MAME-Q✱bert research script in this repo. If
you're debugging a script that "stopped working," check NVRAM first.

---

## Final state

- [`docs/investigations/qbert_cube_face_colors.md`](qbert_cube_face_colors.md):
  16 rounds × 3 cube-top states + lit/shadow side colors. No `unknown ⚠️`
  markers. `grep -ni "unknown\|⚠️\|unconfirmed"` returns zero results.
- [`scripts/research/mame/qbert_walker.lua`](../../scripts/research/mame/qbert_walker.lua):
  multi-round walker, DIP-cheat-driven, deterministic. Captures 32 PNGs
  (state-0 + state-1 per round) in a single ~95-second `-speed 10` run.
- [`scripts/research/mame/qbert_l4r1_walker.lua`](../../scripts/research/mame/qbert_l4r1_walker.lua):
  standalone L4R1 capture for the multi-round edge case.
- [`scripts/research/mame/sample_cube_colors.py`](../../scripts/research/mame/sample_cube_colors.py):
  reads each PNG at `(120, 56)` apex top, `(137, 80)` cube (1,1), and
  `(40, 55)` HUD CHANGE TO indicator; classifies 1-step vs 2-step rounds
  by comparing post-hop sample to state-2 target.
- [`scripts/research/mame/qbert_round_byte_hunt.lua`](../../scripts/research/mame/qbert_round_byte_hunt.lua):
  diagnostic that proved the +119-frame timing.

Phase E (WF-side parity) is now well-scoped — the walker protocol is
fully defined: snap state-0 at apex; force DR; snap state-1 after UL
back; advance round; repeat. The WF autopilot
([`mb[430] AUTOPILOT_ON`](2026-05-05-qbert-autopilot.md)) needs a
`mb[431] CAPTURE_TRIGGER` extension and a debug-bridge `screenshot` op
to emit the same protocol on the WF side. Pixel-diff at the three
sample points against the MAME captures becomes the palette regression
test.

---

<sub>

## Appendix — dead ends, spikes, and side research

The mainline glosses over a long sequence of approaches that didn't
pan out. Documented here so the next person doesn't repeat them.

### <a name="dead-end-1"></a>1. JPG eyeball samples

The pre-2026-05-04 palette in repo claimed L1R1 cube top was `#52A9A3`
("teal") based on arcade-museum.com JPGs. JPEG compression had drifted
the actual `#5646EF` purple by ~150 RGB units across the visible
spectrum. Memory note
[feedback_oracle_mirror_first.md](../../docs/../../.claude/projects/-home-will-WorldFoundry/memory/feedback_oracle_mirror_first.md)
codifies the lesson: "Mirror the oracle first, deviate later." JPGs are
not the oracle. Lossless ROM-rendered PNGs are.

### <a name="dead-end-2"></a>2. The visual-round counter byte that doesn't exist

[`scripts/research/mame/qbert_round_byte_hunt.lua`](../../scripts/research/mame/qbert_round_byte_hunt.lua)
was originally written to find the byte the HUD reads to display
"LEVEL: X ROUND: Y". Strategy: snapshot RAM at known visual rounds
(L1R1, L1R4, L2R1, L2R4, L3R1, L3R4, L4R1, L4R4), then look for bytes
matching the level pattern `(1,1,2,2,3,3,4,4)` or the round-within-level
pattern `(1,4,1,4,1,4,1,4)`. **No byte matched.** The HUD digits aren't
stored as integers; they're tile-render pen indices, possibly computed
on the fly from `ram[0x0081]`. The hunt was a near-miss — but the
*screenshot* at the snap moment incidentally showed `LEVEL 4 ROUND 1`,
which proved the +119 timing window. Side benefit > main goal.

### <a name="dead-end-3"></a>3. Cheat-toggle (`qbert_capture_v2.lua`)

Idea: turn DIP cheat ON to advance to the round we want, then turn it
OFF to suspend Demo AI during the snap window, then turn it back ON to
advance. **Doesn't work**: DIP switches in MAME are sampled at
boot/reset only, not at runtime. Setting the cheat field's value mid-run
is a silent no-op — `fields[CHEAT]:set_value(0)` succeeds, but the ROM
doesn't see it. Three different attempts failed identically before we
realized DIPs aren't runtime-toggleable. See
[`qbert_capture_v2.lua`](../../scripts/research/mame/qbert_capture_v2.lua).

### <a name="dead-end-4"></a>4. `qbert_bot.lua`'s round-clear heuristic

The full Warnsdorff bot at
[`scripts/research/mame/qbert_bot.lua`](../../scripts/research/mame/qbert_bot.lua)
treats `cubes_done >= 28` as the round-complete signal — i.e., "I, the
bot, think I've visited all 28 cubes; therefore the ROM has round-cleared."
This is bot self-narrative, not ROM truth.
[`docs/investigations/qbert_bot_run.log`](qbert_bot_run.log) shows
`[palette] unchanged` for **all 16 supposed round-clears** — the
palette write-tap never fired, meaning the ROM never actually advanced
rounds. The bot was hopping in L1R1 the entire run, claiming victory
after each cycle. The bot's internal `ROUND COMPLETE L4R1` log line is
particularly misleading; it never was on L4R1. The fix path is in the
plan as Phase C.5: drop dead-reckoning, sync `qrow,qcol` from real ROM
position each iteration. Not done because Phase C.5's foundation
collapsed in dead-end #5 below.

### <a name="dead-end-5"></a>5. Position byte hunt — `0x0D64` collisions

[`scripts/research/mame/qbert_position_hunt.lua`](../../scripts/research/mame/qbert_position_hunt.lua)
ran a strict-uniqueness diff: drive Q✱bert through a known sequence of 5
cubes (apex / (1,1) / (2,1) / (3,2) / (1,0)), find bytes whose values
are stable per position and distinct between positions. Found *one*
strict candidate: `0x0D64`, with apex `0xB8`, (1,1) `0xF5`, etc. We
celebrated. Phase A done in ten minutes.

The follow-up
[`scripts/research/mame/qbert_pos_calibrate.lua`](../../scripts/research/mame/qbert_pos_calibrate.lua)
visiting all 28 cubes told the truth: `0x0D64` collides hard. `(6,0)`,
`(6,2)`, `(6,4)`, `(6,6)` all share `0x26`. `(5,0)`, `(5,2)`, `(5,4)`
all share `0x69`. `(3,0)` and `(3,2)` both `0xEF`. The byte appears to
encode something like row-Y-coordinate (or sprite Y for a particular
animation phase), not unique cube ID.

Lesson: a strict-uniqueness test that only visits 5 cubes can pass on
any byte whose value-space happens to differ across those 5. Test the
whole space.

### <a name="dead-end-6"></a>6. 16-bit X/Y sprite key

After `0x0D64` collapsed, we tried combining `0x0D58` (sprite X) and
`0x0D59` (sprite Y) as a 16-bit key. Calibration showed (6,0) had key
`0x391E` and (6,2) had `0x815D` — different! Promising. We rebuilt the
walker around a `pos_to_cube` lookup keyed on the 16-bit value.

Failure mode: **animation transients.** During a single multi-round
run, the bot registered apex with two distinct keys (`0x257D` and
`0x917D`) at different times. Q✱bert's sprite-X shifts by ~12 pixels
between idle and hop animation frames; if we sample during one frame
we get one X, during the next animation frame a different X. The bot's
learned table fragmented apex across keys, then mis-merged distinct
cubes whose keys happened to match between transient states. Drift
returned through a different door.

### <a name="dead-end-7"></a>7. Dynamic-learned `pos_to_cube` with drift correction

We tried this anyway: seed `pos_to_cube[apex_key] = (0,0)`, learn each
new cube via dead-reckoning (issue DR from (0,0), record landed key as
(1,1)), and use the table to override dead-reckoning on subsequent hops
when the lookup says the bot is somewhere unexpected. The
[`drift-correct]` log lines in `qbert_walker_run.log` show dozens of
corrections firing per run — proof the lookup *was* catching errors.

But the early registrations were themselves wrong: the bot thought it
was hopping to (3,1) (dead-reckoned), but the actual hop dropped or
landed at a transient key the bot then registered as (3,1). Subsequent
lookups returned the wrong cube. The table ratcheted into corruption.

Phase C.5 plan calls for an offline calibration walk to build a clean
table BEFORE any drift can happen. Not implemented — it conflicts with
the goal of "boot, no cheat, just work" and would burn ~3000 frames at
boot for the calibration walk during which enemies would spawn and
disrupt the calibration.

### <a name="dead-end-8"></a>8. Burst-snap during L4R1

[`scripts/research/mame/qbert_l4r1_burst.lua`](../../scripts/research/mame/qbert_l4r1_burst.lua)
took a different angle: at L4R1 entry, snap a screenshot every 4 frames
for 1200 frames (20 seconds). Surely *some* of those frames would catch
cube (1,1) in state-1 cleanly?

What we found: with no joystick stimulation, **Demo AI in L4R1 is
frozen at apex**. Q✱bert sits there indefinitely. With stimulation
(injected DR/UL hops), Demo AI activates but ROM transitions to attract
mode within ~80 frames — Q✱bert dies offscreen and the title sequence
takes over.

The "catch L4R1 by spamming screenshots" approach assumes there's *some*
window in which the desired state is on screen. For L4R1 specifically
that window is `+119` ± a handful of frames, after which Demo AI's play
contaminates the sample. Burst sampling can find the window only if
you already know roughly where it is — at which point you don't need
the burst.

### <a name="dead-end-9"></a>9. Stable-apex detection

Variation on the L4R1 capture: wait for `0x0D64 == 0xB8` (apex value)
for 30 consecutive frames before starting the snap dance. Intent: "let
Demo AI's queued actions settle into a stable rest state." Reality:
in L4R1, Demo AI gives us *zero* stable apex frames; Q✱bert is moving
constantly until he dies. The detector waits forever, then ROM transitions
to attract.

### <a name="dead-end-10"></a>10. `TARGET_ROUND = 17`

When `qbert_l4r1_walker.lua` with `TARGET_ROUND = 16` was capturing what
visually appeared to be L3R4, an early hypothesis was that the off-by-one
file mapping documented in `sample_cube_colors.py` extended to round
counting itself — bump TARGET to 17 and see. **Result:** captured L1R1
(game had restarted to attract mode after Demo AI played L4 too quickly).
The off-by-one was real but lived in a different place — it's about
which file index maps to which visual round, not about which `round_num`
value is L4R1. Round 16 IS L4R1 ram-wise; the HUD just lags.

### <a name="dead-end-11"></a>11. Decoding `0x0D64` to (row, col)

The values `apex=0xB8`, `(1,1)=0xF5`, `(2,1)=0xB2`, `(3,2)=0xEF`,
`(1,0)=0x75` looked suspiciously sprite-Y-coordinate-ish, and we spent
some time trying to derive `(row, col)` from the byte arithmetically.
None of the obvious encodings (linear in row, BCD, packed nibbles)
matched. After dead-end #5 confirmed `0x0D64` collides anyway, the
decode question became moot — we just need uniqueness, not
interpretation.

### <a name="dead-end-12"></a>12. The "flat" rounds aren't really flat

L2R4 and L4R2 are documented as "flat" rounds in
[`sample_cube_colors.py`](../../scripts/research/mame/sample_cube_colors.py)
because the cubes appear without visible side faces — top diamond
floating against black background. The original doc table marked their
side colors as `flat | flat`.

The user's correction: they're not special "no-side" cubes; the side
faces exist and are simply rendered black (`#000000`), the same as the
playfield background. For the WF port, model them as normal cubes with
side faces of `#000000`. No special geometry needed. Doc updated to
`#000000 black | #000000 black`.

### Things that turned out to be the right idea

(Listed for symmetry — these are the small wins that cumulatively
mainlined the path.)

- Vendoring the ROM (`assets/arcade-roms/qbert.zip`,
  `assets/arcade-roms/votrsc01a.7z`) so MAME runs are reproducible.
- DIP-cheat for round advance — the only mechanism that reliably
  progresses ROM through all 16 visual rounds.
- Pixel-sampling at fixed coordinates `(120, 56)`, `(137, 80)`,
  `(40, 55)` rather than chasing color-region detection. The ROM
  framebuffer always renders cubes at the same screen positions.
- Palette write-tap on `0x5000–0x501F` for round-transition detection.
  Threshold ≥32 writes since last round = ROM rewrote palette = round
  cleared. Fully reliable. Not used in the final L4R1 capture (DIP cheat
  handles advancement) but central to Phase B and the future
  ROM-grounded bot if anyone revisits Phase C.5.
- The +119-frame timing window. A constant whose value falls out of
  `qbert_round_shots.lua`'s parameters and proves to be load-bearing
  for L4R1 specifically.
- Clearing NVRAM before each run. Embarrassingly simple, retroactively
  obvious, missed for hours.

</sub>
