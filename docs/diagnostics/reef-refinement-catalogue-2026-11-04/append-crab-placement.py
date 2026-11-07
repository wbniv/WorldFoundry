"""Append the Pixel gameplay comparison for the crab placement."""
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

root = Path(__file__).parent
target = root / 'reef-refinement-catalogue.pdf'
writer = PdfWriter()
for existing in PdfReader(target).pages:
    if 'Guard crab: host coral placement' not in (existing.extract_text() or ''):
        writer.add_page(existing)
stream = BytesIO()
w, h = landscape(A4)
page = canvas.Canvas(stream, pagesize=(w, h))
page.setFillColor(HexColor('#102a3a'))
page.rect(0, 0, w, h, fill=1, stroke=0)
page.setFillColor(HexColor('#eaf6f6'))
page.setFont('Helvetica-Bold', 21)
page.drawString(36, h-45, 'Guard crab: host coral placement')
page.setFont('Helvetica-Bold', 13)
page.drawString(38, h-77, 'BEFORE')
page.drawString(w/2+10, h-77, 'AFTER')
for label, x in (('before', 38), ('after', w/2+10)):
    page.drawImage(str(root / f'crab-placement-{label}.png'), x, 230,
                   width=(w-100)/2, height=220, preserveAspectRatio=True)
page.setFont('Helvetica', 11)
page.drawString(38, 190, 'The crab was behind its host and inside rock; the new position places it on the front branches.')
page.drawString(38, 170, 'Pixel diagnostic views use different camera positions; both preserve the reef and host coral.')
page.drawString(38, 150, 'The after view uses a temporary diagnostic build; the gameplay camera remains unchanged.')
page.showPage()
page.save()
stream.seek(0)
writer.add_page(PdfReader(stream).pages[0])
tmp = target.with_suffix('.updated.pdf')
with tmp.open('wb') as output:
    writer.write(output)
tmp.replace(target)
print(target)
