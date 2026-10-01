#!/usr/bin/env python3
"""make_mockups.py: the mockups for the swarming-poster plan, each a self-contained 1440x900 HTML (inline CSS/SVG) plus a same-name PNG (headless Chrome).

  poster.html        the real poster (docs/reference/swarming-poster/poster.html) scaled into the canvas, with a guide to its panels
  frame-budget.html  what one Forth step costs in a 60 fps frame, all at once vs spread over frames (numbers from measured.json)
  mailboxes.html     the mailbox map: where school.fth's state lives, with the values of a real run (the Forth, in the tank, tick 300)
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


def mailboxes_page():
    sys.path.insert(0, str(REF))
    import tank_trial as tt, forth_check as fc
    r, h = tt.trial(5, 6, 3, 1, ticks=300, s=2.0, theta=120.0)
    n = 11
    state = [[h.read(fc.BASE + i * fc.STRIDE + f) for f in range(14)] for i in range(n)]
    par = [h.read(fc.PAR + k) for k in range(21)]
    h.close()
    FIELDS = ["MB_X", "MB_Y", "MB_Z", "MB_VX", "MB_VY", "MB_VZ", "MB_NX", "MB_NY", "MB_NZ", "MB_NVX", "MB_NVY", "MB_NVZ", "MB_STARTLE", "unused"]
    PARAMS = ["MB_RR  r_r", "MB_DRO  Δr_o now", "MB_DRA  Δr_a now", "MB_COSB  cos blind", "MB_COST  cos turn", "MB_SINT  sin turn", "MB_STEP  speed·dt", "MB_LEADW  leader w", "MB_WALL  wall zone", "MB_STARTLE_T  s",
              "MB_DT  dt", "MB_LOX  box low x", "(MB_LOX+1)  low y", "(MB_LOX+2)  low z", "MB_HIX  box high x", "(MB_HIX+1)  high y", "(MB_HIX+2)  high z", "MB_DRO_SWARM", "MB_DRA_SWARM", "MB_DRO_SCHOOL", "MB_DRA_SCHOOL"]
    SCR = ["MB_SUM_R", "+1", "+2", "MB_SUM_O", "+1", "+2", "MB_SUM_A", "+1", "+2", "MB_N_R", "MB_N_O", "MB_N_A", "MB_WANT", "+1", "+2", "MB_ME",
           "MB_U", "+1", "+2", "MB_YOU", "MB_PERP", "+1", "+2", "MB_DIST", "MB_R2"]
    s = []
    # --- the address map (0..1900) ---
    X0, XW, MAXA = 40, 1360, 1900
    ax = lambda a: X0 + a / MAXA * XW
    blocks = [(600, 638, "player fish rig", "#e4ecff", "#2b5fd9", "existing"), (700, 719, "level", "#e4ecff", "#2b5fd9", ""), (720, 739, "sway", "#e4ecff", "#2b5fd9", ""),
              (740, 759, "camera", "#e4ecff", "#2b5fd9", ""), (800, 953, "school state 11 × 14", "#e3f4ea", "#1f8a4c", "proposed"), (960, 980, "params", "#e3f4ea", "#1f8a4c", ""),
              (985, 1009, "scratch", "#e3f4ea", "#1f8a4c", ""), (1100, 1499, "followers’ rig blocks, 10 × 40 (open: the rig takes a base)", "#fff2d9", "#b26a00", "proposed, not built")]
    s.append(f'<rect x="{X0}" y="114" width="{XW}" height="36" fill="#f3f7fa" stroke="#9fb0bd"/>')
    for a in range(0, 1901, 100):
        s.append(f'<line x1="{ax(a):.1f}" y1="150" x2="{ax(a):.1f}" y2="158" stroke="{MUTED}"/><text x="{ax(a):.1f}" y="172" font-size="12" text-anchor="middle" fill="{MUTED}">{a}</text>')
    for lo, hi, name, fill, edge, tag in blocks:
        s.append(f'<rect x="{ax(lo):.1f}" y="114" width="{max(ax(hi + 1) - ax(lo), 3):.1f}" height="36" fill="{fill}" stroke="{edge}" stroke-width="1.5"/>')
    lab = [(600, 62, "600–638 the player’s fish rig (existing)", "#2b5fd9"), (700, 78, "700–759 level, sway, camera (existing)", "#2b5fd9"),
           (800, 94, "800–1009 school.fth: state, params, scratch (proposed)", "#1f8a4c"), (1100, 62, "1100–1499 the ten followers’ rig blocks (proposed, not built)", "#b26a00")]
    for a, y, t, col in lab:
        s.append(f'<line x1="{ax(a):.1f}" y1="{y + 4}" x2="{ax(a):.1f}" y2="114" stroke="{col}"/><text x="{ax(a) + 4:.1f}" y="{y}" font-size="13" font-weight="700" fill="{col}">{t}</text>')
    s.append(f'<text x="{X0}" y="194" font-size="13" fill="{MUTED}">Global user mailboxes are 2..1900 and shared by every actor (clownfish.py).. The proposed addresses are the ones the tests run at (forth_check.py: BASE 800, PAR 960, SCR 985).</text>')
    # --- the state grid ---
    gx, gy, cw, chh = 40, 258, 68, 22
    s.append(f'<text x="{gx}" y="226" font-size="16" font-weight="700" fill="{INK}">School state: 11 fish × 14 slots (a real run: school setting, w = 3, tick 300)</text>')
    s.append(f'<text x="{gx}" y="{gy - 6}" font-size="12" fill="{MUTED}">fish</text>')
    cols = list(zip(*state))
    for f in range(14):
        s.append(f'<text x="{gx + 56 + f * cw + cw / 2:.0f}" y="{gy - 6}" font-size="12" text-anchor="middle" fill="{INK}" font-weight="700">{FIELDS[f]}</text>')
    for i in range(n):
        y = gy + i * chh
        s.append(f'<text x="{gx}" y="{y + 16}" font-size="12" fill="{INK}" font-weight="700">{"0 leader" if i == 0 else i}</text>')
        for f in range(14):
            v = state[i][f]
            lo, hi = min(cols[f]), max(cols[f])
            t = 0.0 if hi - lo < 1e-9 else (v - lo) / (hi - lo)
            col = "#%02x%02x%02x" % (int(236 - t * 200), int(244 - t * 150), int(248 - t * 120)) if f != 13 else "#f3f3f3"
            fg = "#ffffff" if t > 0.62 and f != 13 else INK
            s.append(f'<rect x="{gx + 56 + f * cw}" y="{y}" width="{cw - 2}" height="{chh - 2}" fill="{col}"/><text x="{gx + 56 + f * cw + cw / 2 - 1:.0f}" y="{y + 16}" font-size="12" text-anchor="middle" fill="{fg}">{v:.2f}</text>')
    import textwrap
    for k, ln in enumerate(textwrap.wrap("The mailbox of a cell is 800 + 14·fish + its MB_ slot. Slots 0–2 position (body lengths), 3–5 a unit heading, 6–11 the next state (committed only after every follower has read the old one), 12 the startle timer, 13 unused. Each column is shaded from its own minimum to its maximum.", 150)):
        s.append(f'<text x="{gx}" y="{gy + n * chh + 16 + k * 15}" font-size="12" fill="{MUTED}">{ln}</text>')
    # --- params ---
    px = 1130
    s.append(f'<text x="{px - 40}" y="226" font-size="16" font-weight="700" fill="{INK}">Parameters, 960..980</text>')
    for k in range(21):
        y = 240 + k * 17
        s.append(f'<text x="{px - 40}" y="{y + 12}" font-size="12" fill="{MUTED}">{960 + k}</text><text x="{px}" y="{y + 12}" font-size="12" fill="{INK}">{PARAMS[k]}</text><text x="{px + 190}" y="{y + 12}" font-size="12" font-weight="700" text-anchor="end" fill="{INK}">{par[k]:.3g}</text>')
    # --- scratch ---
    sy = 600
    s.append(f'<text x="{gx}" y="{sy}" font-size="16" font-weight="700" fill="{INK}">Scratch, 985..1009 (rewritten for every follower; nothing in it is state)</text>')
    for k in range(25):
        x = gx + (k % 13) * 104; y = sy + 14 + (k // 13) * 44
        s.append(f'<rect x="{x}" y="{y}" width="100" height="38" fill="#f3f7fa" stroke="#9fb0bd"/><text x="{x + 4}" y="{y + 15}" font-size="12" fill="{MUTED}">{985 + k}</text><text x="{x + 4}" y="{y + 31}" font-size="12" fill="{INK}">{SCR[k]}</text>')
    # --- notes ---
    notes = ["Why a map: every actor and the Director share one number space, so a new script must say which numbers it owns. 200 mailboxes are needed here; the next free hundreds are 760..799 (kept spare) and 1010..1099.",
             f"Cost of using mailboxes: each read or write is one system call into the engine. The {json.loads((REF / 'measured.json').read_text())['device']['ms']:.1f} ms per step on the Chromecast already counts them (as a plain array); in the engine each goes through the object manager, which Phase 0 measures.",
             "Open: the ten followers need their own copy of the rig’s 39 mailboxes (600..638 today are one fish’s). That means the rig must take a base address (a change in clownfish_idle.fth), or the followers are posed by a smaller rig."]
    for i, t in enumerate(notes):
        s.append(f'<text x="{gx}" y="{722 + i * 44}" font-size="13" fill="{INK}">{t[:165]}</text>' + (f'<text x="{gx}" y="{722 + i * 44 + 15}" font-size="13" fill="{INK}">{t[165:]}</text>' if len(t) > 165 else ""))
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="900" viewBox="0 0 1440 900">{"".join(s)}</svg>'
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Mailbox map mockup</title><style>{BASE_CSS} svg{{position:absolute;left:0;top:0}}</style></head>'
            f'<body>{svg}<h1 style="position:absolute;left:40px;top:8px;font-size:22px">Where the school’s state lives: the mailboxes</h1></body></html>')


def shot(html_path):
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    png = html_path.with_suffix(".png")
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", f"--user-data-dir={prof}", "--hide-scrollbars", "--window-size=1440,900",
                        f"--screenshot={png}", html_path.as_uri()], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)


def main():
    if len(sys.argv) > 1:
        print(__doc__); return
    for name, fn in (("poster", poster_page), ("frame-budget", frame_budget_page), ("mailboxes", mailboxes_page), ("data-flow", data_flow_page)):
        p = HERE / f"{name}.html"
        p.write_text(fn(), encoding="utf-8")
        shot(p)
        print(name, p.stat().st_size // 1024, "KB html,", p.with_suffix(".png").stat().st_size // 1024, "KB png")

main()
