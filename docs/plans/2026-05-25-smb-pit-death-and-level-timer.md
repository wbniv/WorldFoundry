# SMB W1-1 — pit/fall death + level countdown timer

**Status:** Done + verified (2026-05-25). Both features land as designed; one deviation noted below. ~½-day implementation.

**Verified** (debug bridge + screenshots, [`tests/verify_smb_pit_timer.py`](../../tests/verify_smb_pit_timer.py) ALL PASS):
HUD shows `TIME` counting down from ~400 ([pit screenshot](../../tests/screenshots/smb_pit_falling.png) reads `TIME 380`); Mario walks off the first pit lip (X≈29, Z<−0.2 → falls), the pit ActBox fires the existing respawn → `LIVES 3→2` and he reappears at spawn ([after-respawn](../../tests/screenshots/smb_after_respawn.png) reads `LIVES 2`, `TIME 398` — clock re-anchored on death); forcing `SMB_TIMER_START` into the past drains the clock to 0 → "TIME UP" fires `SMB_PLAYER_HURT` → `LIVES 2→1` + respawn + `TIME` resets to ~400. Camera-scroll regression [`verify_smb_scroll.py`](../../tests/verify_smb_scroll.py) still 4/4 (appended Director timer block leaves the ratchet untouched).

**Deviation / confirmed limitation:** the documented i-frame edge case is real and observable — a timeout (or pit fall) landing inside the 2 s post-respawn invulnerability window is swallowed (life not lost) while the Director still re-anchors the clock; the verify harness re-arms the timeout until a life is actually lost. Acceptable for v1 (spawn is far from any pit; a back-to-back timeout is unlikely). A dedicated unconditional-death path is a follow-up if it ever bites.

**Build note:** the game build was blocked by a pre-existing link error (`gEditorMode` undefined, from `13be9fe2`) — fixed separately in `ba9b2101` before this feature could build.

## Context

