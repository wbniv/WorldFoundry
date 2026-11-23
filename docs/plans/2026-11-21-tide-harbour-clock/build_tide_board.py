#!/usr/bin/env python3
"""Mockup: tide data you can read in Tide Harbour (docs/plans/2026-11-21-tide-harbour-clock.md).

Will, 2026-11-21: "seems like we should have some actual tide data on the tide screensaver?"
A proposal, not a decision: a tide board on the pier with the next high water and the next low
water (time and height) and a rising or falling arrow, and numerals on the gauge board's metre marks.

Writes tide-board.html beside this file and, with --png, tide-board.png (headless google-chrome).
Reuses the harbour scene, the page shell and the shipped tide constants from build_mockups.py:

    python3 docs/plans/2026-11-21-tide-harbour-clock/build_tide_board.py --png
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_mockups as bm  # noqa: E402  (the scene, the CSS and the constants)

# The PNG is pinned to one moment so it does not change from day to day.
PNG_HASH = "#d=324&h=16.5"   # 2026-11-21 16:30 Thai time

BODY = (
    '<h1 style="left:14px;top:12px">Tide Harbour: tide data you can read '
    '<span style="font-weight:400;color:#aeb4c0;font-size:14px">&nbsp; proposal, not built</span></h1>'
    # the scene, with the board standing on the pier
    '<div class="tv" style="left:14px;top:46px;width:868px;height:494px"><svg id="scene" viewBox="0 0 1120 630"></svg></div>'
    # the board, close up
    '<div class="cap" style="left:900px;top:46px"><b>The tide board, close up</b></div>'
    '<div style="position:absolute;left:900px;top:70px;width:480px;height:240px"><svg id="close" viewBox="0 0 400 200" width="480" height="240"></svg></div>'
    '<div class="cap" style="left:900px;top:318px;width:526px;font-size:13px;line-height:1.45">'
    '<b>Top row:</b> the next high water. <b>Bottom row:</b> the next low water. Each has its time, to 10&nbsp;minutes, '
    'and its height, to 0.1&nbsp;m above the lowest low water. <b>Arrow:</b> the tide is rising or falling now.<br>'
    'All of it comes from the <b>same 64 waves</b> that move the river, stepped forward to the next turn. No table, no network.<br>'
    '<b>13 rigid actors</b> (proposed, untested): 12 digit drums that turn to a numeral, and the arrow. '
    'In the scene the board is about 315 &times; 158 pixels on a 1080p TV.</div>'
    # controls
    '<div style="position:absolute;left:14px;top:554px;width:868px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
    '<button id="b-now">Now</button><button id="b-rise">Rising</button><button id="b-fall">Falling</button>'
    '<button id="b-turn">At the turn</button><button id="b-night">Night</button>'
    '<label style="margin-left:10px"><input type="checkbox" id="c-thai" checked> Thai numerals</label></div>'
    '<div style="position:absolute;left:14px;top:596px;width:868px;display:flex;gap:12px;align-items:center">'
    '<span style="color:#8d94a3;font-size:13px">hour</span><input type="range" id="scrub" min="0" max="24" step="0.01" style="flex:1">'
    '<span id="readout" style="font:600 14px ui-monospace,Menlo,monospace;color:#eef0f4;width:330px;text-align:right;white-space:nowrap"></span></div>'
    # the curve the board is read from
    '<div style="position:absolute;left:14px;top:630px;width:868px"><svg id="curve" viewBox="0 0 868 150" width="868" height="150"></svg></div>'
    '<div class="cap" style="left:14px;top:788px;width:868px;font-size:13px;line-height:1.45">'
    '<b>A prediction, not a measurement.</b> The constants are fitted to the Royal Thai Navy Hydrographic Department\'s published '
    'table for Bangkok: within 4 to 5&nbsp;cm and 13&nbsp;minutes of it (median; 43&nbsp;minutes at the 90th percentile), which is why the '
    'board rounds to 10&nbsp;minutes. Rain and river discharge move the real river and are not in it.<br>'
    '<b>Found while drawing this:</b> the model wiggles at flat tops: 1440 turns in 2026 where the table lists 1225. '
    'The board ignores turns under 4&nbsp;cm, which leaves 1224 (<code>count_turns.py</code>). Grey marks on the curve are turns it skipped.</div>'
    # the states
    '<div class="cap" style="left:900px;top:482px"><b>States</b> (the same day)</div>'
    '<div id="states" style="position:absolute;left:900px;top:506px;width:526px;display:grid;grid-template-columns:1fr 1fr;gap:10px 14px"></div>'
)

SCRIPT = r"""
const $ = id => document.getElementById(id);
const TH = '๐๑๒๓๔๕๖๗๘๙';
let thai = true;
const dg = s => thai ? String(s).replace(/\d/g, d => TH[d]) : String(s);
const pad2 = n => String(n).padStart(2, '0');
// a time of day rounded to 10 minutes: the fit is not better than that
function fmtTime(t) { const m = Math.round((((t % 24) + 24) % 24) * 6) * 10 % 1440; return dg(pad2(Math.floor(m / 60))) + ':' + dg(pad2(m % 60)); }
const fmtH = h => dg(h.toFixed(1)) + (thai ? ' ม.' : ' m');

