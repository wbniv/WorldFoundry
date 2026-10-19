// Unit tests for the reaction-game state machine. Drives the plugin directly
// (no WebSocket layer) with a mocked services surface: controllable time,
// deterministic random, manual schedule(). Separate integration test covers
// the plugin wired into createServer.

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  createReactionGame,
  COUNTDOWN_SHOW_MS,
  COUNTDOWN_MIN_MS,
  COUNTDOWN_MAX_MS,
  SCORING_WINDOW_MS,
  ROUND_END_PAUSE_MS,
  POINTS_BY_RANK,
} = require('../reaction');

// ───── mock services ───────────────────────────────────────────────────────

function makeServices({ players = [], random = 0.5 } = {}) {
  let time = 1_000_000;
  const broadcasts = [];
  const scheduled = [];  // { fireAt, fn, id }
  let nextId = 1;

  function advanceTo(t) {
    if (t < time) throw new Error('time goes forward only');
    while (true) {
      const due = scheduled
        .filter(s => s.fireAt <= t)
        .sort((a, b) => a.fireAt - b.fireAt);
      if (due.length === 0) { time = t; break; }
      const [next] = due;
      time = next.fireAt;
      scheduled.splice(scheduled.indexOf(next), 1);
      next.fn();
    }
  }
  function advance(ms) { advanceTo(time + ms); }

  function lastBroadcast(typeFilter) {
    for (let i = broadcasts.length - 1; i >= 0; i--) {
      if (!typeFilter || broadcasts[i].type === typeFilter) return broadcasts[i];
    }
    return null;
  }

  const services = {
    broadcast(msg) { broadcasts.push(msg); },
    sendTo(/* id, msg */) { /* unused in this test */ },
    getPlayers() { return players.slice(); },
    getHost() { return players[0] || null; },
    now() { return time; },
    schedule(ms, fn) {
      const id = nextId++;
      scheduled.push({ fireAt: time + ms, fn, id });
      return () => {
        const i = scheduled.findIndex(s => s.id === id);
        if (i !== -1) scheduled.splice(i, 1);
      };
    },
    random: () => random,
  };

  return {
    services,
    advance, advanceTo,
    broadcasts,
    byType(t) { return broadcasts.filter(m => m.type === t); },
    lastBroadcast,
    players,           // mutable in-place (push / splice) if the test needs to add/remove
    get time() { return time; },
    setRandom(r) { services.random = () => r; },
  };
}

// ───── tests ───────────────────────────────────────────────────────────────

test('starts in LOBBY; onJoin registers player with score 0', () => {
  const { services } = makeServices({ players: [] });
  const game = createReactionGame();
  assert.equal(game._debugState().phase, 'LOBBY');
  game.onJoin({ id: 1, name: 'Alice' }, services);
  assert.equal(game._debugState().scores.get(1), 0);
});

test('START_GAME from non-host is ignored', () => {
  const alice = { id: 1, name: 'Alice' }, bob = { id: 2, name: 'Bob' };
  const ctx = makeServices({ players: [alice, bob] });
  const game = createReactionGame();
  game.onJoin(alice, ctx.services);
  game.onJoin(bob, ctx.services);
  // Bob is not host (Alice is first).
  game.onMessage(bob, { type: 'START_GAME' }, ctx.services);
  assert.equal(game._debugState().phase, 'LOBBY');
});

test('START_GAME from host → ROUND_COUNTDOWN with stable broadcast sequence', () => {
  const alice = { id: 1, name: 'Alice' };
  const ctx = makeServices({ players: [alice], random: 0.0 });  // realMs = COUNTDOWN_MIN_MS
  const game = createReactionGame();
  game.onJoin(alice, ctx.services);
  game.onMessage(alice, { type: 'START_GAME' }, ctx.services);

  const phases = ctx.byType('PHASE').map(m => m.phase);
  assert.deepEqual(phases, ['ROUND_COUNTDOWN']);

  const rc = ctx.lastBroadcast('ROUND_COUNTDOWN');
  assert.ok(rc);
  assert.equal(rc.roundId, 1);
  assert.equal(rc.showMs, COUNTDOWN_SHOW_MS);

  const st = game._debugState();
  assert.equal(st.round.realMs, COUNTDOWN_MIN_MS);  // random=0 → min
});

