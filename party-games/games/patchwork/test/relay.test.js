const {test}=require('node:test');
const assert=require('node:assert/strict');
const WebSocket=require('../../../platform/server/node_modules/ws');
const {createServer}=require('../../../platform/server/createServer');
const {createPatchworkGame}=require('../patchwork');
function client(port,hello) {
  const ws=new WebSocket(`ws://127.0.0.1:${port}/ws`),messages=[],waiters=[];
  ws.on('message',raw=>{const msg=JSON.parse(raw);messages.push(msg);for(const w of waiters.slice())if(w.predicate(msg)){waiters.splice(waiters.indexOf(w),1);clearTimeout(w.timer);w.resolve(msg);}});
  const wait=predicate=>{const found=messages.find(predicate);if(found)return Promise.resolve(found);return new Promise((resolve,reject)=>{const w={predicate,resolve,timer:setTimeout(()=>reject(new Error('Message timeout')),3000)};waiters.push(w);});};
  ws.on('open',()=>ws.send(JSON.stringify(hello)));
  return {ws,messages,wait,send:m=>ws.send(JSON.stringify(m))};
}
test('receiver mount handshake, late snapshot, reload credentials and presence',async t=>{
  const srv=await createServer({port:0,quiet:true,gameName:'patchwork',gameFactory:createPatchworkGame,presence:true,preferConnectedHost:true,serverSessionIds:true});
  t.after(()=>srv.close());
  const phone=client(srv.port,{type:'HELLO',role:'controller',room:'ABCD',name:'Host'});
  const welcome=await phone.wait(m=>m.type==='WELCOME');assert.ok(welcome.sessionId);
  phone.send({type:'PD_START'});await phone.wait(m=>m.type==='PD_ERROR'&&m.message.includes('display'));
  const tv=client(srv.port,{type:'HELLO',role:'receiver',room:'ABCD'});
  await tv.wait(m=>m.type==='WELCOME_RECEIVER');tv.send({type:'RECEIVER_READY'});
  await phone.wait(m=>m.type==='PD_STATE'&&m.receiverOnline);
  phone.send({type:'PD_START'});await phone.wait(m=>m.type==='PD_PRIVATE');
  // A fresh receiver must be able to request the running game's snapshot.
  const tv2=client(srv.port,{type:'HELLO',role:'receiver',room:'ABCD'});
  await tv2.wait(m=>m.type==='WELCOME_RECEIVER');tv2.send({type:'RECEIVER_READY'});
  const snapshot=await tv2.wait(m=>m.type==='PD_STATE'&&m.phase==='STARTING');assert.equal(snapshot.players.length,1);
  const resumed=client(srv.port,{type:'HELLO',role:'controller',room:'ABCD',sessionId:welcome.sessionId});
  const w=await resumed.wait(m=>m.type==='WELCOME');assert.equal(w.resumed,true);assert.equal(w.id,welcome.id);
  const privateState=await resumed.wait(m=>m.type==='PD_PRIVATE');assert.ok(privateState.start.cells.length===7);
  await new Promise(resolve=>resumed.ws.close()||resumed.ws.once('close',resolve));
  await tv2.wait(m=>m.type==='PD_STATE'&&m.players.some(p=>!p.connected));
  const qr=await fetch(`http://localhost:${srv.port}/join-qr?room=ABCD`);assert.equal(qr.status,200);assert.match(await qr.text(),/<svg/);
  const badQr=await fetch(`http://localhost:${srv.port}/join-qr?room=INVALID`);assert.equal(badQr.status,400);
});
