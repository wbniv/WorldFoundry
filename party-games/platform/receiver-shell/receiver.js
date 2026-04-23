// Receiver shell — Phase 2a. Reaction-game aware. Runs on both Chromecast and
// in a plain browser tab (the dev loop).

const statusEl       = document.getElementById('status');
const playerListEl   = document.getElementById('player-list');
const eventLogEl     = document.getElementById('event-log');

const panels = {
  // shared
  LOBBY:           document.getElementById('lobby'),
  ROUND_ENDED:     document.getElementById('ended'),
  GAME_OVER:       document.getElementById('gameover'),
  // reaction (mini-game 1)
  ROUND_COUNTDOWN: document.getElementById('countdown'),
  ROUND_OPEN:      document.getElementById('open'),
  // image-recognition (mini-game 2): REVEAL shows the memorisation target;
  // PLAY is the uniform-random image stream (#distractors holds its element
  // for historical id reasons — the target now appears randomly within it).
  REVEAL:          document.getElementById('reveal'),
  PLAY:            document.getElementById('distractors'),
};
const countdownFillEl = document.getElementById('countdown-fill');
const roundNumEl      = document.getElementById('round-num');
const endedRoundNumEl = document.getElementById('ended-round-num');
const roundRanksEl    = document.getElementById('round-ranks');
const scoreboardEl    = document.getElementById('scoreboard');
const winnerNameEl    = document.getElementById('winner-name');
const finalScoreEl    = document.getElementById('final-scoreboard');
const revealImageEl     = document.getElementById('reveal-image');
const revealBarFillEl   = document.getElementById('reveal-bar-fill');
const distractorImageEl = document.getElementById('distractor-image');
const distRoundNumEl    = document.getElementById('dist-round-num');
const commitIndicatorEl = document.getElementById('commit-indicator');
const commits = new Map();  // playerId → 'pressed' | 'lockedOut' for the current round
let lastScores = {};        // id → pts last seen, so renderScoreboard can highlight changed rows

// Default panel
showPanel('LOBBY');

// ───── CAF boot ────────────────────────────────────────────────────────────
// Only initialise CAF when we're actually running on a Cast device. In a
// plain browser, ctx.start() tries to connect to ws://localhost:8008/v2/ipc
// (Chromecast's internal IPC port) — it fails and retries forever, spamming
// the console. CrKey is the Chromecast user-agent marker; Android TV / Tizen
// / webOS cover other Cast-capable TV platforms we might end up on.
const looksLikeCastDevice = /CrKey|AndroidTV|Android TV|Tizen\/|web0s/i.test(navigator.userAgent);
let isCastContext = false;
let castSessionDetail = '';
if (looksLikeCastDevice && typeof cast !== 'undefined' && cast.framework) {
  try {
    const ctx = cast.framework.CastReceiverContext.getInstance();
    ctx.addEventListener(cast.framework.system.EventType.READY, () => {
      const info = ctx.getApplicationData();
      castSessionDetail = info?.name ? ` (${info.name})` : '';
      refreshStatus('cast + server connected' + castSessionDetail);
    });
    ctx.addEventListener(cast.framework.system.EventType.SENDER_CONNECTED, (ev) => {
      pushLog(`sender connected: ${ev.senderId}`);
    });
    ctx.addEventListener(cast.framework.system.EventType.SENDER_DISCONNECTED, (ev) => {
      pushLog(`sender disconnected: ${ev.senderId}`);
    });
    ctx.start();
    isCastContext = true;
  } catch (e) {
    console.warn('[cast] start failed', e);
  }
}

// ───── WebSocket ───────────────────────────────────────────────────────────

const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
const ws = new WebSocket(wsUrl);

ws.addEventListener('open', () => {
  ws.send(JSON.stringify({ type: 'HELLO', role: 'receiver' }));
  refreshStatus(isCastContext ? 'cast + server connected' + castSessionDetail : 'server connected (browser)');
});
ws.addEventListener('close', () => refreshStatus('disconnected'));
ws.addEventListener('error', (e) => console.warn('[ws] error', e));

ws.addEventListener('message', (ev) => {
  let msg;
  try { msg = JSON.parse(ev.data); } catch { return; }
  handle(msg);
});

