"""Build docs/rfq/2026-11-11-639-balcony-screen-frame-spec-v3.html from the v2 sheet:
adds the continuous latch channel and the third (solar) panel set, with page 5 drawn by
build_solar_sheet_svgs.py. Run from the repository root; then print to PDF with headless Chrome."""
import json, pathlib, subprocess, sys

here = pathlib.Path(__file__).parent
rfq = here.parent.parent / 'rfq'
svg = json.loads(subprocess.run([sys.executable, str(here / 'build_solar_sheet_svgs.py')], check=True, capture_output=True, text=True).stdout)
s = (rfq / '2026-11-08-639-balcony-screen-frame-spec-v2.html').read_text()

def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)

rep('<title>ข้อกำหนดกรอบมุ้งระเบียง v2 / Balcony screen frame specification v2 — condo 639</title>', '<title>ข้อกำหนดกรอบมุ้งระเบียง v3 / Balcony screen frame specification v3 — condo 639</title>')
rep('<h1>ข้อกำหนดกรอบมุ้งระเบียง v2 · Balcony screen frame specification v2</h1>', '<h1>ข้อกำหนดกรอบมุ้งระเบียง v3 · Balcony screen frame specification v3</h1>')
rep('8&nbsp;November&nbsp;2026 · v2: เพิ่มบานกันฝน · adds weather inserts', '11&nbsp;November&nbsp;2026 · v3: ร่องล็อกต่อเนื่อง และบานโซลาร์ชุดที่ 3 · continuous latch channel and a third set of solar inserts')
rep('รับบานได้ 2 ชุดในรางเดียวกัน: บานมุ้ง 6 บาน และบานกันฝน 6 บานสำหรับช่วงที่เจ้าของไม่อยู่ · Fixed black aluminium frame, no mullions, taking two panel sets in the same rails: six pet-mesh screens, and six weather inserts that keep all rain out while the owner is away',
    'รับบานได้ 3 ชุดในรางเดียวกัน: บานมุ้ง 6 บาน บานกันฝน 6 บาน และบานโซลาร์ 4 บาน · Fixed black aluminium frame, no mullions, taking three panel sets in the same rails: six pet-mesh screens, six weather inserts that keep all rain out while the owner is away, and four solar inserts')
anchor = '<tr><td>บาน 2 ชุด ขนาดภายนอกและความหนาเท่ากัน ใช้รางเดียวกัน: บานมุ้ง Pet Screen สีดำ 6 บาน และบานกันฝน 6 บาน</td><td class="ans"><span class="box"></span></td><td>Two panel sets with the same outer size and thickness, sharing the same rails: six black pet-mesh screens and six weather inserts.</td></tr>'
rows = ('<tr><td>ร่องล็อกยาวต่อเนื่องตลอดรางบนและรางล่าง ตัวล็อกกดอัดและสลักกันยกอยู่ที่บาน เกี่ยวร่องได้ทุกตำแหน่ง กรอบจึงรับบานได้ทุกความกว้าง (รูป C, D)</td><td class="ans"><span class="box"></span></td><td>A continuous latch channel along the head and sill rails. The cam latches and anti-lift bolts are on the panels and catch anywhere along it, so the frame takes panels of any width (figures C, D).</td></tr>'
        '<tr><td>ชุดที่ 3 สั่งภายหลังได้: บานโซลาร์ 4 บาน กว้างบานละ 1/4 ของช่อง ใช้รางเดียวกัน ซีลและรอยต่อเหมือนบานกันฝน ใส่ 1–4 บานร่วมกับบานอื่นได้ พร้อมบานแคบ 1/12 อีก 2 บาน (หัวข้อ 5)</td><td class="ans"><span class="box"></span></td><td>Third set, may be ordered later: four solar inserts, each a quarter of the width, in the same rails, sealed and jointed like the weather inserts; any 1–4 of them can go in with the other panels, using two narrow 1/12 fillers (section 5).</td></tr>')
