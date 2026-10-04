// Explicit automated-check builds only. These simulated phones run inside the
// owned TV app session; no external physical phone is controlled by this driver.
import {G} from './ui.js';
export function runDeviceCheck(ctx,room) {
  const params=new URLSearchParams(location.search);
  const visual=params.get('visualCheck')==='1';
  const requested=Number(params.get('players'));
  const count=visual?6:Number.isInteger(requested)&&requested>=2&&requested<=6?requested:2+Math.floor(Math.random()*5);
  const names=visual?['Alexandria Montgomery Longname','Christopher Wellington Longname','Madeleine Summerfield Longname','Sebastian Winterbottom Longname','Genevieve Featherstone Longname','Maximilian Butterworth Longname']:Array.from({length:count},(_,i)=>`Device check ${String.fromCharCode(65+i)}`);
  console.info(`PD_AUTOPLAY_PLAYERS ${names.length}`);
  const bots=[],timers=new Set(),handled=new Set();let shared=null,stopped=false;
  function later(key,delay,fn) {
    if(stopped||handled.has(key))return;handled.add(key);
    const timer=setTimeout(()=>{timers.delete(timer);if(!stopped)fn();},delay);timers.add(timer);
  }
  const url=(location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws';
  function send(bot,type,fields={}) {if(bot.ws.readyState===WebSocket.OPEN)bot.ws.send(JSON.stringify({type,stage:shared?.stage,...fields}));}
  function host(){return bots.find(b=>b.id===shared?.hostId);}
  function move() {
    if(!shared||!shared.receiverOnline||bots.length!==names.length||bots.some(b=>!b.id))return;
    const h=host();if(!h)return;
    if(shared.phase==='LOBBY')later('start',visual?8000:1500,()=>send(h,'PD_START'));
    else if(['STARTING','PLACING','SCORING'].includes(shared.phase)) {
      for(const bot of bots) {
        if(bot.private?.stage!==shared.stage||bot.private.ready)continue;
        later(`draft:${bot.id}:${shared.stage}`,visual?700+bots.indexOf(bot)*80:350,()=>{
          const p=bot.private;let placement=null;
          if(shared.phase==='STARTING')placement={cardId:p.start.id,...G.firstFit(p.board,p.start.cells)};
          if(shared.phase==='PLACING') {
            const choices=shared.token<0?shared.circle:[shared.circle[shared.token]];
            const chosen=choices.find(c=>G.firstFit(p.board,c.cells));
            if(chosen)placement={cardId:chosen.id,...G.firstFit(p.board,chosen.cells)};
          }
          send(bot,'PD_DRAFT',{placement,singles:[],ready:true,revision:p.revision+1,actionId:`check:${bot.id}:${shared.stage}`});
        });
      }
      if(shared.players.filter(p=>!p.withdrawn).length===names.length&&shared.players.every(p=>p.ready))later(`advance:${shared.stage}`,visual?500:350,()=>{
        send(h,'PD_ADVANCE');
      });
    } else if(shared.phase==='TURN_RESULTS') {
      later(`boards:${shared.stage}`,4000,()=>send(h,'PD_ADVANCE'));
    } else if(shared.phase==='ROUND_RESULTS')later(`results:${shared.stage}`,visual?2500:800,()=>send(h,'PD_ADVANCE'));
    else if(shared.phase==='FINISHED') {
      const count=shared.players.filter(p=>!p.withdrawn).length*6;
      for(let cursor=1;cursor<=count;cursor++)later(`ceremony:${cursor}`,cursor*(visual?750:1000),()=>send(h,'PD_CEREMONY',{cursor}));
      later('complete',count*(visual?750:1000)+250,()=>console.info('PD_DEVICE_CHECK_COMPLETE'));
    }
  }
  let lastOverview=null;
  const off=ctx.on('PD_STATE',s=>{
    shared=s;
    if(s.phase==='TURN_RESULTS'&&s.stage!==lastOverview) {
      lastOverview=s.stage;console.info(`PD_AUTOPLAY_BOARDS ${s.round}:${s.turn}`);
    }
    move();
  });
  for(const name of names) {
    const bot={ws:new WebSocket(url),id:null,private:null,name};bots.push(bot);
    bot.ws.onopen=()=>send(bot,'HELLO',{role:'controller',name,room});
    bot.ws.onmessage=event=>{
      let msg;try{msg=JSON.parse(event.data);}catch{return;}
      if(msg.type==='WELCOME'){bot.id=msg.id;send(bot,'PD_REQUEST');}
      if(msg.type==='PD_PRIVATE'){bot.private=msg;move();}
      if(msg.type==='PD_ERROR'){console.error('PD_DEVICE_CHECK_FAILED '+msg.message);stopped=true;}
    };
  }
  return ()=>{stopped=true;off();for(const timer of timers)clearTimeout(timer);for(const bot of bots)bot.ws.close();};
}
