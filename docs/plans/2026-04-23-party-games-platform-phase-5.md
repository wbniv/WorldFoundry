# Phase 5 — Worst Take Wins + Shell Plugin Seam

**Date:** 2026-04-23. **Status:** shipped. See §Status for what actually landed.

## Context

Phase 5 was scoped in the parent plan as "scaffold the cards game plugin" — a third game whose job was to check whether `createServer({ game })` actually generalizes, or only fits the reaction family. Exploration confirmed the answer has two halves:

- **Server contract**: generalizes cleanly. `services.sendTo` handles private per-player state (card hands); `schedule` / `random` / `now` are already injected for testability; no leaks into platform internals from `games/reaction/` or `games/image/`.
- **Client shells**: do **not** generalize. `platform/controller-shell/controller.js` and `platform/receiver-shell/receiver.js` have reaction+image assumptions hardcoded (phase tables, panel registry, single-button UI, confetti, scoreboards). A third game today means editing the shells with a third set of hardcoded cases — which is not a platform, it's a switch statement.

Phase 5 therefore became three bundled pieces: (A) build a real per-game client-asset plugin seam, (B) retrofit reaction and image onto it, (C) land Worst Take Wins — a fill-in-the-blank card game (Cards Against Humanity model) — as the first native citizen of the new seam, with its own server state machine, private hands, judge rotation, and the CAH CC BY-NC-SA 2.0 JSON deck wired in.

Chosen name: **Worst Take Wins** (working title in `docs/reference/2026-04-14-party-game-cards.md`). Not "Cards Against Humanity" — CAH content is licensed under CC BY-NC-SA 2.0 so reusing the cards is fine for a non-commercial build, but the product name isn't.

## Scope

**In:**
- Per-game client-asset plugin seam (server + shell HTML template + module contract).
- Retrofit `games/reaction/` and `games/image/` onto the seam (extract game-specific UI out of the shells).
- `games/worst-take-wins/` server plugin: state machine, deck loader, scoring, judge rotation.
- `games/worst-take-wins/client/` phone + TV UI (hand display, prompt board, judge reveal, scoreboard).
- CAH base deck wired in from `crhallberg/JSON-against-humanity` with attribution.
- Tests mirroring reaction/image parity (+deck loader, +shell templating, +WTW integration).

**Out (flagged as follow-ups):**
- Runtime game switching / in-lobby game picker — each process still runs one game via `WF_GAME`.
- Family-mode deck filter (tag-based card exclusion) — deck loader keeps `tags` fields but no filter UI.
- Pick-2 prompt handling end-to-end — server supports it; client UI ships pick-1 only (pick-2 prompts skipped at draw).
- Spectator mode, reconnect-mid-round hand restore.

## Part A — Shell plugin seam

### Loading mechanism

Server templates the shell HTML at request time. `GET /controller` and `GET /receiver` became non-static: they read the shell HTML, substitute placeholders, send the result.

Placeholders in `platform/controller-shell/index.html` + `platform/receiver-shell/index.html`:

- `{{GAME_NAME}}` → the `WF_GAME` string (emitted as `<meta name="game-name" content="…">`).
- `{{GAME_STYLESHEET}}` → `<link rel="stylesheet" href="/game/client/controller.css">` (or `receiver.css`). Omitted when the per-game CSS file is absent.

(Original plan also had `{{GAME_SCRIPT}}`; shipped design uses dynamic `import()` from the shell JS instead, so only the stylesheet + meta placeholders remain in HTML.)

Static resolver in `createServer.js` grew two new prefixes resolved against a new `gamesRoot`:

- `/game/client/*` → `<gamesRoot>/${WF_GAME}/client/*`
- `/game/assets/*` → `<gamesRoot>/${WF_GAME}/client/assets/*`

Each applies its own path-traversal guard anchored at `gamesRoot` (not `staticRoot`). The original single-root guard is now three independent guards (`staticRoot`, `gamesRoot`, and `shell-lib` root — see mid-flight amendment below).

### Changes to `createServer({ ... })` options

Added `gameName` (string) and `gamesRoot` (path; defaults to `<repo>/party-games/games`). `index.js` passes `GAME_NAME` through. Internally `createServer` uses `gameName` for the HTML template substitution and the `/game/*` static prefix. `WF_GAME=none` still works — placeholders collapse to empty strings.

