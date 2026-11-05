"""Append the new neutral/posed model renderings to the existing catalogue."""
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor

root = Path(__file__).parent
target = root / 'reef-refinement-catalogue.pdf'
writer = PdfWriter()
existing = PdfReader(target).pages
motion_count = 5 if 'Feather dusters: new crowns' in existing[-3].extract_text() else 2
for page in existing[:-motion_count]:
    writer.add_page(page)
for key, title, description in (
    ('boxfish_fin_motion', 'Boxfish: independent fins', 'Neutral bind pose and an example fin pose.'),
    ('clam_motion', 'Giant clam: valves and mantle', 'Neutral open pose and an example closed pose.'),
    ('duster_motion', 'Feather dusters: new crowns', 'New crowns at rest and retracted; these animals were absent before this refinement.'),
    ('flowerpot_motion', 'Flowerpot coral: polyp sway', 'Neutral coral and an example of the polyps swaying.'),
    ('leather_motion', 'Leather coral: deflation', 'Neutral coral and an example deflated pose.'),
):
    stream = BytesIO()
    w, h = landscape(A4)
    page = canvas.Canvas(stream, pagesize=(w, h))
    page.setFillColor(HexColor('#102a3a')); page.rect(0, 0, w, h, fill=1, stroke=0)
    page.setFillColor(HexColor('#eaf6f6')); page.setFont('Helvetica-Bold', 21); page.drawString(36, h-45, title)
    page.setFont('Helvetica-Bold', 13); page.drawString(38, h-77, 'BEFORE / NEUTRAL'); page.drawString(w/2+10, h-77, 'AFTER / POSED')
    iw = (w-100)/2; ih = iw*.75; y = h-95-ih
    for label, x in (('before', 38), ('after', w/2+10)):
        page.drawImage(str(root / f'{key}-{label}.png'), x, y, width=iw, height=ih, preserveAspectRatio=True)
    page.setFont('Helvetica', 12); page.drawString(38, y-28, description)
    page.setFont('Helvetica', 9); page.drawString(38, 50, 'Exported mesh and reference deformation; plain swatches, not in-game textures or lighting.')
    page.showPage(); page.save(); stream.seek(0)
    writer.add_page(PdfReader(stream).pages[0])
tmp = target.with_suffix('.updated.pdf')
with tmp.open('wb') as f:
    writer.write(f)
tmp.replace(target)
print(target)