function handle(msg) {
  switch (msg.type) {
    case 'STATE':
      logPlayerDiff(currentPlayers, msg.players || []);
      renderPlayers(msg.players, msg.hostId);
      break;

    case 'PHASE':
      showPanel(msg.phase);
      if (msg.phase === 'LOBBY') renderPlayers(currentPlayers, currentHostId);
      break;

    case 'ROUND_COUNTDOWN':
      roundNumEl.textContent = msg.roundId;
      startCountdownAnimation(msg.showMs);
      showPanel('ROUND_COUNTDOWN');
      // Clear last round's commit pills — the reaction game counterpart of
      // the ROUND_REVEAL reset used by the image game.
      commits.clear();
      renderCommits();
      break;

    case 'TIMER_FIRED':
      stopCountdownAnimation();
      showPanel('ROUND_OPEN');
      break;

    case 'ROUND_REVEAL':
      // Target reveal for memorisation: show for showMs, then clear for clearMs.
      // Phase is already REVEAL; this drives the image sub-animation.
      revealImageEl.textContent = msg.targetId;
      revealImageEl.classList.remove('cleared');
      distRoundNumEl.textContent = msg.roundId;
      startRevealBar(msg.showMs);
      setTimeout(() => { revealImageEl.classList.add('cleared'); }, msg.showMs);
      // Fresh round — clear last round's commit pills.
      commits.clear();
      renderCommits();
      break;

    case 'PRESS_RECORDED':
      commits.set(msg.playerId, { name: msg.name, kind: 'pressed' });
      renderCommits();
      break;

    case 'SHOW_IMAGE':
      // Always update the cycling image — stream keeps running through TARGET
      // phase (target + post-target distractors) until the scoring window
      // closes. Intentionally don't add a special highlight for isTarget: the
      // game is about recognising the target from the REVEAL memorisation,
      // and flagging it on screen would be cheating.
      distractorImageEl.classList.remove('image-flash');
      void distractorImageEl.offsetWidth;  // force reflow so the animation restarts
      distractorImageEl.textContent = msg.imageId;
      distractorImageEl.classList.add('image-flash');
      break;

    case 'EARLY_PRESS':
      pushLog(`early press · ${msg.name} locked out`);
      commits.set(msg.playerId, { name: msg.name, kind: 'lockedOut' });
      renderCommits();
      break;

    case 'ROUND_ENDED':
      endedRoundNumEl.textContent = msg.roundId;
      renderRanks(msg.ranks);
      renderScoreboard(msg.scores, scoreboardEl);
      showPanel('ROUND_ENDED');
      break;

    case 'GAME_OVER':
      winnerNameEl.textContent = msg.name;
      renderFinalScoreboard(msg.scores, msg.winnerId, finalScoreEl);
      showPanel('GAME_OVER');
      break;

    case 'PONG':
      pushLog(`PONG from ${msg.name}`);
      break;
  }
}

// ───── rendering helpers ───────────────────────────────────────────────────

let currentPlayers = [];
let currentHostId = null;

function showPanel(name) {
  // De-dup by element — TARGET aliases DISTRACTORS's panel so the image stream
  // can keep cycling through the scoring window. Without de-dup, the double
  // entry would overwrite the hidden state for that element and blank the
  // screen during DISTRACTORS.
  const target = panels[name];
  const seen = new Set();
  for (const el of Object.values(panels)) {
    if (seen.has(el)) continue;
    seen.add(el);
    el.hidden = el !== target;
  }
}

function renderPlayers(players, hostId) {
  currentPlayers = players || [];
  currentHostId  = hostId ?? null;
  playerListEl.innerHTML = '';
  if (!currentPlayers.length) {
    const li = document.createElement('li');
    li.className = 'empty';
    li.textContent = '(no players yet)';
    playerListEl.appendChild(li);
    return;
  }
  for (const p of currentPlayers) {
    const li = document.createElement('li');
    li.textContent = `#${p.id} · ${p.name}${p.id === currentHostId ? '  (host)' : ''}`;
    playerListEl.appendChild(li);
  }
}

function renderRanks(ranks) {
  roundRanksEl.innerHTML = '';
  // Sort for display: by points desc, then by reaction ms asc. 0-points with
  // lockedOut sink to the bottom.
  const sorted = [...ranks].sort((a, b) => {
    if (a.points !== b.points) return b.points - a.points;
    if (a.ms != null && b.ms != null) return a.ms - b.ms;
    if (a.ms != null) return -1;
    if (b.ms != null) return 1;
    return 0;
  });
  sorted.forEach((r, i) => {
    const li = document.createElement('li');
    // Stagger index drives CSS animation-delay so rows reveal 1-by-1.
    li.style.setProperty('--i', i);
    if (r.points > 0) li.classList.add('scored');
    if (r.lockedOut) li.classList.add('locked-out');

    const nameSpan = document.createElement('span');
    nameSpan.className = 'rank-name';
    nameSpan.textContent = r.name;

    const badge = document.createElement('span');
    badge.className = 'rank-badge';
    badge.textContent = r.points > 0 ? `+${r.points}` : '—';

    const reaction = document.createElement('span');
    reaction.className = 'rank-reaction';
    reaction.textContent = r.lockedOut ? 'locked out'
                        : r.ms != null ? `${r.ms} ms`
                        : 'no press';

    li.append(nameSpan, badge, reaction);
    roundRanksEl.appendChild(li);
  });
}

