// Controller shell — platform-only (Phase 5 seam).
//
// Everything game-specific lives in a per-game module at
// games/<WF_GAME>/client/controller.js, loaded on demand via dynamic
// import from /game/client/controller.js. The shell's job:
//
//   - Open and auto-reconnect the WebSocket
//   - Handle HELLO / WELCOME / STATE / PONG / NEED_ROOM / BAD_ROOM
//   - Show the room-code entry gate if ?room= isn't in the URL
//   - Track player identity + host and expose them through ctx
//   - Boot Cast Sender so the user can launch the receiver on a TV
//   - Surface an AudioContext + reusable haptic/audio feedback helpers
//   - Pass every non-platform message through to the game via ctx.on
//
// The shell never touches the game's DOM inside <div id="game-root">;
// the game module owns that tree from mount() to unmount().

// Party Games Platform (dev) = 071CDEDD (Cast Console). CC1AD845 = Default
// Media Receiver (every Chromecast supports it). Append ?castAppId=<id> to
// the URL to override — used during device-registration diagnostic.
const CAST_APPLICATION_ID =
  new URLSearchParams(location.search).get('castAppId') || '071CDEDD';

const PLATFORM_RESERVED_TYPES = new Set([
  'WELCOME', 'WELCOME_RECEIVER', 'STATE', 'PONG', 'NEED_ROOM', 'BAD_ROOM',
]);

// ───── URL + state ─────────────────────────────────────────────────────────

const params = new URLSearchParams(location.search);
// Name: preferred from URL, else what the user typed into the entry gate.
// No silent `Player 123` fallback any more — if the user didn't pre-set a
// name, we pop the gate and ask for one.
let name = (params.get('name') || '').slice(0, 32);
// Room code: required to connect. If the URL has ?room=ABCD use it; otherwise
// show the entry-gate and wait for the user to enter one.
let roomCode = (params.get('room') || '').toUpperCase();

