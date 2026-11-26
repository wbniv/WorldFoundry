#!/usr/bin/env python3
"""Build the self-contained HTML mockups for docs/plans/2026-11-26-lava-lamp.md.

Every page inlines one shared renderer (LAMP_JS): a 2-D metaball lava lamp
driven by the plan's buoyancy model (section "How the wax moves"). The model
constants here are the plan's starting values; tests/test_lava_lamp.py will
pin the same numbers once Phase 3 lands.

    python3 docs/plans/2026-11-26-lava-lamp/build_mockups.py
    bash docs/plans/2026-11-26-lava-lamp/shoot.sh      # PNGs beside each page

Each page sets window.__ready once its first frame is drawn, and exposes
window.setClock('HH:MM') so a screenshot can pin the displayed time.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent

LAMP_JS = r"""
"use strict";
window.onerror=function(m,s,l){const d=document.createElement('div');d.style.cssText='position:fixed;left:0;top:0;z-index:99;background:#b00;color:#fff;font:14px monospace;padding:6px';d.textContent='JS error: '+m+' @'+l;document.body.appendChild(d);};
const LAVA=[["Red","#e0281e"],["Orange","#ff6516"],["Yellow","#ffc417"],["Pink","#ff4fa0"],["Purple","#9b3cf0"],["Turquoise","#18d2c4"],["Green","#49d23a"],["White","#f4efe6"]];
const WATER=[["Clear","#d9d3c4"],["Yellow","#ffd23a"],["Orange","#ff8a1e"],["Pink","#ff5aa8"],["Violet","#7a2cff"],["Blue","#1f6bff"],["Turquoise","#14c8c0"],["Green","#2fbf4f"]];
const DEF_LAVA=1, DEF_WATER=4;
const clamp=(x,a,b)=>x<a?a:x>b?b:x;
const smooth=(a,b,x)=>{const t=clamp((x-a)/(b-a),0,1);return t*t*(3-2*t);};
const hex=h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)];
const mix=(a,b,t)=>[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t];
const mul=(a,k)=>[a[0]*k,a[1]*k,a[2]*k];
const css=(c,al)=>{const f=x=>Math.max(0,Math.min(255,Math.round(x)));return al===undefined?`rgb(${f(c[0])},${f(c[1])},${f(c[2])})`:`rgba(${f(c[0])},${f(c[1])},${f(c[2])},${al})`;};
function rng(seed){return function(){seed|=0;seed=seed+0x6D2B79F5|0;let t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
// Globe radius at height y (both in globe heights): widest a quarter of the way up.
const GR=y=>y<0.25?0.27-0.72*(0.25-y)*(0.25-y):0.27-0.2*(y-0.25)*(y-0.25);

// ---- the plan's wax model (starting values; game tuning, not measurement) ----
const M={B:0.55,K:0.012,TN:0.6,LO:0.3,REL:0.88,DROP:0.5,DRAG:1.6,COIL:1.1};
const envT=y=>M.LO+0.75*Math.exp(-y/0.08)-0.08*y;   // hot layer over the coil, cool above
function makeSim(seed,n,warm){
  const r=rng(seed),blobs=[];
  for(let i=0;i<n;i++){const rad=0.042+r()*0.042;blobs.push({x:(r()-0.5)*0.25,y:0.06+r()*0.86,vx:0,vy:0,r:rad,T:0.35+r()*0.5,ph:r()*60,stuck:null});}
  const s={blobs,t:0};for(let i=0;i<(warm===undefined?4500:warm);i++)stepSim(s,1/30);return s;
}
function stepSim(s,dt){
  s.t+=dt;const B=s.blobs,t=s.t;
  for(const b of B){
    const k=M.K*(0.06/b.r)*(b.stuck==='bot'?2:1);
    const target=b.stuck==='bot'?M.COIL:envT(b.y);
    b.T+=(target-b.T)*(1-Math.exp(-k*dt));            // exact Newton cooling step (needs exp)
    if(b.stuck==='bot'&&b.T>M.REL)b.stuck=null;
    if(b.stuck==='top'&&b.T<M.DROP)b.stuck=null;
    const buoy=b.stuck?0:M.B*(b.T-M.TN);
    b.vy+=(buoy-M.DRAG*b.vy)*dt; if(b.stuck)b.vy=0;
    const drift=0.010*Math.sin(t*0.11+b.ph)+0.006*Math.sin(t*0.27+b.ph*1.9);
    const conv=b.vy>0?-0.05*b.x:(b.vy<-0.01?0.035*Math.sign(b.x||1):0);
    b.vx+=(drift+conv-1.2*b.vx)*dt;
  }
  for(let i=0;i<B.length;i++)for(let j=i+1;j<B.length;j++){
    const a=B[i],c=B[j];const dx=c.x-a.x,dy=c.y-a.y;const d=Math.hypot(dx,dy)||1e-6;const s0=(a.r+c.r)*0.85;
    if(d<s0){const f=(s0-d)*1.5*dt/d;a.vx-=dx*f;a.vy-=dy*f;c.vx+=dx*f;c.vy+=dy*f;const dT=(c.T-a.T)*0.08*dt;a.T+=dT;c.T-=dT;}
    else if(d<0.3){const f=0.004*(1-d/0.3)*dt/d;a.vx+=dx*f;a.vy+=dy*f;c.vx-=dx*f;c.vy-=dy*f;}
  }
  for(const b of B){
    b.x+=b.vx*dt;b.y+=b.vy*dt;
    const lo=0.03+b.r*0.45,hi=1-b.r*0.8-0.012;
    if(b.y<=lo){b.y=lo;if(b.vy<0)b.vy=0;if(b.T<M.REL)b.stuck='bot';}
    if(b.y>=hi){b.y=hi;if(b.vy>0)b.vy=0;if(b.T>M.DROP)b.stuck='top';}
    const lim=GR(b.y)-b.r*0.9;if(Math.abs(b.x)>lim){b.x=Math.sign(b.x)*lim;b.vx*=-0.2;}
  }
}
// Each blob is drawn as two field sources: head and trailing tail (teardrop when
// moving, pancake when resting at the top). The bottom pool is six fixed sources.
function simBalls(s){
  const out=[],t=s.t;
  for(let i=0;i<6;i++)out.push([-0.18+i*0.072,0.0,0.056+0.009*Math.sin(t*0.15+i*1.7)]);
  for(const b of s.blobs){
    const st=clamp(b.vy*8,-0.6,0.6),hi=1-b.r*0.8-0.012;
    const sq=b.stuck==='top'?1:smooth(0.03,0,hi-b.y)*0.6;
    const wob=0.06*Math.sin(t*0.7+b.ph),ox=sq*b.r*0.55;
    out.push([b.x-ox,b.y+st*b.r*0.55+sq*b.r*0.08,b.r*(1-0.12*Math.abs(st))*(1-0.12*sq)*(1+wob)]);
    out.push([b.x+ox,b.y-st*b.r*0.85,b.r*(0.72-0.15*Math.abs(st))*(1+0.12*sq)*(1-wob)]);
  }
  return out;
}
function waxCanvas(cache,Hg,balls,lava,water){
  const gh=Math.max(20,Math.round(Hg/1.7)),gw=Math.round(gh*0.56);
  if(!cache.c||cache.c.width!==gw||cache.c.height!==gh){cache.c=document.createElement('canvas');cache.c.width=gw;cache.c.height=gh;cache.f=new Float32Array((gw+2)*(gh+2));cache.img=cache.c.getContext('2d').createImageData(gw,gh);}
  const W=gw+2,f=cache.f,du=0.56/gw,dv=1/gh;f.fill(0);
  for(const [bx,by,r] of balls){const s=1.74*r,s2=s*s;
    const i0=Math.max(0,Math.floor((bx-s+0.28)/du)),i1=Math.min(gw+1,Math.ceil((bx+s+0.28)/du)+1);
    const j0=Math.max(0,Math.floor(by/dv-s/dv)),j1=Math.min(gh+1,Math.ceil((by+s)/dv)+1);
    for(let j=j0;j<=j1;j++){const dy=(j-0.5)*dv-by,dy2=dy*dy;if(dy2>=s2)continue;
      for(let i=i0;i<=i1;i++){const dx=-0.28+(i-0.5)*du-bx,q=(dx*dx+dy2)/s2;if(q<1){const u=1-q;f[j*W+i]+=u*u*u;}}}}
  const d=cache.img.data,T0=0.3,LC=lava,wf=mix([1,1,1],mul(water,1/255),0.14);
  const Lx=0,Ly=-0.84,Lz=0.54,Hx=-0.28,Hy=0.5,Hz=0.82;
  for(let j=1;j<=gh;j++){const y=(j-0.5)*dv,g=(1-y)*(1-y),row=(gh-j)*gw;
    for(let i=1;i<=gw;i++){const F=f[j*W+i],p=(row+i-1)*4;
      if(F<T0-0.06){d[p+3]=0;continue;}
      const a=smooth(T0-0.06,T0+0.03,F);
      const gx=(f[j*W+i+1]-f[j*W+i-1])/(2*du),gy=(f[(j+1)*W+i]-f[(j-1)*W+i])/(2*dv);
      let nx=-gx*0.06,ny=-gy*0.06,nz=1;const nl=Math.hypot(nx,ny,nz);nx/=nl;ny/=nl;nz/=nl;
      const diff=Math.max(0,nx*Lx+ny*Ly+nz*Lz),thin=1-smooth(T0,T0+0.4,F);
      const sh=0.42+0.5*diff+0.5*g*(0.4+0.6*diff)+0.35*thin*(0.4+g);
      const sp=Math.pow(Math.max(0,nx*Hx+ny*Hy+nz*Hz),28)*0.45,m=Math.min(sh,1);
      let r=LC[0]*m,gg=LC[1]*m,b=LC[2]*m;
      if(sh>1){const t=Math.min(1,(sh-1)*0.9)*0.6;r+=(255-r)*t;gg+=(240-gg)*t;b+=(215-b)*t;}
      r=r*wf[0]+sp*255;gg=gg*wf[1]+sp*255;b=b*wf[2]+sp*255;
      d[p]=r>255?255:r;d[p+1]=gg>255?255:gg;d[p+2]=b>255?255:b;d[p+3]=a*255;}}
  cache.c.getContext('2d').putImageData(cache.img,0,0);return cache.c;
}
// ---- the starlight dot-matrix font, 5x7 ----
const GLYPH={'0':['01110','10001','10011','10101','11001','10001','01110'],'1':['00100','01100','00100','00100','00100','00100','01110'],
'2':['01110','10001','00001','00010','00100','01000','11111'],'3':['11111','00010','00100','00010','00001','10001','01110'],
'4':['00010','00110','01010','10010','11111','00010','00010'],'5':['11111','10000','11110','00001','00001','10001','01110'],
'6':['00110','01000','10000','11110','10001','10001','01110'],'7':['11111','00001','00010','00100','01000','01000','01000'],
'8':['01110','10001','10001','01110','10001','10001','01110'],'9':['01110','10001','10001','01111','00001','00010','01100'],
'-':['00000','00000','00000','11111','00000','00000','00000'],':':['0','0','1','0','1','0','0']};
function matrixCols(text){const cols=[],pad=()=>cols.push([0,0,0,0,0,0,0,0,0]);pad();pad();
  for(let k=0;k<5;k++){const g=GLYPH[text[k]];for(let c=0;c<g[0].length;c++){const col=[0];for(let r=0;r<7;r++)col.push(+g[r][c]);col.push(0);cols.push(col);}if(k<4)pad();}
  pad();pad();return cols;}
function ell(ctx,x,y,rx,ry){ctx.beginPath();ctx.ellipse(x,y,Math.max(0.1,rx),Math.max(0.1,ry),0,0,Math.PI*2);ctx.fill();}
// Holes on a conical band: yT..yB, radius rAt(y); text lit bright, other holes faint starlight.
function drawHoleBand(ctx,cx,yT,yB,rAt,text,mode,th){
  const cols=matrixCols(text||'--:--'),nC=cols.length,nR=9,pitch=(yB-yT)/nR,hr=pitch*0.3,lit=[];
  th=th||1.0;const level=mode==='dim'?0.45:1;
  for(let c=0;c<nC;c++)for(let r=0;r<nR;r++){
    const y=yT+(r+0.5)*pitch,rr=rAt(y),a=((c-(nC-1)/2)/((nC-1)/2))*th,x=cx+rr*Math.sin(a),w=Math.cos(a);
    if(cols[c][r]){ctx.fillStyle='rgba(20,12,3,0.9)';ell(ctx,x,y,hr*w*1.15,hr*1.15);lit.push([x,y,w]);}else{ctx.fillStyle='rgba(60,40,10,0.55)';ell(ctx,x,y,hr*w*0.8,hr*0.8);ctx.fillStyle='rgba(255,206,130,0.12)';ell(ctx,x,y,hr*w*0.5,hr*0.5);}
  }
  ctx.save();ctx.globalCompositeOperation='lighter';
  for(const [x,y,w] of lit){const g=ctx.createRadialGradient(x,y,0,x,y,hr*2.1);g.addColorStop(0,`rgba(255,196,110,${0.3*level})`);g.addColorStop(1,'rgba(255,170,80,0)');
    ctx.fillStyle=g;ctx.fillRect(x-hr*2.1,y-hr*2.1,hr*4.2,hr*4.2);ctx.fillStyle=`rgba(255,246,222,${level})`;ell(ctx,x,y,hr*w*1.05,hr*1.05);}
  ctx.restore();
}
const FINISH={gold:[[0,'#1e1505'],[0.14,'#5c4213'],[0.32,'#e9c56c'],[0.4,'#fff0b8'],[0.5,'#c2902f'],[0.78,'#6a4c16'],[1,'#1a1205']]};
function lampGeom(cx,baseY,Hg){const hb=0.56*Hg,gb=baseY-hb;return{cx,baseY,Hg,hb,gb,gt:gb-Hg,hc:0.36*Hg,rbB:0.43*Hg,rbT:0.235*Hg,rcB:0.178*Hg,rcT:0.062*Hg};}
function frustum(ctx,cx,yBot,yTop,rB,rT,e){ctx.beginPath();ctx.moveTo(cx-rT,yTop);ctx.lineTo(cx-rB,yBot);ctx.ellipse(cx,yBot,rB,rB*e,0,Math.PI,0,true);ctx.lineTo(cx+rT,yTop);ctx.ellipse(cx,yTop,rT,rT*e,0,0,Math.PI,false);ctx.closePath();}
function metal(ctx,x0,x1){const g=ctx.createLinearGradient(x0,0,x1,0);for(const [o,c] of FINISH.gold)g.addColorStop(o,c);return g;}
function globePath(ctx,G){ctx.beginPath();for(let k=0;k<=48;k++){const y=k/48;ctx.lineTo(G.cx-GR(y)*G.Hg,G.gb-y*G.Hg);}for(let k=48;k>=0;k--){const y=k/48;ctx.lineTo(G.cx+GR(y)*G.Hg,G.gb-y*G.Hg);}ctx.closePath();}
// o: {sim, lava, water (indices), time 'HH:MM'|null, mode, holes (default true), ghost, cache}
function drawLamp(ctx,G,o){
  const L=hex(LAVA[o.lava][1]),Wt=hex(WATER[o.water][1]),Hg=G.Hg,cx=G.cx;
  // base
  ctx.fillStyle=metal(ctx,cx-G.rbB,cx+G.rbB);frustum(ctx,cx,G.baseY,G.gb,G.rbB,G.rbT,0.12);ctx.fill();
  ctx.fillStyle='rgba(0,0,0,0.35)';frustum(ctx,cx,G.baseY,G.baseY-G.hb*0.05,G.rbB,G.rbB*0.985,0.12);ctx.fill();
  if(o.holes!==false){
    const rAt=y=>G.rbT+(G.rbB-G.rbT)*((y-G.gb)/G.hb);
    drawHoleBand(ctx,cx,G.baseY-G.hb*0.84,G.baseY-G.hb*0.2,rAt,o.time,o.mode,0.78);
    const r=rng(11);ctx.fillStyle='rgba(255,206,130,0.16)';
    for(let k=0;k<70;k++){const top=k%2===0,y=top?G.gb+G.hb*(0.04+r()*0.11):G.baseY-G.hb*(0.07+r()*0.1),a=(r()*2-1)*1.25,rr=rAt(y),w=Math.cos(a);ell(ctx,cx+rr*Math.sin(a),y,1.1*w*Hg/270,1.1*Hg/270);}
  }
  ctx.fillStyle='rgba(0,0,0,0.45)';ctx.fillRect(cx-G.rbT,G.gb-1,G.rbT*2,Math.max(1.5,Hg*0.008));
  // globe
  ctx.save();globePath(ctx,G);ctx.clip();
  const lg=ctx.createLinearGradient(0,G.gb,0,G.gt);
  lg.addColorStop(0,css(mix(Wt,[255,238,205],0.62)));lg.addColorStop(0.16,css(mix(Wt,[255,238,205],0.15)));lg.addColorStop(0.55,css(mul(Wt,0.6)));lg.addColorStop(1,css(mul(Wt,0.22)));
  ctx.fillStyle=lg;ctx.fillRect(cx-0.3*Hg,G.gt,0.6*Hg,Hg);
  const bg=ctx.createRadialGradient(cx,G.gb+0.04*Hg,0,cx,G.gb+0.04*Hg,0.42*Hg);bg.addColorStop(0,'rgba(255,240,210,0.55)');bg.addColorStop(1,'rgba(255,240,210,0)');ctx.fillStyle=bg;ctx.fillRect(cx-0.3*Hg,G.gb-0.45*Hg,0.6*Hg,0.5*Hg);
  ctx.strokeStyle='rgba(60,50,40,0.75)';ctx.lineWidth=Math.max(0.6,Hg*0.004);
  for(let k=0;k<6;k++){ctx.beginPath();ctx.ellipse(cx-0.15*Hg+k*0.06*Hg,G.gb-0.018*Hg,0.035*Hg,0.012*Hg,0,0,Math.PI*2);ctx.stroke();}
  if(o.ghost){ctx.save();ctx.font=`600 ${0.12*Hg}px system-ui,sans-serif`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.shadowColor='rgba(255,255,255,0.6)';ctx.shadowBlur=Hg*0.02;ctx.fillStyle='rgba(255,252,240,0.42)';ctx.fillText(o.ghost,cx,G.gb-0.5*Hg);ctx.restore();}
  if(o.sim){const wax=waxCanvas(o.cache||(o.cache={}),Hg,simBalls(o.sim),L,Wt);ctx.imageSmoothingEnabled=true;ctx.drawImage(wax,cx-0.28*Hg,G.gt,0.56*Hg,Hg);}
  const hg=ctx.createLinearGradient(cx-0.27*Hg,0,cx+0.27*Hg,0);
  hg.addColorStop(0,'rgba(0,0,0,0.6)');hg.addColorStop(0.22,'rgba(0,0,0,0.08)');hg.addColorStop(0.5,'rgba(0,0,0,0)');hg.addColorStop(0.8,'rgba(0,0,0,0.12)');hg.addColorStop(1,'rgba(0,0,0,0.62)');
  ctx.fillStyle=hg;ctx.fillRect(cx-0.3*Hg,G.gt,0.6*Hg,Hg);
  const strip=(f0,f1,al)=>{ctx.beginPath();for(let k=2;k<=46;k++){const y=k/48;ctx.lineTo(cx+GR(y)*Hg*f0,G.gb-y*Hg);}for(let k=46;k>=2;k--){const y=k/48;ctx.lineTo(cx+GR(y)*Hg*f1,G.gb-y*Hg);}ctx.closePath();
    const g=ctx.createLinearGradient(0,G.gb,0,G.gt);g.addColorStop(0,`rgba(255,255,255,0)`);g.addColorStop(0.35,`rgba(255,255,255,${al})`);g.addColorStop(0.8,`rgba(255,255,255,${al*0.6})`);g.addColorStop(1,'rgba(255,255,255,0)');ctx.fillStyle=g;ctx.fill();};
  strip(-0.66,-0.55,0.2);strip(-0.47,-0.43,0.08);strip(0.62,0.7,0.07);
  ctx.restore();
  ctx.strokeStyle='rgba(255,255,255,0.1)';ctx.lineWidth=1;globePath(ctx,G);ctx.stroke();
  // cap
  ctx.fillStyle=metal(ctx,cx-G.rcB,cx+G.rcB);frustum(ctx,cx,G.gt+G.hc*0.04,G.gt-G.hc,G.rcB,G.rcT,0.14);ctx.fill();
  ctx.fillStyle='rgba(0,0,0,0.3)';frustum(ctx,cx,G.gt+G.hc*0.04,G.gt-G.hc*0.06,G.rcB,G.rcB*0.97,0.14);ctx.fill();
}
// A room: dim wall lit by the lamp, a sideboard, the lamp. Returns the geometry.
function drawScene(ctx,W,H,o){
  const L=hex(LAVA[o.lava][1]),Wt=hex(WATER[o.water][1]),glowC=o.water===0?L:mix(Wt,L,0.35);
  const Hg=(o.scale||0.458)*H,baseY=H*(o.baseFrac||0.93),cx=(o.cx!==undefined?o.cx:W/2)+(o.drift||0),G=lampGeom(cx,baseY,Hg);
  const yBack=baseY-0.035*H,yFront=o.deepTable?H+1:baseY+0.025*H;
  const wg=ctx.createLinearGradient(0,0,0,yBack);wg.addColorStop(0,'#08070b');wg.addColorStop(1,'#120e15');ctx.fillStyle=wg;ctx.fillRect(0,0,W,yBack);
  const gy=G.gb-0.45*Hg,rg=ctx.createRadialGradient(cx,gy,0,cx,gy,1.7*Hg);rg.addColorStop(0,css(glowC,0.32));rg.addColorStop(0.45,css(glowC,0.1));rg.addColorStop(1,css(glowC,0));ctx.fillStyle=rg;ctx.fillRect(0,0,W,yBack);
  if(o.beforeLamp)o.beforeLamp(ctx,G);
  const tg=ctx.createLinearGradient(0,yBack,0,Math.min(H,yFront));tg.addColorStop(0,'#150f0b');tg.addColorStop(1,'#271a10');ctx.fillStyle=tg;ctx.fillRect(0,yBack,W,yFront-yBack);
  if(yFront<H){ctx.fillStyle='#0b0805';ctx.fillRect(0,yFront,W,H-yFront);ctx.fillStyle='rgba(255,220,180,0.08)';ctx.fillRect(0,yFront,W,1);}
  ctx.save();ctx.translate(cx,baseY);ctx.scale(1,0.09);const pg=ctx.createRadialGradient(0,0,0,0,0,1.3*Hg);pg.addColorStop(0,css(glowC,0.42));pg.addColorStop(1,css(glowC,0));ctx.fillStyle=pg;ctx.fillRect(-1.3*Hg,-1.3*Hg,2.6*Hg,2.6*Hg);ctx.restore();
  if(o.onTable)o.onTable(ctx,G);
  ctx.fillStyle='rgba(0,0,0,0.6)';ell(ctx,cx,baseY+G.rbB*0.03,G.rbB*1.06,G.rbB*0.13);
  drawLamp(ctx,G,o);if(o.afterLamp)o.afterLamp(ctx,G);return G;
}
let CLOCK_OVERRIDE=null;
window.setClock=function(s){CLOCK_OVERRIDE=s;if(window.__redraw)window.__redraw();};
function nowHHMM(){if(CLOCK_OVERRIDE)return CLOCK_OVERRIDE;const d=new Date();return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');}
// Live views: [{canvas, sim, opts, draw(ctx,W,H,opts)}]; one rAF loop steps every sim.
function runViews(views,onFrame){
  let last=performance.now();
  const frame=(now)=>{const dt=Math.min(0.05,Math.max(0,(now-last)/1000));last=now;
    for(const v of views){if(v.sim&&!v.frozen)stepSim(v.sim,dt);const ctx=v.canvas.getContext('2d');v.draw(ctx,v.canvas.width,v.canvas.height,v);}
    if(onFrame)onFrame();window.__ready=true;requestAnimationFrame(frame);};
  window.__redraw=()=>{for(const v of views){const ctx=v.canvas.getContext('2d');v.draw(ctx,v.canvas.width,v.canvas.height,v);}};
  window.__redraw();window.__ready=true;requestAnimationFrame(frame);
}
"""

BASE_CSS = """
:root{--bg:#0d0f12;--fg:#ece6da;--muted:#9aa0a6;--line:#2a2f36;--panel:#15181d;--accent:#e9b54a}
*{box-sizing:border-box}
body{margin:0;width:1440px;height:900px;overflow:hidden;background:var(--bg);color:var(--fg);font:14px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
header{display:flex;align-items:baseline;gap:14px;padding:14px 28px 10px;border-bottom:1px solid var(--line);background:var(--panel)}
header h1{margin:0;font-size:18px;font-weight:650}
header .sub{color:var(--muted);font-size:13px}
header .tag{margin-left:auto;font:600 11px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.04em;color:var(--muted);border:1px solid var(--line);border-radius:10px;padding:2px 8px}
.tv{position:absolute;background:#0a0a0a;border-radius:14px;padding:11px;box-shadow:0 0 0 1px #2b2b2b,0 10px 30px rgba(0,0,0,.6)}
.tv canvas{display:block;border-radius:3px}
.cap{position:absolute;font-size:13px;color:var(--fg)}
.cap b{color:var(--accent);font-weight:650}
.cap small{display:block;color:var(--muted);font-size:12px}
"""


def page(title, sub, body, script, extra_css=''):
    return f"""<!DOCTYPE html>
<!-- Plan mockup for docs/plans/2026-11-26-lava-lamp.md, generated by build_mockups.py. Self-contained; 1440x900. -->
<html lang="en"><head><meta charset="utf-8"><title>Mockup: {title}</title>
<style>{BASE_CSS}{extra_css}</style></head>
<body><header><h1>{title}</h1><span class="sub">{sub}</span><span class="tag">MOCKUP · NOT SHIPPED</span></header>
{body}
<script>{LAMP_JS}
{script}</script></body></html>
"""


# ----------------------------------------------------------------- lamp.html
LAMP_BODY = """
<div class="tv" style="left:34px;top:70px"><canvas id="tv" width="1024" height="576"></canvas></div>
<div id="marks"></div>
<div id="panel" style="position:absolute;left:1112px;top:70px;width:300px">
  <div class="h">Level settings <span class="m">· the LavaLampSettings object</span></div>
  <div id="form" tabindex="0">
    <div class="ttl">Level Settings</div>
    <div class="rail" id="rail"></div>
    <div id="rows"></div>
    <div class="hint" id="hint"></div>
    <div class="foot"><span>↑ ↓ select · ← → change</span><button id="apply">⇠ Apply / close</button></div>
  </div>
  <div class="h" style="margin-top:14px">Base close-up <span class="m">(the time, in starlight holes)</span></div>
  <canvas id="zoom" width="300" height="168" style="border-radius:8px;border:1px solid #2a2f36"></canvas>
  <div class="note">The level's own settings form: the TV and the phone open this over the scene. It's drawn beside the screen here so you can try it. Lava color and Water color live on its <i>Lava lamp</i> sheet; changes reach the scene on Apply.</div>
</div>
<div id="legend" style="position:absolute;left:34px;top:684px;width:1046px;columns:2;column-gap:36px;font-size:13px"></div>
"""
LAMP_CSS = """
#panel .h{font-weight:650;margin:2px 0 6px;font-size:13px;color:#d9d2c4}
#panel .m{color:var(--muted);font-weight:400}
#form{background:#172d27;color:#f0ead6;border-radius:6px;padding:10px 12px 10px;outline:none;font-family:system-ui,sans-serif;box-shadow:0 0 0 1px #24453b}
#form:focus{box-shadow:0 0 0 2px #e7c873}
#form .ttl{font-weight:650;font-size:15px;margin-bottom:8px}
#form .rail{display:flex;gap:4px;margin-bottom:8px}
#form .rail div{flex:1;text-align:center;font-size:12px;padding:4px 0;cursor:pointer;border-radius:3px}
#form .rail div.on{background:#213b31}
#form .row{display:flex;align-items:center;font-size:13px;padding:5px 6px;margin-bottom:3px;cursor:pointer;border-radius:3px}
#form .row.f{background:#4a7d52}
#form .row .v{margin-left:auto;display:flex;align-items:center;gap:6px}
#form .row .v i{display:inline-block;width:12px;height:12px;border-radius:50%;box-shadow:0 0 0 1px rgba(255,255,255,.35)}
#form .row button{all:unset;cursor:pointer;width:16px;text-align:center;color:#e7c873;visibility:hidden}
#form .row.f button{visibility:visible}
#form .hint{font-size:11px;color:#b9c2bb;min-height:30px;margin-top:4px}
#form .foot{display:flex;align-items:center;font-size:11px;color:#e7c873;margin-top:2px}
#form .foot button{all:unset;cursor:pointer;margin-left:auto;color:#f0ead6;font-size:12px;padding:2px 6px;border-radius:3px}
#form .foot button.dirty{background:#4a7d52}
.note{margin-top:10px;font-size:12px;color:var(--muted)}
.mk{position:absolute;width:22px;height:22px;border-radius:50%;background:var(--accent);color:#141006;font:700 12px/22px system-ui;text-align:center}
#legend p{margin:0 0 7px;break-inside:avoid}
#legend b{display:inline-block;width:20px;height:20px;border-radius:50%;background:var(--accent);color:#141006;text-align:center;font:700 11px/20px system-ui;margin-right:8px}
"""
LAMP_SCRIPT = r"""
// Applied values: what the level is running with. Pending: what the form shows until Apply.
const applied={lava:DEF_LAVA,water:DEF_WATER,drift:0,fps:0};
const pending=Object.assign({},applied);
const SHEETS=[
 ["Clock",[["drift","Camera drift",["Slow","Off"],"The camera drifts slowly so no pixel sits still on the screen; Off holds it still"]]],
 ["Lava lamp",[["lava","Lava color",LAVA.map(x=>x[0]),"Wax color while this level is loaded"],["water","Water color",WATER.map(x=>x[0]),"Liquid color while this level is loaded"]]],
 ["Display",[["fps","Show framerate",["Off","On"],"Show the frames per second overlay at the bottom right"]]]];
let sheet=1,row=0;
function renderForm(){
 document.getElementById('rail').innerHTML=SHEETS.map(([n],i)=>`<div class="${i===sheet?'on':''}" data-i="${i}">${n}</div>`).join('');
 const fields=SHEETS[sheet][1];
 document.getElementById('rows').innerHTML=fields.map(([k,label,opts],i)=>{const v=pending[k];const sw=k==='lava'?LAVA[v][1]:k==='water'?WATER[v][1]:null;
  return `<div class="row ${i===row?'f':''}" data-r="${i}">${label}<span class="v"><button data-d="-1">◀</button>${sw?`<i style="background:${sw}"></i>`:''}${opts[v]}<button data-d="1">▶</button></span></div>`;}).join('');
 document.getElementById('hint').textContent=fields[row][3];
 document.getElementById('apply').className=JSON.stringify(pending)!==JSON.stringify(applied)?'dirty':'';
}
function change(d){const [k,,opts]=SHEETS[sheet][1][row];pending[k]=(pending[k]+d+opts.length)%opts.length;renderForm();}
function apply(){Object.assign(applied,pending);renderForm();window.__redraw&&window.__redraw();}
document.getElementById('rail').onclick=e=>{const i=e.target.dataset.i;if(i!==undefined){sheet=+i;row=0;renderForm();}};
document.getElementById('rows').onclick=e=>{const b=e.target.closest('button'),r=e.target.closest('.row');if(r){row=+r.dataset.r;}if(b&&r&&r.classList.contains('f'))change(+b.dataset.d);else renderForm();};
document.getElementById('apply').onclick=apply;
document.getElementById('form').onkeydown=e=>{const n=SHEETS[sheet][1].length;
 if(e.key==='ArrowUp'){row=(row+n-1)%n;}else if(e.key==='ArrowDown'){row=(row+1)%n;}
 else if(e.key==='ArrowLeft'){change(-1);e.preventDefault();return;}else if(e.key==='ArrowRight'){change(1);e.preventDefault();return;}
 else if(e.key==='Enter'){apply();}else if(e.key==='Tab'){sheet=(sheet+(e.shiftKey?2:1))%3;row=0;}else return;
 e.preventDefault();renderForm();};
renderForm();
const sim=makeSim(7,8);let fpsShown=60,lastT=performance.now();
const views=[
 {canvas:document.getElementById('tv'),sim,draw:(ctx,W,H,v)=>{const now=performance.now(),dt=now-lastT;lastT=now;if(dt>0&&dt<200)fpsShown=fpsShown*0.95+0.05*(1000/dt);
   v.G=drawScene(ctx,W,H,{sim,lava:applied.lava,water:applied.water,time:nowHHMM(),cache:v.cache||(v.cache={}),drift:applied.drift?0:W*0.006*Math.sin(sim.t*2*Math.PI/600)});
   if(applied.fps){ctx.font='13px ui-monospace,monospace';const t=fpsShown.toFixed(1),w=ctx.measureText(t).width;ctx.fillStyle='rgba(0,0,0,.6)';ctx.fillRect(W-w-22,H-28,w+12,19);ctx.fillStyle='#fff';ctx.fillText(t,W-w-16,H-14);}}},
 {canvas:document.getElementById('zoom'),sim,frozen:true,draw:(ctx,W,H,v)=>{drawScene(ctx,W,H,{sim,lava:applied.lava,water:applied.water,time:nowHHMM(),cache:v.cache||(v.cache={}),scale:1.25,baseFrac:0.96});}}];
const LEG=[["Cap","conical metal cap; the top of the globe is the coolest place, where wax rests and cools before it sinks"],
["Glass","tapered globe, widest a quarter of the way up; painted highlight strips and darkened edges give the cylinder its volume"],
["Rising blob","heated wax stretches into a teardrop as it climbs, cools as it goes, then flattens against the top"],
["Liquid","lit from below: bright and warm over the bulb, deep and dark at the top. Its colour is the Water color setting"],
["Coil and pool","cold wax pools on the wire coil; when the pool is hot enough a tower rises and pinches off"],
["Starlight digits","the current local time, 24-hour, in the perforated gold base: lit holes spell HH:MM; the others glow faintly"],
["Wall glow","the lamp lights the wall in a mix of liquid and wax colour"],
["Sideboard","a pool of light at the foot of the lamp; nothing else in the room moves"]];
document.getElementById('legend').innerHTML=LEG.map(([t,d],i)=>`<p><b>${i+1}</b><strong>${t}</strong>: ${d}</p>`).join('');
let placed=false;
runViews(views,()=>{if(placed||!views[0].G)return;placed=true;const G=views[0].G,oy=81,x=1085;
 const ys=[G.gt-G.hc*0.5,G.gt+G.Hg*0.12,G.gb-G.Hg*0.55,G.gb-G.Hg*0.28,G.gb-G.Hg*0.03,G.baseY-G.hb*0.5];
 const m=document.getElementById('marks');ys.forEach((y,i)=>{const d=document.createElement('div');d.className='mk';d.style.left=x+'px';d.style.top=(oy+y-11)+'px';d.textContent=i+1;m.appendChild(d);});
 [[G.gb-G.Hg*1.2,7],[G.baseY+4,8]].forEach(([y,n])=>{const d=document.createElement('div');d.className='mk';d.style.left='6px';d.style.top=(oy+y-11)+'px';d.textContent=n;m.appendChild(d);});});
"""

# ------------------------------------------------------- time-options.html
OPTIONS = [
    (1, 'Starlight holes', 'Lit holes in the gold base spell HH:MM; the rest glow faintly, like the Astro’s starlight.', 4, 'S', True),
    (2, 'Shadow numerals', 'A frosted band glows from the bulb behind it; dark numerals sit in front.', 4, 'M', False),
    (3, 'Stencil cut-out', 'Numerals cut through the metal; bulb light shines straight out.', 5, 'S', False),
    (4, 'Nixie tubes', 'Four neon tubes behind a slot in the base: warm orange.', 5, 'M', False),
    (5, 'Split-flap', 'Solari flaps turn over at each minute.', 5, 'M', False),
    (6, 'Number drums', 'Odometer wheels roll the next minute into place.', 4, 'M', False),
    (7, 'VFD window', 'Cyan segments behind smoked glass, like 1970s hi-fi.', 5, 'S', False),
    (8, 'Bubble LEDs', 'Red seven-segment digits under bubble lenses (1970s calculator).', 4, 'S', False),
    (9, 'Turning band', 'An engraved 00–23 band turns past a notch; minutes run below.', 3, 'M', False),
    (10, '24-hour dial', 'One brass hand on a small 24-hour face, 00 at the top.', 3, 'S', False),
    (11, 'Edge-lit plates', 'Stacked engraved acrylic; the lit plate glows (a 1960s readout).', 4, 'M', False),
    (12, 'Maker’s plate', 'A small brass rating plate with a tiny reflective LCD.', 2, 'S', False),
    (13, 'Light on the table', 'The base throws the time onto the sideboard as light.', 3, 'M', False),
    (14, 'Socket timer', 'The cord runs to a 24-hour plug-in timer whose dial turns.', 2, 'M', False),
    (15, 'Flip clock', 'A 1960s flip clock sits beside the lamp.', 5, 'M', False),
    (16, 'Light on the wall', 'The time falls softly on the wall behind, big as the lamp.', 4, 'S', False),
    (17, 'Neon sign', 'A neon 24-hour sign glows on the wall nearby.', 5, 'S', False),
    (18, 'Cap band', 'Lit holes in the cap instead of the base.', 4, 'S', False),
    (19, 'Ghost digits', 'Pepper’s-ghost numerals float in the liquid; wax drifts through.', 3, 'M', False),
    (20, 'Screen text', 'Plain text in a corner, outside the scene.', 5, 'S', False),
]
OPT_CSS = """
#grid{position:absolute;left:24px;top:62px;display:grid;grid-template-columns:repeat(5,264px);gap:10px 16px}
.card{background:#14171b;border:1px solid #262b31;border-radius:9px;overflow:hidden;height:196px}
.card.rec{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.card canvas{display:block}
.card .t{padding:5px 9px 0;font-size:13px;font-weight:650;display:flex;gap:6px;align-items:baseline}
.card .t .n{color:var(--accent)}
.card .t .b{margin-left:auto;font:500 11px system-ui;color:var(--muted)}
.card .d{padding:1px 9px 0;font-size:11px;line-height:1.3;color:#b9b3a8}
"""
OPT_SCRIPT = r"""
const OPTS=__OPTS__;
const sim=makeSim(7,8);const T='21:47';
const DIG=n=>String(n).padStart(2,'0');
function band(G){return{yc:G.baseY-G.hb*0.5,rm:G.rbT+(G.rbB-G.rbT)*0.5};}
function close(ctx,W,H,extra){return drawScene(ctx,W,H,Object.assign({sim,lava:DEF_LAVA,water:DEF_WATER,time:T,holes:false,scale:1.25,baseFrac:0.95,cache:{}},extra||{}));}
function slot(ctx,G,w,h,fill){const {yc}=band(G);ctx.fillStyle=fill||'#0c0906';ctx.beginPath();ctx.roundRect(G.cx-w/2,yc-h/2,w,h,3);ctx.fill();ctx.strokeStyle='rgba(255,230,170,.35)';ctx.lineWidth=1;ctx.stroke();return{x:G.cx-w/2,y:yc-h/2};}
const SEG={'0':'abcdef','1':'bc','2':'abdeg','3':'abcdg','4':'bcfg','5':'acdfg','6':'acdefg','7':'abc','8':'abcdefg','9':'abcdfg','-':'g'};
const SP={a:[0,0,1,0],b:[1,0,1,.5],c:[1,.5,1,1],d:[0,1,1,1],e:[0,.5,0,1],f:[0,0,0,.5],g:[0,.5,1,.5]};
function seg7(ctx,str,x,y,h,on,off,glow){const w=h*.5,t=h*.12;let cx=x;ctx.lineCap='round';ctx.lineWidth=t;
 for(const ch of str){if(ch===':'){ctx.fillStyle=on;ell(ctx,cx+t,y+h*.3,t*.6,t*.6);ell(ctx,cx+t,y+h*.7,t*.6,t*.6);cx+=t*3;continue;}
  const s=SEG[ch]||'';for(const k of 'abcdefg'){const [x0,y0,x1,y1]=SP[k],o=s.includes(k);ctx.strokeStyle=o?on:off;ctx.shadowColor=on;ctx.shadowBlur=o?(glow||0):0;
   const ax=cx+x0*w,ay=y+y0*h,bx=cx+x1*w,by=y+y1*h,dx=(bx-ax),dy=(by-ay),l=Math.hypot(dx,dy),sx=dx/l*t*.8,sy=dy/l*t*.8;ctx.beginPath();ctx.moveTo(ax+sx,ay+sy);ctx.lineTo(bx-sx,by-sy);ctx.stroke();}
  ctx.shadowBlur=0;cx+=w+h*.28;}}
function txt(ctx,s,x,y,px,fill,o){o=o||{};ctx.save();ctx.font=(o.w||600)+' '+px+'px '+(o.f||'system-ui,sans-serif');ctx.textAlign=o.al||'center';ctx.textBaseline='middle';if(o.glow){ctx.shadowColor=o.gc||fill;ctx.shadowBlur=o.glow;}ctx.fillStyle=fill;ctx.fillText(s,x,y);ctx.restore();}
const D={
1:(c,W,H)=>close(c,W,H,{holes:true}),
2:(c,W,H)=>{const G=close(c,W,H),p=slot(c,G,96,30,null);const g=c.createRadialGradient(G.cx,p.y+15,2,G.cx,p.y+15,52);g.addColorStop(0,'#fff0cf');g.addColorStop(1,'#c99a52');c.fillStyle=g;c.beginPath();c.roundRect(p.x+1,p.y+1,94,28,3);c.fill();txt(c,T,G.cx,p.y+16,22,'rgba(45,25,6,.88)',{w:700,glow:2,gc:'rgba(0,0,0,.6)'});},
3:(c,W,H)=>{const G=close(c,W,H),{yc}=band(G);txt(c,T,G.cx,yc,26,'#ffe6b0',{w:800,glow:10,gc:'#ffb04a',f:'"DejaVu Sans Mono",monospace'});},
4:(c,W,H)=>{const G=close(c,W,H),p=slot(c,G,112,40);const ds=T.replace(':','');for(let k=0;k<4;k++){const x=p.x+6+k*26+(k>1?6:0);const g=c.createLinearGradient(x,0,x+22,0);g.addColorStop(0,'rgba(255,255,255,.05)');g.addColorStop(.3,'rgba(255,255,255,.18)');g.addColorStop(1,'rgba(255,255,255,.04)');c.fillStyle='#1a120c';c.beginPath();c.roundRect(x,p.y+3,22,34,9);c.fill();txt(c,'8',x+11,p.y+21,24,'rgba(255,120,40,.13)',{w:300});txt(c,ds[k],x+11,p.y+21,24,'#ffb067',{w:300,glow:7,gc:'#ff5a00'});c.fillStyle=g;c.beginPath();c.roundRect(x,p.y+3,22,34,9);c.fill();}c.fillStyle='#ff8a3a';ell(c,G.cx,p.y+15,1.6,1.6);ell(c,G.cx,p.y+26,1.6,1.6);},
5:(c,W,H)=>{const G=close(c,W,H),p=slot(c,G,112,38);const ds=T.replace(':','');for(let k=0;k<4;k++){const x=p.x+5+k*26+(k>1?4:0);c.fillStyle='#1d1d1f';c.beginPath();c.roundRect(x,p.y+3,23,32,2);c.fill();txt(c,ds[k],x+11.5,p.y+19.5,25,'#f4f1ea',{w:700});c.fillStyle='#000';c.fillRect(x,p.y+19,23,1.2);}},
6:(c,W,H)=>{const G=close(c,W,H),p=slot(c,G,112,38);const ds=T.replace(':','');c.save();c.beginPath();c.rect(p.x,p.y,112,38);c.clip();for(let k=0;k<4;k++){const x=p.x+5+k*26+(k>1?4:0);const g=c.createLinearGradient(0,p.y,0,p.y+38);g.addColorStop(0,'#141210');g.addColorStop(.5,'#ece4d2');g.addColorStop(1,'#141210');c.fillStyle=g;c.fillRect(x,p.y,23,38);const d=+ds[k];txt(c,String(d),x+11.5,p.y+19,20,'#201a12',{w:700});txt(c,String((d+9)%10),x+11.5,p.y+1,20,'rgba(32,26,18,.5)',{w:700});txt(c,String((d+1)%10),x+11.5,p.y+37,20,'rgba(32,26,18,.5)',{w:700});}c.restore();},
7:(c,W,H)=>{const G=close(c,W,H),p=slot(c,G,112,34,'#04201c');seg7(c,T,p.x+12,p.y+7,20,'#8fffe0','rgba(143,255,224,.08)',6);},
8:(c,W,H)=>{const G=close(c,W,H),p=slot(c,G,112,34,'#200406');seg7(c,T,p.x+12,p.y+8,18,'#ff3b30','rgba(255,59,48,.1)',4);for(let k=0;k<4;k++){const x=p.x+19+k*21+(k>1?6:0);const g=c.createRadialGradient(x-3,p.y+12,1,x,p.y+17,13);g.addColorStop(0,'rgba(255,255,255,.35)');g.addColorStop(.4,'rgba(255,255,255,.05)');g.addColorStop(1,'rgba(255,255,255,0)');c.fillStyle=g;ell(c,x,p.y+17,11,14);}},
9:(c,W,H)=>{const G=close(c,W,H),{yc,rm}=band(G);c.fillStyle='rgba(40,28,8,.55)';c.fillRect(G.cx-rm,yc-20,rm*2,40);[[yc-9,[19,20,21,22,23],21,14],[yc+10,[45,46,47,48,49],47,11]].forEach(([y,list,cur,px])=>{list.forEach((n,i)=>{const a=(i-2)*0.42,x=G.cx+rm*Math.sin(a);c.save();c.translate(x,y);c.scale(Math.cos(a),1);txt(c,DIG(n),0,0,px,n===cur?'#2a1c06':'rgba(42,28,6,.55)',{w:800});c.restore();});});c.fillStyle='#fff0b8';c.beginPath();c.moveTo(G.cx-5,yc-21);c.lineTo(G.cx+5,yc-21);c.lineTo(G.cx,yc-16);c.fill();},
10:(c,W,H)=>{const G=close(c,W,H),{yc}=band(G),R=22;c.fillStyle='#8a6420';ell(c,G.cx,yc,R+3,R+3);c.fillStyle='#efe6d0';ell(c,G.cx,yc,R,R);c.strokeStyle='#3a2a10';for(let k=0;k<24;k++){const a=k/24*2*Math.PI;c.lineWidth=k%6?0.8:1.6;c.beginPath();c.moveTo(G.cx+Math.sin(a)*R*.82,yc-Math.cos(a)*R*.82);c.lineTo(G.cx+Math.sin(a)*R*.95,yc-Math.cos(a)*R*.95);c.stroke();}['00','06','12','18'].forEach((s,i)=>{const a=i/4*2*Math.PI;txt(c,s,G.cx+Math.sin(a)*R*.62,yc-Math.cos(a)*R*.62,7,'#3a2a10',{w:700});});const a=(21+47/60)/24*2*Math.PI;c.strokeStyle='#1a1205';c.lineWidth=2;c.beginPath();c.moveTo(G.cx,yc);c.lineTo(G.cx+Math.sin(a)*R*.8,yc-Math.cos(a)*R*.8);c.stroke();c.fillStyle='#8a6420';ell(c,G.cx,yc,2.4,2.4);},
11:(c,W,H)=>{const G=close(c,W,H),p=slot(c,G,104,34,'#05080b');c.save();c.font='600 24px system-ui';c.textAlign='center';c.textBaseline='middle';c.strokeStyle='rgba(200,230,255,.12)';c.lineWidth=1;c.strokeText('88:88',G.cx+1.5,p.y+18);c.strokeText('88:88',G.cx-1.5,p.y+16);c.restore();txt(c,T,G.cx,p.y+17,24,'#d6f1ff',{glow:9,gc:'#7cc8ff'});},
12:(c,W,H)=>{const G=close(c,W,H),{yc}=band(G);c.fillStyle='#c79a40';c.beginPath();c.roundRect(G.cx-44,yc-17,88,34,3);c.fill();c.fillStyle='#5a4012';ell(c,G.cx-40,yc-13,1.4,1.4);ell(c,G.cx+40,yc-13,1.4,1.4);ell(c,G.cx-40,yc+13,1.4,1.4);ell(c,G.cx+40,yc+13,1.4,1.4);txt(c,'MODEL 63 · 240 V ~ 40 W',G.cx,yc-9,6.5,'#3a2a0c',{w:700});c.fillStyle='#9fae8c';c.fillRect(G.cx-22,yc-3,44,15);seg7(c,T,G.cx-18,yc-1,10,'#1d2418','rgba(29,36,24,.08)');},
13:(c,W,H)=>drawScene(c,W,H,{sim,lava:DEF_LAVA,water:DEF_WATER,time:T,holes:false,scale:0.27,baseFrac:0.55,deepTable:true,cache:{},onTable:(cc,G)=>{cc.save();cc.globalCompositeOperation='lighter';cc.translate(G.cx,G.baseY+(H-G.baseY)*0.5);cc.scale(1,0.36);txt(cc,T,0,0,66,'rgba(255,214,150,.42)',{w:800,glow:16,gc:'rgba(255,180,90,.8)'});cc.restore();}}),
14:(c,W,H)=>{const G=drawScene(c,W,H,{sim,lava:DEF_LAVA,water:DEF_WATER,time:T,holes:false,scale:0.4,cx:W*0.36,cache:{}});const x=W*0.8,y=G.baseY-0.035*H-30;c.strokeStyle='#1c1612';c.lineWidth=2.4;c.beginPath();c.moveTo(G.cx+G.rbB*0.7,G.baseY-2);c.bezierCurveTo(G.cx+80,G.baseY+8,x-30,G.baseY+4,x,y+24);c.stroke();c.fillStyle='#5b554c';c.beginPath();c.roundRect(x-26,y-26,52,52,6);c.fill();const R=18,rot=-(21+47/60)/24*2*Math.PI;c.fillStyle='#d9d2c2';ell(c,x,y,R,R);for(let k=0;k<48;k++){const a=k/48*2*Math.PI+rot,on=(k>=36&&k<46);c.fillStyle=on?'#c0392b':'#8d877c';c.save();c.translate(x+Math.sin(a)*R*.9,y-Math.cos(a)*R*.9);c.rotate(a);c.fillRect(-1,-2.6,2,5.2);c.restore();}['00','06','12','18'].forEach((s,i)=>{const a=i/4*2*Math.PI+rot;txt(c,s,x+Math.sin(a)*R*.52,y-Math.cos(a)*R*.52,6,'#2b2620',{w:700});});c.fillStyle='#f4efe4';c.beginPath();c.moveTo(x-4,y-R-6);c.lineTo(x+4,y-R-6);c.lineTo(x,y-R+1);c.fill();},
15:(c,W,H)=>{const G=drawScene(c,W,H,{sim,lava:DEF_LAVA,water:DEF_WATER,time:T,holes:false,scale:0.4,cx:W*0.34,cache:{}});const x=W*0.73,y=G.baseY;c.fillStyle='#e8661a';c.beginPath();c.roundRect(x-40,y-40,80,40,12);c.fill();c.fillStyle='rgba(255,255,255,.18)';c.fillRect(x-36,y-37,72,4);[[x-17,'21'],[x+17,'47']].forEach(([cx,s])=>{c.fillStyle='#161616';c.beginPath();c.roundRect(cx-15,y-33,30,26,2);c.fill();txt(c,s,cx,y-19.5,17,'#f2efe8',{w:700});c.fillStyle='#000';c.fillRect(cx-15,y-20.5,30,1);});},
16:(c,W,H)=>drawScene(c,W,H,{sim,lava:DEF_LAVA,water:DEF_WATER,time:T,holes:false,scale:0.42,cache:{},beforeLamp:(cc,G)=>{cc.save();cc.globalCompositeOperation='lighter';txt(cc,T,G.cx-W*0.27,G.gb-G.Hg*0.7,46,'rgba(255,190,140,.22)',{w:800,glow:22,gc:'rgba(255,170,110,.6)'});cc.restore();}}),
17:(c,W,H)=>drawScene(c,W,H,{sim,lava:DEF_LAVA,water:DEF_WATER,time:T,holes:false,scale:0.42,cx:W*0.4,cache:{},beforeLamp:(cc,G)=>{cc.save();cc.font='italic 400 36px "DejaVu Sans",sans-serif';cc.textAlign='center';cc.textBaseline='middle';cc.strokeStyle='#ff4fd8';cc.lineWidth=3.2;cc.shadowColor='#ff3fd0';cc.shadowBlur=14;cc.strokeText(T,W*0.78,H*0.34);cc.shadowBlur=0;cc.strokeStyle='#ffe8fb';cc.lineWidth=1;cc.strokeText(T,W*0.78,H*0.34);cc.restore();}}),
18:(c,W,H)=>{const Hg=H*1.5,hb=0.56*Hg,hc=0.36*Hg,baseY=H*0.52+hb+Hg+hc*0.5;const G=drawScene(c,W,H,{sim,lava:DEF_LAVA,water:DEF_WATER,time:T,holes:false,scale:Hg/H,baseFrac:baseY/H,cache:{}});const rAt=y=>G.rcB+(G.rcT-G.rcB)*((G.gt-y)/G.hc);drawHoleBand(c,G.cx,G.gt-G.hc*0.78,G.gt-G.hc*0.22,rAt,T,'',1.0);},
19:(c,W,H)=>{const Hg=H*1.7,hb=0.56*Hg,baseY=H*0.5+Hg*0.5+hb;drawScene(c,W,H,{sim,lava:DEF_LAVA,water:DEF_WATER,time:T,holes:false,scale:Hg/H,baseFrac:baseY/H,ghost:T,cache:{}});},
20:(c,W,H)=>{drawScene(c,W,H,{sim,lava:DEF_LAVA,water:DEF_WATER,time:T,holes:false,scale:0.42,cache:{}});txt(c,T,W-30,18,15,'rgba(255,255,255,.88)',{w:500});}
};
const grid=document.getElementById('grid');
OPTS.forEach(([n,name,desc,leg,cost,rec])=>{const card=document.createElement('div');card.className='card'+(rec?' rec':'');
 card.innerHTML=`<canvas width="264" height="138"></canvas><div class="t"><span class="n">${n}</span>${name}${rec?' <span style="color:var(--accent)">★</span>':''}<span class="b">${'●'.repeat(leg)}${'○'.repeat(5-leg)} · ${cost}</span></div><div class="d">${desc}</div>`;
 grid.appendChild(card);const cv=card.querySelector('canvas');D[n](cv.getContext('2d'),cv.width,cv.height);});
window.__ready=true;
"""

# ---------------------------------------------------------- palettes.html
PAL_CSS = """
#pal{position:absolute;left:24px;top:60px}
#pal table{border-collapse:separate;border-spacing:6px 5px}
#pal th{font-size:12px;font-weight:600;color:#cfc8ba;text-align:center;padding:0}
#pal th.r{text-align:right;padding-right:6px;width:80px}
#pal td{padding:0;position:relative;border-radius:6px;overflow:hidden;border:1px solid #23272d}
#pal td.def{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
#pal td canvas{display:block}
#pal td .k{position:absolute;left:4px;top:3px;font:700 10px system-ui;color:#fff;background:rgba(0,0,0,.55);border-radius:7px;padding:0 5px}
#pal td .lc,#key .lc{display:inline-block;width:11px;height:11px;border-radius:50%;border:1.5px solid #ffd77a;background:linear-gradient(90deg,#ffd77a 50%,transparent 50%)}#pal td .lc{position:absolute;right:5px;top:5px}
#pal i.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px;vertical-align:-1px}
#key{position:absolute;left:1196px;top:64px;width:212px;font-size:12px;color:#c9c2b4}
#key p{margin:0 0 6px}
#key b{color:#fff}
"""
PAL_SCRIPT = r"""
const NAMED={'4,1':[1,'Violet / Orange: Astro Gold pairing'],'1,0':[2,'Yellow / Red: original Astro'],'5,0':[3,'Blue / Red: original Astro'],'1,7':[4,'Yellow / White: original Astro'],'5,7':[5,'Blue / White: original Astro'],'4,0':[6,'Violet / Red'],'5,3':[7,'Blue / Pink'],'4,5':[8,'Violet / Turquoise'],'5,6':[9,'Blue / Green'],'1,1':[10,'Yellow / Orange'],'0,2':[11,'Clear / Yellow']};
const LOW=new Set(['1,2','2,1','3,3','6,5','7,6','0,7','2,2']);
const sim=makeSim(7,8);
let h='<table><tr><th></th>'+WATER.map(([n,c])=>`<th><i class="dot" style="background:${c}"></i>${n}</th>`).join('')+'</tr>';
LAVA.forEach(([ln,lc],li)=>{h+=`<tr><th class="r"><i class="dot" style="background:${lc}"></i>${ln}</th>`;WATER.forEach((w,wi)=>{const key=wi+','+li,nm=NAMED[key];h+=`<td class="${li===DEF_LAVA&&wi===DEF_WATER?'def':''}"><canvas width="122" height="86" data-l="${li}" data-w="${wi}"></canvas>${nm?`<span class="k">${nm[0]}</span>`:''}${LOW.has(key)?'<span class="lc" title="low contrast"></span>':''}</td>`;});h+='</tr>';});
document.getElementById('pal').innerHTML=h+'</table>';
document.querySelectorAll('#pal canvas').forEach(cv=>{drawScene(cv.getContext('2d'),cv.width,cv.height,{sim,lava:+cv.dataset.l,water:+cv.dataset.w,time:'21:47',cache:{},scale:0.47});});
document.getElementById('key').innerHTML='<p><b>Rows</b> lava color · <b>columns</b> water color. Gold outline: the default, <b>Orange in Violet</b>.</p><p><b>Numbered</b>: real pairings, written liquid / lava as Mathmos does. 1 is the Astro Gold listing; 2–5 the original Astro (“red or white lava in yellow or blue liquid”); 6–11 current or recent Mathmos colourways. Sources in the plan.</p>'+Object.values(NAMED).sort((a,b)=>a[0]-b[0]).map(([n,t])=>`<p>${n} · ${t}</p>`).join('')+'<p><span class="lc"></span> low contrast: allowed (it is the viewer’s choice), shown so the gamut is honest.</p>';
window.__ready=true;
"""

# ---------------------------------------------------------- settings.html
SET_CSS = """
.ov{position:absolute;inset:0;background:#060d14;font-family:system-ui,sans-serif}
.ov .pnl{position:absolute;left:9.4%;top:10.2%;width:81.2%;height:75.9%;background:#172d27;color:#f0ead6}
.ov h2{margin:0;position:absolute;left:3%;top:5%;font-size:1.0em;font-weight:650}
.ov .rail{position:absolute;left:3%;top:20%;width:21%}
.ov .rail div{background:transparent;padding:.35em .6em;margin-bottom:.25em;font-size:.82em}
.ov .rail div.on{background:#213b31}
.ov .rows{position:absolute;left:27%;top:20%;width:70%}
.ov .rows div{padding:.35em .6em;margin-bottom:.25em;font-size:.84em}
.ov .rows div.f{background:#4a7d52}
.ov .hint{position:absolute;left:27%;bottom:15%;font-size:.7em;color:#b9c2bb}
.ov .foot{position:absolute;left:3%;bottom:6%;right:3%;font-size:.7em;color:#e7c873;display:flex;gap:1.4em}
.ov .foot span:last-child{margin-left:auto;color:#f0ead6}
#tbl{position:absolute;left:764px;top:520px;width:648px;font-size:12.5px;border-collapse:collapse}
#tbl th,#tbl td{border-bottom:1px solid #262b31;padding:6px 8px;text-align:left;vertical-align:top}
#tbl th{color:#cfc8ba;font-weight:650}
#tbl code{font:12px ui-monospace,monospace;color:#e9d9b0}
.phone{position:absolute;background:#0b0b0c;border-radius:30px;padding:12px 26px;box-shadow:0 0 0 1px #333,0 10px 30px rgba(0,0,0,.6)}
"""
SET_BODY = """
<div class="tv" style="left:34px;top:70px"><div style="position:relative;width:680px;height:383px;font-size:21px;overflow:hidden;border-radius:3px">
 <div class="ov"><div class="pnl"><h2>Level Settings</h2>
 <div class="rail"><div>Clock</div><div class="on">Lava lamp</div><div>Display</div></div>
 <div class="rows"><div class="f">Lava color: Orange</div><div>Water color: Violet</div></div>
 <div class="hint">Wax color while this level is loaded</div>
 <div class="foot"><span>Up / down: select</span><span>Left / right: change</span><span>⇠&nbsp; Apply / close</span></div></div></div></div></div>
<div class="cap" style="left:40px;top:478px"><b>1 · TV, settings open.</b> The new <i>Lava lamp</i> sheet sits between the shared Clock and Display sheets.<small>Left / right steps through the eight names; the scene behind updates when you apply.</small></div>
<div class="tv" style="left:730px;top:70px"><canvas id="after" width="680" height="383"></canvas></div>
<div class="cap" style="left:736px;top:478px"><b>2 · After Apply: Lava Red, Water Yellow.</b> Wax, liquid, wall glow and the light pool all follow.<small>Live: the same renderer and wax model as the main mockup.</small></div>
<div class="phone" style="left:40px;top:560px"><div style="position:relative;width:620px;height:279px;font-size:17px;overflow:hidden;border-radius:4px">
 <div class="ov"><div class="pnl"><h2>Level Settings</h2>
 <div class="rail"><div>Clock</div><div class="on">Lava lamp</div><div>Display</div></div>
 <div class="rows"><div>Lava color: Orange</div><div class="f">Water color: Turquoise</div></div>
 <div class="hint">Liquid color while this level is loaded</div>
 <div class="foot"><span>Tap a row · tap again to change</span><span>⇠&nbsp; Apply / close</span></div></div></div></div></div>
<div class="cap" style="left:730px;top:478px;display:none"></div>
<table id="tbl"><tr><th>Sheet</th><th>Field</th><th>Choices</th><th>Default</th></tr>
<tr><td>Lava lamp</td><td><code>Lava color</code></td><td>Red · Orange · Yellow · Pink · Purple · Turquoise · Green · White</td><td>Orange</td></tr>
<tr><td>Lava lamp</td><td><code>Water color</code></td><td>Clear · Yellow · Orange · Pink · Violet · Blue · Turquoise · Green</td><td>Violet</td></tr>
<tr><td>Clock (shared)</td><td><code>Camera drift</code></td><td>Slow · Off</td><td>Slow</td></tr>
<tr><td>Display (global)</td><td><code>Show framerate</code></td><td>Off · On</td><td>Off</td></tr>
<tr><td colspan="4" style="color:#9aa0a6">3 · Phone (left): the existing touch form, drawn from the same catalog; this plan adds fields, not widgets. The phone frame shows the narrow layout with the second field focused.</td></tr></table>
"""
SET_SCRIPT = r"""
const sim=makeSim(7,8);
runViews([{canvas:document.getElementById('after'),sim,draw:(ctx,W,H,v)=>drawScene(ctx,W,H,{sim,lava:0,water:1,time:nowHHMM(),cache:v.cache||(v.cache={})})}]);
"""

# ------------------------------------------------------------ states.html
ST_BODY = """
<div class="tv" style="left:34px;top:66px"><canvas id="s1" width="640" height="360"></canvas></div>
<div class="cap" style="left:40px;top:452px"><b>Running.</b> Local time 21:47, Orange in Violet (defaults). Camera drift Slow.<small>The level opens mid-flow: about 150 s of model time runs at load.</small></div>
<div class="tv" style="left:730px;top:66px"><canvas id="s2" width="520" height="292"></canvas></div>
<canvas id="s2a" width="138" height="78" style="position:absolute;left:1276px;top:80px;border-radius:6px;border:1px solid #2a2f36"></canvas>
<canvas id="s2b" width="138" height="78" style="position:absolute;left:1276px;top:204px;border-radius:6px;border:1px solid #2a2f36"></canvas>
<div class="cap" style="left:1276px;top:160px;font-size:12px">23:59:59</div><div class="cap" style="left:1276px;top:284px;font-size:12px">00:00:00</div>
<div class="cap" style="left:736px;top:384px;width:660px"><b>Minute change, 23:59 → 00:00.</b> The holes switch at the boundary; the wax ignores the clock entirely.<small>Tested at 09:59 → 10:00 and 23:59 → 00:00 with WF_WALL_CLOCK on the desktop.</small></div>
<div class="tv" style="left:34px;top:500px"><canvas id="s3" width="560" height="315"></canvas></div>
<div class="cap" style="left:40px;top:838px;width:660px"><b>Clock not set.</b> WALL_DAY says the device clock predates 2026-01-01: the base shows dim dashes, the lamp runs on.</div>
<div class="tv" style="left:730px;top:470px"><canvas id="s4" width="430" height="323"></canvas></div>
<div class="tv" style="left:1196px;top:430px"><canvas id="s5" width="208" height="370"></canvas></div>
<div class="cap" style="left:736px;top:838px;width:680px"><b>Narrow.</b> 4:3 tablet and 9:16 phone portrait: the lamp keeps its height and the room crops at the sides.</div>
"""
ST_SCRIPT = r"""
const mk=(id,seed,o)=>{const sim=makeSim(seed,8);return{canvas:document.getElementById(id),sim,draw:(ctx,W,H,v)=>drawScene(ctx,W,H,Object.assign({sim,lava:DEF_LAVA,water:DEF_WATER,cache:v.cache||(v.cache={})},typeof o==='function'?o():o))};};
const z=(id,t)=>{const s=makeSim(5,8);return{canvas:document.getElementById(id),sim:s,frozen:true,draw:(ctx,W,H,v)=>drawScene(ctx,W,H,{sim:s,lava:DEF_LAVA,water:DEF_WATER,time:t,cache:v.cache||(v.cache={}),scale:1.25,baseFrac:0.96})};};
runViews([mk('s1',7,{time:'21:47'}),mk('s2',3,{time:'00:00'}),z('s2a','23:59'),z('s2b','00:00'),mk('s3',9,{time:null,mode:'dim'}),mk('s4',13,{time:'21:47'}),mk('s5',21,{time:'21:47',scale:0.42,baseFrac:0.9})]);
"""

# ------------------------------------------------------------ poster.html
POSTER_CSS = """
#sheet{position:absolute;left:34px;top:58px;width:1123px;height:1587px;transform:scale(.5293);transform-origin:0 0;background:#f4ede0;color:#1d1712;font:15px/1.42 "DejaVu Serif",Georgia,serif;box-shadow:0 8px 30px rgba(0,0,0,.6)}
#sheet h1{font:800 64px/1 "DejaVu Sans",system-ui,sans-serif;letter-spacing:-.01em;margin:0}
#sheet .kick{font:600 16px "DejaVu Sans",sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#a04a12}
#sheet h2{font:700 19px "DejaVu Sans",sans-serif;margin:0 0 6px;color:#2b1d12}
#sheet h2 .n{color:#c2581a;margin-right:6px}
#sheet p{margin:0 0 7px}
#sheet .small{font-size:12.5px;color:#4b4036}
#sheet .chip{display:inline-block;font:700 10px "DejaVu Sans",sans-serif;letter-spacing:.03em;border-radius:8px;padding:0 6px;margin-left:4px;vertical-align:2px}
#sheet .v{background:#2f6b45;color:#fff}#sheet .o{background:#b07a1c;color:#fff}#sheet .u{background:#5a4bb0;color:#fff}
#sheet .pnl{position:absolute;background:#fbf6ec;border:1px solid #dccfb8;border-radius:10px;padding:14px 16px}
#sheet pre{font:12.6px/1.38 "DejaVu Sans Mono",monospace;background:#211a14;color:#f1e3c8;border-radius:8px;padding:10px 12px;margin:6px 0;white-space:pre}
#sheet pre .c{color:#a99a80}
#sheet table{border-collapse:collapse;width:100%;font-size:12.5px}
#sheet td,#sheet th{border-bottom:1px solid #e1d5bf;padding:2.5px 5px;text-align:left;vertical-align:top}
#sheet th{font:700 12px "DejaVu Sans",sans-serif;color:#5a4a3a}
#sheet a{color:#8a3b0c;text-decoration:none;border-bottom:1px dotted #8a3b0c}
#notes{position:absolute;left:652px;top:58px;width:762px;font-size:13px;color:#cfc8ba}
#notes h3{margin:0 0 6px;font-size:14px;color:#fff}
#notes p{margin:0 0 9px}
#notes .ch{display:inline-block;font:700 10px system-ui;border-radius:8px;padding:0 6px;color:#fff}
"""
POSTER_BODY = r"""
<div id="sheet">
 <div style="position:absolute;left:44px;top:38px;width:700px"><div class="kick">World Foundry · 3D Clocks · A3 poster</div><h1>The lava lamp</h1>
 <p style="font-size:19px;margin-top:10px;color:#4a3a2c">Two liquids that will not mix, one light bulb, and a density that changes with heat: a slow convection engine, and a clock built around it.</p></div>
 <canvas id="hero" width="330" height="510" style="position:absolute;left:770px;top:32px;border-radius:12px"></canvas>
 <div class="pnl" style="left:44px;top:200px;width:700px;height:342px"><h2><span class="n">01</span>How it moves</h2>
  <svg id="cycle" width="668" height="196" viewBox="0 0 668 196"></svg>
  <p>The bulb warms the wax pooled on the coil. Wax expands more than the liquid, so above some temperature it is the lighter of the two and rises <span class="chip v">verified [1]</span>. Near the cool top it gives up heat, grows denser and sinks; the coil breaks the surface tension of returning blobs so they merge again <span class="chip v">verified [1]</span>. Fluid dynamicists file it as a form of Rayleigh–Taylor instability <span class="chip v">verified [1]</span>.</p></div>
 <div class="pnl" style="left:44px;top:556px;width:508px;height:300px"><h2><span class="n">02</span>What is in the bottle</h2>
  <div style="display:flex;gap:12px"><svg id="dens" width="190" height="150" viewBox="0 0 190 150" style="flex:none"></svg>
  <table><tr><th>Ingredient</th><th>Property</th></tr>
  <tr><td>Paraffin wax</td><td>≈ 0.9 g/cm³; melts at 46–68 °C by grade <span class="chip v">verified [2]</span></td></tr>
  <tr><td>On melting</td><td>volume grows up to ≈ 10 % <span class="chip o">other source [3]</span></td></tr>
  <tr><td>CCl₄</td><td>≈ 60 % denser than water; once added to weigh the wax down; out of US lamps since 1970 <span class="chip v">verified [1]</span></td></tr>
  <tr><td>Today</td><td>the formula is a trade secret <span class="chip v">verified [1]</span></td></tr></table></div>
  <p class="small" style="margin-top:6px">The curves are schematic: the crossing is the point, not the numbers.</p></div>
 <div class="pnl" style="left:572px;top:556px;width:508px;height:300px"><h2><span class="n">03</span>Time in the base</h2>
  <div style="display:flex;gap:12px"><canvas id="baseZoom" width="230" height="150" style="border-radius:8px;flex:none"></canvas>
  <div><p>The 1963 Astro’s gold base was pierced with small holes that glowed like starlight <span class="chip o">other source [5]</span>.</p><p>Ours spell the local time, 24-hour, on a 29 × 9 grid: the digits bright, every other hole a faint glow.</p></div></div>
  <p class="small" style="margin-top:8px">The wax is not the clock and never knows the time. Only the holes change, once a minute.</p></div>
 <div class="pnl" style="left:44px;top:870px;width:1036px;height:258px"><h2><span class="n">04</span>Patents <span class="chip v">verified [4]</span></h2>
  <table><tr><th style="width:120px">Number</th><th>What</th><th style="width:250px">Dates</th></tr>
  <tr><td><a href="https://patents.google.com/patent/GB703924A/en">GB 703,924</a></td><td>Donald Dunnet: a lamp-heated display of liquid bubbles rising through another liquid</td><td>filed 1950‑12‑21 · published 1954‑02‑10</td></tr>
  <tr><td><a href="https://patents.google.com/patent/US3387396A/en">US 3,387,396</a></td><td>David George Smith for Crestworth Ltd: “Display devices”, the lava lamp’s US patent</td><td>priority 1964‑03‑18 · granted 1968‑06‑11</td></tr>
  <tr><td><a href="https://patents.google.com/patent/US3689139A/en">US 3,689,139</a></td><td>Alexander Gross: optical projector (cites Dunnet)</td><td>granted 1972‑09‑05</td></tr>
  <tr><td><a href="https://patents.google.com/patent/US3777379A/en">US 3,777,379</a></td><td>W. Lewellen: aesthetic fluid suspension and its preparation</td><td>granted 1973‑12‑11</td></tr>
  <tr><td><a href="https://patents.google.com/patent/US4057921A/en">US 4,057,921</a></td><td>Derek William Ball: decorative device</td><td>granted 1977‑11‑15</td></tr>
  <tr><td><a href="https://patents.google.com/patent/US5732138A/en">US 5,732,138</a></td><td>Silicon Graphics (Noll, Mende, Sisodiya): random-number seeds from a chaotic system, the Lavarand</td><td>filed 1996‑01‑29 · granted 1998‑03‑24</td></tr></table>
  </div>
 <div class="pnl" style="left:44px;top:1140px;width:1036px;height:136px"><h2><span class="n">05</span>A short history</h2><svg id="tl" width="1004" height="90" viewBox="0 0 1004 90"></svg></div>
 <div class="pnl" style="left:44px;top:1288px;width:620px;height:250px"><h2><span class="n">06</span>Forth that moves the wax <span class="chip u">ours</span></h2>
<pre><span class="c">\ One blob, one step; state in its local mailboxes</span>
: blob@ ( box blob -- v )  read-actor-mailbox ;
: blob! ( v box blob -- )  write-actor-mailbox ;
<span class="c">\ the liquid: a hot layer over the coil</span>
: env  ( y -- T )  dup 0.08 / negate exp  0.75 *  0.3 +  swap 0.08 * - ;
<span class="c">\ exact Newton cooling over dt</span>
: cool ( T target k dt -- T' )
  * negate expm1 negate  >r  over -  r> *  + ;
: buoy ( T -- a )  0.6 -  0.55 * ;</pre>
  <p class="small">A sketch. Phase 3 writes the real words and checks them step for step against the Python model. <code>exp</code> and <code>expm1</code> are new engine words.</p></div>
 <div class="pnl" style="left:684px;top:1288px;width:396px;height:250px"><h2><span class="n">07</span>Four ways to move it</h2>
  <table><tr><th></th><th>Approach</th><th>Cost</th></tr>
  <tr><td>✓</td><td><b>Forth model</b>: buoyancy, heat and pooling in the level script</td><td>small</td></tr>
  <tr><td></td><td><b>Baked tape</b>: a long run computed in Python, played back</td><td>data</td></tr>
  <tr><td></td><td><b>Native word</b>: a C++ simulator behind one word</td><td>engine</td></tr>
  <tr><td></td><td><b>Jolt</b>: rigid spheres pushed by buoyancy</td><td>heavy</td></tr></table>
  <p class="small" style="margin-top:4px">Shapes are morph targets: teardrop, drop, pancake, neck.</p></div>
 <div style="position:absolute;left:44px;top:1546px;width:1036px;font:11px/1.35 'DejaVu Sans',sans-serif;color:#5a4d40">[1] Wikipedia, “Lava lamp”, citing US 3,387,396 and the US EPA. [2] Wikipedia, “Paraffin wax”. [3] Schimmelpfennig et al., dip-tube volume measurements of paraffins. [4] Google Patents, each number above. [5] Retail and encyclopedia descriptions of the Astro; the research document must pin a primary source before print. Chips: <b style="color:#2f6b45">verified</b> · <b style="color:#b07a1c">other source</b> · <b style="color:#5a4bb0">ours</b>. A3 portrait · 297 × 420 mm.</div>
</div>
<div id="notes">
 <h3>A3 poster, drawn at print size and scaled to fit</h3>
 <p>A layout draft on real, sourced text. The finished poster uses the repository's poster pipeline (Phase P): first a research document (<code>docs/reference/lava-lamp-research.md</code>), then <code>make_poster.py</code> and <code>export_poster.py</code>. These produce one 297 × 420 mm PDF page, a 300 DPI PNG and <code>layout-review.json</code>, guarded by a pytest.</p>
 <p>Every printed claim carries a chip: <span class="ch" style="background:#2f6b45">verified</span> (checked against the cited source), <span class="ch" style="background:#b07a1c">other source</span> (a secondary or retail source, which the research document must confirm or cut) or <span class="ch" style="background:#5a4bb0">ours</span> (our model or design). <code>make_poster.py</code> refuses to build if any claim is unconfirmed.</p>
 <p>The hero image on the sheet is this mockup's canvas lamp. The print uses a Cycles render of the shipped Blender scene, as the aquarium posters do.</p>
 <p>The patent table links each number to Google Patents. The PDF keeps the links, and the print adds a QR code per row (Q8).</p>
 <p>Panel 05 runs from Dunnet's 1950 filing to Cloudflare's wall of about 100 lamps in 2017. Events are spaced evenly, not to scale.</p>
 <p>Q7 asks whether the timeline should mention that Craven Walker also directed <i>Travelling Light</i> (1959), the first naturist film released publicly in the UK.</p>
 <p>Panel 06 is the movement code. Panel 07 lists the four ways to move the wax that the plan weighs (D6); the Forth model is ticked as recommended.</p>
</div>
"""
POSTER_SCRIPT = r"""
const sim=makeSim(7,8);
drawScene(document.getElementById('hero').getContext('2d'),330,510,{sim,lava:DEF_LAVA,water:DEF_WATER,time:'21:47',cache:{},scale:0.5,baseFrac:0.95});
drawScene(document.getElementById('baseZoom').getContext('2d'),230,150,{sim,lava:DEF_LAVA,water:DEF_WATER,time:'21:47',cache:{},scale:1.3,baseFrac:0.97});
const S=(id,h)=>document.getElementById(id).innerHTML=h;
const T=(x,y,s,o)=>`<text x="${x}" y="${y}" font-family="DejaVu Sans,sans-serif" font-size="${(o&&o.fs)||13}" fill="${(o&&o.c)||'#2b1d12'}" text-anchor="${(o&&o.a)||'middle'}" font-weight="${(o&&o.w)||400}">${s}</text>`;
// 01: a cross-section of the globe, rise in the middle and fall at the walls, steps on the right
const gx=150,gb=182,gh=168,R=y=>(0.27-0.2*(y-0.25)*(y-0.25)-(y<0.25?0.52*(0.25-y)*(0.25-y):0))*gh*1.15;
let gp='';for(let k=0;k<=24;k++){const y=k/24;gp+=(k?'L':'M')+(gx-R(y)).toFixed(1)+' '+(gb-y*gh).toFixed(1);}for(let k=24;k>=0;k--){const y=k/24;gp+='L'+(gx+R(y)).toFixed(1)+' '+(gb-y*gh).toFixed(1);}
S('cycle',`<defs><marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10z" fill="context-stroke"/></marker>
<linearGradient id="lq" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#fff0d8"/><stop offset=".25" stop-color="#b48cff"/><stop offset="1" stop-color="#3a1a78"/></linearGradient></defs>
<path d="${gp}Z" fill="url(#lq)" stroke="#7a6a58"/>
<ellipse cx="${gx}" cy="${gb-8}" rx="44" ry="9" fill="#ff6516"/><path d="M${gx-40} ${gb-3} q8 -6 16 0 q8 6 16 0 q8 -6 16 0 q8 6 16 0 q8 -6 16 0" stroke="#4a3a2c" fill="none"/>
<ellipse cx="${gx}" cy="${gb-70}" rx="13" ry="19" fill="#ff7a2a"/><ellipse cx="${gx+8}" cy="${gb-156}" rx="22" ry="8" fill="#e0561a"/><circle cx="${gx-34}" cy="${gb-96}" r="9" fill="#c9481a"/>
<path d="M${gx} ${gb-94} V${gb-138}" stroke="#c2581a" stroke-width="3" marker-end="url(#ar)"/>
<path d="M${gx-34} ${gb-82} V${gb-40}" stroke="#3d6fb0" stroke-width="3" marker-end="url(#ar)"/>
<path d="M${gx+40} ${gb-140} V${gb-50}" stroke="#3d6fb0" stroke-width="3" stroke-dasharray="5 4" marker-end="url(#ar)"/>
${T(gx,gb+12,'bulb ↑',{fs:11,c:'#7a5a2a'})}
${[['1 · Heat','the pool on the coil warms; a tower forms and pinches off'],['2 · Rise','hot wax is lighter than the liquid; it stretches into a teardrop'],['3 · Rest and cool','it flattens under the cap and gives up heat'],['4 · Fall and merge','denser again, it sinks by the walls; the coil breaks its skin']].map(([h,t],i)=>T(300,34+i*44,h,{a:'start',w:700,fs:14})+T(300,52+i*44,t,{a:'start',fs:12,c:'#4b4036'})).join('')}`);
// 02: density against temperature, schematic, crossing marked
S('dens',`<rect x="0" y="0" width="190" height="150" fill="#fff8ea" rx="8"/><path d="M28 14 V122 H182" stroke="#5a4a3a" fill="none"/>
<path d="M32 30 L178 110" stroke="#ff6516" stroke-width="3"/><path d="M32 60 L178 84" stroke="#3d6fb0" stroke-width="3"/>
<circle cx="103" cy="72" r="4.5" fill="#2b1d12"/>${T(103,60,'crossing',{fs:10,w:700})}
${T(150,136,'temperature →',{fs:10})}${T(12,70,'ρ',{fs:14,w:700})}${T(58,28,'wax',{fs:10,c:'#c2481a',w:700})}${T(58,72,'liquid',{fs:10,c:'#3d6fb0',w:700})}
${T(62,146,'sinks',{fs:10})}${T(150,146,'rises',{fs:10})}`);
// 05: evenly spaced timeline, two-line labels
const ev=[['1950','Dunnet files','GB 703,924'],['1963','Astro','launched'],['1965','US rights:','Lava Lite, Chicago'],['1968','US 3,387,396','granted'],['1970','CCl₄ banned','in US lamps'],['late 1970s','Haggerty buys','the US rights'],['1992','Crestworth','becomes Mathmos'],['1998','Lavarand','patent granted'],['2000','Craven Walker','dies'],['2017','Cloudflare’s','lamp wall']];
S('tl',`<path d="M10 40 H994" stroke="#5a4a3a" stroke-width="2"/>`+ev.map(([y,a,b],i)=>{const x=60+i*98;return `<circle cx="${x}" cy="40" r="5" fill="#c2581a"/>${T(x,26,y,{w:700,fs:13})}${T(x,62,a,{fs:11})}${T(x,76,b,{fs:11})}`;}).join(''));
window.__ready=true;
"""


def main():
    import json
    opts = json.dumps([[n, a, b, c, d, e] for n, a, b, c, d, e in OPTIONS])
    pages = {
        'lamp.html': page('Lava lamp: the screensaver', 'Live: the plan’s wax model, real local time in the base (24-hour), colours from the Level Settings form', LAMP_BODY, LAMP_SCRIPT, LAMP_CSS),
        'time-options.html': page('Twenty ways to show the time', '★ recommended · ●●●●● legibility from a sofa · S/M build size', '<div id="grid"></div>', OPT_SCRIPT.replace('__OPTS__', opts), OPT_CSS),
        'palettes.html': page('Lava × water: all 64 pairings', 'The two new settings, every combination, at 21:47', '<div id="pal"></div><div id="key"></div>', PAL_SCRIPT, PAL_CSS),
        'settings.html': page('Level settings: lava and water color', 'TV overlay, result after Apply, phone form', SET_BODY, SET_SCRIPT, SET_CSS),
        'states.html': page('States', 'Running · minute change · clock not set · narrow screens', ST_BODY, ST_SCRIPT),
        'poster.html': page('A3 poster draft', 'Physics, properties, history, patents and Forth: layout on sourced text', POSTER_BODY, POSTER_SCRIPT, POSTER_CSS),
    }
    for name, html in pages.items():
        (HERE / name).write_text(html)
        print(f'{name}: {len(html.encode()) // 1024} KB')


if __name__ == '__main__':
    main()
