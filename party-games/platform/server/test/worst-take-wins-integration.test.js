// End-to-end: worst-take-wins plugin wired into createServer, three real
// WebSocket controllers + one receiver. Verifies the anonymity invariant
// (private hands never hit the receiver / other players), judge pick
// flow, and score propagation.

const test = require('node:test');
const assert = require('node:assert/strict');
const WebSocket = require('ws');

const { createServer } = require('../createServer');
const { createWorstTakeWinsGame } = require('../../../games/worst-take-wins/worst-take-wins');

// Minimal deterministic deck — enough for a round or two, never triggers
// reshuffle. Using inline content so the test doesn't depend on assets/.
function miniContent() {
  const prompts = [];
  for (let i = 1; i <= 10; i++) prompts.push({ id: `p${i}`, text: `prompt ${i} ____.`, blanks: 1 });
  const responses = [];
  for (let i = 1; i <= 40; i++) responses.push({ id: `r${i}`, text: `response ${i}` });
  return { prompts, responses };
}

function makeFakeClock(startMs = 1_000_000) {
  let time = startMs;
  const queue = [];
  let nextId = 1;
  return {
    now: () => time,
    schedule: (ms, fn) => {
      const id = nextId++;
      queue.push({ at: time + ms, fn, id });
      return () => {
        const i = queue.findIndex((q) => q.id === id);
        if (i !== -1) queue.splice(i, 1);
      };
    },
    advance: (ms) => {
      const target = time + ms;
      while (true) {
        const due = queue.filter((q) => q.at <= target).sort((a, b) => a.at - b.at);
        if (!due.length) { time = target; return; }
        const next = due[0];
        time = next.at;
        queue.splice(queue.indexOf(next), 1);
        next.fn();
      }
    },
  };
}

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

const nextTick = () => new Promise((r) => setImmediate(r));

// ───── tests ─────────────────────────────────────────────────────────────

