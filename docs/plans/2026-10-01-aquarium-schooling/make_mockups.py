#!/usr/bin/env python3
"""make_mockups.py: the mockups for the aquarium schooling plan: a LIVE simulation of the proposed rules (school and swarm around the player's fish),
the rule/mode diagram with frozen snapshots of the same simulation, and the edge-case states. Each page is one self-contained 1440x900 HTML (inline CSS/JS)
plus a same-name PNG made with headless Chrome (the simulation is run for a fixed number of steps first, from a seeded generator, so the PNG is deterministic).
The simulation is a mockup of the BEHAVIOUR, in the tank's real proportions (48 in wide, the fish 3.5 in at x10 scale); the engine implementation is Forth.
Usage: python3 make_mockups.py
"""
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent

SIM = r"""
// ---- the proposed behaviour, 2D side view + a little depth. Units: metres at WORLD_SCALE 10 (the tank is 12.19 m wide, 5.33 m tall, 3.3 m deep) ----
const T={W:12.19,H:5.33,D:3.3}, BL=0.889;                      // the fish body length
function rng(seed){let s=seed>>>0;return()=>{s=(s*1664525+1013904223)>>>0;return s/4294967296}}
const P={ // tunables, each one a Forth constant in the real build
  vSchoolOn:0.9, vSchoolOff:0.4, offDelay:0.5,                    // m/s: school when the leader swims faster than vSchoolOn; swarm again after vSchoolOff for offDelay s
  sepR:0.9*BL, sepW:2.2, alignW:1.6, slotW:1.8, orbitW:1.1, wanderW:0.5, wallM:0.9, wallW:3.0, maxTurn:2.6, vMax:3.9, catchK:1.2 };
function makeWorld(seed){
  const r=rng(seed), W={r,t:0,mode:0,blend:0,slow:0,player:{x:3.2,y:0,z:2.5,hx:1,hz:0,v:0},fish:[]};
  for(let i=0;i<10;i++){const a=r()*6.283;W.fish.push({x:W.player.x+Math.cos(a)*(1.5+r()*2),y:(r()-.5)*1.6,z:W.player.z+(r()-.5)*2,hx:Math.cos(a+1.5),hz:Math.sin(a+1.5)*0.2,v:0.5,
    slot:{back:BL*(1.4+0.9*(i>>1)),side:(i&1?1:-1)*BL*(0.7+0.5*(i>>2)),vert:((i%3)-1)*0.25*BL},orbR:BL*(1.6+((i*37)%10)/10*2.2),ph:r()*6.283,size:0.78+0.22*r()});}
  return W;}
function norm(x,y,z){const l=Math.hypot(x,y,z)||1;return[x/l,y/l,z/l]}
function step(W,dt,input){ // input: {tx,tz} the player's target point (the mouse / the held buttons)
  const p=W.player, P0=p.v;
  // the player swims toward the target like the real one: turn toward it, speed ~ distance, glide
  const dx=input.tx-p.x, dz=input.tz-p.z, d=Math.hypot(dx,dz);
  if(d>0.3){const [ux,uz]=[dx/d,dz/d]; p.hx+=(ux-p.hx)*Math.min(1,3*dt); p.hz+=(uz-p.hz)*Math.min(1,3*dt); const n=Math.hypot(p.hx,p.hz); p.hx/=n; p.hz/=n; p.v+=((Math.min(3.0,d*1.4))-p.v)*Math.min(1,4*dt);} else p.v+=(0-p.v)*Math.min(1,4*dt);
  p.x+=p.hx*p.v*dt; p.z+=p.hz*p.v*dt; p.x=Math.max(0.6,Math.min(T.W-0.6,p.x)); p.z=Math.max(0.5,Math.min(T.H-0.5,p.z));
  // mode with hysteresis (a Forth state machine on the leader's speed)
  if(W.mode===0){ if(p.v>P.vSchoolOn){W.mode=1;W.slow=0} } else { if(p.v<P.vSchoolOff){W.slow+=dt; if(W.slow>P.offDelay)W.mode=0} else W.slow=0 }
  W.blend+=((W.mode)-W.blend)*Math.min(1,1.6*dt);                   // 0 = swarm, 1 = school, blended so it never snaps
  const s=W.blend, F=W.fish; W.t+=dt;
  for(let i=0;i<F.length;i++){const f=F[i]; let ax=0,ay=0,az=0;
    // separation from the leader and every other follower
    const all=[p,...F.filter(g=>g!==f)];
    for(const g of all){const ex=f.x-g.x,ey=(f.y-g.y)*1.2,ez=f.z-g.z,dd=Math.hypot(ex,ey,ez); if(dd<P.sepR&&dd>1e-4){const k=P.sepW*(1-dd/P.sepR)/dd; ax+=ex*k;ay+=ey*k;az+=ez*k;}}
    // SCHOOL: align with the leader and keep a slot behind and beside it (the slots form a loose V that never overlaps)
    const lx=-p.hx,lz=-p.hz; const sx=-lz, sz=lx;                     // behind, and sideways (in the x-z plane)
    const tx=p.x+lx*f.slot.back+sx*f.slot.side, tz=p.z+lz*f.slot.back+sz*f.slot.side+f.slot.vert, ty=f.slot.side*0.25;
    ax+=s*P.slotW*(tx-f.x); az+=s*P.slotW*(tz-f.z); ay+=s*P.slotW*0.5*(ty-f.y);
    ax+=s*P.alignW*(p.hx*p.v-f.hx*f.v); az+=s*P.alignW*(p.hz*p.v-f.hz*f.v);
    // SWARM: mill round the leader on a loose shell, a slow tangential swirl and a wander (the leader is a hub, not a head)
    const rx=f.x-p.x,rz=f.z-p.z,rd=Math.hypot(rx,rz)||1, k2=(1-s);
    const dirn=(i%2?1:-1); ax+=k2*P.orbitW*((rx/rd)*(f.orbR-rd)*0.9 + (-rz/rd)*0.9*dirn); az+=k2*P.orbitW*((rz/rd)*(f.orbR-rd)*0.9 + (rx/rd)*0.9);
    ax+=k2*P.wanderW*Math.cos(W.t*0.7+f.ph); az+=k2*P.wanderW*Math.sin(W.t*0.9+f.ph*1.3); ay+=k2*0.3*Math.sin(W.t*0.5+f.ph)-0.4*f.y;
    // the anemone crown is a keep-out sphere; while the leader is in its zone (camshot B) followers also drift to the far side of the leader's depth, away from the lens
    {const cx=10.1,cz=2.7,ex=f.x-cx,ez=f.z-cz,ed=Math.hypot(ex,ez)||1; if(ed<1.8){const k=3.2*(1-ed/1.8); ax+=ex/ed*k*3; az+=ez/ed*k*3}
     if(Math.hypot(p.x-cx,p.z-cz)<1.7) ay+=2.0*((p.y+1.0)-f.y);}
    // walls, the floor and the surface push back inside a margin
    const wall=(v,lo,hi)=>v<lo?(lo-v):v>hi?-(v-hi):0, m=P.wallM;
    ax+=P.wallW*wall(f.x,m,T.W-m); az+=P.wallW*wall(f.z,m,T.H-m); ay+=P.wallW*wall(f.y,-T.D/2+0.4,T.D/2-0.4);
    // steer: turn-rate limited toward the wanted velocity, speed from the mode
    let wx=f.hx*f.v+ax*dt*3, wz=f.hz*f.v+az*dt*3; const wv=Math.hypot(wx,wz)||1e-3;
    const vt=(1-s)*(0.35+0.15*Math.sin(W.t+f.ph))+s*Math.min(P.vMax,p.v+P.catchK*Math.hypot(tx-f.x,tz-f.z)*0.5);
    const th=Math.atan2(f.hz,f.hx), tw=Math.atan2(wz,wx); let da=tw-th; while(da>Math.PI)da-=6.283; while(da<-Math.PI)da+=6.283; da=Math.max(-P.maxTurn*dt,Math.min(P.maxTurn*dt,da));
    f.hx=Math.cos(th+da); f.hz=Math.sin(th+da); f.v+=(vt-f.v)*Math.min(1,2.5*dt);
    f.x+=f.hx*f.v*dt; f.z+=f.hz*f.v*dt; f.y+=ay*dt*0.5; f.x=Math.max(0.3,Math.min(T.W-0.3,f.x)); f.z=Math.max(0.3,Math.min(T.H-0.3,f.z)); f.y=Math.max(-T.D/2+.25,Math.min(T.D/2-.25,f.y));
  }
  W.p0=P0;}
function cruise(W,n){for(let i=0;i<n;i++)step(W,0.05,{tx:Math.min(11.8,W.player.x+1.6),tz:W.player.z})}
function metrics(W){const F=W.fish; let sx=0,sz=0,sc=0,mind=1e9,md=0; for(const f of F){const l=Math.hypot(f.hx,f.hz)||1;sx+=f.hx/l;sz+=f.hz/l; md+=Math.hypot(f.x-W.player.x,f.z-W.player.z);}
  for(let i=0;i<F.length;i++){ for(let j=i+1;j<F.length;j++) mind=Math.min(mind,Math.hypot(F[i].x-F[j].x,(F[i].y-F[j].y),F[i].z-F[j].z)); mind=Math.min(mind,Math.hypot(F[i].x-W.player.x,F[i].z-W.player.z)); }
  return{pol:Math.hypot(sx,sz)/F.length, dist:md/F.length, mind};}
// ---- drawing ----
function fishPath(c,x,y,hx,hz,len,flip){c.save();c.translate(x,y);c.rotate(Math.atan2(hz,hx));if(hx<0)c.scale(1,-1);c.beginPath();c.moveTo(len*.5,0);c.quadraticCurveTo(len*.2,-len*.22,-len*.28,-len*.1);c.lineTo(-len*.5,-len*.2);c.lineTo(-len*.42,0);c.lineTo(-len*.5,len*.2);c.lineTo(-len*.28,len*.1);c.quadraticCurveTo(len*.2,len*.22,len*.5,0);c.closePath();}
function drawFish(c,sx,sy,f,scale,tint,isPlayer){const len=BL*scale*(f.size||1);fishPath(c,sx,sy,f.hx,-f.hz,len);c.fillStyle=isPlayer?'#ff4d00':tint;c.fill();if(isPlayer){c.lineWidth=len*.12;c.strokeStyle='#ffffff';c.stroke()}c.lineWidth=Math.max(1,len*.04);c.strokeStyle='#1a0d00';c.stroke();
  c.clip();c.fillStyle='#fff';for(const o of[.22,-.02,-.24]){c.fillRect(len*o-len*.04,-len*.3,len*.08,len*.6)}c.restore();
  c.save();c.translate(sx,sy);c.rotate(Math.atan2(-f.hz,f.hx));if(f.hx<0)c.scale(1,-1);c.fillStyle='#000';c.beginPath();c.arc(len*.33,-len*.05,len*.035,0,6.3);c.fill();c.restore();}
function drawTank(c,w,h,scale){c.fillStyle='#0f2a3c';c.fillRect(0,0,w,h);const g=c.createLinearGradient(0,0,0,h);g.addColorStop(0,'#3aa3c4');g.addColorStop(1,'#0e5a77');c.fillStyle=g;c.fillRect(0,0,T.W*scale,T.H*scale);
  c.fillStyle='rgba(255,255,255,.07)';for(let i=0;i<4;i++){c.beginPath();c.moveTo(i*3.4*scale+1*scale,0);c.lineTo(i*3.4*scale+2.6*scale,0);c.lineTo(i*3.4*scale+1.6*scale,T.H*scale);c.lineTo(i*3.4*scale+0.4*scale,T.H*scale);c.fill()}
  c.fillStyle='#c4b078';c.fillRect(0,(T.H-0.0)*scale-0,T.W*scale,0);                                      // z up: the floor is z=0 at the bottom
  c.fillStyle='#c4b078';c.fillRect(0,h-0.35*scale,T.W*scale,0.35*scale);
  c.fillStyle='#6e7172';c.beginPath();c.moveTo(9.0*scale,h-0.35*scale);c.lineTo(9.5*scale,h-1.0*scale);c.lineTo(10.6*scale,h-1.0*scale);c.lineTo(11.1*scale,h-0.35*scale);c.fill();       // the rock
  c.fillStyle='#9c6b40';c.fillRect(9.85*scale,h-1.9*scale,0.5*scale,0.9*scale);c.strokeStyle='#b0467f';c.lineWidth=2;for(let a=-9;a<=9;a++){c.beginPath();c.moveTo(10.1*scale,h-1.9*scale);c.lineTo(10.1*scale+a*0.17*scale,h-3.0*scale-Math.abs(a)*0.0);c.stroke()}        // the anemone
}
"""

