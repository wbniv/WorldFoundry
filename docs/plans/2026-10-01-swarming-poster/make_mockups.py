#!/usr/bin/env python3
"""make_mockups.py: the mockups for the swarming-poster plan, each a self-contained 1440x900 HTML (inline CSS/SVG) plus a same-name PNG (headless Chrome).

  poster.html        the real poster (docs/reference/swarming-poster/poster.html) scaled into the canvas, with a guide to its panels
  frame-budget.html  what one Forth step costs in a 60 fps frame, all at once vs spread over frames (numbers from measured.json)
  data-flow.html     how the pieces connect: the Couzin reference, the Forth core, the engine, the poster's inputs

Usage: python3 make_mockups.py [-h]
"""
import json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REF = HERE.parents[1] / "reference" / "swarming-poster"
INK, MUTED, ACC = "#1d2733", "#5c6b7a", "#0f7c93"
BASE_CSS = f"""*{{box-sizing:border-box}}html,body{{margin:0;width:1440px;height:900px;overflow:hidden;background:#fff;color:{INK};font:14px/1.4 "Noto Sans","DejaVu Sans",Arial,sans-serif}}
h1{{font-size:26px;margin:0}}.sub{{color:{MUTED}}}"""


def poster_page():
    doc = (REF / "poster.html").read_text(encoding="utf-8")
    style = re.search(r"<style>(.*?)</style>", doc, re.S).group(1)
    body = re.search(r'<div class="page">(.*)</div><script>', doc, re.S).group(1)
    guide = [("A", "The four collective states, simulated: swarm, torus, dynamic parallel, highly parallel"),
             ("B", "The zones and the blind volume"), ("C", "A map of p_group over the two zone widths; where our swarm, torus and school sit"),
             ("D", "The rule in eight lines, each mapped to the Forth word that does it"),
             ("F", "The Forth core in full, bytes per word, size, error, timing on the Chromecast HD"),
             ("G", "The Forth running in the tank’s real box: swarm, torus, school, a startle"),
             ("Src", "Sources, each chipped verified / unverified / ours; what is not claimed")]
    li = "".join(f'<li><b>{k}</b> {t}</li>' for k, t in guide)
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Swarming poster mockup</title><style>{style}</style>'
            f'<style>{BASE_CSS} .wrap{{position:absolute;left:0;top:0;width:640px;height:900px;overflow:hidden}} .wrap .page{{transform:scale(.567);transform-origin:0 0}}'
            f'.side{{position:absolute;left:680px;top:30px;width:720px}} .side li{{margin:0 0 10px}} .side ul{{padding-left:20px}}</style></head><body>'
            f'<div class="wrap"><div class="page">{body}</div></div><div class="side"><h1>The swarming poster, A3</h1>'
            f'<p class="sub">Left: the generated poster at 57 %. The PDF is one A3 page; this is what is on it.</p><ul>{li}</ul>'
            f'<p><b>Every figure is computed</b> by <code>make_swarm_poster.py</code> from the Couzin reference, the Forth core run in the engine’s own zForth, and the measured files; '
            f'a changed constant or a changed <code>school.fth</code> redraws it.</p></div></body></html>')


