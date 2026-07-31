# Breakable Bricks — SMB World 1-1

> On approval, the canonical copy of this plan is authored at
> `docs/plans/2026-05-26-smb-breakable-bricks.md` and committed **with** the code
> (per the project plan-workflow convention). This file is the plan-mode artifact.

## Context

The SMB level (`wflevels/smb_w1_1/`) has `?`-blocks (coin generators), a one-shot
mushroom block, pipes, enemies, a flagpole and a pipe-warp coin room — but **no
breakable bricks**, the single most iconic SMB block. The just-landed
power-up state machine (`16503788`) added `SMB_MARIO_STATE` (0=Small / 1=Super),
which is exactly the gate breakable bricks need: **Super Mario shatters a brick
from below; Small Mario only bumps it.** This plan adds that mechanic and lays out
a faithful World 1-1 brick row.

User decisions (confirmed): **4-fragment debris shatter**, **recreate the 1-1 brick
layout** (brick row interleaved with the existing `?`-blocks + a hidden-item brick),
and **animate a small bump** when Small Mario hits a brick.

Nothing here needs new engine C++ or new OAS fields — it is composition + Forth on
top of proven primitives (the `?`-block generator pattern, hit-from-below collision
mailboxes, `ALIVE=0` despawn). The golden source is the procedural builder
`wflevels/smb_w1_1/blender_create_smb.py`; the `.lev`/`.iff` are generated, never
hand-edited.

## Target layout (height 4 = `BLOCK_Z` 6.75; `T`=1.5, blocks 1 tile wide, centres 1.5 m apart)

```
           hidden mushroom brick (tan after use)
                              ┌─────┐
                              │ Bk* │  X=27.0 (tile 18)
   pipe        B     ?    B   │  B  │   ?     | pit
 ┌──────┐   ┌────┐┌───┐┌────┐ └─────┘ ┌───┐   ▓▓▓▓
 │ 16.5 │   │19.5││ ? ││22.5│ │24.0 │ │ ? │   ▓▓▓▓
 │  ..  │   │ Bk ││21 ││ Bk │ │ Bk  │ │25.│   ▓▓▓▓
 │ 19.5 │   └────┘└───┘└────┘ └─────┘ └───┘   28.5→
 └──────┘    new   qb01  new    new   qb02
  ENTRY      brick_0    brick_1 brick_2
```

- `qblock_01`@21 and `qblock_02`@25.5 stay put (existing coin `?`-blocks).
- New plain bricks `brick_0`@19.5, `brick_1`@22.5, `brick_2`@24.0 interleave into a
  brick/`?` band reading `B ? B B ?`.
- `brick_hidden`@27.0 (one tile higher row optional) is a brick-skinned one-shot
  mushroom dispenser.
- Hard constraints: stay clear of the **entry pipe X[16.5, 19.5]** and the **pit
  X[28.5, 31.5]**. If `brick_0`'s left edge (18.75) feels tight against the pipe,
  shift it to X=20.25.

## Resolved technical risks (from engine source)

1. **Debris must not award score.** `gold`-class is unsafe: the level's `OAD_DIR`
   points at stale fixtures that drop the `Gold Value` field, so a value-0 coin still
   credits +1 (TODO §63; `gold.cc:57`). **Decision:** `debris_template` is a
   `generator`-class physics body that *throws nothing* (Activation MailBox → an
   always-0 slot, so the spawn branch at `generator.cc:72` is never taken) and
   self-despawns from its own script. No `Gold` → no scoring path. Generator-vs-floor
   isn't in `objects.mac` COLTABLE, so fragments fall through the floor off-screen;
   the TTL despawn is the backstop.
2. **Bump animation on an anchored brick.** `EMAILBOX_Z_POS` writes `_position.z`
   absolutely (`actor.cc:1478-1493`); on a world-baked mesh `_position` starts at 0,
   so the write is effectively an **additive offset** (`docs/level-design-troubleshooting.md:231`).
   Anchored bricks have no Jolt character, so the write sticks. → write small deltas
   (0.30 → 0.10 → 0), never a world Z. Fallback: `Z_SCALE` squash.
