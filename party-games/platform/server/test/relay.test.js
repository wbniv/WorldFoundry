// Platform relay — behaviour tests. Uses node:test (built-in; no Jest / mocha).
//
//   node --test test/
//
// Each test spins up an isolated server on an ephemeral port with quiet=true
// so output stays clean.

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const WebSocket = require('ws');

const { createServer, MAX_NAME_LEN, MAX_MESSAGE_BYTES } = require('../createServer');

// ───────── helpers ──────────────────────────────────────────────────────────

function withServer(fn) {
  return async () => {
    const srv = await createServer({ port: 0, quiet: true });
    const base = `ws://localhost:${srv.port}/ws`;
    try {
      await fn({ base, port: srv.port, ...srv });
    } finally {
      await srv.close();
    }
  };
}

/** Open a ws client; resolves once the socket is OPEN.
 *
 * `waitFor(predicate, { timeoutMs, sinceIndex })` — `sinceIndex` (default 0)
 * skips messages that arrived before that index. Snapshot `client.messages.length`
 * before an action, then pass it in to wait strictly for *new* messages.
 */
function openClient(url) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    const messages = [];
    ws.on('message', (data) => {
      try { messages.push(JSON.parse(data.toString())); } catch { /* drop */ }
    });
    ws.on('error', reject);
    ws.once('open', () => resolve({ ws, messages, waitFor }));

    function waitFor(predicate, opts = {}) {
      const timeoutMs = opts.timeoutMs ?? 1000;
      const sinceIndex = opts.sinceIndex ?? 0;
      return new Promise((resolveW, rejectW) => {
        let settled = false;
        const scanFrom = (start) => {
          for (let i = start; i < messages.length; i++) {
            if (predicate(messages[i])) {
              if (settled) return;
              settled = true;
              clearTimeout(to);
              ws.off('message', listener);
              return resolveW(messages[i]);
            }
          }
        };
        const listener = () => scanFrom(sinceIndex);
        ws.on('message', listener);
        const to = setTimeout(() => {
          if (settled) return;
          settled = true;
          ws.off('message', listener);
          rejectW(new Error(`timeout waiting for message (since=${sinceIndex}); saw: ${JSON.stringify(messages.slice(sinceIndex))}`));
        }, timeoutMs);
        scanFrom(sinceIndex);
      });
    }
  });
}

function send(ws, msg) { ws.send(JSON.stringify(msg)); }
function close(ws) {
  return new Promise((res) => { ws.once('close', res); ws.close(); });
}

// ───────── tests ────────────────────────────────────────────────────────────

test('receiver gets empty STATE on HELLO', withServer(async ({ base }) => {
  const recv = await openClient(base);
  send(recv.ws, { type: 'HELLO', role: 'receiver', room: 'ABCD' });
  const state = await recv.waitFor(m => m.type === 'STATE');
  assert.deepEqual(state.players, []);
  await close(recv.ws);
}));

test('controller HELLO yields WELCOME and broadcasts STATE', withServer(async ({ base }) => {
  const recv = await openClient(base);
  send(recv.ws, { type: 'HELLO', role: 'receiver', room: 'ABCD' });
  await recv.waitFor(m => m.type === 'STATE');

  const alice = await openClient(base);
  send(alice.ws, { type: 'HELLO', role: 'controller', name: 'Alice', room: 'ABCD' });
  const welcome = await alice.waitFor(m => m.type === 'WELCOME');
  assert.equal(welcome.id, 1);
  assert.equal(welcome.name, 'Alice');

  const stateBroadcast = await recv.waitFor(m => m.type === 'STATE' && m.players.length === 1);
  assert.deepEqual(stateBroadcast.players, [{ id: 1, name: 'Alice' }]);

  await close(alice.ws);
  await close(recv.ws);
}));

