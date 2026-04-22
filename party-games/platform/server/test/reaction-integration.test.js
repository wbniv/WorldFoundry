// End-to-end: reaction-game plugin wired into createServer, exercised via
// real WebSocket clients on an ephemeral port. Uses injected clock + schedule
// so the 3-second scoring window and 2-9 s countdown fire instantly.

const test = require('node:test');
const assert = require('node:assert/strict');
const WebSocket = require('ws');

const { createServer } = require('../createServer');
const {
  createReactionGame,
  COUNTDOWN_MIN_MS,
  SCORING_WINDOW_MS,
} = require('../../../games/reaction/reaction');

// ───── fake clock + schedule ───────────────────────────────────────────────

function makeFakeClock(startMs = 1_000_000) {
  let time = startMs;
  const queue = [];  // { at, fn, id }
  let nextId = 1;

  return {
    now: () => time,
    schedule: (delayMs, fn) => {
      const id = nextId++;
      queue.push({ at: time + delayMs, fn, id });
      return () => {
        const i = queue.findIndex((q) => q.id === id);
        if (i !== -1) queue.splice(i, 1);
      };
    },
    advance: (ms) => {
      const target = time + ms;
      while (true) {
        const due = queue
          .filter((q) => q.at <= target)
          .sort((a, b) => a.at - b.at);
        if (!due.length) { time = target; return; }
        const next = due[0];
        time = next.at;
        queue.splice(queue.indexOf(next), 1);
        next.fn();
      }
    },
    setTime: (t) => { time = t; },
  };
}

// ───── test helpers ────────────────────────────────────────────────────────

function openClient(url) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    const messages = [];
    ws.on('message', (d) => { try { messages.push(JSON.parse(d.toString())); } catch {} });
    ws.on('error', reject);
    ws.once('open', () => resolve({ ws, messages, waitFor }));
    function waitFor(predicate, { timeoutMs = 1500, sinceIndex = 0 } = {}) {
      return new Promise((res, rej) => {
        let settled = false;
        const scan = () => {
          for (let i = sinceIndex; i < messages.length; i++) {
            if (predicate(messages[i])) {
              if (settled) return;
              settled = true;
              clearTimeout(to); ws.off('message', listener);
              return res(messages[i]);
            }
          }
        };
        const listener = () => scan();
        ws.on('message', listener);
        const to = setTimeout(() => {
          if (settled) return;
          settled = true;
          ws.off('message', listener);
          rej(new Error(`timeout; saw: ${JSON.stringify(messages.slice(sinceIndex))}`));
        }, timeoutMs);
        scan();
      });
    }
  });
}

function send(ws, msg) { ws.send(JSON.stringify(msg)); }
function close(ws) { return new Promise((r) => { ws.once('close', r); ws.close(); }); }

// Wait briefly for any in-flight ws messages to flush.
const nextTick = () => new Promise((r) => setImmediate(r));

// ───── test ────────────────────────────────────────────────────────────────

test('reaction game end-to-end: countdown → open → ranked scores', async () => {
  const clock = makeFakeClock();
  const game = createReactionGame({ winScore: 100 });   // disable auto-win in this run
  const srv = await createServer({
    port: 0,
    quiet: true,
    game,
    now: clock.now,
    schedule: clock.schedule,
    random: () => 0,   // countdown = COUNTDOWN_MIN_MS exactly
  });
  const base = `ws://localhost:${srv.port}/ws`;

  try {
    const recv = await openClient(base);
    send(recv.ws, { type: 'HELLO', role: 'receiver' });
    await recv.waitFor((m) => m.type === 'STATE');

    const alice = await openClient(base);
    send(alice.ws, { type: 'HELLO', role: 'controller', name: 'Alice' });
    await alice.waitFor((m) => m.type === 'WELCOME');

    const bob = await openClient(base);
    send(bob.ws, { type: 'HELLO', role: 'controller', name: 'Bob' });
    await bob.waitFor((m) => m.type === 'WELCOME');
    await recv.waitFor((m) => m.type === 'STATE' && m.players.length === 2);

    // Alice is the host (first joined). Start the game.
    send(alice.ws, { type: 'START_GAME' });
    await recv.waitFor((m) => m.type === 'ROUND_COUNTDOWN');

    // Advance past the hidden timer → TIMER_FIRED broadcast.
    const sinceBeforeAdvance = recv.messages.length;
    clock.advance(COUNTDOWN_MIN_MS);
    await nextTick();
    await recv.waitFor((m) => m.type === 'TIMER_FIRED', { sinceIndex: sinceBeforeAdvance });

    // Bob presses first, then Alice.
    send(bob.ws, { type: 'BUTTON_PRESS', clientTs: clock.now() });
    await nextTick();
    clock.advance(30);
    send(alice.ws, { type: 'BUTTON_PRESS', clientTs: clock.now() });
    await nextTick();

    // Close the scoring window.
    const sinceBeforeEnd = recv.messages.length;
    clock.advance(SCORING_WINDOW_MS);
    await nextTick();
    const ended = await recv.waitFor((m) => m.type === 'ROUND_ENDED', { sinceIndex: sinceBeforeEnd });

    const bobRank = ended.ranks.find((r) => r.playerId === 2);
    const aliceRank = ended.ranks.find((r) => r.playerId === 1);
    assert.equal(bobRank.points, 4, 'Bob first → 4 pts');
    assert.equal(aliceRank.points, 3, 'Alice second → 3 pts');
    assert.deepEqual(ended.scores, { 1: 3, 2: 4 });

    await close(alice.ws); await close(bob.ws); await close(recv.ws);
  } finally {
    await srv.close();
  }
});

test('reaction game end-to-end: early press locks out the presser', async () => {
  const clock = makeFakeClock();
  const game = createReactionGame();
  const srv = await createServer({
    port: 0,
    quiet: true,
    game,
    now: clock.now,
    schedule: clock.schedule,
    random: () => 0,   // real countdown = COUNTDOWN_MIN_MS, so the advance below is enough
  });
  const base = `ws://localhost:${srv.port}/ws`;

  try {
    const recv = await openClient(base);
    send(recv.ws, { type: 'HELLO', role: 'receiver' });
    const alice = await openClient(base);
    send(alice.ws, { type: 'HELLO', role: 'controller', name: 'Alice' });
    await alice.waitFor((m) => m.type === 'WELCOME');

    send(alice.ws, { type: 'START_GAME' });
    await recv.waitFor((m) => m.type === 'ROUND_COUNTDOWN');

    // Alice presses before timer fires.
    send(alice.ws, { type: 'BUTTON_PRESS', clientTs: clock.now() });
    await recv.waitFor((m) => m.type === 'EARLY_PRESS' && m.playerId === 1);

    // Finish round.
    clock.advance(COUNTDOWN_MIN_MS + SCORING_WINDOW_MS + 100);
    await nextTick();
    const ended = await recv.waitFor((m) => m.type === 'ROUND_ENDED');
    const rank = ended.ranks.find((r) => r.playerId === 1);
    assert.equal(rank.points, 0);
    assert.equal(rank.lockedOut, true);

    await close(alice.ws); await close(recv.ws);
  } finally {
    await srv.close();
  }
});
