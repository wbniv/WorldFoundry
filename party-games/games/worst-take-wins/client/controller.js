// Worst Take Wins — controller (phone) module.
//
// Phases rendered here:
//   LOBBY        host sees START; others see "waiting for host"
//   SHOW_PROMPT  non-judge: prompt + horizontal card strip + submit button
//                judge:     "you are judging" + prompt + submission counter
//   JUDGE_REVEAL non-judge: "waiting for judge"
//                judge:     one submission at a time, advance, final pick
//   SCORE        brief "X wins the round" + scores
//   GAME_OVER    final scoreboard; host sees NEW_GAME

let ctx = null;
let rootEl = null;

// Incremental state — driven by messages from the server.
let phase = 'LOBBY';
let myHand = [];             // [{ id, text }]
let currentPrompt = null;    // { id, text, blanks }
let currentJudgeId = null;
let currentRoundId = 0;
let submittedCount = 0;
let submittedTotal = 0;
let revealSubmissions = []; // [{ submissionId, cardIds, cards: [{id,text}] }]
let revealIndex = 0;
let iSubmitted = false;
let myScores = {};
let lastRoundWinner = null;  // { playerId, name, cardIds, cards, promptCard }
let gameOverPayload = null;

// Selection within the current hand during SHOW_PROMPT.
let selectedCardIds = [];

const unsubs = [];

export function mount(shellCtx) {
  ctx = shellCtx;
  rootEl = ctx.root;
  rootEl.classList.add('wtw');
  // Delegated click handler — rootEl lives across all renders, so one
  // listener handles every button no matter which phase is showing.
  rootEl.addEventListener('click', onClick);
  render();

  unsubs.push(ctx.on('STATE',             () => render()));
  unsubs.push(ctx.on('WELCOME',           () => render()));
  unsubs.push(ctx.on('PHASE',             onPhase));
  unsubs.push(ctx.on('DEAL_HAND',         (m) => { myHand = m.cards || []; render(); }));
  unsubs.push(ctx.on('SHOW_PROMPT',       onShowPrompt));
  unsubs.push(ctx.on('SUBMISSION_COUNT',  onSubmissionCount));
  unsubs.push(ctx.on('JUDGE_REVEAL_START', onJudgeRevealStart));
  unsubs.push(ctx.on('REVEAL_NEXT',       onRevealNext));
  unsubs.push(ctx.on('ROUND_WINNER',      onRoundWinner));
  unsubs.push(ctx.on('SCORE_UPDATE',      (m) => { myScores = m.scores || {}; render(); }));
  unsubs.push(ctx.on('GAME_WINNER',       onGameWinner));
  unsubs.push(ctx.on('ERROR',             onError));
}

export function unmount() {
  for (const un of unsubs) { try { un(); } catch {} }
  unsubs.length = 0;
  if (rootEl) {
    rootEl.removeEventListener('click', onClick);
    rootEl.classList.remove('wtw');
    rootEl.innerHTML = '';
  }
  ctx = rootEl = null;
  phase = 'LOBBY';
  myHand = [];
  currentPrompt = null;
  currentJudgeId = null;
  currentRoundId = 0;
  submittedCount = 0;
  submittedTotal = 0;
  revealSubmissions = [];
  revealIndex = 0;
  iSubmitted = false;
  myScores = {};
  lastRoundWinner = null;
  gameOverPayload = null;
  selectedCardIds = [];
}

// ───── message handlers ────────────────────────────────────────────────────

function onPhase(msg) {
  phase = msg.phase;
  currentJudgeId = msg.judgeId ?? null;
  currentRoundId = msg.round ?? currentRoundId;
  myScores = msg.scores ?? myScores;
  if (phase === 'SHOW_PROMPT') {
    selectedCardIds = [];
    iSubmitted = false;
  }
  if (phase === 'LOBBY') {
    currentPrompt = null;
    lastRoundWinner = null;
    gameOverPayload = null;
  }
  render();
}

function onShowPrompt(msg) {
  currentPrompt = msg.prompt;
  currentJudgeId = msg.judgeId;
  currentRoundId = msg.round;
  selectedCardIds = [];
  iSubmitted = false;
  render();
}

function onSubmissionCount(msg) {
  submittedCount = msg.submitted;
  submittedTotal = msg.total;
  render();
}

function onJudgeRevealStart(msg) {
  revealSubmissions = msg.submissions || [];
  revealIndex = 0;
  render();
}

function onRevealNext(msg) {
  revealIndex = msg.submissionIndex;
  render();
}

function onRoundWinner(msg) {
  lastRoundWinner = msg;
  render();
}

function onGameWinner(msg) {
  gameOverPayload = msg;
  render();
}

