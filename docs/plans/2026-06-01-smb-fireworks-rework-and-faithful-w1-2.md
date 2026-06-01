# Plan: SMB radial-burst fireworks + faithful underground W1-2

**Date:** 2026-06-01
**Status:** Part A in progress

## Context

The W1-1 flagpole celebration ([Phases 1–3](2026-05-31-smb-flagpole-celebration.md)) is done. This
pass takes the remaining banked celebration follow-ups **except the fanfare SFX**:

1. **Radial spark-burst fireworks** (the debris idiom) replacing the three flashing slabs, with the
   **faithful firework count = remaining-timer last digit** — 1, 3, or 6 → that many bursts; any
   other digit → none (the real SMB rule).
2. **Positioning fixes**: tighten the castle flag onto its rooftop pole; lift the fireworks clear
   into open sky so they don't overlap the flag.
3. **Faithful underground W1-2** (full build): the 256-tile underground level — dark bg + brick
   ceiling, coins, ?-blocks, bricks, pipes, Goombas/Koopas/Piranhas, the bonus coin room, decorative
   warp-zone — plus the W1-1 celebration ending (with the new fireworks). Source of truth:
   [`docs/smb-level-layouts.md`](../smb-level-layouts.md) §1-2 (lines 137-188); faithful = an exact
   copy of the original layout.

Two parts: **Part A** reworks fireworks + positioning on W1-1 (where the celebration is fully built
and verifiable); **Part B** builds faithful W1-2 and carries the now-final celebration over.

---

## Part A — W1-1 radial-burst fireworks + count + positioning

Reuses the proven **debris idiom** ([`blender_create_smb.py:2316-2418`](../../wflevels/smb_w1_1/blender_create_smb.py)):
a `generator`-class Physics template parked off-map, thrown by a parent `generator` actor, fanned
outward via `ACTOR_INDEX`, self-despawning. zForth notes (carry forward): bitwise and/or are
`&`/`|` (no `and`/`or` word — see [[reference_zforth_and_or_ampersand]]); `%` casts to int; `/` is
float. Use **only LOCAL_SYSTEM mailboxes (3000+)** on the template (a LOCAL_USER write on a
default-sized template overflows its array → crash); **no Random Displacement** (`Scalar::Random()`
asserts). `Generation Rate` cap is 10/s.

### A1. `spark_template` (new, modeled on `_make_debris_template`)
- Small bright cube (~0.25 m), `generator` class, Physics, low mass, `Falling Acceleration` ~10,
  zero drag/friction, parked off-map. Reuse the celebration mats (yellow/white/orange).
- `SPARK_SCRIPT` (LOCAL_SYSTEM only):
  - Fan velocity into a **radial 2-D spread (XZ plane = the side-view plane)** by `ACTOR_INDEX`: an
    if-ladder mapping `idx % N` → ~6–8 `(XSPEED, ZSPEED)` direction pairs (write `INDEXOF_XSPEED`
    3018 + `INDEXOF_ZSPEED` 3020 each tick). The generator's upward `Object Z Velocity` + gravity
    give the arc; the per-spark fan makes it burst outward.
  - **Despawn** when it falls back below a sky threshold (`Z_POS < origin_Z − ~4` → `ALIVE=0`),
    giving ~0.6–1.0 s life — the firework "sparkle then fade".

### A2. Six firework generators (replace the 3 slabs at `blender_create_smb.py:1850-1878`)
- Each: `generator` class, Anchored, `Object To Throw='spark_template'`, `Generation Rate=10`,
  `Object Z Velocity` ~7 (up), X/Y velocity 0; `Activation MailBox = SMB_FIREWORK_n` (n=0..5).
- **Positions** in an arc in open sky, clear of the flag: X spread ~316..324, **Z ~9..11** (above
  the raised flag at 7.5 and above the castle roof at 4.5).
- Per-generator script (self-contained, evolves the current window idiom):
  ```
  0 INDEXOF_SMB_FIREWORK_n write-mailbox            ( default off )
  INDEXOF_SMB_CELEBRATE read-mailbox if
    n INDEXOF_SMB_FIREWORK_COUNT read-mailbox < if  ( this burst enabled? )
      INDEXOF_TIME read-mailbox INDEXOF_SMB_CELEBRATE_START read-mailbox -   ( elapsed )
      dup t0 > swap t1 < & if 1 INDEXOF_SMB_FIREWORK_n write-mailbox then    ( pulse generator )
    then
  then
  ```
  The generator's engine spawn-check runs before the script (per the brick comment), so it reads the
  pulsed `Activation MailBox` and throws a burst during the window. Windows staggered:
  `t_n = 2.0 + n*0.35` (2.0…3.75), each ~0.5 s → last ends ~4.25.

