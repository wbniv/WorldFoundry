// Platform relay server — factory form so tests can spin up isolated instances.
//
// Serves receiver-shell/ and controller-shell/ as static, exposes a WebSocket at /ws,
// and relays HELLO / PING events between clients. Rooms are identified by a
// 4-character code so multiple groups can share one server without colliding.

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
// Room code alphabet — uppercase Latin letters with the visually ambiguous
// ones (I, O, Q) dropped. 23^4 ≈ 280k distinct codes, plenty for our scale.
const ROOM_ALPHA = 'ABCDEFGHJKLMNPRSTUVWXYZ';
const ROOM_CODE_LEN = 4;
const ROOM_CODE_RE = new RegExp(`^[${ROOM_ALPHA}]{${ROOM_CODE_LEN}}$`);

function resolveStatic(url) {
  const clean = url.split('?')[0];
  if (clean === '/' || clean === '')      return '/controller-shell/index.html';
  if (clean === '/receiver')              return '/receiver-shell/index.html';
  if (clean === '/controller')            return '/controller-shell/index.html';
  // Sibling assets — <script src="receiver.js"> loaded from /receiver (no trailing
  // slash) resolves to /receiver.js, not /receiver/receiver.js. Route those in.
  if (clean.startsWith('/receiver.'))     return '/receiver-shell/' + clean.slice(1);
  if (clean.startsWith('/controller.'))   return '/controller-shell/' + clean.slice(1);
  if (clean.startsWith('/receiver/'))     return '/receiver-shell' + clean.slice('/receiver'.length);
  if (clean.startsWith('/controller/'))   return '/controller-shell' + clean.slice('/controller'.length);
  return clean;
}

/**
 * Start a platform relay instance.
 *
 * @param {object} opts
 * @param {number}  [opts.port=8080]          0 = ephemeral (tests)
 * @param {string}  [opts.staticRoot]         dir holding receiver-shell/ + controller-shell/
 * @param {boolean} [opts.quiet=false]        suppress console.log chatter (tests)
 * @param {function} [opts.gameFactory]       () → game plugin instance; called once per room.
 *                                            Plugin interface: {onJoin?, onLeave?, onMessage?}
 *                                            where services = {broadcast, sendTo, getPlayers,
 *                                            getHost, now, schedule, random}.
 * @param {object}  [opts.game]               DEPRECATED — single game instance shared across
 *                                            every room. Works fine for single-room testing
 *                                            but state collides once two rooms share it.
 *                                            Prefer gameFactory.
 * @returns {Promise<{server, wss, port, close, rooms}>}
 */