function onError(msg) {
  // Non-intrusive flash at the top of the UI.
  const bar = document.createElement('div');
  bar.className = 'wtw-flash';
  bar.textContent = msg.message || msg.code || 'error';
  rootEl.prepend(bar);
  setTimeout(() => bar.remove(), 3000);
}

// ───── rendering ───────────────────────────────────────────────────────────

function render() {
  if (!rootEl) return;
  const myId = ctx.playerId;
  const isJudge = myId != null && myId === currentJudgeId;
  const isHost = ctx.isHost();

  let html = '';

  html += renderScoreboardBar();

  if (phase === 'LOBBY' || myId == null) {
    html += renderLobby(isHost);
  } else if (phase === 'SHOW_PROMPT') {
    html += isJudge ? renderJudgeWaiting() : renderSubmitHand();
  } else if (phase === 'JUDGE_REVEAL') {
    html += isJudge ? renderJudgeReveal() : renderNonJudgeReveal();
  } else if (phase === 'SCORE') {
    html += renderScoreSplash();
  } else if (phase === 'GAME_OVER') {
    html += renderGameOver(isHost);
  }

  rootEl.innerHTML = html;
}

function renderScoreboardBar() {
  const players = ctx.players();
  if (!players.length) return '';
  const rows = players.map((p) => {
    const pts = myScores[p.id] || 0;
    const judgeTag = p.id === currentJudgeId ? ' ⚖︎' : '';
    const mine = p.id === ctx.playerId;
    return `<li class="${mine ? 'me' : ''}"><span>${escapeHtml(p.name)}${judgeTag}</span><span class="pts">${pts}</span></li>`;
  }).join('');
  return `<ul class="wtw-scores">${rows}</ul>`;
}

function renderLobby(isHost) {
  const n = ctx.players().length;
  if (isHost) {
    const can = n >= 3;
    return `
      <div class="wtw-lobby">
        <h2>Worst Take Wins</h2>
        <p>${n} player${n === 1 ? '' : 's'} in. Need at least 3 to start.</p>
        <button class="wtw-start-btn" data-action="start" ${can ? '' : 'disabled'}>START</button>
      </div>
    `;
  }
  return `
    <div class="wtw-lobby">
      <h2>Worst Take Wins</h2>
      <p>waiting for the host to start…</p>
    </div>
  `;
}

function renderJudgeWaiting() {
  return `
    <div class="wtw-judging">
      <p class="wtw-role">You are judging this round</p>
      ${renderPromptCard(currentPrompt)}
      <p class="wtw-counter">${submittedCount} / ${submittedTotal} submitted</p>
    </div>
  `;
}

function renderSubmitHand() {
  const blanks = (currentPrompt && currentPrompt.blanks) || 1;
  const need = blanks;
  const chosen = selectedCardIds.length;
  const canSubmit = !iSubmitted && chosen === need;
  const cards = myHand.map((c) => {
    const idx = selectedCardIds.indexOf(c.id);
    const selClass = idx >= 0 ? 'selected' : '';
    const pickBadge = idx >= 0 && blanks > 1 ? `<span class="pick-order">${idx + 1}</span>` : '';
    return `
      <button class="wtw-card ${selClass}" data-action="toggle-card" data-card-id="${escapeHtml(c.id)}" ${iSubmitted ? 'disabled' : ''}>
        ${pickBadge}
        <span class="wtw-card-text">${escapeHtml(c.text)}</span>
      </button>
    `;
  }).join('');
  const subLabel = iSubmitted ? 'waiting for others…'
                : canSubmit   ? 'SUBMIT'
                : `pick ${need - chosen} more`;
  return `
    <div class="wtw-submit">
      ${renderPromptCard(currentPrompt)}
      <p class="wtw-counter">${submittedCount} / ${submittedTotal} submitted</p>
      <div class="wtw-hand" role="listbox" aria-label="your hand">${cards}</div>
      <button class="wtw-submit-btn" data-action="submit" ${canSubmit ? '' : 'disabled'}>${escapeHtml(subLabel)}</button>
    </div>
  `;
}

function renderNonJudgeReveal() {
  const remaining = Math.max(0, (revealSubmissions.length - 1) - revealIndex);
  return `
    <div class="wtw-reveal-wait">
      ${renderPromptCard(currentPrompt)}
      <p class="wtw-role">Judge is reading submissions…</p>
      <p class="wtw-counter">${remaining} remaining</p>
    </div>
  `;
}

