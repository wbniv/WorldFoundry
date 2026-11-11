"""Generate the two SVG figures for page 5 of the v3 shop sheet (solar inserts and the
continuous latch channel). Prints a JSON object {"layout": "<svg…>", "channel": "<svg…>"}.

Units are mm. Sizes follow the plan's example frame (25 mm face, 20 mm insert edges);
the shop's own profiles govern.
"""
import json

W, H, F, S = 2680, 1110, 25, 20
QW = (W - 2 * F) / 4            # solar insert width
BH = H - 2 * F                  # insert height
PW, PH, GAP = 600, 460, 10      # panel, landscape

STYLE = ('<style>.t{font-size:38px;fill:#111}.s{font-size:34px;fill:#333}.h{font-size:44px;font-weight:700;fill:#111}'
         '.d{stroke:#444;stroke-width:2.5;fill:none}.w{font-size:32px;fill:#fff}</style>')


def panel(x, y, k):
    out = [f'<rect x="{x:.1f}" y="{y:.1f}" width="{PW*k:.1f}" height="{PH*k:.1f}" fill="#3a3d42"/>']
    cw, ch = (PW - 30) / 9, (PH - 30) / 4
    for r in range(4):
        for c in range(9):
            out.append(f'<rect x="{x+(15+c*cw+1.5)*k:.1f}" y="{y+(15+r*ch+1.5)*k:.1f}" width="{(cw-3)*k:.1f}" height="{(ch-3)*k:.1f}" fill="#1c2b4d"/>')
    return ''.join(out)


def insert(x0, y0, k, label=''):
    X = lambda v: x0 + v * k
    Y = lambda v: y0 + v * k
    o = [f'<path fill="#2e2e2e" fill-rule="evenodd" d="M{X(0):.1f} {Y(0):.1f}h{QW*k:.1f}v{BH*k:.1f}h{-QW*k:.1f}Z '
         f'M{X(S):.1f} {Y(S):.1f}v{(BH-2*S)*k:.1f}h{(QW-2*S)*k:.1f}v{-(BH-2*S)*k:.1f}Z"/>',
         f'<rect x="{X(S):.1f}" y="{Y(S):.1f}" width="{(QW-2*S)*k:.1f}" height="{(BH-2*S)*k:.1f}" fill="#dfeaf3"/>']
    px = (QW - PW) / 2
    for j in range(2):
        py = BH - S - PH * (j + 1) - GAP * j
        o.append(panel(X(px), Y(py), k))
    if label:
        o.append(f'<text x="{X(QW/2):.1f}" y="{Y(BH/2)+9:.1f}" text-anchor="middle" class="w" style="font-size:30px;font-weight:700">{label}</text>')
    return ''.join(o)


def dim_h(x1, x2, y, text, anchor='middle', tx=None):
    tx = (x1 + x2) / 2 if tx is None else tx
    return (f'<path class="d" d="M{x1:.1f} {y-9:.1f}v18M{x2:.1f} {y-9:.1f}v18M{x1:.1f} {y:.1f}H{x2:.1f}"/>'
            f'<text x="{tx:.1f}" y="{y+30:.1f}" text-anchor="{anchor}" class="s">{text}</text>')


def dim_v(x, y1, y2, text, side='right'):
    tx, anc = (x + 14, 'start') if side == 'right' else (x - 14, 'end')
    return (f'<path class="d" d="M{x-9:.1f} {y1:.1f}h18M{x-9:.1f} {y2:.1f}h18M{x:.1f} {y1:.1f}V{y2:.1f}"/>'
            f'<text x="{tx:.1f}" y="{(y1+y2)/2+8:.1f}" text-anchor="{anc}" class="s">{text}</text>')


