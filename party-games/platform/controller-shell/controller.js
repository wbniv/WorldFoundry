// Controller — Phase 2a. Reaction-game aware:
//   - Cast Sender SDK to launch the receiver onto a TV (same as Phase 1c)
//   - Host-only "Start Game" button when in LOBBY / GAME_OVER
//   - PING button becomes the reaction-game BIG BUTTON during ROUND_COUNTDOWN /
//     ROUND_OPEN, forwarded to the server as BUTTON_PRESS with clientTs.

// Party Games Platform (dev) = 071CDEDD (Cast Console). CC1AD845 = Default
// Media Receiver (every Chromecast supports it). Append ?castAppId=<id> to
// the URL to override — used during device-registration diagnostic.
const CAST_APPLICATION_ID =
  new URLSearchParams(location.search).get('castAppId') || '071CDEDD';

// ───── URL + state ─────────────────────────────────────────────────────────

const params = new URLSearchParams(location.search);
const name = (params.get('name') || `Player ${Math.floor(Math.random() * 900 + 100)}`).slice(0, 32);

const statusEl      = document.getElementById('status');
const nameEl        = document.getElementById('name');
const btn           = document.getElementById('ping');
const castStateEl   = document.getElementById('cast-state');

nameEl.textContent = `Hi, ${name}.`;

let myId = null;
let hostId = null;
let phase = 'LOBBY';        // mirror of game phase, updated on PHASE broadcasts
let lockedOutThisRound = false;

function refreshButton() {
  // Button label + behaviour depend on game phase.
  btn.classList.remove('flash');
  switch (phase) {
    case 'LOBBY':
    case 'GAME_OVER':
      if (myId != null && myId === hostId) {
        btn.textContent = phase === 'GAME_OVER' ? 'NEW GAME' : 'START';
        btn.disabled = false;
        btn.dataset.action = phase === 'GAME_OVER' ? 'new-game' : 'start-game';
      } else {
        btn.textContent = myId === hostId ? 'START' : 'WAIT';
        btn.disabled = true;
        btn.dataset.action = 'idle';
      }
      break;
    case 'ROUND_COUNTDOWN':    // reaction game: countdown bar running
    case 'REVEAL':             // image game: memorise the target
    case 'DISTRACTORS':        // image game: distractor frames streaming
      btn.textContent = 'WAIT';
      btn.disabled = lockedOutThisRound;   // stays tappable before lockout — so an early press CAN happen
      btn.dataset.action = 'press';        // any press here is an early press on the server side
      break;
    case 'ROUND_OPEN':         // reaction game: GO! window
      btn.textContent = lockedOutThisRound ? 'LOCKED' : 'GO!';
      btn.disabled = lockedOutThisRound;
      btn.dataset.action = 'press';
      break;
    case 'TARGET':             // image game: target visible, scoring window open
      btn.textContent = lockedOutThisRound ? 'LOCKED' : 'TAP!';
      btn.disabled = lockedOutThisRound;
      btn.dataset.action = 'press';
      break;
    case 'ROUND_ENDED':
      btn.textContent = '···';
      btn.disabled = true;
      btn.dataset.action = 'idle';
      break;
    default:
      btn.textContent = '···';
      btn.disabled = true;
      btn.dataset.action = 'idle';
  }
}

// ───── WebSocket ───────────────────────────────────────────────────────────

const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
const ws = new WebSocket(wsUrl);

ws.addEventListener('open', () => {
  ws.send(JSON.stringify({ type: 'HELLO', role: 'controller', name }));
});
ws.addEventListener('close', () => {
  statusEl.textContent = 'disconnected';
  btn.disabled = true;
  btn.dataset.action = 'idle';
});
ws.addEventListener('error', (e) => console.warn('[ws] error', e));

