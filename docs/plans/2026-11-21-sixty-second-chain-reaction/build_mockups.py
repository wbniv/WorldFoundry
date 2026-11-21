#!/usr/bin/env python3
"""Mockups for the Minute Machine plan (docs/plans/2026-11-21-sixty-second-chain-reaction.md).

Writes four self-contained 1440x900 pages beside this file and, with --png, a
same-basename PNG for each (headless google-chrome):

  machine.html   the machine running from the clock: scrub, jump, speed
  moments.html   six frozen moments, including the hour change
  timeline.html  one minute, piece by piece: armed, acting, spent, re-arming
  picker.html    the Android surfaces: screensaver list, banner, portrait strip

They are schematics of design intent (a flat side view), not game assets. The
one timeline table TL below feeds the drawing code, the timeline bar and the
chart, so the three cannot disagree.

    python3 docs/plans/2026-11-21-sixty-second-chain-reaction/build_mockups.py --png
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Seconds within the minute. The plan's act table quotes these numbers.
TL = {
    "rail": [0, 12],
    "dominoes": [12, 20],
    "seesaw": [20, 22],
    "sand": [22, 52],
    "hold": [52, 55],
    "last": [55, 60],
    "bucket_empty": [1, 7],
    "sand_lift": [7, 20],
    "marble_lift": [30, 58],
    "comb": [41, 52.1],
    "flip": 0.4,
    "cascade": 0.12,
    "push_in": [50, 58],
    "pull_back": [1, 5],
}

CSS = """
*{box-sizing:border-box}
html,body{margin:0;background:#0b0c10;color:#d9dce3;font:15px/1.35 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
body{width:1440px;height:900px;position:relative;overflow:hidden}
.tv{position:absolute;background:#000;border:10px solid #23252b;border-radius:14px;box-shadow:0 0 0 1px #3a3d46}
.tv svg{display:block;width:100%;height:100%}
.cap{position:absolute;color:#aeb4c0;font-size:14px}
.cap b{color:#eef0f4;font-weight:600}
h1{position:absolute;margin:0;font-size:19px;font-weight:600;color:#eef0f4}
.note{position:absolute;color:#8d94a3;font-size:13px}
button{font:inherit;color:#e8eaf0;background:#1c1f27;border:1px solid #3a3f4c;border-radius:8px;padding:7px 12px;cursor:pointer}
button:hover{background:#262a35}
button.on{background:#34405c;border-color:#6d86c9}
label{color:#c3c8d3;user-select:none}
input[type=range]{accent-color:#e0704f}
"""

# ---------------------------------------------------------------------------
# The scene: every pose is a function of (hour, minute, seconds-in-minute).
# renderScene(sec, o) returns the inner SVG of a 1120x630 view.
SCENE_JS = r"""
const TL = __TL__;
const TABLE = 520, MR = 12;
const c01 = x => Math.max(0, Math.min(1, x));
const seg = (t, a, b) => c01((t - a) / (b - a));
const sm = u => { u = c01(u); return u * u * (3 - 2 * u); };
const lerp = (a, b, u) => a + (b - a) * u;
const f1 = v => (Math.round(v * 10) / 10).toString();
const RAILS = [[80, 118, 330, 158], [360, 200, 100, 244], [76, 290, 352, 520]];
const ry = (r, x) => r[1] + (x - r[0]) * (r[3] - r[1]) / (r[2] - r[0]);
const GATE_Y = ry(RAILS[0], 92) - MR;
const DN = 16, DX0 = 390, DP = 20, DW = 7, DH = 46, DLEAN = 69.5;

function marble(t) {
  const sq = u => u * u;
  if (t < 4.2) { const x = lerp(92, 342, sq(t / 4.2)); return { x, y: ry(RAILS[0], x) - MR, v: 1 }; }
  if (t < 4.5) return { x: 342, y: lerp(ry(RAILS[0], 342), ry(RAILS[1], 342), sq((t - 4.2) / .3)) - MR, v: 1 };
  if (t < 8.2) { const x = lerp(342, 88, sq((t - 4.5) / 3.7)); return { x, y: ry(RAILS[1], x) - MR, v: 1 }; }
  if (t < 8.5) return { x: 88, y: lerp(ry(RAILS[1], 88), ry(RAILS[2], 88), sq((t - 8.2) / .3)) - MR, v: 1 };
  if (t < 11.4) { const x = lerp(88, 352, sq((t - 8.5) / 2.9)); return { x, y: ry(RAILS[2], x) - MR, v: 1 }; }
  if (t < 12) return { x: lerp(352, 378, (t - 11.4) / .6), y: TABLE - MR, v: 1 };
  if (t < 12.5) return { x: lerp(378, 362, sm((t - 12) / .5)), y: TABLE - MR, v: 1 };
  if (t < 13.2) return { x: 362, y: lerp(TABLE - MR, TABLE + 40, sq((t - 12.5) / .7)), v: 1 };
  if (t < 30) return { x: 60, y: 505, v: 0 };
  if (t < 57) return { x: 60, y: lerp(505, GATE_Y, (t - 30) / 27), v: 1 };
  if (t < 58) return { x: lerp(60, 92, sm(t - 57)), y: GATE_Y, v: 1 };
  return { x: 92, y: GATE_Y, v: 1 };
}

function dominoAngle(i, t) {
  const last = i === DN - 1;
  const fin = last ? 80 : DLEAN;
  const f = TL.dominoes[0] + .5 * i;
  const r = TL.comb[0] + .7 * i;
  if (t < f) return 0;
  if (t < r) { const u = (t - f) / (last ? 1.0 : 2.0); return fin * (last ? c01(u) * c01(u) : c01(u)); }
  return fin * (1 - sm((t - r) / .6));
}

function sandState(t) {
  const bucket = t < TL.sand[0] ? 1 - seg(t, 2, 5.5) : seg(t, TL.sand[0], TL.sand[1]);
  const hopper = t < TL.sand_lift[0] ? 0 : t < TL.sand_lift[1] ? seg(t, TL.sand_lift[0], TL.sand_lift[1])
               : t < TL.sand[0] ? 1 : 1 - seg(t, TL.sand[0], TL.sand[1]);
  const trough = t < 2 ? 0 : t < 5.5 ? seg(t, 2, 5.5) : t < 7 ? 1 : 1 - seg(t, 7, 20);
  const tip = sm(seg(t, 1, 2.5)) - sm(seg(t, 5.5, 7));
  let pin = 0;
  if (t < 5.5) pin = 20 * bucket;
  else if (t >= TL.last[0]) for (let k = 0; k < 5; k++) pin += 4 * sm(seg(t, 55 + k, 55.15 + k));
  let click = 0;
  if (t >= TL.last[0]) { const fr = t - Math.floor(t); click = fr < .25 ? Math.sin(fr / .25 * Math.PI) : 0; }
  return { bucket, hopper, trough, tip, pin, click };
}

function hhmm(sec) {
  const s = ((Math.floor(sec) % 86400) + 86400) % 86400;
  const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60;
  return String(h).padStart(2, '0') + String(m).padStart(2, '0');
}

function digit(ch, cx, mid, fill) {
  return `<text x="${cx}" y="${mid + 34}" font-size="96" font-weight="700" text-anchor="middle" fill="${fill}"
    font-family="Helvetica Neue,Helvetica,Arial,sans-serif" transform="translate(${cx} 0) scale(.56 1) translate(${-cx} 0)">${ch}</text>`;
}

function flapCell(id, x, y, w, h, oldCh, newCh, p) {
  const mid = y + h / 2, cx = x + w / 2;
  const card = `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="3" fill="#0c0d10"/>`;
  const defs = `<clipPath id="${id}t"><rect x="${x}" y="${y}" width="${w}" height="${h / 2}"/></clipPath>
    <clipPath id="${id}b"><rect x="${x}" y="${mid}" width="${w}" height="${h / 2}"/></clipPath>`;
  const split = `<line x1="${x}" y1="${mid}" x2="${x + w}" y2="${mid}" stroke="#000" stroke-width="2"/>
    <line x1="${x}" y1="${mid + 1.5}" x2="${x + w}" y2="${mid + 1.5}" stroke="#2c2f37" stroke-width="1"/>`;
  if (p <= 0 || p >= 1 || oldCh === newCh) {
    const ch = p >= 1 ? newCh : oldCh;
    return card + digit(ch, cx, mid, '#f0ece0') + split;
  }
  const ang = p * Math.PI, sy = Math.abs(Math.cos(ang));
  const moving = p < .5
    ? `<g transform="translate(0 ${mid}) scale(1 ${f1(sy * 100) / 100}) translate(0 ${-mid})"><g clip-path="url(#${id}t)">
         <rect x="${x}" y="${y}" width="${w}" height="${h / 2}" fill="#15171c"/>${digit(oldCh, cx, mid, '#cfcbc0')}</g></g>`
    : `<g transform="translate(0 ${mid}) scale(1 ${f1(sy * 100) / 100}) translate(0 ${-mid})"><g clip-path="url(#${id}b)">
         <rect x="${x}" y="${mid}" width="${w}" height="${h / 2}" fill="#15171c"/>${digit(newCh, cx, mid, '#fffaf0')}</g></g>`;
  return defs + card
    + `<g clip-path="url(#${id}t)">${digit(newCh, cx, mid, '#f0ece0')}</g>`
    + `<g clip-path="url(#${id}b)">${digit(oldCh, cx, mid, '#f0ece0')}</g>`
    + moving + split;
}

function tag(x, y, n) {
  return `<g><circle cx="${x}" cy="${y}" r="13" fill="#0b0c10" stroke="#f3d27a" stroke-width="1.5"/>
    <text x="${x}" y="${y + 5}" text-anchor="middle" font-size="14" font-weight="700" fill="#f3d27a"
    font-family="system-ui,sans-serif">${n}</text></g>`;
}

function renderScene(sec, o) {
  o = o || {};
  const id = o.id || 's';
  const t = ((sec % 60) + 60) % 60;
  const now = hhmm(sec), prev = hhmm(sec - 60);
  const onHour = now.slice(2) === '00';
  const S = sandState(t);
  let g = '';

  // backdrop
  g += `<defs>
    <linearGradient id="${id}bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1c2029"/><stop offset="1" stop-color="#0e1015"/></linearGradient>
    <linearGradient id="${id}wd" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5b4130"/><stop offset="1" stop-color="#2c1f16"/></linearGradient>
    <radialGradient id="${id}mb" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#ff9a7a"/><stop offset=".5" stop-color="#d8452f"/><stop offset="1" stop-color="#7d1a10"/></radialGradient>
    <clipPath id="${id}hop"><polygon points="780,165 860,165 828,245 812,245"/></clipPath>
    <clipPath id="${id}fr"><rect x="0" y="0" width="1120" height="630"/></clipPath>
  </defs>`;
  g += `<rect x="0" y="0" width="1120" height="630" fill="url(#${id}bg)"/>`;

  // camera push-in toward the latch (decision D6)
  let zoom = 1;
  if (o.push !== false) {
    zoom = 1 + .10 * (t >= TL.push_in[0] ? sm(seg(t, TL.push_in[0], TL.push_in[1])) : 1 - sm(seg(t, TL.pull_back[0], TL.pull_back[1])));
  }
  g += `<g clip-path="url(#${id}fr)"><g transform="translate(1120 400) scale(${zoom.toFixed(4)}) translate(-1120 -400)">`;

  // sand lift (behind)
  g += `<rect x="843" y="150" width="14" height="358" fill="#20242d" stroke="#343946"/>`;
  const slOn = t > TL.sand_lift[0] && t < TL.sand_lift[1];
  for (let k = 0; k < 26; k++) {
    const yy = 508 - ((k * 14 + (slOn ? t * 30 : 0)) % 358);
    g += `<line x1="843" y1="${f1(yy)}" x2="857" y2="${f1(yy - 6)}" stroke="${slOn ? '#b79c62' : '#4a5160'}" stroke-width="2"/>`;
  }
  g += `<line x1="845" y1="152" x2="826" y2="166" stroke="#4a5160" stroke-width="4" stroke-linecap="round"/>`;
  if (slOn) g += `<line x1="826" y1="166" x2="822" y2="${f1(lerp(243, 172, S.hopper))}" stroke="#e3c27a" stroke-width="2.5"/>`;

  // bell (hour only)
  let bell = 0, ham = 24;
  if (onHour) {
    ham = 24 * (1 - sm(seg(t, .3, .5))) + 24 * sm(seg(t, .5, 1.2));
    if (t > .5 && t < 7.5) { const q = t - .5; bell = 16 * Math.pow(1 - q / 7, 2) * Math.sin(2 * Math.PI * 1.3 * q); }
  }
  g += `<line x1="585" y1="520" x2="585" y2="120" stroke="#6b4d34" stroke-width="7"/>
        <line x1="585" y1="122" x2="640" y2="122" stroke="#6b4d34" stroke-width="6" stroke-linecap="round"/>
        <g transform="rotate(${f1(bell)} 625 126)"><path d="M625 126 L625 134 M607 172 Q607 138 625 136 Q643 138 643 172 Z" fill="#cfa64a" stroke="#8c6d28" stroke-width="2"/>
        <circle cx="625" cy="176" r="4" fill="#8c6d28"/></g>
        <g transform="rotate(${f1(ham)} 600 124)"><line x1="600" y1="124" x2="600" y2="160" stroke="#9aa3b2" stroke-width="3"/><rect x="596" y="154" width="14" height="9" rx="2" fill="#9aa3b2"/></g>`;

  // rails and end posts
  for (const r of RAILS) g += `<line x1="${r[0]}" y1="${r[1]}" x2="${r[2]}" y2="${r[3]}" stroke="#b88a55" stroke-width="6" stroke-linecap="round"/>`;
  g += `<line x1="366" y1="146" x2="366" y2="208" stroke="#8a6740" stroke-width="5" stroke-linecap="round"/>
        <line x1="70" y1="234" x2="70" y2="298" stroke="#8a6740" stroke-width="5" stroke-linecap="round"/>`;
  // gate at the top of the rail: lifted by the falling flap
  const gate = 22 * (sm(seg(t, 0, .3)) - sm(seg(t, 1.5, 2.2)));
  g += `<rect x="105" y="${f1(GATE_Y - 16 - gate)}" width="5" height="30" rx="2" fill="#cfa64a"/>`;

  // marble lift
  g += `<rect x="46" y="96" width="28" height="424" fill="#222631" stroke="#3a4050"/>`;
  const M = marble(t);
  if (M.v) g += `<circle cx="${f1(M.x)}" cy="${f1(M.y)}" r="${MR}" fill="url(#${id}mb)"/>`;
  for (let k = 0; k < 31; k++) {
    const yy = 520 - ((k * 14 + t * 14.78) % 424);
    g += `<line x1="46" y1="${f1(yy)}" x2="74" y2="${f1(yy - 8)}" stroke="#6f7a8c" stroke-width="2" opacity=".8"/>`;
  }
  g += `<rect x="40" y="474" width="40" height="46" rx="3" fill="#2d3340" stroke="#465066"/>
        <line x1="62" y1="${f1(GATE_Y + MR + 2)}" x2="96" y2="${f1(GATE_Y + MR + 2)}" stroke="#b88a55" stroke-width="5" stroke-linecap="round"/>`;

  // hopper with its sand, rod, gate, chute
  g += `<polygon points="780,165 860,165 828,245 812,245" fill="#2a2f3a" stroke="#7f8ea3" stroke-width="2.5"/>`;
  if (S.hopper > .005) g += `<rect x="780" y="${f1(lerp(245, 172, S.hopper))}" width="80" height="80" fill="#e3c27a" clip-path="url(#${id}hop)"/>`;
  const see = sm(seg(t, 20.3, 20.8)) - sm(seg(t, 52.1, 52.6));
  const sa = lerp(-12, 12, see) * Math.PI / 180;
  const sxr = 745 + 50 * Math.cos(sa), syr = 508 - 50 * Math.sin(sa), sxl = 745 - 50 * Math.cos(sa), syl = 508 + 50 * Math.sin(sa);
  g += `<line x1="795" y1="${f1(syr)}" x2="795" y2="${f1(syr - 252)}" stroke="#9aa3b2" stroke-width="3"/>
        <line x1="795" y1="${f1(syr - 252)}" x2="808" y2="${f1(syr - 256)}" stroke="#9aa3b2" stroke-width="3" stroke-linecap="round"/>
        <rect x="${f1(808 - 22 * see)}" y="246" width="24" height="5" rx="2" fill="#cfa64a"/>
        <line x1="820" y1="254" x2="878" y2="287" stroke="#7f8ea3" stroke-width="5" stroke-linecap="round"/>`;
  const bTop = 330 + 46 * S.bucket;
  const sandOn = t > TL.sand[0] + .3 && t < TL.sand[1];
  if (sandOn) g += `<polyline points="820,250 878,283 878,${f1(bTop + 56 - 50 * S.bucket)}" fill="none" stroke="#e3c27a" stroke-width="3" stroke-linejoin="round"/>`;

  // trough and the sand that the bucket pours back
  g += `<path d="M831 506 L831 520 L885 520 L885 506" fill="none" stroke="#7f8ea3" stroke-width="3"/>`;
  if (S.trough > .01) g += `<rect x="833" y="${f1(519 - 11 * S.trough)}" width="50" height="${f1(11 * S.trough)}" fill="#e3c27a"/>`;
  if (t > 2 && t < 5.5) g += `<line x1="862" y1="${f1(bTop + 14)}" x2="860" y2="510" stroke="#e3c27a" stroke-width="3"/>`;

  // bucket, bail, string, pulleys, spring, pin, pawl
  const stretch = 46 * S.bucket - S.pin;
  const sprTop = 170 - 46 * S.bucket, pinTop = 214 - S.pin;
  g += `<line x1="890" y1="92" x2="890" y2="${f1(bTop - 18)}" stroke="#d9d4c4" stroke-width="1.6"/>
        <line x1="899" y1="83" x2="1022" y2="83" stroke="#d9d4c4" stroke-width="1.6"/>
        <line x1="1031" y1="92" x2="1031" y2="${f1(sprTop)}" stroke="#d9d4c4" stroke-width="1.6"/>
        <circle cx="899" cy="92" r="9" fill="#2a2f3a" stroke="#cfa64a" stroke-width="2.5"/><circle cx="899" cy="92" r="2" fill="#cfa64a"/>
        <circle cx="1022" cy="92" r="9" fill="#2a2f3a" stroke="#cfa64a" stroke-width="2.5"/><circle cx="1022" cy="92" r="2" fill="#cfa64a"/>
        <line x1="880" y1="62" x2="1040" y2="62" stroke="#6b4d34" stroke-width="6" stroke-linecap="round"/>
        <line x1="899" y1="62" x2="899" y2="92" stroke="#6b4d34" stroke-width="3"/><line x1="1022" y1="62" x2="1022" y2="92" stroke="#6b4d34" stroke-width="3"/>`;
  { // spring: 8 zigzags between sprTop and pinTop
    const n = 8, L = pinTop - sprTop; let d = `M1031 ${f1(sprTop)}`;
    for (let k = 0; k < n; k++) d += ` L${k % 2 ? 1024 : 1038} ${f1(sprTop + L * (k + .5) / n)}`;
    d += ` L1031 ${f1(pinTop)}`;
    g += `<path d="${d}" fill="none" stroke="#cfa64a" stroke-width="2.2" stroke-linejoin="round"/>`;
  }
  g += `<rect x="1027" y="${f1(pinTop)}" width="8" height="110" rx="2" fill="#cfd3da"/>`;
  for (let k = 0; k < 5; k++) g += `<path d="M1035 ${f1(pinTop + 84 + 4 * k)} l4 2 l-4 2z" fill="#cfd3da"/>`;
  g += `<g transform="rotate(${f1(-22 * S.click)} 1052 300)"><path d="M1052 296 L1039 300 L1052 304 Z" fill="#cfa64a"/><circle cx="1052" cy="300" r="3" fill="#8c6d28"/></g>`;
  g += `<path d="M864 ${f1(bTop)} Q890 ${f1(bTop - 36)} 916 ${f1(bTop)}" fill="none" stroke="#9aa3b2" stroke-width="2"/>`;
  g += `<g transform="rotate(${f1(-105 * S.tip)} 890 ${f1(bTop)})">
        <clipPath id="${id}bk"><polygon points="864,${f1(bTop)} 916,${f1(bTop)} 909,${f1(bTop + 56)} 871,${f1(bTop + 56)}"/></clipPath>
        <polygon points="864,${f1(bTop)} 916,${f1(bTop)} 909,${f1(bTop + 56)} 871,${f1(bTop + 56)}" fill="#252a34" stroke="#7f8ea3" stroke-width="2.5"/>
        ${S.bucket > .01 ? `<rect x="864" y="${f1(bTop + 56 - 50 * S.bucket)}" width="52" height="56" fill="#e3c27a" clip-path="url(#${id}bk)"/>` : ''}
        </g>`;

  // flap display
  g += `<rect x="952" y="310" width="160" height="160" rx="8" fill="#23262e" stroke="#3b404b" stroke-width="2"/>
        <circle cx="1031" cy="376" r="3" fill="#f0ece0"/><circle cx="1031" cy="404" r="3" fill="#f0ece0"/>`;
  const xs = [958, 993, 1038, 1073];
  for (let i = 0; i < 4; i++) {
    const u = c01((t - (3 - i) * TL.cascade) / TL.flip);
    g += flapCell(id + 'c' + i, xs[i], 338, 31, 104, prev[i], now[i], u * u);
  }

  // seesaw
  g += `<polygon points="745,508 736,520 754,520" fill="#8a6740"/>
        <line x1="${f1(sxl)}" y1="${f1(syl)}" x2="${f1(sxr)}" y2="${f1(syr)}" stroke="#c99a5e" stroke-width="6" stroke-linecap="round"/>`;

  // dominoes
  for (let i = 0; i < DN; i++) {
    const x = DX0 + DP * i, a = dominoAngle(i, t);
    g += `<rect x="${x}" y="${TABLE - DH}" width="${DW}" height="${DH}" rx="1.5" fill="hsl(${(i * 22 + 8) % 360} 62% 62%)"
          transform="rotate(${f1(a)} ${x + DW} ${TABLE})"/>`;
  }

  // table
  g += `<rect x="0" y="${TABLE}" width="1120" height="110" fill="url(#${id}wd)"/>
        <line x1="0" y1="${TABLE}" x2="1120" y2="${TABLE}" stroke="#a67c52" stroke-width="2.5"/>
        <ellipse cx="362" cy="${TABLE + 1}" rx="15" ry="3" fill="#0a0a0c"/>`;
  g += `</g></g>`;

  if (o.tags) {
    g += tag(210, 92, 1) + tag(540, 562, 2) + tag(745, 562, 3) + tag(820, 132, 4) + tag(1076, 200, 5)
       + tag(1032, 496, 6) + tag(60, 70, 7) + tag(668, 150, 8);
  }
  return g;
}
"""


def page(title: str, body: str, script: str = "") -> str:
    scene = SCENE_JS.replace("__TL__", json.dumps(TL))
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>{title}</title>"
            f"<meta name=\"viewport\" content=\"width=1440\"><style>{CSS}</style></head><body>{body}"
            f"<script>{scene}\n{script}</script></body></html>")


# ---------------------------------------------------------------------------
ACTS = [("rail", "1 Rail"), ("dominoes", "2 Dominoes"), ("seesaw", "3"), ("sand", "4 Sand and bucket"),
        ("hold", "Hold"), ("last", "5 Last five")]
REARMS = [("bucket_empty", "Bucket empties"), ("sand_lift", "Sand lift"), ("marble_lift", "7 Marble lift"),
          ("comb", "Comb stands the dominoes")]


def bar_svg() -> str:
    """The stage bar under the TV: acts above, re-arms below. x = 160 + t/60*1120."""
    def x(t): return 160 + t / 60 * 1120
    s = ""
    cols = ["#e0704f", "#e3a34f", "#c9c25a", "#6fb58a", "#5d6472", "#6d86c9"]
    for (k, label), c in zip(ACTS, cols):
        a, b = TL[k]
        s += (f'<rect x="{x(a):.1f}" y="6" width="{x(b) - x(a) - 2:.1f}" height="26" rx="4" fill="{c}" id="act-{k}" stroke="#fff" stroke-width="0"/>'
              f'<text x="{(x(a) + x(b)) / 2:.1f}" y="24" text-anchor="middle" font-size="13" font-weight="600" fill="#0b0c10">{label}</text>')
    for k, label in REARMS:
        a, b = TL[k]
        y = 62 if k == "comb" else 38
        s += (f'<rect x="{x(a):.1f}" y="{y}" width="{x(b) - x(a) - 2:.1f}" height="20" rx="4" fill="url(#hatch)" stroke="#59607080"/>'
              f'<text x="{(x(a) + x(b)) / 2:.1f}" y="{y + 14.5}" text-anchor="middle" font-size="12" fill="#e3e6ee">{label}</text>')
    for t in range(0, 61, 5):
        s += (f'<line x1="{x(t):.1f}" y1="86" x2="{x(t):.1f}" y2="92" stroke="#6b7280"/>'
              f'<text x="{x(t):.1f}" y="106" text-anchor="middle" font-size="12" fill="#8d94a3">:{t:02d}</text>')
    return ('<svg width="1440" height="112" style="position:absolute;left:0;top:674px">'
            '<defs><pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            '<rect width="7" height="7" fill="#1c1f27"/><line x1="0" y1="0" x2="0" y2="7" stroke="#59607a" stroke-width="2.5"/></pattern></defs>'
            f'{s}<line id="ph" x1="160" y1="0" x2="160" y2="88" stroke="#fff" stroke-width="2"/></svg>')


def machine() -> str:
    body = (
        '<div class="tv" style="left:150px;top:14px;width:1140px;height:650px"><svg id="scene" viewBox="0 0 1120 630"></svg></div>'
        '<div class="cap" style="left:1304px;top:20px;width:128px;font-size:12.5px;line-height:1.5">'
        '<b>1</b> Switchback rail<br><b>2</b> Dominoes<br><b>3</b> Seesaw<br><b>4</b> Hopper, bucket<br>'
        '<b>5</b> Spring, latch pin<br><b>6</b> Flap display<br><b>7</b> Marble lift<br><b>8</b> Hour bell</div>'
        '<div class="cap" style="left:14px;top:20px;width:128px;font-size:12.5px;line-height:1.5">Flat side view of a 3D scene. '
        'The camera drift is not shown; the push-in toward the latch is.</div>'
        + bar_svg() +
        '<div style="position:absolute;left:160px;top:796px;width:1120px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">'
        '<button id="b-now">Now</button><button id="b-ref">10:08:22</button><button id="b-last">Last five seconds</button>'
        '<button id="b-hour">Hour change</button><button id="b-x1">×1</button><button id="b-x4">×4</button>'
        '<label><input type="checkbox" id="c-tags" checked> numbers</label>'
        '<label><input type="checkbox" id="c-push" checked> push-in</label>'
        '<span id="clock" style="margin-left:auto;font:600 22px ui-monospace,Menlo,monospace;color:#eef0f4"></span></div>'
        '<div style="position:absolute;left:160px;top:848px;width:1120px;display:flex;gap:12px;align-items:center">'
        '<span style="color:#8d94a3;font-size:13px">second</span>'
        '<input type="range" id="scrub" min="0" max="59.9" step="0.1" style="flex:1">'
        '<span id="what" style="color:#aeb4c0;font-size:13px;width:430px;text-align:right"></span></div>'
    )
    script = r"""
const $ = id => document.getElementById(id);
const sod = d => d.getHours() * 3600 + d.getMinutes() * 60 + d.getSeconds() + d.getMilliseconds() / 1000;
let st = { base: sod(new Date()), ref: performance.now(), rate: 1, paused: false, follow: true };
const cur = () => st.follow ? sod(new Date()) : st.paused ? st.base : st.base + (performance.now() - st.ref) / 1000 * st.rate;
function set(base, paused, rate) { st = { base, ref: performance.now(), rate: rate || st.rate, paused, follow: false }; }
const hms = (h, m, s) => h * 3600 + m * 60 + s;
const WHAT = [[0, 'the marble runs the rail; the bucket empties'], [12, 'the dominoes fall; the sand lift refills the hopper'],
  [20, 'the last domino tips the seesaw, which opens the hopper'], [22, 'sand fills the bucket; it sinks and stretches the spring'],
  [52, 'the hopper is empty; everything holds still'], [55, 'the latch pin escapes one tooth a second']];
function draw() {
  const s = cur(), t = ((s % 60) + 60) % 60;
  $('scene').innerHTML = renderScene(s, { tags: $('c-tags').checked, push: $('c-push').checked });
  $('ph').setAttribute('x1', 160 + t / 60 * 1120); $('ph').setAttribute('x2', 160 + t / 60 * 1120);
  const d = ((Math.floor(s) % 86400) + 86400) % 86400;
  $('clock').textContent = [Math.floor(d / 3600), Math.floor(d / 60) % 60, d % 60].map(v => String(v).padStart(2, '0')).join(':');
  if (document.activeElement !== $('scrub')) $('scrub').value = t;
  let w = ''; for (const [a, txt] of WHAT) if (t >= a) w = txt; $('what').textContent = w;
  for (const k of ['rail', 'dominoes', 'seesaw', 'sand', 'hold', 'last'])
    $('act-' + k).setAttribute('stroke-width', t >= TL[k][0] && t < TL[k][1] ? 3 : 0);
  $('b-now').className = st.follow ? 'on' : '';
  $('b-x1').className = !st.follow && st.rate === 1 && !st.paused ? 'on' : '';
  $('b-x4').className = !st.follow && st.rate === 4 && !st.paused ? 'on' : '';
}
$('b-now').onclick = () => { st.follow = true; st.rate = 1; };
$('b-ref').onclick = () => set(hms(10, 8, 22), true, 1);
$('b-last').onclick = () => set(hms(10, 8, 52), false, 1);
$('b-hour').onclick = () => set(hms(12, 59, 52), false, 1);
$('b-x1').onclick = () => set(cur(), false, 1);
$('b-x4').onclick = () => set(cur(), false, 4);
$('scrub').oninput = e => set(Math.floor(cur() / 60) * 60 + parseFloat(e.target.value), true);
const m = /t=(\d+):(\d+):(\d+(?:\.\d+)?)/.exec(location.hash);
if (m) set(hms(+m[1], +m[2], parseFloat(m[3])), true, 1);
draw();
(function loop() { draw(); requestAnimationFrame(loop); })();
"""
    return page("Minute Machine: the machine", body, script)


MOMENTS = [
    ("10:08:03.0", "<b>10:08:03</b> The flap has just dropped. The marble is on the first rail and the bucket is pouring its sand back."),
    ("10:08:15.2", "<b>10:08:15</b> The dominoes are falling, three a second. The sand lift refills the hopper."),
    ("10:08:38.0", "<b>10:08:38</b> The slow act. Sand fills the bucket, which sinks and stretches the spring; the marble rides the lift."),
    ("10:08:57.6", "<b>10:08:57</b> The last five seconds. Three teeth out, two to go; the camera has pushed in."),
    ("10:09:00.3", "<b>10:09:00.3</b> The minute flap is falling. Its fall has lifted the gate, and the next run has begun."),
    ("13:00:00.38", "<b>13:00:00.4</b> The hour. Three drums flip in a cascade, right to left, and the hammer strikes the bell."),
]


def moments() -> str:
    body = '<h1 style="left:40px;top:18px">Six moments. A Dream that starts at any of them looks exactly like this.</h1>'
    for i, (_, cap) in enumerate(MOMENTS):
        col, row = i % 3, i // 3
        x, y = 40 + col * 460, 84 + row * 392
        body += (f'<div class="tv" style="left:{x}px;top:{y}px;width:440px;height:258px;border-width:6px;border-radius:9px">'
                 f'<svg id="m{i}" viewBox="0 0 1120 630"></svg></div>'
                 f'<div class="cap" style="left:{x + 4}px;top:{y + 268}px;width:432px">{cap}</div>')
    times = json.dumps([m[0] for m in MOMENTS])
    script = (f"const TIMES={times};"
              "TIMES.forEach((s,i)=>{const p=s.split(':');"
              "document.getElementById('m'+i).innerHTML=renderScene(p[0]*3600+p[1]*60+parseFloat(p[2]),{id:'m'+i+'_'});});")
    return page("Minute Machine: six moments", body, script)


# Piece-by-piece states over one minute, for timeline.html. (state, from, to, label)
ROWS = [
    ("Marble", [("act", 0, 13.2, "runs the rail, strikes domino 1, drops through the table"),
                ("rearm", 13.2, 30, "returns under the table"), ("rearm", 30, 58, "rides the lift"), ("armed", 58, 60, "")]),
    ("Dominoes", [("armed", 0, 12, ""), ("act", 12, 21, "fall, three a second"), ("spent", 21, 41, ""),
                  ("rearm", 41, 52.1, "the comb stands them up"), ("armed", 52.1, 60, "")]),
    ("Seesaw and hopper gate", [("armed", 0, 20.3, ""), ("act", 20.3, 21.5, ""), ("spent", 21.5, 52.1, "holds the gate open"),
                                ("rearm", 52.1, 52.6, ""), ("armed", 52.6, 60, "")]),
    ("Hopper sand", [("spent", 0, 7, ""), ("rearm", 7, 20, "sand lift refills"), ("armed", 20, 22, ""),
                     ("act", 22, 52, "drains into the bucket"), ("spent", 52, 60, "")]),
    ("Bucket", [("spent", 0, 1, ""), ("rearm", 1, 7, "tips, empties"), ("armed", 7, 22, ""),
                ("act", 22, 52, "fills and sinks"), ("spent", 52, 60, "full")]),
    ("Spring and latch pin", [("spent", 0, 2, ""), ("rearm", 2, 5.5, "re-seats"), ("armed", 5.5, 22, ""),
                              ("act", 22, 52, "spring stretches"), ("spent", 52, 55, "hold"), ("act", 55, 60, "five teeth")]),
    ("Flap display", [("act", 0, 0.8, ""), ("armed", 0.8, 60, "shows the minute")]),
    ("Hour bell (on the hour)", [("act", 0.3, 7.5, "strike, then swing and settle"), ("armed", 7.5, 60, "")]),
    ("Camera", [("rearm", 1, 5, "pulls back"), ("armed", 5, 50, "wide, drifting"), ("act", 50, 58, "pushes in"), ("spent", 58, 60, ""),
                ("spent", 0, 1, "")]),
]


def timeline() -> str:
    X0, X1, Y0, RH = 250, 1400, 120, 70
    def x(t): return X0 + t / 60 * (X1 - X0)
    col = {"act": "#e0704f", "rearm": "url(#hatch)", "armed": "#3f6b55", "spent": "#343946"}
    s = ('<defs><pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
         '<rect width="8" height="8" fill="#2a3350"/><line x1="0" y1="0" x2="0" y2="8" stroke="#6d86c9" stroke-width="3"/></pattern></defs>')
    for t in range(0, 61, 5):
        s += (f'<line x1="{x(t):.1f}" y1="{Y0 - 14}" x2="{x(t):.1f}" y2="{Y0 + RH * len(ROWS)}" stroke="#262a33"/>'
              f'<text x="{x(t):.1f}" y="{Y0 - 22}" text-anchor="middle" font-size="13" fill="#8d94a3">:{t:02d}</text>')
    for i, (name, spans) in enumerate(ROWS):
        y = Y0 + i * RH
        s += f'<text x="{X0 - 16}" y="{y + 31}" text-anchor="end" font-size="15" fill="#e3e6ec">{name}</text>'
        for kind, a, b, label in spans:
            thin = kind in ("armed", "spent")
            h, yy = (10, y + 21) if thin else (34, y + 9)
            w = max(x(b) - x(a) - 1.5, 2)
            s += f'<rect x="{x(a):.1f}" y="{yy}" width="{w:.1f}" height="{h}" rx="4" fill="{col[kind]}"/>'
            if label:
                fits = w > len(label) * 6.6
                if thin:
                    s += f'<text x="{x(a) + 6:.1f}" y="{y + 50}" font-size="12" fill="#8d94a3">{label}</text>'
                elif fits:
                    s += (f'<text x="{(x(a) + x(b)) / 2:.1f}" y="{y + 31}" text-anchor="middle" font-size="12.5" font-weight="600" '
                          f'fill="{"#0b0c10" if kind == "act" else "#e8ecf6"}">{label}</text>')
                else:
                    s += f'<text x="{x(a):.1f}" y="{y + 58}" font-size="12" fill="#aeb4c0">{label}</text>'
    for t in (12, 20.3, 22, 52, 55):
        s += f'<line x1="{x(t):.1f}" y1="{Y0 - 8}" x2="{x(t):.1f}" y2="{Y0 + RH * len(ROWS)}" stroke="#f3d27a" stroke-dasharray="3 5" opacity=".55"/>'
    ly = Y0 + RH * len(ROWS) + 34
    legend = [("act", "acting"), ("rearm", "re-arming"), ("armed", "armed, waiting"), ("spent", "spent, waiting to re-arm")]
    lx = X0
    for kind, label in legend:
        thin = kind in ("armed", "spent")
        s += (f'<rect x="{lx}" y="{ly + (7 if thin else 0)}" width="34" height="{8 if thin else 22}" rx="4" fill="{col[kind]}"/>'
              f'<text x="{lx + 44}" y="{ly + 16}" font-size="14" fill="#c3c8d3">{label}</text>')
        lx += 70 + len(label) * 9
    s += (f'<text x="{lx + 20}" y="{ly + 16}" font-size="14" fill="#f3d27a">┆ a contact that starts the next act</text>')
    body = ('<h1 style="left:40px;top:22px">One minute, piece by piece. The right edge joins the left: every row ends in the state it starts in.</h1>'
            f'<svg width="1440" height="900" style="position:absolute;left:0;top:0">{s}</svg>')
    return page("Minute Machine: one minute", body)


def picker() -> str:
    rows = ["Ambient mode", "Aquarium", "Seahorse Grid", "Planted Tank", "Minute Machine"]
    lst = ""
    for i, r in enumerate(rows):
        sel = i == 4
        lst += (f'<div style="display:flex;align-items:center;gap:14px;padding:13px 18px;border-radius:10px;margin:4px 10px;'
                f'background:{"#e8eaf0" if sel else "transparent"};color:{"#111318" if sel else "#d5d9e2"};font-size:17px">'
                f'<span style="width:16px;height:16px;border-radius:50%;border:2px solid {"#111318" if sel else "#8d94a3"};'
                f'display:inline-block;box-shadow:{"inset 0 0 0 3px #e8eaf0, inset 0 0 0 9px #111318" if sel else "none"}"></span>{r}</div>')
    banner = ('<svg viewBox="0 0 320 180" width="320" height="180" style="border-radius:10px;display:block">'
              '<rect width="320" height="180" fill="#14161c"/><rect y="132" width="320" height="48" fill="#3b2a1e"/>'
              '<line x1="0" y1="132" x2="320" y2="132" stroke="#a67c52" stroke-width="2"/>'
              + "".join(f'<rect x="{40 + i * 24}" y="78" width="9" height="54" rx="2" fill="hsl({i * 40 + 8} 62% 62%)" '
                        f'transform="rotate({a} {49 + i * 24} 132)"/>' for i, a in enumerate([68, 68, 52, 24, 0, 0])) +
              '<circle cx="26" cy="120" r="12" fill="#d8452f"/>'
              '<text x="196" y="64" font-size="25" font-weight="700" fill="#f0ece0" font-family="system-ui,sans-serif">Minute</text>'
              '<text x="196" y="94" font-size="25" font-weight="700" fill="#f0ece0" font-family="system-ui,sans-serif">Machine</text>'
              '<circle cx="296" cy="156" r="14" fill="#f0ece0"/><text x="296" y="161" text-anchor="middle" font-size="11" font-weight="700" fill="#14161c">WF</text></svg>')
    body = (
        '<div class="tv" style="left:30px;top:30px;width:900px;height:516px"><div style="position:relative;width:100%;height:100%">'
        '<svg id="pv" viewBox="0 0 1120 630" style="position:absolute;inset:0;opacity:.55"></svg>'
        '<div style="position:absolute;right:0;top:0;bottom:0;width:340px;background:#1d2027f2;padding-top:26px">'
        '<div style="padding:0 28px 14px;font-size:22px;font-weight:600;color:#eef0f4">Screen saver</div>' + lst +
        '</div></div></div>'
        '<div class="cap" style="left:34px;top:560px;width:890px"><b>The TV\'s screensaver list.</b> Minute Machine is a fourth World Foundry entry, '
        'beside Aquarium, Seahorse Grid and Planted Tank. The list is Android\'s own; only the name and the preview behind it are ours.</div>'
        f'<div style="position:absolute;left:980px;top:30px">{banner}</div>'
        '<div class="cap" style="left:980px;top:220px;width:420px"><b>TV banner, 320 × 180.</b> Three dominoes down, one going, two to go, '
        'with the World Foundry badge lower right as on the other three apps.</div>'
        '<div style="position:absolute;left:980px;top:300px;width:230px;height:470px;border:8px solid #23252b;border-radius:26px;background:#000;overflow:hidden">'
        '<svg id="ph" viewBox="0 0 1120 630" style="position:absolute;left:0;top:176px;width:214px;height:120px"></svg></div>'
        '<div class="cap" style="left:1228px;top:300px;width:190px"><b>Portrait phone, "follow device".</b> The scene keeps 16:9 and shows as a strip, '
        'as the other Dreams do. The default stays landscape.</div>'
        '<div class="tv" style="left:30px;top:640px;width:400px;height:236px;border-width:6px;border-radius:9px"><svg id="bad" viewBox="0 0 1120 630"></svg></div>'
        '<div class="cap" style="left:446px;top:646px;width:480px"><b>A TV whose clock is wrong.</b> A device that has never set its clock shows what '
        'the device believes, here 00:00 on its first boot. The machine still runs and still drops a flap each minute; it never shows a blank or an error. '
        'When the clock is corrected, the next frame shows the right time.</div>'
    )
    script = ("document.getElementById('pv').innerHTML=renderScene(10*3600+8*60+22,{id:'pv_'});"
              "document.getElementById('ph').innerHTML=renderScene(10*3600+8*60+38,{id:'ph_'});"
              "document.getElementById('bad').innerHTML=renderScene(31.5,{id:'bad_'});")
    return page("Minute Machine: Android surfaces", body, script)


PAGES = {"machine": (machine, "#t=10:08:22"), "moments": (moments, ""), "timeline": (timeline, ""), "picker": (picker, "")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--png", action="store_true", help="also render each mockup to a 1440x900 PNG with google-chrome")
    args = ap.parse_args()
    for name, (fn, frag) in PAGES.items():
        out = HERE / f"{name}.html"
        out.write_text(fn(), encoding="utf-8")
        print(f"{out.name}: {out.stat().st_size / 1024:.0f} KB")
        if args.png:
            png = HERE / f"{name}.png"
            subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--window-size=1440,900", "--virtual-time-budget=1500",
                            f"--screenshot={png}", out.as_uri() + frag],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if png.stat().st_size > 512 * 1024:
                from PIL import Image
                im = Image.open(png).convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT)
                im.save(png, optimize=True)
            print(f"  {png.name}: {png.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
