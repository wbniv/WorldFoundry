// Image Recognition Game — server-side state machine. Mini-game 2.
//
// Plugs into platform createServer({ game: createImageGame() }).
// Flow: REVEAL (memorise target) → DISTRACTORS (4–8 non-target images stream) →
// TARGET (target shown; scoring window opens) → ROUND_ENDED → next / GAME_OVER.
// Same server-receive-timestamp adjudication as the reaction game.

const WIN_SCORE              = 10;
const REVEAL_MS              = 3000;    // target shown at start to memorise
const REVEAL_CLEAR_MS        =  500;    // blank between reveal and distractor stream
const IMAGE_SHOW_MS          =  800;    // duration each image is on screen (distractor or target)
const MIN_DISTRACTORS        =    4;    // inclusive
const MAX_DISTRACTORS        =    8;    // inclusive
const SCORING_WINDOW_MS      = 3000;    // after target SHOW_IMAGE, presses count for this long
const ROUND_END_PAUSE_MS     = 3000;    // pause between rounds
const POINTS_BY_RANK         = [4, 3, 2, 1];
const MIN_PLAYERS_TO_START   = 1;       // matches reaction; see platform README

// Pool of visually distinct flat icons (emoji v1; design doc calls for SVG in prod).
const IMAGE_POOL = [
  '🍎','⚡','🐸','🚀','🌙','☀️','🔥','💧','🎯','🎸',
  '🐙','🦒','🍕','🎁','🌈','🧊','🔮','🎪','🦖','🎨',
];

/**
 * Game lifecycle:
 *   LOBBY → REVEAL → DISTRACTORS → TARGET → ROUND_ENDED → (next round | GAME_OVER)
 *
 * Messages OUT (broadcast unless noted):
 *   PHASE          { phase, scores }
 *   ROUND_REVEAL   { roundId, targetId, showMs, clearMs }
 *   SHOW_IMAGE     { roundId, seq, imageId, showMs, isTarget, serverTs }
 *   EARLY_PRESS    { roundId, playerId, name }
 *   ROUND_ENDED    { roundId, ranks, scores, targetId }
 *   GAME_OVER      { winnerId, name, scores }
 *
 * Messages IN (controller):
 *   START_GAME                              (host only; from LOBBY / GAME_OVER)
 *   BUTTON_PRESS  { clientTs }              (any phase except LOBBY/ROUND_ENDED/GAME_OVER)
 *   NEW_GAME                                (host only; from GAME_OVER)
 */
