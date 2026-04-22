// Controller shell — Phase 1a. Plain browser/phone page; no Cast sender yet.

const params = new URLSearchParams(location.search);
const name = (params.get('name') || `Player ${Math.floor(Math.random() * 900 + 100)}`).slice(0, 32);

const statusEl = document.getElementById('status');
const nameEl = document.getElementById('name');
const btn = document.getElementById('ping');

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

ws.addEventListener('error', (e) => {
  console.warn('[ws] error', e);
});

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
  // iOS Safari silently ignores navigator.vibrate(); CSS scale flash is the portable visual substitute.
  btn.classList.add('flash');
  setTimeout(() => btn.classList.remove('flash'), 150);
});
