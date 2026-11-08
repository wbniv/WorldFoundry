#!/usr/bin/env python3
"""Build the source-checked Gulf reef poster; refuse incomplete research."""
from __future__ import annotations

import argparse
import base64
from pathlib import Path
import re

from claims import CARDS, FISHES, HABITAT, SOURCES
from layout import (HTML_TEXT_PAIRS, PRINTABLE, PX_TO_PT, TEXT_PAIRS, UNITS,
                    FIT_SCRIPT, contrast, css, esc, polish)
import render

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent / 'thai-reef-research.md'


def all_claims():
    for c in HABITAT:
        yield 'habitat', c
    for card in CARDS:
        for c in card['claims']:
            yield card['name'], c
    for fish in FISHES:
        for c in fish['claims']:
            yield fish['name'], c


def printed_taxa():
    return {x['taxon'] for x in CARDS + FISHES if x.get('taxon')}


def source_order():
    seen = []
    for _, claim in all_claims():
        for key in claim.get('src', []):
            if key not in seen:
                seen.append(key)
    return seen


def check_claims():
    """Validate every claim and require the complete, reviewed research roster."""
    problems = []
    research = RESEARCH.read_text(encoding='utf-8') if RESEARCH.exists() else ''
    if 'Poster visual review: approved' not in research:
        problems.append('poster visual review is incomplete')
    if '## Final species list' not in research:
        problems.append('final researched species list is missing')
    else:
        section = research.split('## Final species list', 1)[1].split('\n## ', 1)[0]
        rows = []
        for line in section.splitlines():
            if line.startswith('|'):
                cells = [cell.strip().replace('*', '') for cell in line.strip().strip('|').split('|')]
                if len(cells) >= 4 and cells[0].isdigit():
                    rows.append(cells)
                    if re.search(r'\b(pending|unverified|unresolved)\b', cells[3], re.I):
                        problems.append('final species list contains unresolved entries')
        # The plan has 22 numbered invertebrate/builder roles and two fish taxa.
        # Keep dropped or swapped roles as rows so omissions cannot look complete.
        numbers = [int(row[0]) for row in rows]
        if sorted(numbers) != list(range(1, 25)):
            problems.append('final species list must decide all 22 numbered roles and both fish (rows 1–24)')
        for row in rows:
            if not re.match(r'^(yes|dropped|swapped)\b', row[3], re.I):
                problems.append(f'roster row {row[0]} has no final decision')
            elif re.match(r'^(yes|swapped)\b', row[3], re.I) and not any('https://' in cell for cell in row):
                problems.append(f'roster row {row[0]} has no linked Gulf source')
        for taxon in printed_taxa():
            # Column 3 is taxon and column 4 is its final yes/drop/swap decision.
            def approved(row):
                if row[2] == taxon and re.match(r'^yes\b', row[3], re.I):
                    return True
                match = re.match(r'^swapped to\s+([^;(]+)', row[3], re.I)
                return bool(match and match.group(1).strip() == taxon)
            if not any(approved(row) for row in rows):
                problems.append(f'{taxon}: not approved in final species list')
    for area, c in all_claims():
        status, refs = c.get('status'), c.get('src', [])
        if status not in PRINTABLE:
            problems.append(f'{area}: {status!r} may not print')
        if not c.get('text', '').strip():
            problems.append(f'{area}: empty {c.get("role", "claim")}')
        if status in ('verified', 'other-region') and not refs:
            problems.append(f'{area}: {status} without a source')
        for ref in refs:
            if ref not in SOURCES:
                problems.append(f'{area}: unknown source {ref}')
            elif SOURCES[ref]['url'] not in research:
                problems.append(f'{area}: source {ref} not in research')
        if c.get('role') == 'gulf' and status != 'verified':
            problems.append(f'{area}: Gulf record must be verified')
    for card in CARDS:
        if not card.get('taxon'):
            problems.append(f'{card["name"]}: taxon is unresolved')
    return problems