### Shell ↔ game client API

Shell keeps: WebSocket connect + reconnect, HELLO/WELCOME handshake, room code + QR, name entry, host tracking via `hostId`, PING/PONG, Cast Sender boot (controller) / CAF boot (receiver), player-list state, visibilitychange reconnect, AudioContext gesture unlock.

Game client module (ES module) exports:

```js
export function mount(ctx) { /* build DOM inside ctx.root, subscribe via ctx.on */ }
export function unmount() { /* cleanup — called on reconnect before re-mount */ }
```

`ctx` (controller-side; receiver differs slightly — see below):

```
{
  root:       HTMLElement,                           // <div id="game-root">
  send:       (msg) => void,                         // WS send wrapper; no-op if closed
  on:         (type, handler) => unsubscribe,        // subscribe to server messages
  playerId:   number | null,                         // set after WELCOME
  isHost:     () => boolean,                         // recomputed from latest hostId
  players:    () => Array<{id, name}>,
  feedback:   { press, lockout, win, lose, roundStart },  // haptic/audio helpers
  assetUrl:   (name) => string,                      // '/game/assets/' + name
  ensureAudio: () => AudioContext | null,            // force-unlock on custom gesture
  log:        (s) => void,                           // no-op on controller
}
```

Receiver `ctx` has `hostId: () => number | null` (instead of `isHost`), no-op `feedback`, functional `log`, and always returns `null` from `playerId`.

Shell calls `mount()` after WELCOME / WELCOME_RECEIVER and `unmount()` on reconnect before re-mounting. Shell inserts a single `<div id="game-root">` and the game owns everything inside.

### Error handling

Startup: if `WF_GAME` is set but `games/<name>/client/controller.js` doesn't exist, shell logs a warning and renders a "game UI missing for 'X'" fallback inside `#game-root` rather than a silent blank.

## Part B — Retrofit reaction + image

Moved out of `platform/controller-shell/controller.js` into game clients:

- `refreshButton` phase table, BUTTON_PRESS dispatch, `START_GAME` / `NEW_GAME` click handlers, PHASE / EARLY_PRESS / GAME_OVER / ROUND_ENDED handlers, outcome overlay, confetti, `showOutcome` / `hideOutcome` / `spawnConfetti`.

Stayed in the shell: `feedbackPress/Lockout/Win/Lose/RoundStart` audio+haptic helpers (exposed via `ctx.feedback`).

Moved out of `platform/receiver-shell/receiver.js`:

- Panels map, `showPanel`, ROUND_COUNTDOWN / TIMER_FIRED / ROUND_REVEAL / SHOW_IMAGE / PRESS_RECORDED / ROUND_ENDED / GAME_OVER / EARLY_PRESS / LAST_STANDING handlers, commit indicator, scoreboard rendering, countdown+reveal bar animation.

Split: **reaction** owns `countdown`, `open`, `ended`, `gameover`, commit indicator, countdown bar. **image** owns `reveal`, `play` (distractors), reveal bar, image-flash CSS. Scoreboard rendering moved to `platform/shell-lib/scoreboard.js`, consumed by all three games.

Retrofit kept every existing test green. Platform integration tests (`platform/server/test/reaction-integration.test.js` + `image-integration.test.js`) were the safety net.

## Part C — Worst Take Wins server plugin

Location: `games/worst-take-wins/worst-take-wins.js` — factory `createWorstTakeWinsGame(opts)`. Mirrors the reaction/image shape exactly (same `{ name, onJoin, onLeave, onMessage, _debugState }` exports; same `services` usage).

### State machine

```
LOBBY
  └─ START_GAME (host) ──→ SHOW_PROMPT
        └─ all non-judge players submit ──→ JUDGE_REVEAL
              └─ judge taps submissions (advance one at a time)
                    └─ JUDGE_PICK ──→ SCORE
                          ├─ winner reaches winScore ──→ GAME_OVER
                          └─ otherwise ──→ (next round, rotate judge) → SHOW_PROMPT
```

(Original plan had a separate DEAL phase; shipped implementation folds dealing into the SHOW_PROMPT transition — hands are topped up before the prompt broadcasts.)

### Messages