test('PING from controller yields PONG to everyone with client+server ts', withServer(async ({ base }) => {
  const recv = await openClient(base);
  send(recv.ws, { type: 'HELLO', role: 'receiver', room: 'ABCD' });
  const alice = await openClient(base);
  send(alice.ws, { type: 'HELLO', role: 'controller', name: 'Alice', room: 'ABCD' });
  await alice.waitFor(m => m.type === 'WELCOME');

  const t0 = Date.now();
  send(alice.ws, { type: 'PING', clientTs: t0 });

  const pongAtReceiver = await recv.waitFor(m => m.type === 'PONG');
  assert.equal(pongAtReceiver.from, 1);
  assert.equal(pongAtReceiver.name, 'Alice');
  assert.equal(pongAtReceiver.clientTs, t0);
  assert.ok(pongAtReceiver.serverTs >= t0, 'serverTs should be ≥ clientTs');
  assert.ok(pongAtReceiver.serverTs < t0 + 5000, 'serverTs should be reasonable');

  const pongAtAlice = await alice.waitFor(m => m.type === 'PONG');
  assert.equal(pongAtAlice.from, 1);

  await close(alice.ws); await close(recv.ws);
}));

test('disconnect broadcasts updated STATE without the departed player', withServer(async ({ base }) => {
  const recv = await openClient(base);
  send(recv.ws, { type: 'HELLO', role: 'receiver', room: 'ABCD' });

  const alice = await openClient(base);
  send(alice.ws, { type: 'HELLO', role: 'controller', name: 'Alice', room: 'ABCD' });
  const bob = await openClient(base);
  send(bob.ws, { type: 'HELLO', role: 'controller', name: 'Bob', room: 'ABCD' });
  await recv.waitFor(m => m.type === 'STATE' && m.players.length === 2);

  const sinceIndex = recv.messages.length;
  await close(alice.ws);
  const stateAfterLeave = await recv.waitFor(
    m => m.type === 'STATE' && m.players.length === 1,
    { sinceIndex },
  );
  assert.deepEqual(stateAfterLeave.players, [{ id: 2, name: 'Bob' }]);

  await close(bob.ws); await close(recv.ws);
}));

test('PING from unregistered socket is ignored', withServer(async ({ base }) => {
  const recv = await openClient(base);
  send(recv.ws, { type: 'HELLO', role: 'receiver', room: 'ABCD' });
  await recv.waitFor(m => m.type === 'STATE');

  const anon = await openClient(base);
  send(anon.ws, { type: 'PING', clientTs: Date.now() });     // no HELLO first
  await new Promise(r => setTimeout(r, 100));                // allow stray broadcast to arrive
  assert.equal(recv.messages.filter(m => m.type === 'PONG').length, 0,
               'receiver should not have seen a PONG from an anon socket');

  await close(anon.ws); await close(recv.ws);
}));

test('malformed JSON does not crash or leak state', withServer(async ({ base }) => {
  const recv = await openClient(base);
  send(recv.ws, { type: 'HELLO', role: 'receiver', room: 'ABCD' });
  await recv.waitFor(m => m.type === 'STATE');

  const garbled = await openClient(base);
  garbled.ws.send('{not valid json');
  garbled.ws.send('42');           // valid json but not an object
  garbled.ws.send('[]');           // array
  garbled.ws.send(JSON.stringify({ /* no type */ name: 'ghost', room: 'ABCD' }));
  send(garbled.ws, { type: 'UNKNOWN_FANCY_TYPE' });

  // Now a legit HELLO must still work.
  send(garbled.ws, { type: 'HELLO', role: 'controller', name: 'Eve', room: 'ABCD' });
  const welcome = await garbled.waitFor(m => m.type === 'WELCOME');
  assert.equal(welcome.name, 'Eve');

  await close(garbled.ws); await close(recv.ws);
}));

test('name is truncated to MAX_NAME_LEN characters', withServer(async ({ base }) => {
  const client = await openClient(base);
  const long = 'x'.repeat(MAX_NAME_LEN + 20);
  send(client.ws, { type: 'HELLO', role: 'controller', name: long, room: 'ABCD' });
  const welcome = await client.waitFor(m => m.type === 'WELCOME');
  assert.equal(welcome.name.length, MAX_NAME_LEN);
  assert.equal(welcome.name, 'x'.repeat(MAX_NAME_LEN));
  await close(client.ws);
}));

test('repeated HELLO from same socket is ignored (role stays first-set)', withServer(async ({ base }) => {
  const client = await openClient(base);
  send(client.ws, { type: 'HELLO', role: 'controller', name: 'Alice', room: 'ABCD' });
  await client.waitFor(m => m.type === 'WELCOME');

  // Attempt to re-HELLO as receiver — should be silently ignored.
  send(client.ws, { type: 'HELLO', role: 'receiver', room: 'ABCD' });
  await new Promise(r => setTimeout(r, 80));
  // No second WELCOME / no fresh STATE snapshot should be sent to Alice.
  const welcomes = client.messages.filter(m => m.type === 'WELCOME');
  assert.equal(welcomes.length, 1, 'only one WELCOME expected');

  await close(client.ws);
}));

