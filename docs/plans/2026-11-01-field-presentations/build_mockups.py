#!/usr/bin/env python3
"""Write the field-presentation mockups (self-contained HTML, 1440x900) and their PNGs.

Colours and proportions follow wfsource/source/game/runtime_property_ui.cc (TV, a 1920x1080
canvas drawn here at 0.7) and runtime_property_touch.cc (phone, dp). Run from anywhere:
    python3 docs/plans/2026-11-01-field-presentations/build_mockups.py
"""
import html
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = html.escape

CSS = """*{box-sizing:border-box;margin:0;padding:0}body{width:1440px;height:900px;background:#061014;
font-family:'DejaVu Sans',Arial,sans-serif;color:#f1f2e4;overflow:hidden;position:relative}
.cap{position:absolute;left:24px;right:24px;bottom:10px;font-size:15px;color:#9eb1a7}
.tv{position:absolute;left:48px;top:40px;width:1344px;height:756px;background:#061014;border:2px solid #24352d}
.panel{position:absolute;left:126px;top:77px;width:1092px;height:574px;background:#142d25}
.title{position:absolute;left:158px;top:93px;font-size:32px;font-weight:600}
.rail{position:absolute;left:158px;width:231px;height:48px;background:#233e31;font-size:24px;padding:10px 13px}
.rail.on{background:#497b51}
.row{position:absolute;left:420px;width:756px;background:#233e31;font-size:24px;padding:0 13px;display:flex;align-items:center;gap:12px}
.row.focus{background:#497b51}.row .lab{flex:0 0 auto}.row .val{color:#f1f2e4}
.box{background:#102621;border:1px solid #5d7d66;padding:4px 10px;font-size:22px;display:flex;align-items:center;gap:10px;margin-left:auto;min-width:330px}
.chev{width:0;height:0;border-left:8px solid transparent;border-right:8px solid transparent;border-top:10px solid #e4efd9;margin-left:auto}
.id{background:#e4efd9;color:#132b26;font-size:19px;padding:1px 8px;font-weight:700}
.seg{display:flex;gap:8px;margin-left:auto}.seg span{background:#19382d;padding:4px 18px;font-size:21px}.seg span.on{background:#e4efd9;color:#132b26}
.pill{width:64px;height:30px;border-radius:15px;background:#68aa72;position:relative;margin-left:auto}.pill i{position:absolute;right:3px;top:3px;width:24px;height:24px;border-radius:12px;background:#f4f6ee}
.pill.off{background:#5d6b63}.pill.off i{right:auto;left:3px}
.bounds{margin-left:auto;color:#cbd4ba;font-size:19px}
.file{width:18px;height:22px;background:#cbd4ba;clip-path:polygon(0 0,70% 0,100% 30%,100% 100%,0 100%)}
.dim{color:#9eb1a7}
.hint{position:absolute;left:158px;top:612px;font-size:19px;color:#ffdd99}
.help{position:absolute;left:420px;top:553px;font-size:15px;color:#b6c7ba}
.group{position:absolute;left:424px;font-size:18px;color:#cbd4ba}
.list{position:absolute;left:640px;top:150px;width:520px;background:#0d1f1a;border:2px solid #e4efd9;padding:10px}
.opt{font-size:22px;padding:8px 12px;margin:4px 0;background:#19382d;display:flex;gap:12px;align-items:flex-start;line-height:1.25}
.opt.focus{background:#497b51}.opt.sel::after{content:'';margin-left:auto;width:12px;height:12px;background:#efce83;flex:0 0 12px;margin-top:6px}
.chips{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;margin-top:6px}.chips span{background:#19382d;font-size:17px;padding:3px 6px}.chips span.on{background:#e4efd9;color:#132b26}
.err{color:#ffdd99}
.phone{position:absolute;top:30px;width:400px;height:820px;background:#061014;border:10px solid #2a2f2c;border-radius:34px;overflow:hidden}
.ph-title{position:absolute;left:18px;top:24px;font-size:22px;font-weight:700}
.ph-sec{position:absolute;left:16px;right:16px;top:64px;height:52px;background:#497b51;font-size:17px;padding:14px}
.card{position:absolute;left:16px;right:16px;height:72px;background:#233e31;padding:8px 13px}
.card .l{font-size:16px;font-weight:700}.card .v{font-size:15px;color:#b6c7ba;margin-top:6px;display:flex;align-items:center;gap:8px}
.card .grp{font-size:11px;color:#efce83}
.foot{position:absolute;left:0;right:0;bottom:0;height:86px;background:#142d25;display:flex;gap:10px;padding:14px 16px}
.foot span{flex:1;background:#233e31;font-size:17px;padding:16px 14px}.foot span.ap{background:#497b51}
.sheet{position:absolute;left:16px;right:16px;font-size:16px;background:#233e31;padding:10px 14px;line-height:1.3}
.sheet.on{background:#497b51}
.tick{width:26px;height:26px;border:2px solid #e4efd9;margin-left:auto;display:flex;align-items:center;justify-content:center;font-size:18px}
.lbl{position:absolute;top:2px;font-size:14px;color:#9eb1a7}
"""


