// Unit tests for the image-recognition state machine. Drives the plugin
// directly (no WebSocket) with a mocked services surface: controllable time,
// deterministic random, manual schedule(). Mirrors reaction tests' shape.

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  createImageGame,
  IMAGE_POOL,
  REVEAL_MS,
  REVEAL_CLEAR_MS,
  IMAGE_SHOW_MS,
  ROUND_END_PAUSE_MS,
  MAX_ROUND_MS,
  POINTS_BY_RANK,
} = require('../image');

// ───── mock services ───────────────────────────────────────────────────────

function makeServices({ players = [], random = 0.5 } = {}) {
  let time = 1_000_000;
  const broadcasts = [];
  const scheduled = [];
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

  let randomSeries = null;
  let randomPos = 0;
  const randomFn = () => {
    if (randomSeries) {
      const v = randomSeries[randomPos % randomSeries.length];
      randomPos++;
      return v;
    }
    return random;
  };

  const services = {
    broadcast(msg) { broadcasts.push(msg); },
    sendTo() {},
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
    random: randomFn,
  };

  return {
    services,
    advance, advanceTo,
    broadcasts,
    byType(t) { return broadcasts.filter(m => m.type === t); },
    players,
    get time() { return time; },
    setRandomSeries(series) { randomSeries = series; randomPos = 0; },
    setRandom(r) { random = r; randomSeries = null; },
  };
}

function pressButton(game, services, player, opts = {}) {
  game.onMessage(player, { type: 'BUTTON_PRESS', clientTs: opts.clientTs ?? 0 }, services);
}

// Two-item pool — random < 0.5 → pool[0] (target), random ≥ 0.5 → pool[1] (distractor).
const TWO_POOL = ['★', '•'];

// ───── tests ───────────────────────────────────────────────────────────────

test('starts in LOBBY; onJoin registers player with score 0', () => {
  const h = makeServices();
  const game = createImageGame();
  assert.equal(game._debugState().phase, 'LOBBY');
  const p = { id: 1, name: 'Alice' };
  h.players.push(p);
  game.onJoin(p, h.services);
  assert.equal(game._debugState().scores.get(1), 0);
});

test('START_GAME from LOBBY → REVEAL; ROUND_REVEAL carries a target from the pool', () => {
  const h = makeServices();
  const game = createImageGame();
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);

  assert.equal(game._debugState().phase, 'REVEAL');
  const reveal = h.byType('ROUND_REVEAL')[0];
  assert.ok(reveal);
  assert.equal(reveal.roundId, 1);
  assert.equal(reveal.showMs, REVEAL_MS);
  assert.equal(reveal.clearMs, REVEAL_CLEAR_MS);
  assert.ok(IMAGE_POOL.includes(reveal.targetId));
});

test('START_GAME rejected if not from host', () => {
  const h = makeServices();
  const game = createImageGame();
  const alice = { id: 1, name: 'Alice' };
  const bob   = { id: 2, name: 'Bob' };
  h.players.push(alice, bob);
  game.onJoin(alice, h.services);
  game.onJoin(bob,   h.services);
  game.onMessage(bob, { type: 'START_GAME' }, h.services);
  assert.equal(game._debugState().phase, 'LOBBY');
  assert.equal(h.byType('ROUND_REVEAL').length, 0);
});

test('after REVEAL_MS + REVEAL_CLEAR_MS transitions to PLAY', () => {
  const h = makeServices();
  const game = createImageGame();
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS - 1);
  assert.equal(game._debugState().phase, 'REVEAL');
  h.advance(1);
  assert.equal(game._debugState().phase, 'PLAY');
});

test('PLAY streams SHOW_IMAGE at IMAGE_SHOW_MS; isTarget flag matches random picks', () => {
  const h = makeServices();
  // [pickTarget, pick1, pick2, pick3, pick4]  — in TWO_POOL, 0.1 → target, 0.9 → distractor
  h.setRandomSeries([0.1, 0.9, 0.1, 0.9, 0.1]);
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  h.advance(IMAGE_SHOW_MS * 3);

  const imgs = h.byType('SHOW_IMAGE');
  assert.equal(imgs.length, 4);
  assert.equal(imgs[0].isTarget, false);
  assert.equal(imgs[1].isTarget, true);
  assert.equal(imgs[2].isTarget, false);
  assert.equal(imgs[3].isTarget, true);
});