**Incoming (controller → server):**
- `START_GAME` (host-gated) — begin game
- `SUBMIT_CARDS { cardIds[] }` — non-judge only; exactly `blanks` cards
- `JUDGE_ADVANCE` — judge only; next submission reveal
- `JUDGE_PICK { submissionId }` — judge only; winner
- `NEW_GAME` (host-gated) — reset after GAME_OVER

**Outgoing (server → clients):**
- `PHASE { phase, judgeId, scores, round }` — broadcast on every transition
- `DEAL_HAND { cards: [{id,text}] }` — **private via `sendTo`** — per-player hand
- `SHOW_PROMPT { prompt: {id,text,blanks}, round, judgeId }` — broadcast
- `SUBMISSION_COUNT { submitted, total }` — broadcast after each SUBMIT_CARDS
- `JUDGE_REVEAL_START { submissions: [{submissionId, cardIds, cards}], prompt }` — broadcast; shuffled; **no playerId**
- `REVEAL_NEXT { submissionIndex }` — broadcast
- `ROUND_WINNER { playerId, name, submissionId, cardIds, cards, promptCard }` — broadcast with attribution
- `SCORE_UPDATE { scores }` — broadcast
- `GAME_WINNER { playerId, name, scores }` — broadcast
- `ERROR { code, message }` — private, surfaced on invalid host actions (e.g. `NOT_ENOUGH_PLAYERS`)

### Anonymity invariant

Server-stored submission is `{ submissionId, playerId, cardIds[], auto }`. `JUDGE_REVEAL_START` strips `playerId`. Only `ROUND_WINNER` reintroduces it. No code path sends another player's hand anywhere. Integration test asserts the receiver never sees a DEAL_HAND and non-judge players never see the judge's reveal with player attribution.

### Key decisions

- Hand size: **7**.
- Win score: default **8** prompt cards (configurable via `opts.winScore`).
- Submit timeout: default **90 s**, configurable; auto-submit a random card from hand, mark `auto: true` in state.
- Judge rotation: round-robin over current roster (stable by `id`).
- Min players: **3**. `START_GAME` below threshold sends `ERROR { code: 'NOT_ENOUGH_PLAYERS' }` privately and stays in LOBBY.
- Mid-round leaves: judge leaves → abort round, schedule next round immediately. Submitter leaves pre-submit → decrement expected total; if everyone else has submitted, advance to JUDGE_REVEAL. Submitter leaves post-submit → submission stays. Fall below `minPlayers` → fold back to LOBBY.
- Pick-2 prompts: server handles them; client v1 doesn't, so `opts.allowPick2` defaults `false` and the draw loop skips `blanks>1` prompts.

## Part D — Deck loader + CAH content

Location: `games/worst-take-wins/deckLoader.js`. `loadDeckContent(dir)` globs every `.json` file in the directory (sorted, first-occurrence wins for duplicate ids), returns `{ prompts, responses }`. `createDeck({ prompts, responses, random })` builds a per-room Deck with `drawPrompt` / `drawResponse` / `discardPrompt` / `discardResponse` / `responseTextIndex()`, Fisher-Yates shuffle using the supplied `random`. Pool drained → reshuffle from discard.

### JSON format

```json
{
  "name": "CAH Base Set",
  "license": "CC BY-NC-SA 2.0",
  "attribution": "Cards Against Humanity LLC — via crhallberg/JSON-against-humanity",
  "source": "…",
  "prompts":   [ { "id": "p00001", "text": "…____…", "blanks": 1, "tags": [] } ],
  "responses": [ { "id": "r00001", "text": "…",                  "tags": [] } ]
}
```

### CAH content (shipped)

Pulled `cah-all-compact.json` from `crhallberg/JSON-against-humanity` (branch `latest`), selected the "CAH Base Set" pack, transformed to this project's format (id stable per-index: `p{NNNNN}` / `r{NNNNN}`; blank marker `_` normalised to `____`). Final counts: **279 prompts**, **1270 responses**, **~105 KB**.

Files:
- `games/worst-take-wins/assets/decks/cah-base.json` — the deck.
- `games/worst-take-wins/assets/decks/NOTICE.md` — CC BY-NC-SA 2.0 notice, source pointer, format notes.

Repo-level attribution added to `party-games/README.md` under §Worst Take Wins.

Hot-reload not implemented; the content cache is populated on first game-start and reused across rooms.

