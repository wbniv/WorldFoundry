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

// Two-item pool lets tests force the target vs. distractor pick per frame:
// random < 0.5 → pool[0] (target), random ≥ 0.5 → pool[1] (distractor).
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

test('START_GAME from LOBBY → REVEAL; broadcasts ROUND_REVEAL with a target from the pool', () => {
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

test('PLAY streams SHOW_IMAGE at IMAGE_SHOW_MS; isTarget matches the pool picks', () => {
  const h = makeServices();
  // random series: [pickTarget, pick1, pick2, pick3, pick4]
  // With TWO_POOL: 0.1 → pool[0]=target, 0.9 → pool[1]=distractor.
  h.setRandomSeries([0.1, 0.9, 0.1, 0.9, 0.1]);
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  assert.equal(game._debugState().phase, 'PLAY');

  // After entering PLAY, 4 SHOW_IMAGEs fire: 1 immediate, then 3 more at 800 ms each.
  h.advance(IMAGE_SHOW_MS * 3);
  const imgs = h.byType('SHOW_IMAGE');
  assert.equal(imgs.length, 4);
  // per random series: distractor, target, distractor, target
  assert.equal(imgs[0].isTarget, false);
  assert.equal(imgs[1].isTarget, true);
  assert.equal(imgs[2].isTarget, false);
  assert.equal(imgs[3].isTarget, true);
  for (const m of imgs) assert.equal(m.showMs, IMAGE_SHOW_MS);
});

test('BUTTON_PRESS during REVEAL → lockout (EARLY_PRESS broadcast)', () => {
  const h = makeServices();
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  const bob   = { id: 2, name: 'Bob' };
  h.players.push(alice, bob);
  game.onJoin(alice, h.services);
  game.onJoin(bob,   h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  assert.equal(game._debugState().phase, 'REVEAL');

  pressButton(game, h.services, bob);
  assert.ok(game._debugState().round.lockedOut.has(2));
  const ep = h.byType('EARLY_PRESS');
  assert.equal(ep.length, 1);
  assert.equal(ep[0].playerId, 2);
});

test('BUTTON_PRESS during PLAY on a target frame → recorded as a press', () => {
  const h = makeServices();
  h.setRandomSeries([0.1, 0.1]);  // target picked for both pickTarget and first image
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  assert.equal(game._debugState().phase, 'PLAY');
  // First SHOW_IMAGE should be target.
  const firstImg = h.byType('SHOW_IMAGE')[0];
  assert.equal(firstImg.isTarget, true);

  pressButton(game, h.services, alice);
  assert.ok(game._debugState().round.presses.has(1));
});

test('BUTTON_PRESS during PLAY on a distractor frame → lockout', () => {
  const h = makeServices();
  h.setRandomSeries([0.1, 0.9]);  // target = pool[0]; first image = pool[1] distractor
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  assert.equal(h.byType('SHOW_IMAGE')[0].isTarget, false);

  pressButton(game, h.services, alice);
  assert.ok(game._debugState().round.lockedOut.has(1));
  assert.equal(h.byType('EARLY_PRESS').length, 1);
});

test('ranks 4/3/2/1 across players who pressed on target; locked-out players get 0', () => {
  const h = makeServices();
  // Random series:
  //   [0]    → pickTarget = pool[0]
  //   [1]    → first image = target (t=0 in PLAY)
  //   [2..]  → alternating distractor to give later target appearances
  //
  // Actually we only need the first image to be target; once everyone commits,
  // round ends. Series = [0, 0, 0, 0, 0] makes every image the target so each
  // player's press lands on a target frame deterministically.
  h.setRandomSeries([0, 0, 0, 0, 0, 0]);
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
  // All four committed → round ends early; we don't need to advance more.

  const ended = h.byType('ROUND_ENDED')[0];
  assert.ok(ended, 'round should end as soon as all players are committed');
  const byId = Object.fromEntries(ended.ranks.map(r => [r.playerId, r]));
  assert.equal(byId[2].points, POINTS_BY_RANK[0], 'Bob first → 4 pts');
  assert.equal(byId[1].points, POINTS_BY_RANK[1], 'Alice 2nd → 3 pts');
  assert.equal(byId[3].points, POINTS_BY_RANK[2], 'Cara 3rd → 2 pts');
  assert.equal(byId[4].points, POINTS_BY_RANK[3], 'Dan 4th → 1 pt');
});

test('ROUND_ENDED includes targetId even when players are locked out', () => {
  const h = makeServices();
  h.setRandomSeries([0, 0.9, 0.9]);  // target pick, then 2 distractor frames
  const game = createImageGame({ pool: TWO_POOL, maxRoundMs: 2_000 });  // short cap
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  const targetFromReveal = h.byType('ROUND_REVEAL')[0].targetId;

  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  pressButton(game, h.services, alice);   // distractor frame → lockout, ends early
  const ended = h.byType('ROUND_ENDED')[0];
  assert.equal(ended.targetId, targetFromReveal);
});

test('round ends with timedOut=true when maxRoundMs elapses without commitment', () => {
  const h = makeServices();
  h.setRandomSeries([0, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9]);  // target picked, but stream is all distractors
  const game = createImageGame({ pool: TWO_POOL, maxRoundMs: 3 * IMAGE_SHOW_MS });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS + 3 * IMAGE_SHOW_MS);

  const ended = h.byType('ROUND_ENDED').find(m => m.timedOut === true);
  assert.ok(ended);
  assert.equal(ended.ranks[0].points, 0, 'no presses → 0 pts');
});

test('round ends early when all active players have committed', () => {
  const h = makeServices();
  h.setRandomSeries([0, 0, 0]);  // target, then target image frame
  const game = createImageGame({ pool: TWO_POOL });
  const alice = { id: 1, name: 'Alice' };
  const bob   = { id: 2, name: 'Bob' };
  h.players.push(alice, bob);
  game.onJoin(alice, h.services);
  game.onJoin(bob,   h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  assert.equal(game._debugState().phase, 'PLAY');

  pressButton(game, h.services, alice);
  pressButton(game, h.services, bob);

  assert.equal(game._debugState().phase, 'ROUND_ENDED', 'should end as soon as last player commits');
});

test('winner at win-score → GAME_OVER', () => {
  const h = makeServices();
  h.setRandomSeries([0, 0, 0, 0, 0, 0, 0]);  // everything a target
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
  assert.equal(game._debugState().phase, 'REVEAL');
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  pressButton(game, h.services, alice);
  assert.equal(game._debugState().phase, 'GAME_OVER');

  const over = h.byType('GAME_OVER')[0];
  assert.equal(over.winnerId, 1);
  assert.equal(over.scores[1], 8);
});

test('NEW_GAME from GAME_OVER resets scores and returns to LOBBY', () => {
  const h = makeServices();
  h.setRandomSeries([0, 0, 0]);
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
  // Sanity-check the constant — surface in the exports so anyone setting
  // game-specific timeouts knows the baseline.
  assert.equal(MAX_ROUND_MS, 60_000);
});
