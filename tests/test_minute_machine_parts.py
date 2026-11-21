"""Minute Machine geometry: budgets, pivots, and the flap-card depth rule.

Plan: docs/plans/2026-11-21-sixty-second-chain-reaction.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "wflevels" / "minute_machine"))

import parts  # noqa: E402
import timeline as tl  # noqa: E402


def test_fallen_cards_never_show_art_through_the_card_in_front():
    """cast1, 2026-11-21: the hour 9 drew as 8. Cards were 18 mm thick with art 10 mm proud, stacked 10 mm
    apart, so the art of a card behind came out level with the front card's face. A card behind must put
    even its art entirely behind the front card's plate."""
    front_plate_back = parts.CARD_T / 2
    behind_art_front = -parts.CARD_T / 2 - parts.ART_T + tl.CARD_STACK
    assert behind_art_front > front_plate_back, (behind_art_front, front_plate_back)
    assert tl.CARD_STACK > parts.CARD_T + parts.ART_T


def test_the_deepest_fallen_card_is_in_front_of_the_housing_back_plate():
    deepest = max((n - 2) * tl.CARD_STACK for n in tl.DRUM_SIZES) + parts.CARD_T / 2
    assert deepest < parts.HOUSING_BACK_Y, (deepest, parts.HOUSING_BACK_Y)


def test_the_two_halves_of_every_digit_are_on_the_right_faces():
    for k in range(4):
        n = tl.DRUM_SIZES[k]
        for c in range(n):
            mesh = parts.card_mesh(k, c)
            # a card carries a front (-y) and a back (+y) face of art
            front = [v for v in mesh.vertices if v[1] < -parts.CARD_T / 2 - 1e-9]
            back = [v for v in mesh.vertices if v[1] > parts.CARD_T / 2 + 1e-9]
            assert front and back, (k, c)


def test_animated_actor_budget_and_pivots():
    meshes = parts.all_meshes()
    assert len(meshes) <= 80
    assert sum(len(m.faces) for m in meshes.values()) + sum(len(m.faces) for m in parts.static_meshes()) < 15000
    for i in range(tl.DOMINO_COUNT):
        lo, hi = meshes[f"domino_{i:02d}"].bounds()
        assert abs(lo[2]) < 1e-9 and abs(hi[0]) < 1e-9, i          # base at z = 0, pivot on the right edge
    for k in range(4):
        for c in range(tl.DRUM_SIZES[k]):
            lo, hi = meshes[f"card_{k}_{c}"].bounds()
            assert abs(lo[2]) < 1e-9, (k, c)                        # a card hangs from its spindle at z = 0
