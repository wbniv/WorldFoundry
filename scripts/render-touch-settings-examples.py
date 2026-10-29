#!/usr/bin/env python3
"""Render the plan's field matrix and visual example gallery from one inventory."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/plans/2026-10-29-touch-settings"
CASES = json.loads(BASE.with_name(BASE.name + "-examples.json").read_text())
PLAN = BASE.with_name(BASE.name + "-phone-tablet.md")
SVG = BASE.with_name(BASE.name + "-examples.svg")
START = "<!-- examples-table:start -->"
END = "<!-- examples-table:end -->"


def table():
    lines = ["| Example | Type / modifier | `showAs` | Phone control | Presentation |",
             "|---|---|---|---|---|"]
    for c in CASES:
        cells = [f"`{c['id']}`", c["type"], c["showAs"], c["touch"],
                 "Current visual pattern" if c["status"] == "existing" else "New visual pattern"]
        lines.append("| " + " | ".join(x.replace("|", "\\|") for x in cells) + " |")
    return "\n".join(lines)


def control(c, x, y):
    kind, show, cid = c["type"], c["showAs"], c["id"]
    fg = '#dcf0df'
    if cid == 'spacer':
        return f'<line x1="{x}" y1="{y+18}" x2="{x+290}" y2="{y+18}" stroke="#72917b" stroke-dasharray="5 5"/>'
    if cid == 'enum-many':
        return (f'<rect x="{x}" y="{y}" width="290" height="39" rx="7" fill="#335b3e"/>'
                f'<text x="{x+12}" y="{y+26}" class="value">Species A · Species B · +10 more</text>')
    if cid == 'enum-long':
        return (f'<rect x="{x}" y="{y}" width="290" height="39" rx="7" fill="#335b3e"/>'
                f'<text x="{x+12}" y="{y+25}" class="value">Along the northern wall… ▾</text>')
    if cid == 'int-help':
        return (f'<text x="{x}" y="{y+13}" class="meta">Lighting · controls scene brightness</text>'
                f'<rect x="{x}" y="{y+16}" width="290" height="27" rx="5" fill="#335b3e"/>'
                f'<text x="{x+12}" y="{y+36}" class="value">Intensity: 75</text>')
    if 'SLIDER' in show:
        return (f'<line x1="{x}" y1="{y+18}" x2="{x+290}" y2="{y+18}" stroke="#8fb99b" stroke-width="5"/>'
                f'<circle cx="{x+170}" cy="{y+18}" r="12" fill="#f1d487"/>')
    if cid == 'int-color':
        return f'<rect x="{x}" y="{y}" width="60" height="37" rx="5" fill="#6eb6c6"/><text x="{x+72}" y="{y+26}" class="value">#6EB6C6  ▾</text>'
    if 'RADIOBUTTONS' in show or cid == 'enum-toggle':
        return (f'<rect x="{x}" y="{y}" width="140" height="38" rx="7" fill="#e2efe1"/>'
                f'<rect x="{x+148}" y="{y}" width="140" height="38" rx="7" fill="#335b3e"/>'
                f'<text x="{x+13}" y="{y+26}" class="selectedtext">First</text><text x="{x+164}" y="{y+26}" class="value">Second</text>')
    if 'Bool' in kind:
        return (f'<rect x="{x}" y="{y}" width="65" height="37" rx="18" fill="#68aa72"/>'
                f'<circle cx="{x+46}" cy="{y+18}" r="14" fill="#f4f6ee"/><text x="{x+77}" y="{y+26}" class="value">On</text>')
    if cid in ('action',):
        return f'<rect x="{x}" y="{y}" width="290" height="39" rx="7" fill="#447a51"/><text x="{x+16}" y="{y+27}" class="value">Regenerate tank  →</text>'
    if cid in ('ref-readonly', 'int-readonly'):
        return f'<rect x="{x}" y="{y}" width="290" height="39" rx="7" fill="#30453a"/><text x="{x+13}" y="{y+26}" class="muted">Read only · {html.escape(c["sample"].split(" · ")[-1])}</text>'
    if 'Enum' in kind:
        return f'<rect x="{x}" y="{y}" width="290" height="39" rx="7" fill="#335b3e"/><text x="{x+13}" y="{y+26}" class="value">{html.escape(c["sample"].split(" · ")[-1][:25])}  ▾</text>'
    if cid == 'str-multiline':
        return f'<rect x="{x}" y="{y}" width="290" height="39" rx="7" fill="#335b3e"/><text x="{x+13}" y="{y+26}" class="value">Two-line description…  ✎</text>'
    return f'<rect x="{x}" y="{y}" width="290" height="39" rx="7" fill="#335b3e"/><text x="{x+13}" y="{y+26}" class="value">{html.escape(c["sample"].split(" · ")[-1][:24])}  ✎</text>'


def gallery():
    cols, width, height = 3, 380, 180
    rows = (len(CASES) + cols - 1) // cols
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {cols*width+30} {rows*height+80}" role="img" aria-labelledby="title desc">',
             '<title id="title">All sensible touch settings examples</title>',
             '<desc id="desc">Gallery of field presentations and edge cases from the table in the plan.</desc>',
             '<style>text{font-family:Arial,sans-serif}.title{font-size:23px;font-weight:bold;fill:#243f2e}.id{font-size:16px;font-weight:bold;fill:#f1f5ec}.meta{font-size:13px;fill:#b8cebd}.value{font-size:17px;fill:#f4f6ee}.selectedtext{font-size:17px;fill:#173222}.muted{font-size:16px;fill:#b8cebd}.card{fill:#142c20;stroke:#588168;stroke-width:2}.new{fill:#f4d990}.old{fill:#aad7af}</style>',
             '<text x="20" y="37" class="title">Field gallery · proposed phone touch treatment</text>']
    for index, c in enumerate(CASES):
        col, row = index % cols, index // cols
        x, y = 20 + col*width, 58 + row*height
        label = html.escape(c['id'])
        status = 'new presentation' if c['status'] == 'proposed' else 'current presentation'
        parts += [f'<g data-example="{label}"><rect class="card" x="{x}" y="{y}" width="355" height="158" rx="12"/>',
                  f'<text class="id" x="{x+16}" y="{y+28}">{label}</text>',
                  f'<text class="meta" x="{x+16}" y="{y+51}">{html.escape(c["type"])} · {html.escape(c["showAs"])}</text>',
                  f'<text class="meta" x="{x+16}" y="{y+75}">{html.escape(c["sample"][:43])}</text>',
                  control(c, x+18, y+86),
                  f'<text class="meta" x="{x+16}" y="{y+144}">{html.escape(c["touch"])} · {status}</text></g>']
    parts.append('</svg>')
    return '\n'.join(parts) + '\n'


def main():
    source = PLAN.read_text()
    assert source.count(START) == source.count(END) == 1
    before, rest = source.split(START, 1)
    _, after = rest.split(END, 1)
    PLAN.write_text(before + START + '\n' + table() + '\n' + END + after)
    SVG.write_text(gallery())
    print(f'{len(CASES)} examples: {PLAN} and {SVG}')


if __name__ == '__main__':
    main()