test('HELLO with unknown role ignored; client stays anonymous (PING drops)', withServer(async ({ base }) => {
  const recv = await openClient(base);
  send(recv.ws, { type: 'HELLO', role: 'receiver', room: 'ABCD' });
  await recv.waitFor(m => m.type === 'STATE');

  const spectator = await openClient(base);
  send(spectator.ws, { type: 'HELLO', role: 'spectator', room: 'ABCD' });   // unknown role
  send(spectator.ws, { type: 'PING', clientTs: Date.now() }); // should be rejected since not a controller
  await new Promise(r => setTimeout(r, 100));
  assert.equal(recv.messages.filter(m => m.type === 'PONG').length, 0);

  await close(spectator.ws); await close(recv.ws);
}));

test('oversize payload is rejected by ws (closes connection)', withServer(async ({ base }) => {
  const client = await openClient(base);
  // Enqueue a payload larger than maxPayload; ws library closes the socket.
  const bigName = 'y'.repeat(MAX_MESSAGE_BYTES);
  const oversize = JSON.stringify({ type: 'HELLO', role: 'controller', name: bigName });
  assert.ok(oversize.length > MAX_MESSAGE_BYTES, 'setup: payload genuinely larger than max');

  const closed = new Promise(r => client.ws.once('close', r));
  client.ws.send(oversize);
  await closed;
  // Success = socket closed on its own; no crash.
}));

test('two rooms on one server are fully isolated', withServer(async ({ base }) => {
  // Room ABCD.
  const recvA = await openClient(base);
  send(recvA.ws, { type: 'HELLO', role: 'receiver', room: 'ABCD' });
  await recvA.waitFor(m => m.type === 'WELCOME_RECEIVER' && m.room === 'ABCD');
  const aliceA = await openClient(base);
  send(aliceA.ws, { type: 'HELLO', role: 'controller', name: 'Alice', room: 'ABCD' });
  await aliceA.waitFor(m => m.type === 'WELCOME' && m.room === 'ABCD');

  // Room WXYZ.
  const recvB = await openClient(base);
  send(recvB.ws, { type: 'HELLO', role: 'receiver', room: 'WXYZ' });
  await recvB.waitFor(m => m.type === 'WELCOME_RECEIVER' && m.room === 'WXYZ');
  const aliceB = await openClient(base);
  send(aliceB.ws, { type: 'HELLO', role: 'controller', name: 'Alice', room: 'WXYZ' });
  const welcomeB = await aliceB.waitFor(m => m.type === 'WELCOME' && m.room === 'WXYZ');
  // Each room starts its own player-id counter.
  assert.equal(welcomeB.id, 1);

  // Alice-A pings — only ABCD should see it.
  send(aliceA.ws, { type: 'PING', clientTs: Date.now() });
  await recvA.waitFor(m => m.type === 'PONG');
  await new Promise(r => setTimeout(r, 80));  // let any stray traffic arrive
  assert.equal(recvB.messages.filter(m => m.type === 'PONG').length, 0,
    'PONG from room ABCD must not reach room WXYZ');

  await close(aliceA.ws); await close(recvA.ws);
  await close(aliceB.ws); await close(recvB.ws);
}));

test('HELLO without a room rejects controllers with NEED_ROOM', withServer(async ({ base }) => {
  const ctl = await openClient(base);
  send(ctl.ws, { type: 'HELLO', role: 'controller', name: 'Nomad' });
  const need = await ctl.waitFor(m => m.type === 'NEED_ROOM');
  assert.ok(need);
  await close(ctl.ws);
}));

test('HELLO with malformed room code rejects with BAD_ROOM', withServer(async ({ base }) => {
  const ctl = await openClient(base);
  send(ctl.ws, { type: 'HELLO', role: 'controller', name: 'Typo', room: 'abc1' });  // has digit + lowercase; also too short
  const bad = await ctl.waitFor(m => m.type === 'BAD_ROOM');
  assert.ok(bad);
  await close(ctl.ws);
}));

