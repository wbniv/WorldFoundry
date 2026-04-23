// Image-game controller — phone UI module.
//
// Mirrors the reaction controller's big-button shape but maps the
// image-game phases: REVEAL (memorise target) / PLAY (stream, press on
// target). Any press during REVEAL is an early press → lockout.

let ctx = null;
let rootEl = null;
let buttonEl = null;
let helpEl = null;
let outcomeEl = null;
let outcomeHeadlineEl = null;
let outcomeSublineEl = null;
let outcomeScoreEl = null;
let confettiEl = null;

let phase = 'LOBBY';
let lockedOutThisRound = false;
let pressedThisRound = false;
let flashTimer = null;

const unsubs = [];

export function mount(shellCtx) {
  ctx = shellCtx;
  rootEl = ctx.root;
  rootEl.classList.add('image-game');
  rootEl.innerHTML = `
    <button id="im-btn" type="button" class="big-button" disabled>···</button>
    <p class="im-help">Tap the cast button to launch the receiver on your TV.</p>
    <div id="im-outcome" class="outcome" hidden>
      <div class="outcome-content">
        <p id="im-outcome-headline" class="outcome-headline"></p>
        <p id="im-outcome-subline" class="outcome-subline"></p>
        <ol id="im-outcome-scoreboard" class="outcome-scoreboard"></ol>
      </div>
      <div id="im-confetti" class="confetti" hidden aria-hidden="true"></div>
    </div>
  `;

  buttonEl = rootEl.querySelector('#im-btn');
  helpEl   = rootEl.querySelector('.im-help');
  outcomeEl         = rootEl.querySelector('#im-outcome');
  outcomeHeadlineEl = rootEl.querySelector('#im-outcome-headline');
  outcomeSublineEl  = rootEl.querySelector('#im-outcome-subline');
  outcomeScoreEl    = rootEl.querySelector('#im-outcome-scoreboard');
  confettiEl        = rootEl.querySelector('#im-confetti');

  buttonEl.addEventListener('click', onButtonClick);

  unsubs.push(ctx.on('PHASE',        onPhase));
  unsubs.push(ctx.on('EARLY_PRESS',  onEarlyPress));
  unsubs.push(ctx.on('ROUND_ENDED',  onRoundEnded));
  unsubs.push(ctx.on('GAME_OVER',    onGameOver));
  unsubs.push(ctx.on('STATE',        () => refreshButton()));
  unsubs.push(ctx.on('WELCOME',      () => refreshButton()));

  refreshButton();
}

export function unmount() {
  for (const un of unsubs) { try { un(); } catch {} }
  unsubs.length = 0;
  if (flashTimer) { clearTimeout(flashTimer); flashTimer = null; }
  if (buttonEl) buttonEl.removeEventListener('click', onButtonClick);
  if (rootEl) {
    rootEl.classList.remove('image-game');
    rootEl.innerHTML = '';
  }
  ctx = null;
  rootEl = buttonEl = helpEl = null;
  outcomeEl = outcomeHeadlineEl = outcomeSublineEl = outcomeScoreEl = confettiEl = null;
  phase = 'LOBBY';
  lockedOutThisRound = false;
  pressedThisRound = false;
}

// ───── handlers ────────────────────────────────────────────────────────────

function onPhase(msg) {
  if (phase === msg.phase) return;
  const wasGameOver = phase === 'GAME_OVER';
  phase = msg.phase;
  if (phase === 'REVEAL') {
    lockedOutThisRound = false;
    pressedThisRound = false;
    ctx.feedback.roundStart();
  }
  if (wasGameOver && phase !== 'GAME_OVER') hideOutcome();
  refreshButton();
}

function onEarlyPress(msg) {
  if (msg.playerId === ctx.playerId) {
    lockedOutThisRound = true;
    ctx.feedback.lockout();
    refreshButton();
  }
}

function onRoundEnded() {
  lockedOutThisRound = false;
}

function onGameOver(msg) {
  showOutcome(msg);
}

function onButtonClick() {
  const action = buttonEl.dataset.action;
  if (action === 'press') {
    ctx.send({ type: 'BUTTON_PRESS', clientTs: Date.now() });
    pressedThisRound = true;
    refreshButton();
    ctx.feedback.press();
    buttonEl.classList.add('flash');
    if (flashTimer) clearTimeout(flashTimer);
    flashTimer = setTimeout(() => buttonEl.classList.remove('flash'), 150);
  } else if (action === 'start-game') {
    ctx.send({ type: 'START_GAME' });
  } else if (action === 'new-game') {
    ctx.send({ type: 'NEW_GAME' });
  }
}

