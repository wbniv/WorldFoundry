# Q\*bert — replace raw mailbox numbers with named `INDEXOF_*` / `EMAILBOX_*` constants

**Status:** Parked (TODO). Plan agreed 2026-05-17; not yet implemented. Pick back up when there is appetite to bring qbert in line with [feedback_named_mailbox_constants.md](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_named_mailbox_constants.md).

## Context

[wfsource/source/mailbox/mailbox.inc](../../wfsource/source/mailbox/mailbox.inc) is the project's single source of truth for mailbox slots: each `MAILBOXENTRY(NAME, VALUE)` row generates both `EMAILBOX_NAME` (C++ enum, [mailbox.hp:50-54](../../wfsource/source/mailbox/mailbox.hp)) and `INDEXOF_NAME` (Forth constant, [engine/stubs/scripting_stub.cc:69-76](../../engine/stubs/scripting_stub.cc)). User feedback memory `feedback_named_mailbox_constants.md` makes the rule explicit: any Forth (or C++) reference to a mailbox must use the named constant, never a bare integer literal.

The `smb_w1_1` scrolling-camera change followed this rule (`SMB_PLAYER_X` / `SMB_TARGET_CAM_X` / `SMB_MAX_CAM_X` at 1800/1801/1802). The qbert_practice level — written before the rule was codified — uses raw integers throughout, in both the emitted Forth scripts (~50 distinct slots) and in two C++ call sites in `game.cc`. The qbert catalogue page mirrors the level's raw integers in its Forth samples.

Goal: bring qbert in line with the convention. Work lives in three places — `mailbox.inc` (add ~95 rows), [wflevels/qbert_practice/blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py) (emit `INDEXOF_*` names instead of integer-substituted f-strings), and [docs/qbert/catalogue.md](../qbert/catalogue.md) (update displayed Forth snippets). Two raw-int holdouts in [wfsource/source/game/game.cc](../../wfsource/source/game/game.cc) also get the `EMAILBOX_*` treatment so both sides of the C++↔Forth contract reference the same name.

## Naming convention decisions

| Aspect | Decision |
|---|---|
| Prefix style | **No level prefix** on qbert-specific mailboxes (per user direction). Short descriptive names: `QBERT_ROW`, `HOP_COOLDOWN`, `POPUP_VALUE`, etc. |
| Per-cube state array (28 cubes × 1 byte) | One BASE row: `CUBE_STATE_BASE=200`, `CUBE_PREV_STATE_BASE=228`. Forth indexes via `CUBE_STATE_BASE  cube-idx +  read-mailbox`. |
| Round top-color LUT (16 rounds × 3 states) | One BASE row: `ROUND_TOP_LUT_BASE=256`. Forth indexes via `ROUND_TOP_LUT_BASE  round 3 * +  state +  read-mailbox`. |
| Per-enemy slot blocks (8 fields × 8 actors) | **Fully enumerate** — `RB0_ROW=462, RB0_COL=463, …, RB0_FROM_COL=469, RB1_ROW=470, …`. Python already emits flat integers per‑(actor, field) via `_rb_mb(k, off)` at script-generation time; the Forth never re-indexes at runtime, so each slot gets its own name. 64 entries total. |
| HUD slots (70/71/72, also used by mm_practice and read by C++ DrawHud) | Subsystem prefix `HUD_SCORE / HUD_TIMER / HUD_LIVES` — same shape as existing `LOS_X/Y/Z`, `HARDWARE_JOYSTICKn_*` groupings. |
| C++ ↔ Forth contract slots (590/591) | Add `GO_BLOCK=590`, `GO_HOLD_TIMER=591` to `mailbox.inc`; replace raw 590/591 in `game.cc` with `EMAILBOX_*`. Two raw-int leftovers in the same block (1910, 425) also get named while we're there. |

The lone potentially-ambiguous bare names are `ROW`, `COL`, `PHASE`, `ACTIVE` — these will be qualified by their use case (`QBERT_ROW`, `RB0_ROW`, `GB_PHASE`, `SLICK_ACTIVE`, etc.) so there is no actual collision risk.

## New rows added to `wfsource/source/mailbox/mailbox.inc`

