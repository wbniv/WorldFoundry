// Receiver shell — platform-only (Phase 5 seam).
//
// Runs on both Chromecast and in a plain browser tab (the dev loop). Like
// the controller shell, it delegates all game-specific rendering to a
// per-game module at games/<WF_GAME>/client/receiver.js loaded dynamically
// from /game/client/receiver.js.
//
// Shell responsibilities:
//   - Open the WebSocket and identify as receiver
//   - Render the room-code chip and mirror it into the URL
//   - Track player roster + host (for games that want them via ctx.players())
//   - Boot CAF on actual Cast devices (skip in browser; CAF retries forever)
//   - Maintain the event log at the bottom of the page
//   - Dispatch non-platform messages to game subscribers
//
// Everything under <div id="game-root"> belongs to the game module.

const statusEl     = document.getElementById('status');
const roomCodeEl   = document.getElementById('room-code');
const eventLogEl   = document.getElementById('event-log');
const gameRoot     = document.getElementById('game-root');

const gameNameMeta = document.querySelector('meta[name="game-name"]');
const gameName = (gameNameMeta && gameNameMeta.content) ? gameNameMeta.content : null;

// Room code: from URL ?room=ABCD, else server assigns on HELLO and we fill
// this in from the WELCOME_RECEIVER response. URL is rewritten on assign so
// a refresh stays in the same room.
const urlParams = new URLSearchParams(location.search);
let roomCode = (urlParams.get('room') || '').toUpperCase();
if (roomCode) roomCodeEl.textContent = roomCode;

let currentPlayers = [];
let currentHostId = null;

// Subscribers registered by the game via ctx.on(type, handler)
const gameSubscribers = new Map();  // type → Set<handler>

let gameModule = null;
let mounted = false;

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

// ───── game module loading ─────────────────────────────────────────────────

async function loadGameModule() {
  if (gameModule || !gameName) return;
  try {
    gameModule = await import(`/game/client/receiver.js?g=${encodeURIComponent(gameName)}`);
  } catch (e) {
    console.warn(`[shell] failed to load /game/client/receiver.js for '${gameName}':`, e.message);
    gameRoot.innerHTML =
      `<p class="shell-error">game UI missing for '<code>${escapeHtml(gameName)}</code>' — ` +
      `expected <code>games/${escapeHtml(gameName)}/client/receiver.js</code></p>`;
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
    get playerId() { return null; },   // receivers aren't players
    isHost: () => false,
    players: () => currentPlayers.map((p) => ({ id: p.id, name: p.name })),
    hostId: () => currentHostId,
    feedback: { press: noop, lockout: noop, win: noop, lose: noop, roundStart: noop },
    assetUrl: (asset) => `/game/assets/${asset}`,
    log: pushLog,
  };
}

function noop() {}

// ───── WebSocket ───────────────────────────────────────────────────────────

const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
const ws = new WebSocket(wsUrl);

ws.addEventListener('open', () => {
  ws.send(JSON.stringify({ type: 'HELLO', role: 'receiver', room: roomCode || undefined }));
  refreshStatus(isCastContext ? 'cast + server connected' + castSessionDetail : 'server connected (browser)');
});
ws.addEventListener('close', () => { unmountGame(); refreshStatus('disconnected'); });
ws.addEventListener('error', (e) => console.warn('[ws] error', e));

ws.addEventListener('message', async (ev) => {
  let msg;
  try { msg = JSON.parse(ev.data); } catch { return; }
  if (!msg || typeof msg.type !== 'string') return;

  switch (msg.type) {
    case 'WELCOME_RECEIVER':
      roomCode = msg.room;
      roomCodeEl.textContent = roomCode;
      // Reflect the code in the URL so a refresh keeps the same room.
      if (!urlParams.get('room')) {
        urlParams.set('room', roomCode);
        const newUrl = location.pathname + '?' + urlParams.toString() + location.hash;
        history.replaceState(null, '', newUrl);
      }
      await loadGameModule();
      mountGame();
      break;

    case 'STATE':
      logPlayerDiff(currentPlayers, msg.players || []);
      currentPlayers = msg.players || [];
      currentHostId  = msg.hostId ?? null;
      break;
  }

  // Dispatch to game subscribers — including STATE so games can re-render
  // their player list / scoreboard.
  const subs = gameSubscribers.get(msg.type);
  if (subs) {
    for (const handler of subs) {
      try { handler(msg); } catch (e) { console.error(`[shell] game handler for ${msg.type} threw:`, e); }
    }
  }
});

// ───── helpers ─────────────────────────────────────────────────────────────

function refreshStatus(text) { statusEl.textContent = text; }

function pushLog(text) {
  const li = document.createElement('li');
  const time = new Date().toLocaleTimeString();
  li.textContent = `[${time}] ${text}`;
  eventLogEl.prepend(li);
  while (eventLogEl.children.length > 20) eventLogEl.removeChild(eventLogEl.lastChild);
}

function logPlayerDiff(oldList, newList) {
  const oldById = new Map((oldList || []).map((p) => [p.id, p]));
  const newById = new Map((newList || []).map((p) => [p.id, p]));
  for (const [, p] of newById) if (!oldById.has(p.id)) pushLog(`${p.name} joined`);
  for (const [, p] of oldById) if (!newById.has(p.id)) pushLog(`${p.name} left`);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[ch]);
}
