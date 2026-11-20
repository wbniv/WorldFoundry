"""Regression guard for the Sea Stars A3 poster (docs/plans/2026-11-20-sea-stars-poster.md).

The poster is about the animals and their world. It states research facts, game-design choices and a
piece of the shipped Forth. Every research number must trace to the research file, every [n] must have
a source link, every game-design statement must be marked as such, and the Forth must be the real
autopilot. The exported layout must be one A3 page with a margin at the bottom.
"""
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
POSTER = ROOT/'docs/reference/sea-stars-biomechanics-poster'
RESEARCH = (ROOT/'docs/reference/sea-stars-research.md').read_text()
HTML = (POSTER/'poster.html').read_text()
LEVEL = ROOT/'wflevels/aquarium_sea_stars'

ANIMALS = (('Blue sea star', 'Linckia laevigata', '18 cm'), ('Chocolate-chip star', 'Protoreaster nodosus', '20 cm'),
           ('Red Fromia', 'Fromia milleporella', '8 cm'), ('Sand-sifting star', 'Archaster typicus', '11.2 cm'),
           ('Green brittle star', 'Ophiarachna incrassata', '3.8 cm disc'), ('Cushion star', 'Culcita novaeguineae', '14.4 cm'))


def body_text():
    footer = HTML.index('<footer>')
    return re.sub(r'<[^>]+>', ' ', HTML[HTML.index('<main'):footer])


def test_layout_is_one_a3_page_with_a_bottom_margin():
    review = json.loads((POSTER/'layout-review.json').read_text())
    assert review['pages'] == 1
    assert abs(review['page_mm'][0]-297) < 1.5 and abs(review['page_mm'][1]-420) < 1.5
    assert review['bottom_margin_mm'] >= 6, review          # the page clips, so overflow hides in the padding
    assert (POSTER/'sea-stars-biomechanics-a3.pdf').read_bytes().startswith(b'%PDF')


def test_the_six_animals_lead_the_poster():
    tiles = HTML[HTML.index('<section class="tiles">'):HTML.index('</section>', HTML.index('<section class="tiles">'))]
    assert tiles.count('<figure>') == 6
    for name, latin, size in ANIMALS:
        assert name in tiles and latin in tiles and size in tiles, name
        assert latin.split()[0] in RESEARCH, latin
    # The animals come before every diagram panel.
    assert HTML.index('<section class="tiles">') < HTML.index('<div class="row">')
    for image in re.findall(r'<img src="(tiles/[^"]+)"', tiles):
        assert (POSTER/image).exists(), image


def test_every_citation_has_a_source_and_every_source_is_cited():
    footer = HTML[HTML.index('<footer>'):]
    sources = set(re.findall(r'\[(\d+)\] ', footer))
    cited = {n for group in re.findall(r'\[(\d+(?:,\d+)*)\]', body_text()) for n in group.split(',')}
    assert cited <= sources, f'cited without a source: {sorted(cited-sources)}'
    assert sources <= cited, f'source never cited: {sorted(sources-cited)}'
    for url in re.findall(r'<a href="(https://[^"]+)">\[\d', footer):
        assert url in RESEARCH, f'{url} is not in sea-stars-research.md'


def test_research_numbers_match_the_research_file():
    text = body_text()
    for value in ('8.1', '18.8', '45.8'):                    # Mueller et al. 2011 mean speeds, cm/min
        assert f'{value} cm a minute' in text and value in RESEARCH, value
    assert 'multiplied by 30, 20 and 20' in text
    assert '16 joints' in text and '16 joints per arm' in RESEARCH and '15 cm' in text and '34 cm' in text
    assert '9 to 18 cm' in text and '9–18 cm' in RESEARCH       # seagrass tufts


def test_game_design_is_marked_as_such():
    game = ' '.join(re.sub(r'<[^>]+>', '', g) for g in re.findall(r'<(?:p|span) class="game">(.*?)</(?:p|span)>', HTML, re.S))
    for phrase in ('multiplied by 30, 20 and 20', 'two-second reach', 'authored, not measured', 'readability choice',
                   'Rests 20 to 60 s', 'Creeps along the three rocks', 'Hides under the ledges', 'five planes'):
        assert phrase in game, f'{phrase!r} is game design and must be set in the amber class'


def test_the_forth_on_the_poster_is_the_shipped_autopilot():
    shipped = ' '.join((LEVEL/'sea_stars_screensaver.fth').read_text().split())
    block = html.unescape(re.search(r'<pre>(.*?)</pre>', HTML, re.S).group(1))
    lines = [' '.join(l.split()) for l in block.splitlines() if l.strip() and '...' not in l]
    assert len(lines) >= 6
    for line in lines:
        assert line in shipped, f'not in the shipped autopilot: {line!r}'
    # The five planes the diagram labels are the ones the player script defines.
    header = (LEVEL/'sea_star_player.fth').read_text().splitlines()[0]
    assert 'surface id 0 sand, 1 front, 2 right, 3 back, 4 left' in header
    planes = (POSTER/'planes.svg').read_text()
    for label in ('0 sand', '1 front', '2 right', '3 back', '4 left'):
        assert label in planes