def layout_svg():
    o = []
    # A: the opening, k = 0.62 px/mm
    k, ox, oy = 0.62, 70, 170
    X = lambda v: ox + v * k
    Y = lambda v: oy + v * k
    o.append(f'<text x="{ox-40}" y="40" class="h">A · ช่องเปิดกับบานโซลาร์ 4 บาน · The opening with the four solar inserts</text>')
    o.append(f'<rect x="{X(-90):.1f}" y="{Y(-110):.1f}" width="{(W+170)*k:.1f}" height="{110*k:.1f}" fill="#d7d4ce"/>'
             f'<rect x="{X(-90):.1f}" y="{Y(H):.1f}" width="{(W+170)*k:.1f}" height="{90*k:.1f}" fill="#d7d4ce"/>'
             f'<rect x="{X(-90):.1f}" y="{Y(0):.1f}" width="{90*k:.1f}" height="{H*k:.1f}" fill="#d7d4ce"/>'
             f'<rect x="{X(W):.1f}" y="{Y(0):.1f}" width="{80*k:.1f}" height="{H*k:.1f}" fill="#d7d4ce"/>')
    o.append(f'<path fill="#111" fill-rule="evenodd" d="M{X(0):.1f} {Y(0):.1f}H{X(W):.1f}V{Y(H):.1f}H{X(0):.1f}Z M{X(F):.1f} {Y(F):.1f}H{X(W-F):.1f}V{Y(H-F):.1f}H{X(F):.1f}Z"/>')
    for i in range(4):
        o.append(insert(X(F + i * QW), Y(F), k, str(i + 1)))
    o.append(dim_h(X(0), X(W), Y(H) + 90, 'ช่องเปิด · opening 2680'))
    y5 = Y(H) + 165
    o.append(f'<path class="d" d="M{X(F):.1f} {y5-9:.1f}v18M{X(F+QW):.1f} {y5-9:.1f}v18M{X(F):.1f} {y5:.1f}H{X(F+QW):.1f}"/>'
             f'<text x="{X(F+QW)+16:.1f}" y="{y5+11:.1f}" class="s">บานละ · each insert ≈ 657 = (2680 − 2×25) ÷ 4</text>')
    o.append(dim_v(X(W) + 85, Y(0), Y(H), '1110'))
    # B: one insert, k2
    k2, bx, by = 0.78, 2000, 170
    XB = lambda v: bx + v * k2
    YB = lambda v: by + v * k2
    o.append(f'<text x="{bx-60}" y="40" class="h">B · บานโซลาร์ 1 บาน · One solar insert</text>')
    o.append(insert(bx, by, k2))
    px = (QW - PW) / 2
    ptop = BH - S - 2 * PH - GAP
    o.append(f'<text x="{XB(QW/2):.1f}" y="{YB(S+(ptop-S)/2)+8:.1f}" text-anchor="middle" class="t">โพลีคาร์บอเนตใส · clear PC</text>')
    for j, yy in enumerate((ptop, ptop + PH + GAP)):
        o.append(f'<text x="{XB(QW/2):.1f}" y="{YB(yy+PH/2)-14:.1f}" text-anchor="middle" class="w">แผง 50 W 18 V</text>'
                 f'<text x="{XB(QW/2):.1f}" y="{YB(yy+PH/2)+30:.1f}" text-anchor="middle" class="w">600 × 460 × 25–30</text>')
    # junction boxes, wire, plug
    for yy in (ptop + PH - 50, ptop + 2 * PH + GAP - 50):
        o.append(f'<rect x="{XB(QW-px-90):.1f}" y="{YB(yy):.1f}" width="{50*k2:.1f}" height="{30*k2:.1f}" rx="4" fill="#777"/>')
    o.append(f'<path d="M{XB(QW-px-65):.1f} {YB(ptop+PH-35):.1f}V{YB(BH+40):.1f}" stroke="#c0392b" stroke-width="4" fill="none"/>')
    o.append(f'<rect x="{XB(QW-px-120):.1f}" y="{YB(BH+40):.1f}" width="{110*k2:.1f}" height="{34*k2:.1f}" rx="5" fill="#c0392b"/>')
    o.append(f'<text x="{XB(QW-px-130):.1f}" y="{YB(BH+66):.1f}" text-anchor="end" class="s">ปลั๊ก MC4 1 ชุด ด้านใน · one MC4 plug, room side</text>')
    o.append(dim_v(XB(QW) + 60, YB(0), YB(BH), '1060'))
    o.append(dim_v(XB(-40), YB(ptop), YB(BH - S), '930', side='left'))
    o.append(dim_v(XB(-40), YB(S), YB(ptop), '≈ 90', side='left'))
    o.append(dim_h(XB(0), XB(QW), YB(BH) + 140, 'บาน · insert ≈ 657 · แผง · panels 600'))
    return (f'<svg viewBox="0 0 2700 1220" xmlns="http://www.w3.org/2000/svg" font-family="Noto Sans, Noto Sans Thai, sans-serif">{STYLE}'
            + ''.join(o) + '</svg>')