function renderJudgeReveal() {
  if (!revealSubmissions.length) return '<p>no submissions</p>';
  const isLast = revealIndex >= revealSubmissions.length - 1;
  if (!isLast) {
    const cur = revealSubmissions[revealIndex];
    return `
      <div class="wtw-reveal-one">
        ${renderPromptCard(currentPrompt)}
        ${renderSubmissionCards(cur, false)}
        <div class="wtw-reveal-row">
          <p class="wtw-counter">${revealSubmissions.length - 1 - revealIndex} more</p>
          <button class="wtw-advance-btn" data-action="advance">Next →</button>
        </div>
      </div>
    `;
  }
  // Final screen: list all submissions, tap to pick.
  const tiles = revealSubmissions.map((s) => `
    <button class="wtw-pick-btn" data-action="pick" data-submission-id="${escapeHtml(s.submissionId)}">
      ${renderSubmissionCards(s, true)}
    </button>
  `).join('');
  return `
    <div class="wtw-reveal-pick">
      ${renderPromptCard(currentPrompt)}
      <p class="wtw-role">Tap the winner</p>
      <div class="wtw-pick-grid">${tiles}</div>
    </div>
  `;
}

function renderPromptCard(p) {
  if (!p) return '';
  return `<div class="wtw-prompt"><p>${escapeHtml(p.text)}</p></div>`;
}

function renderSubmissionCards(sub, asTile) {
  if (!sub || !sub.cards) return '';
  const cls = asTile ? 'wtw-submission tile' : 'wtw-submission';
  const inner = sub.cards.map((c) => `<p>${escapeHtml(c.text)}</p>`).join('');
  return `<div class="${cls}">${inner}</div>`;
}

function renderScoreSplash() {
  if (!lastRoundWinner) return `<p class="wtw-role">calculating…</p>`;
  const w = lastRoundWinner;
  const myId = ctx.playerId;
  const mine = w.playerId === myId;
  const niceSub = (w.cards || []).map((c) => `<p>${escapeHtml(c.text)}</p>`).join('');
  return `
    <div class="wtw-score-splash ${mine ? 'mine' : ''}">
      <p class="wtw-headline">${escapeHtml(w.name)} wins the round!</p>
      ${renderPromptCard(w.promptCard)}
      <div class="wtw-submission">${niceSub}</div>
    </div>
  `;
}

function renderGameOver(isHost) {
  if (!gameOverPayload) return `<p class="wtw-role">game over</p>`;
  const w = gameOverPayload;
  const mine = w.playerId === ctx.playerId;
  const rows = Object.entries(w.scores || {})
    .map(([id, pts]) => {
      const p = ctx.players().find((pl) => pl.id === Number(id));
      return { id: Number(id), name: p ? p.name : `#${id}`, pts };
    })
    .sort((a, b) => b.pts - a.pts);
  const board = rows.map((r) => `
    <li class="${r.id === w.playerId ? 'winner' : ''} ${r.id === ctx.playerId ? 'me' : ''}">
      <span>${escapeHtml(r.name)}${r.id === ctx.playerId ? ' (you)' : ''}</span>
      <span>${r.pts} pt${r.pts === 1 ? '' : 's'}</span>
    </li>`).join('');
  return `
    <div class="wtw-game-over ${mine ? 'mine' : ''}">
      <p class="wtw-headline">${mine ? 'YOU WIN' : `${escapeHtml(w.name)} wins`}</p>
      <ol class="wtw-final-scoreboard">${board}</ol>
      ${isHost ? `<button class="wtw-start-btn" data-action="new-game">NEW GAME</button>` : ''}
    </div>
  `;
}

// ───── interactions ────────────────────────────────────────────────────────

function onClick(ev) {
  const btn = ev.target.closest('[data-action]');
  if (!btn || btn.disabled) return;
  const action = btn.dataset.action;

  if (action === 'start') {
    ctx.send({ type: 'START_GAME' });
  } else if (action === 'new-game') {
    ctx.send({ type: 'NEW_GAME' });
  } else if (action === 'toggle-card') {
    const id = btn.dataset.cardId;
    const blanks = (currentPrompt && currentPrompt.blanks) || 1;
    const idx = selectedCardIds.indexOf(id);
    if (idx >= 0) {
      selectedCardIds.splice(idx, 1);
    } else if (selectedCardIds.length < blanks) {
      selectedCardIds.push(id);
    } else if (blanks === 1) {
      // For pick-1 prompts, tapping a different card replaces selection.
      selectedCardIds = [id];
    }
    render();
  } else if (action === 'submit') {
    if (iSubmitted || selectedCardIds.length === 0) return;
    ctx.send({ type: 'SUBMIT_CARDS', cardIds: selectedCardIds.slice() });
    iSubmitted = true;
    ctx.feedback.press();
    render();
  } else if (action === 'advance') {
    ctx.send({ type: 'JUDGE_ADVANCE' });
  } else if (action === 'pick') {
    const sid = btn.dataset.submissionId;
    if (sid) {
      ctx.send({ type: 'JUDGE_PICK', submissionId: sid });
      ctx.feedback.press();
    }
  }
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[ch]);
}