The SMB enemy combat loop just landed — stomp + hurt/death/respawn + lives ([`5b675915`](https://github.com/wbniv/WorldFoundry/commit/5b675915), [`8a210042`](https://github.com/wbniv/WorldFoundry/commit/8a210042)). What it leaves open is the rest of the **lose-conditions**: in real SMB you also die by **falling into a pit** and by **the timer running out**. Both are the highest-value next step in the [SMB→primitives mapping](../investigations/2026-05-25-smb-features-to-wf-primitives.md) (🔧 *Pit/fall death*, 🔧 *Level timer*), and both are nearly free now because the Phase-3 respawn state machine and the marble-madness timer pattern already exist — this is composition + a few lines of Forth, **no engine C++ change**.

Intended outcome: Mario falls into a gap in the ground → loses a life → respawns at the start (or game-over at 0 lives); a 400-unit timer counts down in the HUD and, at 0, kills Mario (faithful "TIME UP"). The camera scroll, stomp, and existing respawn are untouched.

## What we reuse (don't rebuild)

- **Respawn state machine** — the `SMB_PLAYER_HURT` branch in the player script ([`blender_create_smb.py:687-699`](../../wflevels/smb_w1_1/blender_create_smb.py)): decrements `LIVES`, repositions to `MARIO_SPAWN_*`, zeroes speeds, sets 2 s i-frames, `LIVES<1 → END_OF_LEVEL`. Both new death sources funnel into it by writing `SMB_PLAYER_HURT=1`.
- **ActBox-as-region-sensor** — the flagpole end-of-level trigger ([`blender_create_smb.py:882-904`](../../wflevels/smb_w1_1/blender_create_smb.py)): invisible cube + `actbox` schema, `wf_MailBox`/`wf_MailBoxValue`, `wf_Activated By Actor='Player'`, `wf_Activated Actor Mailbox=4005`. ActBox uses a **PA-based AABB test** ([`actbox.cc:123-149`](../../wfsource/source/game/actbox.cc)), not Jolt body dispatch — so unlike the enemy CharacterVirtual proximity problem, it *does* fire for the player. Mirror it for pit volumes.
- **Director countdown** — marble-madness pattern (`gen_lev.py:289-299`): store an anchor time off `INDEXOF_TIME`, derive remaining each tick, write it to the HUD slot, trigger on ≤0. Timing is in **seconds off the level clock**, never ticks.
- **HUD wiring** — [`game.cc:554`](../../wfsource/source/game/game.cc) already reads mb 70 (score) / 71 (timer) / 72 (lives). Writing the countdown to mb 71 displays it with zero engine work.

## Design

### Mailboxes (`wfsource/source/mailbox/mailbox.inc`)

Add named constants (the user prefers named entries over bare literals; note the `INDEXOF_` prefix is slated for eventual removal — following the convention here, not entrenching it):

| Name | Index | Note |
|------|-------|------|
| `HUD_SCORE` | 70 | HUD score slot (`game.cc:554`); player already writes it as the bare literal `70` |
| `HUD_TIMER` | 71 | HUD timer slot (`game.cc:554`); Director writes the countdown here |
| `SMB_TIMER_START` | 1808 | level-clock `TIME` at which the current life's countdown began; `0` = uninitialised |

`LIVES`=72, `SMB_PLAYER_HURT`=1804, `TIME`=1906, `END_OF_LEVEL`=1905 already exist.

> **Build gotcha:** adding a `MAILBOXENTRY` does NOT recompile `engine/stubs/scripting_stub.cc` (it only `#include`s the `.inc`). Must `touch engine/stubs/scripting_stub.cc wfsource/source/mailbox/mailbox.cc` before `task build`, else scripts fail with `error 7 not_a_word`. Verify with `strings engine/wf_game | grep INDEXOF_SMB_TIMER_START`.

### Pit / fall death (`blender_create_smb.py`)

**Faithful W1-1 layout.** Real W1-1 has two signature bottomless gaps — one mid-level and one on the final approach by the double-pyramid staircase before the flag ([Super Mario Wiki — World 1-1](https://www.mariowiki.com/World_1-1_(Super_Mario_Bros.)), [nesmaps W1-1 map](https://nesmaps.com/maps/SuperMarioBrothers/SuperMarioBrosWorld1-1Map.html)). Our level is geometrically **compressed** (~49 tiles, flag at tile 42, vs the real ~212-tile level), so we reproduce the two-pit *structure* at proportional positions rather than 1:1 tile coordinates. (True tile-faithful placement would require re-authoring the level at full width — a separate follow-up, out of scope here.)

1. **Segment the ground.** Replace the single `build_textured_ground_mesh('ground', GROUND_X0…GROUND_X1)` call (§5) with a loop that builds one slab per solid span, skipping the pit X-ranges. Pit list (tiles in comments; `T=1.5`), placed clear of the ? cluster (tiles 8/14/17), Goomba (22), Koopa (28), flag (42):
   ```python
   PITS = [(28.5, 31.5),   # tiles 19–20: mid-level gap, between the ? cluster and the first Goomba
           (51.0, 54.0)]   # tiles 34–35: the signature late gap on the final approach to the flag
   ```
   Each is a 2-tile (3 m) gap — comfortably jumpable under the current [jump tuning](2026-05-17-smb-mario-speed-jump-tuning.md); widen toward 3 tiles only if verified clearable. Each ground segment keeps the existing `statplat` schema + `wf_Visibility Mailbox=1` + `wf_Model Type='Mesh'`, named `ground_0`, `ground_1`, …. Jolt builds static collision per mesh, so segments give real holes.
2. **Pit-death ActBox** per pit — mirror the flagpole ActBox, positioned **below** the gap so a standing Mario at the edge doesn't false-trigger but a falling one does:
   - center `((L+R)/2, 0, -8)`, half-extents `((R-L)/2 + 0.5, GROUND_Y, 7)` → Z-band `[-15, -1]`.
   - `wf_MailBox = SMB_PLAYER_HURT (1804)`, `wf_MailBoxValue = 1`, `wf_Activated By Actor='Player'`, `wf_Activated Actor Mailbox = 4005`.
   - Falling Mario enters the band → `SMB_PLAYER_HURT=1` → existing respawn fires (−1 life, back to spawn). No new player-script code.
   - *Known v1 limitation:* a pit fall during the 2 s post-respawn i-frame window is ignored; practically unreachable (spawn X=4.5 is far from the pit) — noted, not handled.

### Level countdown timer

1. **Append to the existing Director script** ([`blender_create_smb.py:136-150`](../../wflevels/smb_w1_1/blender_create_smb.py)) — it already runs after every actor each tick. Append a stack-balanced block (camera ratchet logic untouched):
   - init once: `SMB_TIMER_START==0 → SMB_TIMER_START = TIME`.
   - each tick: `elapsed = TIME − SMB_TIMER_START`; `display = 400 − elapsed*RATE` (clamp ≥0); write `display` to `HUD_TIMER`. `RATE ≈ 2.67` units/s → 400 units over ~150 s real (SMB-faithful; tunable constant).
   - on `display ≤ 0`: write `SMB_PLAYER_HURT=1` (faithful "TIME UP, Mario dies") **and** reset `SMB_TIMER_START = TIME` (restart the clock for the next life).
2. **Reset the clock on every death.** Add one line to the player respawn branch (after the speed-zeroing): `INDEXOF_TIME read-mailbox INDEXOF_SMB_TIMER_START write-mailbox` — so enemy/pit/timeout deaths all restart the 400 countdown, matching SMB.
3. Swap the player script's bare `70 write-mailbox` (score) to `INDEXOF_HUD_SCORE write-mailbox` while here (named-constant tidy-up).

*Out of scope (follow-ups):* the 100-seconds-left tempo change + beep SFX, and converting remaining time → score at the flagpole (50 pts/s) — both noted in the brief, both audio/score polish.

## Files

| File | Change |
|------|--------|
| [`wfsource/source/mailbox/mailbox.inc`](../../wfsource/source/mailbox/mailbox.inc) | + `HUD_SCORE`(70), `HUD_TIMER`(71), `SMB_TIMER_START`(1808) |
| [`wflevels/smb_w1_1/blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py) | segment ground + `PITS`; pit-death ActBox(es); Director timer block; respawn clock-reset line; `HUD_SCORE` constant |
| level binaries (`.lev`/`.lvl`/`.iff`/`-standalone.iff`) | rebuilt |
| [`docs/level-design-troubleshooting.md`](../level-design-troubleshooting.md) | log any new gotcha as discovered (mid-execution, not batched) |

## Build & run

```
# 1. engine (new mailbox constant must reach the scripting stub table)
touch engine/stubs/scripting_stub.cc wfsource/source/mailbox/mailbox.cc
task build
strings engine/wf_game | grep -E 'INDEXOF_SMB_TIMER_START|INDEXOF_HUD_TIMER'   # must print

# 2. regenerate the level from the Blender source, then the binary chain
blender --background --python wflevels/smb_w1_1/blender_create_smb.py   # exports smb_w1_1.lev
task build-level -- smb_w1_1                                            # .lev → .lvl → .iff → -standalone.iff

# 3. run
task run-smb
```

## Verification (debug bridge + screenshots — visual proof required)

Launch `wf_game -Lwflevels/smb_w1_1-standalone.iff --debug-port 7777`; drive via `tests/debug_bridge_client.py`.

1. **Pit death.** `watch` LIVES (idx 0, mb 72) + `SMB_PLAYER_Z` (player idx, mb 1803). Inject sticky RIGHT (`inject_input joystick1_raw 0x2000 -1`), `step` frames until Mario walks off the first pit edge (X≈28.5, before the Goomba). Assert: `Z` drops below −1, then LIVES `3→2`, and X/Z snap back to `MARIO_SPAWN_*` (4.5/4.5). Screenshot at the pit edge and after respawn. (Don't drive past it into the Goomba — confirm the pit alone decrements a life.)
2. **Timer counts down + expires.** `watch` HUD_TIMER (mb 71). Confirm it starts ≈400 and decreases as frames step. To exercise expiry without waiting ~150 s: `set_mailbox SMB_TIMER_START = (TIME − big)` so `display ≤ 0`; assert `SMB_PLAYER_HURT` fires → LIVES decrements + respawn, and HUD_TIMER resets to ≈400. Screenshot the HUD timer number.
3. **Regression.** `python3 tests/verify_smb_scroll.py` → 4/4 (camera ratchet on the shared Director must be unaffected by the appended timer block).

Commit per feature (pit-death, then timer), each with its screenshots.
