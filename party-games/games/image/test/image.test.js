// Unit tests for the image-recognition state machine. Drives the plugin
// directly (no WebSocket) with a mocked services surface: controllable time,
// deterministic random, manual schedule(). Same shape as reaction tests.

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  createImageGame,
  IMAGE_POOL,
  REVEAL_MS,
  REVEAL_CLEAR_MS,
  IMAGE_SHOW_MS,
  MIN_DISTRACTORS,
  MAX_DISTRACTORS,
  SCORING_WINDOW_MS,
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

  // deterministic "random" — cycles through a supplied series of values so
  // tests can force specific target + distractor picks.
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
  assert.ok(reveal, 'expected a ROUND_REVEAL broadcast');
  assert.equal(reveal.roundId, 1);
  assert.equal(reveal.showMs, REVEAL_MS);
  assert.equal(reveal.clearMs, REVEAL_CLEAR_MS);
  assert.ok(IMAGE_POOL.includes(reveal.targetId), 'target must come from pool');
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

test('after REVEAL_MS + REVEAL_CLEAR_MS transitions to DISTRACTORS', () => {
  const h = makeServices();
  const game = createImageGame();
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);

  h.advance(REVEAL_MS + REVEAL_CLEAR_MS - 1);
  assert.equal(game._debugState().phase, 'REVEAL');
  h.advance(1);
  assert.equal(game._debugState().phase, 'DISTRACTORS');
});

test('DISTRACTORS streams SHOW_IMAGE frames at IMAGE_SHOW_MS intervals, none with isTarget=true until the final frame', () => {
  const h = makeServices();
  // Force deterministic pool indices: target = pool[0], distractor count = MIN
  // (random=0 → pickInt returns low bound).
  h.setRandom(0);
  const game = createImageGame();
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);

  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  assert.equal(game._debugState().phase, 'DISTRACTORS');

  // 4 distractors → 4 SHOW_IMAGE events fire before target, each non-target.
  for (let i = 0; i < MIN_DISTRACTORS; i++) {
    h.advance(i === 0 ? 0 : IMAGE_SHOW_MS);
    // The first distractor is emitted synchronously when DISTRACTORS begins;
    // subsequent ones each IMAGE_SHOW_MS later.
  }
  const showDistractors = h.byType('SHOW_IMAGE').filter(m => !m.isTarget);
  assert.equal(showDistractors.length, MIN_DISTRACTORS, 'distractor count should match MIN_DISTRACTORS');
  for (const m of showDistractors) {
    assert.equal(m.showMs, IMAGE_SHOW_MS);
    assert.ok(IMAGE_POOL.includes(m.imageId));
  }
  // Target image can't equal any distractor (pool exclusion during build).
  const targetFromReveal = h.byType('ROUND_REVEAL')[0].targetId;
  for (const m of showDistractors) {
    assert.notEqual(m.imageId, targetFromReveal, 'distractor should never be the target');
  }
});

test('target fires after all distractors; phase transitions to TARGET; SHOW_IMAGE.isTarget=true', () => {
  const h = makeServices();
  h.setRandom(0);  // MIN_DISTRACTORS, target = pool[0]
  const game = createImageGame();
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);

  // Advance through REVEAL + CLEAR + all distractors.
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS + MIN_DISTRACTORS * IMAGE_SHOW_MS);
  assert.equal(game._debugState().phase, 'TARGET');

  const targetFrames = h.byType('SHOW_IMAGE').filter(m => m.isTarget);
  assert.equal(targetFrames.length, 1, 'exactly one target SHOW_IMAGE');
  const targetFromReveal = h.byType('ROUND_REVEAL')[0].targetId;
  assert.equal(targetFrames[0].imageId, targetFromReveal, 'target SHOW_IMAGE matches ROUND_REVEAL.targetId');
});

test('pre-target distractor count stays within [MIN, MAX]', () => {
  // Pre-target = distractors with a seq index less than the target's seq index.
  // The stream keeps cycling post-target (extra distractors until the scoring
  // window closes) — those don't count toward the pre-target bound.
  for (const r of [0, 0.25, 0.5, 0.75, 1.0]) {
    const h = makeServices();
    h.setRandom(r);
    const game = createImageGame();
    const alice = { id: 1, name: 'Alice' };
    h.players.push(alice);
    game.onJoin(alice, h.services);
    game.onMessage(alice, { type: 'START_GAME' }, h.services);
    // Advance far enough to land inside TARGET phase but not past the scoring window.
    h.advance(REVEAL_MS + REVEAL_CLEAR_MS + MAX_DISTRACTORS * IMAGE_SHOW_MS);
    const target = h.byType('SHOW_IMAGE').find(m => m.isTarget);
    assert.ok(target, `random=${r}: target SHOW_IMAGE should have fired by now`);
    const preTargetDistractors = h.byType('SHOW_IMAGE').filter(m => !m.isTarget && m.seq < target.seq).length;
    assert.ok(
      preTargetDistractors >= MIN_DISTRACTORS && preTargetDistractors <= MAX_DISTRACTORS,
      `random=${r}: preTargetDistractors=${preTargetDistractors} out of [${MIN_DISTRACTORS},${MAX_DISTRACTORS}]`,
    );
  }
});