def frame_budget_page():
    m = json.loads((REF / "measured.json").read_text())
    tick = m["device"]["ms"]; per = tick / 10
    W, ms_px = 1180, 1180 / 50.0                       # 50 ms across (three 60 fps frames)
    fr = 1000 / 60
    s = []
    def lane(y, title, blocks, note):
        s.append(f'<text x="30" y="{y - 16}" font-size="16" font-weight="700" fill="{INK}">{title}</text>')
        for i in range(3):                              # frame boundaries
            x = 130 + i * fr * ms_px
            s.append(f'<rect x="{x:.1f}" y="{y}" width="{fr * ms_px:.1f}" height="64" fill="#f3f7fa" stroke="#9fb0bd"/>')
            s.append(f'<text x="{x + 6:.1f}" y="{y + 78}" font-size="12" fill="{MUTED}">frame {i + 1} (16.7 ms)</text>')
        for fx, w, label, col in blocks:
            s.append(f'<rect x="{130 + fx * ms_px:.1f}" y="{y + 8}" width="{w * ms_px:.1f}" height="48" fill="{col}"/>')
            s.append(f'<text x="{130 + fx * ms_px + 6:.1f}" y="{y + 38}" font-size="13" font-weight="700" fill="#fff">{label}</text>')
        s.append(f'<text x="30" y="{y + 102}" font-size="14" fill="{INK}">{note}</text>')
    lane(130, "A. One full step in one frame, every 6th frame (10 Hz)",
         [(0.0, 4.0, "", "#5c6b7a"), (4.0, tick, "", "#b02a2a")],
         f"One frame in six gets {tick:.1f} ms added on top of whatever it already costs: a visible spike if that frame was already close to 16.7 ms.")
    blocks = []
    for i in range(3):
        blocks.append((i * fr, 4.0, "", "#5c6b7a"))
        blocks.append((i * fr + 4.0, per * 2, "", "#0f7c93"))
    lane(330, "B. Two followers per frame, round robin (a full step every 5 frames, 12 Hz)", blocks,
         f"{per:.2f} ms per follower, so {per * 2:.1f} ms a frame. Each follower is updated at 12 Hz and its position is blended in between.")
    s.append(f'<text x="{130 + (4.0 + tick) * ms_px + 8:.1f}" y="{130 + 38}" font-size="14" font-weight="700" fill="#b02a2a">+{tick:.1f} ms</text>')
    for i in range(3):
        s.append(f'<text x="{130 + (i * fr + 4.0 + per * 2) * ms_px + 8:.1f}" y="{330 + 38}" font-size="14" font-weight="700" fill="#0f5f73">+{per * 2:.1f} ms</text>')
    s.append('<rect x="30" y="470" width="16" height="12" fill="#5c6b7a"/><text x="52" y="481" font-size="13">the rest of the frame: not measured, its width is only illustrative</text>'
             '<rect x="560" y="470" width="16" height="12" fill="#b02a2a"/><text x="582" y="481" font-size="13">school.fth, one step</text>'
             '<rect x="760" y="470" width="16" height="12" fill="#0f7c93"/><text x="782" y="481" font-size="13">school.fth, two followers</text>')
    s.append(f'<text x="30" y="570" font-size="16" font-weight="700">What was measured, and what was not</text>')
    notes = [f"Measured: {tick:.1f} ms for one 11-fish step (median of 3 runs of 200 ticks) on the Chromecast HD, with the engine’s zForth, float cells, mailboxes as a plain array.",
             f"Not measured: the same code inside the engine, where each mailbox access goes through the object manager: expect more. Phase 0 of the schooling plan measures it.",
             f"On this PC the same step takes {m['x86_ms']:.1f} ms: the Chromecast is no slower than the desktop here because the interpreter, not the CPU, is the cost.",
             f"Size: {m['dictionary_bytes']} bytes of the 65,536-byte dictionary, {m['code_lines']} code lines."]
    for i, t in enumerate(notes):
        s.append(f'<text x="30" y="{600 + i * 26}" font-size="14" fill="{INK}">{t}</text>')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="900" viewBox="0 0 1440 900">{"".join(s)}</svg>'
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Frame budget mockup</title><style>{BASE_CSS} svg{{position:absolute;left:0;top:70px}}'
            f'h1{{position:absolute;left:30px;top:18px}}</style></head><body><h1>One Forth step against the 60 fps frame</h1>{svg}</body></html>')