test('receiver with no room gets a server-generated code back in WELCOME_RECEIVER', withServer(async ({ base }) => {
  const recv = await openClient(base);
  send(recv.ws, { type: 'HELLO', role: 'receiver' });  // no room
  const welcome = await recv.waitFor(m => m.type === 'WELCOME_RECEIVER');
  assert.ok(welcome.room, 'server should assign a code');
  assert.match(welcome.room, /^[ABCDEFGHJKLMNPRSTUVWXYZ]{4}$/, 'code matches allowed alphabet');
  await close(recv.ws);
}));

test('session-id reconnect within grace: resumes same player id, WELCOME.resumed=true', withServer(async ({ base }) => {
  const session = 'testsession12345';  // passes SESSION_ID_RE (8-64 [A-Za-z0-9_-])

  const first = await openClient(base);
  send(first.ws, { type: 'HELLO', role: 'controller', name: 'Alice', room: 'ABCD', sessionId: session });
  const w1 = await first.waitFor(m => m.type === 'WELCOME');
  assert.equal(w1.resumed, false);
  assert.equal(w1.sessionId, session);
  const originalId = w1.id;

  // Disconnect first ws. Room holds the session in grace; open a second ws
  // with the same sessionId and watch it resume.
  await close(first.ws);

  const second = await openClient(base);
  send(second.ws, { type: 'HELLO', role: 'controller', name: 'Alice', room: 'ABCD', sessionId: session });
  const w2 = await second.waitFor(m => m.type === 'WELCOME');
  assert.equal(w2.id, originalId, 'same player id preserved across reconnect');
  assert.equal(w2.resumed, true);
  await close(second.ws);
}));

test('session-id reconnect: a DIFFERENT sessionId gets a fresh player id', withServer(async ({ base }) => {
  const firstSession  = 'alice-session-aaa1';
  const secondSession = 'alice-session-bbb2';

  const first = await openClient(base);
  send(first.ws, { type: 'HELLO', role: 'controller', name: 'Alice', room: 'ABCD', sessionId: firstSession });
  const w1 = await first.waitFor(m => m.type === 'WELCOME');
  await close(first.ws);

  const second = await openClient(base);
  send(second.ws, { type: 'HELLO', role: 'controller', name: 'Alice', room: 'ABCD', sessionId: secondSession });
  const w2 = await second.waitFor(m => m.type === 'WELCOME');
  assert.notEqual(w2.id, w1.id, 'different session → different player id');
  assert.equal(w2.resumed, false);
  await close(second.ws);
}));

test('session-id reconnect: missing sessionId falls back to old behavior (no resume)', withServer(async ({ base }) => {
  // Keep a receiver attached so the room isn't destroyed when the controller
  // disconnects — that way the second HELLO lands in the same room, and any
  // session-based resume would be visible.
  const recv = await openClient(base);
  send(recv.ws, { type: 'HELLO', role: 'receiver', room: 'ABCD' });
  await recv.waitFor(m => m.type === 'WELCOME_RECEIVER');

  const first = await openClient(base);
  send(first.ws, { type: 'HELLO', role: 'controller', name: 'Nomad', room: 'ABCD' });
  const w1 = await first.waitFor(m => m.type === 'WELCOME');
  assert.equal(w1.sessionId, null);
  assert.equal(w1.resumed, false);
  await close(first.ws);
  await recv.waitFor(m => m.type === 'STATE' && m.players.length === 0);

  const second = await openClient(base);
  send(second.ws, { type: 'HELLO', role: 'controller', name: 'Nomad', room: 'ABCD' });
  const w2 = await second.waitFor(m => m.type === 'WELCOME');
  assert.equal(w2.resumed, false, 'no session → server cannot resume, always treated as fresh');
  assert.notEqual(w2.id, w1.id, 'with room preserved, new player gets a fresh id (nextPlayerId advances)');
  await close(second.ws); await close(recv.ws);
}));