def page(name, body, caption):
    doc = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=1440">'
           f'<title>{E(name)}</title><style>{CSS}</style></head><body>{body}<div class="cap">{E(caption)}</div></body></html>')
    (HERE / (name + '.html')).write_text(doc)


def tv(title, section, rails, rows, hint, extra='', help_text=''):
    out = ['<div class="tv"></div><div class="panel"></div>', f'<div class="title">{E(title)}</div>']
    for i, r in enumerate(rails):
        out.append(f'<div class="rail{" on" if r == section else ""}" style="top:{168 + i * 60}px">{E(r)}</div>')
    for top, height, cls, inner in rows:
        out.append(f'<div class="row {cls}" style="top:{top}px;height:{height}px">{inner}</div>')
    out.append(f'<div class="hint">{E(hint)}</div>')
    if help_text:
        out.append(f'<div class="help">{E(help_text)}</div>')
    out.append(extra)
    return ''.join(out)


RAILS = ['Numbers', 'Choices', 'Switches', 'Text', 'References', 'Actions']
CHEV = '<span class="chev"></span>'


def box(value, numbered=None, wrap=False):
    ident = f'<span class="id">{numbered}</span>' if numbered is not None else ''
    style = ' style="white-space:normal;line-height:1.2;max-width:420px"' if wrap else ''
    return f'<span class="box"{style}>{ident}<span>{E(value)}</span>{CHEV}</span>'


def choices_rows(focus):
    rows, y = [], 168
    spec = [
        ('Mode', box('Calm'), 51), ('Powerup', box('Flying', 2), 51), ('Water type', box('Freshwater'), 51),
        ('Habitat', '<span class="seg"><span class="on">Freshwater</span><span>Saltwater</span></span>', 51),
        ('Direction', '<span class="seg"><span class="on">Forward</span><span>Reverse</span></span>', 51),
        ('Tool', box('Staff'), 51),
        ('Placement', box('Along the northern wall, facing the glass', wrap=True), 70)]
    for i, (label, ctrl, h) in enumerate(spec):
        rows.append((y, h, 'focus' if i == focus else '', f'<span class="lab">{E(label)}</span>{ctrl}'))
        y += h + 9
    return rows


