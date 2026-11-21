#!/usr/bin/env python3
"""Mockup: the river panel in Tide Harbour (docs/plans/2026-11-21-tide-harbour-clock.md).

Will, 2026-11-21: "how about an inset with a map of the river? add mockup for that idea, too", then
"let's just make it take up the left or right side as a full-length side panel". So the map is a
full-height panel at one side of the screen, with the tide board's readings above it. Not built. The river is its real course (chao-phraya-centreline.json, from
OpenStreetMap); the level is the shipped tide model. The travelling high water is ILLUSTRATIVE:
its travel time is assumed, not measured, and the page says so.

Writes river-map.html beside this file and, with --png, river-map.png (headless google-chrome):

    python3 docs/plans/2026-11-21-tide-harbour-clock/build_river_map.py --png
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_mockups as bm          # noqa: E402  (the scene, the CSS and the constants)
import build_tide_board as tb       # noqa: E402  (numerals, turning points, the reading)

PNG_HASH = "#d=324&h=16.5"   # 2026-11-21 16:30 Thai time, as the tide-board mockup

BODY = (
    '<h1 style="left:14px;top:12px">Tide Harbour: the river panel, full height at one side '
    '<span style="font-weight:400;color:#aeb4c0;font-size:14px">&nbsp; proposal, not built</span></h1>'
    '<div class="tv" style="left:14px;top:46px;width:868px;height:494px"><svg id="scene" viewBox="0 0 1120 630"></svg></div>'
    # the map, close up, and what it says
    '<div class="cap" style="left:900px;top:46px"><b>The panel, close up</b></div>'
    '<div style="position:absolute;left:900px;top:70px;width:262px;height:550px"><svg id="close" viewBox="0 0 300 630" width="262" height="550"></svg></div>'
    '<div class="cap" style="left:1178px;top:70px;width:252px;font-size:12.5px;line-height:1.42">'
    '<b>At the top:</b> the next high water and the next low water, with time and height, and the rising or falling arrow '
    '(the <a href="tide-board.html" style="color:#9ec1ff">tide board</a>).<br><br>'
    '<b>The river is real:</b> its course from the sea to the city, drawn from OpenStreetMap.<br><br>'
    '<b>The tower</b> marks this harbour: the Navy\'s Bangkok station, <b>50&nbsp;km up the river</b> from its mouth (measured along that line).<br><br>'
    '<b>The column</b> is the tide here and now, in metres, with the rising or falling arrow. The same model moves the water.<br><br>'
    '<b>The staff at the bottom</b> is Bangkok Bar, where the Navy publishes a second table.<br><br>'
    '<b>Not shown as fact:</b> how long high water takes to travel from the bar to the city. Fitting the bar\'s table with the same tool '
    'would measure it; until then the travelling band is a sketch, off by default.<br><br>'
    '<b>Untested:</b> whether the engine draws a panel fixed to the screen. If not, it is a slab the camera carries.</div>'
    # controls
    '<div style="position:absolute;left:14px;top:554px;width:868px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
    '<button id="b-now">Now</button><button id="b-high">High</button><button id="b-low">Low</button><button id="b-night">Night</button>'
    '<span style="width:8px"></span><button id="b-right" class="on">Right side</button><button id="b-left">Left side</button>'
    '<label style="margin-left:8px"><input type="checkbox" id="c-thai" checked> Thai</label>'
    '<label style="margin-left:8px"><input type="checkbox" id="c-crest"> travelling high water (sketch)</label></div>'
    '<div style="position:absolute;left:14px;top:596px;width:868px;display:flex;gap:12px;align-items:center">'
    '<span style="color:#8d94a3;font-size:13px">hour</span><input type="range" id="scrub" min="0" max="24" step="0.01" style="flex:1">'
    '<span id="readout" style="font:600 14px ui-monospace,Menlo,monospace;color:#eef0f4;width:330px;text-align:right;white-space:nowrap"></span></div>'
    # states
    '<div class="cap" style="left:14px;top:630px"><b>States</b> (the same day)</div>'
    '<div id="states" style="position:absolute;left:14px;top:654px;width:560px;display:flex;gap:16px"></div>'
    '<div class="cap" style="left:590px;top:654px;width:292px;font-size:12.5px;line-height:1.45">'
    '<b>Where it goes.</b> A full-height panel at one side, 27% of the width (Will, 2026&#8209;11&#8209;21). The harbour is framed in the rest, '
    'so the camera pulls back to keep the house and the tower in view (drawn here at 82%). '
    'Left or right is still open: both are here. <b>One thing to settle:</b> a panel that never moves is against this clock\'s '
    'burn-in rule (D10, nothing sits still). The fix proposed is small: the panel drifts a few pixels with the camera.<br><br>'
    '<b>Credit.</b> Wherever the map is shown: &copy;&nbsp;OpenStreetMap contributors, a line in the app\'s credits.</div>'
    '<div class="cap" style="left:900px;top:650px;width:526px;font-size:12.5px;line-height:1.45">'
    '<b>Sources.</b> River: &copy; OpenStreetMap contributors (ODbL), 74 points, <code>chao-phraya-centreline.json</code>. '
    'Station position: the department\'s table (13&deg;&nbsp;44&prime;&nbsp;36&Prime;&nbsp;N, 100&deg;&nbsp;29&prime;&nbsp;25&Prime;&nbsp;E). '
    'Bangkok Bar: PSMSL station 287 (13.45&deg;&nbsp;N, 100.6&deg;&nbsp;E). The coast is not drawn: only the river was fetched.</div>'
)

SCRIPT = r"""
const RIVER = __RIVER__;                     // [[lon, lat], ...], mouth first
const HD = __HD__, BB = __BB__;              // [lon, lat]
const HD_KM = __HD_KM__;                     // km up the river from the line's start
// The map box is 240 x 400. North is up; one pixel is KMPX kilometres.
const LAT0 = 13.43, LAT1 = 13.80, LONC = 100.541, KMPX = (LAT1 - LAT0) * 111.2 / 360, COS = Math.cos(13.65 * Math.PI / 180);
const MX = lon => 136 + (lon - LONC) * COS * 111.2 / KMPX, MY = lat => 380 - (lat - LAT0) * 111.2 / KMPX;
const SHOWN = RIVER.filter(p => p[1] <= LAT1 + .004);
const KM = [0]; for (let i = 1; i < RIVER.length; i++) KM.push(KM[i - 1] + Math.hypot((RIVER[i][0] - RIVER[i - 1][0]) * COS, RIVER[i][1] - RIVER[i - 1][1]) * 111.2);
function along(km) { for (let i = 1; i < RIVER.length; i++) if (KM[i] >= km) { const u = (km - KM[i - 1]) / (KM[i] - KM[i - 1]); return [lerp(RIVER[i - 1][0], RIVER[i][0], u), lerp(RIVER[i - 1][1], RIVER[i][1], u)]; } return RIVER[RIVER.length - 1]; }
const LABEL = { city: ['กรุงเทพฯ', 'Bangkok'], mouth: ['ปากน้ำ', 'Pak Nam'], gulf: ['อ่าวไทย', 'Gulf of Thailand'], km: ['กม.', 'km'], sea: ['จากทะเล', 'from the sea'] };
const L = k => LABEL[k][thai ? 0 : 1];
const CREST_H = 2;   // ILLUSTRATIVE: hours assumed for high water to travel from the mouth to the city. Not measured.
let crest = false;