test('random→COUNTDOWN_MAX_MS at random=1.0', () => {
  const alice = { id: 1, name: 'Alice' };
  const ctx = makeServices({ players: [alice], random: 1.0 });
  const game = createReactionGame();
  game.onJoin(alice, ctx.services);
  game.onMessage(alice, { type: 'START_GAME' }, ctx.services);
  assert.equal(game._debugState().round.realMs, COUNTDOWN_MAX_MS);
});

test('TIMER_FIRED fires exactly at realMs; phase → ROUND_OPEN', () => {
  const alice = { id: 1, name: 'Alice' };
  const ctx = makeServices({ players: [alice], random: 0.0 });
  const game = createReactionGame();
  game.onJoin(alice, ctx.services);
  game.onMessage(alice, { type: 'START_GAME' }, ctx.services);

  // Just before realMs → nothing
  ctx.advance(COUNTDOWN_MIN_MS - 1);
  assert.equal(ctx.byType('TIMER_FIRED').length, 0);
  assert.equal(game._debugState().phase, 'ROUND_COUNTDOWN');

  // Fire
  ctx.advance(1);
  const tf = ctx.lastBroadcast('TIMER_FIRED');
  assert.ok(tf);
  assert.equal(tf.roundId, 1);
  assert.equal(game._debugState().phase, 'ROUND_OPEN');
});

test('BUTTON_PRESS during countdown → EARLY_PRESS; player locked out for this round', () => {
  // Use three players so a single early press doesn't trip LAST_STANDING
  // — that's covered separately. This test is specifically about the
  // EARLY_PRESS → lockout mechanic surviving into ROUND_ENDED.
  const alice = { id: 1, name: 'Alice' };
  const bob   = { id: 2, name: 'Bob' };
  const carol = { id: 3, name: 'Carol' };
  const ctx = makeServices({ players: [alice, bob, carol], random: 0.5 });
  const game = createReactionGame();
  for (const p of [alice, bob, carol]) game.onJoin(p, ctx.services);
  game.onMessage(alice, { type: 'START_GAME' }, ctx.services);

  ctx.advance(500);  // still in countdown
  game.onMessage(bob, { type: 'BUTTON_PRESS', clientTs: ctx.time }, ctx.services);

  const early = ctx.lastBroadcast('EARLY_PRESS');
  assert.ok(early, 'EARLY_PRESS was not broadcast');
  assert.equal(early.playerId, 2);
  // LAST_STANDING should NOT have fired — Alice and Carol both still in.
  assert.equal(ctx.byType('LAST_STANDING').length, 0);

  // Ride out the round; Bob should score 0 with lockedOut flag on this round's ROUND_ENDED.
  ctx.advance(COUNTDOWN_MAX_MS + SCORING_WINDOW_MS);
  const re = ctx.byType('ROUND_ENDED')[0];  // specifically round 1
  assert.ok(re);
  const bobRank = re.ranks.find(r => r.playerId === 2);
  assert.equal(bobRank.points, 0);
  assert.equal(bobRank.lockedOut, true);
});

test('LAST_STANDING: EARLY_PRESS that leaves one player un-locked auto-wins the remaining player', () => {
  const alice = { id: 1, name: 'Alice' }, bob = { id: 2, name: 'Bob' };
  const ctx = makeServices({ players: [alice, bob], random: 0.5 });
  const game = createReactionGame();
  game.onJoin(alice, ctx.services);
  game.onJoin(bob, ctx.services);
  game.onMessage(alice, { type: 'START_GAME' }, ctx.services);

  ctx.advance(500);  // still in countdown
  game.onMessage(bob, { type: 'BUTTON_PRESS', clientTs: ctx.time }, ctx.services);

  const ls = ctx.lastBroadcast('LAST_STANDING');
  assert.ok(ls, 'LAST_STANDING must be broadcast when Bob locking out leaves Alice alone');
  assert.equal(ls.playerId, 1);
  assert.equal(ls.name, 'Alice');
  const re = ctx.lastBroadcast('ROUND_ENDED');
  assert.ok(re, 'ROUND_ENDED fires right after LAST_STANDING');
  const aliceRank = re.ranks.find(r => r.playerId === 1);
  const bobRank   = re.ranks.find(r => r.playerId === 2);
  assert.equal(aliceRank.points, POINTS_BY_RANK[0], 'Alice auto-win → 4 pts');
  assert.equal(bobRank.points, 0);
  assert.equal(bobRank.lockedOut, true);
});

