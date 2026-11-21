"""docs/forth-math-words.md lists exactly the words the bridge registers, with the same stack effects.

Plan: docs/plans/2026-11-21-forth-trig-words.md, Verification 5.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def registered():
    header = (ROOT / "engine/stubs/forth_math_zforth.hpp").read_text()
    table = header[header.index("constexpr WordInfo kWords[]"):header.index("constexpr int kFirstCustom")]
    return {m.group(1): (int(m.group(2)), m.group(3)) for m in re.finditer(r'\{"([^"]+)",\s*(\d+),\s*"([^"]*)"\}', table)}


def documented():
    text = (ROOT / "docs/forth-math-words.md").read_text()
    words = {}
    for line in text.split("\n"):
        m = re.match(r"\|\s*`([a-z0-9-]+)`\s*\|\s*`([^`]+)`\s*\|", line)
        if m:
            words[m.group(1)] = m.group(2)
    return words


def test_the_document_lists_exactly_the_registered_words_with_their_stack_effects():
    reg, doc = registered(), documented()
    assert set(reg) == set(doc), (sorted(set(reg) ^ set(doc)))
    for name, (_, effect) in reg.items():
        assert doc[name] == effect, (name, doc[name], effect)


def test_the_syscall_numbers_are_a_contiguous_block_after_the_neural_gate():
    reg = registered()
    numbers = sorted(n for n, _ in reg.values())
    assert numbers == list(range(73, 73 + len(reg)))
    header = (ROOT / "engine/stubs/forth_math_zforth.hpp").read_text()
    assert f"kFirstCustom = {numbers[0]}" in header and f"kLastCustom = {numbers[-1]}" in header


def test_the_bridge_registers_and_dispatches_through_the_shared_table():
    bridge = (ROOT / "engine/stubs/scripting_zforth.cc").read_text()
    assert "wf::forthmath::kWords" in bridge and "wf::forthmath::HandleSyscall" in bridge
    assert '"sin-rev"' not in bridge        # the old private definition must be gone


def test_the_scripting_doc_points_at_the_reference():
    assert "forth-math-words.md" in (ROOT / "docs/scripting-languages.md").read_text()
