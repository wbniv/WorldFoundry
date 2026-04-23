// Worst Take Wins — receiver (TV) module.
//
// Phases rendered:
//   LOBBY         room code (shell) + player list + "waiting for host"
//   SHOW_PROMPT   big prompt card + submission count + judge banner
//   JUDGE_REVEAL  current submission full-bleed
//   SCORE         winner callout + completed strip + running scoreboard
//   GAME_OVER     final scoreboard (winner decorated)

import { renderFinalScoreboard } from '/shell-lib/scoreboard.js';

let ctx = null;
let rootEl = null;

let phase = 'LOBBY';
let currentPrompt = null;
let currentJudgeId = null;
let currentRoundId = 0;
let submittedCount = 0;
let submittedTotal = 0;
let revealSubmissions = [];
let revealIndex = 0;
let lastRoundWinner = null;
let scores = {};
let gameOverPayload = null;

const unsubs = [];

export function mount(shellCtx) {
  ctx = shellCtx;
  rootEl = ctx.root;
  rootEl.classList.add('wtw');
  render();

  unsubs.push(ctx.on('STATE',             () => { if (phase === 'LOBBY') render(); }));
  unsubs.push(ctx.on('PHASE',             (m) => {
    phase = m.phase;
    currentJudgeId = m.judgeId ?? null;
    currentRoundId = m.round ?? currentRoundId;
    scores = m.scores ?? scores;
    if (phase === 'LOBBY') {
      currentPrompt = null;
      revealSubmissions = [];
      lastRoundWinner = null;
      gameOverPayload = null;
    }
    render();
  }));
  unsubs.push(ctx.on('SHOW_PROMPT',       (m) => {
    currentPrompt = m.prompt;
    currentJudgeId = m.judgeId;
    currentRoundId = m.round;
    render();
  }));
  unsubs.push(ctx.on('SUBMISSION_COUNT',  (m) => {
    submittedCount = m.submitted;
    submittedTotal = m.total;
    render();
  }));
  unsubs.push(ctx.on('JUDGE_REVEAL_START', (m) => {
    revealSubmissions = m.submissions || [];
    revealIndex = 0;
    if (m.prompt) currentPrompt = m.prompt;
    render();
  }));
  unsubs.push(ctx.on('REVEAL_NEXT',       (m) => { revealIndex = m.submissionIndex; render(); }));
  unsubs.push(ctx.on('ROUND_WINNER',      (m) => {
    lastRoundWinner = m;
    ctx.log(`${m.name} wins the round`);
    render();
  }));
  unsubs.push(ctx.on('SCORE_UPDATE',      (m) => { scores = m.scores || {}; render(); }));
  unsubs.push(ctx.on('GAME_WINNER',       (m) => {
    gameOverPayload = m;
    ctx.log(`🏆 ${m.name} wins the game`);
    render();
  }));
}

export function unmount() {
  for (const un of unsubs) { try { un(); } catch {} }
  unsubs.length = 0;
  if (rootEl) {
    rootEl.classList.remove('wtw');
    rootEl.innerHTML = '';
  }
  ctx = rootEl = null;
  phase = 'LOBBY';
  currentPrompt = null;
  currentJudgeId = null;
  currentRoundId = 0;
  submittedCount = 0;
  submittedTotal = 0;
  revealSubmissions = [];
  revealIndex = 0;
  lastRoundWinner = null;
  scores = {};
  gameOverPayload = null;
}

// ───── rendering ───────────────────────────────────────────────────────────

function render() {
  if (!rootEl) return;

  let html = '';
  if (phase === 'LOBBY') html += renderLobby();
  else if (phase === 'SHOW_PROMPT') html += renderShowPrompt();
  else if (phase === 'JUDGE_REVEAL') html += renderReveal();
  else if (phase === 'SCORE') html += renderScore();
  else if (phase === 'GAME_OVER') html += renderGameOver();

  html += renderScoreStrip();

  rootEl.innerHTML = html;

  if (phase === 'GAME_OVER' && gameOverPayload) {
    const el = rootEl.querySelector('#wtw-final-scoreboard');
    if (el) renderFinalScoreboard(el, gameOverPayload.scores, gameOverPayload.playerId, ctx.players());
  }
}

