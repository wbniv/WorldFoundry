"""Append Pixel captures of the final model restoration review."""
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
root=Path(__file__).resolve().parent
repo=root.parents[2]
diag=repo/'docs/diagnostics/reef-triangle-normal-2026-11-06'
target=root/'reef-refinement-catalogue.pdf'
title='Final restoration: Pixel textured close-up review'
r=PdfReader(target)
if any(title in (p.extract_text() or '') for p in r.pages):raise SystemExit('Review already exists')
w=PdfWriter()
for p in r.pages:w.add_page(p)
buf=BytesIO(); width,height=landscape(A4);c=canvas.Canvas(buf,pagesize=(width,height))
def page(name, items, foot):
 c.setFillColor(HexColor('#102a3a'));c.rect(0,0,width,height,fill=1,stroke=0);c.setFillColor(HexColor('#eaf6f6'));c.setFont('Helvetica-Bold',18);c.drawString(30,height-38,title+' — '+name)
 for i,(label,path) in enumerate(items):
  c.setFont('Helvetica-Bold',11);y=height-75-i*215;c.drawString(35,y,label);c.drawImage(str(path),35,y-185,width=width-70,height=175,preserveAspectRatio=True,anchor='c')
 c.setFont('Helvetica',9);c.drawString(35,35,foot);c.showPage()
page('flowerpot',[('REALISTIC',diag/'pixel-flowerpot-close-realistic/screenshot.png'),('ANIME',diag/'pixel-flowerpot-close-anime/screenshot.png')],'Diagnostic camera; restored crowns are visible. Faceting and texture stretching remain.')
page('closed clam',[('REALISTIC: BEFORE',repo/'docs/diagnostics/reef-gameplay-verification-2026-11-05/clam-near-pixel-2026-11-06.png'),('REALISTIC: AFTER',diag/'pixel-clam-close-realistic/screenshot.png')],'The revised shell edge is smoother; shell shading remains flat and gray.')
page('closed clam, anime',[('ANIME: AFTER',diag/'pixel-clam-close-anime/screenshot.png')],'Diagnostic fish placement triggers closure; no matching earlier anime close-up is available.')
c.save();buf.seek(0)
for p in PdfReader(buf).pages:w.add_page(p)
tmp=target.with_suffix('.review.tmp.pdf')
with tmp.open('wb') as f:w.write(f)
tmp.replace(target)
print(target)
