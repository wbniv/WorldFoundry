"""Tests for GitHub-style alert callout rendering in scripts/md-to-pdf.sh."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "md-to-pdf.sh"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "alerts.md"
OUT_HTML = Path(os.environ["HOME"]) / "tmp" / "alerts.html"


@pytest.fixture(scope="module")
def rendered_html() -> str:
    subprocess.run(
        [str(SCRIPT), str(FIXTURE.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return OUT_HTML.read_text(encoding="utf-8")


def _alert_div(html: str, kind: str) -> str:
    """Extract the body of the first <div class="alert alert-{kind}">...</div>."""
    m = re.search(
        rf'<div class="alert alert-{kind}">(.*?)</div>',
        html,
        re.DOTALL,
    )
    assert m, f"alert-{kind} div not found in output"
    return m.group(1)


def test_note_renders_as_alert_div(rendered_html: str) -> None:
    body = _alert_div(rendered_html, "note")
    assert "Note</p>" in body
    assert "This is a note." in body
    assert "[!NOTE]" not in rendered_html


def test_tip_renders_as_alert_div(rendered_html: str) -> None:
    body = _alert_div(rendered_html, "tip")
    assert "Tip</p>" in body
    assert "This is a tip." in body
    assert "[!TIP]" not in rendered_html


def test_important_renders_as_alert_div(rendered_html: str) -> None:
    body = _alert_div(rendered_html, "important")
    assert "Important</p>" in body
    assert "This is important." in body
    assert "It spans two lines." in body
    # Two body <p>s (one per line) plus the title <p>
    assert body.count("<p>") == 2
    assert "[!IMPORTANT]" not in rendered_html


def test_warning_renders_as_alert_div(rendered_html: str) -> None:
    body = _alert_div(rendered_html, "warning")
    assert "Warning</p>" in body
    assert "This is a warning." in body
    assert "[!WARNING]" not in rendered_html


def test_caution_renders_as_alert_div(rendered_html: str) -> None:
    body = _alert_div(rendered_html, "caution")
    assert "Caution</p>" in body
    assert "This is a caution." in body
    assert "[!CAUTION]" not in rendered_html


def test_plain_blockquote_unchanged(rendered_html: str) -> None:
    m = re.search(r"<blockquote>(.*?)</blockquote>", rendered_html, re.DOTALL)
    assert m, "plain <blockquote> not found"
    body = m.group(1)
    assert "This is a plain blockquote" in body
    assert "Second line of the plain quote." in body
    assert 'class="alert' not in body


def test_lowercase_marker_recognized(rendered_html: str) -> None:
    # The lowercase [!note] fixture line is the *second* alert-note in the doc.
    notes = re.findall(
        r'<div class="alert alert-note">(.*?)</div>',
        rendered_html,
        re.DOTALL,
    )
    assert len(notes) == 2, f"expected 2 alert-note divs, got {len(notes)}"
    assert "Lowercase marker" in notes[1]


def test_unknown_marker_falls_back_to_blockquote(rendered_html: str) -> None:
    # [!BOGUS] should appear inside a plain blockquote (preserve marker text)
    assert "[!BOGUS]" in rendered_html
    bogus_in_alert = re.search(
        r'<div class="alert[^"]*">[^<]*<p[^>]*>[^<]*</p>\s*<p>\[!BOGUS\]',
        rendered_html,
    )
    assert bogus_in_alert is None, "[!BOGUS] should not be wrapped in an alert div"


def test_alert_css_present(rendered_html: str) -> None:
    for kind, color in [
        ("note", "#0969da"),
        ("tip", "#1a7f37"),
        ("important", "#8250df"),
        ("warning", "#9a6700"),
        ("caution", "#cf222e"),
    ]:
        assert f".alert-{kind}" in rendered_html, f"missing .alert-{kind} CSS"
        assert color in rendered_html, f"missing accent color {color} for {kind}"


def test_alert_titles_use_unicode_icons(rendered_html: str) -> None:
    for icon in ("ℹ", "✓", "◆", "⚠", "⛔"):
        assert icon in rendered_html, f"missing icon glyph {icon!r}"