### Discard / reshuffle

Drawn cards go to an in-memory discard pile when consumed (prompt at `ROUND_WINNER`; response on submission). Pool drains → shuffle the discard back in. Permanent `responseTextIndex` Map keyed at deck construction so any cardId can be resolved to text even after discard (needed for `ROUND_WINNER` and late-joiner catch-up).

## Part E — Client UI for Worst Take Wins

### Controller (phone)

Location: `games/worst-take-wins/client/controller.{js,css}`.

- **LOBBY**: host sees "X players in · need 3" + START (enabled at ≥3); others see "waiting for host to start".
- **SHOW_PROMPT (non-judge)**: scoreboard strip + prompt card + horizontal card hand (tap-to-select, visual selected state with border + lift); SUBMIT button enabled when `blanks`-many cards selected.
- **SHOW_PROMPT (judge)**: "you are judging this round" + prompt + submission counter.
- **JUDGE_REVEAL (non-judge)**: "judge is reading submissions…" + remaining count.
- **JUDGE_REVEAL (judge)**: one submission displayed at a time with Next →; final screen lists all submissions as tappable tiles.
- **SCORE**: splash "X wins the round!" + prompt + submitted card.
- **GAME_OVER**: final scoreboard with winner highlighted; host sees NEW GAME.

Tap-to-select with re-tap to deselect. For pick-1 prompts, tapping a second card replaces the selection (no extra gesture needed to change your mind).

### Receiver (TV)

Location: `games/worst-take-wins/client/receiver.{js,css}`.

- **LOBBY**: room code + QR (shell-provided via header) + player list + host indicator + hint.
- **SHOW_PROMPT**: "Round N · Judge: X" + big prompt card + "X / N submitted".
- **JUDGE_REVEAL**: prompt + current submission full-bleed + "N more remaining".
- **SCORE**: winner headline + completed strip (prompt + winning response cards).
- **GAME_OVER**: "GAME OVER" label + winner callout + final scoreboard (trophy on the winner).

Score-strip bar renders on every phase with live scores + judge indicator (⚖︎) next to the current judge.

## Part F — Tests

Actual counts shipped: reaction 15 (baseline), image 22 (baseline), platform 31 (was 19; +10 shell-template + +2 WTW integration), **worst-take-wins 30** (20 game state machine + 10 deck loader). Total: **98** tests, all green.

### Unit tests shipped

- `games/worst-take-wins/test/worst-take-wins.test.js` — 20 tests covering LOBBY entry, min-players rejection with ERROR surfaced, private DEAL_HAND (via `sendTo` spy), unique cards across hands, SUBMIT_CARDS validation (wrong count, not-in-hand, judge blocked, double-submit ignored), JUDGE_REVEAL_START anonymity invariant, judge-only JUDGE_ADVANCE, judge-only JUDGE_PICK + ROUND_WINNER, judge rotation, winScore → GAME_OVER flow, NEW_GAME reset, auto-submit timeout, mid-round judge leave, submitter leave pre-submit, fold-to-LOBBY on depopulation, mid-game join catch-up, pick-2 prompt skipping.
- `games/worst-take-wins/test/deck.test.js` — 10 tests: single file load, multi-file merge + dedupe, malformed JSON error message, empty dir, draw-to-exhaustion, reshuffle-from-discard, seeded determinism, `responseTextIndex` survives discard.

### Integration tests shipped

- `platform/server/test/worst-take-wins-integration.test.js` — 2 tests: full 3-player round (join, deal, submit, judge pick, score increment; receiver never gets DEAL_HAND); `START_GAME` with 2 players surfaces `ERROR: NOT_ENOUGH_PLAYERS` privately to the host.
- `platform/server/test/shell-template.test.js` — 10 tests: HTML `meta game-name` + `game-root` + stylesheet link present; placeholder collapses to empty when no game; stylesheet omitted when per-game CSS file absent; `/game/client/*` serves under active game; `/game/client/<missing>` 404 with helpful message; `/game/*` path-traversal 403; `/game/*` with no active game 404s with clear message; `/shell-lib/*` serves; `/shell-lib/*` path-traversal 403.

### Client unit tests (not shipped)

The original plan proposed jsdom-based smoke tests for each game's client module. Deferred — the integration + shell-template tests cover the seam end-to-end, and client DOM rendering is verified by the live browser click-through (see §Verification).