Grouped, with the comment that introduces each block. Numbers below come from [blender_create_qbert.py:59-138](../../wflevels/qbert_practice/blender_create_qbert.py) and the comments above lines 1000-1059.

```
Comment(" HUD shared across Q*bert and Mega-Man practice — read by DrawHud (display.cc). ")
MAILBOXENTRY( HUD_SCORE, 70 )
MAILBOXENTRY( HUD_TIMER, 71 )
MAILBOXENTRY( HUD_LIVES, 72 )

Comment(" Q*bert (qbert_practice) — director / player / enemy state.                       ")
Comment(" See wflevels/qbert_practice/blender_create_qbert.py:59 for the full map.         ")

Comment(" Camshot zone signal — ActBoxOR from cs_pyramid trigger box. ")
MAILBOXENTRY( CAMSHOT_ZONE, 100 )

Comment(" Per-cube state arrays (28 cubes; indexed by cube number 0..27).                  ")
MAILBOXENTRY( CUBE_STATE_BASE,      200 )    Comment("CUBE_STATE_BASE + N  →  cube N's per-frame state (0/1/2)")
MAILBOXENTRY( CUBE_PREV_STATE_BASE, 228 )    Comment("director compares prev vs current to detect state changes")

Comment(" Round top-color lookup table (16 rounds × 3 states → 24-bit RGB).                ")
MAILBOXENTRY( ROUND_TOP_LUT_BASE, 256 )      Comment("base + round*3 + state  →  packed RGB")

Comment(" Q*bert player & director state. ")
MAILBOXENTRY( QBERT_ROW,           400 )
MAILBOXENTRY( QBERT_COL,           401 )
MAILBOXENTRY( HOP_COOLDOWN,        402 )
MAILBOXENTRY( QBERT_LANDED,        411 )    Comment("player→director one-shot on hop completion")
MAILBOXENTRY( CUBES_TO_TARGET,     412 )    Comment("director-internal count")
MAILBOXENTRY( ROUND_CLEAR,         413 )    Comment("director→engine win flag")
MAILBOXENTRY( FALL_DEATH,          414 )    Comment("player→director one-shot at end of fall")
MAILBOXENTRY( CS_DEATH_COUNTDOWN,  415 )
MAILBOXENTRY( INTRO_PHASE,         416 )
MAILBOXENTRY( INTRO_TIMER,         417 )
MAILBOXENTRY( INTRO_DONE,          418 )
MAILBOXENTRY( FALL_PHASE,          419 )
MAILBOXENTRY( GAME_OVER,           420 )
MAILBOXENTRY( LEVEL_INITIALIZED,   421 )
MAILBOXENTRY( LAST_STICK,          422 )
MAILBOXENTRY( ROUND_CLEAR_TIMER,   424 )
MAILBOXENTRY( ROUND_NUMBER,        425 )    Comment("0-based round 0..15 (L1R1..L4R4)")
MAILBOXENTRY( ROUND_CHANGED,       426 )
MAILBOXENTRY( LAST_LEVEL,          427 )
MAILBOXENTRY( CAPTURE_TRIGGER,     432 )    Comment("Phase E walker — host-watched snapshot triggers")
MAILBOXENTRY( QBERT_TARGET_YAW,    433 )    Comment("target yaw in revolutions for player hop turn-lerp")
MAILBOXENTRY( PENDING_LAND,        434 )    Comment("player internal; promoted to QBERT_LANDED on landing")
MAILBOXENTRY( QBERT_STASH_X,       435 )    Comment("player→enemy contact pos snapshot")
MAILBOXENTRY( QBERT_STASH_Y,       436 )
MAILBOXENTRY( QBERT_STASH_Z,       437 )
MAILBOXENTRY( HOP_END_Z,           438 )    Comment("player hop arc destination Z (lerped to over cooldown)")

Comment(" Per-cube visibility fan-out slots (28 cubes × 3 states × 4 palette tints).       ")
Comment(" Indexed in Forth as 440 + cube_idx * 12 + palette * 3 + state. ")
MAILBOXENTRY( CUBE_VIS_BASE, 440 )           Comment("336 slots: 440..775")

Comment(" Red-ball enemies (3 instances; 8 slots each at 462+8*K).                          ")
MAILBOXENTRY( RB0_ROW, 462 )  MAILBOXENTRY( RB0_COL, 463 )  MAILBOXENTRY( RB0_COOLDOWN, 464 )
MAILBOXENTRY( RB0_PHASE, 465 )  MAILBOXENTRY( RB0_START_Z, 466 )  MAILBOXENTRY( RB0_END_Z, 467 )
MAILBOXENTRY( RB0_FROM_ROW, 468 )  MAILBOXENTRY( RB0_FROM_COL, 469 )
MAILBOXENTRY( RB1_ROW, 470 )  MAILBOXENTRY( RB1_COL, 471 )  MAILBOXENTRY( RB1_COOLDOWN, 472 )
MAILBOXENTRY( RB1_PHASE, 473 )  MAILBOXENTRY( RB1_START_Z, 474 )  MAILBOXENTRY( RB1_END_Z, 475 )
MAILBOXENTRY( RB1_FROM_ROW, 476 )  MAILBOXENTRY( RB1_FROM_COL, 477 )
MAILBOXENTRY( RB2_ROW, 478 )  MAILBOXENTRY( RB2_COL, 479 )  MAILBOXENTRY( RB2_COOLDOWN, 480 )
MAILBOXENTRY( RB2_PHASE, 481 )  MAILBOXENTRY( RB2_START_Z, 482 )  MAILBOXENTRY( RB2_END_Z, 483 )
MAILBOXENTRY( RB2_FROM_ROW, 484 )  MAILBOXENTRY( RB2_FROM_COL, 485 )

Comment(" Green ball (single instance; same 8-slot layout, base 486). ")
MAILBOXENTRY( GB_ROW, 486 )  MAILBOXENTRY( GB_COL, 487 )  MAILBOXENTRY( GB_COOLDOWN, 488 )
MAILBOXENTRY( GB_PHASE, 489 )  MAILBOXENTRY( GB_START_Z, 490 )  MAILBOXENTRY( GB_END_Z, 491 )
MAILBOXENTRY( GB_FROM_ROW, 492 )  MAILBOXENTRY( GB_FROM_COL, 493 )

Comment(" Slick (cube-reverter; base 494). ")
MAILBOXENTRY( SLICK_ROW, 494 )  MAILBOXENTRY( SLICK_COL, 495 )  MAILBOXENTRY( SLICK_COOLDOWN, 496 )
MAILBOXENTRY( SLICK_PHASE, 497 )  MAILBOXENTRY( SLICK_START_Z, 498 )  MAILBOXENTRY( SLICK_END_Z, 499 )
MAILBOXENTRY( SLICK_FROM_ROW, 500 )  MAILBOXENTRY( SLICK_FROM_COL, 501 )

Comment(" Sam (cube-reverter; base 502). ")
MAILBOXENTRY( SAM_ROW, 502 )  MAILBOXENTRY( SAM_COL, 503 )  MAILBOXENTRY( SAM_COOLDOWN, 504 )
MAILBOXENTRY( SAM_PHASE, 505 )  MAILBOXENTRY( SAM_START_Z, 506 )  MAILBOXENTRY( SAM_END_Z, 507 )
MAILBOXENTRY( SAM_FROM_ROW, 508 )  MAILBOXENTRY( SAM_FROM_COL, 509 )

Comment(" Red-ball spawn / RNG director state. ")
MAILBOXENTRY( RB_LFSR,          511 )    Comment("Galois LFSR-16 RNG")
MAILBOXENTRY( RB_SPAWN_TIMER,   512 )
MAILBOXENTRY( RB_ACTIVE_BASE,   514 )    Comment("RB_ACTIVE_BASE + K = alive flag for ball K")
MAILBOXENTRY( RB_SPAWN_CLAIMED, 517 )

Comment(" Coily spawn / phase. ")
MAILBOXENTRY( COILY_ROUND_DONE,      542 )
MAILBOXENTRY( COILY_SPAWN_DELAY,     544 )
MAILBOXENTRY( GB_FREEZE_TIMER,       546 )    Comment("global; >0 → all enemies skip tick")
MAILBOXENTRY( GB_SPAWN_TIMER,        547 )
MAILBOXENTRY( GB_ACTIVE,             548 )
MAILBOXENTRY( SLICK_ACTIVE,          549 )
MAILBOXENTRY( SLICK_SPAWN_TIMER,     550 )
MAILBOXENTRY( SAM_ACTIVE,            551 )
MAILBOXENTRY( SAM_SPAWN_TIMER,       552 )

Comment(" Ugg (side climber; base 553). ")
MAILBOXENTRY( UGG_ROW, 553 )  MAILBOXENTRY( UGG_COL, 554 )  MAILBOXENTRY( UGG_COOLDOWN, 555 )
MAILBOXENTRY( UGG_PHASE, 556 )  MAILBOXENTRY( UGG_START_Z, 557 )  MAILBOXENTRY( UGG_END_Z, 558 )
MAILBOXENTRY( UGG_FROM_ROW, 559 )  MAILBOXENTRY( UGG_FROM_COL, 560 )

Comment(" Wrong-Way (deterministic left-edge climber; base 561). ")
MAILBOXENTRY( WW_ROW, 561 )  MAILBOXENTRY( WW_COL, 562 )  MAILBOXENTRY( WW_COOLDOWN, 563 )
MAILBOXENTRY( WW_PHASE, 564 )  MAILBOXENTRY( WW_START_Z, 565 )  MAILBOXENTRY( WW_END_Z, 566 )
MAILBOXENTRY( WW_FROM_ROW, 567 )  MAILBOXENTRY( WW_FROM_COL, 568 )

MAILBOXENTRY( UGG_ACTIVE,         569 )
MAILBOXENTRY( UGG_SPAWN_TIMER,    570 )
MAILBOXENTRY( WW_ACTIVE,          571 )
MAILBOXENTRY( WW_SPAWN_TIMER,     572 )
MAILBOXENTRY( COILY_EGG_ACTIVE,   573 )
MAILBOXENTRY( COILY_SNAKE_ACTIVE, 574 )

Comment(" Coily egg #2 (L4 only; 12 slots 575..586 for its internals).                     ")
MAILBOXENTRY( COILY_EGG2_BASE, 575 )         Comment("12 contiguous slots; field offsets per blender_create_qbert.py")

Comment(" Game-over screen — C++ ↔ Forth contract.                                          ")
Comment(" C++ writes 1 to GO_BLOCK while initials entry is live; arms GO_HOLD_TIMER to 180. ")
Comment(" Forth must not restart while GO_BLOCK is set or GO_HOLD_TIMER > 0.                ")
MAILBOXENTRY( GO_BLOCK,      590 )
MAILBOXENTRY( GO_HOLD_TIMER, 591 )

Comment(" Bonus popup state (display only). ")
MAILBOXENTRY( POPUP_TIMER,      592 )
MAILBOXENTRY( POPUP_VALUE,      593 )    Comment("0=idle, 25/50/100/300/500 = pending trigger")
MAILBOXENTRY( POPUP_PENDING_X,  594 )
MAILBOXENTRY( POPUP_PENDING_Y,  595 )
MAILBOXENTRY( POPUP_PENDING_Z,  596 )    Comment("includes +1.5 Z offset above cube top")

Comment(" Shared spawn sequencer (arcade-faithful; replaces six per-enemy timers). ")
MAILBOXENTRY( SEQ_TIMER,  597 )    Comment("countdown; fires at 0")
MAILBOXENTRY( SEQ_STEP,   598 )    Comment("position in sequence (0-based)")
MAILBOXENTRY( SPAWN_REQ,  599 )    Comment("0=none, 1=RB, 3=CE, 6=Slick, 8=Sam")
```

