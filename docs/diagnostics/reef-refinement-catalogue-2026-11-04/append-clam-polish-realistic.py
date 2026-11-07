"""Append the clam ribs restoration comparison without replacing existing pages."""
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

root = Path(__file__).resolve().parent
target = root / 'reef-refinement-catalogue.pdf'
title = 'Giant clam: realistic game texture comparison'
reader = PdfReader(target)
if any(title in (page.extract_text() or '') for page in reader.pages):
    raise SystemExit('Comparison already exists; review it before replacing it.')
writer = PdfWriter()
for existing in reader.pages:
    writer.add_page(existing)
stream = BytesIO()
w, h = landscape(A4)
page = canvas.Canvas(stream, pagesize=(w, h))
page.setFillColor(HexColor('#102a3a'))
page.rect(0, 0, w, h, fill=1, stroke=0)
page.setFillColor(HexColor('#eaf6f6'))
page.setFont('Helvetica-Bold', 19)
page.drawString(36, h-45, title)
page.setFont('Helvetica-Bold', 13)
page.drawString(38, h-77, 'BEFORE: SAND TEXTURE')
page.drawString(w/2+10, h-77, 'AFTER: SHELL TEXTURE')
iw, ih = (w-100)/2, ((w-100)/2)*.75
y = h-95-ih
for label, x in (('before', 38), ('after', w/2+10)):
    page.drawImage(str(root/f'clam_polish_realistic-{label}.png'), x, y,
                   width=iw, height=ih, preserveAspectRatio=True)
page.setFont('Helvetica', 11)
page.drawString(38, y-27, 'Actual Pixel captures: the shell now has visible striped color variation.')
page.setFont('Helvetica', 9)
page.drawString(38, 54, 'Diagnostic camera and fish placement; both views use the game atlas and lighting.')
page.showPage()
page.save()
stream.seek(0)
writer.add_page(PdfReader(stream).pages[0])
temporary = target.with_suffix('.restoration.tmp.pdf')
with temporary.open('wb') as f:
    writer.write(f)
temporary.replace(target)
print(target)
