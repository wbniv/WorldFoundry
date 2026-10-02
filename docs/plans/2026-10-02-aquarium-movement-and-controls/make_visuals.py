"""Original movement/control concepts. These are not engine captures."""
from pathlib import Path
from html import escape
import json
import math

OUT = Path(__file__).resolve().parent
STYLE = '''<style>text{font-family:DejaVu Sans,sans-serif;fill:#203b46}.title{font-size:32px;font-weight:700}.head{font-size:23px;font-weight:700}.body{font-size:18px}.small{font-size:15px}.tag{font-size:13px;font-weight:700;letter-spacing:1px}</style>'''
DEFS = '''<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#247d85"/></marker></defs>'''


def text(x, y, words, cls='body'):
    return f'<text x="{x}" y="{y}" class="{cls}">{escape(words)}</text>'


def svg(name, body, height):
    (OUT / f'{name}.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">{STYLE}{DEFS}<rect width="1200" height="{height}" fill="#f5f1e8"/>{body}</svg>')


def fish(kind='clownfish'):
    if kind == 'arowana':
        return '<path d="M-88 0L-126-22L-139 0L-126 22Z" fill="#a4b17a"/><path d="M-95-12L-68-35L-15-30L-10-15M-95 12L-65 36L-12 30L-8 15" fill="#c4ca98"/><ellipse rx="106" ry="23" fill="#a4b17a" stroke="#45614d" stroke-width="2"/><path d="M84-8L122-14M84-2L124-4" stroke="#697c50" stroke-width="2"/><circle cx="85" cy="-9" r="4" fill="#253a2d"/><path d="M55 8L25 39L67 18" fill="#c4ca98"/>'
    color = {'clownfish': '#e58c32', 'betta': '#27768b', 'lionfish': '#b99a79'}[kind]
    tail = '#b3477b' if kind == 'betta' else color
    out = f'<path d="M-55 0L-98 -38Q-120 0-98 38Z" fill="{tail}" stroke="#284852" stroke-width="2"/>'
    if kind == 'betta':
        out += '<path d="M-25-16Q-55-75 0-66L30-20Z" fill="#8d4e95"/><path d="M-25 16Q0 80 47 32L50 12Z" fill="#b3477b"/><path d="M20 20Q15 48-10 65" fill="none" stroke="#b3477b" stroke-width="6"/>'
    if kind == 'lionfish':
        for i in range(6):
            x = -40 + i * 15
            out += f'<path d="M{x}-15L{x-18}-{45+i%3*9}" stroke="#935b4c" stroke-width="4"/>'
        out += '<path d="M-5 6L-42 63L33 49L40 10Z" fill="#b7937b" stroke="#744a43" stroke-width="2"/>'
    out += f'<ellipse cx="0" cy="0" rx="62" ry="25" fill="{color}" stroke="#284852" stroke-width="2"/>'
    if kind == 'clownfish':
        out += '<path d="M-24-23V23M18-24V24" stroke="#faf6dd" stroke-width="13"/>'
    elif kind == 'lionfish':
        out += '<path d="M-25-23V23M8-24V24M37-18V18" stroke="#894c43" stroke-width="12"/>'
    out += '<path d="M15 0Q-9 8 5 26" stroke="#385362" stroke-width="7" fill="none"/><circle cx="45" cy="-7" r="5" fill="#102e3b"/>'
    return out


def jelly(contraction=0):
    w, h = 58*(1-.18*contraction), 76*(1+.28*contraction)
    rim = 17-12*contraction
    return f'<path d="M{-w} 0Q-44 {-h} 0 {-h}Q44 {-h} {w} 0Q0 {rim} {-w} 0" fill="#9ddad9" stroke="#397e8b" stroke-width="3"/><path d="M-24 6Q-45 44-17 69Q10 92-18 121M0 7Q-18 44 9 75Q29 98 3 132M25 4Q4 41 32 70Q51 98 27 123" fill="none" stroke="#75b9c9" stroke-width="6"/>'


def shrimp():
    out = '<path d="M-58 3Q-45-24 10-18Q41-16 54 1L22 15L-48 18Z" fill="#2b93d8" stroke="#225b79" stroke-width="2"/><path d="M-48 9L-70 31L-83 24L-62 2" fill="#3ca6dc"/><path d="M48-4Q84-34 119-29M48 0Q87-16 127 0" stroke="#69a5b9" fill="none" stroke-width="2"/>'
    for i in range(5):
        x = -35 + 15 * i
        out += f'<path d="M{x} 12l-8 18 11 7" stroke="#318bbc" stroke-width="3" fill="none"/>'
    return out + '<circle cx="39" cy="-9" r="5" fill="#163341"/>'