test('worst-take-wins end-to-end: 3 players, one round, winner scores', async () => {
  const clock = makeFakeClock();
  const game = createWorstTakeWinsGame({
    content: miniContent(),
    winScore: 100,         // keep game going through this test
    submitTimeoutMs: 999_999,
  });
  const srv = await createServer({
    port: 0,
    quiet: true,
    game,
    now: clock.now,
    schedule: clock.schedule,
    random: () => 0.42,
  });
  const base = `ws://localhost:${srv.port}/ws`;

  try {
    const recv = await openClient(base);
    send(recv.ws, { type: 'HELLO', role: 'receiver', room: 'ABCD' });
    await recv.waitFor((m) => m.type === 'STATE');

    const alice = await openClient(base);
    send(alice.ws, { type: 'HELLO', role: 'controller', name: 'Alice', room: 'ABCD' });
    const aliceWelcome = await alice.waitFor((m) => m.type === 'WELCOME');

    const bob = await openClient(base);
    send(bob.ws, { type: 'HELLO', role: 'controller', name: 'Bob', room: 'ABCD' });
    const bobWelcome = await bob.waitFor((m) => m.type === 'WELCOME');

    const carol = await openClient(base);
    send(carol.ws, { type: 'HELLO', role: 'controller', name: 'Carol', room: 'ABCD' });
    const carolWelcome = await carol.waitFor((m) => m.type === 'WELCOME');

    await recv.waitFor((m) => m.type === 'STATE' && m.players.length === 3);

    // Alice (host) starts.
    send(alice.ws, { type: 'START_GAME' });
    const showPrompt = await recv.waitFor((m) => m.type === 'SHOW_PROMPT');
    assert.ok(showPrompt.prompt.text, 'prompt text broadcast');

    // Each controller should have received a private DEAL_HAND.
    const aliceHand = alice.messages.find((m) => m.type === 'DEAL_HAND' && m.cards && m.cards.length > 0);
    const bobHand   = bob.messages.find((m) => m.type === 'DEAL_HAND' && m.cards && m.cards.length > 0);
    const carolHand = carol.messages.find((m) => m.type === 'DEAL_HAND' && m.cards && m.cards.length > 0);
    assert.ok(aliceHand && bobHand && carolHand, 'each controller receives a non-empty hand');
    // Default handSize = 7.
    assert.equal(aliceHand.cards.length, 7);
    assert.equal(bobHand.cards.length, 7);
    assert.equal(carolHand.cards.length, 7);

    // Anonymity/privacy invariant: receiver must NEVER see a DEAL_HAND.
    assert.equal(recv.messages.filter((m) => m.type === 'DEAL_HAND').length, 0,
      'receiver must not receive DEAL_HAND');
    // No controller sees another's hand.
    assert.ok(!bob.messages.some((m) => m.type === 'DEAL_HAND' && m.cards.length > 0
      && m.cards[0].id === aliceHand.cards[0].id && aliceWelcome.id !== bobWelcome.id),
      'bob did not receive alice\'s hand cards verbatim');

    // Which controller is the judge? onPhase carries judgeId.
    const phase = await alice.waitFor((m) => m.type === 'PHASE' && m.phase === 'SHOW_PROMPT');
    const judgeId = phase.judgeId;
    const nonJudges = [
      { client: alice, id: aliceWelcome.id, hand: aliceHand.cards },
      { client: bob,   id: bobWelcome.id,   hand: bobHand.cards },
      { client: carol, id: carolWelcome.id, hand: carolHand.cards },
    ].filter((p) => p.id !== judgeId);
    const judge = [
      { client: alice, id: aliceWelcome.id },
      { client: bob,   id: bobWelcome.id },
      { client: carol, id: carolWelcome.id },
    ].find((p) => p.id === judgeId);

    // Non-judges submit their first card.
    for (const p of nonJudges) {
      send(p.client.ws, { type: 'SUBMIT_CARDS', cardIds: [p.hand[0].id] });
    }

    const revealStart = await recv.waitFor((m) => m.type === 'JUDGE_REVEAL_START');
    assert.equal(revealStart.submissions.length, 2);
    for (const s of revealStart.submissions) {
      assert.equal(s.playerId, undefined, 'playerId must NOT be present in reveal');
      assert.ok(s.cards[0].text, 'card text resolved in reveal payload');
    }

    // Judge picks the first submission.
    const targetSub = revealStart.submissions[0];
    send(judge.client.ws, { type: 'JUDGE_PICK', submissionId: targetSub.submissionId });

    const winner = await recv.waitFor((m) => m.type === 'ROUND_WINNER');
    assert.ok(winner.playerId);
    assert.ok(winner.name);
    assert.deepEqual(winner.cardIds, targetSub.cardIds);

    // Score updated for the winner.
    const scoreUpdate = await recv.waitFor((m) => m.type === 'SCORE_UPDATE');
    assert.equal(scoreUpdate.scores[winner.playerId], 1);

    await close(alice.ws); await close(bob.ws); await close(carol.ws); await close(recv.ws);
  } finally {
    await srv.close();
  }
});

test('START_GAME rejected with <3 players, surfaces ERROR to host', async () => {
  const game = createWorstTakeWinsGame({ content: miniContent() });
  const srv = await createServer({ port: 0, quiet: true, game });
  const base = `ws://localhost:${srv.port}/ws`;

  try {
    const recv = await openClient(base);
    send(recv.ws, { type: 'HELLO', role: 'receiver', room: 'ZZZZ' });
    await recv.waitFor((m) => m.type === 'STATE');

    const alice = await openClient(base);
    send(alice.ws, { type: 'HELLO', role: 'controller', name: 'Alice', room: 'ZZZZ' });
    await alice.waitFor((m) => m.type === 'WELCOME');
    const bob = await openClient(base);
    send(bob.ws, { type: 'HELLO', role: 'controller', name: 'Bob', room: 'ZZZZ' });
    await bob.waitFor((m) => m.type === 'WELCOME');

    const sinceIndex = alice.messages.length;
    send(alice.ws, { type: 'START_GAME' });
    const err = await alice.waitFor((m) => m.type === 'ERROR' && m.code === 'NOT_ENOUGH_PLAYERS', { sinceIndex });
    assert.ok(err);

    await close(alice.ws); await close(bob.ws); await close(recv.ws);
  } finally {
    await srv.close();
  }
});