## Status (shipped 2026-04-23)

All nine sequencing steps completed:

1. ✅ Seam scaffolding: `/game/*` + `/shell-lib/*` routes, `gamesRoot`, HTML templating, `gameName` option. Shell serves `<div id="game-root">` + dynamically imports the game module.
2. ✅ Retrofit reaction → `games/reaction/client/`.
3. ✅ Retrofit image → `games/image/client/`.
4. ✅ Worst Take Wins server plugin + 20 unit tests.
5. ✅ Deck loader + CAH JSON import + 10 deck tests + NOTICE.md.
6. ✅ Worst Take Wins controller UI.
7. ✅ Worst Take Wins receiver UI.
8. ✅ Integration + shell-template tests (12 new tests in `platform/server/test/`). **Live browser click-through still owed** — see §Verification.
9. ✅ Docs: `party-games/README.md` updated (plugin interface now documents the `client/` contract + CAH attribution); `docs/plans/2026-04-22-party-games-platform-phase-1.md` has a Phase 5 completion section appended.

## Mid-flight amendments (discovered while building)

- **`/shell-lib/*` HTTP route added** on top of `/game/*`. Game client modules served from `/game/client/receiver.js` can't import a path outside their origin, so shared helpers (`scoreboard.js`) needed a dedicated path. Added `/shell-lib/<path>` → `<staticRoot>/shell-lib/<path>` in `createServer.js` with its own path-traversal guard. Games import via `import { renderScoreboard } from '/shell-lib/scoreboard.js'`.
- **Shell → game message passing is permissive**, not filtered. The shell passes every message type (including `STATE`, `WELCOME`, `PONG`) through `gameSubscribers`. Games subscribe deliberately via `ctx.on('STATE', …)` if they want them — avoids the shell needing to know which platform-reserved types remain useful to a game (e.g. STATE's `hostId` drives the reaction controller's START button skinning).
- **`ctx.hostId()`** added to the receiver `ctx` (not in original plan). Receivers want to decorate the lobby list with the host indicator; without it each game would reconstruct from STATE itself. Kept as a function (not a property) to mirror `ctx.isHost()` on the controller.
- **`ctx.ensureAudio()`** on the controller so a game can force-unlock the AudioContext on a specific gesture (the shell-level click listener handles the default case).
- **`GAME_SCRIPT` placeholder dropped**; the shell dynamic-imports the game module instead. Simpler HTML, one fewer round-trip, and keeps the shell in charge of module lifecycle (mount/unmount on reconnect).
- **index.js factory-name bug** — kebab-to-PascalCase conversion. Original was `GAME_NAME[0].toUpperCase() + GAME_NAME.slice(1)` which produced `createWorst-take-winsGame`. Fixed to split-and-join: `GAME_NAME.split('-').map((s) => s[0].toUpperCase() + s.slice(1)).join('')`.
- **Shell CSS cleanup deferred.** `platform/controller-shell/controller.css` still has reaction-era `.big-button`, `.outcome`, `.confetti` rules (unused by the stripped shell HTML). Harmless dead rules; listed in §Follow-ups.
- **Client unit tests deferred** — the integration + shell-template tests cover the seam, and a live browser run is the final gate. If a regression lands that could've been caught by jsdom tests, they become worth writing.
- **Shipped deck size: 105 KB**, not the ~500 KB estimated in the original plan. The CAH base pack is smaller than the full aggregate dump.

## Critical files

Created:
- `party-games/games/worst-take-wins/worst-take-wins.js`
- `party-games/games/worst-take-wins/deckLoader.js`
- `party-games/games/worst-take-wins/package.json`
- `party-games/games/worst-take-wins/client/controller.js` + `.css`
- `party-games/games/worst-take-wins/client/receiver.js` + `.css`
- `party-games/games/worst-take-wins/assets/decks/cah-base.json`
- `party-games/games/worst-take-wins/assets/decks/NOTICE.md`
- `party-games/games/worst-take-wins/test/worst-take-wins.test.js`
- `party-games/games/worst-take-wins/test/deck.test.js`
- `party-games/games/reaction/client/controller.{js,css}` + `receiver.{js,css}`
- `party-games/games/image/client/controller.{js,css}` + `receiver.{js,css}`
- `party-games/platform/shell-lib/scoreboard.js`
- `party-games/platform/server/test/shell-template.test.js`
- `party-games/platform/server/test/worst-take-wins-integration.test.js`