def urchin():
    out = '<ellipse rx="38" ry="25" fill="#52336f"/>'
    for i in range(23):
        a = math.tau * i / 23
        out += f'<path d="M{32*math.cos(a):.1f} {21*math.sin(a):.1f}L{(53+i%4*2)*math.cos(a):.1f} {(33+i%3*4)*math.sin(a):.1f}" stroke="#583774" stroke-width="2"/>'
    return out


TANKS = [
    dict(name='Clownfish & Tiger Barbs', kind='clownfish', state='Steer → stroke → coast → hover', rules='Turn and pitch before following the new direction. Keep the current clownfish as the quality baseline; preserve barb motion and startle.', direction='D-pad: steer, climb/dive', action='OK: dart', mode='Up → OK: Side / Depth', note='An arc follows the current facing.'),
    dict(name='Blue Shrimp', kind='shrimp', state='Graze → walk → swim → settle', rules='Feet contact sand or an authored support. Swimming and backward escape use separate gaits. Stride follows distance traveled.', direction='D-pad: walk, excursion / settle', action='OK: backward tail flip', mode='Up → OK: Side / Depth', note='Contact walking; a separate backward escape.'),
    dict(name='Calm Betta', kind='betta', state='Hover → orient → swim → brake', rules='Slow into turns, then swim forward. Independent pectoral hover, curved fan membranes and delayed pelvic ribbons. Fully opaque fins.', direction='D-pad: steer, pitched climb/dive', action='OK: small swim burst', mode='Up → OK: Side / Depth', note='Fin roots turn first; flexible tips trail.'),
    dict(name='Jellyfish', kind='jellyfish', state='Contract → recover → open coast', rules='Steer bell tilt and pulse cadence. Momentum/current continue after input release. Thrust and bell deformation share one stroke phase.', direction='D-pad: tilt; Up active / Down rest', action='OK: pulse; hold to repeat gently', mode='Up → OK: Side / Depth', note='Pulse along the bell axis; retain drift.'),
    dict(name='Lionfish', kind='lionfish', state='Hover → stalk → strike → recover', rules='Deliberate forward motion and pectoral hover, with a separate brief feeding strike. Player and resident use the same locomotion rules.', direction='D-pad: steer, pitched climb/dive', action='OK: feed request', mode='Up → OK: mode · Down → OK: prey', note='Slow approach; a distinct quick strike.'),
    dict(name='Planted Tank', kind='urchin', state='Rest → tiny contact crawl → rest', rules='Sea urchin stays on the substrate. Maximum 0.0125 world units/s including diagonals. View changes never accelerate it; plants remain static.', direction='D-pad: both substrate axes', action='OK: wide / close view', mode='One crawl plane; no mode chord', note='Barely perceptible travel; inspect a long trace.'),
    dict(name='Asian Arowana', kind='arowana', state='Scull → cruise → brake/turn → recover', rules='Long 65 cm fish in a 4 × 3 × 1.2 m tank. Turn radius scales with length and speed. Brake into broad inward U-turns; check the entire nose/tail/fin/barbel sweep. Head leads, posterior wave grows toward the tail.', direction='D-pad: heading, gentle pitched swim', action='OK: brief forward burst + recovery', mode='Up → OK: Side / Depth; neutral to rearm', note='Length governs the arc; tail sweep needs room.'),
]

