let ctx, state, root, pulse, frame, stops=[],held=new Map(),lastPaint='',ping=0;
const DIR={ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right'};
export function mount(context) {
 ctx=context;root=ctx.root;root.classList.add('bm');
 root.innerHTML=`<h1>Bomberman</h1><div class="bm-room"><span id="bm-room"></span><button id="bm-share">Copy invite</button></div><p id="bm-info" role="status">Waiting for the room…</p><div id="bm-score"></div><div id="bm-arena" aria-label="Battle arena"></div><div id="bm-choose"><label>Your cat <select id="bm-cat"></select></label><button id="bm-ready">Ready</button></div><div class="bm-controls"><div class="bm-dpad"><button data-dir="up" aria-label="Up">↑</button><button data-dir="left" aria-label="Left">←</button><button data-dir="right" aria-label="Right">→</button><button data-dir="down" aria-label="Down">↓</button></div><button id="bm-bomb">BOMB</button></div><p id="bm-net">Connecting…</p><p class="bm-hint">One life per round · first to 3 wins · flames hurt both cats</p>`;
 const names=['Marmalade','Domino','Radar','Socks','Willow','Pepper','Mochi','Cleo','Tiger','Luna','Shadow','Ginger','Misty','Felix','Bean','Pip','Oreo','Nala','Biscuit','Ziggy'];
 for(let i=0;i<20;i++){const option=document.createElement('option');option.value=i;option.textContent=names[i];root.querySelector('#bm-cat').append(option);}
 for(let i=0;i<143;i++){const cell=document.createElement('div');cell.className='bm-cell';root.querySelector('#bm-arena').append(cell);}
 root.querySelector('#bm-cat').onchange=e=>ctx.send({type:'BM_CAT',cat:Number(e.target.value)});
 root.querySelector('#bm-ready').onclick=()=>ctx.send({type:'BM_READY'});
 const room=new URLSearchParams(location.search).get('room');root.querySelector('#bm-room').textContent='Room '+room;
 const invite=new URL(location.href);invite.searchParams.delete('name');
 root.querySelector('#bm-share').onclick=async()=>{try{await navigator.clipboard.writeText(invite.href);root.querySelector('#bm-share').textContent='Copied';}catch{prompt('Share this invite link',invite.href);}};
 function bind(target,type,fn){target.addEventListener(type,fn);stops.push(()=>target.removeEventListener(type,fn));}
 const send=()=>ctx.send({type:'BM_INPUT',direction:[...held.values()].at(-1)||null});
 function release(id){held.delete(id);send();}
 for(const b of root.querySelectorAll('[data-dir]')) {
  bind(b,'pointerdown',e=>{e.preventDefault();b.setPointerCapture(e.pointerId);held.set(e.pointerId,b.dataset.dir);send();});
  for(const event of ['pointerup','pointercancel','lostpointercapture'])bind(b,event,e=>release(e.pointerId));
 }
 const bomb=()=>ctx.send({type:'BM_BOMB'});
 bind(root.querySelector('#bm-bomb'),'pointerdown',e=>{e.preventDefault();bomb();});
 bind(window,'keydown',e=>{if(DIR[e.key]){e.preventDefault();if(!e.repeat){held.set(e.key,DIR[e.key]);send();}}else if(e.key===' '&&!e.repeat){e.preventDefault();bomb();}});
 bind(window,'keyup',e=>{if(DIR[e.key])release(e.key);});
 const clear=()=>{held.clear();send();};bind(window,'blur',clear);bind(document,'visibilitychange',()=>{if(document.hidden)clear();});
 stops.push(ctx.on('BM_STATE',s=>{state=s;if(s.phase!=='playing')held.clear();paint();}));
 stops.push(ctx.on('PONG',s=>{if(s.clientTs)ping=Date.now()-s.clientTs;}));
 stops.push(ctx.on('WELCOME',()=>{clear();ctx.send({type:'BM_SYNC'});}));
 pulse=setInterval(()=>{send();ctx.send({type:'PING',clientTs:Date.now()});},150);
 ctx.send({type:'BM_SYNC'});
 frame=setInterval(()=>{root.querySelector('#bm-net').textContent=`${document.querySelector('#status').textContent} · ${ping?ping+' ms ping':'measuring ping'}`;},500);
}
function paint(){
 if(!state)return;const me=state.players.find(p=>p.id===ctx.playerId),watcher=!me;
 const info=root.querySelector('#bm-info');const phase=state.phase;
 info.textContent=phase==='playing'?`Round ${state.round} · ${Math.ceil(state.time)}s${me&&!me.alive?' · You are out this round':''}`:phase==='paused'?'Connection lost. Both players tap Ready to resume.':phase==='lobby'?'Both players choose a cat and tap Ready.':state.winner===null?'Draw — tap Ready for the next round.':`${state.players.find(p=>p.id===state.winner)?.name||'Player'} wins${phase==='match-over'?' the match':' the round'}! Tap Ready to play again.`;
 const scores=root.querySelector('#bm-score');scores.replaceChildren();
 state.players.forEach((p,i)=>{const el=document.createElement('span');el.className='bm-p'+i;el.textContent=`${p.name} ${p.wins}/3${p.ready?' · ready':''}${!p.connected?' · offline':''}${p.id===ctx.playerId?' · you':''}`;scores.append(el);});
 root.querySelector('#bm-ready').disabled=watcher||phase==='playing'||!!me?.ready;
 root.querySelector('#bm-ready').textContent=watcher?'Spectating':me?.ready?'Ready — waiting…':phase==='paused'?'Resume':'Ready';
 root.querySelector('#bm-cat').disabled=watcher||phase==='playing';if(me)root.querySelector('#bm-cat').value=me.cat;
 root.querySelector('#bm-bomb').disabled=watcher||phase!=='playing'||!me.alive;
 const render=JSON.stringify([state.cells,state.players.map(p=>[p.x,p.y,p.alive,p.cat]),state.bombs.map(b=>[b.x,b.y]),state.flames,state.powers]);
 if(render===lastPaint)return;lastPaint=render;
 const cells=[...root.querySelector('#bm-arena').children];
 cells.forEach((el,i)=>{el.className='bm-cell '+(['','soft','hard'][state.cells[i]]||'');el.replaceChildren();});
 const add=(x,y,cls,text)=>{const el=document.createElement('span');el.className=cls;el.textContent=text;cells[y*13+x]?.append(el);return el;};
 for(const p of state.powers)add(p.x,p.y,'pickup',p.kind==='bomb'?'+B':p.kind==='flame'?'+F':'+S');
 for(const b of state.bombs)add(b.x,b.y,'bomb','●');
 for(const f of state.flames)add(f.x,f.y,'flame','✹');
 state.players.forEach((p,i)=>{if(p.alive&&p.x!==undefined){const el=add(p.x,p.y,'cat bm-p'+i,'');el.style.backgroundPosition=`${p.cat%5*25}% ${Math.floor(p.cat/5)*100/3}%`;const label=document.createElement('b');label.textContent=String(i+1);el.append(label);}});
}
export function unmount(){held.clear();clearInterval(pulse);clearInterval(frame);stops.forEach(fn=>fn());stops=[];lastPaint='';state=null;root?.classList.remove('bm');ctx=null;}