// Every turn of the model in [t, t + span] hours, then drop the wiggles: a pair of neighbouring turns less than MIN_SWING apart.
const MIN_SWING = 0.04;   // count_turns.py: 4 cm brings the count of turns to within 3 of the table's in both years
function turns(t, span) {
  const step = 1 / 60; let raw = [], prev = tide(t), cur = tide(t + step);
  for (let x = t + step; x < t + span; x += step) { const nxt = tide(x + step);
    if ((cur - prev) * (nxt - cur) < 0) raw.push({ t: x, h: cur, high: cur > prev });
    prev = cur; cur = nxt; }
  const kept = raw.map(e => ({ ...e })), skipped = [];
  for (;;) { let k = -1, small = MIN_SWING;
    for (let i = 0; i + 1 < kept.length; i++) { const s = Math.abs(kept[i + 1].h - kept[i].h); if (s < small) { small = s; k = i; } }
    if (k < 0) break; skipped.push(kept[k], kept[k + 1]); kept.splice(k, 2); }
  return { kept, skipped };
}
function reading(t) {
  const { kept, skipped } = turns(t, 40);
  const hi = kept.find(e => e.high), lo = kept.find(e => !e.high);
  return { now: tide(t), rising: kept.length ? kept[0].high : tide(t + .05) > tide(t), hi, lo, kept, skipped };
}

// The board, in a 400 x 200 box. dark is 0 by day and 1 at night, when its lantern lights it.
const FONT = `'IBM Plex Sans Thai','Noto Sans Thai','Sarabun',system-ui,sans-serif`;
function board(r, dark, bare) {      // bare: no frame, the wood runs to the edges (the river panel)
  const wood = mix('#3b2716', '#7d5a33', 1 - dark * .7), edge = mix('#170f08', '#3d2915', 1 - dark * .6), ink = '#f8efd6';
  let g = bare ? `<rect width="400" height="200" fill="${wood}"/>` : `<rect width="400" height="200" rx="10" fill="${edge}"/><rect x="6" y="6" width="388" height="188" rx="7" fill="${wood}"/>`;
  if (dark > .05 && !bare) g += `<rect x="6" y="6" width="388" height="188" rx="7" fill="#ffb347" opacity="${(.2 * dark).toFixed(2)}"/>`;   // bare: no lamp, it dims with the panel
  g += `<line x1="16" y1="100" x2="322" y2="100" stroke="${edge}" stroke-width="3"/>`;
  const row = (y, high, e) => {
    // the mark: a water line with a triangle above it (high water) or below it (low water)
    const mark = high ? `<line x1="18" y1="${y + 16}" x2="62" y2="${y + 16}" stroke="${ink}" stroke-width="5"/><polygon points="40,${y - 24} 58,${y + 4} 22,${y + 4}" fill="${ink}"/>`
                      : `<line x1="18" y1="${y - 16}" x2="62" y2="${y - 16}" stroke="${ink}" stroke-width="5"/><polygon points="40,${y + 24} 58,${y - 4} 22,${y - 4}" fill="${ink}"/>`;
    const txt = e ? `<text x="76" y="${y + 17}" font-size="47" font-weight="700" fill="${ink}" font-family="${FONT}">${fmtTime(e.t)}</text>` +
                    `<text x="318" y="${y + 14}" font-size="34" font-weight="600" fill="${ink}" font-family="${FONT}" text-anchor="end">${fmtH(e.h)}</text>`
                  : `<text x="76" y="${y + 17}" font-size="47" fill="${ink}" font-family="${FONT}">--:--</text>`;
    return mark + txt;
  };
  g += row(53, true, r.hi) + row(147, false, r.lo);
  // the arrow: one actor, turned up (rising) or down (falling)
  const col = r.rising ? '#9be28f' : '#ff9466';
  g += `<g transform="translate(359,100) rotate(${r.rising ? 0 : 180})"><polygon points="0,-62 26,-18 10,-18 10,58 -10,58 -10,-18 -26,-18" fill="${col}"/></g>`;
  return g;
}