def channel_svg():
    o = []
    # C: the sill rail seen from inside, with latch points of both sets
    k, ox, oy = 0.85, 70, 120
    X = lambda v: ox + v * k
    o.append('<text x="30" y="44" class="h">C · ร่องล็อกต่อเนื่อง มองจากด้านใน · The continuous latch channel, seen from inside</text>')
    o.append(f'<rect x="{X(0):.1f}" y="{oy:.1f}" width="{(W-2*F)*k:.1f}" height="70" fill="#1a1a1a"/>'
             f'<rect x="{X(0):.1f}" y="{oy+24:.1f}" width="{(W-2*F)*k:.1f}" height="22" fill="#9aa3ab"/>')
    o.append(f'<text x="{X(0):.1f}" y="{oy-14:.1f}" class="s">รางล่าง (รางบนเหมือนกัน) ร่องยาวตลอด · sill rail (head rail the same), channel runs the full length</text>')
    q6, q4 = (W - 2 * F) / 6, (W - 2 * F) / 4
    for i in range(6):
        for f in (0.2, 0.8):
            x = X(i * q6 + f * q6)
            o.append(f'<path d="M{x:.1f} {oy+90:.1f}v40" stroke="#2a78d6" stroke-width="6"/>')
    for i in range(4):
        for f in (0.15, 0.85):
            x = X(i * q4 + f * q4)
            o.append(f'<path d="M{x:.1f} {oy+150:.1f}v40" stroke="#eb6834" stroke-width="6"/>')
    o.append(f'<rect x="{X(0):.1f}" y="{oy+222:.1f}" width="14" height="34" fill="#2a78d6"/><text x="{X(0)+26:.1f}" y="{oy+250:.1f}" class="s">ตัวล็อกของบาน 6 บาน · latches of the 6-panel sets</text>'
             f'<rect x="{X(1300):.1f}" y="{oy+222:.1f}" width="14" height="34" fill="#eb6834"/><text x="{X(1300)+26:.1f}" y="{oy+250:.1f}" class="s">ตัวล็อกของบานโซลาร์ 4 บาน · latches of the 4-insert solar set</text>')
    o.append(f'<text x="{X(0):.1f}" y="{oy+305:.1f}" class="t">ตัวล็อกและสลักอยู่ที่บาน เกี่ยวร่องได้ทุกตำแหน่ง ไม่มีจุดล็อกตายตัวที่กรอบ</text>'
             f'<text x="{X(0):.1f}" y="{oy+352:.1f}" class="t">Latches and bolts are on the panels and catch anywhere along the channel; the frame has no fixed latch points.</text>')
    # D: section through the sill rail with the channel and a cam latch
    s, sx, sy = 7.0, 760, 600
    P = lambda x, y: (sx + x * s, sy + y * s)
    o.append('<text x="30" y="560" class="h">D · หน้าตัดรางล่างกับร่องล็อก · Sill rail section with the latch channel</text>')
    def rect(x, y, w, h, fill, extra=''):
        a, b = P(x, y)
        return f'<rect x="{a:.1f}" y="{b:.1f}" width="{w*s:.1f}" height="{h*s:.1f}" fill="{fill}" {extra}/>'
    o.append(rect(-10, 60, 100, 14, '#d7d4ce'))                       # cap
    o.append(rect(0, 57, 45, 3, '#1a1a1a'))                            # rail floor
    o.append(rect(0, 32, 2, 25, '#1a1a1a'))                            # outer stop 25
    o.append(rect(24, 39, 2, 18, '#1a1a1a'))                           # inner dam 18
    o.append(rect(26, 44, 19, 13, '#1a1a1a'))                          # box + channel body
    o.append(rect(30, 47, 11, 7, '#fff'))                              # channel void
    o.append(rect(30, 44, 3, 3, '#fff') + rect(38, 44, 3, 3, '#fff'))  # slot opening between lips
    o.append(rect(33, 44, 5, 3, '#fff'))
    o.append(rect(5, 20, 16, 36, '#3a3a3a'))                           # insert (edge)
    o.append(rect(3, 30, 2, 18, '#5a7fa8'))                            # gasket
    o.append(rect(21, 46, 14, 3, '#c49a2c') + rect(32, 46, 3, 6, '#c49a2c') + rect(32, 51, 7, 2, '#c49a2c'))  # cam latch hook
    labels = [((1, 28), 'ขอบกั้นนอก 25 · outer stop 25', -330, -40), ((4, 40), 'ยางซีล · gasket', -300, 0),
              ((13, 24), 'บาน · panel', -260, -70), ((25, 41), 'ขอบในกันน้ำ 18 · dam 18', 260, -120),
              ((35, 52), 'ขอเกี่ยวตัวล็อกกดอัดใต้ปากร่อง · cam-latch hook under the channel lips', 280, 60),
              ((35, 45.5), 'ร่องยาวต่อเนื่อง · continuous channel', 300, -40)]
    for (x, y), txt, dx, dy in labels:
        a, b = P(x, y)
        o.append(f'<path d="M{a:.1f} {b:.1f}L{a+dx*0.6:.1f} {b+dy:.1f}" stroke="#c0392b" stroke-width="2"/><circle cx="{a:.1f}" cy="{b:.1f}" r="4" fill="#c0392b"/>')
        o.append(f'<text x="{a+dx*0.6+(8 if dx>0 else -8):.1f}" y="{b+dy+8:.1f}" text-anchor="{"start" if dx>0 else "end"}" class="s">{txt}</text>')
    o.append(f'<text x="{sx-300}" y="{sy+70*s:.1f}" class="s">นอก · OUT</text><text x="{sx+50*s:.1f}" y="{sy+70*s:.1f}" class="s">ใน · IN</text>')
    return (f'<svg viewBox="0 0 2700 1140" xmlns="http://www.w3.org/2000/svg" font-family="Noto Sans, Noto Sans Thai, sans-serif">{STYLE}'
            + ''.join(o) + '</svg>')


if __name__ == '__main__':
    print(json.dumps({'layout': layout_svg(), 'channel': channel_svg()}))
