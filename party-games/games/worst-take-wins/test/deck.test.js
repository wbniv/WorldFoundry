// Unit tests for the Worst Take Wins deck loader + per-room Deck.

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { loadDeckContent, createDeck } = require('../deckLoader');

function tmpDeckDir(files) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wtw-deck-'));
  for (const [name, obj] of Object.entries(files)) {
    fs.writeFileSync(path.join(dir, name), typeof obj === 'string' ? obj : JSON.stringify(obj));
  }
  return dir;
}

// Seeded pseudo-random — same seed reproduces the same shuffle.
function seededRandom(seed = 1) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1103515245 + 12345) >>> 0;
    return (s & 0x7fffffff) / 0x80000000;
  };
}

// ───── tests ─────────────────────────────────────────────────────────────

test('loadDeckContent reads one file', () => {
  const dir = tmpDeckDir({
    'a.json': {
      name: 'A',
      prompts:   [{ id: 'p1', text: '____', blanks: 1 }],
      responses: [{ id: 'r1', text: 'a response' }],
    },
  });
  const c = loadDeckContent(dir);
  assert.equal(c.prompts.length, 1);
  assert.equal(c.responses.length, 1);
  assert.equal(c.prompts[0].id, 'p1');
});

test('loadDeckContent merges multiple files and dedupes by id', () => {
  const dir = tmpDeckDir({
    'a.json': { prompts: [{ id: 'p1', text: 'a' }], responses: [{ id: 'r1', text: 'x' }] },
    'b.json': {
      prompts:   [{ id: 'p1', text: 'dup' }, { id: 'p2', text: 'b' }],
      responses: [{ id: 'r1', text: 'dup' }, { id: 'r2', text: 'y' }],
    },
  });
  const c = loadDeckContent(dir);
  assert.equal(c.prompts.length, 2);
  assert.equal(c.responses.length, 2);
  // First occurrence wins — a.json sorts before b.json.
  assert.equal(c.prompts.find((p) => p.id === 'p1').text, 'a');
});

test('loadDeckContent throws with filename on malformed JSON', () => {
  const dir = tmpDeckDir({ 'bad.json': '{not valid' });
  assert.throws(() => loadDeckContent(dir), /bad\.json/);
});

test('loadDeckContent rejects malformed card entries', () => {
  const dir = tmpDeckDir({
    'broken.json': { prompts: [{ id: 'p1' /* missing text */ }], responses: [] },
  });
  assert.throws(() => loadDeckContent(dir), /bad prompt/);
});

test('loadDeckContent returns empty arrays for nonexistent dir', () => {
  const c = loadDeckContent('/does/not/exist/anywhere');
  assert.deepEqual(c, { prompts: [], responses: [] });
});

test('createDeck: drawPrompt / drawResponse consume from pool', () => {
  const prompts = [
    { id: 'p1', text: 'p1' }, { id: 'p2', text: 'p2' }, { id: 'p3', text: 'p3' },
  ];
  const responses = [
    { id: 'r1', text: 'r1' }, { id: 'r2', text: 'r2' },
  ];
  const d = createDeck({ prompts, responses, random: seededRandom(42) });
  const drawn = [d.drawPrompt(), d.drawPrompt(), d.drawPrompt(), d.drawPrompt()];
  assert.equal(drawn.filter(Boolean).length, 3);
  assert.equal(drawn[3], null);  // pool dry, discard empty
});

test('createDeck reshuffles from discard when pool drains', () => {
  const prompts = [{ id: 'p1', text: 'p1' }, { id: 'p2', text: 'p2' }];
  const responses = [];
  const d = createDeck({ prompts, responses, random: seededRandom(7) });
  const p1 = d.drawPrompt();
  const p2 = d.drawPrompt();
  // Pool empty. Discard both — they must come back.
  d.discardPrompt(p1);
  d.discardPrompt(p2);
  assert.ok(d.drawPrompt());
  assert.ok(d.drawPrompt());
  assert.equal(d.drawPrompt(), null);
});

test('createDeck: same seed → same draw order (determinism check)', () => {
  const prompts = Array.from({ length: 10 }, (_, i) => ({ id: `p${i}`, text: `p${i}` }));
  const d1 = createDeck({ prompts, responses: [], random: seededRandom(1) });
  const d2 = createDeck({ prompts, responses: [], random: seededRandom(1) });
  const seq1 = [];
  const seq2 = [];
  for (let i = 0; i < 10; i++) { seq1.push(d1.drawPrompt().id); seq2.push(d2.drawPrompt().id); }
  assert.deepEqual(seq1, seq2);
});

test('createDeck: responseTextIndex survives discards', () => {
  const responses = [{ id: 'r1', text: 'hello' }];
  const d = createDeck({ prompts: [], responses, random: seededRandom(1) });
  const c = d.drawResponse();
  d.discardResponse(c);
  // After discard, the index still resolves the id.
  assert.equal(d.responseTextIndex().get('r1'), 'hello');
});
