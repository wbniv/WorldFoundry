// Reaction Game — server-side state machine. Mini-game 1 (countdown timer).
//
// Plugs into platform createServer({ game: createReactionGame() }).
// Owns all game state + timestamps; clients just forward button presses.

const WIN_SCORE         = 10;         // first to WIN_SCORE total points takes the game
const COUNTDOWN_SHOW_MS = 9000;       // receiver displays a 9 s countdown bar
const COUNTDOWN_MIN_MS  = 2000;       // the hidden real timer lands somewhere in [MIN, MAX]
const COUNTDOWN_MAX_MS  = 9000;       // inclusive
const SCORING_WINDOW_MS = 3000;       // after TIMER_FIRED, presses count for this long
const ROUND_END_PAUSE_MS = 3000;      // pause between rounds so players can read results
const POINTS_BY_RANK    = [4, 3, 2, 1]; // 1st → 4 pts, 2nd → 3, 3rd → 2, 4th → 1, rest → 0
const MIN_PLAYERS_TO_START = 1;       // allow solo dev loop; 2 is the intended floor, see README

/**
 * Game lifecycle:
 *   LOBBY → ROUND_COUNTDOWN → ROUND_OPEN → ROUND_ENDED → (next round | GAME_OVER)
 *
 * Messages OUT (broadcast unless noted):
 *   PHASE            { phase, scores }
 *   ROUND_COUNTDOWN  { roundId, showMs }                        // enter countdown
 *   TIMER_FIRED      { roundId, serverTs }                      // scoring window opens
 *   EARLY_PRESS      { roundId, playerId, name }                // lockout announcement
 *   ROUND_ENDED      { roundId, ranks, scores }                 // rankings + scoreboard
 *   GAME_OVER        { winnerId, name, scores }                 // terminal
 *
 * Messages IN (controller):
 *   START_GAME                                   (host only, from LOBBY / GAME_OVER)
 *   BUTTON_PRESS    { clientTs }                 (during ROUND_COUNTDOWN → lockout;
 *                                                 during ROUND_OPEN → ranked)
 *   NEW_GAME                                     (host only, from GAME_OVER; back to LOBBY)
 */
function createReactionGame(opts = {}) {
  const winScore = opts.winScore ?? WIN_SCORE;

  const state = {
    phase: 'LOBBY',
    roundId: 0,
    round: null,          // { id, realMs, startedAt, firedAt, presses: Map, earlyPressed: Set }
    scores: new Map(),    // playerId → points
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

  function pickRealCountdownMs(services) {
    // Math.random() returns [0, 1) so +1 on the span gives inclusive MAX for typical
    // callers; but tests inject random=1.0 directly, so clamp the spread to [0, span].
    const span = COUNTDOWN_MAX_MS - COUNTDOWN_MIN_MS;
    const step = Math.min(Math.floor(services.random() * (span + 1)), span);
    return COUNTDOWN_MIN_MS + step;
  }

  function startRound(services) {
    clearTimer();
    state.phase = 'ROUND_COUNTDOWN';
    state.roundId += 1;
    state.round = {
      id: state.roundId,
      realMs: pickRealCountdownMs(services),
      startedAt: services.now(),
      firedAt: null,
      presses: new Map(),
      earlyPressed: new Set(),
    };
    broadcastPhase(services);
    services.broadcast({
      type: 'ROUND_COUNTDOWN',
      roundId: state.roundId,
      showMs: COUNTDOWN_SHOW_MS,
    });
    cancelTimer = services.schedule(state.round.realMs, () => fireTimer(services));
  }

  function fireTimer(services) {
    if (state.phase !== 'ROUND_COUNTDOWN') return;
    clearTimer();
    state.phase = 'ROUND_OPEN';
    state.round.firedAt = services.now();
    broadcastPhase(services);
    services.broadcast({
      type: 'TIMER_FIRED',
      roundId: state.roundId,
      serverTs: state.round.firedAt,
    });
    cancelTimer = services.schedule(SCORING_WINDOW_MS, () => endRound(services));
  }

  function endRound(services) {
    if (state.phase !== 'ROUND_OPEN') return;
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
      const ms = orderedPresses[idx].serverTs - r.firedAt;
      return { playerId: p.id, name: p.name, points, ms };
    });

    // Update scoreboard.
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
    });

    // Winner?
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
  function onJoin(player, services) {
    if (!state.scores.has(player.id)) state.scores.set(player.id, 0);
    // Catch late joiners up on the current phase — without this, a player who
    // joins mid-round sees their controller sit on the default phase='LOBBY'
    // (button disabled, action='idle') until the next PHASE broadcast.
    services.sendTo(player.id, {
      type: 'PHASE',
      phase: state.phase,
      scores: Object.fromEntries(state.scores),
    });
  }

  function onLeave(player, services) {
    state.scores.delete(player.id);
    if (state.round) {
      state.round.presses.delete(player.id);
      state.round.earlyPressed.delete(player.id);
    }
    // If the departed was the last remaining player mid-round, fold back to LOBBY.
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
        if (state.phase === 'ROUND_COUNTDOWN') {
          if (r.earlyPressed.has(player.id)) return;  // already flagged
          r.earlyPressed.add(player.id);
          services.broadcast({
            type: 'EARLY_PRESS',
            roundId: r.id,
            playerId: player.id,
            name: player.name,
          });
        } else if (state.phase === 'ROUND_OPEN') {
          if (r.earlyPressed.has(player.id)) return;
          if (r.presses.has(player.id)) return;       // one press per round
          r.presses.set(player.id, {
            serverTs: services.now(),
            clientTs: Number.isFinite(msg.clientTs) ? msg.clientTs : null,
          });
          services.broadcast({
            type: 'PRESS_RECORDED',
            roundId: r.id,
            playerId: player.id,
            name: player.name,
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
    name: 'reaction',
    onJoin,
    onLeave,
    onMessage,
    /** Test-only window into the plugin's state. Do not rely on this in clients. */
    _debugState: () => state,
  };
}

module.exports = {
  createReactionGame,
  WIN_SCORE,
  COUNTDOWN_SHOW_MS,
  COUNTDOWN_MIN_MS,
  COUNTDOWN_MAX_MS,
  SCORING_WINDOW_MS,
  ROUND_END_PAUSE_MS,
  POINTS_BY_RANK,
  MIN_PLAYERS_TO_START,
};
