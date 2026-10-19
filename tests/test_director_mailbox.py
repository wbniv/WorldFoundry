"""Director mailbox integration test for qbert_practice via the debug bridge.

Tests the director script's logic directly via mailbox injection — the player
sprite stays at the apex throughout.  Does NOT test player movement, joystick
input, or hop animation.

Verifies per all 16 rounds:
  - Palette screenshot (cube top colours)
  - Cube-state cycle (1-hop L1/L3, 2-hop L2/L4, mid-round revert)
  - Score increments (+25 hop-1, +50 hop-2 for L2/L4)
  - Enemy-mix spawn gating (RB/Coily always; GB/Slick/Sam L2+; Ugg/WW L3+; CE2 L4)

Run with the game live on --debug-port 7778:
    python3 tests/test_director_mailbox.py
"""
from __future__ import annotations
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))
from tests.debug_bridge_client import BridgeClient

# ── Mailbox constants (must match blender_create_qbert.py) ─────────────
MB_SCORE            = 70
MB_LIVES            = 72
MB_PENDING_LAND     = 411
MB_INTRO_DONE       = 418
MB_GAME_OVER        = 420
MB_LAST_STICK       = 422
MB_ROUND_NUMBER     = 425
MB_ROUND_CHANGED    = 426
MB_LAST_LEVEL       = 427
MB_CUBE_STATE_BASE  = 200   # state of cube[i] at 200+i
MB_QBERT_ROW        = 400
MB_QBERT_COL        = 401
MB_FREEZE_TIMER     = 546   # >0 = all enemies frozen
MB_GO_BLOCK         = 590
MB_GO_HOLD_TIMER    = 591

# Enemy spawn timer mailboxes (zero → fire immediately)
MB_RB_SPAWN_TIMER       = 512
MB_COILY_SPAWN_DELAY    = 544
MB_GB_SPAWN_TIMER       = 547
MB_SLICK_SPAWN_TIMER    = 550
MB_SAM_SPAWN_TIMER      = 552
MB_UGG_SPAWN_TIMER      = 570
MB_WW_SPAWN_TIMER       = 572
MB_COILY_SPAWN_DELAY_2  = 585

# Enemy active mailboxes
MB_RB_ACTIVE_BASE   = 514   # 514, 515, 516 (3 red balls)
MB_GB_ACTIVE        = 548
MB_SLICK_ACTIVE     = 549
MB_SAM_ACTIVE       = 551
MB_UGG_ACTIVE       = 569
MB_WW_ACTIVE        = 571
MB_COILY_EGG_ACTIVE = 573
MB_COILY_SNAKE_ACTIVE = 574
MB_COILY_EGG2_ACTIVE = 586

# Coily internal state (not "active" mirrors — must be reset between checks)
MB_COILY_ROUND_DONE     = 542   # 1 after egg spawns; blocks re-spawn this round
MB_COILY_PHASE_GLOBAL   = 543   # 0=idle, 1=egg/snake live, 2=egg→snake transition
MB_COILY_EGG2_ROUND_DONE = 584  # CE2 equivalent of ROUND_DONE

UP = 0x0800

SCROT_DIR = REPO / "tests" / "screenshots"