def data_flow_page():
    boxes = {
        "player": (40, 120, 220, 70, "The player’s fish", "stick / touch, Director", "#e4ecff", "#2b5fd9"),
        "leader": (330, 120, 260, 70, "Leader state (fish 0)", "position, unit heading, speed", "#e4ecff", "#2b5fd9"),
        "school": (660, 120, 300, 70, "school.fth: sch-tick", "Couzin zones + leader + walls + startle", "#e3f4ea", "#1f8a4c"),
        "mail": (1030, 120, 260, 70, "Follower mailboxes", "x y z, heading, next state, timer", "#e3f4ea", "#1f8a4c"),
        "dir": (1030, 280, 260, 70, "Director", "poses the five part actors per fish", "#e3f4ea", "#1f8a4c"),
        "draw": (1030, 440, 260, 70, "The renderer", "ten more fish in the tank", "#f3f7fa", "#9fb0bd"),
        "couzin": (330, 330, 260, 70, "couzin.py (numpy)", "the reference model, sigma = 0", "#fff2d9", "#b26a00"),
        "host": (660, 330, 300, 70, "zf_host (the engine’s zForth)", "runs school.fth with no engine", "#fff2d9", "#b26a00"),
        "test": (495, 480, 300, 70, "forth_check.py, tests", "one-tick equivalence, tank runs", "#fff2d9", "#b26a00"),
        "dev": (40, 480, 260, 70, "device_bench.sh", "ms per tick on the Chromecast", "#fff2d9", "#b26a00"),
        "meas": (40, 640, 330, 70, "sweep.json · tank.json · measured.json", "the poster’s computed inputs", "#fff2d9", "#b26a00"),
        "poster": (560, 640, 330, 70, "make_swarm_poster.py", "poster.html · .pdf · .png", "#fff2d9", "#b26a00"),
    }
    arrows = [("player", "leader"), ("leader", "school"), ("school", "mail"), ("mail", "dir"), ("dir", "draw"), ("couzin", "test"), ("host", "test"), ("test", "meas"),
              ("dev", "meas"), ("meas", "poster"), ("school", "host")]
    s = []
    def c(k, side):
        x, y, w, h = boxes[k][:4]
        return {"r": (x + w, y + h / 2), "l": (x, y + h / 2), "b": (x + w / 2, y + h), "t": (x + w / 2, y)}[side]
    for a, b in arrows:
        ax, ay = boxes[a][0] + boxes[a][2] / 2, boxes[a][1] + boxes[a][3] / 2
        bx, by = boxes[b][0] + boxes[b][2] / 2, boxes[b][1] + boxes[b][3] / 2
        if abs(bx - ax) > abs(by - ay):
            p1, p2 = c(a, "r" if bx > ax else "l"), c(b, "l" if bx > ax else "r")
        else:
            p1, p2 = c(a, "b" if by > ay else "t"), c(b, "t" if by > ay else "b")
        s.append(f'<line x1="{p1[0]:.0f}" y1="{p1[1]:.0f}" x2="{p2[0]:.0f}" y2="{p2[1]:.0f}" stroke="{INK}" stroke-width="2" marker-end="url(#ar)"/>')
    for k, (x, y, w, h, t, sub, fill, edge) in boxes.items():
        s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{edge}" stroke-width="2"/>'
                 f'<text x="{x + 12}" y="{y + 30}" font-size="16" font-weight="700" fill="{INK}">{t}</text><text x="{x + 12}" y="{y + 52}" font-size="13" fill="{MUTED}">{sub}</text>')
    s.append('<rect x="40" y="790" width="22" height="14" fill="#e3f4ea" stroke="#1f8a4c"/><text x="70" y="802" font-size="14">in the game (the proposed schooling plan)</text>'
             '<rect x="480" y="790" width="22" height="14" fill="#fff2d9" stroke="#b26a00"/><text x="510" y="802" font-size="14">tools and measurements, in docs/reference/swarming-poster/</text>'
             '<rect x="1010" y="790" width="22" height="14" fill="#e4ecff" stroke="#2b5fd9"/><text x="1040" y="802" font-size="14">the player</text>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="900" viewBox="0 0 1440 900"><defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
           f'<path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker></defs>{"".join(s)}</svg>')
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Data flow mockup</title><style>{BASE_CSS} svg{{position:absolute;left:0;top:50px}} h1{{position:absolute;left:30px;top:12px}}</style></head>'
            f'<body><h1>How the pieces connect</h1>{svg}</body></html>')


def shot(html_path):
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    png = html_path.with_suffix(".png")
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", f"--user-data-dir={prof}", "--hide-scrollbars", "--window-size=1440,900",
                        f"--screenshot={png}", html_path.as_uri()], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)


def main():
    if len(sys.argv) > 1:
        print(__doc__); return
    for name, fn in (("poster", poster_page), ("frame-budget", frame_budget_page), ("data-flow", data_flow_page)):
        p = HERE / f"{name}.html"
        p.write_text(fn(), encoding="utf-8")
        shot(p)
        print(name, p.stat().st_size // 1024, "KB html,", p.with_suffix(".png").stat().st_size // 1024, "KB png")

main()
