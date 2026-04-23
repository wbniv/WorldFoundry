// Unit tests for the Worst Take Wins state machine. Drives the plugin
// directly with a mocked services surface (deterministic clock / random /
// schedule + a sendTo spy so we can verify private hand delivery). No WS.

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  createWorstTakeWinsGame,
  DEFAULT_HAND_SIZE,
  DEFAULT_WIN_SCORE,
  SCORE_PAUSE_MS,
} = require('../worst-take-wins');

// ───── mock services ─────────────────────────────────────────────────────

function makeServices({ players = [], random = 0.5 } = {}) {
  let time = 1_000_000;
  const broadcasts = [];
  const privates = [];      // { playerId, msg }
  const scheduled = [];
  let nextId = 1;

  function advance(ms) {
    const target = time + ms;
    while (true) {
      const due = scheduled
        .filter(s => s.fireAt <= target)
        .sort((a, b) => a.fireAt - b.fireAt);
      if (due.length === 0) { time = target; break; }
      const [next] = due;
      time = next.fireAt;
      scheduled.splice(scheduled.indexOf(next), 1);
      next.fn();
    }
  }

  const services = {
    broadcast(msg) { broadcasts.push(msg); },
    sendTo(playerId, msg) { privates.push({ playerId, msg }); },
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
    advance,
    broadcasts,
    privates,
    byType(t) { return broadcasts.filter(m => m.type === t); },
    privatesByType(t) { return privates.filter(p => p.msg.type === t); },
    privatesTo(id, t) { return privates.filter(p => p.playerId === id && (!t || p.msg.type === t)); },
    players,
    get time() { return time; },
    setRandom(r) { services.random = () => r; },
    resetCaptures() { broadcasts.length = 0; privates.length = 0; },
  };
}

// Minimal deck — enough for a few rounds with predictable draws. Cards are
// popped from the end after shuffling, so list them in the order you want
// them drawn under random=0 (which makes shuffle a no-op-ish identity
// sequence; but easier is just to ignore order and assert on counts).
function miniContent() {
  const prompts = [];
  for (let i = 1; i <= 12; i++) prompts.push({ id: `p${i}`, text: `prompt ${i} ____.`, blanks: 1 });
  const responses = [];
  for (let i = 1; i <= 60; i++) responses.push({ id: `r${i}`, text: `response ${i}` });
  return { prompts, responses };
}

function startedGame({ names = ['Alice', 'Bob', 'Carol'], opts = {} } = {}) {
  const players = names.map((n, i) => ({ id: i + 1, name: n }));
  const ctx = makeServices({ players });
  const game = createWorstTakeWinsGame({ content: miniContent(), ...opts });
  for (const p of players) game.onJoin(p, ctx.services);
  ctx.resetCaptures();  // drop the onJoin PHASE/DEAL_HAND noise
  game.onMessage(players[0], { type: 'START_GAME' }, ctx.services);
  return { game, ctx, players };
}

// ───── tests ─────────────────────────────────────────────────────────────

test('starts in LOBBY; onJoin registers player with score 0 and catch-up PHASE', () => {
  const alice = { id: 1, name: 'Alice' };
  const ctx = makeServices({ players: [alice] });
  const game = createWorstTakeWinsGame({ content: miniContent() });
  assert.equal(game._debugState().phase, 'LOBBY');
  game.onJoin(alice, ctx.services);
  assert.equal(game._debugState().scores.get(1), 0);
  // onJoin sends a private PHASE catch-up + an empty DEAL_HAND to smooth rejoins.
  const privates = ctx.privatesTo(1);
  assert.ok(privates.some(p => p.msg.type === 'PHASE' && p.msg.phase === 'LOBBY'));
  assert.ok(privates.some(p => p.msg.type === 'DEAL_HAND'));
});

