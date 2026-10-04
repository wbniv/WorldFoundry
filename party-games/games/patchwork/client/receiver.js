import {escape,patch,board,phaseTitle,standings,skinPicker,skins} from './ui.js';
let cleanup;
export function mount(ctx) {
  console.info('PD_RECEIVER_MOUNTED');
  let state=null,skin=localStorage.getItem('pd-tv-skin')||'linen';
  function render() {
    if(!state){ctx.root.innerHTML='<p>Preparing the shared quilt table…</p>';return;}
    const s=state,active=s.players.filter(p=>!p.withdrawn);
    const readiness=active.every(p=>p.ready)?'all':active.some(p=>p.ready)?'some':'none';
    let html=`<div class="pd television" data-theme="${skins.includes(skin)?skin:'linen'}" data-phase="${s.phase}" data-round="${s.round}" data-turn="${s.turn}" data-ready="${readiness}" data-ceremony="${s.ceremony}" data-player-count="${active.length}"><div class="heading"><div><div class="eyebrow">QUILT NIGHT</div><h1>${phaseTitle(s)}</h1></div>${skinPicker(skin)}</div>`;
    if(s.phase==='TURN_RESULTS') {
      html+=`<div class="autoplay-quilts">${active.map(p=>`<article><h2>${escape(p.name)}</h2>${board(p.board)}</article>`).join('')}</div><p class="autoplay-note">Everyone’s finished turn · host: Continue on your phone</p>`;
    } else if(s.phase==='LOBBY') {
      const code=new URLSearchParams(location.search).get('room')||'';
      const join=new URL('/controller',location.origin);join.searchParams.set('room',code);
      html+=`<div class="lobby"><div><h2>Your next quilt starts here.</h2><p>Scan to join on your phone, or open</p><p class="join-url">${escape(join.href)}</p><div class="join-code">${escape(code)}</div><p>The first player is the host. Start from your phone when everyone has joined.</p></div><div><img class="join-qr" src="/join-qr?room=${encodeURIComponent(code)}" alt="Scan to join room ${escape(code)}"><ul class="tv-roster">${ctx.players().map(p=>`<li>${escape(p.name)}${p.id===s.hostId?' · host':''}</li>`).join('')}</ul></div></div>`;
    } else if(['STARTING','PLACING'].includes(s.phase)) {
      html+=`<div class="shared-table"><div class="card-pool">${s.circle.map((c,i)=>`<div class="shared-card ${i===s.token?'token':''}" style="--order:${i}"><span class="card-marker">${i===s.token?'● Selected':i+1}</span>${patch(c.cells)}<span>${c.cells.length} cells</span></div>`).join('')}</div><aside><div class="die">${s.die===null?'✦':['','⚀','⚁','⚂'][s.die]}</div><h2>${s.phase==='STARTING'?'Your starting patch is on your phone':s.round===3&&s.turn===6?'Choose any of these three patches':'The same patch for everyone'}</h2>${s.token>=0?patch(s.circle[s.token].cells):''}<p>${s.phase==='STARTING'?'Place the seven-cell patch anywhere inside your grid.':s.token<0?'Players may choose the same card.':'Rotate, flip, or pass. The host advances after everyone is ready.'}</p></aside></div>`;
    } else if(s.phase==='SCORING') {
      html+=`<div class="score-prep"><h2>A moment for the finishing touches.</h2><p>Use any remaining eligible special actions on your phone, then mark yourself ready.</p><p>The host locks everyone’s round scores together.</p></div>`;
    } else if(s.phase==='ROUND_RESULTS') {
      html+=`<div class="round-results">${active.map(p=>{const score=p.scores.at(-1);return `<article><h2>${escape(p.name)}</h2>${board(score.board,{highlight:score})}<p><strong>${score.score}</strong> = ${score.square}² + ${score.extra}</p></article>`;}).join('')}</div><p class="tv-note">Your quilts carry forward. The host starts the next round from their phone.</p>`;
    } else if(s.phase==='FINISHED') {
      const max=active.length*6;
      if(s.ceremony>=max)html+=`<h2>Every stitch counted.</h2>${standings(s)}`;
      else {
        const p=active[Math.floor(s.ceremony/6)],step=s.ceremony%6;
        const round=Math.min(step,2),score=p.scores[round];
        const labels=['Round 1 rectangle','Round 2 rectangle','Round 3 rectangle','Add the three round scores','Deduct the empty cells','Final total'];
        const scoreSum=p.scores.map(r=>r.score).join(' + ');
        let math=step<3?`${score.square} × ${score.square} + ${score.extra} = ${score.score}`:step===3?`${scoreSum} = ${p.final.subtotal}`:step===4?`${p.final.subtotal} − ${p.final.empty} = ${p.final.total}`:`${scoreSum} − ${p.final.empty} = ${p.final.total}`;
        html+=`<div class="ceremony"><div>${board(step<3?score.board:p.board,{highlight:step<3?score:null,empty:step===4})}</div><article><div class="eyebrow">${escape(p.name)} · ${Math.floor(s.ceremony/6)+1} of ${active.length}</div><h2>${labels[step]}</h2><p class="arithmetic">${math}</p><p>${step<3?'The outlined square earns one point per cell. Each additional row or column earns one more.':step===4?`${p.final.empty} empty cells remain in the final quilt.`:'All three scores come from the quilt as it stood at the end of each round.'}</p><p class="presentation-step">${step+1} / 6 · Host: next or previous on your phone</p></article></div>`;
      }
    }
    if(['STARTING','PLACING','SCORING'].includes(s.phase))html+=`<div class="tv-readiness">${s.players.map(p=>`<div class="${p.ready?'ready':''}"><strong>${escape(p.name)}</strong><span>${p.withdrawn?'Withdrawn':!p.connected?'Reconnecting…':p.ready?'✓ Ready':s.phase==='SCORING'?'Finishing touches':'Still placing'}</span></div>`).join('')}</div>`;
    html+=`<p class="development">Development deck · physical card inventory pending verification</p></div>`;
    ctx.root.innerHTML=html;
    if(new URLSearchParams(location.search).get('visualCheck')==='1') {
      window.__pdVisual={state:s,players:ctx.players(),skin};
      console.info('PD_VISUAL_FRAME '+JSON.stringify({time:Date.now(),phase:s.phase,round:s.round,turn:s.turn,ready:readiness,ceremony:s.ceremony,players:active.length}));
    }
    ctx.root.querySelector('[data-skin]')?.addEventListener('change',e=>{skin=e.target.value;localStorage.setItem('pd-tv-skin',skin);render();});
  }
  const offs=[ctx.on('PD_STATE',s=>{state=s;console.info(`PD_DISPLAY_STATE ${s.phase} ${s.stage}`);render();}),ctx.on('STATE',render)];
  ctx.send({type:'PD_REQUEST'});
  let stopCheck=null,unmounted=false;
  if(new URLSearchParams(location.search).get('deviceCheck')==='1') {
    import('./device-check.js').then(module=>{
      if(!unmounted)stopCheck=module.runDeviceCheck(ctx,new URLSearchParams(location.search).get('room'));
    });
  }
  cleanup=()=>{unmounted=true;stopCheck?.();offs.forEach(off=>off());};
}
export function unmount(){cleanup?.();}