test('BUTTON_PRESS during ROUND_OPEN → ranked by server-receive timestamp', () => {
  const alice = { id: 1, name: 'Alice' }, bob = { id: 2, name: 'Bob' }, carol = { id: 3, name: 'Carol' };
  const ctx = makeServices({ players: [alice, bob, carol], random: 0.0 });
  const game = createReactionGame();
  for (const p of [alice, bob, carol]) game.onJoin(p, ctx.services);
  game.onMessage(alice, { type: 'START_GAME' }, ctx.services);

  ctx.advance(COUNTDOWN_MIN_MS);                // TIMER_FIRED now fires
  assert.equal(game._debugState().phase, 'ROUND_OPEN');

  // Bob presses fastest, then Carol, then Alice (who squeaks in late).
  ctx.advance(80);
  game.onMessage(bob,   { type: 'BUTTON_PRESS', clientTs: ctx.time }, ctx.services);
  ctx.advance(40);
  game.onMessage(carol, { type: 'BUTTON_PRESS', clientTs: ctx.time }, ctx.services);
  ctx.advance(200);
  game.onMessage(alice, { type: 'BUTTON_PRESS', clientTs: ctx.time }, ctx.services);

  // Close the window.
  ctx.advance(SCORING_WINDOW_MS);
  const re = ctx.lastBroadcast('ROUND_ENDED');
  assert.ok(re);

  const byId = Object.fromEntries(re.ranks.map(r => [r.playerId, r]));
  assert.equal(byId[2].points, POINTS_BY_RANK[0], 'Bob should be 1st');
  assert.equal(byId[3].points, POINTS_BY_RANK[1], 'Carol should be 2nd');
  assert.equal(byId[1].points, POINTS_BY_RANK[2], 'Alice should be 3rd');

  // Scores broadcast alongside ranks.
  assert.deepEqual(re.scores, { 1: 2, 2: 4, 3: 3 });
});

test('successful press during ROUND_OPEN broadcasts a PRESS_RECORDED event', () => {
  const alice = { id: 1, name: 'Alice' };
  const ctx = makeServices({ players: [alice], random: 0.0 });
  const game = createReactionGame();
  game.onJoin(alice, ctx.services);
  game.onMessage(alice, { type: 'START_GAME' }, ctx.services);
  ctx.advance(COUNTDOWN_MIN_MS);
  assert.equal(game._debugState().phase, 'ROUND_OPEN');

  game.onMessage(alice, { type: 'BUTTON_PRESS', clientTs: ctx.time }, ctx.services);
  const pr = ctx.byType('PRESS_RECORDED');
  assert.equal(pr.length, 1);
  assert.equal(pr[0].playerId, 1);
  assert.equal(pr[0].name, 'Alice');
});

test('non-presser gets 0 pts; press after scoring window closes is ignored', () => {
  const alice = { id: 1, name: 'Alice' }, bob = { id: 2, name: 'Bob' };
  const ctx = makeServices({ players: [alice, bob], random: 0.0 });
  const game = createReactionGame();
  for (const p of [alice, bob]) game.onJoin(p, ctx.services);
  game.onMessage(alice, { type: 'START_GAME' }, ctx.services);

  ctx.advance(COUNTDOWN_MIN_MS);
  ctx.advance(50);
  game.onMessage(bob, { type: 'BUTTON_PRESS', clientTs: ctx.time }, ctx.services);

  // Close the scoring window, then Alice tries to press — too late.
  ctx.advance(SCORING_WINDOW_MS);
  game.onMessage(alice, { type: 'BUTTON_PRESS', clientTs: ctx.time }, ctx.services);

  const re = ctx.lastBroadcast('ROUND_ENDED');
  const byId = Object.fromEntries(re.ranks.map(r => [r.playerId, r]));
  assert.equal(byId[2].points, POINTS_BY_RANK[0]);  // Bob 4
  assert.equal(byId[1].points, 0);                  // Alice 0 — didn't press in time
});