Total: ~95 new rows. None overlap any existing entry. All slots stay within the bumped `GLOBAL_USER_MAX=1900` range.

## Files modified

| File | Change |
|---|---|
| [wfsource/source/mailbox/mailbox.inc](../../wfsource/source/mailbox/mailbox.inc) | Add ~95 rows (above). |
| [wfsource/source/game/game.cc](../../wfsource/source/game/game.cc) (lines 371–415) | Replace `590` → `EMAILBOX_GO_BLOCK`, `591` → `EMAILBOX_GO_HOLD_TIMER`, `1910` → `EMAILBOX_HARDWARE_JOYSTICK1_RAW_JUSTPRESSED`, `425` → `EMAILBOX_ROUND_NUMBER`. 6 call sites. |
| [wflevels/qbert_practice/blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py) | Stop emitting integers in Forth strings; emit `INDEXOF_*` names instead. Keep Python-side constants as the *symbolic name* string, not the integer. See pattern below. |
| [docs/qbert/catalogue.md](../qbert/catalogue.md) | Rewrite the 10 Forth code blocks (lines 82–322) to mirror the actual emitted Forth (with `INDEXOF_*` names). |

## `blender_create_qbert.py` rewrite pattern

The current pattern at line 1011:
```python
def _rb_mb(k, off):
    return 462 + _RB_PER_BALL * k + off
```
…and call sites like:
```python
f"{mb_row} read-mailbox dup {mb_from_row} write-mailbox …"
```
…where `mb_row = _rb_mb(k, _RB_OFF_ROW)` is the integer 462 (or 470, 478) substituted into the Forth string.

