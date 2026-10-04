const G = require('./client/geometry');
const {scoreBoard, finalScore} = require('./scoring');
const defaultCards = require('./cards');
const emptyBoard = () => Array(81).fill(0);
const copy = value => JSON.parse(JSON.stringify(value));
function createPatchworkGame(options = {}) {
  const cards = options.cards || defaultCards;
  const state = {phase:'LOBBY', game:0, stage:0, round:0, turn:0, circle:[], token:-1,
    die:null, players:new Map(), deck:[], ceremony:0, lastContext:null};
  function active() {return [...state.players.values()].filter(p => !p.withdrawn);}
  function connected(services, id) {return services.getPlayers().some(p => p.id === id && p.connected !== false);}
  function host(services) {return services.getPlayers().find(p => p.connected !== false)?.id;}
  function stageId() {return `${state.game}:${state.stage}`;}
  function shuffled(list, services) {
    const result = list.slice();
    for(let i=result.length-1;i>0;i--) {const j=Math.min(i,Math.floor(services.random()*(i+1)));[result[i],result[j]]=[result[j],result[i]];}
    return result;
  }
  function publicState(services) {
    return {type:'PD_STATE',phase:state.phase,stage:stageId(),round:state.round,turn:state.turn,
      circle:state.circle,token:state.token,die:state.die,hostId:host(services),
      receiverOnline:services.getReceiverCount?.() > 0,provenance:cards.provenance,
      context:state.phase==='SCORING' ? state.lastContext : null,
      players:[...state.players.values()].map(p => ({id:p.id,name:p.name,ready:p.ready,
        connected:connected(services,p.id),withdrawn:p.withdrawn,scores:p.scores,
        ...(['TURN_RESULTS','FINISHED'].includes(state.phase) ? {board:p.board.slice()} : {}),
        ...(state.phase==='FINISHED' ? {final:finalScore(p)} : {})})),
      ceremony:state.ceremony,waiting:services.getPlayers().filter(p=>!state.players.has(p.id))};
  }
  function privateState(p) {return {type:'PD_PRIVATE',stage:stageId(),id:p.id,board:p.board,
    preview:p.preview,used:p.used,previewUsed:p.previewUsed,draft:p.draft,revision:p.revision,
    start:p.start,ready:p.ready,lastPassed:p.lastPassed};}
  function publish(services) {
    services.broadcast(publicState(services));
    for(const p of state.players.values()) services.sendTo(p.id, privateState(p));
  }
  function resetStage() {
    state.stage++;
    for(const p of active()) {p.ready=false;p.draft=null;p.preview=p.board.slice();p.previewUsed={...p.used};p.revision=0;p.actionIds=new Set();}
  }
  function context() {
    return {circle:copy(state.circle),token:state.token,final:state.round===3 && state.turn===6};
  }
  function beginTurn(services) {
    state.phase='PLACING';
    if(state.round===3 && state.turn===6) {state.die=null;state.token=-1;}
    else {state.die=1+Math.min(2,Math.floor(services.random()*3));state.token=(state.token+state.die)%state.circle.length;}
    resetStage();
  }
  function commit() {
    for(const p of active()) {p.board=p.preview.slice();p.used={...p.previewUsed};}
  }
  function validateDraft(p,msg) {
    let board=p.board.slice(), used={...p.used};
    const take = (type,repeat) => {
      if(repeat) {if(!used[type] || used.repeat) throw new Error('Repeat requires a previously used action and an unused repeat.');used.repeat=true;}
      else {if(used[type]) throw new Error('That special action has already been used.');used[type]=true;}
    };
    const placement=msg.placement;
    if(state.phase==='STARTING' && !placement) throw new Error('Place your starting patch first.');
    if(placement) {
      if(!Number.isInteger(placement.rotation) || placement.rotation<0 || placement.rotation>3 || typeof placement.flip!=='boolean') throw new Error('Invalid patch orientation.');
      let patch;
      if(state.phase==='STARTING') {
        if(placement.cardId!==p.start.id || placement.cut || placement.neighbor) throw new Error('Use your starting patch.');
        patch=p.start;
      } else {
        const ctx=state.phase==='SCORING' ? state.lastContext : context();
        if(state.phase==='SCORING' && (!p.lastPassed || (!placement.neighbor && !placement.cut))) throw new Error('During scoring, only a special patch after a pass is available.');
        const chosen=ctx.circle.find(c=>c.id===placement.cardId);
        if(!chosen) throw new Error('That patch is not available.');
        if(ctx.final) {if(placement.neighbor) throw new Error('Final choice already allows any remaining patch.');}
        else if(placement.neighbor) {
          const allowed=[ctx.circle[(ctx.token+ctx.circle.length-1)%ctx.circle.length].id,ctx.circle[(ctx.token+1)%ctx.circle.length].id];
          if(!allowed.includes(placement.cardId)) throw new Error('Choose an immediate neighbor.');
          take('neighbor',!!placement.repeatNeighbor);
        } else if(chosen.id!==ctx.circle[ctx.token].id) throw new Error('Use the selected patch or the neighbor action.');
        patch=chosen;
      }
      let cells=patch.cells;
      if(placement.cut) {
        const {axis,at,side}=placement.cut;
        const match=G.cuts(cells).find(c=>c.axis===axis && c.at===at && c.side===side);
        if(!match) throw new Error('The cut must make exactly two connected pieces.');
        take('cut',!!placement.repeatCut);cells=match.cells;
      }
      cells=G.orient(cells,placement.rotation,placement.flip);
      board=G.place(board,cells,placement.x,placement.y,state.stage+1);
    }
    const singles=msg.singles || [];
    if(!Array.isArray(singles) || singles.length>2) throw new Error('Invalid extra cells.');
    for(const single of singles) {take('single',!!single.repeat);board=G.place(board,[[0,0]],single.x,single.y,state.stage+1);}
    return {board,used};
  }
  function advance(services) {
    if(!active().length) throw new Error('No active players remain.');
    if(!(services.getReceiverCount?.()>0)) throw new Error('Reconnect the shared display before advancing.');
    if(active().some(p=>!connected(services,p.id))) throw new Error('Wait for disconnected players, or withdraw their seats.');
    if(['STARTING','PLACING','SCORING'].includes(state.phase) && active().some(p=>!p.ready)) throw new Error('Everyone must be ready.');
    if(state.phase==='STARTING') {commit();state.round=1;state.turn=1;beginTurn(services);}
    else if(state.phase==='PLACING') {
      state.lastContext=context();
      commit();for(const p of active()) p.lastPassed=!p.draft?.placement;
      if(state.token>=0) {state.circle.splice(state.token,1);state.token=(state.token-1+state.circle.length)%state.circle.length;}
      state.phase='TURN_RESULTS';resetStage();
    } else if(state.phase==='TURN_RESULTS') {
      if(state.turn===6) {state.phase='SCORING';resetStage();}
      else {state.turn++;beginTurn(services);}
    } else if(state.phase==='SCORING') {
      commit();for(const p of active()) p.scores.push(scoreBoard(p.board));
      state.phase=state.round===3?'FINISHED':'ROUND_RESULTS';state.ceremony=0;resetStage();
    } else if(state.phase==='ROUND_RESULTS') {
      // The remaining cards immediately follow the token, retaining clockwise order.
      const after=(state.token+1)%state.circle.length;
      state.circle=[...state.circle.slice(after),...state.circle.slice(0,after),...state.deck.splice(0,6)];
      state.token=-1;state.round++;state.turn=1;beginTurn(services);
    } else throw new Error('Cannot advance in this phase.');
  }
  function onMessage(player,msg,services) {
    if(!msg.type.startsWith('PD_')) return;
    try {
      if(msg.type==='PD_REQUEST') {publish(services);return;}
      if(msg.type==='PD_START') {
        if(player.id!==host(services) || !['LOBBY','FINISHED'].includes(state.phase)) throw new Error('Only the host can start a new game.');
        const roster=services.getPlayers().filter(p=>p.connected!==false);
        if(roster.length<1 || roster.length>6) throw new Error('Choose one to six players.');
        if(!(services.getReceiverCount?.()>0)) throw new Error('Connect the shared display first.');
        state.game++;state.players.clear();state.deck=shuffled(cards.patches,services);state.circle=state.deck.splice(0,8);
        state.token=Math.min(7,Math.floor(services.random()*8));state.round=0;state.turn=0;state.die=null;state.lastContext=null;
        const starters=shuffled(cards.starts,services);
        roster.forEach((r,i)=>state.players.set(r.id,{...r,start:starters[i],board:emptyBoard(),scores:[],used:{neighbor:false,single:false,cut:false,repeat:false},withdrawn:false,lastPassed:false}));
        state.phase='STARTING';resetStage();publish(services);return;
      }
      if(msg.stage!==stageId()) throw new Error('This turn has changed. Refresh your view and try again.');
      if(msg.type==='PD_ADVANCE') {if(player.id!==host(services)) throw new Error('Only the host can advance.');advance(services);}
      else if(msg.type==='PD_CEREMONY') {
        if(player.id!==host(services) || state.phase!=='FINISHED') throw new Error('Only the host controls the final presentation.');
        const max=active().length*6;
        if(!Number.isInteger(msg.cursor)||msg.cursor<0||msg.cursor>max) throw new Error('Invalid presentation step.');
        state.ceremony=msg.cursor;
      } else if(msg.type==='PD_WITHDRAW') {
        if(player.id!==host(services)) throw new Error('Only the host can withdraw a seat.');
        const p=state.players.get(msg.playerId);if(!p || connected(services,p.id)) throw new Error('Only disconnected seats can be withdrawn.');p.withdrawn=true;
      } else if(msg.type==='PD_DRAFT') {
        const p=state.players.get(player.id);
        if(!p || p.withdrawn || !['STARTING','PLACING','SCORING'].includes(state.phase)) throw new Error('You are not placing this turn.');
        if(typeof msg.actionId!=='string' || msg.actionId.length>80 || !msg.actionId.length) throw new Error('Missing action identity.');
        if(p.actionIds.has(msg.actionId)) {services.sendTo(p.id,privateState(p));return;}
        if(!Number.isInteger(msg.revision) || msg.revision!==p.revision+1) throw new Error('Your draft changed. Use the latest view.');
        const result=validateDraft(p,msg);
        p.preview=result.board;p.previewUsed=result.used;p.ready=!!msg.ready;p.draft=copy({placement:msg.placement||null,singles:msg.singles||[],ready:p.ready});
        p.revision=msg.revision;p.actionIds.add(msg.actionId);
      } else return;
      publish(services);
    } catch(error) {services.sendTo(player.id,{type:'PD_ERROR',message:error.message});}
  }
  return {name:'patchwork',onMessage,
    onJoin:(p,s)=>publish(s),onReconnect:(p,s)=>publish(s),onPresence:s=>publish(s),
    onReceiverReady:s=>publish(s),onReceiverMessage:(msg,s)=>{if(msg.type==='PD_REQUEST')publish(s);},
    onLeave:(p,s)=>{const seat=state.players.get(p.id);if(seat)seat.withdrawn=true;publish(s);},
    _debugState:()=>state};
}
module.exports={createPatchworkGame};
