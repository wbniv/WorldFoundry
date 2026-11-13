"""Q*bert answers the stick after the intro: regressions for docs/plans/2026-11-14-qbert-remote-hop.md.

Runs every actor script of the exported qbert_practice.lev the way the engine does
(tests/level_script_vm.cc), with the stick bits a Chromecast D-pad produces
(hal/android/native_app_entry.cc MapKeyCode: RIGHT 0x2000, DOWN 0x1000, UP 0x0800, LEFT 0x4000).

Before the fix, Ugg spawned on L1R1 the moment the intro ended, climbed to the apex in
106 frames and took all three lives in three frames, so every key press after the intro
landed in the game-over restart guard and Q*bert never hopped.

QBERT_LEV=<path> runs the tests against another export (for a before/after comparison).
"""
import os
from pathlib import Path

import pytest

from level_script_vm import LevelScriptVM, ROOT, build

LEV = Path(os.environ.get('QBERT_LEV', ROOT / 'wflevels/qbert_practice/qbert_practice.lev'))
RIGHT, DOWN = 0x2000, 0x1000
ROW, COL, COOLDOWN, LIVES, FALL_DEATH, INTRO_DONE, GAME_OVER = 400, 401, 402, 72, 414, 418, 420
GREEN_PHASE, UGG_PHASE, WRONGWAY_PHASE = 489, 556, 564
ENEMY_PHASES = [465, 473, 481, GREEN_PHASE, 497, 505, UGG_PHASE, WRONGWAY_PHASE, 521, 529, 578]


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    return build(tmp_path_factory.mktemp('level-vm-build'))


@pytest.fixture
def vm(binary, tmp_path):
    machine = LevelScriptVM(LEV, tmp_path, binary)
    assert machine.run_until(INTRO_DONE, 1, 600) is not None, 'intro never finished'
    yield machine
    machine.close()


def test_a_right_press_after_the_intro_hops(vm):
    vm.step(150)                       # past the frame (106) where Ugg used to reach the apex
    assert vm.get(GAME_OVER, LIVES) == [0, 3]
    vm.step(6, RIGHT)                  # a 100 ms tap
    vm.step(20)
    assert vm.get(ROW, COL) == [1, 1], 'RIGHT from the apex hops down-right to (1,1)'
    vm.step(6, DOWN)
    vm.step(20)
    assert vm.get(ROW, COL, GAME_OVER) == [2, 1, 0], 'DOWN from (1,1) hops down-left to (2,1)'
    assert vm.errors()[0] == 0


def test_green_ball_ugg_and_wrong_way_stay_off_level_one(vm):
    for _ in range(1800):              # 30 s of L1R1 with Q*bert standing on the apex
        vm.step(1)
        assert vm.get(GREEN_PHASE, UGG_PHASE, WRONGWAY_PHASE) == [0, 0, 0], f'frame {vm.frame}'


def test_one_contact_costs_one_life_and_clears_the_board(vm):
    lives = 3
    for _ in range(3600):              # Coily comes for a Q*bert who never moves
        vm.step(1)
        lives = vm.get(LIVES)[0]
        if lives < 3:
            break
    assert lives == 2, 'an enemy should reach the apex within a minute, and take exactly one life'
    assert vm.get(*ENEMY_PHASES) == [0] * len(ENEMY_PHASES), 'every enemy leaves the board on a death'
    vm.step(60)
    assert vm.get(LIVES, GAME_OVER) == [2, 0]


def test_holding_a_key_through_the_game_over_hold_does_not_abort_a_script(vm):
    vm.set(LIVES, 1)
    vm.set(FALL_DEATH, 1)              # last life lost
    vm.step(1)
    assert vm.get(GAME_OVER) == [1]
    vm.step(240, RIGHT)                # held while the 180-frame hold (mb 591) runs out
    total, rows = vm.errors()
    assert total == 0, f'script aborts (actor, count, zf_result): {rows}'
    vm.step(1)
    vm.step(2, RIGHT)                  # a fresh press restarts the game
    assert vm.get(GAME_OVER, INTRO_DONE, LIVES) == [0, 0, 3]
