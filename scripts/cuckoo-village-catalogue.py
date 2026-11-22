#!/usr/bin/env python3
"""Build the Cuckoo Village parts catalogue: an HTML page and a PDF that say what every part of the village is.

    python3 scripts/cuckoo-village-catalogue.py [--render-dir DIR] [--out DIR] [--no-pdf] [-h]

Needs the pictures first (Blender, in the container; about twenty minutes on the CPU):

    WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh bash -c \\
        'export CARGO_HOME=/build/cargo-home CUCKOO_CATALOGUE=/src/build/cuckoo-catalogue; \\
         blender --background --python-exit-code 1 --python wflevels/cuckoo_village/blender_create_cuckoo_village.py'

`CUCKOO_CATALOGUE_ONLY=id,id` limits the render to some cards; CUCKOO_INVENTORY=<file> writes the actor inventory the page's totals
and the coverage test read (docs/reference/cuckoo-village-parts/inventory.json).

One card per entry of wflevels/cuckoo_village/catalogue_entries.py (the texts live there): the part on its own, where it is in the village
or the tower (the part in magenta, ringed when it is small) and a wireframe. Writes index.html, cuckoo-village-parts.pdf (headless
Chrome) and img/ into --out (default docs/reference/cuckoo-village-parts/).
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels" / "cuckoo_village"))
import catalogue_entries as ce  # noqa: E402

NB = " "           # a non-breaking space binds a number to its unit
W, H = 560, 420

CSS = """
:root { color-scheme: dark; font: 14px/1.5 system-ui, sans-serif; background: #171b20; color: #eeeae1; }
* { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
body { margin: 0 auto; max-width: 1360px; padding: 1rem clamp(1rem, 3vw, 3rem) 3rem; }
a { color: #dbbf83; }
h1 { font: 700 clamp(2rem, 4vw, 3rem)/1.1 Georgia, serif; margin: 1rem 0 .4rem; }
h2 { font: 700 1.7rem/1.2 Georgia, serif; border-bottom: 1px solid #716655; padding-bottom: .3rem; margin: 2.4rem 0 1rem; break-after: avoid; }
h3 { font: 700 1.2rem/1.2 Georgia, serif; margin: 0 0 .5rem; break-after: avoid; }
.intro { max-width: 78ch; color: #d7d4ca; }
nav { display: flex; flex-wrap: wrap; gap: .45rem; margin: 1rem 0; }
nav a { border: 1px solid #75684d; border-radius: 99px; padding: .2rem .7rem; text-decoration: none; font-size: .85rem; }
table { border-collapse: collapse; margin: .6rem 0 1rem; font-size: .88rem; }
th, td { border: 1px solid #42484b; padding: .25rem .6rem; text-align: left; vertical-align: top; }
th { background: #242a30; }
td.n { text-align: right; font-variant-numeric: tabular-nums; }
.card { background: #242a30; border: 1px solid #42484b; border-radius: .6rem; padding: .8rem; margin: 0 0 1rem; break-inside: avoid; }
.views { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .4rem; }
.views.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
figure { margin: 0; min-width: 0; position: relative; }
figure img, figure svg { display: block; width: 100%; height: auto; background: #e9edf1; border-radius: .25rem; }
figure .ring { position: absolute; inset: 0; width: 100%; height: 100%; background: none; pointer-events: none; }
figcaption { text-align: center; font-size: .75rem; margin-top: .15rem; color: #bdbab0; }
.chips { display: flex; flex-wrap: wrap; gap: .3rem; margin: .5rem 0 .2rem; }
.chip { font: .72rem/1.3 ui-monospace, monospace; background: #171b20; border: 1px solid #42484b; border-radius: 99px; padding: .1rem .55rem; color: #d7d4ca; }
.what { margin: .4rem 0; }
.card ul { margin: .3rem 0 .3rem 1.1rem; padding: 0; }
.meta { font-size: .82rem; color: #c9c6bb; margin: .2rem 0 0; }
.meta b { color: #eeeae1; }
.missing { display: grid; place-items: center; aspect-ratio: 4 / 3; background: #2b3138; color: #8d928f; font-size: .75rem; border-radius: .25rem; }
@page { size: A4; margin: 10mm; }
@media print { body { max-width: none; padding: 0; } nav { display: none; } .card { margin-bottom: 4mm; } h2 { margin-top: 6mm; } }
"""


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def size_text(size_m) -> str:
    dims = [d for d in size_m]
    parts = [f"{d:.2f}".rstrip("0").rstrip(".") for d in dims]
    return f"{parts[0]} × {parts[1]} × {parts[2]}{NB}m"


def ring_svg(box) -> str:
    """A magenta ring round a small highlighted part, so it can be found in the whole-village picture."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if max(x1 - x0, y1 - y0) >= 70:
        return ""
    r = max(20.0, max(x1 - x0, y1 - y0) / 2 + 12)
    return (f'<svg class="ring" viewBox="0 0 {W} {H}"><circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.0f}" fill="none" stroke="#ff29d6" stroke-width="3"/>'
            f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r + 4:.0f}" fill="none" stroke="#171b20" stroke-width="1" stroke-opacity=".5"/></svg>')


def picture(rel: str, alt: str, have: bool) -> str:
    if not have:
        return f'<div class="missing">{esc(alt)}: not rendered</div>'
    return f'<img src="{rel}" alt="{esc(alt)}" loading="lazy">'


def card(entry: dict, stats: dict | None, svg_text: str | None, have_iso: bool, have_ctx: bool) -> str:
    eid = entry["id"]
    chips = [entry["kind"] if entry["kind"] != "section" else "a piece of a bigger mesh"]
    if stats:
        tris = stats["triangles"]
        chips.append(f"{tris:,} triangles".replace(",", NB) if stats["instances"] == 1 else f"{tris:,} triangles each".replace(",", NB))
        chips.append(size_text(stats["size_m"]))
        if stats["instances"] > 1:
            chips.append(f"{stats['instances']} of them")
    if entry["kind"] == "engine":
        views = ""
        chips = ["engine object"]
    else:
        iso_cap = "Shaded, on its own" if entry["kind"] != "section" else "This piece, on its own"
        ctx_cap = "Where it is (magenta)"
        cells = [f"<figure>{picture(f'img/{eid}-iso.png', entry['title'], have_iso)}<figcaption>{iso_cap}</figcaption></figure>",
                 f"<figure>{picture(f'img/{eid}-ctx.png', entry['title'], have_ctx)}{ring_svg(stats['ctx_box']) if stats and stats.get('ctx_box') else ''}"
                 f"<figcaption>{ctx_cap}</figcaption></figure>"]
        if entry.get("wire"):
            body = svg_text if svg_text else f'<div class="missing">wireframe: not rendered</div>'
            cells.append(f"<figure>{body}<figcaption>Wireframe, hidden lines removed</figcaption></figure>")
        views = f'<div class="views{"" if len(cells) == 3 else " two"}">' + "".join(cells) + "</div>"
    bullets = "".join(f"<li>{esc(d)}</li>" for d in entry["details"])
    return (f'<article class="card" id="{eid}"><h3>{esc(entry["title"])}</h3>{views}'
            f'<div class="chips">' + "".join(f'<span class="chip">{esc(c)}</span>' for c in chips) + "</div>"
            f'<p class="what">{esc(entry["what"])}</p>' + (f"<ul>{bullets}</ul>" if bullets else "") +
            f'<p class="meta"><b>Shown:</b> {esc(entry["shown"])} <b>Moves:</b> {esc(entry["moves"])}'
            + (f' <b>Actors:</b> {esc(", ".join(entry["actors"][:3]))}{" …" if len(entry["actors"]) > 3 else ""}' if entry["kind"] != "engine" else "") + "</p></article>")


GLOSSARY = [
    ("Actor", "One thing the engine draws or runs: a mesh with a place, or an invisible helper such as the camera. The village has 102."),
    ("Mesh and triangle", "A mesh is a shape made of flat triangles; the number of triangles is what costs the graphics chip time. Thirteen cottages share one mesh, so it is stored once."),
    ("Atlas", "The one picture (4 × 4 tiles: wood, plaster, roof tile, stone, pine, gold, skin, …) that nearly every part is painted from, to keep the village within the Chromecast's texture budget."),
    ("Visibility mailbox", "A numbered cell a part watches. 1 means always shown; the director writes 1 or 0 into the others to switch parts on and off (windows 200–212, bird 213, candles 214–226, flowers 227, blocks 228, Bavarian parts 230, Classic parts 231)."),
    ("Director", "The small script that runs every frame. It poses the moving parts and switches the others from the wall clock alone, with no stored state, so a start at any time shows the right picture."),
    ("Setting", "One row of the settings form (hold A on a television): Bavaria mode, Seasonal events, Candles all year, Window lights, Sound, Camera motion and Detailed flowers."),
]

WHEN = [
    ("Every minute and hour", "The minute and hour hands turn (the other way round in Bavaria mode)."),
    ("On the hour", "The cuckoo appears and calls once for each hour; the four figures step out and walk the parade oval on the balcony for 24 seconds (the other way round in Bavaria mode)."),
    ("15, 30 and 45 minutes past", "Figures 1, 2 and 3 step out alone for 8 seconds."),
    ("Dusk to dawn", f"Cottage windows glow, one house after another: from 17:30 over an hour, and back off from 05:30 over an hour."),
    ("1 December to 6 January", "Candles light on the pines (all year when Candles all year is On)."),
    ("Always", "The camera journeys round the village and the tower (unless Camera motion is Still)."),
]


def build_html(stats: dict, render_dir: Path, inventory: list | None) -> str:
    entries = ce.ENTRIES
    groups = []
    for e in entries:
        if e["group"] not in groups:
            groups.append(e["group"])
    tri = {o["name"]: o.get("triangles", 0) for o in inventory} if inventory else {}
    rows = []
    for g in groups:
        es = [e for e in entries if e["group"] == g]
        actors = sorted({n for e in es for n in e["actors"]})
        rows.append((g, len(es), len(actors), sum(tri.get(n, 0) for n in actors) if tri else None))
    summary = "".join(f"<tr><td><a href=\"#g{i}\">{esc(g)}</a></td><td class=\"n\">{c}</td><td class=\"n\">{a}</td><td class=\"n\">{('{:,}'.format(t)).replace(',', NB) if t is not None else ''}</td></tr>"
                      for i, (g, c, a, t) in enumerate(rows))
    total_actors = len(inventory) if inventory else sum(r[2] for r in rows)
    out = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
           f"<title>Cuckoo Village · what every part is</title><style>{CSS}</style></head><body><header>"
           f'<h1>Cuckoo Village: what every part is</h1>'
           f'<p class="intro">A model village on a hill, with a carved cuckoo-clock tower in the middle: a glockenspiel clock whose hands turn, whose figures walk out on the hour and whose bird calls. '
           f"This catalogue shows every part of the level, {total_actors} actors in {len(entries)} cards. Each card shows the part on its own, where it sits (in magenta, ringed when it is small) and its wireframe, and says what it is, "
           f'what shows it and what moves it. Pictures are Blender renders of the level\'s own meshes under neutral light, not engine frames; the engine\'s dusk and night lighting colours them differently.</p>'
           f'<p class="intro">Generated 2026‑11‑22 by <code>scripts/cuckoo-village-catalogue.py</code> from the built level; the texts are in <code>wflevels/cuckoo_village/catalogue_entries.py</code>. '
           f'A test checks that every actor in the level has a card.</p>'
           f'<h2 id="numbers" style="margin-top:1.2rem">The village at a glance</h2><table><tr><th>Section</th><th>Cards</th><th>Actors</th><th>Triangles</th></tr>{summary}</table>'
           f'<h2>What happens when</h2><table>' + "".join(f"<tr><th>{esc(a)}</th><td>{esc(b)}</td></tr>" for a, b in WHEN) + "</table>"
           f'<h2>Words used on the cards</h2><table>' + "".join(f"<tr><th>{esc(a)}</th><td>{esc(b)}</td></tr>" for a, b in GLOSSARY) + "</table>"
           f'<nav aria-label="Sections">' + "".join(f'<a href="#g{i}">{esc(g)}</a>' for i, g in enumerate(groups)) + "</nav></header><main>"]
    for i, g in enumerate(groups):
        out.append(f'<section><h2 id="g{i}">{esc(g)}</h2>')
        for e in [x for x in entries if x["group"] == g]:
            svg_file = render_dir / f"{e['id']}-wire.svg"
            svg_text = svg_file.read_text() if svg_file.is_file() else None
            out.append(card(e, stats.get(e["id"]), svg_text, (render_dir / f"{e['id']}-iso.png").is_file(), (render_dir / f"{e['id']}-ctx.png").is_file()))
        out.append("</section>")
    out.append("</main></body></html>")
    return "\n".join(out)


def compress(src: Path, dst: Path) -> None:
    """A palette PNG: the renders are flat-shaded, so 160 colours lose nothing visible and cut a card's pictures to a tenth."""
    from PIL import Image
    im = Image.open(src).convert("RGB")
    im.quantize(colors=160, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(dst, optimize=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--render-dir", type=Path, default=ROOT / "build" / "cuckoo-catalogue")
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "reference" / "cuckoo-village-parts")
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args(argv)
    views = args.render_dir / "views.json"
    stats = json.loads(views.read_text()) if views.is_file() else {}
    inv_file = args.out / "inventory.json"
    inventory = json.loads(inv_file.read_text()) if inv_file.is_file() else None
    (args.out / "img").mkdir(parents=True, exist_ok=True)
    for png in sorted(args.render_dir.glob("*.png")):
        compress(png, args.out / "img" / png.name)
    # the wireframes are inlined from the render dir
    if args.render_dir != args.out / "img":
        for svg in args.render_dir.glob("*.svg"):
            shutil.copyfile(svg, args.out / "img" / svg.name)
    page = build_html(stats, args.out / "img", inventory)
    (args.out / "index.html").write_text(page, encoding="utf-8")
    print(f"index.html: {len(ce.ENTRIES)} cards, {len(stats)} with measurements")
    if args.no_pdf:
        return 0
    pdf = args.out / "cuckoo-village-parts.pdf"
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        print("no headless Chrome: skipped the PDF", file=sys.stderr)
        return 0
    subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}",
                    (args.out / "index.html").resolve().as_uri()], check=True, capture_output=True, timeout=600)
    print(f"{pdf.name}: {pdf.stat().st_size // 1024} KiB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