const paperOf = dark => mix('#8f8262', '#eadfc2', 1 - dark * .8);
function riverMap(r, dark, phase, bare) {      // bare: no frame and no paper of its own (the panel supplies the paper)
  const paper = paperOf(dark), ink = mix('#1d150c', '#3a2a18', 1 - dark), frame = mix('#170f08', '#3d2915', 1 - dark * .6);
  const water = mix('#2c5f86', '#3f86b8', 1 - dark * .5);
  let g = bare ? '' : `<rect width="240" height="400" rx="8" fill="${frame}"/><rect x="5" y="5" width="230" height="390" rx="5" fill="${paper}"/>`;
  if (dark > .05 && !bare) g += `<rect x="5" y="5" width="230" height="390" rx="5" fill="#ffb347" opacity="${(.16 * dark).toFixed(2)}"/>`;
  const d = SHOWN.map((p, i) => (i ? 'L' : 'M') + MX(p[0]).toFixed(1) + ' ' + MY(p[1]).toFixed(1)).join('');
  g += `<path d="${d}" fill="none" stroke="${water}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>`;
  // the open sea below the mouth: only a label and three ripples, because the coast was not fetched
  const m = RIVER[0];
  for (let k = 0; k < 3; k++) g += `<path d="M${MX(m[0]) - 34 + k * 10} ${MY(m[1]) + 16 + k * 9} q6 -5 12 0 t12 0 t12 0" fill="none" stroke="${water}" stroke-width="1.6" opacity=".7"/>`;
  g += `<text x="${MX(m[0]) + 8}" y="${MY(m[1]) + 54}" font-size="13" text-anchor="end" fill="${ink}" font-family="${FONT}" font-style="italic">${L('gulf')}</text>`;
  g += `<text x="${MX(m[0]) - 16}" y="${MY(m[1]) + 12}" font-size="12" text-anchor="end" fill="${ink}" font-family="${FONT}">${L('mouth')}</text>`;
  // Bangkok Bar: a tide staff
  const bx = MX(BB[0]), by = MY(BB[1]);
  g += `<line x1="${bx}" y1="${by - 9}" x2="${bx}" y2="${by + 7}" stroke="${ink}" stroke-width="2"/><line x1="${bx - 4}" y1="${by - 5}" x2="${bx + 4}" y2="${by - 5}" stroke="${ink}" stroke-width="1.5"/><line x1="${bx - 4}" y1="${by + 1}" x2="${bx + 4}" y2="${by + 1}" stroke="${ink}" stroke-width="1.5"/>`;
  // the travelling high water (a sketch): a bright band that reaches the tower as the board's high water arrives
  if (crest && r.hi) { const lead = r.hi.t - r.t; if (lead >= 0 && lead <= CREST_H) { const p = along(HD_KM * (1 - lead / CREST_H));
    g += `<circle cx="${MX(p[0]).toFixed(1)}" cy="${MY(p[1]).toFixed(1)}" r="9" fill="#fff6c8" opacity=".85"/><circle cx="${MX(p[0]).toFixed(1)}" cy="${MY(p[1]).toFixed(1)}" r="15" fill="none" stroke="#fff6c8" opacity=".5"/>`; } }
  // this harbour: a small tower, a lamp that breathes, and its name
  const hx = MX(HD[0]), hy = MY(HD[1]), pulse = 6 + 3 * Math.sin(TAU * phase * .5);
  g += `<circle cx="${hx}" cy="${hy}" r="${pulse.toFixed(1)}" fill="none" stroke="#e0592f" stroke-width="2" opacity=".8"/>`;
  g += `<rect x="${hx - 4}" y="${hy - 13}" width="8" height="15" fill="#f4ecd6" stroke="${ink}"/><polygon points="${hx - 6},${hy - 13} ${hx},${hy - 22} ${hx + 6},${hy - 13}" fill="#c9a04a" stroke="${ink}"/>`;
  g += `<text x="${hx - 12}" y="${hy - 8}" font-size="15" font-weight="700" text-anchor="end" fill="${ink}" font-family="${FONT}">${L('city')}</text>`;
  g += `<text x="${hx - 12}" y="${hy + 7}" font-size="10" text-anchor="end" fill="${ink}" font-family="${FONT}">${dg(50)} ${L('km')} ${L('sea')}</text>`;
  // scale bar and north
  const ten = 10 / KMPX;
  g += `<line x1="16" y1="382" x2="${16 + ten}" y2="382" stroke="${ink}" stroke-width="2"/><line x1="16" y1="378" x2="16" y2="386" stroke="${ink}"/><line x1="${16 + ten}" y1="378" x2="${16 + ten}" y2="386" stroke="${ink}"/><text x="${20 + ten}" y="386" font-size="11" fill="${ink}" font-family="${FONT}">${dg(10)} ${L('km')}</text>`;
  g += `<polygon points="24,20 30,38 24,34 18,38" fill="${ink}"/>`;
  // the level column: 0 to 3.5 m, the pointer at the tide now, the arrow above it
  const cy = v => 330 - v / 3.5 * 250;
  g += `<rect x="205" y="${cy(3.5)}" width="9" height="250" fill="${mix('#6b5a3c', '#cdbf9a', 1 - dark * .6)}" stroke="${ink}"/><rect x="205" y="${cy(r.now).toFixed(1)}" width="9" height="${(330 - cy(r.now)).toFixed(1)}" fill="${water}"/>`;
  for (let v = 1; v <= 3; v++) g += `<line x1="200" y1="${cy(v)}" x2="214" y2="${cy(v)}" stroke="${ink}"/><text x="197" y="${cy(v) + 5}" font-size="13" font-weight="700" text-anchor="end" fill="${ink}" font-family="${FONT}">${dg(v)}</text>`;
  g += `<polygon points="217,${cy(r.now).toFixed(1)} 229,${(cy(r.now) - 6).toFixed(1)} 229,${(cy(r.now) + 6).toFixed(1)}" fill="#e0592f"/>`;
  g += `<g transform="translate(210,52) rotate(${r.rising ? 0 : 180})"><polygon points="0,-16 10,0 4,0 4,16 -4,16 -4,0 -10,0" fill="${r.rising ? '#3f9a4a' : '#d9643a'}"/></g>`;
  return g;
}

