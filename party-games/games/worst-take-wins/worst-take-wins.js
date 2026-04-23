// Worst Take Wins — server-side state machine. Mini-game 3 (card game).
//
// Fill-in-the-blank card game (Cards Against Humanity model): one player
// per round is the Judge, everyone else submits one or two Response cards
// to complete the Prompt. Judge picks the winner, who scores a point.
// First to `winScore` prompt cards wins.
//
// Plugs into platform createServer({ gameFactory }). Owns all state plus
// the Deck abstraction (drawPrompt / drawResponse / discards). The deck
// itself is built per-room from cached JSON content (loaded at module
// level) and a per-room shuffle using services.random().

const path = require('node:path');
const { loadDeckContent, createDeck } = require('./deckLoader');

const DEFAULT_WIN_SCORE        = 8;      // first to this many prompt cards wins
const DEFAULT_HAND_SIZE        = 7;      // response cards held privately per player
const DEFAULT_SUBMIT_TIMEOUT   = 90_000; // ms before we auto-submit on players who dawdle
const DEFAULT_MIN_PLAYERS      = 3;      // need judge + ≥2 submitters to keep the game meaningful
const SCORE_PAUSE_MS           = 4_000;  // display the winner briefly before dealing the next round

// Lazy module-level cache for the deck content. First access reads the
// assets/decks/ dir synchronously; every room after that reuses the same
// underlying Prompt/Response arrays (the per-room Deck shuffles its own
// copy so they don't trample each other's draw order).
let _cachedContent = null;
function getCachedContent() {
  if (_cachedContent) return _cachedContent;
  _cachedContent = loadDeckContent(path.join(__dirname, 'assets', 'decks'));
  return _cachedContent;
}

/**
 * Factory.
 *
 * @param {object} opts
 * @param {number} [opts.winScore=8]
 * @param {number} [opts.handSize=7]
 * @param {number} [opts.submitTimeoutMs=90000]
 * @param {number} [opts.minPlayers=3]
 * @param {object} [opts.content]       { prompts, responses } — overrides
 *                                      the assets/decks/ read. Tests pass
 *                                      a minimal inline deck.
 * @param {boolean} [opts.allowPick2=false]  If true, two-blank prompts are
 *                                      drawn; if false, they're skipped at
 *                                      draw time. v1 client ships pick-1
 *                                      only, so defaults false.
 */