test('BUTTON_PRESS during REVEAL → lockout', () => {
  const h = makeServices();
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  const bob   = { id: 2, name: 'Bob' };
  h.players.push(alice, bob);
  game.onJoin(alice, h.services);
  game.onJoin(bob,   h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);

  pressButton(game, h.services, bob);
  assert.ok(game._debugState().round.lockedOut.has(2));
  const ep = h.byType('EARLY_PRESS');
  assert.equal(ep.length, 1);
  assert.equal(ep[0].playerId, 2);
});

test('BUTTON_PRESS during PLAY BEFORE target has appeared → lockout', () => {
  const h = makeServices();
  h.setRandomSeries([0.1, 0.9, 0.9]);  // target picked, then distractor, distractor
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  // First frame is a distractor; target hasn't shown yet.
  assert.equal(game._debugState().round.targetFirstShownAt, null);

  pressButton(game, h.services, alice);
  assert.ok(game._debugState().round.lockedOut.has(1));
  assert.equal(h.byType('EARLY_PRESS').length, 1);
});

test('successful press broadcasts a PRESS_RECORDED event (receiver live indicator)', () => {
  const h = makeServices();
  h.setRandomSeries([0.1, 0.1]);  // target pick, first frame = target
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);

  pressButton(game, h.services, alice);
  const pr = h.byType('PRESS_RECORDED');
  assert.equal(pr.length, 1);
  assert.equal(pr[0].playerId, 1);
  assert.equal(pr[0].name, 'Alice');
});

test('BUTTON_PRESS during PLAY AFTER target has appeared → counted (even on a distractor frame)', () => {
  const h = makeServices();
  // [pickTarget=0.1 → target, frame1=0.1 → target, frame2=0.9 → distractor]
  h.setRandomSeries([0.1, 0.1, 0.9]);
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  // Target just flashed as frame 1 — round is now armed.
  assert.ok(h.byType('SHOW_IMAGE')[0].isTarget);
  assert.notEqual(game._debugState().round.targetFirstShownAt, null);

  // Advance into the distractor frame and press — should still count because
  // the target was already seen earlier in the round.
  h.advance(IMAGE_SHOW_MS + 50);
  assert.equal(h.byType('SHOW_IMAGE').pop().isTarget, false, 'sanity: current frame is distractor');
  pressButton(game, h.services, alice);
  assert.ok(game._debugState().round.presses.has(1), 'press should count once target has appeared');
  assert.ok(!game._debugState().round.lockedOut.has(1));
});

test('press ~2 s after target cleared is still valid as long as target appeared earlier', () => {
  const h = makeServices();
  // target appears as frame 1, then lots of distractors.
  h.setRandomSeries([0.1, 0.1, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9]);
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  // Walk 3 distractor frames forward — target is well in the past.
  h.advance(IMAGE_SHOW_MS * 3);
  pressButton(game, h.services, alice);
  assert.ok(game._debugState().round.presses.has(1));
});

test('ranks 4/3/2/1 by serverTs order across players who committed', () => {
  const h = makeServices();
  // Target on first frame; subsequent frames don't matter for ranking.
  h.setRandomSeries([0.1, 0.1, 0.9, 0.9, 0.9, 0.9]);
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  const bob   = { id: 2, name: 'Bob' };
  const cara  = { id: 3, name: 'Cara' };
  const dan   = { id: 4, name: 'Dan' };
  h.players.push(alice, bob, cara, dan);
  for (const p of h.players) game.onJoin(p, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);

  pressButton(game, h.services, bob);   h.advance(10);
  pressButton(game, h.services, alice); h.advance(10);
  pressButton(game, h.services, cara);  h.advance(10);
  pressButton(game, h.services, dan);

  const ended = h.byType('ROUND_ENDED')[0];
  assert.ok(ended, 'round should end when all players commit');
  const byId = Object.fromEntries(ended.ranks.map(r => [r.playerId, r]));
  assert.equal(byId[2].points, POINTS_BY_RANK[0]);
  assert.equal(byId[1].points, POINTS_BY_RANK[1]);
  assert.equal(byId[3].points, POINTS_BY_RANK[2]);
  assert.equal(byId[4].points, POINTS_BY_RANK[3]);
});

test('ms field in ranks is measured from targetFirstShownAt, not from the press itself', () => {
  const h = makeServices();
  h.setRandomSeries([0.1, 0.1, 0.9, 0.9]);   // target at frame 1
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  const targetTs = game._debugState().round.targetFirstShownAt;

  h.advance(123);   // simulate a reaction delay
  pressButton(game, h.services, alice);
  const ended = h.byType('ROUND_ENDED')[0];
  assert.equal(ended.ranks[0].ms, 123);
  assert.equal(ended.ranks[0].ms, h.time - targetTs - 0 /* no frame transitions happened */);
});

