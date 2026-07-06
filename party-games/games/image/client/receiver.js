// Image-game receiver — TV UI module.
//
// Panels: LOBBY, REVEAL (target shown + reveal bar), PLAY (random image
// stream; target may appear at any seq and arms the scoring window),
// ROUND_ENDED, GAME_OVER.

import { renderScoreboard, renderFinalScoreboard } from '/shell-lib/scoreboard.js';

let ctx = null;
let rootEl = null;
let panels = null;
let revealImageEl = null;
let revealBarFillEl = null;
let distractorImageEl = null;
let distRoundNumEl = null;
let endedRoundNumEl = null;
let roundRanksEl = null;
let scoreboardEl = null;
let winnerNameEl = null;
let finalScoreEl = null;
let commitIndicatorEl = null;

const commits = new Map();
let lastScores = {};
const unsubs = [];
let currentPanelName = null;

export function mount(shellCtx) {
  ctx = shellCtx;
  rootEl = ctx.root;
  rootEl.classList.add('image-game');
  rootEl.innerHTML = `
    <div id="im-lobby" class="stage-panel" hidden>
      <h2>Players</h2>
      <ul id="im-player-list"><li class="empty">(no players yet)</li></ul>
      <p class="hint">Host: tap <strong>START</strong> on your phone once everyone has joined.</p>
    </div>
    <div id="im-reveal" class="stage-panel" hidden>
      <p class="phase-label">Memorise the target</p>
      <div id="im-reveal-image" class="image-display"></div>
      <div id="im-reveal-bar" class="reveal-bar"><div id="im-reveal-bar-fill"></div></div>
      <p class="hint">spot it when it comes back</p>
    </div>
    <div id="im-play" class="stage-panel" hidden>
      <p class="phase-label">Round <span id="im-dist-round-num"></span></p>
      <div id="im-distractor-image" class="image-display image-flash"></div>
    </div>
    <div id="im-ended" class="stage-panel" hidden>
      <h2>Round <span id="im-ended-round-num"></span> results</h2>
      <ol id="im-round-ranks"></ol>
      <h3>Scoreboard</h3>
      <ul id="im-scoreboard"></ul>
    </div>
    <div id="im-gameover" class="stage-panel" hidden>
      <p class="phase-label">GAME OVER</p>
      <p class="winner">🏆 <span id="im-winner-name"></span> wins!</p>
      <ol id="im-final-scoreboard" class="final-scoreboard"></ol>
    </div>
    <ul id="im-commit-indicator" class="commit-indicator"></ul>
  `;

  panels = {
    LOBBY:       rootEl.querySelector('#im-lobby'),
    REVEAL:      rootEl.querySelector('#im-reveal'),
    PLAY:        rootEl.querySelector('#im-play'),
    ROUND_ENDED: rootEl.querySelector('#im-ended'),
    GAME_OVER:   rootEl.querySelector('#im-gameover'),
  };
  revealImageEl     = rootEl.querySelector('#im-reveal-image');
  revealBarFillEl   = rootEl.querySelector('#im-reveal-bar-fill');
  distractorImageEl = rootEl.querySelector('#im-distractor-image');
  distRoundNumEl    = rootEl.querySelector('#im-dist-round-num');
  endedRoundNumEl   = rootEl.querySelector('#im-ended-round-num');
  roundRanksEl      = rootEl.querySelector('#im-round-ranks');
  scoreboardEl      = rootEl.querySelector('#im-scoreboard');
  winnerNameEl      = rootEl.querySelector('#im-winner-name');
  finalScoreEl      = rootEl.querySelector('#im-final-scoreboard');
  commitIndicatorEl = rootEl.querySelector('#im-commit-indicator');

  showPanel('LOBBY');
  renderPlayerList();

  unsubs.push(ctx.on('STATE',         () => {
    if (currentPanelName === 'LOBBY') renderPlayerList();
  }));
  unsubs.push(ctx.on('PHASE',         (msg) => {
    showPanel(msg.phase);
    if (msg.phase === 'LOBBY') renderPlayerList();
  }));
  unsubs.push(ctx.on('ROUND_REVEAL',  (msg) => {
    revealImageEl.textContent = msg.targetId;
    revealImageEl.classList.remove('cleared');
    distRoundNumEl.textContent = msg.roundId;
    startRevealBar(msg.showMs);
    setTimeout(() => {
      if (revealImageEl) revealImageEl.classList.add('cleared');
    }, msg.showMs);
    commits.clear();
    renderCommits();
  }));
  unsubs.push(ctx.on('PRESS_RECORDED', (msg) => {
    commits.set(msg.playerId, { name: msg.name, kind: 'pressed' });
    renderCommits();
  }));
  unsubs.push(ctx.on('SHOW_IMAGE',    (msg) => {
    // Cycle image; don't highlight the target — recognising it from REVEAL
    // is the whole game, flagging it on screen would be cheating.
    distractorImageEl.classList.remove('image-flash');
    void distractorImageEl.offsetWidth;  // force reflow so the animation restarts
    distractorImageEl.textContent = msg.imageId;
    distractorImageEl.classList.add('image-flash');
  }));
  unsubs.push(ctx.on('EARLY_PRESS',   (msg) => {
    ctx.log(`early press · ${msg.name} locked out`);
    commits.set(msg.playerId, { name: msg.name, kind: 'lockedOut' });
    renderCommits();
  }));
  unsubs.push(ctx.on('LAST_STANDING', (msg) => {
    ctx.log(`${msg.name} wins by default — everyone else locked out`);
  }));
  unsubs.push(ctx.on('ROUND_ENDED',   (msg) => {
    endedRoundNumEl.textContent = msg.roundId;
    renderRanks(msg.ranks);
    renderScoreboard(scoreboardEl, msg.scores, ctx.players(), lastScores);
    lastScores = { ...(msg.scores || {}) };
    showPanel('ROUND_ENDED');
  }));
  unsubs.push(ctx.on('GAME_OVER',     (msg) => {
    winnerNameEl.textContent = msg.name;
    renderFinalScoreboard(finalScoreEl, msg.scores, msg.winnerId, ctx.players());
    showPanel('GAME_OVER');
  }));
  unsubs.push(ctx.on('PONG',          (msg) => {
    ctx.log(`PONG from ${msg.name}`);
  }));
}

export function unmount() {
  for (const un of unsubs) { try { un(); } catch {} }
  unsubs.length = 0;
  if (rootEl) {
    rootEl.classList.remove('image-game');
    rootEl.innerHTML = '';
  }
  ctx = null;
  rootEl = panels = null;
  revealImageEl = revealBarFillEl = distractorImageEl = distRoundNumEl = null;
  endedRoundNumEl = roundRanksEl = scoreboardEl = null;
  winnerNameEl = finalScoreEl = commitIndicatorEl = null;
  commits.clear();
  lastScores = {};
  currentPanelName = null;
}

// ───── helpers ─────────────────────────────────────────────────────────────

function showPanel(name) {
  const target = panels[name];
  if (!target) return;
  currentPanelName = name;
  for (const el of Object.values(panels)) {
    el.hidden = el !== target;
  }
}

function renderPlayerList() {
  const listEl = rootEl?.querySelector('#im-player-list');
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

function startRevealBar(showMs) {
  if (!revealBarFillEl) return;
  revealBarFillEl.style.transition = 'none';
  revealBarFillEl.style.transform = 'scaleX(1)';
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (!revealBarFillEl) return;
    revealBarFillEl.style.transition = `transform ${showMs}ms linear`;
    revealBarFillEl.style.transform = 'scaleX(0)';
  }));
}