function createWorstTakeWinsGame(opts = {}) {
  const winScore        = opts.winScore        ?? DEFAULT_WIN_SCORE;
  const handSize        = opts.handSize        ?? DEFAULT_HAND_SIZE;
  const submitTimeoutMs = opts.submitTimeoutMs ?? DEFAULT_SUBMIT_TIMEOUT;
  const minPlayers      = opts.minPlayers      ?? DEFAULT_MIN_PLAYERS;
  const allowPick2      = opts.allowPick2      ?? false;
  // Don't touch the filesystem when tests pass inline content; otherwise
  // fall back to the cached default deck at START_GAME time.
  const content         = opts.content ?? null;

  const state = {
    phase: 'LOBBY',              // LOBBY | SHOW_PROMPT | JUDGE_REVEAL | SCORE | GAME_OVER
    roundId: 0,
    round: null,
    scores: new Map(),           // playerId → points
    hands: new Map(),            // playerId → Array<ResponseCard> (private)
    deck: null,                  // built at START_GAME
    judgeOrder: [],              // array of player ids, source-of-truth for rotation
    judgeIdx: 0,
    winScore, handSize, submitTimeoutMs, minPlayers, allowPick2,
  };
  let pauseCancel = null;        // between-round / win-announcement schedule handle
  let nextSubmissionId = 1;

  function clearPause() {
    if (pauseCancel) { pauseCancel(); pauseCancel = null; }
  }

  // ───── broadcasts ───────────────────────────────────────────────────────

  function broadcastPhase(services) {
    services.broadcast({
      type: 'PHASE',
      phase: state.phase,
      judgeId: state.round ? state.round.judgeId : null,
      scores: Object.fromEntries(state.scores),
      round: state.roundId,
    });
  }

  function broadcastScores(services) {
    services.broadcast({
      type: 'SCORE_UPDATE',
      scores: Object.fromEntries(state.scores),
    });
  }

  function sendHandTo(services, playerId) {
    const hand = state.hands.get(playerId) || [];
    services.sendTo(playerId, {
      type: 'DEAL_HAND',
      cards: hand.map((c) => ({ id: c.id, text: c.text })),
    });
  }

  // ───── deal / draw ──────────────────────────────────────────────────────

  function dealOrRefill(services) {
    // After a round the winner's submitted cards come out of their hand (if
    // they submitted; the judge didn't submit so no gap for them). Top every
    // hand back up to handSize. A fresh game starts with empty hands.
    for (const p of services.getPlayers()) {
      let hand = state.hands.get(p.id);
      if (!hand) {
        hand = [];
        state.hands.set(p.id, hand);
      }
      while (hand.length < state.handSize) {
        const c = state.deck.drawResponse();
        if (!c) break;  // deck ran dry even after reshuffle
        hand.push(c);
      }
      sendHandTo(services, p.id);
    }
  }

  function drawPrompt() {
    // Skip pick-2 prompts if the client can't handle them.
    while (true) {
      const p = state.deck.drawPrompt();
      if (!p) return null;
      if (!state.allowPick2 && (p.blanks || 1) > 1) {
        state.deck.discardPrompt(p);
        continue;
      }
      return p;
    }
  }

  // ───── round flow ───────────────────────────────────────────────────────

  function startRound(services) {
    clearPause();

    // Rotate judge; if anyone in judgeOrder has left, collapse them out.
    const presentIds = new Set(services.getPlayers().map((p) => p.id));
    state.judgeOrder = state.judgeOrder.filter((id) => presentIds.has(id));
    for (const p of services.getPlayers()) {
      if (!state.judgeOrder.includes(p.id)) state.judgeOrder.push(p.id);
    }
    if (state.judgeOrder.length < state.minPlayers) {
      // Lost too many players mid-game; fold back to LOBBY.
      state.phase = 'LOBBY';
      state.round = null;
      broadcastPhase(services);
      return;
    }
    if (state.judgeIdx >= state.judgeOrder.length) state.judgeIdx = 0;
    const judgeId = state.judgeOrder[state.judgeIdx];
    state.judgeIdx = (state.judgeIdx + 1) % state.judgeOrder.length;

    dealOrRefill(services);

    const prompt = drawPrompt();
    if (!prompt) {
      // Deck is drained; end the game on whoever's ahead.
      concedeByDeck(services);
      return;
    }

    state.roundId += 1;
    state.round = {
      id: state.roundId,
      prompt,
      judgeId,
      submissions: new Map(),
      revealIndex: 0,
      winnerSubmissionId: null,
      autoSubmitCancel: null,
    };
    state.phase = 'SHOW_PROMPT';
    broadcastPhase(services);
    services.broadcast({
      type: 'SHOW_PROMPT',
      round: state.roundId,
      judgeId,
      prompt: { id: prompt.id, text: prompt.text, blanks: prompt.blanks || 1 },
    });
    services.broadcast({
      type: 'SUBMISSION_COUNT',
      submitted: 0,
      total: expectedSubmitters(services).length,
    });

    // Auto-submit the slowpokes.
    state.round.autoSubmitCancel = services.schedule(state.submitTimeoutMs, () => {
      autoSubmitMissing(services);
    });
  }

  function expectedSubmitters(services) {
    return services.getPlayers().filter((p) => p.id !== state.round.judgeId);
  }

  function autoSubmitMissing(services) {
    const r = state.round;
    if (!r) return;
    if (state.phase !== 'SHOW_PROMPT') return;
    const submittedIds = new Set([...r.submissions.values()].map((s) => s.playerId));
    for (const p of expectedSubmitters(services)) {
      if (submittedIds.has(p.id)) continue;
      const hand = state.hands.get(p.id) || [];
      if (hand.length === 0) continue;
      const blanks = r.prompt.blanks || 1;
      const pickIndices = pickRandomIndices(services, hand.length, Math.min(blanks, hand.length));
      const cardIds = pickIndices.map((i) => hand[i].id);
      acceptSubmission(services, p, cardIds, /* auto */ true);
    }
  }

  function pickRandomIndices(services, n, k) {
    // Fisher-Yates partial: pick k distinct indices from [0..n).
    const arr = Array.from({ length: n }, (_, i) => i);
    for (let i = 0; i < k; i++) {
      const j = i + Math.floor(services.random() * (n - i));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr.slice(0, k);
  }

  function acceptSubmission(services, player, cardIds, auto = false) {
    const r = state.round;
    if (!r) return;
    if (state.phase !== 'SHOW_PROMPT') return;
    if (player.id === r.judgeId) return;
    // Already submitted? Ignore (double-tap guard).
    for (const s of r.submissions.values()) {
      if (s.playerId === player.id) return;
    }
    const blanks = r.prompt.blanks || 1;
    if (!Array.isArray(cardIds) || cardIds.length !== blanks) return;

    const hand = state.hands.get(player.id) || [];
    const handIds = new Set(hand.map((c) => c.id));
    // Every submitted card must actually be in this player's hand — no
    // claiming cards you don't own.
    for (const id of cardIds) {
      if (!handIds.has(id)) return;
    }
    // Pull the cards out of the hand.
    const removed = [];
    for (const id of cardIds) {
      const idx = hand.findIndex((c) => c.id === id);
      if (idx === -1) return;  // shouldn't happen given the check above, but belt-and-suspenders
      removed.push(hand.splice(idx, 1)[0]);
    }

    const submissionId = 's' + (nextSubmissionId++);
    r.submissions.set(submissionId, {
      submissionId,
      playerId: player.id,
      cardIds,
      auto,
    });

    // The cards move to the response discard pile so they can be reshuffled
    // back in if the deck drains.
    for (const c of removed) state.deck.discardResponse(c);

    services.broadcast({
      type: 'SUBMISSION_COUNT',
      submitted: r.submissions.size,
      total: expectedSubmitters(services).length,
    });

    if (r.submissions.size >= expectedSubmitters(services).length) {
      enterJudgeReveal(services);
    }
  }

  function enterJudgeReveal(services) {
    const r = state.round;
    if (!r) return;
    if (r.autoSubmitCancel) { r.autoSubmitCancel(); r.autoSubmitCancel = null; }
    // Shuffle submissions so judge can't trivially identify who submitted what.
    const list = [...r.submissions.values()];
    for (let i = list.length - 1; i > 0; i--) {
      const j = Math.floor(services.random() * (i + 1));
      [list[i], list[j]] = [list[j], list[i]];
    }
    r.revealOrder = list.map((s) => s.submissionId);
    r.revealIndex = 0;

    state.phase = 'JUDGE_REVEAL';
    broadcastPhase(services);
    // Resolve each cardId to its text from any hand's removed cards. Since
    // we already popped them and discarded, reconstruct from the response
    // discard (keyed by id). Keep a lookup by materialising here.
    const textById = state.deck.responseTextIndex();
    services.broadcast({
      type: 'JUDGE_REVEAL_START',
      submissions: list.map((s) => ({
        submissionId: s.submissionId,
        cardIds: s.cardIds,
        cards: s.cardIds.map((id) => ({ id, text: textById.get(id) || '' })),
        // CRITICAL: no playerId here. Anonymity until JUDGE_PICK.
      })),
      prompt: { id: r.prompt.id, text: r.prompt.text, blanks: r.prompt.blanks || 1 },
    });
  }

  function judgeAdvance(services, player) {
    const r = state.round;
    if (!r) return;
    if (state.phase !== 'JUDGE_REVEAL') return;
    if (player.id !== r.judgeId) return;
    if (r.revealIndex < r.revealOrder.length - 1) {
      r.revealIndex += 1;
      services.broadcast({ type: 'REVEAL_NEXT', submissionIndex: r.revealIndex });
    }
  }

  function judgePick(services, player, submissionId) {
    const r = state.round;
    if (!r) return;
    if (state.phase !== 'JUDGE_REVEAL') return;
    if (player.id !== r.judgeId) return;
    const sub = r.submissions.get(submissionId);
    if (!sub) return;

    r.winnerSubmissionId = submissionId;
    const winnerId = sub.playerId;
    const winnerName = nameOf(services, winnerId);

    if (!state.scores.has(winnerId)) state.scores.set(winnerId, 0);
    state.scores.set(winnerId, state.scores.get(winnerId) + 1);

    state.phase = 'SCORE';
    broadcastPhase(services);
    const textById = state.deck.responseTextIndex();
    services.broadcast({
      type: 'ROUND_WINNER',
      playerId: winnerId,
      name: winnerName,
      submissionId,
      cardIds: sub.cardIds,
      cards: sub.cardIds.map((id) => ({ id, text: textById.get(id) || '' })),
      promptCard: { id: r.prompt.id, text: r.prompt.text, blanks: r.prompt.blanks || 1 },
    });
    broadcastScores(services);

    // Discard the prompt regardless of winner. Prompt discard feeds the
    // reshuffle when the prompt pool drains.
    state.deck.discardPrompt(r.prompt);

    // Winner?
    if (state.scores.get(winnerId) >= state.winScore) {
      state.phase = 'GAME_OVER';
      broadcastPhase(services);
      services.broadcast({
        type: 'GAME_WINNER',
        playerId: winnerId,
        name: winnerName,
        scores: Object.fromEntries(state.scores),
      });
      state.round = null;
      return;
    }

    // Pause briefly for the winner callout, then next round.
    pauseCancel = services.schedule(SCORE_PAUSE_MS, () => startRound(services));
  }

  function concedeByDeck(services) {
    // Deck ran dry — resolve the game on whoever's ahead.
    let bestId = null, bestPts = -1;
    for (const [id, pts] of state.scores) {
      if (pts > bestPts) { bestPts = pts; bestId = id; }
    }
    state.phase = 'GAME_OVER';
    state.round = null;
    broadcastPhase(services);
    services.broadcast({
      type: 'GAME_WINNER',
      playerId: bestId,
      name: nameOf(services, bestId) || 'Nobody',
      scores: Object.fromEntries(state.scores),
      reason: 'deck-drained',
    });
  }

  function nameOf(services, playerId) {
    const p = services.getPlayers().find((x) => x.id === playerId);
    return p ? p.name : null;
  }

  // ───── hooks ─────────────────────────────────────────────────────────────

  function onJoin(player, services) {
    if (!state.scores.has(player.id)) state.scores.set(player.id, 0);
    if (!state.judgeOrder.includes(player.id)) state.judgeOrder.push(player.id);
    sendCatchUpTo(services, player.id, /* resume */ false);
  }

  function onReconnect(player, services) {
    // Scores, judgeOrder, and the player's existing hand are preserved across
    // the grace window — don't touch them. Just push PHASE (+ SHOW_PROMPT if
    // applicable + current DEAL_HAND so the controller re-renders the hand
    // strip rather than the "waiting to be dealt in" empty state).
    sendCatchUpTo(services, player.id, /* resume */ true);
  }

  function sendCatchUpTo(services, pid, resume) {
    services.sendTo(pid, {
      type: 'PHASE',
      phase: state.phase,
      judgeId: state.round ? state.round.judgeId : null,
      scores: Object.fromEntries(state.scores),
      round: state.roundId,
    });
    if (state.phase === 'SHOW_PROMPT' && state.round) {
      services.sendTo(pid, {
        type: 'SHOW_PROMPT',
        round: state.roundId,
        judgeId: state.round.judgeId,
        prompt: {
          id: state.round.prompt.id,
          text: state.round.prompt.text,
          blanks: state.round.prompt.blanks || 1,
        },
      });
    }
    // For fresh joiners: empty hand, they're waiting to be dealt in on the
    // next DEAL. For resumers: send their preserved hand so the controller
    // re-renders immediately. Falls back to empty if the hand got cleaned
    // up for some reason.
    const currentHand = (resume && state.hands.get(pid)) || [];
    services.sendTo(pid, { type: 'DEAL_HAND', cards: currentHand });
  }

  function onLeave(player, services) {
    state.scores.delete(player.id);
    state.judgeOrder = state.judgeOrder.filter((id) => id !== player.id);
    state.hands.delete(player.id);

    const r = state.round;
    if (!r) return;

    // Strip any submission from this player.
    for (const [sid, sub] of r.submissions) {
      if (sub.playerId === player.id) r.submissions.delete(sid);
    }

    // Fold to LOBBY if too few players remain.
    if (services.getPlayers().length < state.minPlayers) {
      clearPause();
      if (r.autoSubmitCancel) { r.autoSubmitCancel(); r.autoSubmitCancel = null; }
      state.phase = 'LOBBY';
      state.round = null;
      broadcastPhase(services);
      return;
    }

    // Judge left → abort this round, move on to next judge's round.
    if (r.judgeId === player.id) {
      clearPause();
      if (r.autoSubmitCancel) { r.autoSubmitCancel(); r.autoSubmitCancel = null; }
      // Schedule fresh round immediately (no pause).
      pauseCancel = services.schedule(0, () => startRound(services));
      return;
    }

    // If we were in SHOW_PROMPT and everyone remaining has submitted, advance.
    if (state.phase === 'SHOW_PROMPT' && r.submissions.size >= expectedSubmitters(services).length) {
      enterJudgeReveal(services);
      return;
    }
    // Announce updated counter.
    if (state.phase === 'SHOW_PROMPT') {
      services.broadcast({
        type: 'SUBMISSION_COUNT',
        submitted: r.submissions.size,
        total: expectedSubmitters(services).length,
      });
    }
  }

  function onMessage(player, msg, services) {
    switch (msg.type) {
      case 'START_GAME': {
        if (state.phase !== 'LOBBY' && state.phase !== 'GAME_OVER') return;
        const host = services.getHost();
        if (!host || host.id !== player.id) return;
        if (services.getPlayers().length < state.minPlayers) {
          services.sendTo(player.id, {
            type: 'ERROR',
            code: 'NOT_ENOUGH_PLAYERS',
            message: `need at least ${state.minPlayers} players`,
          });
          return;
        }
        // Build deck from content (cached or injected).
        const c = content ?? getCachedContent();
        state.deck = createDeck({ prompts: c.prompts, responses: c.responses, random: services.random });
        state.scores = new Map(services.getPlayers().map((p) => [p.id, 0]));
        state.hands = new Map();
        state.judgeOrder = services.getPlayers().map((p) => p.id);
        state.judgeIdx = 0;
        state.roundId = 0;
        startRound(services);
        break;
      }
      case 'SUBMIT_CARDS': {
        acceptSubmission(services, player, Array.isArray(msg.cardIds) ? msg.cardIds : []);
        break;
      }
      case 'JUDGE_ADVANCE': {
        judgeAdvance(services, player);
        break;
      }
      case 'JUDGE_PICK': {
        if (typeof msg.submissionId !== 'string') return;
        judgePick(services, player, msg.submissionId);
        break;
      }
      case 'NEW_GAME': {
        if (state.phase !== 'GAME_OVER') return;
        const host = services.getHost();
        if (!host || host.id !== player.id) return;
        clearPause();
        state.phase = 'LOBBY';
        state.round = null;
        state.scores = new Map();
        state.hands = new Map();
        state.judgeIdx = 0;
        broadcastPhase(services);
        break;
      }
    }
  }

  return {
    name: 'worst-take-wins',
    onJoin,
    onReconnect,
    onLeave,
    onMessage,
    _debugState: () => state,
  };
}

module.exports = {
  createWorstTakeWinsGame,
  DEFAULT_WIN_SCORE,
  DEFAULT_HAND_SIZE,
  DEFAULT_SUBMIT_TIMEOUT,
  DEFAULT_MIN_PLAYERS,
  SCORE_PAUSE_MS,
};