test('SHOW_IMAGE stream continues cycling during TARGET phase, then stops at endRound', () => {
  const h = makeServices();
  h.setRandom(0);  // MIN_DISTRACTORS pre-target, target = pool[0]
  const game = createImageGame();
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);

  // Advance into TARGET phase.
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS + MIN_DISTRACTORS * IMAGE_SHOW_MS);
  assert.equal(game._debugState().phase, 'TARGET');
  const countAtTargetFire = h.byType('SHOW_IMAGE').length;

  // Midway through scoring window, more SHOW_IMAGE frames should have fired.
  h.advance(IMAGE_SHOW_MS * 2);
  assert.equal(game._debugState().phase, 'TARGET', 'still in TARGET mid-scoring-window');
  const countMidScoring = h.byType('SHOW_IMAGE').length;
  assert.ok(countMidScoring > countAtTargetFire, 'stream should keep cycling past the target');
  const postTargetFrames = h.byType('SHOW_IMAGE').filter(m => !m.isTarget).slice(-2);
  for (const m of postTargetFrames) {
    assert.equal(m.isTarget, false, 'post-target frames should not be flagged isTarget');
    assert.notEqual(m.imageId, h.byType('ROUND_REVEAL')[0].targetId, 'post-target distractor must not equal the target');
  }

  // Advance past scoring window → endRound → cycling stops.
  h.advance(SCORING_WINDOW_MS);
  assert.equal(game._debugState().phase, 'ROUND_ENDED');
  const countAfterEnd = h.byType('SHOW_IMAGE').length;
  h.advance(IMAGE_SHOW_MS * 5);
  assert.equal(h.byType('SHOW_IMAGE').length, countAfterEnd, 'no more images after round ends');
});

test('BUTTON_PRESS during REVEAL → early-press lockout', () => {
  const h = makeServices();
  h.setRandom(0);
  const game = createImageGame();
  const alice = { id: 1, name: 'Alice' };
  const bob   = { id: 2, name: 'Bob' };
  h.players.push(alice, bob);
  game.onJoin(alice, h.services);
  game.onJoin(bob,   h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);

  assert.equal(game._debugState().phase, 'REVEAL');
  pressButton(game, h.services, bob);
  assert.ok(game._debugState().round.earlyPressed.has(2));
  const ep = h.byType('EARLY_PRESS');
  assert.equal(ep.length, 1);
  assert.equal(ep[0].playerId, 2);
});

test('BUTTON_PRESS during DISTRACTORS → early-press lockout', () => {
  const h = makeServices();
  h.setRandom(0);
  const game = createImageGame();
  const alice = { id: 1, name: 'Alice' };
  const bob   = { id: 2, name: 'Bob' };
  h.players.push(alice, bob);
  game.onJoin(alice, h.services);
  game.onJoin(bob,   h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS);
  assert.equal(game._debugState().phase, 'DISTRACTORS');
  pressButton(game, h.services, bob);
  assert.ok(game._debugState().round.earlyPressed.has(2));
});

test('BUTTON_PRESS during TARGET → scored; ranked 4/3/2/1', () => {
  const h = makeServices();
  h.setRandom(0);
  const game = createImageGame();
  const alice = { id: 1, name: 'Alice' };
  const bob   = { id: 2, name: 'Bob' };
  const cara  = { id: 3, name: 'Cara' };
  const dan   = { id: 4, name: 'Dan' };
  h.players.push(alice, bob, cara, dan);
  for (const p of h.players) game.onJoin(p, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);

  h.advance(REVEAL_MS + REVEAL_CLEAR_MS + MIN_DISTRACTORS * IMAGE_SHOW_MS);
  assert.equal(game._debugState().phase, 'TARGET');

  // Presses arrive in order Bob → Alice → Cara → Dan, each 10 ms apart so
  // server-receive ordering is stable.
  pressButton(game, h.services, bob);   h.advance(10);
  pressButton(game, h.services, alice); h.advance(10);
  pressButton(game, h.services, cara);  h.advance(10);
  pressButton(game, h.services, dan);

  h.advance(SCORING_WINDOW_MS);
  const ended = h.byType('ROUND_ENDED')[0];
  assert.ok(ended, 'ROUND_ENDED should fire after scoring window');
  const byId = Object.fromEntries(ended.ranks.map(r => [r.playerId, r]));
  assert.equal(byId[2].points, POINTS_BY_RANK[0], 'Bob pressed first → 4 pts');
  assert.equal(byId[1].points, POINTS_BY_RANK[1], 'Alice 2nd → 3 pts');
  assert.equal(byId[3].points, POINTS_BY_RANK[2], 'Cara 3rd → 2 pts');
  assert.equal(byId[4].points, POINTS_BY_RANK[3], 'Dan 4th → 1 pt');
});