Modified:
- `party-games/platform/server/createServer.js` — `gameName`+`gamesRoot` options; dual-root resolver; template-at-request for `/controller` + `/receiver`; path-traversal guards for `/game/*` and `/shell-lib/*`.
- `party-games/platform/server/index.js` — kebab-to-PascalCase factory-name, pass `gameName` through.
- `party-games/platform/controller-shell/index.html` + `controller.js` + `controller.css` — placeholders + `<div id="game-root">`; shell is now an ES module with dynamic import of the game module; game-specific DOM/CSS stripped.
- `party-games/platform/receiver-shell/index.html` + `receiver.js` + `receiver.css` — same treatment.
- `party-games/games/reaction/reaction.js` — untouched (server logic stayed).
- `party-games/games/image/image.js` — untouched.
- `party-games/README.md` — plugin interface section rewritten with the full `ctx` contract + CAH attribution.
- `docs/plans/2026-04-22-party-games-platform-phase-1.md` — Phase 5 completion notes appended.

Reused:
- `services` surface (`platform/server/createServer.js`) — unchanged.
- `node:test` + `node:assert/strict` — pattern from `games/reaction/test/reaction.test.js` + `games/image/test/image.test.js`.
- `makeServices` test-double pattern — extended with a `sendTo` spy for WTW's private-hand assertions.
- Integration harness at `platform/server/test/reaction-integration.test.js` — mirrored for WTW.

## Verification

1. `cd party-games/platform/server && WF_GAME=worst-take-wins node index.js`.
2. Open the receiver at `http://localhost:8080/receiver`; confirm room code appears.
3. Open three controller tabs at the URL shown; join with Alice / Bob / Carol.
4. Alice (host) taps START; verify each phone receives 7 unique cards, no phone sees another's hand (visual sanity + the private-hands unit test is the authoritative guarantee).
5. Judge sees "you are judging"; others submit; counter advances.
6. Judge advances through submissions on phone; TV mirrors. Judge picks winner; scoreboard updates.
7. Play to 8 points; GAME_OVER fires; NEW GAME works.
8. `WF_GAME=reaction node index.js` + `WF_GAME=image node index.js` — play one round each to confirm retrofit.
9. Run all tests: `(cd games/reaction && npm test) && (cd games/image && npm test) && (cd games/worst-take-wins && npm test) && (cd platform/server && npm test)`. Should report 15 + 22 + 30 + 31 = **98 green**.

Steps 1, 9 done. Steps 2-8 (live browser click-through) still owed — server-side is covered by unit + integration tests; DOM rendering is syntax-verified only.

## Risks & flagged trade-offs

1. **No runtime game switching.** `WF_GAME` stays env-scoped per process. If a lobby later picks the game, shell template needs per-request or per-room game identity; the `/game/*` path either becomes room-scoped or takes a query param. Cheap to add later; flagged so assumptions are explicit.
2. **ES modules vs classic scripts.** Game client modules are `type="module"`. No hidden global side effects surfaced during retrofit; if they do later, fallback is classic scripts + `window.PartyGame = { mount, unmount }` convention.
3. **Shared scoreboard in `shell-lib/`** vs duplication: the lib is a middle path. If it starts growing per-game branches, duplicate instead — don't let "platform" become a grab bag of game code.
4. **Pick-2 prompts in v1 client.** Server handles them; client punts (filter-to-pick-1 at draw time). The ref doc's "pick-2 tests strategic interest" flavour is lost until a follow-up.
5. **CAH content commit size.** 105 KB JSON committed to the repo (lighter than the 500 KB estimated). Accepted.
6. **Retrofit regression risk for Phase 1d.** Shell refactor touches code that is ground-truth for the physical Chromecast test (still blocked on Cast Console propagation). Landing this while 1d is unverified could confuse debugging if propagation completes mid-refactor. Last-known-good commit on this branch before Phase 5 work: `d3ff4e4` (`party-games: plan — expand post-first-commit grace timer note`). If Phase 1d tests come back red, bisect from there to determine whether the refactor or Cast propagation is at fault.
