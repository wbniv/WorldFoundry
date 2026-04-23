// Reaction-game receiver — TV UI module.
//
// Mounted by the platform receiver shell inside <div id="game-root">.
// Panels: LOBBY, ROUND_COUNTDOWN, ROUND_OPEN, ROUND_ENDED, GAME_OVER.
// Also renders the live commit indicator (player chips showing who's
// pressed / locked out) across all active phases.

import { renderScoreboard, renderFinalScoreboard } from '/shell-lib/scoreboard.js';

let ctx = null;
let rootEl = null;
let panels = null;
let roundNumEl = null;
let endedRoundNumEl = null;
let roundRanksEl = null;
let scoreboardEl = null;
let winnerNameEl = null;
let finalScoreEl = null;
let commitIndicatorEl = null;
let countdownFillEl = null;

const commits = new Map();  // playerId → { name, kind: 'pressed' | 'lockedOut' }
let lastScores = {};
const unsubs = [];

export function mount(shellCtx) {
  ctx = shellCtx;
  rootEl = ctx.root;
  rootEl.classList.add('reaction-game');
  rootEl.innerHTML = `
    <div id="rx-lobby" class="stage-panel" hidden>
      <h2>Players</h2>
      <ul id="rx-player-list"><li class="empty">(no players yet)</li></ul>
      <p class="hint">Host: tap <strong>START</strong> on your phone once everyone has joined.</p>
    </div>
    <div id="rx-countdown" class="stage-panel" hidden>
      <p class="phase-label">ROUND <span id="rx-round-num"></span></p>
      <div id="rx-countdown-bar"><div id="rx-countdown-fill"></div></div>
      <p class="hint">Wait for <strong>GO</strong> · don't tap early!</p>
    </div>
    <div id="rx-open" class="stage-panel" hidden>
      <p id="rx-go" class="go-word">GO!</p>
    </div>
    <div id="rx-ended" class="stage-panel" hidden>
      <h2>Round <span id="rx-ended-round-num"></span> results</h2>
      <ol id="rx-round-ranks"></ol>
      <h3>Scoreboard</h3>
      <ul id="rx-scoreboard"></ul>
    </div>
    <div id="rx-gameover" class="stage-panel" hidden>
      <p class="phase-label">GAME OVER</p>
      <p class="winner">🏆 <span id="rx-winner-name"></span> wins!</p>
      <ol id="rx-final-scoreboard" class="final-scoreboard"></ol>
    </div>
    <ul id="rx-commit-indicator" class="commit-indicator"></ul>
  `;

  panels = {
    LOBBY:           rootEl.querySelector('#rx-lobby'),
    ROUND_COUNTDOWN: rootEl.querySelector('#rx-countdown'),
    ROUND_OPEN:      rootEl.querySelector('#rx-open'),
    ROUND_ENDED:     rootEl.querySelector('#rx-ended'),
    GAME_OVER:       rootEl.querySelector('#rx-gameover'),
  };
  roundNumEl        = rootEl.querySelector('#rx-round-num');
  endedRoundNumEl   = rootEl.querySelector('#rx-ended-round-num');
  roundRanksEl      = rootEl.querySelector('#rx-round-ranks');
  scoreboardEl      = rootEl.querySelector('#rx-scoreboard');
  winnerNameEl      = rootEl.querySelector('#rx-winner-name');
  finalScoreEl      = rootEl.querySelector('#rx-final-scoreboard');
  commitIndicatorEl = rootEl.querySelector('#rx-commit-indicator');
  countdownFillEl   = rootEl.querySelector('#rx-countdown-fill');

  showPanel('LOBBY');
  renderPlayerList();

  unsubs.push(ctx.on('STATE',            () => {
    if (isCurrentPanel('LOBBY')) renderPlayerList();
  }));
  unsubs.push(ctx.on('PHASE',            (msg) => {
    showPanel(msg.phase);
    if (msg.phase === 'LOBBY') renderPlayerList();
  }));
  unsubs.push(ctx.on('ROUND_COUNTDOWN',  (msg) => {
    roundNumEl.textContent = msg.roundId;
    startCountdownAnimation(msg.showMs);
    showPanel('ROUND_COUNTDOWN');
    commits.clear();
    renderCommits();
  }));
  unsubs.push(ctx.on('TIMER_FIRED',      () => {
    stopCountdownAnimation();
    showPanel('ROUND_OPEN');
  }));
  unsubs.push(ctx.on('PRESS_RECORDED',   (msg) => {
    commits.set(msg.playerId, { name: msg.name, kind: 'pressed' });
    renderCommits();
  }));
  unsubs.push(ctx.on('EARLY_PRESS',      (msg) => {
    ctx.log(`early press · ${msg.name} locked out`);
    commits.set(msg.playerId, { name: msg.name, kind: 'lockedOut' });
    renderCommits();
  }));
  unsubs.push(ctx.on('LAST_STANDING',    (msg) => {
    ctx.log(`${msg.name} wins by default — everyone else locked out`);
  }));
  unsubs.push(ctx.on('ROUND_ENDED',      (msg) => {
    endedRoundNumEl.textContent = msg.roundId;
    renderRanks(msg.ranks);
    renderScoreboard(scoreboardEl, msg.scores, ctx.players(), lastScores);
    lastScores = { ...(msg.scores || {}) };
    showPanel('ROUND_ENDED');
  }));
  unsubs.push(ctx.on('GAME_OVER',        (msg) => {
    winnerNameEl.textContent = msg.name;
    renderFinalScoreboard(finalScoreEl, msg.scores, msg.winnerId, ctx.players());
    showPanel('GAME_OVER');
  }));
  unsubs.push(ctx.on('PONG',             (msg) => {
    ctx.log(`PONG from ${msg.name}`);
  }));
}