rep(anchor, anchor + rows)
R = lambda th, en: f'<tr><td>{th}</td><td class="ans"><span class="box"></span></td><td>{en}</td></tr>'
page5 = ('<div class="p2">\n<h2>5 · บานโซลาร์ ชุดที่ 3 และร่องล็อกต่อเนื่อง · Solar inserts (third set) and the continuous latch channel</h2>\n'
         '<p class="small">แบบร่าง หน่วยเป็นมม. ตัวเลขเป็นตัวอย่างจากกรอบหน้า 25 มม. และขอบบาน 20 มม. ร้านกำหนดขนาดจริง · Schematic, mm, sizes are examples for a 25 mm frame face and 20 mm insert edges; the shop sets the real sizes.</p>\n'
         f'<div class="fig3">{svg["layout"]}</div>\n<div class="fig3">{svg["channel"]}</div>\n<div class="fig3">{svg["combos"]}</div>\n'
         '<h2 class="p2">5b · ข้อกำหนดบานโซลาร์และบานแคบ · Solar insert and filler requirements</h2>'
         '<table class="req"><tr><th class="th">ภาษาไทย</th><th class="ans">ยืนยัน · Confirm</th><th class="en">English</th></tr>'
         + R('บานโซลาร์ 4 บาน กว้างเท่ากัน บานละ 1/4 ของช่องใน (≈ 657) สูงเท่าบานมุ้ง', 'Four equal solar inserts, each a quarter of the clear width (≈ 657), the same height as the screens.')
         + R('แต่ละบานใส่แผงโซลาร์ 18 V 50 W ขนาด 600 × 460 × 25–30 จำนวน 2 แผง วางแนวนอน ซ้อนกันชิดขอบล่าง เจ้าของจัดหาแผงให้', 'Each holds two 18 V 50 W panels, 600 × 460 × 25–30, landscape, stacked at the bottom. The owner supplies the panels.')
         + R('พื้นที่เหนือแผงและข้างแผงปิดด้วยโพลีคาร์บอเนตใส ยาแนวหรือยางซีลรอบแผงกันน้ำ', 'Clear polycarbonate fills the space above and beside the panels; each panel sealed into the insert frame, watertight.')
         + R('กระจกแผงอยู่ระนาบเดียวกับบาน กรอบแผงยื่นเข้าด้านในได้ไม่เกิน 15', 'Panel glass in the plane of the insert; the panel frames may stand up to 15 proud on the room side.')
         + R('ยางซีล ตัวล็อกกดอัด สลักกันยก และรอยต่อบาก เหมือนบานกันฝน ทดสอบฉีดน้ำแบบเดียวกันเมื่อส่งงาน', 'Gaskets, cam latches, anti-lift bolts and rebated joints as the weather inserts; the same hose test at handover.')
         + R('รูร้อยสายที่ขอบล่างด้านในบานละ 1 จุด ซีลกันน้ำ ปลั๊ก MC4 1 คู่ต่อบาน แผงทั้ง 2 ต่อขนานกันในบาน', 'One sealed cable exit per insert at the bottom inner edge, with one MC4 plug pair; the two panels wired in parallel inside the insert.')
         + R('บานละประมาณ 8–10 กก. ถอดและใส่จากด้านในแบบเดียวกับบานอื่น', 'About 8–10 kg each; fitted and removed from inside like the other panels.')
         + R('ใส่บานโซลาร์ได้ 1, 2, 3 หรือ 4 บาน (รูป E): โซลาร์ 2 บานกว้างเท่าบานมุ้ง 3 บานพอดี โซลาร์ 1 หรือ 3 บานต้องมีบานแคบ 1/12 (≈ 219) เพิ่ม 2 แบบ คือแบบมุ้งและแบบโพลีคาร์บอเนตใสมีซีลและขอบบาก', 'Any 1, 2, 3 or 4 solar inserts can go in (figure E). Two solar inserts take exactly the width of three screens. One or three need a narrow filler, a twelfth of the width (≈ 219), made in two versions: mesh, and clear polycarbonate gasketed and rebated like the weather inserts.')
         + R('รอยต่อระหว่างบานต่างชนิด (โซลาร์ บานกันฝน บานมุ้ง บานแคบ) ต้องใส่ติดกันได้ทุกแบบ ร้านออกแบบรอยต่อ เมื่อใส่โซลาร์กับบานกันฝนต้องกันฝนได้ทั้งช่อง', 'Any panel type must sit next to any other (solar, weather insert, screen, filler); the shop details the joints. Solar inserts with weather inserts or polycarbonate fillers must keep the whole opening rain-tight.')
         + '</table>\n</div>\n')
rep('</body>\n</html>', page5 + '</body>\n</html>')
rep('.p2{break-before:page}', '.fig3 svg{width:100%;height:auto;display:block;margin:0 0 1.5mm}.p2{break-before:page}')
(rfq / '2026-11-11-639-balcony-screen-frame-spec-v3.html').write_text(s)
print(rfq / '2026-11-11-639-balcony-screen-frame-spec-v3.html')