New pattern — emit the symbolic name instead of the integer:
```python
def _rb_mb(k, off):
    field = {
        _RB_OFF_ROW: "ROW", _RB_OFF_COL: "COL", _RB_OFF_COOLDOWN: "COOLDOWN",
        _RB_OFF_PHASE: "PHASE", _RB_OFF_START_Z: "START_Z", _RB_OFF_END_Z: "END_Z",
        _RB_OFF_FROM_ROW: "FROM_ROW", _RB_OFF_FROM_COL: "FROM_COL",
    }[off]
    return f"INDEXOF_RB{k}_{field}"
```
After substitution the emitted Forth becomes:
```forth
INDEXOF_RB0_ROW read-mailbox dup INDEXOF_RB0_FROM_ROW write-mailbox …
```

Same treatment for other enemy `_mb()` helpers (GB, Slick, Sam, Ugg, WW). For non-array mailboxes (HOP_COOLDOWN, POPUP_VALUE, etc.) the Python constants change from numeric (`POPUP_VALUE_MB = 593`) to string (`POPUP_VALUE_MB = "INDEXOF_POPUP_VALUE"`), with all f-string sites already correct (`f"… {POPUP_VALUE_MB} write-mailbox"`).

Where the .py currently bakes in flat integer literals not bound to a Python constant (e.g. `400 read-mailbox` in the redball contact check at line 1445), replace with the `INDEXOF_QBERT_ROW` token directly in the string.