export function unmount() {
  for (const un of unsubs) { try { un(); } catch {} }
  unsubs.length = 0;
  stopCountdownAnimation();
  if (rootEl) {
    rootEl.classList.remove('reaction-game');
    rootEl.innerHTML = '';
  }
  ctx = null;
  rootEl = panels = null;
  roundNumEl = endedRoundNumEl = roundRanksEl = scoreboardEl = null;
  winnerNameEl = finalScoreEl = commitIndicatorEl = countdownFillEl = null;
  commits.clear();
  lastScores = {};
}

// ───── helpers ─────────────────────────────────────────────────────────────

let currentPanelName = null;

function showPanel(name) {
  const target = panels[name];
  if (!target) return;
  currentPanelName = name;
  for (const el of Object.values(panels)) {
    el.hidden = el !== target;
  }
}

function isCurrentPanel(name) { return currentPanelName === name; }

function renderPlayerList() {
  const listEl = rootEl?.querySelector('#rx-player-list');
  if (!listEl) return;
  const players = ctx.players();
  listEl.innerHTML = '';
  if (!players.length) {
    const li = document.createElement('li');
    li.className = 'empty';
    li.textContent = '(no players yet)';
    listEl.appendChild(li);
    return;
  }
  const hostId = typeof ctx.hostId === 'function' ? ctx.hostId() : null;
  for (const p of players) {
    const li = document.createElement('li');
    li.textContent = `#${p.id} · ${p.name}${p.id === hostId ? '  (host)' : ''}`;
    listEl.appendChild(li);
  }
}

function renderRanks(ranks) {
  roundRanksEl.innerHTML = '';
  const sorted = [...ranks].sort((a, b) => {
    if (a.points !== b.points) return b.points - a.points;
    if (a.ms != null && b.ms != null) return a.ms - b.ms;
    if (a.ms != null) return -1;
    if (b.ms != null) return 1;
    return 0;
  });
  sorted.forEach((r, i) => {
    const li = document.createElement('li');
    li.style.setProperty('--i', i);
    if (r.points > 0)  li.classList.add('scored');
    if (r.lockedOut)   li.classList.add('locked-out');
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

function renderCommits() {
  if (!commitIndicatorEl) return;
  commitIndicatorEl.innerHTML = '';
  for (const [, { name, kind }] of commits) {
    const li = document.createElement('li');
    li.className = kind;
    li.textContent = `${name} ${kind === 'pressed' ? '✓' : '✗'}`;
    commitIndicatorEl.appendChild(li);
  }
}

// ───── countdown animation ─────────────────────────────────────────────────

function startCountdownAnimation(showMs) {
  if (!countdownFillEl) return;
  stopCountdownAnimation();
  countdownFillEl.style.transition = 'none';
  countdownFillEl.style.transform = 'scaleX(1)';
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (!countdownFillEl) return;
    countdownFillEl.style.transition = `transform ${showMs}ms linear`;
    countdownFillEl.style.transform = 'scaleX(0)';
  }));
}

function stopCountdownAnimation() {
  if (!countdownFillEl) return;
  countdownFillEl.style.transition = 'none';
  countdownFillEl.style.transform = 'scaleX(0)';
}
