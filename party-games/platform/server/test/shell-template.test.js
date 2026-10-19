// Shell HTML templating + /game/* and /shell-lib/* routing tests.

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const path = require('node:path');

const { createServer } = require('../createServer');

function fetchText(port, urlPath) {
  return new Promise((resolve, reject) => {
    http.get({ host: 'localhost', port, path: urlPath }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => resolve({
        status: res.statusCode,
        contentType: res.headers['content-type'],
        body: Buffer.concat(chunks).toString('utf8'),
      }));
    }).on('error', reject);
  });
}

async function withSrv(opts, fn) {
  const srv = await createServer({ port: 0, quiet: true, ...opts });
  try { await fn({ port: srv.port, ...srv }); } finally { await srv.close(); }
}

// ───── tests ─────────────────────────────────────────────────────────────

test('/controller has game-name meta, game-root div, and stylesheet link when game has CSS', async () => {
  await withSrv({ gameName: 'reaction' }, async ({ port }) => {
    const r = await fetchText(port, '/controller');
    assert.equal(r.status, 200);
    assert.match(r.body, /<meta\s+name="game-name"\s+content="reaction">/);
    assert.match(r.body, /id="game-root"/);
    // reaction ships a controller.css so the stylesheet link should be present
    assert.match(r.body, /<link[^>]+href="\/game\/client\/controller\.css">/);
  });
});

test('/receiver has game-name meta and stylesheet when game has CSS', async () => {
  await withSrv({ gameName: 'reaction' }, async ({ port }) => {
    const r = await fetchText(port, '/receiver');
    assert.equal(r.status, 200);
    assert.match(r.body, /<meta\s+name="game-name"\s+content="reaction">/);
    assert.match(r.body, /<link[^>]+href="\/game\/client\/receiver\.css">/);
  });
});

test('placeholder empty when no game is active', async () => {
  await withSrv({ gameName: null }, async ({ port }) => {
    const r = await fetchText(port, '/controller');
    assert.equal(r.status, 200);
    assert.match(r.body, /<meta\s+name="game-name"\s+content="">/);
    // No game stylesheet link at all when there's no game.
    assert.doesNotMatch(r.body, /\/game\/client\/controller\.css/);
  });
});

test('stylesheet tag omitted when per-game CSS file is missing', async () => {
  // Point gamesRoot at a temp location where the game exists but has no CSS.
  const tmp = path.join(__dirname, 'fixtures-games-empty');
  const fs = require('node:fs');
  fs.mkdirSync(path.join(tmp, 'noop', 'client'), { recursive: true });
  fs.writeFileSync(path.join(tmp, 'noop', 'client', 'controller.js'),
    'export function mount(){} export function unmount(){}');
  try {
    await withSrv({ gameName: 'noop', gamesRoot: tmp }, async ({ port }) => {
      const r = await fetchText(port, '/controller');
      assert.equal(r.status, 200);
      // Placeholder expands to empty string, not a 404-ing link.
      assert.doesNotMatch(r.body, /\/game\/client\/controller\.css/);
      // Game JS still fetchable.
      const js = await fetchText(port, '/game/client/controller.js');
      assert.equal(js.status, 200);
    });
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});

test('/game/client/<file> resolves under the active game', async () => {
  await withSrv({ gameName: 'reaction' }, async ({ port }) => {
    const js = await fetchText(port, '/game/client/controller.js');
    assert.equal(js.status, 200);
    assert.match(js.contentType, /text\/javascript/);
    assert.match(js.body, /Reaction-game controller/);
  });
});

test('/game/client/<missing> returns a helpful 404', async () => {
  await withSrv({ gameName: 'reaction' }, async ({ port }) => {
    const r = await fetchText(port, '/game/client/does-not-exist.js');
    assert.equal(r.status, 404);
    assert.match(r.body, /reaction/);
  });
});

test('/game/* path traversal returns 403', async () => {
  await withSrv({ gameName: 'reaction' }, async ({ port }) => {
    const r = await fetchText(port, '/game/client/../../server/index.js');
    assert.equal(r.status, 403);
  });
});

test('/game/* when no game active returns 404 with clear message', async () => {
  await withSrv({ gameName: null }, async ({ port }) => {
    const r = await fetchText(port, '/game/client/controller.js');
    assert.equal(r.status, 404);
    assert.match(r.body, /no game active/);
  });
});

test('/shell-lib/<file> serves from platform/shell-lib', async () => {
  await withSrv({}, async ({ port }) => {
    const r = await fetchText(port, '/shell-lib/scoreboard.js');
    assert.equal(r.status, 200);
    assert.match(r.contentType, /text\/javascript/);
    assert.match(r.body, /renderScoreboard/);
  });
});

test('/shell-lib/* path traversal returns 403', async () => {
  await withSrv({}, async ({ port }) => {
    const r = await fetchText(port, '/shell-lib/../server/index.js');
    assert.equal(r.status, 403);
  });
});
