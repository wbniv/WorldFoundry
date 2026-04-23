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
const MAX_ROUND_MS           = 60000;   // defensive failsafe; a natural round is ~10–13 s
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
  const winScore   = opts.winScore ?? WIN_SCORE;
  const pool       = opts.pool ?? IMAGE_POOL;
  const maxRoundMs = opts.maxRoundMs ?? MAX_ROUND_MS;

  const state = {
    phase: 'LOBBY',
    roundId: 0,
    round: null,        // { id, target, preCount, seqIdx, targetShownAt, presses, earlyPressed }
    scores: new Map(),
    winScore,
  };
  // Multiple independent timer slots: the image stream keeps cycling even after
  // the target flashes by, so the next-image schedule and the scoring-window
  // schedule must not clobber each other. Failsafe is a hard overall cap.
  let nextImageCancel = null;
  let scoringCancel   = null;
  let phaseCancel     = null;  // REVEAL → DISTRACTORS transition + round-end pause
  let failsafeCancel  = null;  // MAX_ROUND_MS overall round cap

  function clearAllTimers() {
    if (nextImageCancel) { nextImageCancel(); nextImageCancel = null; }
    if (scoringCancel)   { scoringCancel();   scoringCancel   = null; }
    if (phaseCancel)     { phaseCancel();     phaseCancel     = null; }
    if (failsafeCancel)  { failsafeCancel();  failsafeCancel  = null; }
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

  function pickTarget(services) {
    return pool[pickInt(services, 0, pool.length - 1)];
  }

  function pickDistractor(services, excludeId) {
    const distractorPool = pool.filter((id) => id !== excludeId);
    return distractorPool[pickInt(services, 0, distractorPool.length - 1)];
  }

  function startRound(services) {
    clearAllTimers();
    const target = pickTarget(services);
    const preCount = pickInt(services, MIN_DISTRACTORS, MAX_DISTRACTORS);
    state.phase = 'REVEAL';
    state.roundId += 1;
    state.round = {
      id: state.roundId,
      target,
      preCount,              // distractors shown before the target flashes
      seqIdx: -1,            // incremented on each showNext; target fires at seqIdx===preCount
      targetShownAt: null,
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
    phaseCancel = services.schedule(REVEAL_MS + REVEAL_CLEAR_MS, () => startDistractors(services));
    // Overall round cap — never expected to fire; catches state-machine hangs.
    failsafeCancel = services.schedule(maxRoundMs, () => failsafeEndRound(services));
  }

  function failsafeEndRound(services) {
    if (!state.round) return;
    if (state.phase === 'LOBBY' || state.phase === 'GAME_OVER' || state.phase === 'ROUND_ENDED') return;
    clearAllTimers();
    const r = state.round;
    state.phase = 'ROUND_ENDED';
    const ranks = services.getPlayers().map((p) => ({
      playerId: p.id, name: p.name, points: 0,
      lockedOut: r.earlyPressed.has(p.id) || undefined,
      ms: null,
    }));
    broadcastPhase(services);
    services.broadcast({
      type: 'ROUND_ENDED',
      roundId: r.id,
      ranks,
      scores: Object.fromEntries(state.scores),
      targetId: r.target,
      timedOut: true,
    });
    phaseCancel = services.schedule(ROUND_END_PAUSE_MS, () => startRound(services));
  }

  function startDistractors(services) {
    if (state.phase !== 'REVEAL') return;
    if (phaseCancel) { phaseCancel = null; }
    state.phase = 'DISTRACTORS';
    broadcastPhase(services);
    showNext(services);
  }

  function showNext(services) {
    const r = state.round;
    if (!r) return;
    if (nextImageCancel) { nextImageCancel = null; }  // self-fired

    const idx = r.seqIdx + 1;
    r.seqIdx = idx;
    const isTarget = idx === r.preCount;
    const imageId = isTarget ? r.target : pickDistractor(services, r.target);
    const serverTs = services.now();

    if (isTarget) {
      // Target just appeared — transition into TARGET phase (opens scoring
      // window) and schedule endRound. Keep cycling images; the post-target
      // distractor stream provides pressure while players react.
      state.phase = 'TARGET';
      r.targetShownAt = serverTs;
      broadcastPhase(services);
      scoringCancel = services.schedule(SCORING_WINDOW_MS, () => endRound(services));
    }

    services.broadcast({
      type: 'SHOW_IMAGE',
      roundId: r.id,
      seq: idx,
      imageId,
      showMs: IMAGE_SHOW_MS,
      isTarget,
      serverTs,
    });

    // Always schedule the next image — stream continues until endRound clears
    // the timer when the scoring window expires.
    nextImageCancel = services.schedule(IMAGE_SHOW_MS, () => showNext(services));
  }

  function endRound(services) {
    if (state.phase !== 'TARGET') return;
    clearAllTimers();

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
      phaseCancel = services.schedule(ROUND_END_PAUSE_MS, () => startRound(services));
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
      clearAllTimers();
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
  MAX_ROUND_MS,
  POINTS_BY_RANK,
  MIN_PLAYERS_TO_START,
};