// Per-tab session id: survives reload (sessionStorage), dies with the tab.
// Server keeps the player's slot + scores alive for ~20 s after the WS drops;
// a reconnect HELLO carrying the same sessionId resumes that slot. Closing
// the tab and opening a fresh one gets a new id — intentional, a user who
// genuinely walked away shouldn't keep holding a scoreboard seat.
const SESSION_KEY = 'party-games-session';
let sessionId = null;
try {
  sessionId = sessionStorage.getItem(SESSION_KEY);
} catch { /* private-browsing / disabled storage — fall through */ }
if (!sessionId || !/^[A-Za-z0-9_-]{8,64}$/.test(sessionId)) {
  sessionId = generateSessionId();
  try { sessionStorage.setItem(SESSION_KEY, sessionId); } catch { /* ignore */ }
}
function generateSessionId() {
  const bytes = new Uint8Array(18);   // 24 chars of base64url
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

const gameNameMeta = document.querySelector('meta[name="game-name"]');
const gameName = (gameNameMeta && gameNameMeta.content) ? gameNameMeta.content : null;

const statusEl      = document.getElementById('status');
const nameEl        = document.getElementById('name');
const castStateEl   = document.getElementById('cast-state');
const gameRoot      = document.getElementById('game-root');

refreshNameEl();
function refreshNameEl() {
  nameEl.textContent = name ? `Hi, ${name}.` : '';
}

let myId = null;
let hostId = null;
let playersById = new Map();  // id → name, mirror of STATE broadcasts for ctx.players()

// Subscribers registered by the game via ctx.on(type, handler)
const gameSubscribers = new Map();  // type → Set<handler>

let gameModule = null;
let mounted = false;

// ───── game module loading ─────────────────────────────────────────────────
// Dynamic import keeps the shell decoupled from game-specific code. If the
// game has no client (server-only during development), mount() simply never
// runs; the shell is still useful as a WS + room-gate harness.

async function loadGameModule() {
  if (gameModule || !gameName) return;
  try {
    gameModule = await import(`/game/client/controller.js?g=${encodeURIComponent(gameName)}`);
  } catch (e) {
    console.warn(`[shell] failed to load /game/client/controller.js for '${gameName}':`, e.message);
    gameRoot.innerHTML =
      `<p class="shell-error">game UI missing for '<code>${escapeHtml(gameName)}</code>' — ` +
      `expected <code>games/${escapeHtml(gameName)}/client/controller.js</code></p>`;
  }
}

function mountGame() {
  if (!gameModule || mounted) return;
  if (typeof gameModule.mount !== 'function') {
    console.warn('[shell] game module has no mount() export');
    return;
  }
  try {
    gameModule.mount(buildCtx());
    mounted = true;
  } catch (e) {
    console.error('[shell] game mount() threw:', e);
  }
}

function unmountGame() {
  if (!mounted) return;
  mounted = false;
  gameSubscribers.clear();
  if (gameModule && typeof gameModule.unmount === 'function') {
    try { gameModule.unmount(); } catch (e) { console.error('[shell] game unmount() threw:', e); }
  }
  gameRoot.innerHTML = '';
}

function buildCtx() {
  return {
    root: gameRoot,
    send: (msg) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        console.warn('[shell] send ignored — ws not open (type=' + (msg && msg.type) + ')');
        return;
      }
      ws.send(JSON.stringify(msg));
    },
    on: (type, handler) => {
      if (!gameSubscribers.has(type)) gameSubscribers.set(type, new Set());
      gameSubscribers.get(type).add(handler);
      return () => {
        const set = gameSubscribers.get(type);
        if (set) set.delete(handler);
      };
    },
    get playerId() { return myId; },
    isHost: () => myId != null && myId === hostId,
    players: () => [...playersById.entries()].map(([id, nm]) => ({ id, name: nm })),
    feedback: {
      press:       feedbackPress,
      lockout:     feedbackLockout,
      win:         feedbackWin,
      lose:        feedbackLose,
      roundStart:  feedbackRoundStart,
    },
    assetUrl: (asset) => `/game/assets/${asset}`,
    log: () => {},   // receiver-side log; no-op on controller
    ensureAudio: ensureAudioCtx,
  };
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
  if (!roomCode) return;    // wait for room-gate submission
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  // Don't unmount up-front — if the server resumes our session (WELCOME
  // carries resumed:true + same id), the game module's in-memory state is
  // still the right state for the current round and its subscribers should
  // keep serving the new ws via the stable ctx.send closure.
  statusEl.textContent = reconnectAttempt > 0 ? `reconnecting (attempt ${reconnectAttempt})…` : 'connecting…';
  ws = new WebSocket(wsUrl);

  ws.addEventListener('open', () => {
    reconnectAttempt = 0;
    ws.send(JSON.stringify({
      type: 'HELLO',
      role: 'controller',
      name,
      room: roomCode,
      sessionId,
    }));
  });

  ws.addEventListener('close', () => {
    statusEl.textContent = 'disconnected';
    // Exponential backoff capped at ~8 s so a recovered device reconnects fast.
    const delay = Math.min(8_000, 500 * (2 ** reconnectAttempt));
    reconnectAttempt++;
    reconnectTimer = setTimeout(connect, delay);
  });

  ws.addEventListener('error', (e) => console.warn('[ws] error', e));
  ws.addEventListener('message', handleMessage);
}