PASS_S = "\033[32mPASS\033[0m"
FAIL_S = "\033[31mFAIL\033[0m"
SKIP_S = "\033[33mSKIP\033[0m"

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    label = PASS_S if cond else FAIL_S
    print(f"  {label}  {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(name)
    return cond


def read_mb(cli: BridgeClient, mb: int) -> float | None:
    cli.watch(idx=1, mailbox=mb)
    time.sleep(0.25)
    with cli._lock:
        val = cli.mailbox_values.get((1, mb))
    cli.unwatch(idx=1, mailbox=mb)
    return val


def screenshot(cli: BridgeClient, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cli.send({"op": "screenshot", "filename": path})
    msg = cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=6.0)
    ok = msg and msg.get("op") == "screenshot_done"
    print(f"  screenshot {'OK' if ok else 'WARN'}: {os.path.basename(path)}")


def restart_game(cli: BridgeClient) -> None:
    cli.set_mailbox(mailbox=MB_GO_BLOCK, value=0, idx=0)
    cli.set_mailbox(mailbox=MB_GO_HOLD_TIMER, value=0, idx=0)
    cli.set_mailbox(mailbox=MB_LAST_STICK, value=0, idx=0)
    cli.set_mailbox(mailbox=MB_GAME_OVER, value=1, idx=0)
    time.sleep(0.1)
    cli.inject_input("joystick1_raw", UP, duration_frames=3)
    time.sleep(0.4)
    cli.set_mailbox(mailbox=MB_INTRO_DONE, value=1, idx=0)
    cli.set_mailbox(mailbox=MB_LIVES, value=3, idx=0)
    cli.set_mailbox(mailbox=MB_FREEZE_TIMER, value=7200, idx=0)
    time.sleep(0.3)


def jump_to_round(cli: BridgeClient, r: int) -> None:
    cli.set_mailbox(mailbox=MB_ROUND_NUMBER, value=r, idx=0)
    cli.set_mailbox(mailbox=MB_ROUND_CHANGED, value=1, idx=0)
    cli.set_mailbox(mailbox=MB_FREEZE_TIMER, value=7200, idx=0)
    time.sleep(0.6)  # let director process round change at ~30 Hz


def trigger_land_on_cube(cli: BridgeClient, cube_idx: int) -> None:
    """Set Q*bert position to cube[cube_idx] and fire PENDING_LAND."""
    # cube_idx = row*(row+1)//2 + col for the triangular grid, but for
    # the mailbox layout it's just sequential (0..27). Row 0 = apex = cube 0.
    # Use row=0, col=0 (apex) throughout — cube index 0.
    cli.set_mailbox(mailbox=MB_QBERT_ROW, value=0, idx=0)
    cli.set_mailbox(mailbox=MB_QBERT_COL, value=0, idx=0)
    cli.set_mailbox(mailbox=MB_PENDING_LAND, value=1, idx=0)
    time.sleep(0.25)   # ~8 frames at 30 Hz for director to process


def reset_cube(cli: BridgeClient, cube_idx: int, state: int = 0) -> None:
    cli.set_mailbox(mailbox=MB_CUBE_STATE_BASE + cube_idx, value=state, idx=0)


def reset_score(cli: BridgeClient) -> None:
    cli.set_mailbox(mailbox=MB_SCORE, value=0, idx=0)


_SUPPRESSED_TIMER = 500   # ticks > 8 s window — prevents unwanted enemy spawns

def check_enemy_mix(cli: BridgeClient, level: int) -> None:
    """Unfreeze for 8 s and observe which enemies ever become active.

    Uses peak-value polling (samples every 0.5 s) so enemies that spawn and
    retire within the window are still counted.  Spawn timers for enemies that
    should NOT appear at this level are set to _SUPPRESSED_TIMER (>window) so
    the spawn blocks can't fire even if timers are 0 from a prior check.
    """
    WINDOW_S = 8.0
    POLL_S   = 0.5

    print(f"  Enemy mix (L{level+1}) — unfreezing {WINDOW_S:.0f} s ...")

    # ── reset active mirrors ───────────────────────────────────────────────
    for k in range(3):
        cli.set_mailbox(mailbox=MB_RB_ACTIVE_BASE + k, value=0, idx=0)
    for mb in (MB_GB_ACTIVE, MB_SLICK_ACTIVE, MB_SAM_ACTIVE,
               MB_UGG_ACTIVE, MB_WW_ACTIVE,
               MB_COILY_EGG_ACTIVE, MB_COILY_SNAKE_ACTIVE, MB_COILY_EGG2_ACTIVE):
        cli.set_mailbox(mailbox=mb, value=0, idx=0)

    # ── reset Coily internal state ─────────────────────────────────────────
    # PHASE_GLOBAL != 0 blocks new egg spawns and Ugg/WW.
    # ROUND_DONE=1 blocks the per-round egg spawn even when PHASE_GLOBAL=0.
    cli.set_mailbox(mailbox=MB_COILY_PHASE_GLOBAL,    value=0, idx=0)
    cli.set_mailbox(mailbox=MB_COILY_ROUND_DONE,      value=0, idx=0)
    cli.set_mailbox(mailbox=MB_COILY_EGG2_ROUND_DONE, value=0, idx=0)

    # ── arm spawn timers (level-aware) ─────────────────────────────────────
    # Timers for enemies that should NOT appear at this level are set to
    # _SUPPRESSED_TIMER so they cannot fire in the observation window even if
    # they were left at 0 by a previous check or round-init that skipped arming.
    cli.set_mailbox(mailbox=MB_RB_SPAWN_TIMER,    value=0, idx=0)  # always
    cli.set_mailbox(mailbox=MB_COILY_SPAWN_DELAY, value=0, idx=0)  # always

    if level >= 1:   # L2+: Green Ball, Slick, Sam
        cli.set_mailbox(mailbox=MB_GB_SPAWN_TIMER,    value=0, idx=0)
        cli.set_mailbox(mailbox=MB_SLICK_SPAWN_TIMER, value=0, idx=0)
        cli.set_mailbox(mailbox=MB_SAM_SPAWN_TIMER,   value=0, idx=0)
    else:
        cli.set_mailbox(mailbox=MB_GB_SPAWN_TIMER,    value=_SUPPRESSED_TIMER, idx=0)
        cli.set_mailbox(mailbox=MB_SLICK_SPAWN_TIMER, value=_SUPPRESSED_TIMER, idx=0)
        cli.set_mailbox(mailbox=MB_SAM_SPAWN_TIMER,   value=_SUPPRESSED_TIMER, idx=0)

    if level >= 2:   # L3+: Ugg, Wrong-Way
        cli.set_mailbox(mailbox=MB_UGG_SPAWN_TIMER, value=0, idx=0)
        cli.set_mailbox(mailbox=MB_WW_SPAWN_TIMER,  value=0, idx=0)
    else:
        cli.set_mailbox(mailbox=MB_UGG_SPAWN_TIMER, value=_SUPPRESSED_TIMER, idx=0)
        cli.set_mailbox(mailbox=MB_WW_SPAWN_TIMER,  value=_SUPPRESSED_TIMER, idx=0)

    if level >= 3:   # L4: second Coily egg
        cli.set_mailbox(mailbox=MB_COILY_SPAWN_DELAY_2, value=0, idx=0)
    else:
        cli.set_mailbox(mailbox=MB_COILY_SPAWN_DELAY_2, value=_SUPPRESSED_TIMER, idx=0)

    # ── watch and poll for peak activity ──────────────────────────────────
    mbs_to_watch = (
        [MB_RB_ACTIVE_BASE + k for k in range(3)]
        + [MB_GB_ACTIVE, MB_SLICK_ACTIVE, MB_SAM_ACTIVE,
           MB_UGG_ACTIVE, MB_WW_ACTIVE,
           MB_COILY_EGG_ACTIVE, MB_COILY_SNAKE_ACTIVE, MB_COILY_EGG2_ACTIVE]
    )
    for mb in mbs_to_watch:
        cli.watch(idx=1, mailbox=mb)

    cli.set_mailbox(mailbox=MB_FREEZE_TIMER, value=0, idx=0)

    # Sample every POLL_S; accumulate "was ever > 0" across the window.
    # mailbox_values holds only the last value, so a spawn that retires before
    # the end of the window would otherwise be missed.
    peak_active: dict[int, bool] = {}
    n_polls = int(WINDOW_S / POLL_S)
    for _ in range(n_polls):
        time.sleep(POLL_S)
        with cli._lock:
            for mb in mbs_to_watch:
                v = cli.mailbox_values.get((1, mb))
                if v is not None and v > 0:
                    peak_active[mb] = True

    for mb in mbs_to_watch:
        cli.unwatch(idx=1, mailbox=mb)

    cli.set_mailbox(mailbox=MB_FREEZE_TIMER, value=7200, idx=0)

    def ever_active(mb: int) -> bool:
        return peak_active.get(mb, False)

    rb_any = any(ever_active(MB_RB_ACTIVE_BASE + k) for k in range(3))
    gb     = ever_active(MB_GB_ACTIVE)
    slick  = ever_active(MB_SLICK_ACTIVE)
    sam    = ever_active(MB_SAM_ACTIVE)
    ugg    = ever_active(MB_UGG_ACTIVE)
    ww     = ever_active(MB_WW_ACTIVE)
    egg1   = ever_active(MB_COILY_EGG_ACTIVE) or ever_active(MB_COILY_SNAKE_ACTIVE)
    egg2   = ever_active(MB_COILY_EGG2_ACTIVE)

    check(f"L{level+1}: Red Ball spawns", rb_any)
    check(f"L{level+1}: Coily (egg or snake) spawns", egg1)

    if level >= 1:  # L2+
        check(f"L{level+1}: Green Ball spawns", gb,
              "Green Ball should appear in L2+")
        check(f"L{level+1}: Slick or Sam spawns", slick or sam,
              "Slick/Sam should appear in L2+")
    else:
        check(f"L1: No Green Ball", not gb, f"GB_ACTIVE={gb}")
        check(f"L1: No Slick/Sam", not (slick or sam), f"slick={slick} sam={sam}")

    if level >= 2:  # L3+
        check(f"L{level+1}: Ugg or Wrong-Way spawns", ugg or ww,
              "Ugg/WW should appear in L3+")
    else:
        check(f"L{level+1}: No Ugg/Wrong-Way", not (ugg or ww),
              f"ugg={ugg} ww={ww}")

    if level >= 3:  # L4
        check(f"L4: Second Coily egg spawns", egg2,
              "CE2 should appear in L4")
    else:
        check(f"L{level+1}: No second Coily egg", not egg2,
              f"CE2_active={egg2}")


def test_round(cli: BridgeClient, r: int) -> None:
    level = r // 4            # 0=L1, 1=L2, 2=L3, 3=L4
    is_two_step = (level % 2) == 1   # L2 and L4
    level_name = f"L{level+1}R{(r%4)+1}"

    print(f"\n── Round {r:2d} ({level_name}) {'2-hop' if is_two_step else '1-hop'} ──")
    jump_to_round(cli, r)

    # 1. Palette screenshot
    scrot_path = str(SCROT_DIR / f"round-{r:02d}-{level_name}.png")
    screenshot(cli, scrot_path)

    # 2. Cube-state advance — reset cube 0 and trigger land
    reset_score(cli)
    reset_cube(cli, cube_idx=0, state=0)
    trigger_land_on_cube(cli, cube_idx=0)

    state_after_hop1 = read_mb(cli, MB_CUBE_STATE_BASE + 0)
    score_after_hop1 = read_mb(cli, MB_SCORE)

    expected_state1 = 1 if is_two_step else 2
    check(f"{level_name}: 1st hop → state {expected_state1}",
          state_after_hop1 == expected_state1,
          f"got {state_after_hop1}")
    check(f"{level_name}: 1st hop → +25 score",
          score_after_hop1 == 25,
          f"got {score_after_hop1}")

    if is_two_step:
        # 3. Second hop (state 1 → 2)
        reset_score(cli)
        trigger_land_on_cube(cli, cube_idx=0)

        state_after_hop2 = read_mb(cli, MB_CUBE_STATE_BASE + 0)
        score_after_hop2 = read_mb(cli, MB_SCORE)

        check(f"{level_name}: 2nd hop → state 2",
              state_after_hop2 == 2,
              f"got {state_after_hop2}")
        check(f"{level_name}: 2nd hop → +50 score",
              score_after_hop2 == 50,
              f"got {score_after_hop2}")

        # 4. Mid-round revert (state 2 → 0 for L2, → 1 for L4)
        reset_score(cli)
        trigger_land_on_cube(cli, cube_idx=0)

        state_after_revert = read_mb(cli, MB_CUBE_STATE_BASE + 0)
        expected_revert = 0 if level == 1 else 1  # L2→0, L4→1
        check(f"{level_name}: re-hop state-2 → state {expected_revert} (mid-round revert)",
              state_after_revert == expected_revert,
              f"got {state_after_revert}")


def main() -> None:
    print("Connecting ...")
    cli = BridgeClient(host="127.0.0.1", port=7778, timeout=10.0)

    restart_game(cli)
    print("Game ready.\n")

    # ── Cube-cycle + palette: all 16 rounds ────────────────────────────────
    for r in range(16):
        test_round(cli, r)

    # ── Enemy mix: one check per level boundary ─────────────────────────────
    for r, level in [(0, 0), (4, 1), (8, 2), (12, 3)]:
        print(f"\n── Enemy mix check R{r:02d} L{level+1} ──")
        jump_to_round(cli, r)
        check_enemy_mix(cli, level)

    cli.close()

    print("\n── Summary ──")
    if failures:
        print(f"{FAIL_S} {len(failures)} check(s) failed:")
        for f in failures:
            print(f"  • {f}")
        sys.exit(1)
    else:
        print(f"{PASS_S} All checks passed — 16-round end-to-end test complete.")


if __name__ == "__main__":
    main()
