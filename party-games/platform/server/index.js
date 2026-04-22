// Party Games Platform — relay server. Phase 1a.
//
// Serves the receiver and controller static pages and relays WebSocket events
// between them. Single room, in-memory state; no persistence.

const http = require('http');
const fs = require('fs');
const path = require('path');
const { WebSocketServer } = require('ws');

const PORT = Number(process.env.PORT) || 8080;
const ROOT = path.resolve(__dirname, '..');  // serves sibling receiver-shell/ + controller-shell/

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js':   'text/javascript; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg':  'image/svg+xml',
  '.png':  'image/png',
  '.ico':  'image/x-icon',
};

function resolveStatic(url) {
  const clean = url.split('?')[0];
  if (clean === '/' || clean === '')                return '/controller-shell/index.html';
  if (clean === '/receiver')                        return '/receiver-shell/index.html';
  if (clean === '/controller')                      return '/controller-shell/index.html';
  if (clean.startsWith('/receiver/'))               return '/receiver-shell' + clean.slice('/receiver'.length);
  if (clean.startsWith('/controller/'))             return '/controller-shell' + clean.slice('/controller'.length);
  return clean;
}

const server = http.createServer((req, res) => {
  const mapped = resolveStatic(req.url);
  const filePath = path.join(ROOT, mapped);

  // Path traversal guard.
  if (!filePath.startsWith(ROOT + path.sep) && filePath !== ROOT) {
    res.statusCode = 403;
    res.end('forbidden');
    return;
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.statusCode = 404;
      res.setHeader('content-type', 'text/plain; charset=utf-8');
      res.end('not found: ' + mapped);
      return;
    }
    res.setHeader('content-type', MIME[path.extname(filePath)] || 'application/octet-stream');
    res.end(data);
  });
});

const wss = new WebSocketServer({ server, path: '/ws' });

const everyone  = new Set();                 // all open connections
const receivers = new Set();                 // subset with role=receiver
const players   = new Map();                 // playerId → { id, name, ws }
let nextPlayerId = 1;

function snapshotState() {
  return {
    type: 'STATE',
    players: [...players.values()].map(p => ({ id: p.id, name: p.name })),
  };
}

function broadcast(msg, recipients = everyone) {
  const data = JSON.stringify(msg);
  for (const ws of recipients) {
    if (ws.readyState === ws.OPEN) ws.send(data);
  }
}

wss.on('connection', (ws) => {
  everyone.add(ws);
  let role = null;
  let playerId = null;

  ws.on('message', (raw) => {
    let msg;
    try { msg = JSON.parse(raw); } catch { return; }

    switch (msg.type) {
      case 'HELLO': {
        role = msg.role;
        if (role === 'receiver') {
          receivers.add(ws);
          console.log('[ws] receiver attached');
          ws.send(JSON.stringify(snapshotState()));
        } else if (role === 'controller') {
          playerId = nextPlayerId++;
          const name = (msg.name || `Player ${playerId}`).slice(0, 32);
          players.set(playerId, { id: playerId, name, ws });
          console.log(`[ws] player joined id=${playerId} name=${name}`);
          ws.send(JSON.stringify({ type: 'WELCOME', id: playerId, name }));
          broadcast(snapshotState());
        }
        break;
      }
      case 'PING': {
        if (role !== 'controller' || playerId == null) break;
        broadcast({
          type: 'PONG',
          from: playerId,
          name: players.get(playerId)?.name,
          clientTs: msg.clientTs,
          serverTs: Date.now(),
        });
        break;
      }
    }
  });

  ws.on('close', () => {
    everyone.delete(ws);
    if (role === 'receiver') {
      receivers.delete(ws);
      console.log('[ws] receiver detached');
    } else if (playerId != null) {
      players.delete(playerId);
      console.log(`[ws] player left id=${playerId}`);
      broadcast(snapshotState());
    }
  });
});

server.listen(PORT, () => {
  console.log(`party-games platform ready on http://localhost:${PORT}`);
  console.log(`  receiver:   http://localhost:${PORT}/receiver`);
  console.log(`  controller: http://localhost:${PORT}/controller?name=Alice`);
});
