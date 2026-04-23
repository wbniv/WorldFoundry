// Image Recognition Game — server-side state machine. Mini-game 2.
//
// Plugs into platform createServer({ game: createImageGame() }).
// Flow: REVEAL (memorise target) → PLAY (image stream; each player gets one
// press; press during target = ranked, press during distractor = lockout) →
// ROUND_ENDED → next / GAME_OVER.
// Same server-receive-timestamp adjudication as the reaction game.

const WIN_SCORE              = 10;
const REVEAL_MS              = 3000;    // target shown at start to memorise
const REVEAL_CLEAR_MS        =  500;    // blank between reveal and image stream
const IMAGE_SHOW_MS          =  800;    // duration each image is on screen
const PRESS_GRACE_MS         =  250;    // press arriving up to this soon after the target ends still counts
const ROUND_END_PAUSE_MS     = 3000;    // pause between rounds
const MAX_ROUND_MS           = 60000;   // how long the image stream runs if players don't all commit
const POINTS_BY_RANK         = [4, 3, 2, 1];
const MIN_PLAYERS_TO_START   = 1;       // matches reaction; see platform README

// Pool of visually distinct flat icons (emoji v1; design doc calls for SVG in prod).
const IMAGE_POOL = [
  '🍎','⚡','🐸','🚀','🌙','☀️','🔥','💧','🎯','🎸',
  '🐙','🦒','🍕','🎁','🌈','🧊','🔮','🎪','🦖','🎨',
];

/**
 * Game lifecycle:
 *   LOBBY → REVEAL → PLAY → ROUND_ENDED → (next round | GAME_OVER)
 *
 * Messages OUT (broadcast unless noted):
 *   PHASE          { phase, scores }
 *   ROUND_REVEAL   { roundId, targetId, showMs, clearMs }
 *   SHOW_IMAGE     { roundId, seq, imageId, showMs, isTarget, serverTs }
 *   EARLY_PRESS    { roundId, playerId, name }    // pressed during REVEAL or on a non-target
 *   ROUND_ENDED    { roundId, ranks, scores, targetId, timedOut? }
 *   GAME_OVER      { winnerId, name, scores }
 *
 * Messages IN (controller):
 *   START_GAME                              (host only; from LOBBY / GAME_OVER)
 *   BUTTON_PRESS  { clientTs }              (REVEAL → lockout; PLAY → evaluated)
 *   NEW_GAME                                (host only; from GAME_OVER)
 */