def build():
    # 1. TV, Choices closed: the new choice boxes, segments and the wrapped box.
    page('tv-choices', tv('Field types', 'Choices', RAILS, choices_rows(1),
                          'Left / right: change   A: open list',
                          help_text='(Growth, the stepped slider, and Species, the twelve chips, sit below; unchanged.)'),
         'TV, Choices, list closed. Mode, Powerup, Water type, Tool and Placement are choice boxes. With 2 to 4 options (all of these) Left / Right '
         'cycle and Left on the first option goes to the sections; with 5 or more only A opens the list. A opens it either way. '
         'Powerup shows its id; Placement wraps to two lines; Direction and Habitat are two segments.')
    # 2. TV, numbered list open (enum-number).
    opts = ''.join(f'<div class="opt{" focus sel" if i == 2 else ""}"><span class="id">{i}</span><span>{v}</span></div>'
                   for i, v in enumerate(['None', 'Speed', 'Flying', 'Shield']))
    page('tv-list-numbered', tv('Field types', 'Choices', RAILS, choices_rows(1),
                                'Up / down: choose   A: select   Back: close',
                                extra=f'<div class="list"><div style="font-size:22px;margin:2px 4px 8px">Powerup</div>{opts}</div>'),
         'TV, Powerup list open (enum-number, NUMBER): each option carries its numeric id. A selects into the draft; Back or Left '
         'closes the list without a change. Nothing is applied until the form is applied.')
    # 3. TV, wrapping list open (enum-long).
    longs = ['Along the northern wall, facing the glass', 'In the middle of the tank, under the light',
             'Beside the filter intake, behind the rocks']
    opts = ''.join(f'<div class="opt{" focus sel" if i == 0 else ""}"><span>{E(v)}</span></div>' for i, v in enumerate(longs))
    page('tv-list-wrapping', tv('Field types', 'Choices', RAILS, choices_rows(6),
                                'Up / down: choose   A: select   Back: close',
                                extra=f'<div class="list" style="top:230px;width:440px"><div style="font-size:22px;margin:2px 4px 8px">Placement</div>{opts}</div>'),
         'TV, Placement list open (enum-long): an option longer than one line wraps instead of being cut. The list is the same '
         'control as Mode and Tool; wrapping is decided per label from its measured width.')
    # 4. TV, Numbers: mailbox bounds (new) and the group/help row (kept).
    rows = [(168, 51, '', '<span class="lab">Hold seconds: 120</span>'),
            (228, 51, 'focus', '<span class="lab">Trigger mailbox: 100</span><span class="bounds">0 – 159</span>'),
            (288, 51, '', '<span class="lab">Count: 7</span>'),
            (378, 51, '', '<span class="lab">Intensity: 75</span>')]
    page('tv-numbers', tv('Field types', 'Numbers', RAILS, rows, 'Arrows: select   A: edit',
                          extra='<div class="group" style="top:352px">Lighting</div>',
                          help_text='Mailbox number from 0 to 159'),
         'TV, Numbers: Trigger mailbox (MAILBOX) shows its bounds beside the value; the editor opened with A is titled '
         '"Trigger mailbox (0 – 159)". Intensity keeps its "Lighting" group heading and help line (kept, unchanged).')
    # 5. TV, Switches: checkbox (unchanged) and the new switch.
    rows = [(168, 51, '', '<span class="lab">Textures: On</span>'),
            (228, 51, 'focus', '<span class="lab">Sway</span><span class="pill"><i></i></span><span>On</span>')]
    page('tv-switches', tv('Field types', 'Switches', RAILS, rows, 'Up / down: select   Left / right: change'),
         'TV, Switches: Sway (Bool, TOGGLE) is a switch, no longer the number row "Sway: 1". Left / Right set Off / On and A flips it, '
         'as on the checkbox; Left at Off goes to the sections, so the row never traps focus.')
    # 6. TV, Text: path row, and its validation error.
    rows = [(168, 51, '', '<span class="lab">Caption: Garden</span>'),
            (228, 51, '', '<span class="lab">Seed: 4294967295</span>'),
            (288, 51, '', '<span class="lab">Notes: Two-line description Second line</span>'),
            (348, 51, 'focus', '<span class="lab">Asset path</span><span class="box" style="min-width:380px"><span class="file"></span>'
                               '<span><span class="dim">plants/</span>leaf.png</span></span>')]
    page('tv-path-error', tv('Field types', 'Text', RAILS, rows, 'Enter a relative path: names separated by /'),
         'TV, Text: Asset path (FILENAME) draws a file mark with the folder dimmed and the file name bright. An entry such as '
         '"../x" stays in the draft like any invalid value, and Apply is refused with the engine\'s message; the form stays open.')
    # 7. Phone: Choices, numbered sheet, wrapping sheet.
    def phone(left, title, inner):
        return (f'<div class="phone" style="left:{left}px"><div class="ph-title">{E(title)}</div>{inner}'
                '<div class="foot"><span>Cancel</span><span class="ap">Apply</span></div></div>')
    cards = [('Mode', box_v('Calm')), ('Powerup', '<span class="id">2</span> Flying ▾'), ('Water type', box_v('Freshwater')),
             ('Direction', '<span class="seg" style="margin-left:0"><span class="on">Forward</span><span>Reverse</span></span>'),
             ('Tool', box_v('Staff')), ('Species', 'Choice 4 ▾'), ('Placement', 'Along the northern wall, fa… ▾')]
    a = '<div class="ph-sec">Section: Choices ▾</div>' + ''.join(
        f'<div class="card" style="top:{130 + i * 82}px"><div class="l">{E(l)}</div><div class="v">{v}</div></div>' for i, (l, v) in enumerate(cards))
    b = '<div style="position:absolute;left:18px;top:64px;font-size:15px;color:#b6c7ba">Powerup</div>' + ''.join(
        f'<div class="sheet{" on" if i == 2 else ""}" style="top:{92 + i * 62}px"><span class="id">{i}</span> {v}</div>'
        for i, v in enumerate(['None', 'Speed', 'Flying', 'Shield']))
    c = '<div style="position:absolute;left:18px;top:64px;font-size:15px;color:#b6c7ba">Placement</div>' + ''.join(
        f'<div class="sheet{" on" if i == 0 else ""}" style="top:{92 + i * 82}px">{E(v)}</div>' for i, v in enumerate(longs))
    page('phone-choices', phone(40, 'Field types', a) + phone(520, 'Field types', b) + phone(1000, 'Field types', c),
         'Phone (portrait, 390 dp): Choices cards; the Powerup sheet with numeric ids; the Placement sheet, whose long options '
         'wrap to two lines instead of ending in "...". Direction stays two tappable segments; Species opens the scrollable sheet (kept).')
    # 8. Phone: mailbox bounds + help, checkbox vs switch, path error.
    a = ('<div class="ph-sec">Section: Numbers ▾</div>'
         '<div class="card" style="top:130px"><div class="l">Trigger mailbox</div><div class="v">100<span class="bounds">0 – 159</span></div></div>'
         '<div class="card" style="top:212px"><div class="grp">Lighting</div><div class="l">Intensity</div><div class="v">75</div></div>'
         '<div style="position:absolute;left:18px;bottom:100px;font-size:14px;color:#b6c7ba">How bright the lights are; 0 is off.</div>')
    b = ('<div class="ph-sec">Section: Switches ▾</div>'
         '<div class="card" style="top:130px"><div class="l">Textures</div><div class="v">On<span class="tick">✓</span></div></div>'
         '<div class="card" style="top:212px"><div class="l">Sway</div><div class="v">On<span class="pill"><i></i></span></div></div>')
    c = ('<div class="ph-sec">Section: Text ▾</div>'
         '<div class="card" style="top:130px"><div class="l">Caption</div><div class="v">Garden</div></div>'
         '<div class="card" style="top:212px;background:#497b51"><div class="l">Asset path</div><div class="v"><span class="file"></span>'
         '<span class="dim">plants/</span>leaf.png</div></div>'
         '<div style="position:absolute;left:18px;bottom:100px;font-size:14px;color:#efce83">Enter a relative path: names separated by /</div>')
    page('phone-numbers-switches-text', phone(40, 'Field types', a) + phone(520, 'Field types', b) + phone(1000, 'Field types', c),
         'Phone: Trigger mailbox shows its bounds (the native editor is titled with them); Intensity keeps its group label and help (kept). '
         'Textures is a checkbox, Sway a switch. Asset path draws the file mark; an invalid path shows the engine error above the footer.')


def box_v(value):
    return f'{E(value)} ▾'


def shoot():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={'width': 1440, 'height': 900})
        for f in sorted(HERE.glob('*.html')):
            pg.goto(f.as_uri())
            pg.screenshot(path=str(f.with_suffix('.png')))
        browser.close()


if __name__ == '__main__':
    build()
    shoot()
    for f in sorted(HERE.glob('*.html')):
        print(f.name, f.stat().st_size, f.with_suffix('.png').stat().st_size)
