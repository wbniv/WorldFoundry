"""Generate the plan C frame-detail SVG (schematic, mm) on stdout. Its output is pasted into frame-detail.html and page 2 of docs/rfq/2026-11-08-639-balcony-screen-frame-spec.html."""
K = 1.7
AL, PN = "#1a1a1a", "#3a3a3a"
OUTL = 'stroke="#000" stroke-width=".35"'
geo, ann = [], []          # geometry (scaled groups) and annotations (unscaled)

def g(s): geo.append(s)
def a(s): ann.append(s)

def rect(x, y, wd, ht, fill, extra=""):
    g(f'<rect x="{x}" y="{y}" width="{wd}" height="{ht}" fill="{fill}" {extra}/>')

def box(x, y, wd, ht, fill, t=2):
    rect(x, y, wd, ht, fill, OUTL); rect(x + t, y + t, wd - 2 * t, ht - 2 * t, "#fff")

def brush(x, y, wd, ht, vertical=True):
    rect(x, y, wd, ht, "#8a8a8a")
    n = int((ht if vertical else wd) / 1.2)
    for i in range(n):
        if vertical:
            yy = y + .6 + i * 1.2; g(f'<line x1="{x}" y1="{yy:.1f}" x2="{x+wd}" y2="{yy:.1f}" stroke="#555" stroke-width=".3"/>')
        else:
            xx = x + .6 + i * 1.2; g(f'<line x1="{xx:.1f}" y1="{y}" x2="{xx:.1f}" y2="{y+ht}" stroke="#555" stroke-width=".3"/>')

def conc(x, y, wd, ht):
    rect(x, y, wd, ht, "url(#cc)", 'stroke="#777" stroke-width=".35"')