function createImageGame(opts = {}) {
  const winScore   = opts.winScore ?? WIN_SCORE;
  const pool       = opts.pool ?? IMAGE_POOL;
  const maxRoundMs = opts.maxRoundMs ?? MAX_ROUND_MS;

  const state = {
    phase: 'LOBBY',
    roundId: 0,
    round: null,        // { id, target, seq, currentImage: {imageId,isTarget,serverTs},
                        //   presses: Map(pid → {serverTs, clientTs}), lockedOut: Set(pid) }
    scores: new Map(),
    winScore,
  };
  // Independent timer slots — image cycling, overall round cap, phase transitions
  // (REVEAL→PLAY and ROUND_ENDED→next) all run concurrently.
  let nextImageCancel = null;
  let roundCapCancel  = null;
  let phaseCancel     = null;

  function clearAllTimers() {
    if (nextImageCancel) { nextImageCancel(); nextImageCancel = null; }
    if (roundCapCancel)  { roundCapCancel();  roundCapCancel  = null; }
    if (phaseCancel)     { phaseCancel();     phaseCancel     = null; }
  }

  function broadcastPhase(services) {
    services.broadcast({
      type: 'PHASE',
      phase: state.phase,
      scores: Object.fromEntries(state.scores),
    });
  }

  function pickInt(services, min, max) {
    const span = max - min;
    return min + Math.min(Math.floor(services.random() * (span + 1)), span);
  }

  function pickTarget(services) {
    return pool[pickInt(services, 0, pool.length - 1)];
  }

  function startRound(services) {
    clearAllTimers();
    const target = pickTarget(services);
    state.phase = 'REVEAL';
    state.roundId += 1;
    state.round = {
      id: state.roundId,
      target,
      seq: -1,
      currentImage: null,
      prevImage: null,        // previous frame, kept briefly for press-grace adjudication
      presses: new Map(),
      lockedOut: new Set(),
    };
    broadcastPhase(services);
    services.broadcast({
      type: 'ROUND_REVEAL',
      roundId: state.roundId,
      targetId: target,
      showMs: REVEAL_MS,
      clearMs: REVEAL_CLEAR_MS,
    });
    phaseCancel = services.schedule(REVEAL_MS + REVEAL_CLEAR_MS, () => startPlay(services));
  }

  function startPlay(services) {
    if (state.phase !== 'REVEAL') return;
    phaseCancel = null;
    state.phase = 'PLAY';
    broadcastPhase(services);
    // Overall round cap — round ends when maxRoundMs has elapsed in PLAY, or
    // earlier if all players have committed (pressed or locked out).
    roundCapCancel = services.schedule(maxRoundMs, () => endRound(services, { timedOut: true }));
    showNext(services);
  }

  function showNext(services) {
    if (state.phase !== 'PLAY') return;
    const r = state.round;
    if (!r) return;
    nextImageCancel = null;

    r.seq += 1;
    // Uniform random pick from the full pool — target naturally appears with
    // probability 1/pool.length per frame (~5% with the default 20-image pool).
    const imageId = pool[pickInt(services, 0, pool.length - 1)];
    const isTarget = imageId === r.target;
    const serverTs = services.now();
    // Save the outgoing frame so a press arriving shortly after the transition
    // can still be adjudicated against it (see PRESS_GRACE_MS below).
    r.prevImage = r.currentImage;
    r.currentImage = { imageId, isTarget, serverTs };

    services.broadcast({
      type: 'SHOW_IMAGE',
      roundId: r.id,
      seq: r.seq,
      imageId,
      showMs: IMAGE_SHOW_MS,
      isTarget,
      serverTs,
    });

    nextImageCancel = services.schedule(IMAGE_SHOW_MS, () => showNext(services));
  }

  function checkAllCommitted(services) {
    const r = state.round;
    if (!r) return false;
    const players = services.getPlayers();
    if (players.length === 0) return false;
    return players.every((p) => r.presses.has(p.id) || r.lockedOut.has(p.id));
  }

  function endRound(services, { timedOut = false } = {}) {
    if (state.phase !== 'PLAY') return;
    clearAllTimers();

    const r = state.round;
    const orderedPresses = [...r.presses.entries()]
      .map(([pid, press]) => ({ playerId: pid, ...press }))
      .sort((a, b) => a.serverTs - b.serverTs);

    const allPlayers = services.getPlayers();
    const ranks = allPlayers.map((p) => {
      if (r.lockedOut.has(p.id)) {
        return { playerId: p.id, name: p.name, points: 0, lockedOut: true, ms: null };
      }
      const idx = orderedPresses.findIndex((x) => x.playerId === p.id);
      if (idx === -1) {
        return { playerId: p.id, name: p.name, points: 0, ms: null };
      }
      const points = POINTS_BY_RANK[idx] ?? 0;
      // Reaction time is measured from when that player's pressed image was
      // broadcast — i.e. the frame they actually reacted to. Falls back to
      // null if we lost the frame record.
      const ms = orderedPresses[idx].imageServerTs != null
        ? orderedPresses[idx].serverTs - orderedPresses[idx].imageServerTs
        : null;
      return { playerId: p.id, name: p.name, points, ms };
    });

    for (const rk of ranks) {
      if (!state.scores.has(rk.playerId)) state.scores.set(rk.playerId, 0);
      if (rk.points > 0) state.scores.set(rk.playerId, state.scores.get(rk.playerId) + rk.points);
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
      ...(timedOut ? { timedOut: true } : {}),
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
      state.round.lockedOut.delete(player.id);
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
        if (state.phase === 'REVEAL') {
          // Pressing before the stream starts → lockout for the round.
          if (r.lockedOut.has(player.id)) return;
          r.lockedOut.add(player.id);
          services.broadcast({
            type: 'EARLY_PRESS',
            roundId: r.id,
            playerId: player.id,
            name: player.name,
          });
        } else if (state.phase === 'PLAY') {
          if (r.lockedOut.has(player.id)) return;
          if (r.presses.has(player.id)) return;  // one commit per round
          const now = services.now();
          const img = r.currentImage;
          const prev = r.prevImage;
          // Grace window: a press reacting to the target can arrive up to
          // PRESS_GRACE_MS after the frame transitioned (cloudflare-tunnel
          // latency ~50–100 ms plus human tap jitter). If the current frame
          // is not target but the previous one was and we're still within the
          // grace window, credit the previous frame.
          let creditFrame = null;
          if (img && img.isTarget) {
            creditFrame = img;
          } else if (prev && prev.isTarget && img && (now - img.serverTs) < PRESS_GRACE_MS) {
            creditFrame = prev;
          }

          if (creditFrame) {
            r.presses.set(player.id, {
              serverTs: now,
              clientTs: Number.isFinite(msg.clientTs) ? msg.clientTs : null,
              imageServerTs: creditFrame.serverTs,
              imageSeq: r.seq,
            });
          } else {
            // Pressed on a distractor frame with no target in grace range → lockout.
            r.lockedOut.add(player.id);
            services.broadcast({
              type: 'EARLY_PRESS',
              roundId: r.id,
              playerId: player.id,
              name: player.name,
            });
          }
          if (checkAllCommitted(services)) {
            endRound(services, {});
          }
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
  PRESS_GRACE_MS,
  ROUND_END_PAUSE_MS,
  MAX_ROUND_MS,
  POINTS_BY_RANK,
  MIN_PLAYERS_TO_START,
};