### A3. Count latch (faithful 1/3/6) — Player bonus block (`~1278`, EOL_LATCH edge)
Runs once at celebration start, **before** the Director drains the timer (Player runs first):
```
INDEXOF_HUD_TIMER read-mailbox 10 %        ( last digit, int via % )
dup 1 = if drop 1 else dup 3 = if drop 3 else dup 6 = if drop 6 else drop 0 then then then
INDEXOF_SMB_FIREWORK_COUNT write-mailbox
```
`n < count` enables bursts `0..count-1`, so count=1/3/6 lights 1/3/6 bursts; other digits → 0.

### A4. Positioning fixes
- **Castle flag onto pole** (`~1808-1839`): the flag raises to Z=7.5 at X=318.6 but the
  `castle_pole` top is Z=7.5 at X=319.5 — a 0.9 m horizontal gap. Move the flag's X so its edge meets
  the pole, and set its raised `CFLAG_TOP_Z` so the flag *top* (not center) reaches the pole top.
- **Fireworks clear**: handled by A2's Z~9–11 sky placement (was 6.0–6.7, below/overlapping the flag).
- **Director finale** (`~216`): extend `4.2 >` → `4.5 >` so it fires after the last burst.

### A5. New mailboxes (`mailbox.inc`, `MAILBOXENTRY` rows + Comment)
`SMB_FIREWORK_3` (1868), `SMB_FIREWORK_4` (1869), `SMB_FIREWORK_5` (1870),
`SMB_FIREWORK_COUNT` (1871). (Per convention; the `INDEXOF_` prefix is still wanted gone — see
[[feedback_indexof_prefix_wanted_gone]].)

---

## Part B — Faithful underground W1-2

W1-2 today ([`wflevels/smb_w1_2/blender_create_smb_w1_2.py`](../../wflevels/smb_w1_2/blender_create_smb_w1_2.py),
17 actors) is a bare 36 m corridor: floor + player + flagpole + advance trigger + near-black matte +
a 5-tile brick ceiling. It already forks the W1-1 texture/ground/mario helpers but **none** of the
gameplay builders.

### B0. Shared module `wflevels/smb_common.py`
Rather than copy ~1500 lines (builders + the 700-line Player script + Director + celebration) into a
second file and risk drift — especially right after Part A changes the celebration — **extract the
shared machinery into `wflevels/smb_common.py`** imported by both level scripts:
- Texture/material helpers, `add_box`/`add_statplat`/`_add_textured_box`, ground builder.
- Entity builders: goomba, koopa, coin template + dispenser, powerup block/template, brick + debris,
  popup, qblock, pipe, piranha.
- **Parameterized script-generators**: `player_script(cfg)`, `director_script(cfg)`,
  `celebration(cfg)` (castle/flags/Mario-walk/fireworks) taking per-level config (FLAGPOLE_X, camera
  clamps, spawn, theme colours, layout arrays).
- **Risk mitigation:** refactor W1-1 to import it and re-verify W1-1 is unchanged (`verify_smb_scroll`
  + `verify_smb_scoring` green; re-capture the celebration matches). Done **after** Part A lands +
  is verified, so the module captures the final fireworks — they then propagate to W1-2 for free.

### B1. W1-2 geometry + underground theme
- Widen to **256 tiles** (`GROUND_X1`, room bounds, camera clamps); flagpole at col ~248.
- Underground theme: dark/teal matte (already near-black), full **brick ceiling** spanning the level,
  blue-grey brick palette, the surface→underground entry pipe (decorative).
- Ground with the faithful gaps; **lifts deferred** (need `platform.oas`) — replace the section-4
  ascending/descending lifts with **static brick platforms** so the level stays traversable; note the
  deviation + a follow-up.