function logPlayerDiff(oldList, newList) {
  const oldById = new Map(oldList.map((p) => [p.id, p]));
  const newById = new Map(newList.map((p) => [p.id, p]));
  for (const [, p] of newById) if (!oldById.has(p.id)) pushLog(`${p.name} joined`);
  for (const [, p] of oldById) if (!newById.has(p.id)) pushLog(`${p.name} left`);
}

function renderCommits() {
  if (!commitIndicatorEl) return;
  commitIndicatorEl.innerHTML = '';
  // Preserve insertion order so players see the chronological commit sequence.
  for (const [, { name, kind }] of commits) {
    const li = document.createElement('li');
    li.className = kind;
    li.textContent = `${name} ${kind === 'pressed' ? '✓' : '✗'}`;
    commitIndicatorEl.appendChild(li);
  }
}

function renderScoreboard(scores, el) {
  el.innerHTML = '';
  const rows = Object.entries(scores || {})
    .map(([id, pts]) => {
      const p = currentPlayers.find((pl) => String(pl.id) === String(id));
      const prev = lastScores[id] ?? 0;
      return { id, name: p?.name ?? `#${id}`, pts, changed: pts !== prev, delta: pts - prev };
    })
    .sort((a, b) => b.pts - a.pts);
  for (const row of rows) {
    const li = document.createElement('li');
    if (row.changed) li.classList.add('changed');
    li.textContent = `${row.name}: ${row.pts}`;
    el.appendChild(li);
  }
  lastScores = { ...(scores || {}) };
}

function renderFinalScoreboard(scores, winnerId, el) {
  el.innerHTML = '';
  const rows = Object.entries(scores || {})
    .map(([id, pts]) => {
      const idNum = Number(id);
      const p = currentPlayers.find((pl) => String(pl.id) === String(id));
      return { id: idNum, name: p?.name ?? `#${id}`, pts };
    })
    .sort((a, b) => b.pts - a.pts);
  for (const row of rows) {
    const li = document.createElement('li');
    if (row.id === winnerId) li.classList.add('winner');
    const nameEl = document.createElement('span');
    nameEl.className = 'name';
    nameEl.textContent = row.name;
    const ptsEl = document.createElement('span');
    ptsEl.className = 'pts';
    ptsEl.textContent = `${row.pts} pt${row.pts === 1 ? '' : 's'}`;
    li.appendChild(nameEl);
    li.appendChild(ptsEl);
    el.appendChild(li);
  }
}

// ───── countdown animation ─────────────────────────────────────────────────
// CSS transform-driven; the real hidden timer is on the server, we just decay
// the bar visually over the max showMs window.

let countdownAnimHandle = null;

function startCountdownAnimation(showMs) {
  stopCountdownAnimation();
  countdownFillEl.style.transition = 'none';
  countdownFillEl.style.transform = 'scaleX(1)';
  // double-rAF to ensure the starting state is committed before the transition
  requestAnimationFrame(() => requestAnimationFrame(() => {
    countdownFillEl.style.transition = `transform ${showMs}ms linear`;
    countdownFillEl.style.transform = 'scaleX(0)';
  }));
}

function startRevealBar(showMs) {
  if (!revealBarFillEl) return;
  revealBarFillEl.style.transition = 'none';
  revealBarFillEl.style.transform = 'scaleX(1)';
  requestAnimationFrame(() => requestAnimationFrame(() => {
    revealBarFillEl.style.transition = `transform ${showMs}ms linear`;
    revealBarFillEl.style.transform = 'scaleX(0)';
  }));
}

function stopCountdownAnimation() {
  if (countdownAnimHandle != null) {
    cancelAnimationFrame(countdownAnimHandle);
    countdownAnimHandle = null;
  }
  countdownFillEl.style.transition = 'none';
  countdownFillEl.style.transform = 'scaleX(0)';
}

// ───── misc ────────────────────────────────────────────────────────────────

function refreshStatus(text) { statusEl.textContent = text; }

function pushLog(text) {
  const li = document.createElement('li');
  const time = new Date().toLocaleTimeString();
  li.textContent = `[${time}] ${text}`;
  eventLogEl.prepend(li);
  while (eventLogEl.children.length > 20) eventLogEl.removeChild(eventLogEl.lastChild);
}