body = text(40, 55, 'Seven players, seven movement contracts', 'title') + text(40, 85, 'DESIGN CONCEPTS · schematic paths and animal silhouettes; not engine captures', 'small')
for i, row in enumerate(TANKS):
    x, y = 30 + i % 2 * 585, 110 + i // 2 * 285
    body += f'<rect x="{x}" y="{y}" width="555" height="260" rx="12" fill="#e5e9df"/>'
    body += text(x+20, y+34, f'{i}. {row["name"]}', 'head') + text(x+20, y+64, row['state'], 'small')
    kind = row['kind']
    icon = jelly() if kind == 'jellyfish' else shrimp() if kind == 'shrimp' else urchin() if kind == 'urchin' else fish(kind)
    icon_y, icon_scale = (145, .63) if kind == 'jellyfish' else (155, .75)
    body += f'<g transform="translate({x+160} {y+icon_y}) scale({icon_scale})">{icon}</g>'
    if kind in ('clownfish', 'betta', 'lionfish', 'arowana'):
        body += f'<path d="M{x+255} {y+145}C{x+460} {y+145} {x+460} {y+209} {x+275} {y+209}" stroke="#247d85" stroke-width="3" fill="none" marker-end="url(#arrow)"/>'
        body += text(x+287, y+111, 'Orient → forward arc', 'small')
    elif kind == 'jellyfish':
        body += f'<path d="M{x+290} {y+206}Q{x+346} {y+163} {x+363} {y+93}" stroke="#247d85" stroke-width="3" fill="none" marker-end="url(#arrow)"/>'
        body += text(x+375, y+148, 'tilt + pulse', 'small') + text(x+375, y+178, 'then drift', 'small')
    elif kind == 'shrimp':
        body += f'<path d="M{x+65} {y+188}H{x+500}" stroke="#8c947f" stroke-width="3"/><path d="M{x+324} {y+151}H{x+470}" stroke="#247d85" stroke-width="3" marker-end="url(#arrow)"/><path d="M{x+324} {y+170}H{x+275}" stroke="#247d85" stroke-width="3" marker-end="url(#arrow)"/>'
        body += text(x+345, y+134, 'walk / swim', 'small')
    else:
        body += f'<path d="M{x+65} {y+187}H{x+500}" stroke="#8c947f" stroke-width="3"/><path d="M{x+306} {y+151}H{x+330}" stroke="#247d85" stroke-width="3" marker-end="url(#arrow)"/>'
        body += text(x+354, y+148, '0.0125 max', 'small') + text(x+354, y+178, 'world units/s', 'small')
    body += text(x+20, y+241, row['note'], 'small')
svg('six-players', body, 1275)

body = text(40, 55, 'Direction is intent; locomotion makes the path', 'title') + text(40, 87, 'DESIGN SCHEMATIC · proposed behavior, not measured physics', 'small')
body += '<rect x="30" y="118" width="1140" height="247" rx="12" fill="#e5e9df"/>'
body += text(55, 157, 'Fish: turn, drive, coast and brake', 'head')
for i, (title, a, b) in enumerate([('1 · Input', 'Desired direction', 'No direct axis velocity'), ('2 · Body', 'Yaw + pitch + small bank', 'Full attached-fin transform'), ('3 · Drive', 'Speed × current facing', 'Species hover / coast'), ('4 · Pose', 'Tail, fins and mouth', 'Respond to actual motion')]):
    x = 55 + i*280
    body += text(x, 208, title, 'head') + text(x, 246, a) + text(x, 276, b, 'small')
    if i < 3:
        body += f'<path d="M{x+233} 216h27" stroke="#247d85" stroke-width="3" marker-end="url(#arrow)"/>'
body += text(55, 338, 'Clownfish is the reference. Other fish use species tuning; Arowana turns scale with length.', 'body')
body += '<rect x="30" y="390" width="1140" height="370" rx="12" fill="#e5e9df"/>'
body += text(55, 431, 'Jellyfish: tilt + timed thrust + retained drift', 'head')
for i, (title, label, fill) in enumerate([('Contract', 'Bell-axis thrust', '#7ebdb6'), ('Recover', 'Refill; motion continues', '#acd3c7'), ('Open / coast', 'Current + momentum', '#d1dccb')]):
    x = 85 + 355*i
    body += f'<g transform="translate({x+110} 578) scale(.6)">{jelly((.9,.35,0)[i])}</g>'
    body += text(x, 474, title, 'head') + text(x, 681, label)
    body += f'<rect x="{x}" y="701" width="310" height="12" fill="{fill}"/>'
body += text(55, 742, 'Direction and travel can differ during a turn. No fish tail gait; no instant stop on release.', 'small')
body += text(40, 805, 'Substrate animals use another model: supported gait/contact, free-swim transitions for shrimp, tiny urchin crawl.', 'small')
svg('movement-models', body, 840)