test('after grace expires, session slot is released and reconnect is treated as fresh', async () => {
  // Short grace so the test runs fast; receiver attached keeps room alive
  // across the grace expiry so we can observe the id advance (without a
  // receiver the room would destroy itself and nextPlayerId would reset).
  const srv = await createServer({ port: 0, quiet: true, sessionGraceMs: 50 });
  const base = `ws://localhost:${srv.port}/ws`;
  try {
    const recv = await openClient(base);
    send(recv.ws, { type: 'HELLO', role: 'receiver', room: 'ABCD' });
    await recv.waitFor(m => m.type === 'WELCOME_RECEIVER');

    const session = 'short-grace-sess';
    const first = await openClient(base);
    send(first.ws, { type: 'HELLO', role: 'controller', name: 'Ghost', room: 'ABCD', sessionId: session });
    const w1 = await first.waitFor(m => m.type === 'WELCOME');
    await recv.waitFor(m => m.type === 'STATE' && m.players.length === 1);
    const sinceIndex = recv.messages.length;
    await close(first.ws);
    // Wait past grace → finalizePlayerLeave fires → STATE with players=[].
    await recv.waitFor(
      m => m.type === 'STATE' && m.players.length === 0,
      { sinceIndex, timeoutMs: 1000 },
    );

    const second = await openClient(base);
    send(second.ws, { type: 'HELLO', role: 'controller', name: 'Ghost', room: 'ABCD', sessionId: session });
    const w2 = await second.waitFor(m => m.type === 'WELCOME');
    assert.equal(w2.resumed, false, 'grace expired → server treats reconnect as fresh');
    assert.notEqual(w2.id, w1.id, 'fresh id allocated (nextPlayerId advanced)');
    await close(second.ws); await close(recv.ws);
  } finally { await srv.close(); }
});

test('grace window keeps the room alive even after all sockets drop', withServer(async ({ base, rooms }) => {
  const session = 'grace-test-session1';
  const first = await openClient(base);
  send(first.ws, { type: 'HELLO', role: 'controller', name: 'Solo', room: 'ABCD', sessionId: session });
  await first.waitFor(m => m.type === 'WELCOME');
  assert.equal(rooms.size, 1, 'room present');

  await close(first.ws);
  // Even though we were the only occupant, the grace window should keep the
  // room alive. (Real SESSION_GRACE_MS is 20 s; we only need ~50 ms here to
  // observe the immediate-post-close state.)
  await new Promise(r => setTimeout(r, 50));
  assert.equal(rooms.size, 1, 'room still present during grace');

  // Reconnect resumes the same slot — confirms the room really was preserved.
  const second = await openClient(base);
  send(second.ws, { type: 'HELLO', role: 'controller', name: 'Solo', room: 'ABCD', sessionId: session });
  const w2 = await second.waitFor(m => m.type === 'WELCOME');
  assert.equal(w2.resumed, true);
  await close(second.ws);
}));

test('static file routing — index + sibling assets + 404', withServer(async ({ port }) => {
  const fetch = (path) => new Promise((resolve, reject) => {
    http.get(`http://localhost:${port}${path}`, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => resolve({
        status: res.statusCode,
        contentType: res.headers['content-type'],
        body: Buffer.concat(chunks),
      }));
    }).on('error', reject);
  });

  const receiver = await fetch('/receiver');
  assert.equal(receiver.status, 200);
  assert.match(receiver.contentType, /text\/html/);
  assert.ok(receiver.body.length > 0);

  // These are the paths the browser requests after loading /receiver:
  // <script src="receiver.js"> → /receiver.js,  <link href="receiver.css"> → /receiver.css.
  const recvJs = await fetch('/receiver.js');
  assert.equal(recvJs.status, 200, 'receiver.js sibling path must be served');
  assert.match(recvJs.contentType, /text\/javascript/);
  assert.ok(recvJs.body.length > 100);

  const recvCss = await fetch('/receiver.css');
  assert.equal(recvCss.status, 200);
  assert.match(recvCss.contentType, /text\/css/);

  const ctrlJs = await fetch('/controller.js');
  assert.equal(ctrlJs.status, 200, 'controller.js sibling path must be served');
  assert.match(ctrlJs.contentType, /text\/javascript/);

  const ctrlCss = await fetch('/controller.css');
  assert.equal(ctrlCss.status, 200);

  // Under-directory path still works (legacy form).
  const nested = await fetch('/receiver/receiver.js');
  assert.equal(nested.status, 200);

  const missing = await fetch('/does-not-exist.js');
  assert.equal(missing.status, 404);
}));