LIVE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Mockup 1: school and swarm (live)</title><style>
*{box-sizing:border-box}body{margin:0;width:1440px;height:900px;background:#0d1117;color:#e6edf3;font:16px/1.4 system-ui,'Noto Sans',sans-serif;overflow:hidden}
.top{padding:20px 34px 8px;border-bottom:1px solid #263041;display:flex;justify-content:space-between;align-items:baseline}h1{margin:0;font-size:22px;font-weight:650}.sub{color:#8b98a9;font-size:14px}
canvas{display:block;margin:14px 34px 0;border:1px solid #2b3a52;border-radius:6px}.hud{display:flex;gap:26px;align-items:center;margin:12px 34px;font-size:15px}
.badge{padding:3px 14px;border-radius:999px;font-weight:650}.school{background:#1f6f43;color:#d6ffe8}.swarm{background:#6b4b12;color:#ffe6b0}.m{color:#9fb3cc}.m b{color:#e6edf3}
.note{color:#ffb454;font-size:13px;margin:0 34px}</style></head><body>
<div class="top"><h1>Mockup 1: ten fish school and swarm around the player (live)</h1><div class="sub">move the mouse: the player's fish (orange) swims to the pointer; the ten followers are the proposal</div></div>
<canvas id="c" width="1372" height="620"></canvas>
<div class="hud"><span id="badge" class="badge swarm">SWARM</span><span class="m">leader speed <b id="v">0.0</b> m/s</span><span class="m">blend <b id="b">0.00</b></span><span class="m">alignment (polarisation) <b id="pol">0.00</b></span><span class="m">mean distance to leader <b id="dist">0.0</b> m</span><span class="m">closest pair <b id="mind">0.0</b> m (body = 0.89 m)</span></div>
<div class="note">Move slowly or stop: the fish <b>swarm</b> (mill round you, unaligned). Swim across the tank: they <b>school</b> (fall in behind and beside, aligned). The switch has a hysteresis and a blend, so it never snaps. Rules, tunables and edge cases: mockups 2 and 3.</div>
<script>__SIM__
const c=document.getElementById('c').getContext('2d'), S=1372/T.W; let W=makeWorld(7), tx=W.player.x, tz=W.player.z, last=0;
const cv=document.getElementById('c'); cv.addEventListener('mousemove',e=>{const r=cv.getBoundingClientRect();tx=(e.clientX-r.left)/S;tz=(cv.height-(e.clientY-r.top))/S});
function frame(){drawTank(c,cv.width,cv.height,S);
  const all=[...W.fish.map(f=>[f,false]),[W.player,true]].sort((a,b)=>a[0].y-b[0].y);
  for(const [f,pl] of all){const sc=S*(0.9+0.1*(f.y/T.D)+0.0);drawFish(c,f.x*S,cv.height-f.z*S,{hx:f.hx,hz:f.hz,size:f.size},sc,'#f2c96b',pl)}
  const m=metrics(W);document.getElementById('v').textContent=W.player.v.toFixed(1);document.getElementById('b').textContent=W.blend.toFixed(2);document.getElementById('pol').textContent=m.pol.toFixed(2);document.getElementById('dist').textContent=m.dist.toFixed(1);document.getElementById('mind').textContent=m.mind.toFixed(2);
  const bd=document.getElementById('badge');bd.textContent=W.mode?'SCHOOL':'SWARM';bd.className='badge '+(W.mode?'school':'swarm');}
function loop(t){const dt=Math.min(.05,(t-last)/1000||0.016);last=t;step(W,dt,{tx,tz});frame();requestAnimationFrame(loop)}
const demo=location.hash.indexOf('demo=')>=0;
if(demo){tx=1.2;tz=3.0;for(let i=0;i<200;i++)step(W,0.05,{tx,tz});cruise(W,60);frame();}
else requestAnimationFrame(loop);
</script></body></html>"""

MODES = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Mockup 2: the two modes and their rules</title><style>
*{box-sizing:border-box}body{margin:0;width:1440px;height:900px;background:#0d1117;color:#e6edf3;font:15px/1.4 system-ui,'Noto Sans',sans-serif;overflow:hidden}
.top{padding:20px 34px 8px;border-bottom:1px solid #263041;display:flex;justify-content:space-between;align-items:baseline}h1{margin:0;font-size:22px;font-weight:650}.sub{color:#8b98a9;font-size:14px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px;padding:18px 34px}canvas{border:1px solid #2b3a52;border-radius:6px;width:100%}h3{margin:0 0 6px;font-size:17px}.school{color:#56d364}.swarm{color:#ffb454}
table{border-collapse:collapse;font-size:13.5px;width:100%;margin-top:8px}td,th{padding:5px 8px 5px 0;border-bottom:1px solid #1d2635;text-align:left;vertical-align:top}th{color:#8b98a9;font-weight:500}.mono{font-family:ui-monospace,monospace;color:#9fb3cc}
.tl{margin:0 34px;padding:10px 14px;background:#111826;border:1px solid #233048;border-radius:8px;font-size:13.5px}</style></head><body>
<div class="top"><h1>Mockup 2: school and swarm, the rules and the switch</h1><div class="sub">frozen snapshots of the mockup-1 simulation (seeded, so they never change); the numbers are the proposed tunables</div></div>
<div class="grid"><div><h3 class="school">SCHOOL: the leader is cruising</h3><canvas id="a" width="640" height="300"></canvas>
<table><tr><th>Rule</th><th>What the follower does</th></tr><tr><td>slot</td><td>seeks its own place <b>behind and beside</b> the leader (a loose V, two ranks), so the school never overlaps</td></tr>
<tr><td>align</td><td>matches the leader's heading and speed (catches up with a burst if it falls behind)</td></tr><tr><td>separate</td><td>pushes off any fish nearer than 0.9 body lengths (always on)</td></tr></table></div>
<div><h3 class="swarm">SWARM: the leader is resting or drifting</h3><canvas id="b" width="640" height="300"></canvas>
<table><tr><th>Rule</th><th>What the follower does</th></tr><tr><td>orbit</td><td>mills round the leader on its own shell (1.6 to 3.8 body lengths) with a slow swirl: the leader is a hub, not a head</td></tr>
<tr><td>wander</td><td>a small per-fish drift (own phase), so the swarm breathes and never freezes</td></tr><tr><td>separate</td><td>the same push-off; no alignment, so the headings are scattered</td></tr></table></div></div>
<div class="tl"><b>The switch.</b> Mode follows the leader's speed through a <b>hysteresis</b>: SCHOOL when it exceeds <span class="mono">0.9 m/s</span>; back to SWARM only after it stays under <span class="mono">0.4 m/s</span> for <span class="mono">0.5 s</span>. The rules are blended by a value that eases toward 0 or 1 (about 0.6 s), so a school <i>loosens</i> into a swarm instead of snapping. Always on, both modes: separation, walls and floor and surface (soft push inside 0.9 m), the anemone crown (steer round, below), a turn-rate limit, and the same fixed-point-safe maths as the player. <b>Measured in the tests:</b> polarisation (how aligned the headings are) at least 0.8 in SCHOOL and at most 0.5 in SWARM; no pair closer than 0.5 body lengths; nobody through a wall.</div>
<script>__SIM__
function snap(id,fn){const cv=document.getElementById(id),c=cv.getContext('2d'),S=cv.width/T.W;const W=makeWorld(7);fn(W);drawTank(c,cv.width,cv.height,S);
 const all=[...W.fish.map(f=>[f,false]),[W.player,true]].sort((a,b)=>a[0].y-b[0].y);for(const[f,pl]of all)drawFish(c,f.x*S,cv.height-f.z*S,{hx:f.hx,hz:f.hz,size:f.size},S*(0.9+0.1*(f.y/T.D)),'#f2c96b',pl);
 const m=metrics(W);c.fillStyle='#000a';c.fillRect(8,8,236,26);c.fillStyle='#e6edf3';c.font='13px system-ui';c.fillText('polarisation '+m.pol.toFixed(2)+'   closest pair '+m.mind.toFixed(2)+' m',14,26);}
snap('a',W=>{for(let i=0;i<200;i++)step(W,0.05,{tx:1.2,tz:3.0});cruise(W,60)});
snap('b',W=>{for(let i=0;i<300;i++)step(W,0.05,{tx:5.0,tz:2.8})});
</script></body></html>"""

STATES = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Mockup 3: edge cases</title><style>
*{box-sizing:border-box}body{margin:0;width:1440px;height:900px;background:#0d1117;color:#e6edf3;font:15px/1.4 system-ui,'Noto Sans',sans-serif;overflow:hidden}
.top{padding:20px 34px 8px;border-bottom:1px solid #263041;display:flex;justify-content:space-between;align-items:baseline}h1{margin:0;font-size:22px;font-weight:650}.sub{color:#8b98a9;font-size:14px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;padding:18px 34px}.c{background:#111826;border:1px solid #233048;border-radius:10px;padding:12px}canvas{width:100%;border:1px solid #2b3a52;border-radius:6px;background:#0f2a3c}
h3{margin:8px 0 4px;font-size:16px}p{margin:0;font-size:13.5px;color:#b7c3d4}.ok{color:#56d364}.warn{color:#ffb454}.bad{color:#ff7b72}</style></head><body>
<div class="top"><h1>Mockup 3: the edge cases the plan has to handle</h1><div class="sub">each frame is the same seeded simulation, set up to stress one rule</div></div>
<div class="grid" id="g"></div>
<script>__SIM__
const cases=[["1 Dart (A): the school scatters, then regroups","warn","The leader's burst is faster than any follower. Followers inside 2 body lengths get a short outward kick (a startle, 0.6 s), then the slots pull them back. Optional: a decision for the user.",W=>{for(let i=0;i<150;i++)step(W,.05,{tx:2.5,tz:3});for(let i=0;i<20;i++){step(W,.05,{tx:9,tz:3});}for(const f of W.fish){const dx=f.x-W.player.x,dz=f.z-W.player.z,d=Math.hypot(dx,dz)||1;if(d<2){f.hx=dx/d;f.hz=dz/d;f.v=3.2}}for(let i=0;i<8;i++)step(W,.05,{tx:9,tz:3})}],
["2 The anemone crown (camshot B)","ok","Inside the anemone zone the camera closes in on the leader. Followers steer round a keep-out sphere over the crown and stay <b>behind the leader's depth</b> (away from the camera), so nobody swims between the lens and the player.",W=>{for(let i=0;i<260;i++)step(W,.05,{tx:10.1,tz:2.6})}],
["3 Hard against the glass and the walls","ok","Walls and the floor push back from 0.9 m, and a follower's turn rate is limited, so a fast school bends away from an end wall instead of piling into it. Tested: nobody through a wall.",W=>{for(let i=0;i<200;i++)step(W,.05,{tx:11.8,tz:4.6})}],
["4 Leader at rest in a corner","warn","A swarm around a leader pinned to the corner has little room: orbit shells are clipped by the walls. The wall push wins; the swarm bunches on the open side. Acceptable, and measured.",W=>{for(let i=0;i<300;i++)step(W,.05,{tx:0.4,tz:0.6})}],
["5 Slow frame on the Chromecast","bad","If the frame cost rises (the budget is 16.7 ms), the followers update in <b>round-robin</b>: a third of them per tick, the rest keep their last velocity. The picture degrades to a slightly lazier school, never to a hitch. Measured on the device before it ships. <i>(An implementation mode: not simulated in this mockup.)</i>",W=>{for(let i=0;i<260;i++){step(W,.05,{tx:6+4*Math.sin(i/40),tz:3})}}],
["6 Fish keep their own size and phase","ok","Sizes vary 0.78 to 1.0 of the player's, and each fish has its own tail-beat phase, so ten copies do not move as one. Same model and rig as the player.",W=>{for(let i=0;i<180;i++)step(W,.05,{tx:5,tz:2.6})}]];
const g=document.getElementById('g');
cases.forEach(([t,k,d,fn],i)=>{const e=document.createElement('div');e.className='c';e.innerHTML='<canvas id="k'+i+'" width="420" height="190"></canvas><h3 class="'+k+'">'+t+'</h3><p>'+d+'</p>';g.appendChild(e);
 const cv=document.getElementById('k'+i),c=cv.getContext('2d'),S=cv.width/T.W,W=makeWorld(7+i);fn(W);drawTank(c,cv.width,cv.height,S);
 const all=[...W.fish.map(f=>[f,false]),[W.player,true]].sort((a,b)=>a[0].y-b[0].y);for(const[f,pl]of all)drawFish(c,f.x*S,cv.height-f.z*S,{hx:f.hx,hz:f.hz,size:f.size},S*(0.9+0.1*(f.y/T.D)),'#f2c96b',pl);
 if(i==1){c.strokeStyle='#ff7b72';c.setLineDash([4,3]);c.beginPath();c.arc(10.1*S,cv.height-2.6*S,1.7*S,0,6.3);c.stroke();c.setLineDash([])}});
</script></body></html>"""

for name, tpl in (("live-sim", LIVE), ("modes", MODES), ("edge-cases", STATES)):
    html = tpl.replace("__SIM__", SIM)
    f = HERE / f"{name}.html"; f.write_text(html, encoding="utf-8")
    kb = f.stat().st_size // 1024; assert kb < 512, (name, kb)
    url = f"file://{f}" + ("#demo=1" if name == "live-sim" else "")
    subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--hide-scrollbars", "--window-size=1440,900", "--virtual-time-budget=4000",
                    f"--screenshot={HERE / (name + '.png')}", url], capture_output=True, text=True)
    print(f"{name}: {kb} KB html, png {'ok' if (HERE / (name + '.png')).exists() else 'MISSING'}")