function createImageGame(opts = {}) {
  const winScore = opts.winScore ?? WIN_SCORE;
  const pool     = opts.pool ?? IMAGE_POOL;

  const state = {
    phase: 'LOBBY',
    roundId: 0,
    round: null,        // { id, target, sequence: [{imageId, isTarget}], shownAt: Map(seq→serverTs),
                        //   targetShownAt, seqIdx, presses: Map, earlyPressed: Set }
    scores: new Map(),
    winScore,
  };
  let cancelTimer = null;

  function clearTimer() {
    if (cancelTimer) { cancelTimer(); cancelTimer = null; }
  }

  function broadcastPhase(services) {
    services.broadcast({
      type: 'PHASE',
      phase: state.phase,
      scores: Object.fromEntries(state.scores),
    });
  }

  function pickInt(services, min, max) {
    // [min, max] inclusive; tolerant of services.random() returning exactly 1.0 (tests do this).
    const span = max - min;
    return min + Math.min(Math.floor(services.random() * (span + 1)), span);
  }

  function buildSequence(services) {
    const target = pool[pickInt(services, 0, pool.length - 1)];
    const nDistractors = pickInt(services, MIN_DISTRACTORS, MAX_DISTRACTORS);
    const distractorPool = pool.filter((id) => id !== target);
    const distractors = [];
    for (let i = 0; i < nDistractors; i++) {
      distractors.push(distractorPool[pickInt(services, 0, distractorPool.length - 1)]);
    }
    const sequence = [
      ...distractors.map((imageId) => ({ imageId, isTarget: false })),
      { imageId: target, isTarget: true },
    ];
    return { target, sequence };
  }

  function startRound(services) {
    clearTimer();
    const { target, sequence } = buildSequence(services);
    state.phase = 'REVEAL';
    state.roundId += 1;
    state.round = {
      id: state.roundId,
      target,
      sequence,
      shownAt: new Map(),   // seqIdx → serverTs when broadcast
      targetShownAt: null,
      seqIdx: -1,
      presses: new Map(),
      earlyPressed: new Set(),
    };
    broadcastPhase(services);
    services.broadcast({
      type: 'ROUND_REVEAL',
      roundId: state.roundId,
      targetId: target,
      showMs: REVEAL_MS,
      clearMs: REVEAL_CLEAR_MS,
    });
    cancelTimer = services.schedule(REVEAL_MS + REVEAL_CLEAR_MS, () => startDistractors(services));
  }

  function startDistractors(services) {
    if (state.phase !== 'REVEAL') return;
    clearTimer();
    state.phase = 'DISTRACTORS';
    broadcastPhase(services);
    showNext(services);
  }

  function showNext(services) {
    const r = state.round;
    if (!r) return;
    const idx = r.seqIdx + 1;
    if (idx >= r.sequence.length) {
      // Should not happen — target is the last entry and triggers its own scoring schedule.
      return;
    }
    r.seqIdx = idx;
    const entry = r.sequence[idx];
    const serverTs = services.now();
    r.shownAt.set(idx, serverTs);

    if (entry.isTarget) {
      // Transition into TARGET phase before broadcasting SHOW_IMAGE so the
      // PHASE change lands first (controller updates its button before the
      // target fires).
      state.phase = 'TARGET';
      r.targetShownAt = serverTs;
      broadcastPhase(services);
      services.broadcast({
        type: 'SHOW_IMAGE',
        roundId: r.id,
        seq: idx,
        imageId: entry.imageId,
        showMs: IMAGE_SHOW_MS,
        isTarget: true,
        serverTs,
      });
      cancelTimer = services.schedule(SCORING_WINDOW_MS, () => endRound(services));
      return;
    }

    services.broadcast({
      type: 'SHOW_IMAGE',
      roundId: r.id,
      seq: idx,
      imageId: entry.imageId,
      showMs: IMAGE_SHOW_MS,
      isTarget: false,
      serverTs,
    });
    cancelTimer = services.schedule(IMAGE_SHOW_MS, () => showNext(services));
  }

  function endRound(services) {
    if (state.phase !== 'TARGET') return;
    clearTimer();

    const r = state.round;
    const orderedPresses = [...r.presses.entries()]
      .map(([pid, press]) => ({ playerId: pid, ...press }))
      .sort((a, b) => a.serverTs - b.serverTs);

    const allPlayers = services.getPlayers();
    const ranks = allPlayers.map((p) => {
      if (r.earlyPressed.has(p.id)) {
        return { playerId: p.id, name: p.name, points: 0, lockedOut: true, ms: null };
      }
      const idx = orderedPresses.findIndex((x) => x.playerId === p.id);
      if (idx === -1) {
        return { playerId: p.id, name: p.name, points: 0, ms: null };
      }
      const points = POINTS_BY_RANK[idx] ?? 0;
      const ms = orderedPresses[idx].serverTs - r.targetShownAt;
      return { playerId: p.id, name: p.name, points, ms };
    });

    for (const rk of ranks) {
      if (!state.scores.has(rk.playerId)) state.scores.set(rk.playerId, 0);
      if (rk.points > 0) {
        state.scores.set(rk.playerId, state.scores.get(rk.playerId) + rk.points);
      }
    }

    state.phase = 'ROUND_ENDED';
    const scoresObj = Object.fromEntries(state.scores);
    broadcastPhase(services);
    services.broadcast({
      type: 'ROUND_ENDED',
      roundId: state.roundId,
      ranks,
      scores: scoresObj,
      targetId: r.target,
    });

    let winner = null;
    for (const [pid, pts] of state.scores) {
      if (pts >= state.winScore) {
        const p = allPlayers.find((x) => x.id === pid);
        if (p) { winner = p; break; }
      }
    }
    if (winner) {
      state.phase = 'GAME_OVER';
      broadcastPhase(services);
      services.broadcast({
        type: 'GAME_OVER',
        winnerId: winner.id,
        name: winner.name,
        scores: scoresObj,
      });
      state.round = null;
    } else {
      cancelTimer = services.schedule(ROUND_END_PAUSE_MS, () => startRound(services));
    }
  }

  // ──── hooks ────────────────────────────────────────────────────────────────
  function onJoin(player /* , services */) {
    if (!state.scores.has(player.id)) state.scores.set(player.id, 0);
  }

  function onLeave(player, services) {
    state.scores.delete(player.id);
    if (state.round) {
      state.round.presses.delete(player.id);
      state.round.earlyPressed.delete(player.id);
    }
    if (services.getPlayers().length === 0 && state.phase !== 'LOBBY') {
      clearTimer();
      state.phase = 'LOBBY';
      state.round = null;
      broadcastPhase(services);
    }
  }

  function onMessage(player, msg, services) {
    switch (msg.type) {
      case 'START_GAME': {
        if (state.phase !== 'LOBBY' && state.phase !== 'GAME_OVER') return;
        const host = services.getHost();
        if (!host || host.id !== player.id) return;
        if (services.getPlayers().length < MIN_PLAYERS_TO_START) return;
        if (state.phase === 'GAME_OVER') state.scores = new Map();
        for (const p of services.getPlayers()) {
          if (!state.scores.has(p.id)) state.scores.set(p.id, 0);
        }
        startRound(services);
        break;
      }
      case 'BUTTON_PRESS': {
        const r = state.round;
        if (!r) return;
        if (state.phase === 'REVEAL' || state.phase === 'DISTRACTORS') {
          if (r.earlyPressed.has(player.id)) return;
          r.earlyPressed.add(player.id);
          services.broadcast({
            type: 'EARLY_PRESS',
            roundId: r.id,
            playerId: player.id,
            name: player.name,
          });
        } else if (state.phase === 'TARGET') {
          if (r.earlyPressed.has(player.id)) return;
          if (r.presses.has(player.id)) return;  // one press per round
          r.presses.set(player.id, {
            serverTs: services.now(),
            clientTs: Number.isFinite(msg.clientTs) ? msg.clientTs : null,
          });
        }
        // ROUND_ENDED / LOBBY / GAME_OVER: ignore.
        break;
      }
      case 'NEW_GAME': {
        if (state.phase !== 'GAME_OVER') return;
        const host = services.getHost();
        if (!host || host.id !== player.id) return;
        state.scores = new Map();
        for (const p of services.getPlayers()) state.scores.set(p.id, 0);
        state.phase = 'LOBBY';
        state.round = null;
        broadcastPhase(services);
        break;
      }
    }
  }

  return {
    name: 'image',
    onJoin,
    onLeave,
    onMessage,
    /** Test-only window into the plugin's state. */
    _debugState: () => state,
  };
}

module.exports = {
  createImageGame,
  IMAGE_POOL,
  WIN_SCORE,
  REVEAL_MS,
  REVEAL_CLEAR_MS,
  IMAGE_SHOW_MS,
  MIN_DISTRACTORS,
  MAX_DISTRACTORS,
  SCORING_WINDOW_MS,
  ROUND_END_PAUSE_MS,
  POINTS_BY_RANK,
  MIN_PLAYERS_TO_START,
};