async function handleMessage(ev) {
  let msg;
  try { msg = JSON.parse(ev.data); } catch { return; }
  if (!msg || typeof msg.type !== 'string') return;

  switch (msg.type) {
    case 'WELCOME':
      // Fresh session → unmount any stale game tree before remounting with
      // the new identity. Session resume → the game module is already
      // mounted and holding the right state for the round in progress; just
      // refresh myId/hostId and let the existing subscribers continue.
      if (!msg.resumed && mounted) unmountGame();
      myId = msg.id;
      hostId = msg.hostId;
      statusEl.textContent = msg.resumed
        ? `reconnected · id=${myId}`
        : `connected · id=${myId}`;
      if (!msg.resumed) {
        await loadGameModule();
        mountGame();
      }
      break;
    case 'STATE':
      hostId = msg.hostId;
      playersById = new Map((msg.players || []).map((p) => [p.id, p.name]));
      break;
    case 'NEED_ROOM':
    case 'BAD_ROOM':
      // The room-gate UI already handles re-prompting; surface the state.
      statusEl.textContent = msg.type === 'NEED_ROOM' ? 'needs a room code' : 'bad room code';
      break;
    case 'PONG':
      // Platform-level echo — games that want latency diagnostics can PING
      // via ctx.send; the response is also offered through gameSubscribers.
      break;
  }

  // Deliver every message (including platform ones) to any game subscribers
  // that explicitly asked for that type. STATE and WELCOME are commonly
  // useful for games that want to keep their own player list, so don't hide
  // them — games subscribe deliberately.
  const subs = gameSubscribers.get(msg.type);
  if (subs) {
    for (const handler of subs) {
      try { handler(msg); } catch (e) { console.error(`[shell] game handler for ${msg.type} threw:`, e); }
    }
  }
}

// ───── entry gate ─────────────────────────────────────────────────────────
// If the URL is missing ?name= and/or ?room=ABCD, we pop a modal that asks
// for whichever piece(s) are missing. connect() only fires once everything
// we need is populated.

const entryGateEl   = document.getElementById('entry-gate');
const entryFormEl   = document.getElementById('entry-form');
const entryHeadingEl = document.getElementById('entry-heading');
const entryHintEl   = document.getElementById('entry-hint');
const nameFieldEl   = document.getElementById('name-field');
const nameInputEl   = document.getElementById('name-input');
const roomFieldEl   = document.getElementById('room-field');
const roomInputEl   = document.getElementById('room-input');

function needsName() { return !name; }
function needsRoom() { return !roomCode; }

if (needsName() || needsRoom()) {
  nameFieldEl.hidden = !needsName();
  roomFieldEl.hidden = !needsRoom();
  // Heading + hint tune themselves to whatever's actually being asked.
  if (needsName() && needsRoom()) {
    entryHeadingEl.textContent = 'Join the game';
    entryHintEl.textContent = 'Pick a name and enter the 4-letter room code shown on the TV.';
  } else if (needsName()) {
    entryHeadingEl.textContent = 'Pick a name';
    entryHintEl.textContent = 'What should other players call you?';
  } else {
    entryHeadingEl.textContent = 'Enter room code';
    entryHintEl.textContent = 'Look at the TV. The receiver shows a 4-letter room code.';
  }
  entryGateEl.hidden = false;
  statusEl.textContent = 'waiting for entry';
  // Focus the first un-filled field.
  (needsName() ? nameInputEl : roomInputEl).focus();

  entryFormEl.addEventListener('submit', (ev) => {
    ev.preventDefault();
    if (needsName()) {
      const enteredName = nameInputEl.value.trim().slice(0, 32);
      if (!enteredName) {
        nameInputEl.setCustomValidity('name required');
        nameInputEl.reportValidity();
        return;
      }
      nameInputEl.setCustomValidity('');
      name = enteredName;
      params.set('name', name);
      refreshNameEl();
    }
    if (needsRoom()) {
      const enteredRoom = roomInputEl.value.trim().toUpperCase();
      if (!/^[ABCDEFGHJKLMNPRSTUVWXYZ]{4}$/.test(enteredRoom)) {
        roomInputEl.setCustomValidity('4 letters, no I/O/Q');
        roomInputEl.reportValidity();
        return;
      }
      roomInputEl.setCustomValidity('');
      roomCode = enteredRoom;
      params.set('room', roomCode);
    }
    // Reflect both pieces in the URL so a refresh keeps them.
    const newUrl = location.pathname + '?' + params.toString() + location.hash;
    history.replaceState(null, '', newUrl);
    entryGateEl.hidden = true;
    connect();
  });
} else {
  connect();
}