test('ROUND_ENDED includes targetId', () => {
  const h = makeServices();
  h.setRandom(0);
  const game = createImageGame();
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  const targetFromReveal = h.byType('ROUND_REVEAL')[0].targetId;

  h.advance(REVEAL_MS + REVEAL_CLEAR_MS + MIN_DISTRACTORS * IMAGE_SHOW_MS);
  pressButton(game, h.services, alice);
  h.advance(SCORING_WINDOW_MS);
  const ended = h.byType('ROUND_ENDED')[0];
  assert.equal(ended.targetId, targetFromReveal);
});

test('early-pressed player scores 0 even if they press again during TARGET', () => {
  const h = makeServices();
  h.setRandom(0);
  const game = createImageGame();
  const alice = { id: 1, name: 'Alice' };
  const bob   = { id: 2, name: 'Bob' };
  h.players.push(alice, bob);
  game.onJoin(alice, h.services);
  game.onJoin(bob,   h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);

  // Lock Bob out during REVEAL.
  pressButton(game, h.services, bob);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS + MIN_DISTRACTORS * IMAGE_SHOW_MS);
  // Bob tries to press during TARGET — should not be recorded.
  pressButton(game, h.services, bob);
  pressButton(game, h.services, alice);
  h.advance(SCORING_WINDOW_MS);
  const ended = h.byType('ROUND_ENDED')[0];
  const byId = Object.fromEntries(ended.ranks.map(r => [r.playerId, r]));
  assert.equal(byId[2].points, 0);
  assert.equal(byId[2].lockedOut, true);
  assert.equal(byId[1].points, POINTS_BY_RANK[0]);
});

test('winner at 10 points → GAME_OVER', () => {
  const h = makeServices();
  h.setRandom(0);
  const game = createImageGame({ winScore: 8 });  // shorten for test speed: 2 rounds of solo 4-pt wins
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);

  // Round 1: Alice solo presses during TARGET → 4 pts.
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS + MIN_DISTRACTORS * IMAGE_SHOW_MS);
  pressButton(game, h.services, alice);
  h.advance(SCORING_WINDOW_MS);
  assert.equal(game._debugState().phase, 'ROUND_ENDED');
  // Round 2 scheduled.
  h.advance(ROUND_END_PAUSE_MS);
  assert.equal(game._debugState().phase, 'REVEAL');
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS + MIN_DISTRACTORS * IMAGE_SHOW_MS);
  pressButton(game, h.services, alice);
  h.advance(SCORING_WINDOW_MS);

  assert.equal(game._debugState().phase, 'GAME_OVER');
  const over = h.byType('GAME_OVER')[0];
  assert.equal(over.winnerId, 1);
  assert.equal(over.scores[1], 8);
});

test('NEW_GAME from GAME_OVER resets scores and returns to LOBBY', () => {
  const h = makeServices();
  h.setRandom(0);
  const game = createImageGame({ winScore: 4 });  // one round wins
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  h.advance(REVEAL_MS + REVEAL_CLEAR_MS + MIN_DISTRACTORS * IMAGE_SHOW_MS);
  pressButton(game, h.services, alice);
  h.advance(SCORING_WINDOW_MS);
  assert.equal(game._debugState().phase, 'GAME_OVER');

  game.onMessage(alice, { type: 'NEW_GAME' }, h.services);
  assert.equal(game._debugState().phase, 'LOBBY');
  assert.equal(game._debugState().scores.get(1), 0);
});

test('failsafe: round hanging past maxRoundMs force-ends with zero scores and timedOut flag', () => {
  // To provoke the failsafe we set maxRoundMs shorter than the natural round
  // length (REVEAL + CLEAR alone is 3500 ms), so the failsafe fires while the
  // round is still in REVEAL and nothing has progressed. In production
  // maxRoundMs = MAX_ROUND_MS = 60 s; natural rounds end in ~10-13 s, so it
  // never fires unless something is genuinely stuck.
  const h = makeServices();
  h.setRandom(0);
  const game = createImageGame({ maxRoundMs: 500 });
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  assert.equal(game._debugState().phase, 'REVEAL');

  h.advance(500);
  const ended = h.byType('ROUND_ENDED').find(m => m.timedOut === true);
  assert.ok(ended, 'failsafe ROUND_ENDED should have fired with timedOut=true');
  assert.equal(ended.ranks[0].points, 0, 'forced ending gives nobody points');
  assert.equal(game._debugState().phase, 'ROUND_ENDED');

  // Next round schedules normally after ROUND_END_PAUSE_MS.
  h.advance(ROUND_END_PAUSE_MS);
  assert.equal(game._debugState().phase, 'REVEAL', 'next round should have started');
});

test('onLeave with last player mid-round folds to LOBBY', () => {
  const h = makeServices();
  h.setRandom(0);
  const game = createImageGame();
  const alice = { id: 1, name: 'Alice' };
  h.players.push(alice);
  game.onJoin(alice, h.services);
  game.onMessage(alice, { type: 'START_GAME' }, h.services);
  assert.equal(game._debugState().phase, 'REVEAL');

  // Alice disconnects.
  h.players.length = 0;
  game.onLeave(alice, h.services);
  assert.equal(game._debugState().phase, 'LOBBY');
  assert.equal(game._debugState().round, null);
});