test('START_GAME from non-host is ignored', () => {
  const alice = { id: 1, name: 'Alice' }, bob = { id: 2, name: 'Bob' }, carol = { id: 3, name: 'Carol' };
  const ctx = makeServices({ players: [alice, bob, carol] });
  const game = createWorstTakeWinsGame({ content: miniContent() });
  game.onJoin(alice, ctx.services);
  game.onJoin(bob, ctx.services);
  game.onJoin(carol, ctx.services);
  game.onMessage(bob, { type: 'START_GAME' }, ctx.services);
  assert.equal(game._debugState().phase, 'LOBBY');
});

test('START_GAME with <3 players surfaces an ERROR and stays in LOBBY', () => {
  const alice = { id: 1, name: 'Alice' }, bob = { id: 2, name: 'Bob' };
  const ctx = makeServices({ players: [alice, bob] });
  const game = createWorstTakeWinsGame({ content: miniContent() });
  game.onJoin(alice, ctx.services);
  game.onJoin(bob, ctx.services);
  game.onMessage(alice, { type: 'START_GAME' }, ctx.services);
  assert.equal(game._debugState().phase, 'LOBBY');
  const errs = ctx.privatesTo(1, 'ERROR');
  assert.equal(errs.length, 1);
  assert.equal(errs[0].msg.code, 'NOT_ENOUGH_PLAYERS');
});

test('START_GAME from host deals 7 cards privately to each player and broadcasts SHOW_PROMPT', () => {
  const { game, ctx, players } = startedGame();
  assert.equal(game._debugState().phase, 'SHOW_PROMPT');
  for (const p of players) {
    const deals = ctx.privatesTo(p.id, 'DEAL_HAND');
    assert.equal(deals.length, 1, `one DEAL_HAND for player ${p.id}`);
    assert.equal(deals[0].msg.cards.length, DEFAULT_HAND_SIZE);
  }
  const shows = ctx.byType('SHOW_PROMPT');
  assert.equal(shows.length, 1);
  assert.ok(shows[0].prompt);
  assert.equal(typeof shows[0].prompt.text, 'string');
  // Submission counter announces total = players - judge.
  const counts = ctx.byType('SUBMISSION_COUNT');
  assert.equal(counts[0].submitted, 0);
  assert.equal(counts[0].total, players.length - 1);
});

test('no two players receive overlapping cards at deal', () => {
  const { ctx, players } = startedGame();
  const hands = players.map((p) => ctx.privatesTo(p.id, 'DEAL_HAND')[0].msg.cards.map(c => c.id));
  const all = hands.flat();
  assert.equal(new Set(all).size, all.length, 'dealt card ids must all be distinct');
});

test('SUBMIT_CARDS with wrong count is rejected', () => {
  const { game, ctx, players } = startedGame();
  const judgeId = game._debugState().round.judgeId;
  const bob = players.find((p) => p.id !== judgeId);
  const bobHand = ctx.privatesTo(bob.id, 'DEAL_HAND')[0].msg.cards;
  ctx.resetCaptures();
  // blanks=1 but submit 2 cards
  game.onMessage(bob, { type: 'SUBMIT_CARDS', cardIds: [bobHand[0].id, bobHand[1].id] }, ctx.services);
  const counts = ctx.byType('SUBMISSION_COUNT');
  assert.equal(counts.length, 0, 'no submission recorded');
  assert.equal(game._debugState().round.submissions.size, 0);
});

test('judge cannot SUBMIT_CARDS', () => {
  const { game, ctx, players } = startedGame();
  const judgeId = game._debugState().round.judgeId;
  const judge = players.find((p) => p.id === judgeId);
  const judgeHand = ctx.privatesTo(judge.id, 'DEAL_HAND')[0].msg.cards;
  ctx.resetCaptures();
  game.onMessage(judge, { type: 'SUBMIT_CARDS', cardIds: [judgeHand[0].id] }, ctx.services);
  assert.equal(game._debugState().round.submissions.size, 0);
});

