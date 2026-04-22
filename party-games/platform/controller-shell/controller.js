// Controller — Phase 1c. Adds Cast Sender so the user can launch the receiver
// on their TV with one tap. Game state still flows through the relay server,
// not through the Cast message bus.

const CAST_APPLICATION_ID = 'A40DF337';  // Party Games Platform (dev) — registered in Cast Console.

// ───── party-games WebSocket ────────────────────────────────────────────────

const params = new URLSearchParams(location.search);
const name = (params.get('name') || `Player ${Math.floor(Math.random() * 900 + 100)}`).slice(0, 32);

const statusEl = document.getElementById('status');
const nameEl = document.getElementById('name');
const btn = document.getElementById('ping');
const castStateEl = document.getElementById('cast-state');

nameEl.textContent = `Hi, ${name}.`;

const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
const ws = new WebSocket(wsUrl);

ws.addEventListener('open', () => {
  ws.send(JSON.stringify({ type: 'HELLO', role: 'controller', name }));
});
ws.addEventListener('close', () => {
  statusEl.textContent = 'disconnected';
  btn.disabled = true;
});
ws.addEventListener('error', (e) => console.warn('[ws] error', e));
ws.addEventListener('message', (ev) => {
  let msg;
  try { msg = JSON.parse(ev.data); } catch { return; }
  if (msg.type === 'WELCOME') {
    statusEl.textContent = `connected · id=${msg.id}`;
    btn.disabled = false;
  }
});

btn.addEventListener('click', () => {
  if (ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: 'PING', clientTs: Date.now() }));
  btn.classList.add('flash');
  setTimeout(() => btn.classList.remove('flash'), 150);
});

// ───── Cast Sender ──────────────────────────────────────────────────────────

// The Cast SDK fires __onGCastApiAvailable once cast_sender.js + cast.framework finish loading.
window.__onGCastApiAvailable = (isAvailable) => {
  if (!isAvailable) {
    setCastState('cast: unavailable', 'unavail');
    return;
  }
  try {
    const ctx = cast.framework.CastContext.getInstance();
    ctx.setOptions({
      receiverApplicationId: CAST_APPLICATION_ID,
      autoJoinPolicy: chrome.cast.AutoJoinPolicy.ORIGIN_SCOPED,
      resumeSavedSession: true,
    });
    ctx.addEventListener(cast.framework.CastContextEventType.CAST_STATE_CHANGED, (ev) => {
      switch (ev.castState) {
        case cast.framework.CastState.NO_DEVICES_AVAILABLE:
          setCastState('cast: no devices found', 'idle');
          break;
        case cast.framework.CastState.NOT_CONNECTED:
          setCastState('cast: ready — tap the button', 'idle');
          break;
        case cast.framework.CastState.CONNECTING:
          setCastState('cast: connecting…', 'connecting');
          break;
        case cast.framework.CastState.CONNECTED: {
          const session = ctx.getCurrentSession();
          const device = session?.getCastDevice()?.friendlyName || 'Chromecast';
          setCastState(`cast: on ${device}`, 'connected');
          break;
        }
      }
    });
    // Trigger initial state emission after setOptions settles.
    setCastState('cast: initialising…', 'idle');
  } catch (e) {
    console.warn('[cast] init failed', e);
    setCastState('cast: init failed', 'unavail');
  }
};

function setCastState(text, cls) {
  castStateEl.textContent = text;
  castStateEl.dataset.state = cls;
}
