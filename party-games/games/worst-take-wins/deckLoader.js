// Worst Take Wins — deck loader + per-room Deck.
//
// Deck content is loaded from party-games/games/worst-take-wins/assets/decks/*.json
// at module startup (once, cached). Each room then builds its own shuffled
// Deck instance over that shared content using services.random() so per-
// room randomness stays isolated.

const fs = require('node:fs');
const path = require('node:path');

/**
 * Read every `.json` file in `dir` and merge into one content object.
 *
 * File format:
 *   {
 *     "name": "...",
 *     "license": "...",
 *     "attribution": "...",
 *     "prompts":   [{ "id": "p001", "text": "...____...", "blanks": 1, "tags": [] }],
 *     "responses": [{ "id": "r001", "text": "...",                    "tags": [] }]
 *   }
 *
 * Duplicate ids across files are dropped (first occurrence wins). A
 * malformed file throws with the filename included so the operator can
 * find it quickly.
 *
 * @returns {{ prompts: Array, responses: Array }}
 */
function loadDeckContent(dir) {
  const entries = fs.existsSync(dir) ? fs.readdirSync(dir) : [];
  const files = entries
    .filter((f) => f.toLowerCase().endsWith('.json'))
    .map((f) => path.join(dir, f))
    .sort();

  const prompts = [];
  const responses = [];
  const promptIds = new Set();
  const responseIds = new Set();

  for (const file of files) {
    let data;
    try {
      data = JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch (e) {
      throw new Error(`failed to parse deck ${file}: ${e.message}`);
    }
    if (Array.isArray(data.prompts)) {
      for (const p of data.prompts) {
        if (!p || typeof p.id !== 'string' || typeof p.text !== 'string') {
          throw new Error(`bad prompt in ${file}: ${JSON.stringify(p)}`);
        }
        if (promptIds.has(p.id)) continue;
        promptIds.add(p.id);
        prompts.push({
          id: p.id,
          text: p.text,
          blanks: Number(p.blanks) || 1,
          tags: Array.isArray(p.tags) ? p.tags : [],
        });
      }
    }
    if (Array.isArray(data.responses)) {
      for (const r of data.responses) {
        if (!r || typeof r.id !== 'string' || typeof r.text !== 'string') {
          throw new Error(`bad response in ${file}: ${JSON.stringify(r)}`);
        }
        if (responseIds.has(r.id)) continue;
        responseIds.add(r.id);
        responses.push({
          id: r.id,
          text: r.text,
          tags: Array.isArray(r.tags) ? r.tags : [],
        });
      }
    }
  }

  return { prompts, responses };
}

/**
 * Build a per-room Deck over the given content. `random` is the random
 * source (typically `services.random`) — all shuffles use it so tests can
 * seed deterministically.
 *
 * @returns {{
 *   drawPrompt:      () => PromptCard | null,
 *   drawResponse:    () => ResponseCard | null,
 *   discardPrompt:   (card) => void,
 *   discardResponse: (card) => void,
 *   responseTextIndex: () => Map<string, string>,
 *   _stats: () => { promptPool:number, responsePool:number, promptDiscard:number, responseDiscard:number },
 * }}
 */
function createDeck({ prompts, responses, random }) {
  const rnd = random || Math.random;
  // Keep a permanent lookup so the game can resolve any cardId back to text
  // even after the card has been discarded — needed for ROUND_WINNER and
  // late-joiner catch-up.
  const responseText = new Map(responses.map((r) => [r.id, r.text]));

  let promptPool   = shuffleCopy(prompts, rnd);
  let responsePool = shuffleCopy(responses, rnd);
  const promptDiscard = [];
  const responseDiscard = [];

  function drawPrompt() {
    if (promptPool.length === 0) {
      if (promptDiscard.length === 0) return null;
      promptPool = shuffleCopy(promptDiscard, rnd);
      promptDiscard.length = 0;
    }
    return promptPool.pop();
  }

  function drawResponse() {
    if (responsePool.length === 0) {
      if (responseDiscard.length === 0) return null;
      responsePool = shuffleCopy(responseDiscard, rnd);
      responseDiscard.length = 0;
    }
    return responsePool.pop();
  }

  function discardPrompt(card)   { if (card) promptDiscard.push(card); }
  function discardResponse(card) { if (card) responseDiscard.push(card); }

  function responseTextIndex() { return responseText; }

  function _stats() {
    return {
      promptPool: promptPool.length,
      responsePool: responsePool.length,
      promptDiscard: promptDiscard.length,
      responseDiscard: responseDiscard.length,
    };
  }

  return { drawPrompt, drawResponse, discardPrompt, discardResponse, responseTextIndex, _stats };
}

function shuffleCopy(arr, rnd) {
  const out = arr.slice();
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

module.exports = { loadDeckContent, createDeck };
