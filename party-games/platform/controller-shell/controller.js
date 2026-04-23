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
      btn.textContent = 'WAIT';
      btn.disabled = lockedOutThisRound;   // stays tappable before lockout — so an early press CAN happen
      btn.dataset.action = 'press';        // any press here is an early press on the server side
      break;
    case 'ROUND_OPEN':         // reaction game: GO! window (post-TIMER_FIRED)
      btn.textContent = lockedOutThisRound ? 'LOCKED' : 'GO!';
      btn.disabled = lockedOutThisRound;
      btn.dataset.action = 'press';
      break;
    case 'PLAY':               // image game: stream running, press when you see target
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
// Mobile browsers (Android Chrome especially) aggressively suspend/drop
// WebSocket connections when the tab goes to background, screen locks, or
// network hiccups; Cloudflare quick tunnels also have their own idle quirks.
// An auto-reconnecting loop keeps Bob's controller usable without the user
// having to notice and manually reload.

const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
let ws = null;
let reconnectAttempt = 0;
let reconnectTimer = null;

function connect() {
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  statusEl.textContent = reconnectAttempt > 0 ? `reconnecting (attempt ${reconnectAttempt})…` : 'connecting…';
  ws = new WebSocket(wsUrl);

  ws.addEventListener('open', () => {
    reconnectAttempt = 0;
    // Re-identify; on reconnect the server will issue a new player id (scores
    // for any in-progress round are forfeit — acceptable trade for a usable
    // controller after a transient drop).
    ws.send(JSON.stringify({ type: 'HELLO', role: 'controller', name }));
  });

  ws.addEventListener('close', () => {
    statusEl.textContent = 'disconnected';
    btn.textContent = '↻';       // rotating-reconnect hint; refreshButton() will re-skin once WELCOME lands
    btn.disabled = true;
    btn.dataset.action = 'idle';
    // Exponential backoff capped at ~8 s so a recovered device reconnects fast.
    const delay = Math.min(8_000, 500 * (2 ** reconnectAttempt));
    reconnectAttempt++;
    reconnectTimer = setTimeout(connect, delay);
  });

  ws.addEventListener('error', (e) => console.warn('[ws] error', e));
  ws.addEventListener('message', handleMessage);
}

function handleMessage(ev) {
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
}

connect();

// When the tab comes back to foreground on mobile, kick a reconnect if the
// socket had been suspended. The `close` event usually fires first and
// schedules a reconnect anyway; this is belt-and-suspenders.
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && ws && ws.readyState === WebSocket.CLOSED) {
    reconnectAttempt = 0;
    connect();
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
