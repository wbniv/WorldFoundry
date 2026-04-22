// Receiver shell — Phase 1a. Runs on both Chromecast and in a plain browser.

const statusEl = document.getElementById('status');
const playerListEl = document.getElementById('player-list');
const eventLogEl = document.getElementById('event-log');

// Cast Application Framework (CAF) start — only on real Cast / dev-whitelisted devices.
// In a regular browser, `cast.framework` is undefined; we skip silently and keep the
// server WebSocket as the only transport for dev-loop iteration.
let isCastContext = false;
let castSessionDetail = '';
if (typeof cast !== 'undefined' && cast.framework) {
  try {
    const ctx = cast.framework.CastReceiverContext.getInstance();
    ctx.addEventListener(cast.framework.system.EventType.READY, (ev) => {
      const info = ctx.getApplicationData();
      castSessionDetail = info?.name ? ` (${info.name})` : '';
      refreshStatus('cast + server connected' + castSessionDetail);
      console.log('[cast] READY', info);
    });
    ctx.addEventListener(cast.framework.system.EventType.SENDER_CONNECTED, (ev) => {
      pushLog(`sender connected: ${ev.senderId}`);
    });
    ctx.addEventListener(cast.framework.system.EventType.SENDER_DISCONNECTED, (ev) => {
      pushLog(`sender disconnected: ${ev.senderId}`);
    });
    ctx.start();
    isCastContext = true;
    console.log('[cast] CastReceiverContext started');
  } catch (e) {
    console.warn('[cast] start failed', e);
  }
}

const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
const ws = new WebSocket(wsUrl);

ws.addEventListener('open', () => {
  ws.send(JSON.stringify({ type: 'HELLO', role: 'receiver' }));
  refreshStatus(isCastContext ? 'cast + server connected' + castSessionDetail : 'server connected (browser)');
});

ws.addEventListener('close', () => {
  refreshStatus('disconnected');
});

function refreshStatus(text) {
  statusEl.textContent = text;
}

ws.addEventListener('error', (e) => {
  console.warn('[ws] error', e);
});

ws.addEventListener('message', (ev) => {
  let msg;
  try { msg = JSON.parse(ev.data); } catch { return; }

  if (msg.type === 'STATE') {
    renderPlayers(msg.players);
  } else if (msg.type === 'PONG') {
    const latency = msg.serverTs - msg.clientTs;
    pushLog(`PONG from ${msg.name} (client→server ≈ ${latency} ms)`);
  }
});

function renderPlayers(players) {
  playerListEl.innerHTML = '';
  if (!players || !players.length) {
    const li = document.createElement('li');
    li.className = 'empty';
    li.textContent = '(no players yet)';
    playerListEl.appendChild(li);
    return;
  }
  for (const p of players) {
    const li = document.createElement('li');
    li.textContent = `#${p.id} · ${p.name}`;
    playerListEl.appendChild(li);
  }
}

function pushLog(text) {
  const li = document.createElement('li');
  const time = new Date().toLocaleTimeString();
  li.textContent = `[${time}] ${text}`;
  eventLogEl.prepend(li);
  while (eventLogEl.children.length > 20) eventLogEl.removeChild(eventLogEl.lastChild);
}
