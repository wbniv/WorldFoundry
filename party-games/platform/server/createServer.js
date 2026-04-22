// Platform relay server — factory form so tests can spin up isolated instances.
//
// Serves receiver-shell/ and controller-shell/ as static, exposes a WebSocket at /ws,
// and relays HELLO / PING events between clients. Single room, in-memory state.

const http = require('http');
const fs = require('fs');
const path = require('path');
const { WebSocketServer } = require('ws');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js':   'text/javascript; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg':  'image/svg+xml',
  '.png':  'image/png',
  '.ico':  'image/x-icon',
};

const MAX_MESSAGE_BYTES = 16 * 1024;
const MAX_NAME_LEN = 32;

function resolveStatic(url) {
  const clean = url.split('?')[0];
  if (clean === '/' || clean === '')      return '/controller-shell/index.html';
  if (clean === '/receiver')              return '/receiver-shell/index.html';
  if (clean === '/controller')            return '/controller-shell/index.html';
  if (clean.startsWith('/receiver/'))     return '/receiver-shell' + clean.slice('/receiver'.length);
  if (clean.startsWith('/controller/'))   return '/controller-shell' + clean.slice('/controller'.length);
  return clean;
}

/**
 * Start a platform relay instance.
 *
 * @param {object} opts
 * @param {number} [opts.port=8080]     0 = ephemeral (tests)
 * @param {string} [opts.staticRoot]    dir holding receiver-shell/ + controller-shell/
 * @param {boolean} [opts.quiet=false]  suppress console.log chatter (tests)
 * @returns {Promise<{server: http.Server, wss: WebSocketServer, port: number, close: () => Promise<void>}>}
 */
function createServer(opts = {}) {
  const port = opts.port ?? 8080;
  const staticRoot = opts.staticRoot ?? path.resolve(__dirname, '..');
  const quiet = !!opts.quiet;
  const log = quiet ? () => {} : (...args) => console.log(...args);

  const server = http.createServer((req, res) => {
    const mapped = resolveStatic(req.url);
    const filePath = path.join(staticRoot, mapped);

    // Path-traversal guard — reject anything that escapes the static root.
    if (!filePath.startsWith(staticRoot + path.sep) && filePath !== staticRoot) {
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

  const wss = new WebSocketServer({
    server,
    path: '/ws',
    maxPayload: MAX_MESSAGE_BYTES,
  });

  const everyone  = new Set();
  const receivers = new Set();
  const players   = new Map();   // playerId → { id, name, ws }
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
      // raw is a Buffer. The `ws` library already enforces maxPayload, so the
      // size check here is belt-and-suspenders for downstream ws versions.
      if (raw.length > MAX_MESSAGE_BYTES) return;

      let msg;
      try { msg = JSON.parse(raw); } catch { return; }
      if (!msg || typeof msg !== 'object' || typeof msg.type !== 'string') return;

      switch (msg.type) {
        case 'HELLO': {
          if (role !== null) return;  // HELLO is not repeatable
          role = msg.role === 'receiver' ? 'receiver'
               : msg.role === 'controller' ? 'controller'
               : null;
          if (role === 'receiver') {
            receivers.add(ws);
            log('[ws] receiver attached');
            ws.send(JSON.stringify(snapshotState()));
          } else if (role === 'controller') {
            playerId = nextPlayerId++;
            const name = String(msg.name ?? '').slice(0, MAX_NAME_LEN) || `Player ${playerId}`;
            players.set(playerId, { id: playerId, name, ws });
            log(`[ws] player joined id=${playerId} name=${name}`);
            ws.send(JSON.stringify({ type: 'WELCOME', id: playerId, name }));
            broadcast(snapshotState());
          } else {
            role = null;  // reject unknown role; stay anonymous
          }
          break;
        }
        case 'PING': {
          if (role !== 'controller' || playerId == null) break;
          const clientTs = Number.isFinite(msg.clientTs) ? msg.clientTs : null;
          broadcast({
            type: 'PONG',
            from: playerId,
            name: players.get(playerId)?.name,
            clientTs,
            serverTs: Date.now(),
          });
          break;
        }
        // Unknown types are silently dropped.
      }
    });

    ws.on('close', () => {
      everyone.delete(ws);
      if (role === 'receiver') {
        receivers.delete(ws);
        log('[ws] receiver detached');
      } else if (playerId != null) {
        players.delete(playerId);
        log(`[ws] player left id=${playerId}`);
        broadcast(snapshotState());
      }
    });

    ws.on('error', (err) => {
      log('[ws] socket error', err.message);
    });
  });

  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, () => {
      const actualPort = server.address().port;
      resolve({
        server,
        wss,
        port: actualPort,
        close() {
          return new Promise((res) => {
            for (const ws of everyone) {
              try { ws.terminate(); } catch {}
            }
            wss.close(() => {
              server.close(() => res());
            });
          });
        },
      });
    });
  });
}

module.exports = { createServer, MAX_MESSAGE_BYTES, MAX_NAME_LEN };
