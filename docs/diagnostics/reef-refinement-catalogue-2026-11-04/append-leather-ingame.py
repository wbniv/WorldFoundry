"""Append the Pixel close-up review after the leather restoration page."""
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

root = Path(__file__).resolve().parent
target = root/'reef-refinement-catalogue.pdf'
title = 'Leather coral: in-game close-up review'
reader = PdfReader(target)
if any(title in (page.extract_text() or '') for page in reader.pages):
    raise SystemExit('In-game review already exists; review before replacing it.')
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
page.drawString(38, h-77, 'REALISTIC')
page.drawString(w/2+10, h-77, 'ANIME')
iw, ih = (w-100)/2, ((w-100)/2)*1008/2244
y = h-95-ih
for label, x in (('realistic', 38), ('anime', w/2+10)):
    page.drawImage(str(root/f'leather_ingame-{label}.png'), x, y,
                   width=iw, height=ih, preserveAspectRatio=True)
page.setFont('Helvetica', 10)
page.drawString(38, y-28, 'Pixel captures use temporary camera/player placement with the rebuilt production mesh and textures.')
page.drawString(38, y-45, 'The slim purple polyps are visible on the pink leather coral; its neighbors and the boxfish overlap the view.')
page.setFont('Helvetica', 9)
page.drawString(38, 54, 'These are after captures in the two styles; the previous page shows the source-mesh before/after comparison.')
page.showPage()
page.save()
stream.seek(0)
writer.add_page(PdfReader(stream).pages[0])
temporary = target.with_suffix('.ingame.tmp.pdf')
with temporary.open('wb') as f:
    writer.write(f)
temporary.replace(target)
print(target)