// ───── button skinning ─────────────────────────────────────────────────────

function refreshButton() {
  if (!buttonEl) return;
  buttonEl.classList.remove('flash');
  const host = ctx.isHost();
  switch (phase) {
    case 'LOBBY':
    case 'GAME_OVER':
      if (host) {
        buttonEl.textContent = phase === 'GAME_OVER' ? 'NEW GAME' : 'START';
        buttonEl.disabled = false;
        buttonEl.dataset.action = phase === 'GAME_OVER' ? 'new-game' : 'start-game';
      } else {
        buttonEl.textContent = 'WAIT';
        buttonEl.disabled = true;
        buttonEl.dataset.action = 'idle';
      }
      break;
    case 'REVEAL':
      buttonEl.textContent = 'WAIT';
      buttonEl.disabled = lockedOutThisRound;
      buttonEl.dataset.action = 'press';
      break;
    case 'PLAY':
      buttonEl.textContent = lockedOutThisRound ? 'LOCKED'
                           : pressedThisRound    ? '✓'
                           : 'TAP!';
      buttonEl.disabled = lockedOutThisRound || pressedThisRound;
      buttonEl.dataset.action = 'press';
      break;
    case 'ROUND_ENDED':
      buttonEl.textContent = '···';
      buttonEl.disabled = true;
      buttonEl.dataset.action = 'idle';
      break;
    default:
      buttonEl.textContent = '···';
      buttonEl.disabled = true;
      buttonEl.dataset.action = 'idle';
  }
}

// ───── end-of-game overlay ─────────────────────────────────────────────────

function showOutcome(gameOver) {
  if (!outcomeEl) return;
  const myId = ctx.playerId;
  const isWinner = gameOver.winnerId === myId;
  outcomeEl.classList.toggle('win',  isWinner);
  outcomeEl.classList.toggle('lose', !isWinner);

  if (isWinner) {
    outcomeHeadlineEl.textContent = 'YOU WIN';
    outcomeSublineEl.textContent = 'You spotted them all. Nicely done.';
    spawnConfetti();
    confettiEl.hidden = false;
    ctx.feedback.win();
  } else {
    outcomeHeadlineEl.textContent = 'Game over';
    const winnerName = gameOver.name || 'someone';
    outcomeSublineEl.textContent = `${winnerName} won this round.`;
    confettiEl.hidden = true;
    confettiEl.innerHTML = '';
    ctx.feedback.lose();
  }

  const nameMap = new Map(ctx.players().map((p) => [p.id, p.name]));
  outcomeScoreEl.innerHTML = '';
  const rows = Object.entries(gameOver.scores || {})
    .map(([id, pts]) => ({ id: Number(id), pts, name: nameMap.get(Number(id)) || `Player ${id}` }))
    .sort((a, b) => b.pts - a.pts);
  for (const r of rows) {
    const li = document.createElement('li');
    if (r.id === gameOver.winnerId) li.classList.add('winner');
    if (r.id === myId)              li.classList.add('me');
    const nameSpan = document.createElement('span');
    nameSpan.textContent = r.name + (r.id === myId ? ' (you)' : '');
    const ptsSpan = document.createElement('span');
    ptsSpan.textContent = `${r.pts} pt${r.pts === 1 ? '' : 's'}`;
    li.appendChild(nameSpan);
    li.appendChild(ptsSpan);
    outcomeScoreEl.appendChild(li);
  }

  outcomeEl.hidden = false;
}

function hideOutcome() {
  if (!outcomeEl) return;
  outcomeEl.hidden = true;
  if (confettiEl) {
    confettiEl.hidden = true;
    confettiEl.innerHTML = '';
  }
}

function spawnConfetti() {
  if (!confettiEl) return;
  const pieces = ['🎉', '🎊', '⭐', '✨', '🏆', '🥇'];
  confettiEl.innerHTML = '';
  const N = 28;
  for (let i = 0; i < N; i++) {
    const s = document.createElement('span');
    s.textContent = pieces[Math.floor(Math.random() * pieces.length)];
    s.style.left = `${Math.random() * 100}%`;
    s.style.animationDuration = `${2.5 + Math.random() * 2.5}s`;
    s.style.animationDelay = `${Math.random() * 1.2}s`;
    confettiEl.appendChild(s);
  }
}
