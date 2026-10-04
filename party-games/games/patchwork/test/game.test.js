const {test}=require('node:test');
const assert=require('node:assert/strict');
const G=require('../client/geometry');
const {scoreBoard,finalScore}=require('../scoring');
const {createPatchworkGame}=require('../patchwork');
function harness(count=2) {
  const game=createPatchworkGame();
  const roster=Array.from({length:count},(_,i)=>({id:i+1,name:`P${i+1}`,connected:true}));
  const messages=[];let receivers=1,serial=0;
  const services={getPlayers:()=>roster,getReceiverCount:()=>receivers,random:()=>.4,broadcast:m=>messages.push(m),sendTo:(id,m)=>messages.push({...m,to:id})};
  const state=game._debugState;
  const stage=()=>`${state().game}:${state().stage}`;
  const send=(id,type,fields={})=>{game.onMessage({id}, {type,stage:stage(),...fields},services);};
  const draft=(id,fields={})=>send(id,'PD_DRAFT',{actionId:`action-${++serial}`,revision:state().players.get(id).revision+1,ready:true,...fields});
  const error=()=>messages.at(-1)?.type==='PD_ERROR'?messages.at(-1).message:null;
  return {game,services,roster,messages,state,stage,send,draft,error,setReceivers:n=>{receivers=n;}};
}
function start(h) {
  h.send(1,'PD_START');
  for(const p of h.state().players.values()) {
    const f=G.firstFit(p.board,p.start.cells);
    h.draft(p.id,{placement:{cardId:p.start.id,...f}});
    assert.equal(h.error(),null);
  }
  h.send(1,'PD_ADVANCE');assert.equal(h.state().phase,'PLACING');
}
test('placement is atomic; orientations and cuts preserve expected geometry',()=>{
  const board=Array(81).fill(0);board[1]=1;
  assert.throws(()=>G.place(board,[[0,0],[1,0]],0,0,2));assert.equal(board[0],0);
  const shape=[[0,0],[1,0],[2,0],[0,1]];
  assert.deepEqual(G.orient(shape,4),G.normalize(shape));
  for(let r=0;r<4;r++)for(const f of [false,true])assert.equal(new Set(G.orient(shape,r,f).map(String)).size,4);
  const disconnectedCut=[[0,0],[1,0],[2,0],[0,1],[2,1]];
  assert.ok(!G.cuts(disconnectedCut).some(c=>c.axis===1&&c.at===1));
  assert.equal(G.fit(Array(81).fill(0),[[0,0],[1,0]],8,0),false);
});
test('scoring chooses best score rather than largest area and deducts empties',()=>{
  const b=Array(81).fill(0);
  for(let y=0;y<4;y++)for(let x=0;x<5;x++)b[y*9+x]=1;
  for(let y=0;y<3;y++)for(let x=0;x<8;x++)b[y*9+x]=1;
  const result=scoreBoard(b);assert.equal(result.score,17);assert.equal(result.width,5);assert.equal(result.height,4);
  assert.equal(scoreBoard(Array(81).fill(1)).score,81);
  assert.equal(scoreBoard(Array(81).fill(0)).score,0);
  assert.deepEqual(finalScore({board:Array(81).fill(0),scores:[{score:10},{score:20},{score:30}]}),{subtotal:60,empty:81,total:-21});
});
test('three rounds, no turn refills, final choice and historical scores',()=>{
  const h=harness();start(h);
  for(let round=1;round<=3;round++) {
    for(let turn=1;turn<=6;turn++) {
      const s=h.state();assert.equal(s.round,round);assert.equal(s.turn,turn);assert.equal(s.circle.length,9-turn);
      assert.ok(s.die>=1&&s.die<=3 || round===3&&turn===6&&s.die===null);
      if(round===3&&turn===6) {
        assert.equal(s.token,-1);
        for(const p of s.players.values()) {
          const chosen=s.circle.find(c=>G.firstFit(p.board,c.cells)),fit=G.firstFit(p.board,chosen.cells);
          h.draft(p.id,{placement:{cardId:chosen.id,...fit}});
        }
      } else for(const p of s.players.values())h.draft(p.id);
      h.send(1,'PD_ADVANCE');assert.equal(h.error(),null);
      assert.equal(h.state().phase,'TURN_RESULTS');
      assert.equal(h.state().turn,turn);
      h.send(1,'PD_ADVANCE');assert.equal(h.error(),null);
    }
    assert.equal(h.state().phase,'SCORING');
    for(const p of h.state().players.values())h.draft(p.id);
    h.send(1,'PD_ADVANCE');
    assert.equal(h.state().players.get(1).scores.length,round);
    if(round<3){assert.equal(h.state().phase,'ROUND_RESULTS');h.send(1,'PD_ADVANCE');}
  }
  assert.equal(h.state().phase,'FINISHED');
  const p=h.state().players.get(1);assert.notDeepEqual(p.scores[0].board,p.scores[2].board);
  h.send(1,'PD_CEREMONY',{cursor:12});assert.equal(h.state().ceremony,12);
  h.send(2,'PD_CEREMONY',{cursor:0});assert.match(h.error(),/host/);
});
test('readiness edits, stale stages, duplicate actions and host checks',()=>{
  const h=harness();start(h);
  h.send(2,'PD_ADVANCE');assert.match(h.error(),/host/);
  const s=h.state(),p=s.players.get(1);
  const message={type:'PD_DRAFT',stage:h.stage(),actionId:'duplicate',revision:1,ready:true,singles:[{x:8,y:8}]};
  h.game.onMessage({id:1},message,h.services);assert.equal(h.error(),null);
  h.game.onMessage({id:1},message,h.services);assert.equal(p.revision,1);
  h.draft(1,{ready:false});assert.equal(p.ready,false);assert.equal(p.preview[80],0);assert.equal(p.used.single,false);
  h.send(1,'PD_ADVANCE');assert.match(h.error(),/ready/);
  const previous=h.stage();h.draft(1);h.draft(2);h.send(1,'PD_ADVANCE');
  h.game.onMessage({id:1},{type:'PD_DRAFT',stage:previous,revision:1,actionId:'stale',ready:true},h.services);assert.match(h.error(),/changed/);
});
test('specials consume once, repeat a second time, drafts undo consumption',()=>{
  const h=harness(1);start(h);
  const p=h.state().players.get(1);
  h.draft(1,{singles:[{x:8,y:8},{x:7,y:8,repeat:true}]});assert.equal(h.error(),null);
  assert.equal(p.previewUsed.single,true);assert.equal(p.previewUsed.repeat,true);assert.equal(p.used.single,false);
  h.send(1,'PD_ADVANCE');assert.equal(p.used.single,true);assert.equal(p.used.repeat,true);
  h.send(1,'PD_ADVANCE');
  h.draft(1,{singles:[{x:6,y:8}]});assert.match(h.error(),/already/);
  assert.equal(p.board[78],0);
});
test('neighbor and cut use only valid cards and straight connected splits',()=>{
  const h=harness(1);start(h);
  const s=h.state(),p=s.players.get(1),neighbor=s.circle[(s.token+1)%s.circle.length],cut=G.cuts(neighbor.cells)[0],fit=G.firstFit(p.board,cut.cells);
  h.draft(1,{placement:{cardId:neighbor.id,neighbor:true,cut:{axis:cut.axis,at:cut.at,side:cut.side},...fit}});
  assert.equal(h.error(),null);assert.equal(p.previewUsed.neighbor,true);assert.equal(p.previewUsed.cut,true);
  const tokenId=s.circle[s.token].id;h.send(1,'PD_ADVANCE');assert.ok(!s.circle.some(c=>c.id===tokenId));assert.ok(s.circle.some(c=>c.id===neighbor.id));
});
test('disconnect pauses progression, connected host can withdraw, late join waits',()=>{
  const h=harness();start(h);h.draft(1);h.draft(2);
  h.setReceivers(0);h.send(1,'PD_ADVANCE');assert.match(h.error(),/display/);
  h.setReceivers(1);h.roster[1].connected=false;h.send(1,'PD_ADVANCE');assert.match(h.error(),/disconnected/);
  h.send(1,'PD_WITHDRAW',{playerId:2});h.send(1,'PD_ADVANCE');assert.equal(h.state().phase,'TURN_RESULTS');
  h.send(1,'PD_ADVANCE');assert.equal(h.state().turn,2);
  h.roster.push({id:3,name:'Late',connected:true});h.game.onJoin(h.roster[2],h.services);assert.equal(h.state().players.has(3),false);
});
test('turn overview exposes committed boards only and survives reconnects, with host/stage guards',()=>{
  for(let count=1;count<=6;count++) {
    const h=harness(count);start(h);
    const publicSnapshot=()=>h.messages.findLast(m=>m.type==='PD_STATE');
    assert.ok(publicSnapshot().players.every(p=>!('board' in p)));
    const p=h.state().players.get(1),chosen=h.state().circle[h.state().token];
    const fit=G.firstFit(p.board,chosen.cells),draftStage=h.stage();
    h.draft(1,{placement:{cardId:chosen.id,...fit}});
    const expected=p.preview.slice();
    assert.ok(publicSnapshot().players.every(p=>!('board' in p)),'draft boards must remain private');
    for(let id=2;id<=count;id++)h.draft(id);
    h.send(1,'PD_ADVANCE');
    assert.equal(h.state().phase,'TURN_RESULTS');assert.equal(h.state().turn,1);
    const snapshot=publicSnapshot();assert.equal(snapshot.players.length,count);
    assert.deepEqual(snapshot.players[0].board,expected);
    for(let id=2;id<=count;id++)assert.equal(snapshot.players[id-1].board.filter(Boolean).length,7,'pass preserves starting quilt');
    const overviewStage=h.stage();
    h.draft(1);assert.match(h.error(),/not placing/);
    h.game.onMessage({id:1},{type:'PD_ADVANCE',stage:draftStage},h.services);assert.match(h.error(),/changed/);
    if(count>1){h.send(2,'PD_ADVANCE');assert.match(h.error(),/host/);}
    h.game.onReceiverReady(h.services);assert.deepEqual(publicSnapshot().players,snapshot.players);
    h.game.onReconnect(h.roster[0],h.services);assert.equal(publicSnapshot().stage,overviewStage);
    h.setReceivers(0);h.send(1,'PD_ADVANCE');assert.match(h.error(),/display/);
    h.setReceivers(1);
    if(count>1){
      h.roster[0].connected=false;
      h.send(2,'PD_ADVANCE');assert.match(h.error(),/disconnected/);
      h.send(2,'PD_WITHDRAW',{playerId:1});h.send(2,'PD_ADVANCE');
    } else h.send(1,'PD_ADVANCE');
    assert.equal(h.state().phase,'PLACING');assert.equal(h.state().turn,2);
    h.game.onMessage({id:count>1?2:1},{type:'PD_ADVANCE',stage:overviewStage},h.services);assert.match(h.error(),/changed/);
    assert.ok(publicSnapshot().players.every(p=>!('board' in p)));
  }
});