ws.addEventListener('message', (ev) => {
  let msg;
  try { msg = JSON.parse(ev.data); } catch { return; }

  switch (msg.type) {
    case 'WELCOME':
      myId = msg.id;
      hostId = msg.hostId;
      statusEl.textContent = `connected · id=${myId}`;
      refreshButton();
      break;
    case 'STATE':
      hostId = msg.hostId;
      refreshButton();
      break;
    case 'PHASE':
      if (phase !== msg.phase) {
        phase = msg.phase;
        // Reset lockout at the top of any fresh round. ROUND_COUNTDOWN (reaction)
        // and REVEAL (image) are both the "entering a new round" phase.
        if (phase === 'ROUND_COUNTDOWN' || phase === 'REVEAL') lockedOutThisRound = false;
        refreshButton();
      }
      break;
    case 'EARLY_PRESS':
      if (msg.playerId === myId) {
        lockedOutThisRound = true;
        refreshButton();
      }
      break;
    case 'ROUND_ENDED':
      lockedOutThisRound = false;
      break;
  }
});

// ───── button handler ──────────────────────────────────────────────────────

btn.addEventListener('click', () => {
  if (ws.readyState !== WebSocket.OPEN) return;
  const action = btn.dataset.action;
  if (action === 'press') {
    ws.send(JSON.stringify({ type: 'BUTTON_PRESS', clientTs: Date.now() }));
    btn.classList.add('flash');
    setTimeout(() => btn.classList.remove('flash'), 150);
  } else if (action === 'start-game') {
    ws.send(JSON.stringify({ type: 'START_GAME' }));
  } else if (action === 'new-game') {
    ws.send(JSON.stringify({ type: 'NEW_GAME' }));
  }
});

// ───── Cast Sender ──────────────────────────────────────────────────────────

window.__onGCastApiAvailable = (isAvailable) => {
  if (!isAvailable) { setCastState('cast: unavailable', 'unavail'); return; }
  // The SDK sometimes fires this callback before `cast.framework` or
  // `chrome.cast.AutoJoinPolicy` is populated; poll briefly for readiness.
  let attempts = 0;
  const waitReady = () => {
    const ready =
      typeof cast !== 'undefined' && cast.framework && cast.framework.CastContext
      && typeof chrome !== 'undefined' && chrome.cast && chrome.cast.AutoJoinPolicy;
    if (ready) { initCastContext(); return; }
    if (++attempts >= 40) {
      setCastState('cast: SDK never ready (40×100ms)', 'unavail');
      return;
    }
    setTimeout(waitReady, 100);
  };
  waitReady();
};

function initCastContext() {
  try {
    const AUTO_JOIN_POLICY = chrome.cast.AutoJoinPolicy.ORIGIN_SCOPED || 'origin_scoped';
    const ctx = cast.framework.CastContext.getInstance();
    ctx.setOptions({
      receiverApplicationId: CAST_APPLICATION_ID,
      autoJoinPolicy: AUTO_JOIN_POLICY,
      resumeSavedSession: true,
    });
    const applyCastState = (state) => {
      switch (state) {
        case cast.framework.CastState.NO_DEVICES_AVAILABLE:
          setCastState('cast: no devices found', 'idle'); break;
        case cast.framework.CastState.NOT_CONNECTED:
          setCastState('cast: ready — tap the button', 'idle'); break;
        case cast.framework.CastState.CONNECTING:
          setCastState('cast: connecting…', 'connecting'); break;
        case cast.framework.CastState.CONNECTED: {
          const session = ctx.getCurrentSession();
          const device = session?.getCastDevice()?.friendlyName || 'Chromecast';
          setCastState(`cast: on ${device}`, 'connected');
          break;
        }
        default:
          setCastState(`cast: ? (${state})`, 'idle');
      }
    };
    ctx.addEventListener(
      cast.framework.CastContextEventType.CAST_STATE_CHANGED,
      (ev) => applyCastState(ev.castState),
    );
    // Seed the UI from the current state — the SDK doesn't always emit an
    // initial CAST_STATE_CHANGED, so otherwise we'd sit on "initialising…".
    applyCastState(ctx.getCastState());
  } catch (e) {
    console.warn('[cast] init failed', e);
    const detail = (e && (e.message || e.toString())) || 'unknown';
    setCastState('cast: init failed — ' + detail.slice(0, 80), 'unavail');
  }
};

function setCastState(text, cls) {
  castStateEl.textContent = text;
  castStateEl.dataset.state = cls;
}