// The board in the scene: on two posts at the end of the pier, with a lantern over it; and numerals on the gauge board.
const BX = 548, BY = 268, BS = .46;          // 184 x 92 scene pixels: 315 x 158 on a 1080p TV
function overlay(t, r) {
  const dark = clamp(sky(t).glow), post = mix('#1a110a', '#5a3d22', 1 - dark * .6), wy = m => 452 - (m - TIDE[0]) * PX_PER_M;
  let g = rect(BX + 22, BY + 80, 7, 34, post) + rect(BX + 155, BY + 80, 7, 34, post);
  g += `<g transform="translate(${BX},${BY}) scale(${BS})">${board(r, dark)}</g>`;
  g += `<line x1="${BX + 92}" y1="${BY - 14}" x2="${BX + 92}" y2="${BY - 4}" stroke="#2a1c10"/><circle cx="${BX + 92}" cy="${BY - 6}" r="5" fill="#ffb347" opacity="${(.3 + .7 * dark).toFixed(2)}"/>`;
  for (let m = 1; m <= 3; m++) g += `<text x="738" y="${(wy(m) + 5).toFixed(1)}" font-size="15" font-weight="700" text-anchor="end" fill="#f1e9d2" font-family="${FONT}">${dg(m)}</text>`;
  return g;
}