The `write-actor-mailbox` calls pass an actor index as well (e.g. `33 write-actor-mailbox`). Actor indices are not mailboxes and remain integer literals — `mailbox.inc` is only the right source of truth for mailbox slots.

## `docs/qbert/catalogue.md` update

For each of the 10 embedded Forth code blocks (lines 82, 110, 138, 162, 192, 219, 253, 273, 286, 311 in [docs/qbert/catalogue.md](../qbert/catalogue.md)), rewrite to mirror the new emitted Forth — every integer that named a mailbox becomes `INDEXOF_*`. The block currently at line 82 is the player; the rest are enemies and follow the patterns laid out above.

Where the catalogue uses pseudo-aliases like `: cd 402 read-mailbox ;` to abbreviate the snippet, change to `: cd INDEXOF_HOP_COOLDOWN read-mailbox ;` (keeping the alias for readability of the snippet, but defined in terms of the named constant).

Sample diff for the player block (catalogue.md:82-101):
```diff
 : stick INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox ;
-: cd 402 read-mailbox ;
-: tick-cd cd dup 0 > if 1 - 402 write-mailbox else drop then ;
+: cd INDEXOF_HOP_COOLDOWN read-mailbox ;
+: tick-cd cd dup 0 > if 1 - INDEXOF_HOP_COOLDOWN write-mailbox else drop then ;
 : do-hop
   over over
   dup 0 = if drop 0 < if 0.125 else 0.625 then
            else swap drop 0 > if 0.875 else 0.375 then then
-  433 write-mailbox             ( target yaw in rev )
-  INDEXOF_X_POS read-mailbox 435 write-mailbox   ( HOP_START_X )
-  INDEXOF_Y_POS read-mailbox 436 write-mailbox
-  INDEXOF_Z_POS read-mailbox 437 write-mailbox
-  401 read-mailbox + swap 400 read-mailbox +
-  dup 400 write-mailbox over 401 write-mailbox
-  6 swap - 2 * 1 + 2 + 438 write-mailbox          ( HOP_END_Z )
-  drop 13 402 write-mailbox                       ( arm cooldown )
+  INDEXOF_QBERT_TARGET_YAW write-mailbox          ( target yaw in rev )
+  INDEXOF_X_POS read-mailbox INDEXOF_QBERT_STASH_X write-mailbox
+  INDEXOF_Y_POS read-mailbox INDEXOF_QBERT_STASH_Y write-mailbox
+  INDEXOF_Z_POS read-mailbox INDEXOF_QBERT_STASH_Z write-mailbox
+  INDEXOF_QBERT_COL read-mailbox + swap INDEXOF_QBERT_ROW read-mailbox +
+  dup INDEXOF_QBERT_ROW write-mailbox over INDEXOF_QBERT_COL write-mailbox
+  6 swap - 2 * 1 + 2 + INDEXOF_HOP_END_Z write-mailbox
+  drop 13 INDEXOF_HOP_COOLDOWN write-mailbox       ( arm cooldown )
```