test('SUBMIT_CARDS with a card not in your hand is rejected', () => {
  const { game, ctx, players } = startedGame();
  const judgeId = game._debugState().round.judgeId;
  const bob = players.find((p) => p.id !== judgeId);
  ctx.resetCaptures();
  game.onMessage(bob, { type: 'SUBMIT_CARDS', cardIds: ['r-does-not-exist'] }, ctx.services);
  assert.equal(game._debugState().round.submissions.size, 0);
});

test('double-submit is ignored', () => {
  const { game, ctx, players } = startedGame();
  const judgeId = game._debugState().round.judgeId;
  const nonJudges = players.filter((p) => p.id !== judgeId);
  const bob = nonJudges[0];
  const bobHand = ctx.privatesTo(bob.id, 'DEAL_HAND')[0].msg.cards;
  game.onMessage(bob, { type: 'SUBMIT_CARDS', cardIds: [bobHand[0].id] }, ctx.services);
  game.onMessage(bob, { type: 'SUBMIT_CARDS', cardIds: [bobHand[1].id] }, ctx.services);
  assert.equal(game._debugState().round.submissions.size, 1);
});

test('all submissions in → JUDGE_REVEAL_START with playerId stripped and submissions shuffled', () => {
  const { game, ctx, players } = startedGame();
  const judgeId = game._debugState().round.judgeId;
  const nonJudges = players.filter((p) => p.id !== judgeId);
  for (const p of nonJudges) {
    const hand = ctx.privatesTo(p.id, 'DEAL_HAND')[0].msg.cards;
    game.onMessage(p, { type: 'SUBMIT_CARDS', cardIds: [hand[0].id] }, ctx.services);
  }
  assert.equal(game._debugState().phase, 'JUDGE_REVEAL');
  const reveal = ctx.byType('JUDGE_REVEAL_START')[0];
  assert.ok(reveal);
  assert.equal(reveal.submissions.length, nonJudges.length);
  for (const s of reveal.submissions) {
    assert.equal(s.playerId, undefined, 'reveal must NOT expose playerId');
    assert.ok(Array.isArray(s.cards));
    assert.ok(s.cards[0].text, 'resolved response text should be present');
  }
});

test('JUDGE_ADVANCE advances only for the judge', () => {
  const { game, ctx, players } = startedGame();
  const judgeId = game._debugState().round.judgeId;
  const nonJudges = players.filter((p) => p.id !== judgeId);
  const judge = players.find((p) => p.id === judgeId);
  for (const p of nonJudges) {
    const hand = ctx.privatesTo(p.id, 'DEAL_HAND')[0].msg.cards;
    game.onMessage(p, { type: 'SUBMIT_CARDS', cardIds: [hand[0].id] }, ctx.services);
  }
  ctx.resetCaptures();
  game.onMessage(nonJudges[0], { type: 'JUDGE_ADVANCE' }, ctx.services);
  assert.equal(ctx.byType('REVEAL_NEXT').length, 0);
  game.onMessage(judge, { type: 'JUDGE_ADVANCE' }, ctx.services);
  assert.equal(ctx.byType('REVEAL_NEXT').length, 1);
});

