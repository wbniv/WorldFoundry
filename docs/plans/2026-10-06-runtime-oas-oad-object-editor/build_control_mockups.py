"""Review schematics for section/group policies; no runtime layout changes."""
from pathlib import Path
from build_plan import svg, text, box
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
content = text(28, 37, 'Sections and groups · three layout alternatives', 25)
content += text(28, 68, 'Same schema: General / Appearance / Motion. Appearance contains Colour and Labels.', 16)
for index, (title, note) in enumerate([
    ('A · Section navigation', 'Rail on TV/editor; section selector on phone. Groups are headings.'),
    ('B · Tabs and group cards', 'Horizontal section tabs. Groups have visible boundaries.'),
    ('C · Accordion sections', 'Expand a section in the document. Nested groups retain their labels.'),
]):
    y = 102 + index * 365
    content += text(28, y + 25, title, 22) + text(28, y + 53, note, 16)
    for host, x, width in [('TV', 28, 480), ('Phone', 526, 225), ('wf-edit / Blender', 769, 303)]:
        content += box(x, y + 70, width, 264, host, fill='#173c35')
        top = y + 113
        if index == 0:
            if host == 'Phone':
                content += box(x + 12, top, width - 24, 36, 'Appearance ▾', fill='#397559')
                left, body, bw = x + 12, top + 64, width - 24
            else:
                for k, name in enumerate(['General', 'Appearance', 'Motion']):
                    content += box(x + 10, top + k * 42, 112, 36, name, fill='#397559' if k == 1 else '#244b40')
                left, body, bw = x + 132, top + 12, width - 144
        elif index == 1:
            names = ['General', 'Appearance', 'Motion'] if host == 'TV' else ['Gen.', 'Appear.', 'Motion']
            cell = (width - 20) / 3
            for k, name in enumerate(names):
                content += f'<rect x="{x+10+k*cell}" y="{top}" width="{cell-3}" height="34" rx="5" fill="'+('#397559' if k==1 else '#244b40')+'"/>'
                content += text(x + 14 + k * cell, top + 23, name, 13)
            left, body, bw = x + 14, top + 66, width - 28
            content += f'<rect x="{left-4}" y="{body-20}" width="{bw+8}" height="151" rx="6" fill="#244b40" stroke="#81d5bc"/>'
        else:
            content += text(x + 14, top + 18, '▸ General', 17)
            content += box(x + 10, top + 31, width - 20, 34, '▾ Appearance', fill='#397559')
            left, body, bw = x + 26, top + 88, width - 40
            content += text(x + 14, top + 199, '▸ Motion', 17)
        content += text(left, body, 'Colour', 17, '#81d5bc')
        content += f'<rect x="{left}" y="{body+12}" width="26" height="22" fill="#58a78c"/>'
        content += text(left + 36, body + 29, '#58A78C', 16)
        content += text(left, body + 65, 'Labels', 17, '#81d5bc')
        content += text(left, body + 94, 'Name: River garden', 14)
content += text(28, 1220, 'Review schematics. Group choice remains pending; RGB and full keyboard are separate implementation work.', 16)
path = HERE / 'sections-groups.svg'
path.write_text(svg(1100, 1250, content))
ET.parse(path)
