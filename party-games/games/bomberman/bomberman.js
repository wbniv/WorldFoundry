// Server-authoritative two-player battle, using the existing room transport.
const W=13,H=11,DIR={up:[0,-1],down:[0,1],left:[-1,0],right:[1,0]};
function createBombermanGame() {
 let phase='lobby',players=[],cells=[],bombs=[],flames=[],powers=[],time=120,winner=null,round=0,cancel=null,last=0;
 const snapshot=()=>({type:'BM_STATE',phase,players:players.map(({input,...p})=>p),cells,bombs,flames,powers,time,winner,round});
 const emit=s=>s.broadcast(snapshot());
 const clear=()=>{if(cancel)cancel();cancel=null;};
 const open=(x,y,p)=>x>0&&y>0&&x<W-1&&y<H-1&&cells[y*W+x]===0&&!bombs.some(b=>b.x===x&&b.y===y);
 function presence(s) {
  const connected=s.getPlayers();
  for(const p of players) {p.connected=connected.some(q=>q.id===p.id&&q.connected!==false);if(!p.connected){p.input=null;p.ready=false;}}
  if(phase==='playing'&&players.some(p=>!p.connected)){phase='paused';clear();for(const p of players){p.ready=false;p.input=null;}}
  emit(s);
 }
 function begin(s) {
  clear();phase='playing';winner=null;time=120;round++;bombs=[];flames=[];powers=[];
  cells=Array(W*H).fill(0);const safe=new Set([14,15,27,128,127,115]);
  for(let y=0;y<H;y++)for(let x=0;x<W;x++){const i=y*W+x;cells[i]=(x===0||y===0||x===12||y===10||(x%2===0&&y%2===0))?2:(!safe.has(i)&&s.random()<.55?1:0);}
  players.forEach((p,i)=>Object.assign(p,{x:i?11:1,y:i?9:1,alive:true,range:2,capacity:1,speed:1,input:null,nextMove:0,ready:false,lastInput:0}));
  last=s.now();emit(s);schedule(s);
 }
 function schedule(s){cancel=s.schedule(50,()=>{cancel=null;const now=s.now();step(Math.min(.2,Math.max(0,(now-last)/1000)),now,s);last=now;if(phase==='playing')schedule(s);});}
 function step(dt,now,s) {
  if(phase!=='playing')return;
  time=Math.max(0,time-dt);
  for(const p of players){if(!p.alive||!p.input||now-p.lastInput>500)continue;if(now>=p.nextMove){const [dx,dy]=DIR[p.input];if(open(p.x+dx,p.y+dy,p)){p.x+=dx;p.y+=dy;const power=powers.find(q=>q.x===p.x&&q.y===p.y);if(power){powers=powers.filter(q=>q!==power);if(power.kind==='bomb')p.capacity=Math.min(5,p.capacity+1);if(power.kind==='flame')p.range=Math.min(8,p.range+1);if(power.kind==='speed')p.speed=Math.min(1.8,p.speed+.2);}}p.nextMove=now+150/p.speed;}}
  // Old flames persist, but newly dropped items are not burnt by their spawning blast.
  flames=flames.map(f=>({...f,t:f.t-dt})).filter(f=>f.t>0);
  for(const b of bombs)b.t-=dt;
  const due=bombs.filter(b=>b.t<=0),seen=new Set();
  while(due.length){const b=due.shift();if(seen.has(b))continue;seen.add(b);bombs=bombs.filter(q=>q!==b);const hit=[[b.x,b.y]];
   for(const [dx,dy] of Object.values(DIR))for(let n=1;n<=b.range;n++){const x=b.x+dx*n,y=b.y+dy*n;if(x<0||x>=W||y<0||y>=H||cells[y*W+x]===2)break;hit.push([x,y]);powers=powers.filter(q=>q.x!==x||q.y!==y);if(cells[y*W+x]===1){cells[y*W+x]=0;if(s.random()<.34)powers.push({x,y,kind:['bomb','flame','speed'][Math.floor(s.random()*3)]});break;}const other=bombs.find(q=>q.x===x&&q.y===y);if(other){due.push(other);break;}}
   for(const [x,y] of hit)flames.push({x,y,t:.52});
  }
  for(const p of players)if(p.alive&&flames.some(f=>f.x===p.x&&f.y===p.y)){p.alive=false;p.input=null;}
  const alive=players.filter(p=>p.alive);
  if(alive.length<2||time===0){clear();winner=alive.length===1?alive[0].id:null;if(winner!==null)alive[0].wins++;phase=players.some(p=>p.wins>=3)?'match-over':'round-over';for(const p of players){p.ready=false;p.input=null;}}
  emit(s);
 }
 function ready(s){if(players.length!==2||!players.every(p=>p.connected&&p.ready))return;if(phase==='paused'){phase='playing';players.forEach(p=>{p.ready=false;p.input=null;});last=s.now();schedule(s);emit(s);}else {if(phase==='match-over'){players.forEach(p=>p.wins=0);round=0;}begin(s);}}
 return {name:'Bomberman',
  onJoin(p,s){if(!players.some(q=>q.id===p.id)&&players.length<2)players.push({...p,wins:0,connected:true,ready:false,alive:true,input:null,cat:players.length?1:0});presence(s);},
  onPresence(s){presence(s);},
  onLeave(p,s){players=players.filter(q=>q.id!==p.id);clear();phase='lobby';players.forEach(q=>{q.ready=false;q.input=null;});emit(s);},
  onMessage(p,msg,s){const me=players.find(q=>q.id===p.id);if(msg.type==='BM_SYNC'){presence(s);return;}if(!me)return;
   if(msg.type==='BM_READY'&&phase!=='playing'){me.ready=true;presence(s);ready(s);emit(s);}
   if(msg.type==='BM_INPUT'&&phase==='playing'&&me.alive){me.input=Object.hasOwn(DIR,msg.direction)?msg.direction:null;me.lastInput=s.now();}
   if(msg.type==='BM_BOMB'&&phase==='playing'&&me.alive&&bombs.filter(b=>b.owner===me.id).length<me.capacity&&!bombs.some(b=>b.x===me.x&&b.y===me.y)){bombs.push({x:me.x,y:me.y,t:2.05,range:me.range,owner:me.id});emit(s);}
   if(msg.type==='BM_CAT'&&phase!=='playing'&&Number.isInteger(msg.cat)&&msg.cat>=0&&msg.cat<20){me.cat=msg.cat;emit(s);}
  },
  dispose(){clear();},
  _test:{step,snapshot,begin}
 };
}
module.exports={createBombermanGame};