test('JUDGE_PICK by non-judge is ignored; judge picks → ROUND_WINNER + score increments', () => {
  const { game, ctx, players } = startedGame();
  const judgeId = game._debugState().round.judgeId;
  const nonJudges = players.filter((p) => p.id !== judgeId);
  const judge = players.find((p) => p.id === judgeId);
  for (const p of nonJudges) {
    const hand = ctx.privatesTo(p.id, 'DEAL_HAND')[0].msg.cards;
    game.onMessage(p, { type: 'SUBMIT_CARDS', cardIds: [hand[0].id] }, ctx.services);
  }
  const reveal = ctx.byType('JUDGE_REVEAL_START')[0];
  const targetSubmissionId = reveal.submissions[0].submissionId;
  const winnerSub = game._debugState().round.submissions.get(targetSubmissionId);

  // Non-judge attempt: ignored.
  ctx.resetCaptures();
  game.onMessage(nonJudges[0], { type: 'JUDGE_PICK', submissionId: targetSubmissionId }, ctx.services);
  assert.equal(ctx.byType('ROUND_WINNER').length, 0);

  // Judge picks.
  game.onMessage(judge, { type: 'JUDGE_PICK', submissionId: targetSubmissionId }, ctx.services);
  const rw = ctx.byType('ROUND_WINNER')[0];
  assert.ok(rw);
  assert.equal(rw.playerId, winnerSub.playerId);
  assert.equal(rw.submissionId, targetSubmissionId);
  assert.ok(rw.promptCard.text);
  assert.equal(game._debugState().scores.get(winnerSub.playerId), 1);
  assert.equal(game._debugState().phase, 'SCORE');
});

test('next round after SCORE pause rotates the judge', () => {
  const { game, ctx, players } = startedGame();
  const firstJudgeId = game._debugState().round.judgeId;
  const nonJudges = players.filter((p) => p.id !== firstJudgeId);
  const judge = players.find((p) => p.id === firstJudgeId);
  for (const p of nonJudges) {
    const hand = ctx.privatesTo(p.id, 'DEAL_HAND')[0].msg.cards;
    game.onMessage(p, { type: 'SUBMIT_CARDS', cardIds: [hand[0].id] }, ctx.services);
  }
  const reveal = ctx.byType('JUDGE_REVEAL_START')[0];
  game.onMessage(judge, { type: 'JUDGE_PICK', submissionId: reveal.submissions[0].submissionId }, ctx.services);
  ctx.advance(SCORE_PAUSE_MS + 1);
  const secondJudgeId = game._debugState().round.judgeId;
  assert.notEqual(secondJudgeId, firstJudgeId, 'judge should rotate');
  assert.equal(game._debugState().phase, 'SHOW_PROMPT');
});

test('winner reaches winScore → GAME_OVER + GAME_WINNER', () => {
  // winScore=2 makes this reachable in two rounds, deterministically give
  // bob the first-pick and first wins.
  const { game, ctx, players } = startedGame({ opts: { winScore: 2 } });
  let round = 0;
  while (game._debugState().phase !== 'GAME_OVER') {
    round++;
    const judgeId = game._debugState().round.judgeId;
    const nonJudges = players.filter((p) => p.id !== judgeId);
    const judge = players.find((p) => p.id === judgeId);
    for (const p of nonJudges) {
      // Only pull a DEAL_HAND from *this* round — the earliest one is the
      // round 1 deal. Simpler: just look at current hand from state.
      const hand = game._debugState().hands.get(p.id);
      assert.ok(hand.length >= 1);
      game.onMessage(p, { type: 'SUBMIT_CARDS', cardIds: [hand[0].id] }, ctx.services);
    }
    const reveal = ctx.byType('JUDGE_REVEAL_START').at(-1);
    // Always pick the first submission (deterministic; winner rotates via
    // shuffle seeded by random=0.5).
    game.onMessage(judge, { type: 'JUDGE_PICK', submissionId: reveal.submissions[0].submissionId }, ctx.services);
    ctx.advance(SCORE_PAUSE_MS + 1);
    assert.ok(round < 20, 'sanity: game should end in under 20 rounds');
  }
  const winner = ctx.byType('GAME_WINNER')[0];
  assert.ok(winner);
  assert.ok(winner.playerId);
});