test('ROUND_ENDED includes targetId', () => {
  const h = makeServices();
  h.setRandomSeries([0.1, 0.1]);
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  const targetFromReveal = h.byType('ROUND_REVEAL')[0].targetId;
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  pressButton(game, h.services, alice);
  const ended = h.byType('ROUND_ENDED')[0];
  assert.equal(ended.targetId, targetFromReveal);
});

test('round ends with timedOut=true when maxRoundMs elapses without commitment', () => {
  const h = makeServices();
  h.setRandomSeries([0.1, 0.9, 0.9, 0.9, 0.9]);   // target picked, but stream is all distractors
  const game = createImageGame({ pool: TWO_POOL, maxRoundMs: 3 * IMAGE_SHOW_MS });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS + 3 * IMAGE_SHOW_MS);

  const ended = h.byType('ROUND_ENDED').find(m => m.timedOut === true);
  assert.ok(ended);
  assert.equal(ended.ranks[0].points, 0);
});

test('round ends early when all active players have committed', () => {
  const h = makeServices();
  h.setRandomSeries([0.1, 0.1]);   // target at frame 1
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  const bob   = { id: 2, name: 'Bob' };
  h.players.push(alice, bob);
  game.onJoin(alice, h.services);
  game.onJoin(bob,   h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);

  pressButton(game, h.services, alice);
  pressButton(game, h.services, bob);
  assert.equal(game._debugState().phase, 'ROUND_ENDED');
});

test('winner at win-score → GAME_OVER', () => {
  const h = makeServices();
  h.setRandomSeries([0.1, 0.1, 0.1, 0.1, 0.1, 0.1]);
  const game = createImageGame({ pool: TWO_POOL, winScore: 8 });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);

  // Round 1 → 4 pts.
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  pressButton(game, h.services, alice);
  assert.equal(game._debugState().phase, 'ROUND_ENDED');

  // Round 2.
  h.advance(ROUND_END_PAUSE_MS);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  pressButton(game, h.services, alice);
  assert.equal(game._debugState().phase, 'GAME_OVER');
  const over = h.byType('GAME_OVER')[0];
  assert.equal(over.winnerId, 1);
  assert.equal(over.scores[1], 8);
});

test('NEW_GAME from GAME_OVER resets scores and returns to LOBBY', () => {
  const h = makeServices();
  h.setRandomSeries([0.1, 0.1]);
  const game = createImageGame({ pool: TWO_POOL, winScore: 4 });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  pressButton(game, h.services, alice);
  assert.equal(game._debugState().phase, 'GAME_OVER');

  game.onMessage(alice, { type: 'NEW_GAME' }, h.services);
  assert.equal(game._debugState().phase, 'LOBBY');
  assert.equal(game._debugState().scores.get(1), 0);
});

test('onJoin catches late joiners up on the current phase (bug that sat them on LOBBY)', () => {
  // Need a services mock that records sendTo calls — default mock is a no-op.
  const sentTo = [];
  const h = makeServices();
  h.services.sendTo = (pid, msg) => sentTo.push({ pid, msg });
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  assert.equal(game._debugState().phase, 'PLAY');

  // Bob joins mid-PLAY.
  const bob = { id: 2, name: 'Bob' };
  h.players.push(bob);
  const sinceJoin = sentTo.length;
  game.onJoin(bob, h.services);
  const toBob = sentTo.slice(sinceJoin).filter(x => x.pid === 2);
  const phaseMsg = toBob.find(x => x.msg.type === 'PHASE');
  assert.ok(phaseMsg, 'Bob must receive a PHASE message on join');
  assert.equal(phaseMsg.msg.phase, 'PLAY', 'should match the current round phase');
});

test('onLeave with last player mid-round folds to LOBBY', () => {
  const h = makeServices();
  const game = createImageGame();
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  assert.equal(game._debugState().phase, 'REVEAL');

  h.players.length = 0;
  game.onLeave(alice, h.services);
  assert.equal(game._debugState().phase, 'LOBBY');
  assert.equal(game._debugState().round, null);
});

test('default MAX_ROUND_MS is 60_000', () => {
  assert.equal(MAX_ROUND_MS, 60_000);
});