body = text(40, 55, 'One action button: OK + directional chords', 'title') + text(40, 87, 'PROPOSED CONTROLS · direction first, then a new OK press; test on the physical remote', 'small')
for i, row in enumerate(TANKS):
    x, y = 30 + i % 2 * 585, 115 + i // 2 * 220
    body += f'<rect x="{x}" y="{y}" width="555" height="198" rx="12" fill="#e5e9df"/>'
    body += text(x+20, y+32, row['name'], 'head')
    for j, field in enumerate(('direction', 'action', 'mode')):
        body += text(x+20, y+75+j*36, row[field], 'body' if field != 'mode' else 'small')
body += text(40, 1025, 'Phone: A = OK/Action; B = optional Mode shortcut. Chromecast needs no B or C.', 'body')
body += text(40, 1059, 'Chord is latched through chord release; consumes the direction; never also darts, feeds or pulses.', 'small')
body += text(40, 1089, 'If the remote cannot report chords: neutral double-tap OK → Controls panel, with no accidental action.', 'small')
svg('controls', body, 1130)

template = '''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aquarium movement and controls — seven players</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#102632;color:#e9f1ed;font:17px/1.55 system-ui}main{max-width:1160px;margin:auto;padding:30px}h1{font-size:34px;line-height:1.2}h2{margin-top:40px}p{max-width:1000px;color:#c4d5d7}a{color:#8fddda}.badge{font-size:13px;letter-spacing:1px;color:#f2cf87}nav,.tabs{display:flex;gap:10px;flex-wrap:wrap}button{font:inherit;color:#e9f1ed;background:#24424e;border:1px solid #67838a;border-radius:7px;padding:9px 13px;cursor:pointer}button[aria-pressed=true]{background:#2d756f;border-color:#9ad9c5}button:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid #f2cf87;outline-offset:4px}.panel{padding:20px;background:#1b3540;border-radius:12px;margin:20px 0}#rules{min-height:85px}#bindings{color:#f2cf87}img{display:block;width:100%;height:auto;background:#f5f1e8;border-radius:10px;margin:20px 0}label{display:block}input{width:min(90%,540px);margin:12px}#pulse{width:100%;height:auto;background:#f5f1e8;border-radius:8px;color:#203b46}.row{display:flex;gap:15px;align-items:center;flex-wrap:wrap}footer{margin:40px 0;color:#b5cace}
</style><main>
<div class="badge">PLAN VISUALS · ORIGINAL SCHEMATICS · GAME PROPOSALS</div>
<h1>Movement and controls for all seven players</h1>
<p>Fish turn before following a new direction. Jellyfish pulse, recover and drift. Shrimp switch between supported and swimming gaits; the sea urchin barely crawls. These concepts are not a running engine or a newly implemented fish mesh.</p>
<nav><a href="#players">Each player</a><a href="#pulse-section">Jelly pulse</a><a href="#diagrams">Motion diagrams</a><a href="#controls">One-button controls</a><a href="../2026-10-02-aquarium-movement-and-controls.md">Full plan + sources</a></nav>
<h2 id="players">Player / tank selector</h2><div class="tabs" id="tabs" role="group" aria-label="Player concepts"></div>
<section class="panel" aria-live="polite"><h3 id="name"></h3><div id="state"></div><p id="rules"></p><div id="bindings"></div></section>
<h2 id="pulse-section">Jellyfish: examine one proposed stroke</h2>
<p>The slider shows the draft 20% contraction, 30% recovery and 50% open interval. These are game choices, not fitted animal data. A thrust arrow is distinct from retained travel; this picture does not calculate fluid forces.</p>
<div class="panel"><div class="row"><button id="play" aria-pressed="false">Play cycle</button><strong id="phase-text"></strong></div>
<label for="phase">Stroke phase <input id="phase" type="range" min="0" max="1000" value="0"><output id="phase-value"></output></label>
<svg id="pulse" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 390" role="img" aria-label="Illustrative jelly bell, flexible margin, trailing arms and separate thrust/travel arrows">
<defs><marker id="tip" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#277c85"/></marker></defs>
<g id="animal"><path id="bell" fill="#a7d8d4" stroke="#367784" stroke-width="3"/><path id="margin" fill="none" stroke="#47808a" stroke-width="5"/><g id="arms" fill="none" stroke="#6da7b7" stroke-width="6"></g></g>
<path id="thrust" d="M475 145L475 65" stroke="#277c85" stroke-width="7" marker-end="url(#tip)"/>
<text x="505" y="90" fill="#203b46" font-family="sans-serif" font-size="20">Active thrust</text>
<path d="M690 255Q750 218 775 165" stroke="#277c85" stroke-width="4" fill="none" marker-end="url(#tip)"/>
<text x="670" y="294" fill="#203b46" font-family="sans-serif" font-size="19">Travel persists</text>
<text x="660" y="324" fill="#203b46" font-family="sans-serif" font-size="16">Momentum + gentle current</text>
<text x="45" y="360" fill="#203b46" font-family="sans-serif" font-size="16">Schematic deformation and arrows · the engine will integrate velocity separately</text>
</svg></div>
<h2 id="diagrams">Motion contracts and pipelines</h2><img src="six-players.svg" alt="Seven schematic animal silhouettes and distinct movement paths"><img src="movement-models.svg" alt="Fish intent-to-facing-to-drive pipeline compared with jelly contraction, recovery and drift">
<h2 id="controls">D-pad + one OK button</h2><p>Up held before OK changes Side/Depth mode. In Lionfish, Down held before OK releases prey. OK alone performs the current animal's action. The urchin uses one floor plane and OK changes view. Phone B is an optional shortcut.</p><img src="controls.svg" alt="One-button control bindings for seven players and optional phone shortcut">
<footer>Implementation and real-device checks are pending. <a href="../2026-10-02-aquarium-movement-and-controls.md">Read the plan</a> · <a href="../2026-10-02-betta-poster-and-flowing-fins/index.html">Betta poster + mesh concepts</a></footer>
</main><script>
const tanks=__TANKS__;
const buttons=[];
tanks.forEach((tank,i)=>{const button=document.createElement('button');button.textContent=tank.name;button.setAttribute('aria-pressed','false');button.onclick=()=>select(i);buttons.push(button);document.getElementById('tabs').append(button)});
function select(i){buttons.forEach((b,j)=>b.setAttribute('aria-pressed',String(i===j)));const t=tanks[i];document.getElementById('name').textContent=t.name;document.getElementById('state').textContent=t.state;document.getElementById('rules').textContent=t.rules;document.getElementById('bindings').textContent=[t.direction,t.action,t.mode].join(' · ')}select(0);
const range=document.getElementById('phase'),play=document.getElementById('play');let playing=false,last=0,phase=0;
const smooth=u=>u*u*(3-2*u);
function render(){const p=phase;let c=0,label='Open / coast';if(p<.2){c=smooth(p/.2);label='Contract — bell-axis thrust'}else if(p<.5){c=1-smooth((p-.2)/.3);label='Recover — refill, motion continues'}const w=120*(1-.18*c),h=95*(1+.28*c),cy=160,root=330;
document.getElementById('bell').setAttribute('d',`M${root-w} ${cy} Q${root-w*.9} ${cy-h} ${root} ${cy-h} Q${root+w*.9} ${cy-h} ${root+w} ${cy} Q${root} ${cy+18-12*c} ${root-w} ${cy}Z`);
document.getElementById('margin').setAttribute('d',`M${root-w} ${cy} Q${root-w*.6} ${cy+20-18*c} ${root} ${cy+10} Q${root+w*.6} ${cy+20-18*c} ${root+w} ${cy}`);
let arms='';for(let i=0;i<4;i++){const x=root-55+i*36,lag=Math.sin(2*Math.PI*p-i*.6)*12;arms+=`<path d="M${x} 171 Q${x-16+lag} 214 ${x+10+lag} 248 Q${x+29+lag} 286 ${x+lag*.5} ${305+i%2*20}"/>`}document.getElementById('arms').innerHTML=arms;
document.getElementById('thrust').setAttribute('opacity',p<.2?'1':'.12');document.getElementById('phase-text').textContent=label;document.getElementById('phase-value').textContent=Math.round(p*100)+'%';range.value=Math.round(p*1000)}
range.oninput=()=>{playing=false;play.textContent='Play cycle';play.setAttribute('aria-pressed','false');phase=Number(range.value)/1000;render()};
play.onclick=()=>{playing=!playing;play.textContent=playing?'Pause cycle':'Play cycle';play.setAttribute('aria-pressed',String(playing));last=performance.now()};
function tick(now){if(playing){phase=(phase+Math.min((now-last)/1000,.1)/4)%1;render()}last=now;requestAnimationFrame(tick)}render();requestAnimationFrame(tick);
</script></html>'''
(OUT / 'index.html').write_text(template.replace('__TANKS__', json.dumps(TANKS, ensure_ascii=False)))