// When the tab comes back to foreground on mobile, kick a reconnect if the
// socket had been suspended. The `close` event usually fires first and
// schedules a reconnect anyway; this is belt-and-suspenders.
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && ws && ws.readyState === WebSocket.CLOSED) {
    reconnectAttempt = 0;
    connect();
  }
});

// A first click on the page is also our AudioContext unlock gesture —
// games that use ctx.feedback will have their audio silently blocked
// otherwise. Done at the shell level because the gesture requirement is
// browser policy, not game-specific.
document.addEventListener('click', () => { ensureAudioCtx(); }, { capture: true });

// ───── haptic + audio feedback ─────────────────────────────────────────────
// Two light cues: a confirming click on a successful press, a lower buzz on
// lockout. Web Audio so we don't ship audio files; navigator.vibrate for
// haptics where supported (Android; iOS doesn't expose it to the web).
// AudioContext must be created/resumed from a user-gesture callback, so we
// defer creation until the first click.

let audioCtx = null;
function ensureAudioCtx() {
  if (audioCtx) {
    if (audioCtx.state === 'suspended') audioCtx.resume().catch(() => {});
    return audioCtx;
  }
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (Ctx) audioCtx = new Ctx();
  } catch { /* browser blocks audio; fail silent */ }
  return audioCtx;
}

function playBlip({ freq, durMs, kind = 'sine', fadeOut = 0.05 }) {
  const ctx = audioCtx;
  if (!ctx) return;
  const t0 = ctx.currentTime;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = kind;
  osc.frequency.setValueAtTime(freq, t0);
  gain.gain.setValueAtTime(0.0001, t0);
  gain.gain.exponentialRampToValueAtTime(0.2, t0 + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.0001, t0 + durMs / 1000);
  osc.connect(gain).connect(ctx.destination);
  osc.start(t0);
  osc.stop(t0 + durMs / 1000 + fadeOut);
}

function feedbackPress() {
  if (navigator.vibrate) navigator.vibrate(40);
  playBlip({ freq: 880, durMs: 120, kind: 'triangle' });
}
function feedbackLockout() {
  if (navigator.vibrate) navigator.vibrate([20, 40, 80]);
  // Descending two-tone buzz.
  playBlip({ freq: 260, durMs: 180, kind: 'sawtooth' });
  setTimeout(() => playBlip({ freq: 180, durMs: 220, kind: 'sawtooth' }), 160);
}
function feedbackWin() {
  if (navigator.vibrate) navigator.vibrate([60, 40, 60, 40, 120]);
  // Arpeggio: C5, E5, G5, C6 over ~300 ms.
  const notes = [523, 659, 784, 1047];
  notes.forEach((f, i) => setTimeout(() => playBlip({ freq: f, durMs: 160, kind: 'triangle' }), i * 90));
}
function feedbackLose() {
  // Mellow descending two-note sigh (A4 → F4). No haptic — the visual overlay
  // is already clear that the round ended; buzzing on top of that feels like
  // extra punishment we don't need.
  playBlip({ freq: 440, durMs: 220, kind: 'triangle' });
  setTimeout(() => playBlip({ freq: 349, durMs: 320, kind: 'triangle' }), 180);
}
function feedbackRoundStart() {
  // Short ascending two-note "get ready". Subtle enough not to be distracting
  // across rounds but distinct from the press/lockout tones.
  playBlip({ freq: 587, durMs: 100, kind: 'sine' });
  setTimeout(() => playBlip({ freq: 784, durMs: 140, kind: 'sine' }), 110);
}

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

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[ch]);
}
