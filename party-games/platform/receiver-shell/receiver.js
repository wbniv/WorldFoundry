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
  // image-recognition (mini-game 2). TARGET reuses the distractors panel so
  // the image stream keeps cycling visually through the scoring window.
  REVEAL:          document.getElementById('reveal'),
  DISTRACTORS:     document.getElementById('distractors'),
  TARGET:          document.getElementById('distractors'),
};
const countdownFillEl = document.getElementById('countdown-fill');
const roundNumEl      = document.getElementById('round-num');
const endedRoundNumEl = document.getElementById('ended-round-num');
const roundRanksEl    = document.getElementById('round-ranks');
const scoreboardEl    = document.getElementById('scoreboard');
const winnerNameEl    = document.getElementById('winner-name');
const finalScoreEl    = document.getElementById('final-scoreboard');
const revealImageEl     = document.getElementById('reveal-image');
const distractorImageEl = document.getElementById('distractor-image');
const distRoundNumEl    = document.getElementById('dist-round-num');

// Default panel
showPanel('LOBBY');

// ───── CAF boot ────────────────────────────────────────────────────────────

let isCastContext = false;
let castSessionDetail = '';
if (typeof cast !== 'undefined' && cast.framework) {
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
      setTimeout(() => { revealImageEl.classList.add('cleared'); }, msg.showMs);
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
      break;

    case 'ROUND_ENDED':
      endedRoundNumEl.textContent = msg.roundId;
      renderRanks(msg.ranks);
      renderScoreboard(msg.scores, scoreboardEl);
      showPanel('ROUND_ENDED');
      break;

    case 'GAME_OVER':
      winnerNameEl.textContent = msg.name;
      renderScoreboard(msg.scores, finalScoreEl);
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
  for (const r of sorted) {
    const li = document.createElement('li');
    const reaction = r.lockedOut ? 'locked out'
                   : r.ms != null ? `${r.ms} ms`
                   : 'no press';
    li.textContent = `${r.name} — ${r.points} pt${r.points === 1 ? '' : 's'} (${reaction})`;
    roundRanksEl.appendChild(li);
  }
}

function renderScoreboard(scores, el) {
  el.innerHTML = '';
  const rows = Object.entries(scores || {})
    .map(([id, pts]) => {
      const p = currentPlayers.find((pl) => String(pl.id) === String(id));
      return { name: p?.name ?? `#${id}`, pts };
    })
    .sort((a, b) => b.pts - a.pts);
  for (const row of rows) {
    const li = document.createElement('li');
    li.textContent = `${row.name}: ${row.pts}`;
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