function renderLobby() {
  const players = ctx.players();
  const hostId = typeof ctx.hostId === 'function' ? ctx.hostId() : null;
  const items = players.length
    ? players.map((p) => `<li>#${p.id} · ${escapeHtml(p.name)}${p.id === hostId ? ' (host)' : ''}</li>`).join('')
    : `<li class="empty">(no players yet)</li>`;
  return `
    <div class="wtw-lobby">
      <h2>Worst Take Wins</h2>
      <ul class="wtw-player-list">${items}</ul>
      <p class="wtw-hint">Host: tap <strong>START</strong> on your phone once everyone has joined. 3+ players required.</p>
    </div>
  `;
}

function renderShowPrompt() {
  const judgeName = nameOf(currentJudgeId);
  return `
    <div class="wtw-show-prompt">
      <p class="wtw-phase-label">Round ${currentRoundId} · Judge: ${escapeHtml(judgeName || '—')}</p>
      ${renderPromptCard(currentPrompt, true)}
      <p class="wtw-counter-big">${submittedCount} / ${submittedTotal} submitted</p>
    </div>
  `;
}

function renderReveal() {
  const cur = revealSubmissions[revealIndex];
  const remaining = Math.max(0, revealSubmissions.length - 1 - revealIndex);
  return `
    <div class="wtw-reveal">
      ${renderPromptCard(currentPrompt, false)}
      ${cur ? renderSubmissionBig(cur) : ''}
      <p class="wtw-counter-big">${remaining} more remaining</p>
    </div>
  `;
}

function renderScore() {
  if (!lastRoundWinner) return `<div class="wtw-score"><p class="wtw-phase-label">calculating…</p></div>`;
  const w = lastRoundWinner;
  return `
    <div class="wtw-score">
      <p class="wtw-winner-headline">★ ${escapeHtml(w.name)} wins this round!</p>
      ${renderCompletedStrip(w)}
    </div>
  `;
}

function renderGameOver() {
  if (!gameOverPayload) return '';
  return `
    <div class="wtw-game-over">
      <p class="wtw-phase-label">GAME OVER</p>
      <p class="wtw-winner-headline">🏆 ${escapeHtml(gameOverPayload.name || '?')} wins!</p>
      <ol id="wtw-final-scoreboard" class="final-scoreboard"></ol>
    </div>
  `;
}

function renderScoreStrip() {
  const players = ctx.players();
  if (!players.length) return '';
  const rows = players
    .map((p) => ({ id: p.id, name: p.name, pts: scores[p.id] || 0 }))
    .sort((a, b) => b.pts - a.pts);
  const max = Math.max(1, ...rows.map((r) => r.pts));
  const html = rows.map((r) => {
    const pct = Math.round((r.pts / max) * 100);
    const judge = r.id === currentJudgeId ? ' ⚖︎' : '';
    return `
      <li>
        <span class="wtw-row-name">${escapeHtml(r.name)}${judge}</span>
        <div class="wtw-bar"><div class="wtw-bar-fill" style="width: ${pct}%"></div></div>
        <span class="wtw-row-pts">${r.pts}</span>
      </li>`;
  }).join('');
  return `<ul class="wtw-score-strip">${html}</ul>`;
}

function renderPromptCard(p, big) {
  if (!p) return '';
  return `<div class="wtw-prompt ${big ? 'big' : ''}"><p>${escapeHtml(p.text)}</p></div>`;
}

function renderSubmissionBig(sub) {
  if (!sub || !sub.cards) return '';
  const inner = sub.cards.map((c) => `<p>${escapeHtml(c.text)}</p>`).join('');
  return `<div class="wtw-submission-big">${inner}</div>`;
}

function renderCompletedStrip(w) {
  const prompt = w.promptCard || currentPrompt;
  const inner = (w.cards || []).map((c) => `<p>${escapeHtml(c.text)}</p>`).join('');
  return `
    <div class="wtw-completed">
      ${renderPromptCard(prompt, false)}
      <div class="wtw-submission-big">${inner}</div>
    </div>
  `;
}

function nameOf(id) {
  if (id == null) return null;
  const p = ctx.players().find((x) => x.id === id);
  return p ? p.name : null;
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[ch]);
}