// The panel: 300 x 630, the full height of the 1120 x 630 screen. The tide board's readings above, the river below.
// No border (Will, 2026-11-21: "it needs no border"): the wood band and the paper run to the panel's edges.
function panel(r, dark, phase) {
  return `<rect width="300" height="630" fill="${paperOf(dark)}"/>` +
    (dark > .05 ? `<rect width="300" height="630" fill="#ffb347" opacity="${(.16 * dark).toFixed(2)}"/>` : '') +
    `<g transform="scale(.75)">${board(r, dark, true)}</g>` +
    `<g transform="translate(6,150) scale(1.2)">${riverMap(r, dark, phase, true)}</g>`;
}
let place = 'right', hour = 16.5, t0 = performance.now();
// The harbour is framed in the other 820 pixels. The house, the pier and the tower span more than that, so the
// camera pulls back: the scene is drawn at 82%, with more sky above it. The engine's framing is its own to choose.
function frame(scene, t, r, phase) {
  const dark = clamp(sky(t).glow), left = place === 'left', x0 = left ? 300 : 0, px = left ? 0 : 820;
  return `<defs><clipPath id="view"><rect x="${x0}" y="0" width="820" height="630"/></clipPath></defs>` +
    `<rect x="${x0}" y="0" width="820" height="630" fill="${sky(t).top}"/>` +
    `<g clip-path="url(#view)"><g transform="translate(${x0 - 49},113) scale(.82)">${scene}</g></g>` +
    `<g transform="translate(${px},0)">${panel(r, dark, phase)}</g>`;
}
const read = t => ({ ...reading(t), t });
const DATE = () => new Date(Date.UTC(2026, 0, 1) + TIDE_DAY * 86400e3).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
function draw() {
  const r = read(hour), phase = (performance.now() - t0) / 1000;
  $('scene').innerHTML = frame(renderScene(hour, phase, {}).svg, hour, r, phase);
  $('close').innerHTML = panel(r, clamp(sky(hour).glow), phase);
  $('readout').textContent = DATE() + ' ' + hhmm(hour) + ' · ' + r.now.toFixed(2) + ' m, ' + (r.rising ? 'rising' : 'falling');
  if (document.activeElement !== $('scrub')) $('scrub').value = hour;
}
function pick() { const day = turns(0, 24).kept; return { high: (day.find(e => e.high) || { t: 12 }).t, low: (day.find(e => !e.high) || { t: 6 }).t, night: 22.5 }; }
let P = null;
function states() {
  P = pick(); const keep = crest;
  const list = [['High water', P.high % 24, false], ['Low water', P.low % 24, false], ['Night', P.night, false], ['On its way (sketch)', (P.high - 1) % 24, true]];
  $('states').innerHTML = list.map(([name, h, c]) => { crest = c; const s = `<div style="width:120px"><svg viewBox="0 0 300 630" width="100" height="210">${panel(read(h), clamp(sky(h).glow), 0)}</svg>` +
    `<div style="color:#aeb4c0;font-size:12px;margin-top:2px;line-height:1.3">${name} <span style="color:#8d94a3">(${hhmm(h)})</span></div></div>`; return s; }).join('');
  crest = keep;
}
function set(h) { hour = ((h % 24) + 24) % 24; draw(); }
function all() { states(); draw(); }
$('b-now').onclick = () => { const d = new Date(Date.now() + 7 * 3600e3); TIDE_DAY = Math.floor((d - Date.UTC(2026, 0, 1)) / 86400e3); hour = d.getUTCHours() + d.getUTCMinutes() / 60; all(); };
$('b-high').onclick = () => set(P.high);
$('b-low').onclick = () => set(P.low);
$('b-night').onclick = () => set(P.night);
const where = p => { place = p; $('b-right').className = p === 'right' ? 'on' : ''; $('b-left').className = p === 'left' ? 'on' : ''; draw(); };
$('b-right').onclick = () => where('right');
$('b-left').onclick = () => where('left');
$('c-thai').onchange = e => { thai = e.target.checked; all(); };
$('c-crest').onchange = e => { crest = e.target.checked; draw(); };
$('scrub').oninput = e => set(parseFloat(e.target.value));
const hd = /d=(\d+)/.exec(location.hash), hh = /h=(\d+(?:\.\d+)?)/.exec(location.hash);
if (hd) TIDE_DAY = parseInt(hd[1], 10);
if (hh) hour = parseFloat(hh[1]); else { const d = new Date(Date.now() + 7 * 3600e3); hour = d.getUTCHours() + d.getUTCMinutes() / 60; }
if (/place=left/.test(location.hash)) place = 'left';
all(); where(place);
(function loop() { if (document.activeElement !== $('scrub')) draw(); setTimeout(() => requestAnimationFrame(loop), 120); })();
document.documentElement.dataset.ready = '1';
"""


def river_map() -> str:
    doc = json.loads((HERE / "chao-phraya-centreline.json").read_text(encoding="utf-8"))
    hd, bb = doc["station_HD"], doc["station_BB"]
    script = (SCRIPT.replace("__RIVER__", json.dumps(doc["points"], separators=(",", ":")))
              .replace("__HD_KM__", str(hd["km_up_river_from_the_line_start"]))
              .replace("__HD__", json.dumps([round(hd["lon"], 5), round(hd["lat"], 5)]))
              .replace("__BB__", json.dumps([bb["lon"], bb["lat"]])))
    return bm.page("Tide Harbour: the river panel", BODY, tb.COMMON_JS + tb.BOARD_JS + script)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--png", action="store_true", help="also render river-map.png (1440x900) with google-chrome")
    args = ap.parse_args()
    out = HERE / "river-map.html"
    out.write_text(river_map(), encoding="utf-8")
    print(f"{out.name}: {out.stat().st_size / 1024:.0f} KB")
    if args.png:
        png = HERE / "river-map.png"
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