3. **4-fragment burst + despawn ordering.** `Generato::update` runs the spawn check
   *before* the script each tick (`generator.cc:70-143`). So hold the activation
   pulse for a short window (~0.12 s) at `Generation Rate=30`, getting a fragment
   every ~2 ticks (~3-4 total), **then** write `ALIVE=0`. Never write `ALIVE=0` the
   same tick you first set the pulse (zero fragments would spawn).

## Implementation (phased, each independently committable)

All edits in `blender_create_smb.py` + `mailbox.inc` unless noted.

**Phase 0 — Mailbox constants** (`wfsource/source/mailbox/mailbox.inc`, after
`SMB_QBLOCK_DIE,2012`, staying in the 2000-2099 LOCAL band):
- `SMB_BRICK_BREAK_END` (2013) — level-time the break burst closes; on that tick
  write `ALIVE=0`. 0 = not breaking. (Reused by `debris_template` as its own TTL.)
- `SMB_BRICK_BUMP_END` (2014) — level-time a Small-hit bump ends.
- `SMB_BRICK_BUMP_PEAK` (2015) — bump apex (rising → settling), so the bump is a
  2-phase step with no float-division easing.
Bricks set `Number Of Local Mailboxes = 16` (covers 2000..2015). New `INDEXOF_`
constants follow the existing convention; **call out in the commit** that the
`INDEXOF_` prefix is the wart slated for removal (don't invent a new style here).
`mailbox.inc` changed → Phase 7 needs `task build`.

**Phase 1 — Brick texture + builder.** Add `_make_brick_tga()` mirroring
`_make_qblock_tga` (`blender_create_smb.py:265`): NES orange/brown brick courses
with dark mortar. Reuse `_add_textured_box` (`:323`) unchanged.

**Phase 2 — `debris_template` + `DEBRIS_SCRIPT`.** `_make_debris_template()` mirrors
`_make_coin_template` (`:605`) but `attach_schema(obj,'generator')` (not gold),
small ~0.35 m cube, `Mobility='Physics'`, `Falling Acceleration=12.0`, frictionless,
`Object To Throw` unset + `Activation MailBox=0`, `Script=DEBRIS_SCRIPT`. Script:
latch a death-time on first tick (reusing `SMB_BRICK_BREAK_END` as its local TTL),
write `ALIVE=0` after ~1.0 s; optional spin via `TIME → ROTATION_C` (the `COIN_SCRIPT`
idiom, `:600`).

**Phase 3 — `BRICK_SCRIPT` + `_add_brick(name, x)`.** Three-state flat Forth (no
nested `:`, `not`/`0<>`/`>` only; avoid `/`):
- *Break window open* (`SMB_BRICK_BREAK_END≠0`): keep `SMB_QBLOCK_ACTIVATE=1` until
  `TIME > break_end`, then `ALIVE=0`.
- *Bump in progress* (`SMB_BRICK_BUMP_END≠0`): write `Z_POS` 0.30 (rising) → 0.10
  (`TIME>peak`) → 0 + clear latch (`TIME>end`).
- *Idle/solid*: on hit-from-below (`COLLIDER_IDX≠0` & `COLLISION_NORMAL_Z>0`,
  the `?`-block gate at `:578`): if `SMB_MARIO_STATE≠0` → set `break_end=TIME+0.12`
  + pulse activate; else → latch `bump_peak=TIME+0.05`, `bump_end=TIME+0.10`.
`_add_brick` mirrors the qblock loop (`:641`): generator class, `Anchored`,
`Object To Throw='debris_template'`, `Generation Rate=30`, X-vel 0 / Random X 3.0,
Z-vel 6.0 / Random Z 2.0, `Number Of Local Mailboxes=16`, `Script=BRICK_SCRIPT`.

**Phase 4 — Placement (append-only).** Add `brick_0/1/2` per the layout table.
**Critical:** append all new objects *after* every existing authored object so actor
indices don't shift — `verify_coin_slide.py:19` and `screenshot_coin_arc.py:58`
hardcode `BLOCK_IDX/COIN_IDX/QBLOCK_00_IDX = 13/21/13`. Do **not** move `qblock_02`;
get the alternating look by placing `brick_2`@24.0 between the unmoved `?`-blocks.

**Phase 5 — Hidden-item brick.** Clone the existing one-shot `mushroom_block`
(`:715-754`, reusing `MUSHROOM_BLOCK_SCRIPT` and `mushroom_template`) at X=27.0 but
skinned with `brick_tex`. It bumps out one mushroom on first hit-from-below, recolors
tan, stays solid (consistent with "Small can't break"). A 1-Up/Star reward is TODO
§67 taxonomy work — note, don't build.

**Phase 6 — Sound (optional).** Add `INDEXOF_SOUND write-mailbox` on break/bump if a
brick SFX index exists; else leave a TODO (audio can't be verified on this host).

**Phase 7 — Build.** `blender --background --python wflevels/smb_w1_1/blender_create_smb.py`
→ `task build-level -- smb_w1_1` → `task build` (mailbox.inc changed) → `task run-smb`.
`git checkout` any unrelated `.iff` that re-export jitter touches (TODO §142).

## Verification (`tests/verify_smb_brick_break.py`, debug bridge)

Launch `engine/wf_game -L wflevels/smb_w1_1-standalone.iff --debug-port 7781
--debug-print-actors`; discover the brick idx from the actor log; inject
`COLLIDER_IDX=player` + `COLLISION_NORMAL_Z=1` on the brick (the
`cheat_trigger_coin_spawn.py` pattern); step + screenshot to `tests/screenshots/`.

1. **Super break:** `SMB_MARIO_STATE=1`, inject hit, step ~10 ticks → ≥3
   `debris_template` actors appear with diverging X and rise-then-fall Z; brick leaves
   the actor list; **player `GOLD` (3001) unchanged** (proves no scoring, risk #1).
   Screenshot: mid-burst fragments arcing, then brick gone.
2. **Small bump:** `SMB_MARIO_STATE=0`, inject hit → brick `Z_POS` goes 0→0.30→0.10→0,
   brick stays alive, no debris. Screenshot: brick nudges up and settles.
3. **Hidden brick:** inject hit → exactly one mushroom spawns, brick turns tan, stays
   solid (reuse `verify_smb_mushroom_spawn.py` asserts).
4. **Regression:** re-run `verify_coin_slide.py`, `screenshot_coin_arc.py`,
   `verify_smb_mushroom.py` — confirm idx 13/21/9 still resolve (proves Phase 4
   preserved indices).

## Gotchas
- zForth `/` is float division; the scripts above avoid it. `not`=`0=`; use `0<>`/`>`.
  No nested `:` in script bodies.
- `Z_POS` on a brick is an **additive delta** — never write world Z (would render 2×).
- Never `ALIVE=0` the same tick you first pulse the generator (risk #3).
- `Number Of Local Mailboxes` ≥ 16 on bricks or 2013-2015 writes overflow.
- `mailbox.inc` change requires `task build`, not just `build-level`.
- Append new objects only; reordering breaks index-hardcoded test harnesses.

## Critical files
- `wflevels/smb_w1_1/blender_create_smb.py` — golden source (all level edits)
- `wfsource/source/mailbox/mailbox.inc` — new brick mailbox constants
- `wfsource/source/game/generator.cc`, `actor.cc` — reference for spawn/despawn/Z_POS
- `tests/verify_smb_brick_break.py` (new) — verification harness
- `docs/plans/2026-05-26-smb-breakable-bricks.md` (new) — canonical plan, committed with code
