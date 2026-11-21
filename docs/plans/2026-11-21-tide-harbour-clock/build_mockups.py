#!/usr/bin/env python3
"""Mockups for the Tide Harbour plan (docs/plans/2026-11-21-tide-harbour-clock.md).

Writes three self-contained 1440x900 pages beside this file and, with --png, a same-basename PNG for each
(headless google-chrome):

  harbour.html   the harbour, live: scrub the hour; the water is dozens of separately posed strips
  moments.html   five frozen moments: dawn, high tide at noon, sunset, dusk, night
  chooser.html   the clocks bundle: the chooser, a Dream straight into one clock, the settings choice

They are schematics of design intent, not game assets. The tide curve is ILLUSTRATIVE (made-up
amplitudes), not a prediction: the plan's Phase 0 finds the real constants.

    python3 docs/plans/2026-11-21-tide-harbour-clock/build_mockups.py --png
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

CSS = """
*{box-sizing:border-box}
html,body{margin:0;background:#0b0c10;color:#d9dce3;font:15px/1.35 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
body{width:1440px;height:900px;position:relative;overflow:hidden}
.tv{position:absolute;background:#000;border:10px solid #23252b;border-radius:14px;box-shadow:0 0 0 1px #3a3d46;overflow:hidden}
.tv svg{display:block;width:100%;height:100%}
.cap{position:absolute;color:#aeb4c0;font-size:14px}
.cap b{color:#eef0f4;font-weight:600}
h1{position:absolute;margin:0;font-size:19px;font-weight:600;color:#eef0f4}
button{font:inherit;color:#e8eaf0;background:#1c1f27;border:1px solid #3a3f4c;border-radius:8px;padding:7px 12px;cursor:pointer}
button:hover{background:#262a35}button.on{background:#34405c;border-color:#6d86c9}
label{color:#c3c8d3;user-select:none}
input[type=range]{accent-color:#e0704f}
"""

# ---------------------------------------------------------------------------
# The scene. renderScene(hours, phase, o) returns the inner SVG of a 1120x630 view.
SCENE_JS = r"""
const TAU = Math.PI * 2;
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, u) => a + (b - a) * u;
const hex = h => h[0] === '#' ? [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)) : h.match(/\d+/g).slice(0, 3).map(Number);
const mix = (a, b, u) => { const A = hex(a), B = hex(b); return 'rgb(' + A.map((v, i) => Math.round(lerp(v, B[i], u))).join(',') + ')'; };
const f1 = v => (Math.round(v * 10) / 10).toString();

// sky keys: hour, top, bottom, water, glow (lamps and windows)
const KEYS = [[0, '#070b1f', '#141c3f', '#0c1a2e', 1], [5.3, '#0f1535', '#2a2a5a', '#102038', .9], [6.2, '#6a4c93', '#f4a261', '#4a4a78', .4],
  [7.5, '#6db3e8', '#f6dcc0', '#3f7fa8', 0], [12, '#4fa3e0', '#bfe3f7', '#2f7fae', 0], [16.2, '#68a8d8', '#f2e0c0', '#3b7fa6', 0],
  [17.8, '#8e5da8', '#f49f6b', '#6a5a8a', .35], [18.7, '#2b2d6e', '#c75d6a', '#2c3260', .8], [19.8, '#0b1030', '#26285a', '#0e1a30', 1], [24, '#070b1f', '#141c3f', '#0c1a2e', 1]];
function sky(t) {
  for (let i = 0; i < KEYS.length - 1; i++) {
    const a = KEYS[i], b = KEYS[i + 1];
    if (t >= a[0] && t <= b[0]) { const u = (t - a[0]) / (b[0] - a[0]); return { top: mix(a[1], b[1], u), bot: mix(a[2], b[2], u), water: mix(a[3], b[3], u), glow: lerp(a[4], b[4], u) }; }
  }
  return { top: KEYS[0][1], bot: KEYS[0][2], water: KEYS[0][3], glow: 1 };
}
// The tide, from the shipped constants (wflevels/tide_harbour/tide_constants.json): a fit to the Navy's published predictions
// for Bangkok. Metres above the lowest low water. t is the hour of day in Thai time (UTC+7) on TIDE_DAY.
const TIDE = __TIDE__;   // [z0, [[cycles per hour, amplitude m, phase rev], ...]]
let TIDE_DAY = Math.floor((Date.now() + 7 * 3600e3 - Date.UTC(2026, 0, 1)) / 86400e3);   // days since 2026-01-01, Thai calendar
const tide = t => { const T = TIDE_DAY * 24 + t; let h = TIDE[0]; for (const c of TIDE[1]) h += c[1] * Math.cos(TAU * (c[0] * T + c[2])); return h; };
const PX_PER_M = 30;
const WATER_TOP = 336, WATER_BOT = 630, STRIPS = 36;
const rect = (x, y, w, h, fill, extra = '') => `<rect x="${f1(x)}" y="${f1(y)}" width="${f1(w)}" height="${f1(h)}" fill="${fill}" ${extra}/>`;

function renderScene(t, phase, o) {
  o = o || {};
  const id = o.id || 's';
  const S = sky(t), dark = clamp(S.glow);
  const level = (tide(t) - TIDE[0]) * PX_PER_M;                 // pixels the water is above its mean
  const wy = 452 - level;                                   // the water line at the piers
  let g = '', n = 0;
  g += `<defs><linearGradient id="${id}sk" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${S.top}"/><stop offset="1" stop-color="${S.bot}"/></linearGradient>
    <radialGradient id="${id}sun"><stop offset="0" stop-color="#fff6d8"/><stop offset="1" stop-color="#ffb35a" stop-opacity="0"/></radialGradient></defs>`;
  g += rect(0, 0, 1120, WATER_TOP + 2, `url(#${id}sk)`); n++;                      // the sky dome

  // sun on its arc, moon on the other half of the day
  const sunU = (t - 6) / 12, moonU = ((t < 6 ? t + 24 : t) - 18) / 12;
  if (sunU > -.05 && sunU < 1.05) { const x = lerp(90, 1030, sunU), y = WATER_TOP - Math.sin(Math.PI * clamp(sunU)) * 250 + 10;
    g += `<circle cx="${f1(x)}" cy="${f1(y)}" r="70" fill="url(#${id}sun)" opacity="${f1(1 - dark * .6)}"/><circle cx="${f1(x)}" cy="${f1(y)}" r="20" fill="#fff2cc"/>`; n += 2; }
  if (moonU > 0 && moonU < 1) { const x = lerp(90, 1030, moonU), y = WATER_TOP - Math.sin(Math.PI * moonU) * 230 + 20;
    g += `<circle cx="${f1(x)}" cy="${f1(y)}" r="16" fill="#e9eefc" opacity=".92"/>`; n++; }
  // clouds drift
  for (let k = 0; k < 3; k++) { const x = ((k * 420 + phase * 6 + t * 30) % 1500) - 200, y = 70 + k * 46;
    g += `<ellipse cx="${f1(x)}" cy="${y}" rx="${90 + k * 24}" ry="${16 + k * 3}" fill="#fff" opacity="${f1(.16 * (1 - dark * .7))}"/>`; n++; }
  // far bank and the temple spires
  g += rect(0, WATER_TOP - 26, 1120, 28, mix('#1a2a2a', '#3a4a40', 1 - dark), ''); n++;
  g += `<polygon points="520,${WATER_TOP - 26} 540,${WATER_TOP - 120} 560,${WATER_TOP - 26}" fill="${mix('#241a2e', '#6a5a70', 1 - dark)}"/>
        <polygon points="578,${WATER_TOP - 26} 590,${WATER_TOP - 84} 602,${WATER_TOP - 26}" fill="${mix('#241a2e', '#6a5a70', 1 - dark)}"/>`; n += 2;

  g += rect(0, WATER_TOP, 1120, WATER_BOT - WATER_TOP + 4, S.water); n++;                     // the river bed the bars ride on
  // the river: STRIPS separately posed bars, each lifted by a sum of two waves and tilted to the slope
  for (let i = 0; i < STRIPS; i++) {
    const d = i / (STRIPS - 1), y = WATER_TOP + 294 * Math.pow(d, 1.35), h = 4 + 14 * d;
    const w1 = Math.sin(TAU * (phase * .22 + d * 2.1 + i * .05)), w2 = Math.sin(TAU * (phase * .37 - d * 3.3));
    const dy = (w1 * 1.4 + w2 * .9) * (.4 + d * 1.6), tilt = w1 * 1.2;
    const glint = clamp(.5 + .5 * Math.sin(TAU * (phase * .6 + i * .31)));
    const fill = mix(S.water, mix(S.bot, '#ffffff', .25), .22 + .22 * glint * (1 - dark * .7) * (.4 + d * .6));
    g += `<rect x="-60" y="${f1(y + dy - level * .1 * (1 - d))}" width="1240" height="${f1(h + 1.5)}" fill="${fill}" transform="rotate(${f1(tilt)} 560 ${f1(y)})"${o.outline ? ' stroke="#ffd36a" stroke-width=".6" fill-opacity=".85"' : ''}/>`;
    n++;
  }
  // sun glitter column
  if (sunU > 0 && sunU < 1) { const x = lerp(90, 1030, sunU);
    for (let k = 0; k < 12; k++) { const y = WATER_TOP + 8 + k * 24, w = 6 + k * 3 + 10 * Math.sin(TAU * (phase * .9 + k * .37));
      g += rect(x - w / 2 + 10 * Math.sin(TAU * (phase * .4 + k)), y, Math.max(2, w), 3, '#fff2c8', `opacity="${f1(.5 * (1 - dark))}"`); n++; } }

  // stilt houses and the pier (fixed), with the tide gauge board
  g += rect(0, 300, 330, 20, mix('#3a1d18', '#7a3a2a', 1 - dark * .7)); n++;
  g += `<polygon points="10,300 120,230 240,230 340,300" fill="${mix('#2a120f', '#8a3a2a', 1 - dark * .7)}"/>`; n++;
  g += rect(60, 300, 230, 80, mix('#2a1c14', '#6a4a2c', 1 - dark * .7)); n++;
  g += rect(92, 322, 34, 40, `rgb(255,${Math.round(190 + 30 * dark)},${Math.round(110 - 40 * dark)})`, `opacity="${f1(.25 + .7 * S.glow)}"`); n++;
  g += rect(0, 380, 640, 14, mix('#2a1a10', '#8a6a3a', 1 - dark * .7)); n++;                  // pier deck
  for (const x of [40, 150, 270, 400, 520, 640]) g += rect(x, 394, 12, 96, mix('#1a110a', '#5a3d22', 1 - dark * .6));
  n += 6;
  g += `<polygon points="420,380 470,380 440,430 400,430" fill="none"/>`;
  // tide gauge board on a post
  g += rect(742, 380, 8, 118, mix('#1a110a', '#6a4a2c', 1 - dark * .6)); n++;
  for (let m = 1; m <= 3; m++) g += rect(742, wyMark(m), 8, 1.5, '#e8e0cc'), n;
  function wyMark(m) { return 452 - (m - TIDE[0]) * PX_PER_M; }
  g += `<polygon points="754,${f1(wy)} 774,${f1(wy - 7)} 774,${f1(wy + 7)}" fill="#ff7a4a"/>`; n++;

  // the raft rides the tide between two posts; the ropes change length
  const rx = 600 + 6 * Math.sin(TAU * phase * .15), ry = wy - 12 + 2 * Math.sin(TAU * (phase * .3));
  g += rect(rx - 60, ry, 120, 14, mix('#2a1a10', '#9a7a44', 1 - dark * .7)); n++;
  g += `<ellipse cx="${f1(rx - 34)}" cy="${f1(ry + 16)}" rx="9" ry="6" fill="#c76a2a"/><ellipse cx="${f1(rx + 34)}" cy="${f1(ry + 16)}" rx="9" ry="6" fill="#c76a2a"/>`; n += 2;
  g += `<line x1="520" y1="${f1(wy - 40)}" x2="${f1(rx - 60)}" y2="${f1(ry + 4)}" stroke="#d8c8a0" stroke-width="1.5"/><line x1="640" y1="${f1(wy - 40)}" x2="${f1(rx + 60)}" y2="${f1(ry + 4)}" stroke="#d8c8a0" stroke-width="1.5"/>`; n += 2;

  // boats bob, rock and swing on their moorings
  function boat(cx, scale, ph, canopy) {
    const bob = 2.6 * Math.sin(TAU * (phase * .27 + ph)), rock = 2.6 * Math.sin(TAU * (phase * .21 + ph * 1.7)), y = wy + 4 + bob;
    let s = `<g transform="translate(${f1(cx)} ${f1(y)}) rotate(${f1(rock)}) scale(${scale})">`;
    s += `<path d="M-70 -8 Q-60 18 -30 20 L40 20 Q70 18 84 -14 Q40 -2 -70 -8Z" fill="${mix('#2a120a', '#8a4a2a', 1 - dark * .7)}"/>`;
    if (canopy) s += `<path d="M-46 -8 Q-44 -36 -10 -38 L26 -38 Q46 -36 50 -8Z" fill="${mix('#2a2014', '#b8924a', 1 - dark * .7)}"/>`;
    return s + '</g>';
  }
  g += boat(300, 1.5, 0, true) + boat(470, 1.0, .3, false); n += 2;
  // the long-tail boat crosses the river in a few minutes: its place is a function of the clock
  const cross = (t * 60 / 7) % 1;
  g += boat(lerp(-80, 1200, cross), .7, .6, false).replace('translate(', 'translate(').replace(`${f1(wy + 4)}`, f1(WATER_TOP + 58)); n++;
  // water hyacinth drifts with the tide
  for (let k = 0; k < 4; k++) { const x = 220 + k * 190 + level * 1.5 + 8 * Math.sin(TAU * (phase * .1 + k)), y = wy + 40 + k * 14;
    g += `<ellipse cx="${f1(x)}" cy="${f1(y)}" rx="16" ry="5" fill="${mix('#102a14', '#4a8a3a', 1 - dark * .6)}"/>`; n++; }
  // birds
  for (let k = 0; k < 3; k++) { const x = ((phase * 22 + k * 140) % 1300) - 100, y = 120 + k * 36 + 10 * Math.sin(TAU * (phase * .2 + k));
    g += `<path d="M${f1(x - 9)} ${f1(y)} Q${f1(x)} ${f1(y - 7 * Math.sin(TAU * (phase * 1.4 + k)))} ${f1(x + 9)} ${f1(y)}" fill="none" stroke="#1a1a22" stroke-width="2" opacity="${f1(1 - dark * .6)}"/>`; n++; }

  // the clock tower and its dial: the one thing that tells the time
  g += rect(890, 310, 190, 130, mix('#2a2824', '#b8b0a0', 1 - dark * .65)); n++;                   // plinth and stairs
  g += rect(922, 150, 128, 168, mix('#3a342a', '#e8dcc0', 1 - dark * .65)); n++;                    // tower body
  g += `<polygon points="906,152 986,66 1066,152" fill="${mix('#2a1e10', '#c9a24a', 1 - dark * .6)}"/><polygon points="960,70 986,14 1012,70" fill="${mix('#2a1e10', '#c9a24a', 1 - dark * .6)}"/>`; n += 2;
  const cx = 986, cy = 218, R = 46;
  g += `<circle cx="${cx}" cy="${cy}" r="${R + 5}" fill="#c9a24a"/><circle cx="${cx}" cy="${cy}" r="${R}" fill="${mix('#4a463c', '#f6efdc', 1 - dark * .55)}"/>`; n += 2;
  for (let k = 0; k < 12; k++) { const a = k / 12 * TAU; g += `<line x1="${f1(cx + Math.sin(a) * (R - 9))}" y1="${f1(cy - Math.cos(a) * (R - 9))}" x2="${f1(cx + Math.sin(a) * (R - 2))}" y2="${f1(cy - Math.cos(a) * (R - 2))}" stroke="#2a2418" stroke-width="${k % 3 ? 1.6 : 3}"/>`; }
  const hh = (t % 12) / 12 * TAU, mm = ((t * 60) % 60) / 60 * TAU, ss = ((t * 3600) % 60) / 60 * TAU;
  const hand = (a, len, w, col) => `<line x1="${cx}" y1="${cy}" x2="${f1(cx + Math.sin(a) * len)}" y2="${f1(cy - Math.cos(a) * len)}" stroke="${col}" stroke-width="${w}" stroke-linecap="round"/>`;
  g += hand(hh, 24, 4, '#1a1610') + hand(mm, 36, 3, '#1a1610') + hand(ss, 40, 1.2, '#c02a1a'); n += 3;
  g += rect(944, 238 + 50, 84, 40, mix('#1a1410', '#8a7a58', 1 - dark * .6)); n++;                // the arch below the dial
  g += rect(970, 296, 32, 20, `rgb(255,${Math.round(180 + 30 * dark)},100)`, `opacity="${f1(.2 + .75 * S.glow)}"`); n++;
  // lanterns swing
  for (let k = 0; k < 3; k++) { const x = 120 + k * 150, sw = 6 * Math.sin(TAU * (phase * .33 + k * .3));
    g += `<line x1="${x}" y1="300" x2="${f1(x + sw)}" y2="322" stroke="#3a2a1a"/><circle cx="${f1(x + sw * 1.1)}" cy="328" r="7" fill="#ffb347" opacity="${f1(.35 + .65 * S.glow)}"/>`; n++; }
  if (o.counter) g += `<text x="14" y="26" font-size="15" fill="#fff" font-family="ui-monospace,Menlo,monospace" opacity=".92">${n} actors posed this frame</text>`;
  return { svg: g, actors: n, tide: tide(t), level: level };
}
const hhmm = t => { const m = Math.floor(t * 60 + 1e-6); return String(Math.floor(m / 60) % 24).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0'); };
"""


def tide_js() -> str:
    import json
    d = json.loads((HERE.parents[2] / "wflevels" / "tide_harbour" / "tide_constants.json").read_text())
    return json.dumps([d["z0_m"], [[c["cycles_per_hour"], c["amp_m"], c["phase_rev"]] for c in d["constituents"]]], separators=(",", ":"))


def page(title: str, body: str, script: str = "") -> str:
    scene = SCENE_JS.replace("__TIDE__", tide_js())
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>{title}</title>"
            f"<meta name=\"viewport\" content=\"width=1440\"><style>{CSS}</style></head><body>{body}"
            f"<script>{scene}\n{script}</script></body></html>")


def harbour() -> str:
    body = (
        '<div class="tv" style="left:150px;top:14px;width:1140px;height:650px"><svg id="scene" viewBox="0 0 1120 630"></svg></div>'
        '<div class="cap" style="left:14px;top:20px;width:128px;font-size:12.5px;line-height:1.5">Flat view of a 3D scene. The water is '
        'dozens of separate bars, each posed with its own height and tilt: the technique the plan proposes, shown live.</div>'
        '<div class="cap" style="left:1304px;top:20px;width:128px;font-size:12.5px;line-height:1.5">The tide is from the <b>shipped constants</b>, '
        'a fit to the Navy\'s published predictions for Bangkok, for today\'s date. The gauge board reads metres above the lowest low water.</div>'
        '<div style="position:absolute;left:160px;top:682px;width:1120px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">'
        '<button id="b-now">Now</button><button id="b-dawn">Dawn</button><button id="b-low">Low tide</button><button id="b-high">High tide</button>'
        '<button id="b-sun">Sunset</button><button id="b-night">Night</button><button id="b-play">Run ×600</button>'
        '<label><input type="checkbox" id="c-out"> outline the water bars</label>'
        '<span id="readout" style="margin-left:auto;font:600 20px ui-monospace,Menlo,monospace;color:#eef0f4"></span></div>'
        '<div style="position:absolute;left:160px;top:730px;width:1120px;display:flex;gap:12px;align-items:center">'
        '<span style="color:#8d94a3;font-size:13px">hour</span><input type="range" id="scrub" min="0" max="24" step="0.01" style="flex:1">'
        '<span id="what" style="color:#aeb4c0;font-size:13px;width:330px;text-align:right"></span></div>'
        '<div style="position:absolute;left:160px;top:785px;width:1120px"><svg id="curve" viewBox="0 0 1120 90" width="1120" height="90"></svg></div>'
    )
    script = r"""
const $ = id => document.getElementById(id);
const now = new Date();
let hour = now.getHours() + now.getMinutes() / 60, playing = false, last = performance.now(), t0 = performance.now();
function curve() {
  let d = '', lo = 9, hi = -9;
  for (let h = 0; h <= 24; h += .1) { const v = tide(h); lo = Math.min(lo, v); hi = Math.max(hi, v); }
  for (let h = 0; h <= 24; h += .1) { const x = h / 24 * 1120, y = 78 - (tide(h) - lo) / (hi - lo) * 66; d += (h ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1); }
  const cx = hour / 24 * 1120, cy = 78 - (tide(hour) - lo) / (hi - lo) * 66;
  let ticks = ''; for (let h = 0; h <= 24; h += 3) ticks += `<line x1="${h / 24 * 1120}" y1="4" x2="${h / 24 * 1120}" y2="84" stroke="#262a33"/><text x="${h / 24 * 1120 + 3}" y="88" font-size="11" fill="#8d94a3">${String(h).padStart(2, '0')}:00</text>`;
  $('curve').innerHTML = ticks + `<path d="${d}" fill="none" stroke="#6d86c9" stroke-width="2"/><circle cx="${cx}" cy="${cy}" r="5" fill="#ff7a4a"/>`;
}
function draw() {
  const phase = (performance.now() - t0) / 1000;
  const r = renderScene(hour, phase, { counter: true, outline: $('c-out').checked });
  $('scene').innerHTML = r.svg;
  $('readout').textContent = hhmm(hour) + '   tide ' + r.tide.toFixed(2) + ' m';
  if (document.activeElement !== $('scrub')) $('scrub').value = hour;
  const s = sky(hour); $('what').textContent = s.glow > .85 ? 'night: lamps and windows lit' : s.glow > .3 ? 'dusk or dawn' : 'daylight';
  curve();
}
function set(h) { hour = ((h % 24) + 24) % 24; }
function best(fn) { let b = 0, bv = fn(0); for (let h = 0; h < 24; h += .02) { const v = fn(h); if (v > bv) { bv = v; b = h; } } return b; }
$('b-now').onclick = () => { const d = new Date(); set(d.getHours() + d.getMinutes() / 60); playing = false; $('b-play').className = ''; };
$('b-dawn').onclick = () => set(6.1);
$('b-low').onclick = () => set(best(h => -tide(h)));
$('b-high').onclick = () => set(best(tide));
$('b-sun').onclick = () => set(17.85);
$('b-night').onclick = () => set(22.5);
$('b-play').onclick = () => { playing = !playing; $('b-play').className = playing ? 'on' : ''; };
$('scrub').oninput = e => set(parseFloat(e.target.value));
(function loop() {
  const t = performance.now(); if (playing) set(hour + (t - last) / 1000 * 600 / 3600);
  last = t; draw(); requestAnimationFrame(loop);
})();
const m = /h=(\d+(?:\.\d+)?)/.exec(location.hash); if (m) set(parseFloat(m[1]));
"""
    return page("Tide Harbour: the harbour", body, script)


def tide_at(hour: float, year=2026, month=11, day=21):
    """The shipped tide, metres above the lowest low water, at an hour of Thai time on a date, and whether it is rising."""
    import datetime as dt
    import json
    import math
    d = json.loads((HERE.parents[2] / "wflevels" / "tide_harbour" / "tide_constants.json").read_text())
    t0 = (dt.datetime(year, month, day) - dt.datetime(2026, 1, 1)).total_seconds() / 3600.0

    def h(x):
        return d["z0_m"] + sum(c["amp_m"] * math.cos(2 * math.pi * (c["cycles_per_hour"] * (t0 + x) + c["phase_rev"])) for c in d["constituents"])
    return h(hour), h(hour + 0.1) > h(hour - 0.1)


def _moment(hour: float, label: str, text: str):
    m, up = tide_at(hour)
    return (hour, f"<b>{label}</b> {text} Water {m:.2f} m above the lowest low water, {'rising' if up else 'falling'}.")


MOMENTS = [_moment(6.1, "06:06", "Dawn. The tower dial reads six."),
           _moment(12.0, "12:00", "Noon, flat light."),
           _moment(17.85, "17:51", "Sunset, the look of the concept art: gold on the water and the lanterns coming on."),
           _moment(19.3, "19:18", "Dusk. The sky has gone to violet, and the windows and the tower arch glow."),
           _moment(23.5, "23:30", "Night. The moon is up and the dial is still readable by lamplight."),
           _moment(3.2, "03:12", "Deep night. The scene is a pure function of the date and the time.")]


def moments() -> str:
    body = '<h1 style="left:40px;top:18px">Six moments. A Dream that starts at any of them looks exactly like this.</h1>'
    for i in range(len(MOMENTS)):
        col, row = i % 3, i // 3
        x, y = 40 + col * 460, 84 + row * 392
        body += (f'<div class="tv" style="left:{x}px;top:{y}px;width:440px;height:258px;border-width:6px;border-radius:9px"><svg id="m{i}" viewBox="0 0 1120 630"></svg></div>'
                 f'<div class="cap" style="left:{x + 4}px;top:{y + 268}px;width:432px">{MOMENTS[i][1]}</div>')
    script = ("TIDE_DAY = Math.floor((Date.UTC(2026, 10, 21) - Date.UTC(2026, 0, 1)) / 86400e3);\n"
              "const MOM=" + str([m[0] for m in MOMENTS]) + ";"
              "MOM.forEach((h,i)=>{document.getElementById('m'+i).innerHTML=renderScene(h,3.0+i*1.7,{id:'m'+i+'_'}).svg;});")
    return page("Tide Harbour: six moments", body, script)


def chooser() -> str:
    clocks = [("Minute Machine", "a Rube Goldberg machine that drops the minute flap"), ("Tide Harbour", "a stilt-house harbour, the tide and a clock tower")]
    rows = ""
    for i, (name, sub) in enumerate(clocks):
        sel = i == 1
        rows += (f'<div style="display:flex;align-items:center;gap:16px;padding:14px 22px;border-radius:12px;margin:6px 14px;'
                 f'background:{"#e8eaf0" if sel else "transparent"};color:{"#111318" if sel else "#d5d9e2"}">'
                 f'<span style="width:18px;height:18px;border-radius:50%;border:2px solid {"#111318" if sel else "#8d94a3"};display:inline-block;'
                 f'box-shadow:{"inset 0 0 0 3px #e8eaf0, inset 0 0 0 10px #111318" if sel else "none"}"></span>'
                 f'<span><span style="font-size:20px;font-weight:600">{name}</span><br><span style="font-size:13px;opacity:.75">{sub}</span></span></div>')
    menu = ('<div style="position:absolute;inset:0;background:linear-gradient(180deg,#14161c,#0c0d12);padding-top:30px">'
            '<div style="padding:0 36px 6px;font-size:28px;font-weight:700;color:#eef0f4">WF Clocks</div>'
            '<div style="padding:0 36px 18px;font-size:16px;color:#8d94a3">Choose a clock</div>' + rows +
            '<div style="position:absolute;left:36px;bottom:20px;font-size:13px;color:#8d94a3">▲ ▼ choose · OK start · Back leaves</div></div>')
    phone = ("".join(
        f'<div style="display:flex;justify-content:space-between;padding:11px 14px;border-bottom:1px solid #2a2e38;font-size:14px;color:{"#eef0f4" if v == "Random" else "#c3c8d3"}">'
        f'<span>{v}</span><span>{"●" if v == "Random" else "○"}</span></div>' for v in ("Random", "Minute Machine", "Tide Harbour")))
    body = (
        '<h1 style="left:40px;top:18px">One bundle, one chooser, and a way to skip it</h1>'
        f'<div class="tv" style="left:40px;top:70px;width:640px;height:360px;border-width:8px"><div style="position:relative;width:100%;height:100%">{menu}</div></div>'
        '<div class="cap" style="left:44px;top:446px;width:632px"><b>1. Open from the TV launcher.</b> No clock is named, so the engine\'s own level menu shows, built from a manifest: '
        'a title, a prompt and one line per clock. Back returns to it.</div>'
        '<div class="tv" style="left:720px;top:70px;width:640px;height:360px;border-width:8px"><svg id="d" viewBox="0 0 1120 630"></svg></div>'
        '<div class="cap" style="left:724px;top:446px;width:632px"><b>2. Start as a screensaver.</b> The Dream is told which clock to play (its saved choice, or Random resolved once), '
        'so the menu never appears. <code style="color:#f3d27a">am start … --es clock tide_harbour</code> does the same from a shell or the coordinator.</div>'
        '<div style="position:absolute;left:40px;top:560px;width:300px;border:8px solid #23252b;border-radius:26px;background:#14161c;padding:14px 0 0">'
        '<div style="padding:0 14px 10px;font-size:15px;font-weight:600;color:#eef0f4">Clock for the screensaver</div>' + phone + '</div>'
        '<div class="cap" style="left:372px;top:566px;width:420px"><b>3. Choose it once.</b> The same shell-only settings provider the Aquarium and Seahorse Dreams use '
        'offers the choice (<code style="color:#f3d27a">clock:random</code>, <code style="color:#f3d27a">clock:minute_machine</code>, <code style="color:#f3d27a">clock:tide_harbour</code>), '
        'so the coordinator and the KDE tray can set it too.</div>'
        '<div class="cap" style="left:840px;top:566px;width:520px"><b>The bundle</b> is one <code style="color:#f3d27a">cd.iff</code>: the clock levels in table-of-contents order, '
        'plus the menu chunk after the last. A level added later is one manifest line and one entry in the app\'s list of clocks.</div>'
    )
    script = "document.getElementById('d').innerHTML=renderScene(17.85,3.4,{id:'d_'}).svg;"
    return page("Tide Harbour: the clocks bundle", body, script)



def poster() -> str:
    """The A3 poster layout (portrait, 297 x 420 mm) drawn on the 1440x900 canvas, from the real constants and numbers."""
    import datetime as dt
    import json
    import math
    doc = json.loads((HERE.parents[2] / "wflevels" / "tide_harbour" / "tide_constants.json").read_text())
    epoch = dt.datetime(2026, 1, 1)

    def h(when):
        t = (when - epoch).total_seconds() / 3600.0
        return doc["z0_m"] + sum(c["amp_m"] * math.cos(2 * math.pi * (c["cycles_per_hour"] * t + c["phase_rev"])) for c in doc["constituents"])

    # the department's printed highs and lows for 8, 9 and 10 January 2026 (station HD): time, metres
    pub = {8: [("0437", 1.12), ("1132", 3.09), ("1731", 2.44), ("2043", 2.73)], 9: [("0446", 1.33), ("1139", 3.02), ("1804", 2.28), ("2139", 2.56)],
           10: [("0439", 1.59), ("1120", 2.97), ("1844", 2.14), ("2243", 2.39)]}
    X0, X1, Y0, Y1 = 10, 280, 20, 100                       # panel 1 plot box (user units of a 290 x 130 viewBox)

    def px(hours): return X0 + (X1 - X0) * hours / 72.0
    def py(m): return Y1 - (Y1 - Y0) * (m - 0.8) / (3.4 - 0.8)
    t_start = dt.datetime(2026, 1, 8)
    pts = " ".join(f"{px(k / 6):.1f},{py(h(t_start + dt.timedelta(minutes=10 * k))):.1f}" for k in range(0, 72 * 6 + 1))
    dots = ""
    for day, evs in pub.items():
        for hhmm, m in evs:
            hours = (day - 8) * 24 + int(hhmm[:2]) + int(hhmm[2:]) / 60.0
            dots += f'<circle cx="{px(hours):.1f}" cy="{py(m):.1f}" r="1.9" fill="#d9552b"/>'
    grid = "".join(f'<line x1="{px(24 * d)}" y1="{Y0 - 6}" x2="{px(24 * d)}" y2="{Y1 + 2}" stroke="#d6d1c4" stroke-width=".4"/><text x="{px(24 * d) + 2}" y="{Y1 + 9}" font-size="5.2" fill="#6b665a">{8 + d} Jan 00:00</text>' for d in range(3))
    p1 = (f'<svg viewBox="0 0 290 120" width="100%"><rect x="{X0}" y="{Y0 - 6}" width="{X1 - X0}" height="{Y1 - Y0 + 8}" fill="#fbf8ef"/>{grid}'
          f'<polyline points="{pts}" fill="none" stroke="#2c5d8a" stroke-width="1.1"/>{dots}</svg>')

    # panel 2: the four main waves and their sum, for one day
    c4 = {c["name"]: c for c in doc["constituents"] if c["name"] in ("K1", "O1", "M2", "S2")}
    def wave(name, k): 
        c = c4[name]; t = k / 6.0 + 7 * 24 * 1.0 + 24 * 7
        return c["amp_m"] * math.cos(2 * math.pi * (c["cycles_per_hour"] * t + c["phase_rev"]))
    rows = ""
    for i, name in enumerate(("K1", "O1", "M2", "S2")):
        base = 18 + i * 24
        path = " ".join(f"{10 + 270 * k / 144:.1f},{base - 17 * wave(name, k) / 0.5:.1f}" for k in range(145))
        rows += f'<polyline points="{path}" fill="none" stroke="#2c5d8a" stroke-width=".9"/><text x="8" y="{base - 12}" font-size="6" fill="#3d382c" text-anchor="end">{name}</text>'
    sumpath = " ".join(f"{10 + 270 * k / 144:.1f},{116 - 20 * sum(wave(n, k) for n in c4) / 1.4:.1f}" for k in range(145))
    p2 = f'<svg viewBox="0 0 290 130" width="100%">{rows}<line x1="10" y1="104" x2="280" y2="104" stroke="#8a8474" stroke-width=".4"/><polyline points="{sumpath}" fill="none" stroke="#d9552b" stroke-width="1.3"/><text x="146" y="127" font-size="5.5" fill="#d9552b" text-anchor="middle">sum of the four</text></svg>'

    # panel 4: error against the number of constituents (fitted 2026, scored on 2027)
    ns = [(6, 28.0), (12, 21.3), (24, 10.6), (32, 8.2), (48, 5.6), (64, 4.3), (96, 3.8), (171, 3.7)]
    bars = "".join(f'<rect x="{18 + i * 32}" y="{100 - e * 2.8:.1f}" width="22" height="{e * 2.8:.1f}" fill="{"#d9552b" if n == 64 else "#2c5d8a"}"/><text x="{29 + i * 32}" y="109" font-size="6" text-anchor="middle" fill="#3d382c">{n}</text><text x="{29 + i * 32}" y="{96 - e * 2.8:.1f}" font-size="6" text-anchor="middle" fill="#3d382c">{e}</text>' for i, (n, e) in enumerate(ns))
    p4 = f'<svg viewBox="0 0 290 120" width="100%">{bars}<text x="145" y="119" font-size="5.5" fill="#6b665a" text-anchor="middle">constituents kept (median error in cm, on a year the fit never saw)</text></svg>'

    # panel 5: the time-zone check
    zs = [("0 h (GMT)", 308.5), ("+6.5 h", 22.0), ("+7 h", 11.0), ("+7.5 h", 40.0)]
    zb = "".join(f'<rect x="{20 + i * 66}" y="{100 - min(m, 120) * .75:.1f}" width="44" height="{min(m, 120) * .75:.1f}" fill="{"#d9552b" if "7 h" == lab[:3] and lab == "+7 h" else "#2c5d8a"}"/><text x="{42 + i * 66}" y="109" font-size="6" text-anchor="middle" fill="#3d382c">{lab}</text><text x="{42 + i * 66}" y="{96 - min(m, 120) * .75:.1f}" font-size="6" text-anchor="middle" fill="#3d382c">{m:g} min</text>' for i, (lab, m) in enumerate(zs))
    p5 = f'<svg viewBox="0 0 290 120" width="100%">{zb}<text x="145" y="119" font-size="5.5" fill="#6b665a" text-anchor="middle">shift of the table against GMT: median mismatch with Ko Lak observations</text></svg>'

    def chip(kind):
        col = {"V": "#2a7a4b", "O": "#8a6d1f", "K": "#6b3fa0"}[kind]
        txt = {"V": "verified", "O": "other source", "K": "ours (measured)"}[kind]
        return f'<span style="display:inline-block;font-size:7.5px;padding:0 4px;border-radius:6px;background:{col};color:#fff;margin-left:4px;vertical-align:1px">{txt}</span>'

    def panel(n, title, body, caption):
        return (f'<div style="background:#fff;border:.6px solid #cfc9b8;padding:7px 8px 6px;margin-bottom:8px">'
                f'<div style="font:700 11.5px/1.15 Georgia,serif;color:#241f12"><span style="color:#d9552b">{n}</span> {title}</div>{body}'
                f'<div style="font-size:8.3px;line-height:1.3;color:#3d382c">{caption}</div></div>')

    flow = ('<div style="display:flex;gap:4px;align-items:center;font-size:8px;margin:6px 0">'
            + "".join(f'<div style="flex:1;border:.6px solid #8a8474;padding:4px 3px;text-align:center;background:#fbf8ef">{x}</div>' + ('<span style="color:#d9552b">▶</span>' if i < 4 else "")
                      for i, x in enumerate(["published table<br/>1225 highs and lows", "at each event:<br/>height = listed,<br/>slope = 0", "one linear<br/>least squares", "171 candidate<br/>waves, keep 64", "tide_constants<br/>.json"])) + '</div>')
    sheet = (
        '<div style="width:608px;height:860px;background:#f6f2e6;border:1px solid #aaa49a;box-shadow:0 3px 14px #0008;padding:18px 20px;overflow:hidden;font-family:Georgia,serif;color:#241f12"><div style="zoom:1.24">'
        '<div style="border-bottom:2px solid #241f12;padding-bottom:6px;margin-bottom:9px"><div style="font:700 25px/1 Georgia,serif;letter-spacing:.2px">The tide at Bangkok</div>'
        '<div style="font:11px/1.35 Georgia,serif;color:#3d382c;margin-top:3px">What the Chao Phraya does every day, how a computer can add it up, and how far to trust the sum. '
        'Station: Royal Thai Navy Headquarters, 13° 44′ N 100° 29′ E.</div></div>'
        '<div style="display:flex;gap:9px"><div style="flex:1.1">'
        + panel("1", "Two highs a day, or only one" + chip("K"), p1, "Three days of January 2026. Dots are the Navy&rsquo;s printed highs and lows; the line is our sum of 64 waves. Heights are metres above the lowest low water" + chip("V"))
        + panel("2", "A tide is a sum of waves" + chip("V"), p2, "K1 and O1 come once a day, M2 and S2 twice. Added, they make the lumpy curve above. 64 such waves are used in all.")
        + panel("3", "From a table to constants" + chip("K"), flow, "The table lists only the tops and bottoms, so nothing is drawn through them. Where it lists no event the tide has a flat shoulder.")
        + '</div><div style="flex:1">'
        + panel("4", "How good is it?" + chip("K"), p4, "Fitted to 2026 and scored on 2027, and the reverse: median error 4.1 to 4.5 cm, 90th percentile 11 cm, on a range of 2.8 m.")
        + panel("5", "Which clock does the table use?" + chip("K"), p5, "Observed hourly water at Ko Lak (GMT) lines up with the Navy&rsquo;s table only when the table is read as UTC+7: Thai local time.")
        + panel("6", "What the harbour does with it", '<div style="height:92px;margin:5px 0;background:linear-gradient(#e8dcc0 0 35%,#7aa3c0 35% 100%);position:relative"><div style="position:absolute;left:14px;top:8px;width:7px;height:78px;background:#6a4a2c"></div><div style="position:absolute;left:44px;top:46px;width:70px;height:13px;background:#8a4a2a;border-radius:0 0 30px 30px"></div><div style="position:absolute;right:16px;top:6px;width:36px;height:46px;background:#cfc7b0"></div></div>',
                 "The gauge board, the boats and their ropes, the raft and the hyacinth all follow this one number; the dial on the tower tells the time.")
        + panel("7", "What we do not know" + chip("O"), '<div style="height:2px"></div>', "The Navy&rsquo;s own constants are not public. Our fit is to its published predictions. No nodal correction. Discharge of the river is absorbed into the annual wave. Bangkok&rsquo;s form factor is 1.36 here and 1.06 in a model study, both &lsquo;mixed, mainly semidiurnal&rsquo;.")
        + '</div></div></div></div>')
    note = ('<div class="cap" style="left:690px;top:40px;width:700px;font-size:15px;line-height:1.5"><b>A3 poster, portrait, 297 &times; 420 mm</b> (drawn here at about 1:1.5 of a screen).<br/><br/>'
            'Every claim wears a chip: <b style="color:#2a7a4b">verified</b> (a source was read and says it), <b style="color:#8a6d1f">other source</b>, or <b style="color:#6b3fa0">ours (measured)</b> with the script that measures it. '
            'What could not be confirmed stays in the research document and is never printed; the build refuses if it is added.<br/><br/>'
            'Panels 1, 4 and 5 are <b>real data</b>: the shipped constants against the Navy&rsquo;s printed events, the out-of-sample errors, and the Ko Lak clock check. '
            'The harbour drawing in panel 6 is a placeholder for the finished scene.<br/><br/>'
            'Print on matte or uncoated A3 stock (the 2026&#8209;10&#8209;06 print was too glossy).</div>')
    body = f'<div style="position:absolute;left:40px;top:20px">{sheet}</div>{note}'
    return page("Tide Harbour: the tide poster", body)


PAGES = {"harbour": harbour, "moments": moments, "chooser": chooser, "poster": poster}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--png", action="store_true", help="also render each mockup to a 1440x900 PNG with google-chrome")
    args = ap.parse_args()
    for name, fn in PAGES.items():
        out = HERE / f"{name}.html"
        out.write_text(fn(), encoding="utf-8")
        print(f"{out.name}: {out.stat().st_size / 1024:.0f} KB")
        if args.png:
            png = HERE / f"{name}.png"
            url = out.as_uri() + ("#h=17.85" if name == "harbour" else "")
            subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1440,900",
                            "--virtual-time-budget=2500", f"--screenshot={png}", url],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if png.stat().st_size > 512 * 1024:
                from PIL import Image
                Image.open(png).convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT).save(png, optimize=True)
            print(f"  {png.name}: {png.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