let hour = 16.5, t0 = performance.now();
function curve(r) {
  const W = 868, H = 150, a = hour - 4, b = hour + 30, X = t => (t - a) / (b - a) * W;
  let lo = 9, hi = -9; for (let t = a; t <= b; t += .1) { const v = tide(t); lo = Math.min(lo, v); hi = Math.max(hi, v); }
  const Y = v => H - 46 - (v - lo) / (hi - lo) * (H - 82);
  let d = ''; for (let t = a; t <= b; t += .05) d += (d ? 'L' : 'M') + X(t).toFixed(1) + ' ' + Y(tide(t)).toFixed(1);
  let g = ''; for (let t = Math.ceil(a / 6) * 6; t <= b; t += 6) g += `<line x1="${X(t)}" y1="6" x2="${X(t)}" y2="${H - 20}" stroke="#262a33"/><text x="${X(t) + 3}" y="${H - 6}" font-size="11" fill="#8d94a3">${pad2(((t % 24) + 24) % 24)}:00</text>`;
  g += `<path d="${d}" fill="none" stroke="#6d86c9" stroke-width="2"/>`;
  for (const e of r.skipped) g += `<circle cx="${X(e.t)}" cy="${Y(e.h)}" r="3.5" fill="none" stroke="#8d94a3"/>`;
  const tag = (e, high) => e ? `<circle cx="${X(e.t)}" cy="${Y(e.h)}" r="5" fill="#f8efd6"/><text x="${X(e.t)}" y="${Y(e.h) + (high ? -10 : 20)}" font-size="12.5" font-weight="600" text-anchor="middle" fill="#f8efd6" font-family="${FONT}">${high ? 'high' : 'low'} ${fmtTime(e.t)} · ${fmtH(e.h)}</text>` : '';
  g += tag(r.hi, true) + tag(r.lo, false);
  g += `<line x1="${X(hour)}" y1="6" x2="${X(hour)}" y2="${H - 20}" stroke="#ff7a4a" stroke-dasharray="3 3"/><circle cx="${X(hour)}" cy="${Y(r.now)}" r="5" fill="#ff7a4a"/><text x="${X(hour) + 7}" y="16" font-size="12" fill="#ff7a4a">now</text>`;
  $('curve').innerHTML = g;
}
const DATE = () => new Date(Date.UTC(2026, 0, 1) + TIDE_DAY * 86400e3).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
function draw() {
  const r = reading(hour), phase = (performance.now() - t0) / 1000;
  $('scene').innerHTML = renderScene(hour, phase, {}).svg + overlay(hour, r);
  $('close').innerHTML = board(r, clamp(sky(hour).glow));
  $('readout').textContent = DATE() + ' ' + hhmm(hour) + ' · ' + r.now.toFixed(2) + ' m, ' + (r.rising ? 'rising' : 'falling');
  if (document.activeElement !== $('scrub')) $('scrub').value = hour;
  curve(r);
}
// the hours of the day that show each state
function pick() {
  let rise = 0, fall = 0, rs = -9, fs = 9;
  for (let h = 6; h < 18; h += .05) { const s = tide(h + .1) - tide(h - .1); if (s > rs) { rs = s; rise = h; } if (s < fs) { fs = s; fall = h; } }
  const day = turns(6, 30).kept, turn = (day.find(e => e.high) || { t: 12 }).t - .05;
  return { rise, fall, turn, night: 22.5 };
}
function states() {
  const p = pick(), list = [['Rising', p.rise], ['Falling', p.fall], ['At the turn: high water in 3 minutes', p.turn], ['Night: lit by its lantern', p.night]];
  $('states').innerHTML = list.map(([name, h]) => `<div><svg viewBox="0 0 400 200" width="256" height="128">${board(reading(h), clamp(sky(h % 24).glow))}</svg>` +
    `<div style="color:#aeb4c0;font-size:12.5px;margin-top:2px">${name} <span style="color:#8d94a3">(${hhmm(h % 24)})</span></div></div>`).join('');
  return p;
}
function set(h) { hour = ((h % 24) + 24) % 24; draw(); }
let P = null;
function all() { P = states(); draw(); }
$('b-now').onclick = () => { const d = new Date(Date.now() + 7 * 3600e3); TIDE_DAY = Math.floor((d - Date.UTC(2026, 0, 1)) / 86400e3); hour = d.getUTCHours() + d.getUTCMinutes() / 60; all(); };
$('b-rise').onclick = () => set(P.rise);
$('b-fall').onclick = () => set(P.fall);
$('b-turn').onclick = () => set(P.turn);
$('b-night').onclick = () => set(P.night);
$('c-thai').onchange = e => { thai = e.target.checked; all(); };
$('scrub').oninput = e => set(parseFloat(e.target.value));
const hd = /d=(\d+)/.exec(location.hash), hh = /h=(\d+(?:\.\d+)?)/.exec(location.hash);
if (hd) TIDE_DAY = parseInt(hd[1], 10);
if (hh) hour = parseFloat(hh[1]); else { const d = new Date(Date.now() + 7 * 3600e3); hour = d.getUTCHours() + d.getUTCMinutes() / 60; }
all();
(function loop() { if (document.activeElement !== $('scrub')) draw(); setTimeout(() => requestAnimationFrame(loop), 500); })();
document.documentElement.dataset.ready = '1';
"""


# The numerals, the turning-point search and the reading: shared with build_river_map.py.
COMMON_JS = SCRIPT.split("// The board, in a 400 x 200 box.", 1)[0]
# The board itself (and FONT), for the river panel, which carries the same readings above its map.
BOARD_JS = "// The board:" + SCRIPT.split("// The board, in a 400 x 200 box.", 1)[1].split("// The board in the scene", 1)[0]


def tide_board() -> str:
    return bm.page("Tide Harbour: the tide board", BODY, SCRIPT)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--png", action="store_true", help="also render tide-board.png (1440x900) with google-chrome")
    args = ap.parse_args()
    out = HERE / "tide-board.html"
    out.write_text(tide_board(), encoding="utf-8")
    print(f"{out.name}: {out.stat().st_size / 1024:.0f} KB")
    if args.png:
        png = HERE / "tide-board.png"
        subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1440,900",
                        "--virtual-time-budget=2500", f"--screenshot={png}", out.as_uri() + PNG_HASH],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if png.stat().st_size > 512 * 1024:
            from PIL import Image
            Image.open(png).convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT).save(png, optimize=True)
        print(f"  {png.name}: {png.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