## Verify

1. **`mailbox.inc` syntactic check** — the file is preprocessed three ways (C++ enum, Forth constant table, def/tcl). After editing, run an engine compile (`task build`) to confirm the enum still compiles and the Forth constant table builds. Both grow by ~95 entries; no existing values move.

2. **C++ side** ([game.cc](../../wfsource/source/game/game.cc)) — `task build` confirms the `EMAILBOX_GO_BLOCK` / `EMAILBOX_GO_HOLD_TIMER` / `EMAILBOX_HARDWARE_JOYSTICK1_RAW_JUSTPRESSED` / `EMAILBOX_ROUND_NUMBER` references resolve. The integer values are unchanged, so behavior is byte-identical.

3. **Python build script** — `python3 -m py_compile wflevels/qbert_practice/blender_create_qbert.py` after each round of edits (per `feedback_py_compile_check.md`).

4. **Rebuild qbert level binaries** (per `feedback_qbert_blender_build_pipeline.md`):
   ```bash
   bash wftools/wf_blender/build_level_binary.sh qbert_practice
   ```
   This runs Blender → `levcomp-rs` → `iffcomp-rs`. The emitted `.lev` file's script-text chunks will contain `INDEXOF_*` symbols (resolved at runtime by the Forth interpreter); levcomp/iffcomp don't touch script content.

5. **Run the engine and verify gameplay is unchanged**:
   ```bash
   cd wfsource/source/game && ./wf_game qbert_practice
   ```
   Smoke-test that the player can hop, enemies spawn, cubes flip color, popups show — the named constants resolve to the same integers, so behavior should be byte-identical to HEAD. Capture an in-game screenshot per `feedback_screenshots_for_proof.md`.

6. **Spot-check the catalogue** — `task md -- docs/qbert/catalogue.md` and confirm the Forth snippets render correctly with `INDEXOF_*` names.

7. **Grep for residual raw-int mailbox literals** in the new Forth (a regression check):
   ```bash
   grep -nE '\b[0-9]{3,4}\s+(read|write)-(actor-)?mailbox' wflevels/qbert_practice/blender_create_qbert.py
   ```
   Expected: zero hits in script body (actor indices to `write-actor-mailbox` will still match, but those go to the trailing actor-idx arg, not the leading mailbox arg — review by hand).

## Out of scope

- `mm_practice` — also uses the 70/71/72 HUD slots and possibly its own raw-int mailboxes. Per the user's scope ("qbert"), this plan only adds the shared `HUD_*` rows; converting mm_practice's own scripts is a separate follow-up.
- `snowgoons-blender` — already uses `INDEXOF_*` per the script samples seen in `scripts/patch_snowgoons_forth.py`.
- Engine raw-int mailboxes outside qbert's contract surface (not modified).