test('NEW_GAME from host resets state', () => {
  const { game, ctx, players } = startedGame({ opts: { winScore: 1 } });
  const judgeId = game._debugState().round.judgeId;
  const nonJudges = players.filter((p) => p.id !== judgeId);
  const judge = players.find((p) => p.id === judgeId);
  for (const p of nonJudges) {
    const hand = game._debugState().hands.get(p.id);
    game.onMessage(p, { type: 'SUBMIT_CARDS', cardIds: [hand[0].id] }, ctx.services);
  }
  const reveal = ctx.byType('JUDGE_REVEAL_START')[0];
  game.onMessage(judge, { type: 'JUDGE_PICK', submissionId: reveal.submissions[0].submissionId }, ctx.services);
  assert.equal(game._debugState().phase, 'GAME_OVER');

  game.onMessage(players[0], { type: 'NEW_GAME' }, ctx.services);
  assert.equal(game._debugState().phase, 'LOBBY');
  for (const [, s] of game._debugState().scores) assert.equal(s, 0);
});

test('auto-submit fires after timeout, moves to JUDGE_REVEAL', () => {
  const { game, ctx, players } = startedGame({ opts: { submitTimeoutMs: 1_000 } });
  const judgeId = game._debugState().round.judgeId;
  // Nobody submits; advance past the timeout.
  ctx.advance(1_100);
  assert.equal(game._debugState().phase, 'JUDGE_REVEAL');
  const reveal = ctx.byType('JUDGE_REVEAL_START')[0];
  assert.equal(reveal.submissions.length, players.length - 1);
  // Every submission must be flagged auto=true in state (the broadcast
  // doesn't expose that field; check via _debugState).
  for (const s of game._debugState().round.submissions.values()) assert.equal(s.auto, true);
});

test('judge leaving mid-round aborts and next round gets a new judge', () => {
  // 4 players so that after the judge leaves we still have ≥ minPlayers (3).
  const { game, ctx, players } = startedGame({ names: ['Alice', 'Bob', 'Carol', 'Dave'] });
  const firstJudgeId = game._debugState().round.judgeId;
  const judge = players.find((p) => p.id === firstJudgeId);
  const idx = ctx.players.findIndex((p) => p.id === firstJudgeId);
  ctx.players.splice(idx, 1);
  ctx.resetCaptures();
  game.onLeave(judge, ctx.services);
  ctx.advance(5);  // scheduled 0ms fresh round
  assert.equal(game._debugState().phase, 'SHOW_PROMPT');
  const secondJudgeId = game._debugState().round.judgeId;
  assert.notEqual(secondJudgeId, firstJudgeId);
});

test('submitter leaving pre-submit decrements total expected and advances if last', () => {
  // 4 players so we have 2 non-judges remaining after one leaves.
  const { game, ctx, players } = startedGame({ names: ['Alice', 'Bob', 'Carol', 'Dave'] });
  const judgeId = game._debugState().round.judgeId;
  const nonJudges = players.filter((p) => p.id !== judgeId);
  // Submit for 2 of 3 non-judges, then the 3rd leaves → JUDGE_REVEAL.
  for (let i = 0; i < nonJudges.length - 1; i++) {
    const p = nonJudges[i];
    const hand = game._debugState().hands.get(p.id);
    game.onMessage(p, { type: 'SUBMIT_CARDS', cardIds: [hand[0].id] }, ctx.services);
  }
  const leaver = nonJudges.at(-1);
  const idx = ctx.players.findIndex((p) => p.id === leaver.id);
  ctx.players.splice(idx, 1);
  game.onLeave(leaver, ctx.services);
  assert.equal(game._debugState().phase, 'JUDGE_REVEAL');
});

test('too many leaves (below minPlayers) folds back to LOBBY', () => {
  const { game, ctx, players } = startedGame();
  const p = players[0];
  const idx = ctx.players.findIndex((x) => x.id === p.id);
  ctx.players.splice(idx, 1);
  game.onLeave(p, ctx.services);
  assert.equal(game._debugState().phase, 'LOBBY');
});

