import {G,escape,patch,board,phaseTitle,standings,skinPicker,skins} from './ui.js';
let cleanup;
export function mount(ctx) {
  let shared=null,mine=null,local=null,error='',pending=false,skin=localStorage.getItem('pd-skin')||'linen';
  const subscriptions=[];
  let dragging=false,lastCell=-1;
  const send=(type,fields={})=>ctx.send({type,stage:shared?.stage,...fields});
  const fresh=()=>({placement:null,singles:[],ready:false});
  function sync(p) {
    if(mine?.stage!==p.stage || p.revision!==mine?.revision || pending) {local=structuredClone(p.draft||fresh());pending=false;}
    mine=p;render();
  }
  function context() {return shared.phase==='SCORING'?shared.context:{circle:shared.circle,token:shared.token,final:shared.round===3&&shared.turn===6};}
  function available() {
    if(shared.phase==='STARTING')return [mine.start];
    const c=context();if(!c)return [];
    if(shared.phase==='SCORING'&&(!mine.lastPassed||(!local?.placement?.neighbor&&!local?.placement?.cutMode)))return [];
    if(c.final)return c.circle;
    if(local?.placement?.neighbor)return [c.circle[(c.token+c.circle.length-1)%c.circle.length],c.circle[(c.token+1)%c.circle.length]];
    return c.circle[c.token]?[c.circle[c.token]]:[];
  }
  function selected() {return available().find(c=>c.id===local?.placement?.cardId)||available()[0];}
  function cells() {
    const p=local?.placement,c=selected();if(!p||!c)return [];
    const cut=p.cut && G.cuts(c.cells).find(t=>t.axis===p.cut.axis&&t.at===p.cut.at&&t.side===p.cut.side);
    return G.orient(cut?.cells||c.cells,p.rotation,p.flip);
  }
  function choose(c) {
    local.placement={...(local.placement||{x:0,y:0,rotation:0,flip:false}),cardId:c.id};
    delete local.placement.cut;delete local.placement.repeatCut;
    const fit=G.firstFit(mine.board,c.cells);
    if(fit)Object.assign(local.placement,fit);
    local.ready=false;render();
  }
  function submit(ready) {
    if(pending)return;
    error='';pending=true;
    send('PD_DRAFT',{...local,ready,revision:mine.revision+1,actionId:crypto.randomUUID?.() || Array.from(crypto.getRandomValues(new Uint8Array(16)), b=>b.toString(16).padStart(2,'0')).join('')});render();
  }
  function render() {
    if(!shared) {ctx.root.innerHTML='<p class="loading">Threading the needle…</p>';return;}
    const host=ctx.playerId===shared.hostId;
    const seat=shared.players.find(p=>p.id===ctx.playerId);
    const playing=seat&&!seat.withdrawn&&mine?.stage===shared.stage&&['STARTING','PLACING','SCORING'].includes(shared.phase);
    const active=shared.players.filter(p=>!p.withdrawn);
    const canAdvance=shared.receiverOnline&&active.length&&active.every(p=>p.connected&&p.ready);
    const room=new URLSearchParams(location.search).get('room')||'';
    let html=`<div class="pd phone" data-theme="${skins.includes(skin)?skin:'linen'}"><div class="eyebrow">QUILT NIGHT · ${escape(room)}</div><div class="heading"><h1>${phaseTitle(shared)}</h1>${skinPicker(skin)}</div>`;
    if(error)html+=`<p class="error" role="alert">${escape(error)}</p>`;
    if(!shared.receiverOnline)html+='<p class="notice">Shared display disconnected. Turn advancement is paused.</p>';
    if(shared.phase==='LOBBY') {
      html+=`<p>One quilt each. Shared patches. Make the best filled rectangle, then count everyone’s scores on the TV.</p><ul class="roster">${ctx.players().map(p=>`<li>${escape(p.name)}${p.id===shared.hostId?' · host':''}</li>`).join('')}</ul>`;
      if(host)html+='<button class="primary" data-action="start">Start game</button>';
      else html+='<p>Waiting for the host to start.</p>';
      html+=`<a class="tv-link" href="/receiver?room=${encodeURIComponent(room)}" target="_blank" rel="noopener">Open shared display</a>`;
    } else if(shared.phase==='FINISHED') {
      html+=standings(shared);
      if(seat&&!seat.withdrawn)html+=`<p>Your score: ${seat.final.subtotal} − ${seat.final.empty} empty cells = <strong>${seat.final.total}</strong></p>${board(seat.board)}`;
      if(host)html+=`<div class="host-controls"><button data-action="back">Previous score step</button><button class="primary" data-action="next">Next score step</button><button data-action="all">Show standings</button><button data-action="start">New game</button></div>`;
    } else if(playing) {
      const p=local.placement,shape=cells(),ghost=p?shape.map(([x,y])=>[x+p.x,y+p.y]):[];
      let shown=mine.board.slice(), valid=true;
      for(const single of local.singles) {if(G.fit(shown,[[0,0]],single.x,single.y))shown=G.place(shown,[[0,0]],single.x,single.y,shared.turn+20);else valid=false;}
      if(p&&!G.fit(shown,shape,p.x,p.y))valid=false;
      html+=`<div class="placement-layout"><div class="board-panel">${board(shown,{ghost,invalid:!valid,interactive:true})}<p class="board-hint">${mine.ready?'Ready. Choose not ready to edit again.':local.addSingle?'Tap an empty cell for the extra square.':'Tap or drag across the grid to position your patch.'}</p></div><div class="tools-panel">`;
      if(shared.phase==='SCORING')html+='<p>Check your quilt. You can use remaining special actions before scoring.</p>';
      const choices=available();
      html+=`<div class="patch-choices">${choices.map(c=>`<button data-card="${c.id}" class="patch-card ${p?.cardId===c.id?'selected':''}" aria-label="Choose patch ${c.id}">${patch(c.cells)}<small>${c.cells.length} cells</small></button>`).join('')}</div>`;
      if(p) {
        html+=`<div class="transforms"><button data-action="rotate">↻ Rotate</button><button data-action="flip">⇆ Flip</button></div><div class="nudge"><button data-move="0,-1" aria-label="Move up">↑</button><button data-move="-1,0" aria-label="Move left">←</button><button data-move="1,0" aria-label="Move right">→</button><button data-move="0,1" aria-label="Move down">↓</button></div>`;
      }
      if(shared.phase!=='STARTING') {
        html+='<div class="specials"><h2>Special actions</h2>';
        const repeatFree=!mine.used.repeat && !local.singles.some(c=>c.repeat) && !p?.repeatCut && !p?.repeatNeighbor;
        for(const [type,label]of [['neighbor','Neighbor patch'],['cut','Straight cut'],['single','Extra square']]) {
          const drafting=type==='single'?local.singles.length>0:type==='cut'?!!p?.cut:!!p?.neighbor;
          const needsRepeat=mine.used[type] || (type==='single'&&drafting);
          const disabled=(needsRepeat&&!repeatFree)||(shared.phase==='SCORING'&&!mine.lastPassed&&type!=='single')||(context()?.final&&type==='neighbor');
          html+=`<button data-special="${type}" ${disabled?'disabled':''}>${label}${needsRepeat?' · repeat':''}${drafting?' ✓':''}</button>`;
        }
        html+=`<p class="special-status">${Object.entries(mine.used).map(([k,v])=>`${k}: ${v?'used':'available'}`).join(' · ')}</p></div>`;
        if(p?.cutMode) {
          html+=`<label>Keep one piece <select data-cut><option value="">Choose a straight cut</option>${G.cuts(selected().cells).map((c,i)=>`<option value="${i}" ${JSON.stringify(p.cut)===JSON.stringify({axis:c.axis,at:c.at,side:c.side})?'selected':''}>${c.axis?'Horizontal':'Vertical'} at ${c.at}, ${c.side?'second':'first'} piece · ${c.cells.length} cells</option>`).join('')}</select></label>`;
        }
      }
      html+=`<div class="commit-controls"><button data-action="reset">Undo this turn</button>${shared.phase==='STARTING'?'':'<button data-action="pass">Pass patch</button>'}<button class="primary" data-action="ready" ${pending||mine.ready||!valid||(shared.phase==='STARTING'&&!p)?'disabled':''}>${pending?'Saving…':mine.ready?'Ready ✓':'Ready'}</button>${mine.ready?'<button data-action="edit">Not ready · keep editing</button>':''}</div></div></div>`;
    } else if(shared.phase==='TURN_RESULTS') {
      html+=`<div class="placement-layout turn-review"><div class="board-panel">${seat&&!seat.withdrawn?board(seat.board):''}</div><div class="tools-panel"><p>Everyone’s finished quilt is on the shared display.</p>`;
      if(host)html+=`<div class="host-controls"><button class="primary" data-action="advance" ${!shared.receiverOnline||active.some(p=>!p.connected)?'disabled':''}>Continue</button>${active.filter(p=>!p.connected).map(p=>`<button data-withdraw="${p.id}">Withdraw ${escape(p.name)}</button>`).join('')}</div>`;
      else html+='<p>Waiting for the host to continue.</p>';
      html+='</div></div>';
    } else if(shared.phase==='ROUND_RESULTS') {
      html+=`<ul class="roster">${active.map(p=>`<li>${escape(p.name)} <strong>${p.scores.at(-1)?.score} points</strong></li>`).join('')}</ul><p>Round rectangles are shown on the shared display.</p>`;
    } else html+='<p>You’re watching this game. Join the next one.</p>';
    if(!['LOBBY','FINISHED'].includes(shared.phase)) {
      if(shared.phase!=='TURN_RESULTS')html+=`<div class="readiness">${shared.players.map(p=>`<span>${escape(p.name)} · ${p.withdrawn?'withdrawn':!p.connected?'offline':p.ready?'ready':'placing'}</span>`).join('')}</div>`;
      if(host&&shared.phase!=='TURN_RESULTS')html+=`<div class="host-controls"><button class="primary" data-action="advance" ${(shared.phase==='ROUND_RESULTS'?(!shared.receiverOnline||active.some(p=>!p.connected)):!canAdvance)?'disabled':''}>${shared.phase==='ROUND_RESULTS'?'Start next round':shared.phase==='SCORING'?'Lock round scores':'Advance when everyone is ready'}</button>${active.filter(p=>!p.connected).map(p=>`<button data-withdraw="${p.id}">Withdraw ${escape(p.name)}</button>`).join('')}</div>`;
    }
    html+=`<details class="help"><summary>How to play</summary><p>Place the starting patch, then play three rounds of six shared turns. Rotate or flip freely. Cover only empty cells inside the 9×9 grid. You may pass a patch. Ready can be changed until the host advances.</p><p>Each round scores your best filled rectangle: its largest square scores one point per cell, plus one per extra row or column. Add three round scores, then subtract final empty cells. Highest total wins; ties share victory.</p><p>Use each special once: a neighboring patch, a single extra cell, a straight cut leaving two connected pieces (keep one), and repeat one previously used action.</p></details><p class="development">Development deck · physical card inventory pending verification</p></div>`;
    ctx.root.innerHTML=html;
    ctx.root.querySelector('[data-skin]')?.addEventListener('change',e=>{skin=e.target.value;localStorage.setItem('pd-skin',skin);render();});
    ctx.root.querySelectorAll('[data-card]').forEach(el=>el.onclick=()=>{error='';choose(choicesById(el.dataset.card));});
    function choicesById(id){return available().find(c=>c.id===id);}
    ctx.root.querySelectorAll('[data-move]').forEach(el=>el.onclick=()=>{const [dx,dy]=el.dataset.move.split(',').map(Number);local.placement.x+=dx;local.placement.y+=dy;render();});
    ctx.root.querySelectorAll('[data-action]').forEach(el=>el.onclick=()=>{
      const action=el.dataset.action;
      if(action==='start')send('PD_START');
      if(action==='advance')send('PD_ADVANCE');
      if(action==='back')send('PD_CEREMONY',{cursor:Math.max(0,shared.ceremony-1)});
      if(action==='next')send('PD_CEREMONY',{cursor:Math.min(active.length*6,shared.ceremony+1)});
      if(action==='all')send('PD_CEREMONY',{cursor:active.length*6});
      if(action==='rotate'){local.placement.rotation=(local.placement.rotation+1)%4;render();}
      if(action==='flip'){local.placement.flip=!local.placement.flip;render();}
      if(action==='reset'){local=fresh();if(shared.phase==='STARTING')choose(mine.start);else render();}
      if(action==='pass'){local.placement=null;render();}
      if(action==='ready')submit(true);
      if(action==='edit')submit(false);
    });
    ctx.root.querySelectorAll('[data-withdraw]').forEach(el=>el.onclick=()=>send('PD_WITHDRAW',{playerId:Number(el.dataset.withdraw)}));
    ctx.root.querySelectorAll('[data-special]').forEach(el=>el.onclick=()=>{
      const type=el.dataset.special;
      if(type==='single'){local.addSingle=true;render();return;}
      if(!local.placement){const c=context();choose(c.final?c.circle[0]:c.circle[c.token]);}
      const p=local.placement;
      if(type==='neighbor'){p.neighbor=!p.neighbor;p.repeatNeighbor=!!mine.used.neighbor;const next=available()[0];p.cardId=next.id;delete p.cut;}
      if(type==='cut'){p.cutMode=!p.cutMode;p.repeatCut=!!mine.used.cut;if(!p.cutMode)delete p.cut;}
      if(shared.phase==='SCORING'&&!p.neighbor&&!p.cutMode)local.placement=null;
      render();
    });
    ctx.root.querySelector('[data-cut]')?.addEventListener('change',e=>{
      const c=e.target.value===''?null:G.cuts(selected().cells)[Number(e.target.value)];
      local.placement.cut=c?{axis:c.axis,at:c.at,side:c.side}:null;render();
    });
    if (mine?.ready && playing) {
      ctx.root.querySelectorAll('[data-cell], [data-card], [data-move], [data-special], [data-cut], [data-action="rotate"], [data-action="flip"], [data-action="reset"], [data-action="pass"]').forEach(el=>el.disabled=true);
    }
    const quilt=ctx.root.querySelector('.quilt.interactive');
    function position(index) {
      if(index===lastCell)return;lastCell=index;
      const x=index%9,y=Math.floor(index/9);
      if(local.addSingle){local.singles.push({x,y,repeat:mine.used.single||local.singles.length>0});local.addSingle=false;dragging=false;}
      else {if(!local.placement){const c=available()[0];if(!c)return;local.placement={cardId:c.id,x,y,rotation:0,flip:false};}else Object.assign(local.placement,{x,y});}
      render();
    }
    // Delegated pointer handling stays on the root while grid cells re-render.
    ctx.root.onpointerdown=e=>{const cell=e.target.closest('[data-cell]');if(!cell||!playing||mine.ready)return;dragging=true;lastCell=-1;try{ctx.root.setPointerCapture(e.pointerId);}catch{}position(Number(cell.dataset.cell));};
    ctx.root.onpointermove=e=>{if(!dragging||!playing||mine.ready)return;const cell=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-cell]');if(cell){e.preventDefault();position(Number(cell.dataset.cell));}};
    ctx.root.onpointerup=()=>{dragging=false;lastCell=-1;};
    ctx.root.onpointercancel=()=>{dragging=false;lastCell=-1;};
    quilt?.querySelectorAll('[data-cell]').forEach(el=>el.onclick=e=>{if(e.detail===0&&!mine.ready)position(Number(el.dataset.cell));});
  }
  subscriptions.push(ctx.on('PD_STATE',s=>{shared=s;render();}),ctx.on('PD_PRIVATE',sync),ctx.on('PD_ERROR',s=>{pending=false;error=s.message;render();}),ctx.on('WELCOME',()=>send('PD_REQUEST')));
  ctx.send({type:'PD_REQUEST'});
  cleanup=()=>{subscriptions.forEach(off=>off());ctx.root.onpointerdown=ctx.root.onpointermove=ctx.root.onpointerup=ctx.root.onpointercancel=null;};
}
export function unmount(){cleanup?.();}