def mesh_h(x1, x2, y): g(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="#777" stroke-width="1" stroke-dasharray="1.6 1"/>')
def mesh_v(x, y1, y2): g(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="#777" stroke-width="1" stroke-dasharray="1.6 1"/>')

def brk_h(x1, x2, y):
    xs = [x1 + (x2 - x1) * f for f in (0, .4, .47, .53, .6, 1)]; ys = [y, y, y - 3, y + 3, y, y]
    g('<polyline points="' + " ".join(f"{p:.1f},{q:.1f}" for p, q in zip(xs, ys)) + '" fill="none" stroke="#000" stroke-width=".45"/>')

def brk_v(x, y1, y2):
    ys = [y1 + (y2 - y1) * f for f in (0, .4, .47, .53, .6, 1)]; xs = [x, x, x - 3, x + 3, x, x]
    g('<polyline points="' + " ".join(f"{p:.1f},{q:.1f}" for p, q in zip(xs, ys)) + '" fill="none" stroke="#000" stroke-width=".45"/>')

class Detail:
    def __init__(self, ox, oy): self.ox, self.oy = ox, oy
    def P(self, x, y): return self.ox + K * x, self.oy + K * y
    def open(self): g(f'<g transform="translate({self.ox},{self.oy}) scale({K})">')
    def close(self): g('</g>')
    def call(self, x, y, dx, dy, n):
        px, py = self.P(x, y); cx, cy = px + dx, py + dy
        a(f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{cx:.1f}" y2="{cy:.1f}" class="ld"/><circle cx="{px:.1f}" cy="{py:.1f}" r=".9" fill="#c0392b"/>')
        a(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.2" fill="#fff" stroke="#c0392b" stroke-width=".7"/>'
          f'<text x="{cx:.1f}" y="{cy+1.9:.1f}" class="cn">{n}</text>')
    def text(self, x, y, s, cls, anchor="middle"):
        px, py = self.P(x, y); a(f'<text x="{px:.1f}" y="{py:.1f}" class="{cls}" text-anchor="{anchor}">{s}</text>')
    def dimh(self, x1, x2, y, s):
        p1, p2 = self.P(x1, y), self.P(x2, y)
        a(f'<path d="M{p1[0]:.1f} {p1[1]-2.5:.1f}v5M{p2[0]:.1f} {p2[1]-2.5:.1f}v5M{p1[0]:.1f} {p1[1]:.1f}H{p2[0]:.1f}" class="dm"/>')
        a(f'<text x="{(p1[0]+p2[0])/2:.1f}" y="{p1[1]+7:.1f}" class="dt" text-anchor="middle">{s}</text>')
    def dimv(self, x, y1, y2, s):
        p1, p2 = self.P(x, y1), self.P(x, y2)
        a(f'<path d="M{p1[0]-2.5:.1f} {p1[1]:.1f}h5M{p2[0]-2.5:.1f} {p2[1]:.1f}h5M{p1[0]:.1f} {p1[1]:.1f}V{p2[1]:.1f}" class="dm"/>')
        a(f'<text x="{p1[0]-3.5:.1f}" y="{(p1[1]+p2[1])/2+2:.1f}" class="dt" text-anchor="end">{s}</text>')

def title(x, y, s): a(f'<text x="{x}" y="{y}" class="tt">{s}</text>')

def sealant(x, y): g(f'<circle cx="{x}" cy="{y}" r="1.4" fill="#5a7fa8"/>')
def anchor(x, y1, y2, head_y): g(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="#888" stroke-width="1.6"/><rect x="{x-3}" y="{head_y}" width="6" height="1.6" fill="#888"/>')

# ---------- A: head ----------
title(8, 12, "A · รางบน ตัดแนวตั้ง · Head rail, vertical section")
A = Detail(52, 50); A.open()
conc(-24, -18, 92, 18)
rect(0, 0, 45, 2, AL, OUTL); rect(0, 0, 2, 40, AL, OUTL); box(24, 0, 21, 40, AL)
anchor(34.5, -14, 3.5, 2); sealant(-1.2, 1.2); sealant(46.2, 1.2)
box(5, 22, 16, 20, PN); mesh_v(13, 42, 62); brush(2, 26, 3, 14); brk_h(0, 26, 62)
g('<path d="M13 3.5V20.5" fill="none" stroke="#333" stroke-width=".4" marker-start="url(#ar)" marker-end="url(#ar)"/>')
A.close()
A.text(-14, -6, "คอนกรีต · concrete", "cl"); A.text(-14, 50, "นอก · OUT", "side"); A.text(58, 50, "ใน · IN", "side")
A.dimh(0, 45, 72, "45 ความลึกกรอบ · frame depth"); A.dimv(-6, 0, 40, "40")
A.call(1, 36, -10, 16, 1); A.call(13, 12, -26, -6, 2); A.call(3.5, 30, -26, 6, 3)
A.call(22.5, 32, 16, 18, 4); A.call(40, 22, 22, 0, 5); A.call(13, 54, 18, 6, 6); A.call(46.2, 1.2, 16, -10, 7)

# ---------- B: sill ----------
title(212, 12, "B · รางล่าง ตัดแนวตั้ง · Sill rail, vertical section")
B = Detail(250, 18); B.open()
conc(-10, 60, 100, 16)
rect(0, 58, 45, 2, AL, OUTL); g(f'<polygon points="2,56.6 24,54.2 24,58 2,58" fill="{AL}"/>')
rect(0, 43, 2, 11, AL, OUTL); rect(0, 57, 2, 3, AL, OUTL); box(24, 48, 21, 12, AL)
g('<path d="M12 55.6 L-8 56.6" stroke="#2e7fd0" stroke-width="1" fill="none" marker-end="url(#arb)"/>')
sealant(-1.2, 58.8); sealant(46.2, 58.8); anchor(34.5, 56.5, 72, 55)
box(5, 30, 16, 20, PN); rect(8, 50, 7, 3.6, "#b9b9b9", OUTL)
g('<rect x="17" y="42" width="2.2" height="16.5" fill="#c49a2c" stroke="#000" stroke-width=".3"/>')
mesh_v(13, 16, 30); brush(2, 32, 3, 12); brk_h(0, 26, 16)
B.close()
B.text(60, 70, "หลังผนังกันตก · pony-wall cap", "cl"); B.text(-20, 36, "นอก · OUT", "side"); B.text(62, 36, "ใน · IN", "side")
B.dimh(-10, 90, 84, "100 หลังผนัง · cap"); B.dimv(-4, 43, 60, "17")
B.call(1, 46, -14, -6, 8); B.call(18, 47, 22, -18, 9); B.call(34, 49, 20, -14, 10); B.call(14, 55.3, 26, -8, 11)
B.call(-6, 56.4, -8, 12, 12); B.call(11.5, 51.8, -10, -42, 13); B.call(-1.2, 58.8, 4, 16, 7)

# ---------- C: plan ----------
title(8, 204, "C · ตัดแนวนอน ที่ขอบข้างและรอยต่อบาน · Plan section at a jamb and a panel joint")
C = Detail(70, 232); C.open()
conc(-30, -10, 30, 64)
rect(0, 0, 2, 45, AL, OUTL); rect(0, 0, 40, 2, AL, OUTL); box(0, 24, 30, 21, AL)
box(5, 5, 20, 16, PN); brush(5, 2, 35, 3, vertical=False); mesh_h(25, 45, 13); brk_v(50, 0, 26); mesh_h(55, 65, 13)
box(65, 5, 20, 16, PN); brush(85, 6, 3, 14); box(88, 5, 20, 16, PN); mesh_h(108, 128, 13); brk_v(133, 0, 26)
sealant(-1.2, 46.2)
C.close()
C.text(-15, 60, "ผนังข้าง · reveal", "cl"); C.text(70, -6, "นอก · OUTSIDE (west)", "side"); C.text(70, 56, "ใน · INSIDE", "side")
C.dimh(65, 108, 34, "43 เส้นดำที่รอยต่อ · black line at a joint")
C.call(15, 18, 0, 22, 14); C.call(86.5, 10, -4, -24, 15); C.call(97, 18, 20, 22, 16); C.call(18, 38, 26, 20, 17); C.call(30, 3.5, 14, -16, 3); C.call(-1.2, 46.2, -14, 10, 7)

svg = f'''<svg viewBox="0 0 400 350" xmlns="http://www.w3.org/2000/svg" font-family="Noto Sans, Noto Sans Thai, sans-serif">
<defs>
<pattern id="cc" width="5" height="5" patternUnits="userSpaceOnUse"><rect width="5" height="5" fill="#dcd8d1"/><circle cx="1.2" cy="1.5" r=".45" fill="#aaa498"/><circle cx="3.6" cy="3.8" r=".4" fill="#aaa498"/></pattern>
<marker id="ar" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="3.5" markerHeight="3.5" orient="auto-start-reverse"><path d="M0 0L6 3L0 6Z" fill="#333"/></marker>
<marker id="arb" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="4" markerHeight="4" orient="auto"><path d="M0 0L6 3L0 6Z" fill="#2e7fd0"/></marker>
<style>.tt{{font-size:7px;font-weight:700}}.cl{{font-size:4.6px;fill:#555}}.side{{font-size:5px;font-weight:700;fill:#666}}.ld{{stroke:#c0392b;stroke-width:.4}}.dm{{fill:none;stroke:#333;stroke-width:.4}}.dt{{font-size:4.8px}}.cn{{font-size:5.4px;font-weight:700;fill:#c0392b;text-anchor:middle}}</style>
</defs>
{chr(10).join(geo)}
{chr(10).join(ann)}
</svg>'''
print(svg)