### B2. Populate per `docs/smb-level-layouts.md` §1-2 (faithful, left→right)
| Section | cols | Contents |
|---|---|---|
| 1 Entry | 0-40 | 2 Goombas; row of 5 ?-blocks (left=mushroom/flower, rest=coins); block tower + 1 Goomba; brick w/ 10-coin block |
| 2 Mid | 40-120 | brick formations; hidden-Starman brick; 2 Green Koopas; cluster of 5 Goombas + 1 Koopa; hidden-powerup brick; 10-coin brick; gap; hidden 1-Up |
| 3 Pipes | 120-180 | 2 Goombas; 3 Piranha pipes (~130/145/160); pipe 1 → bonus coin room |
| 4 Lifts/exit | 180-230 | gaps + ground platforms; half-pyramid + 2 Goombas; **static platforms (lifts deferred)**; Red Koopa + bricks; hidden-powerup brick |
| 5 Exit | 230-256 | surface section; Piranha pipe; hard-block staircase; flagpole col ~248 |
- **Bonus coin room** (2nd room, ~27 coins + 10-coin block): copy the W1-1 §14 coin-room idiom (entry/exit pipes + warp).
- **Warp zone** (cols ~210): **decorative only** — the three pipes + a "WELCOME TO WARP ZONE" sign;
  non-functional (worlds 2-1/3-1/4-1 don't exist).
- Totals to match the doc: 14 Goombas, 3 Green + 1 Red Koopa, 4 Piranhas, 68 coins, 3 powerups,
  1 Starman, 1 1-Up.
- Add any W1-2-specific mailboxes reusing W1-1 patterns / named `MAILBOXENTRY` constants.

### B3. Celebration ending on W1-2
Wire `celebration(cfg)` from B0 at the W1-2 flagpole: castle + pole/castle flags + Mario walk/hide +
the new radial fireworks + Director timer→score sequencer, exactly as W1-1. W1-2's flagpole advance
keeps looping `LEVEL_TO_RUN` back to W1-1.

---

## Critical files

| File | Change |
|---|---|
| [`wfsource/source/mailbox/mailbox.inc`](../../wfsource/source/mailbox/mailbox.inc) | Part A: + `SMB_FIREWORK_3/4/5` (1868-70), `SMB_FIREWORK_COUNT` (1871); Part B: any W1-2 enemy/pipe mailboxes |
| [`wflevels/smb_w1_1/blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py) | Part A: `spark_template`, 6 firework generators (replace 3 slabs), count latch, flag/finale tweaks; B0: import `smb_common` |
| `wflevels/smb_common.py` (new) | B0: shared builders + parameterized player/director/celebration script-generators |
| [`wflevels/smb_w1_2/blender_create_smb_w1_2.py`](../../wflevels/smb_w1_2/blender_create_smb_w1_2.py) | B1-B3: import `smb_common`; 256-tile underground layout, theme, populate, celebration |
| `engine/wf_game` | rebuilt (mailbox.inc → `touch engine/stubs/scripting_stub.cc && task build`) |
| `wflevels/smb_w1_1*.iff`, `wflevels/smb_w1_2*.iff`, `wfsource/source/game/cd.iff` | rebuilt artifacts (`build_level_binary.sh` + `task build-cd-iff`) |

## Phasing (commit per phase)

- **A** — W1-1 fireworks rework + count + positioning. Verify, commit.
- **B0** — extract `smb_common.py`; W1-1 imports it; re-verify W1-1 unchanged. Commit.
- **B1** — W1-2 geometry + underground theme. Commit.
- **B2** — W1-2 populated (blocks/coins/items, enemies, pipes, bonus room, warp decor). Commit (may split enemies vs items).
- **B3** — W1-2 celebration ending. Commit.

## Verification

- **Build pipeline** each level change: `blender --background --python <script>` →
  `bash wftools/wf_blender/build_level_binary.sh <level>` → `task build-cd-iff`.
- **Part A fireworks** (W1-1): the celebration capture (`/tmp/verify_celebration2.py`) — **settle the
  bungee camera** (hold at 313, velocities zeroed ~2.6 s) before firing `SMB_CELEBRATE`. Drive
  `HUD_TIMER` to a value ending in 1/3/6 and confirm 1/3/6 distinct bursts pop in open sky above the
  castle, clear of the flag; confirm a non-{1,3,6} digit → no fireworks. Screenshots + mp4. Watch the
  actor pool (sparks are temporary objects) — if it OOMs, check `git diff HEAD` on `*.iff.txt`
  before bumping pool sizes.
- **Regressions** stay green throughout: `verify_smb_scroll`, `verify_smb_scoring` (and re-capture the
  celebration after B0 to prove the refactor changed nothing).
- **W1-2**: boot it (cd.iff index 1 / `-L smb_w1_2-standalone.iff`), `--debug-print-actors` to confirm
  the actor inventory matches the doc totals; bridge-walk/teleport Mario through the sections
  (screenshots of entry, pipes, bonus room, staircase, flagpole + celebration); confirm the
  W1-1→W1-2→W1-1 advance loop still works.
- Screenshots → `tests/screenshots/`, mp4 → `tests/recordings/`.

## Risks / gotchas
- **Spark pool**: up to 6 bursts × ~5 sparks staggered — temporary-object budget. Verify, don't blind-bump.
- **Lifts deferred** (`platform.oas`): section-4 lifts + the lift-reached warp zone become static/decorative; flagged as the one faithful gap + a follow-up.
- **B0 refactor risk** on W1-1: mitigated by re-running regressions + re-capturing the celebration; do it after Part A is locked.
- zForth `&`/`|`/`%` rules; LOCAL_SYSTEM-only templates; bungee-settle for capture; Blender is the golden source (every shipped `.lev` from a Blender export).

## Follow-ups (not this pass)
- Fanfare SFX (audio — verify on the other machine) — explicitly excluded now.
- Real moving-platform **lifts** (`platform.oas`) + functional **warp zone** once worlds 2-1/3-1/4-1 exist.
- 3-D (out-of-plane) spark spread if the 2-D burst reads flat.