def build(*, draft=False):
    problems = check_claims()
    if draft:
        # A review draft may lack the finalized roster; every printed claim
        # must still have an accepted status, source and ledger entry.
        problems = [p for p in problems if p not in ('final researched species list is missing',
                                                      'poster visual review is incomplete')]
    if problems:
        raise SystemExit('poster claims incomplete:\n- ' + '\n- '.join(problems))
    order = source_order()
    num = {key: i for i, key in enumerate(order, 1)}
    used = {c['status'] for _, c in all_claims()}
    sites = [('Ko Tao', 99.84, 10.1, 'r'), ('Ko Samui', 100.03, 9.5, 'r'), ('Ko Chang', 102.35, 12.05, 'l')]
    svgs = {'01-tank.svg': render.tank_strip(), '02-map.svg': render.habitat_map(sites),
            '03-cards.svg': render.cards_sheet(CARDS), '04-humbug.svg': render.humbug_drawing(),
            '05-boxfish.svg': render.boxfish_drawing()}
    habitat = ('<div class="depth"><strong>45<span> m</span></strong><div>Average depth of this semi-enclosed sea '
               + render.chip_html(HABITAT[0]) + render.refs_html(HABITAT[0], num) + '</div></div>'
               '<div class="fact-columns">' + ''.join(render.claim_html(c, num, 'habitat') for c in HABITAT[1:]) + '</div>')
    # A few generated illustrations are unsuitable for a named taxon; retain
    # the schematic for those rather than presenting a misleading likeness.
    plate_positions = {'xmas': (0, 0), 'duster': (1, 0), 'clam': (3, 0),
                       'shrimp': (0, 1), 'nudi': (1, 1), 'hermit': (3, 1),
                       'table': (1, 2), 'gonio': (2, 2), 'sarco': (3, 2),
                       'tuba': (0, 3), 'sponge': (2, 3)}
    plate_path = HERE / 'reef-species-plate.png'
    plate = ('data:image/png;base64,' + base64.b64encode(plate_path.read_bytes()).decode('ascii')) if plate_path.is_file() else ''
    # Keys enter this map only after the corresponding illustration has been
    # visually checked against the named animal and the research ledger.
    reviewed_art = {'turbi': 'scroll-coral-illustration.png',
                    'crab': 'guard-crab-illustration-v2.png',
                    'humbug': 'humbug-illustration-v3.png',
                    'boxfish': 'boxfish-illustration.png'}
    individual_css = ''
    for key, path in reviewed_art.items():
        data = base64.b64encode((HERE / path).read_bytes()).decode('ascii')
        individual_css += f'.art-{key}{{background-image:url("data:image/png;base64,{data}")}}'
    def drawing(c):
        if c['draw'] in reviewed_art:
            return f'<span class="individual-art art-{c["draw"]}" role="img" aria-label="Artistic illustration of {esc(c["name"])}"></span>'
        pos = plate_positions.get(c['draw']) if plate else None
        if pos is None:
            return render.card_drawing(c['draw'], w=70, h=56)
        return (f'<span class="species-art" role="img" aria-label="Artistic illustration of {esc(c["name"])}" '
                f'style="background-position:{1.1364 + pos[0] * 32.5758:.4f}% {1.1364 + pos[1] * 32.5758:.4f}%"></span>')
    def card(c):
        gulf = c['claims'][0]
        return ('<article class="card"><div class="top">' + drawing(c) +
                '<div><div class="nm">' + esc(c['name']) + '</div><div class="lt">' + esc(c['taxon']) +
                '</div><div class="occur">' + render.chip_html(gulf) + ' Gulf' + render.refs_html(gulf, num) +
                '</div></div></div><div class="story">' + ''.join(render.claim_html(q, num, c['name']) for q in c['claims'][1:]) + '</div></article>')
    cards = ('<div class="group-title"><span>01</span> Creatures in motion</div><div class="cards">' +
             ''.join(card(c) for c in [c for c in CARDS if c['kind'] == 'moves']) + '</div><div class="group-title"><span>02</span> Reef builders &amp; guardians</div>' +
             '<div class="cards">' + ''.join(card(c) for c in [c for c in CARDS if c['kind'] != 'moves']) + '</div>')
    def fish_drawing(f):
        if f['key'] in reviewed_art:
            label = ('<span class="fish-caption top">fins row · tail steers</span>'
                     '<span class="fish-caption bottom">rigid body</span>') if f['key'] == 'boxfish' else ''
            return f'<span class="individual-art fish-art art-{f["key"]}" role="img" aria-label="Artistic illustration of {esc(f["name"])}">{label}</span>'
        return svgs['04-humbug.svg'] if f['key'] == 'humbug' else svgs['05-boxfish.svg']
    fishes = ''.join('<div class="fish">' + fish_drawing(f) +
                     '<div><div class="nm">' + esc(f['name']) + '</div><div class="lt">' + esc(f['taxon']) + '</div>' +
                     ''.join(render.claim_html(c, num, f['name']) for c in f['claims']) + '</div></div>' for f in FISHES)
    draft_css = ('.page{overflow:visible}.card{overflow:visible}'
                 '.draft-notice{background:#fff0c7;color:#4c2800;border:2px solid #9a4f00;'
                 'padding:12px;font-size:15px;font-weight:700;line-height:1.4;width:297mm} '
                 '@media print{.draft-notice{display:none}.page{position:relative}'
                 '.page:after{content:"REVIEW DRAFT · NOT APPROVED";position:absolute;'
                 'right:9mm;top:9mm;padding:3px 6px;font-size:11px;font-weight:bold;'
                 'color:#712500;background:#fff0c7;border:1px solid #712500}}') if draft else ''
    notice = ('<aside class="draft-notice">REVIEW DRAFT — not approved for print. '
              'The final species roster, model identities, illustration accuracy and page layout remain under review. '
              'Some biology is from other regions or related species; see each source and the research ledger.</aside>') if draft else ''
    hero_path = HERE / 'reef-hero-illustration.png'
    hero = ('<img class="hero" alt="Illustrated Gulf reef scene" src="data:image/png;base64,' +
            base64.b64encode(hero_path.read_bytes()).decode('ascii') + '">') if hero_path.is_file() else ''
    header_class = ' class="has-hero"' if hero else ''
    plate_css = ('.species-art{display:block;flex:none;width:70px;height:56px;'
                 'background-image:url("' + plate + '");background-size:430% 430%;mix-blend-mode:multiply}') if plate else ''
    plate_css += ('.individual-art{display:block;flex:none;width:70px;height:56px;'
                  'background-size:contain;background-position:center;background-repeat:no-repeat;mix-blend-mode:multiply}'
                  '.individual-art.fish-art{position:relative;width:170px;height:150px}'
                  '.fish-caption{position:absolute;left:2px;font-size:11px;line-height:13px;font-weight:700;color:#315865}'
                  '.fish-caption.top{top:0}.fish-caption.bottom{bottom:0}' + individual_css)
    doc = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><style>' + css() + plate_css + draft_css + '</style></head>'
           '<body>' + notice + '<main class="page"><header' + header_class + '>' + hero + '<div class="ttl"><h1>Reef of the Gulf of Thailand</h1>'
           '<div class="thai">แนวปะการังอ่าวไทย</div><div class="sub">A reef and its inhabitants · 2026-11-02</div></div>' +
           ('' if hero else svgs['01-tank.svg']) + '</header><section class="sec" id="panel-habitat"><div class="bar">The habitat</div>'
           '<div class="body">' + svgs['02-map.svg'] + '<div class="facts">' + habitat + '</div></div></section>'
           '<section class="sec"><div class="bar">Life without a backbone</div>' + cards +
           '</section><section class="sec"><div class="bar">The two fishes</div><div class="fishes">' + fishes +
           '</div></section><footer id="panel-src">' + render.legend_html(used) + render.sources_html(order, SOURCES, num) +
           '<div class="note">Research: thai-reef-research.md · Bangkok boundary: W. J. Reynolds / mapthai, CC BY 4.0 · Illustrations are artistic</div></footer></main>' + FIT_SCRIPT + '</body></html>')
    return polish(doc), svgs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, default=HERE)
    args = parser.parse_args(argv)
    doc, svgs = build()  # validate before creating or modifying any output
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / 'poster.html').write_text(doc, encoding='utf-8')
    for name, svg in svgs.items():
        (args.out_dir / name).write_text(svg, encoding='utf-8')


if __name__ == '__main__':
    main()