test('second round auto-starts after ROUND_END_PAUSE_MS', () => {
  const alice = { id: 1, name: 'Alice' };
  const ctx = makeServices({ players: [alice], random: 0.0 });
  const game = createReactionGame();
  game.onJoin(alice, ctx.services);
  game.onMessage(alice, { type: 'START_GAME' }, ctx.services);

  // Finish round 1.
  ctx.advance(COUNTDOWN_MIN_MS);
  game.onMessage(alice, { type: 'BUTTON_PRESS', clientTs: ctx.time }, ctx.services);
  ctx.advance(SCORING_WINDOW_MS);
  assert.equal(game._debugState().phase, 'ROUND_ENDED');

  // Round 2 starts after pause.
  ctx.advance(ROUND_END_PAUSE_MS);
  assert.equal(game._debugState().phase, 'ROUND_COUNTDOWN');
  assert.equal(game._debugState().roundId, 2);
});

test('reaching WIN_SCORE triggers GAME_OVER; no auto-next-round', () => {
  const alice = { id: 1, name: 'Alice' };
  // winScore=4 so one round's worth of points ends it.
  const ctx = makeServices({ players: [alice], random: 0.0 });
  const game = createReactionGame({ winScore: 4 });
  game.onJoin(alice, ctx.services);
  game.onMessage(alice, { type: 'START_GAME' }, ctx.services);
  ctx.advance(COUNTDOWN_MIN_MS);
  game.onMessage(alice, { type: 'BUTTON_PRESS', clientTs: ctx.time }, ctx.services);
  ctx.advance(SCORING_WINDOW_MS);

  const go = ctx.lastBroadcast('GAME_OVER');
  assert.ok(go, 'GAME_OVER was not broadcast');
  assert.equal(go.winnerId, 1);
  assert.equal(game._debugState().phase, 'GAME_OVER');

  // Advance past the old ROUND_END_PAUSE_MS — nothing should fire.
  const roundsBefore = ctx.byType('ROUND_COUNTDOWN').length;
  ctx.advance(ROUND_END_PAUSE_MS + 100);
  assert.equal(ctx.byType('ROUND_COUNTDOWN').length, roundsBefore);
});

test('NEW_GAME from host resets scoreboard and returns to LOBBY', () => {
  const alice = { id: 1, name: 'Alice' };
  const ctx = makeServices({ players: [alice], random: 0.0 });
  const game = createReactionGame({ winScore: 4 });
  game.onJoin(alice, ctx.services);
  game.onMessage(alice, { type: 'START_GAME' }, ctx.services);
  ctx.advance(COUNTDOWN_MIN_MS);
  game.onMessage(alice, { type: 'BUTTON_PRESS', clientTs: ctx.time }, ctx.services);
  ctx.advance(SCORING_WINDOW_MS);
  assert.equal(game._debugState().phase, 'GAME_OVER');

  game.onMessage(alice, { type: 'NEW_GAME' }, ctx.services);
  assert.equal(game._debugState().phase, 'LOBBY');
  assert.equal(game._debugState().scores.get(1), 0);
});

test('leaving mid-round: player dropped from presses + scores, round continues', () => {
  const alice = { id: 1, name: 'Alice' }, bob = { id: 2, name: 'Bob' };
  const ctx = makeServices({ players: [alice, bob], random: 0.0 });
  const game = createReactionGame();
  for (const p of [alice, bob]) game.onJoin(p, ctx.services);
  game.onMessage(alice, { type: 'START_GAME' }, ctx.services);
  ctx.advance(COUNTDOWN_MIN_MS);
  game.onMessage(bob, { type: 'BUTTON_PRESS', clientTs: ctx.time }, ctx.services);

  // Bob leaves.
  ctx.players.splice(ctx.players.indexOf(bob), 1);
  game.onLeave(bob, ctx.services);

  ctx.advance(SCORING_WINDOW_MS);
  const re = ctx.lastBroadcast('ROUND_ENDED');
  // Only Alice should appear in ranks (the current-players list).
  assert.deepEqual(re.ranks.map(r => r.playerId), [1]);
});

test('all players leaving mid-round folds game back to LOBBY', () => {
  const alice = { id: 1, name: 'Alice' };
  const ctx = makeServices({ players: [alice], random: 0.0 });
  const game = createReactionGame();
  game.onJoin(alice, ctx.services);
  game.onMessage(alice, { type: 'START_GAME' }, ctx.services);
  assert.equal(game._debugState().phase, 'ROUND_COUNTDOWN');

  // Alice rage-quits.
  ctx.players.splice(ctx.players.indexOf(alice), 1);
  game.onLeave(alice, ctx.services);
  assert.equal(game._debugState().phase, 'LOBBY');
});