function createServer(opts = {}) {
  const port = opts.port ?? 8080;
  const staticRoot = opts.staticRoot ?? path.resolve(__dirname, '..');
  const quiet = !!opts.quiet;
  const gameFactory = opts.gameFactory ?? (opts.game ? () => opts.game : null);
  const now = opts.now ?? (() => Date.now());
  const scheduleFn = opts.schedule ?? ((ms, fn) => {
    const h = setTimeout(fn, ms);
    return () => clearTimeout(h);
  });
  const log = quiet ? () => {} : (...args) => console.log(...args);
  const random = opts.random ?? Math.random;

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
      // Dev loop: forbid browser caching so controller.js / receiver.js / CSS
      // changes pushed while players have tabs open are reflected on reload
      // without hard-refresh. When we move to production static hosting
      // (Phase 4), we'll revisit with versioned URLs and long max-age.
      res.setHeader('cache-control', 'no-store, no-cache, must-revalidate');
      res.setHeader('pragma', 'no-cache');
      res.end(data);
    });
  });

  const wss = new WebSocketServer({
    server,
    path: '/ws',
    maxPayload: MAX_MESSAGE_BYTES,
  });

  // ──── room registry ────────────────────────────────────────────────────────
  // Each room holds its own player/receiver sets plus an independent game
  // plugin instance. Rooms are created on first HELLO that references them
  // and destroyed when their last member disconnects.
  const rooms = new Map();  // code → Room

  function generateRoomCode() {
    // Cryptographically non-essential — these codes are just for grouping
    // players; collision is merely inconvenient.
    while (true) {
      let code = '';
      for (let i = 0; i < ROOM_CODE_LEN; i++) {
        code += ROOM_ALPHA[Math.floor(random() * ROOM_ALPHA.length)];
      }
      if (!rooms.has(code)) return code;
    }
  }

  function ensureRoom(code) {
    let room = rooms.get(code);
    if (room) return room;
    room = {
      code,
      everyone:  new Set(),
      receivers: new Set(),
      players:   new Map(),   // playerId → { id, name, ws, joinedAt }
      nextPlayerId: 1,
      game: null,
      services: null,
    };
    // Game plugin is per-room so state doesn't leak across rooms.
    room.game = gameFactory ? gameFactory() : null;
    room.services = makeServices(room);
    rooms.set(code, room);
    log(`[ws] room ${code} created`);
    return room;
  }

  function destroyRoomIfEmpty(room) {
    if (room.everyone.size > 0) return;
    rooms.delete(room.code);
    log(`[ws] room ${room.code} destroyed (empty)`);
  }

  function snapshotState(room) {
    return {
      type: 'STATE',
      room: room.code,
      players: [...room.players.values()].map(p => ({ id: p.id, name: p.name })),
      hostId: firstHostId(room),
    };
  }

  function broadcastRoom(room, msg, recipients) {
    const data = JSON.stringify(msg);
    const dest = recipients ?? room.everyone;
    for (const ws of dest) {
      if (ws.readyState === ws.OPEN) ws.send(data);
    }
  }

  function sendToInRoom(room, playerId, msg) {
    const p = room.players.get(playerId);
    if (p && p.ws.readyState === p.ws.OPEN) p.ws.send(JSON.stringify(msg));
  }

  /** First-joined player is host; re-elect when they leave. */
  function firstHostId(room) {
    let first = null;
    for (const p of room.players.values()) {
      if (!first || p.joinedAt < first.joinedAt) first = p;
    }
    return first ? first.id : null;
  }

  // Services surface handed to game plugins. Platform-owned message types
  // (HELLO, PING, STATE, WELCOME, PONG) stay reserved; games should use
  // distinct type names.
  function makeServices(room) {
    return {
      broadcast(msg) { broadcastRoom(room, msg); },
      sendTo(playerId, msg) { sendToInRoom(room, playerId, msg); },
      getPlayers() { return [...room.players.values()].map(p => ({ id: p.id, name: p.name })); },
      getHost() {
        const id = firstHostId(room);
        if (id == null) return null;
        const p = room.players.get(id);
        return { id: p.id, name: p.name };
      },
      now,
      schedule: scheduleFn,
      random,
    };
  }

  wss.on('connection', (ws) => {
    let role = null;
    let room = null;        // Room reference once HELLO lands
    let playerId = null;

    ws.on('message', (raw) => {
      if (raw.length > MAX_MESSAGE_BYTES) return;

      let msg;
      try { msg = JSON.parse(raw); } catch { return; }
      if (!msg || typeof msg !== 'object' || typeof msg.type !== 'string') return;

      switch (msg.type) {
        case 'HELLO': {
          if (role !== null) return;  // HELLO is not repeatable
          const requestedRole = msg.role === 'receiver' ? 'receiver'
                              : msg.role === 'controller' ? 'controller'
                              : null;
          if (!requestedRole) return;  // reject unknown role; stay anonymous

          // Room code: case-insensitive from client. Receivers may omit it
          // to have the server generate a fresh one; controllers must supply
          // a valid one (we're permissive about existence — any valid-
          // shaped code creates the room if it doesn't exist).
          let reqRoom = typeof msg.room === 'string' ? msg.room.toUpperCase() : '';
          if (reqRoom && !ROOM_CODE_RE.test(reqRoom)) {
            ws.send(JSON.stringify({ type: 'BAD_ROOM', room: reqRoom }));
            return;
          }
          if (!reqRoom) {
            if (requestedRole === 'receiver') {
              reqRoom = generateRoomCode();
            } else {
              // Controllers need a code. Tell them so they can prompt.
              ws.send(JSON.stringify({ type: 'NEED_ROOM' }));
              return;
            }
          }

          role = requestedRole;
          room = ensureRoom(reqRoom);
          room.everyone.add(ws);

          if (role === 'receiver') {
            room.receivers.add(ws);
            log(`[ws] receiver attached to room=${room.code}`);
            ws.send(JSON.stringify({ type: 'WELCOME_RECEIVER', room: room.code }));
            ws.send(JSON.stringify(snapshotState(room)));
          } else {
            playerId = room.nextPlayerId++;
            const name = String(msg.name ?? '').slice(0, MAX_NAME_LEN) || `Player ${playerId}`;
            const player = { id: playerId, name, ws, joinedAt: now() };
            room.players.set(playerId, player);
            log(`[ws] player joined room=${room.code} id=${playerId} name=${name}`);
            ws.send(JSON.stringify({
              type: 'WELCOME',
              id: playerId,
              name,
              hostId: firstHostId(room),
              room: room.code,
            }));
            broadcastRoom(room, snapshotState(room));
            try { room.game?.onJoin?.({ id: playerId, name }, room.services); }
            catch (e) { log('[game] onJoin threw', e); }
          }
          break;
        }
        case 'PING': {
          if (role !== 'controller' || playerId == null || !room) break;
          const clientTs = Number.isFinite(msg.clientTs) ? msg.clientTs : null;
          broadcastRoom(room, {
            type: 'PONG',
            from: playerId,
            name: room.players.get(playerId)?.name,
            clientTs,
            serverTs: now(),
          });
          break;
        }
        default: {
          if (role === 'controller' && playerId != null && room && room.game?.onMessage) {
            try {
              const p = room.players.get(playerId);
              room.game.onMessage({ id: p.id, name: p.name }, msg, room.services);
            } catch (e) {
              log('[game] onMessage threw', e);
            }
          }
        }
      }
    });

    ws.on('close', () => {
      if (!room) return;
      room.everyone.delete(ws);
      if (role === 'receiver') {
        room.receivers.delete(ws);
        log(`[ws] receiver detached room=${room.code}`);
      } else if (playerId != null) {
        const p = room.players.get(playerId);
        room.players.delete(playerId);
        log(`[ws] player left room=${room.code} id=${playerId}`);
        broadcastRoom(room, snapshotState(room));
        if (p && room.game?.onLeave) {
          try { room.game.onLeave({ id: p.id, name: p.name }, room.services); }
          catch (e) { log('[game] onLeave threw', e); }
        }
      }
      destroyRoomIfEmpty(room);
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
        rooms,   // expose for tests + diagnostics (e.g., `srv.rooms.size`)
        close() {
          return new Promise((res) => {
            for (const room of rooms.values()) {
              for (const ws of room.everyone) {
                try { ws.terminate(); } catch {}
              }
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

module.exports = {
  createServer,
  MAX_MESSAGE_BYTES,
  MAX_NAME_LEN,
  ROOM_ALPHA,
  ROOM_CODE_LEN,
  ROOM_CODE_RE,
};
