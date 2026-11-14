"""Actor references resolved at export (wftools/wf_blender/actor_refs.py).

Regression guard for docs/plans/2026-11-14-qbert-blender-pipeline-repair.md: Q*bert's
scripts carried hardcoded actor indices (CamShots 8/12/13, curse bubble 33) that went stale
when an object was created earlier, and a CamShot Target named an object that was not
exported. The generator now writes `{{actor:NAME}}` and the exporter resolves it in write order.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'wftools' / 'wf_blender'))
import actor_refs  # noqa: E402


def test_tokens_resolve_to_one_based_write_order():
    indices = actor_refs.index_map(['Actboxor01', 'Room01', 'cs_pyramid', 'curse_bubble'])
    script = (f"{actor_refs.actor_ref('cs_pyramid')} INDEXOF_CAMSHOT write-mailbox "
              f"-30.0 3011 {actor_refs.actor_ref('curse_bubble')} write-actor-mailbox")
    assert actor_refs.resolve_actor_refs(script, indices) == (
        "3 INDEXOF_CAMSHOT write-mailbox -30.0 3011 4 write-actor-mailbox")


def test_inserting_an_object_earlier_moves_every_reference_with_it():
    script = f"3011 {actor_refs.actor_ref('curse_bubble')} write-actor-mailbox"
    before = actor_refs.index_map(['Light01', 'Player', 'curse_bubble'])
    after = actor_refs.index_map(['Light01', 'AmbientLight', 'Player', 'curse_bubble'])
    assert actor_refs.resolve_actor_refs(script, before) == "3011 3 write-actor-mailbox"
    assert actor_refs.resolve_actor_refs(script, after) == "3011 4 write-actor-mailbox"


def test_an_unknown_name_refuses_the_export_and_names_it():
    indices = actor_refs.index_map(['Player'])
    with pytest.raises(ValueError, match=r"Director\.Script: actor reference to 'target_14'"):
        actor_refs.resolve_actor_refs(actor_refs.actor_ref('target_14'), indices, 'Director.Script')


def test_text_without_tokens_is_unchanged():
    text = "\\ wf qbert player\n: stick INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox ;\n{ not a token }"
    assert actor_refs.resolve_actor_refs(text, {}) == text


def test_duplicate_names_are_rejected():
    with pytest.raises(ValueError, match='duplicate object name'):
        actor_refs.index_map(['cube_00', 'cube_00'])


def test_dangling_object_reference():
    names = actor_refs.index_map(['Target01', 'Target02'])
    assert actor_refs.dangling_reference('target_14', names)
    assert not actor_refs.dangling_reference('Target02', names)
    assert not actor_refs.dangling_reference('', names)