test('mid-game join: PHASE + empty DEAL_HAND sent to newcomer, current SHOW_PROMPT replayed', () => {
  const { game, ctx } = startedGame();
  const latecomer = { id: 99, name: 'Dave' };
  ctx.players.push(latecomer);
  ctx.resetCaptures();
  game.onJoin(latecomer, ctx.services);
  const privates = ctx.privatesTo(99);
  assert.ok(privates.find((p) => p.msg.type === 'PHASE' && p.msg.phase === 'SHOW_PROMPT'));
  assert.ok(privates.find((p) => p.msg.type === 'SHOW_PROMPT'));
  const deal = privates.find((p) => p.msg.type === 'DEAL_HAND');
  assert.ok(deal);
  assert.deepEqual(deal.msg.cards, []);  // spectator until next DEAL
});

test('onReconnect mid-round: preserves hand + scores, replays PHASE + SHOW_PROMPT + real hand', () => {
  const { game, ctx, players } = startedGame();
  // Pick a non-judge so we can verify they have a real hand to restore.
  const judgeId = game._debugState().round.judgeId;
  const alice = players.find((p) => p.id !== judgeId);
  const originalHand = game._debugState().hands.get(alice.id).map((c) => c.id);
  assert.equal(originalHand.length, 7);

  // Simulate grace-window reconnect: the player object in ctx.players stays
  // unchanged (platform's grace window keeps the slot), only the game hook
  // call differs.
  ctx.resetCaptures();
  game.onReconnect(alice, ctx.services);

  const privates = ctx.privatesTo(alice.id);
  const phase = privates.find((p) => p.msg.type === 'PHASE');
  assert.ok(phase);
  assert.equal(phase.msg.phase, 'SHOW_PROMPT');
  const show = privates.find((p) => p.msg.type === 'SHOW_PROMPT');
  assert.ok(show, 'in-progress SHOW_PROMPT should be replayed on resume');
  const deal = privates.find((p) => p.msg.type === 'DEAL_HAND');
  assert.ok(deal);
  // Critical: DEAL_HAND on resume carries the actual hand, not an empty one.
  assert.deepEqual(deal.msg.cards.map((c) => c.id), originalHand);
  // Hand + scores untouched in state.
  assert.equal(game._debugState().hands.get(alice.id).length, 7);
});

test('onReconnect for a player who had never been dealt: empty hand, PHASE-only catch-up', () => {
  // Reach a state where alice exists in judgeOrder/scores but has no hand —
  // e.g. she joined during SHOW_PROMPT as a spectator, then the WS dropped.
  const { game, ctx } = startedGame();
  const spectator = { id: 99, name: 'Eve' };
  ctx.players.push(spectator);
  game.onJoin(spectator, ctx.services);
  // Nobody dealt Eve a hand yet.
  assert.equal((game._debugState().hands.get(99) || []).length, 0);

  ctx.resetCaptures();
  game.onReconnect(spectator, ctx.services);
  const deal = ctx.privatesTo(99).find((p) => p.msg.type === 'DEAL_HAND');
  assert.ok(deal);
  assert.deepEqual(deal.msg.cards, []);
});

test('default allowPick2=false skips blanks>1 prompts', () => {
  const content = {
    prompts: [
      { id: 'p-pick2', text: 'x ____ + ____', blanks: 2 },
      { id: 'p-pick1', text: 'x ____',        blanks: 1 },
    ],
    responses: [],
  };
  for (let i = 1; i <= 40; i++) content.responses.push({ id: `r${i}`, text: `r${i}` });
  const players = [1, 2, 3].map((id) => ({ id, name: `P${id}` }));
  const ctx = makeServices({ players });
  const game = createWorstTakeWinsGame({ content });
  for (const p of players) game.onJoin(p, ctx.services);
  ctx.resetCaptures();
  game.onMessage(players[0], { type: 'START_GAME' }, ctx.services);
  const show = ctx.byType('SHOW_PROMPT')[0];
  assert.equal(show.prompt.blanks, 1, 'must skip pick-2 prompt');
});
