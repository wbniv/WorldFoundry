# Party Games Platform

Chromecast-based couch party game platform. Individual games plug into a shared shell:
relay server (Node.js + `ws`) + receiver (HTML page running on a Chromecast or browser)
+ controller (HTML page running on each player's phone).

**Current state: Phase 5 — three games plug into a real per-game client-asset seam.**
Reaction, image, and Worst Take Wins (fill-in-the-blank card game) all run against a
shared shell that dynamically loads `games/<WF_GAME>/client/{controller,receiver}.js`.
Physical Cast device verification for the two reaction-family games is pending
Cast Console propagation (Phase 1d).

## Run locally

**Prerequisites:** Node.js LTS via `fnm` — see [Prerequisites in the phase-1 plan](../docs/plans/2026-04-22-party-games-platform-phase-1.md#prerequisites).

```sh
cd platform/server
npm install
node index.js
```

Server logs `party-games platform ready on http://localhost:8080` and `game plugin: reaction`.

Open three browser tabs:

1. **Receiver** first — <http://localhost:8080/receiver>. The page picks a 4-letter room
   code and displays it in the header (e.g. `HTKM`). Copy that.
2. **Host controller** — <http://localhost:8080/controller?name=Alice&room=HTKM>
3. **Second controller** — <http://localhost:8080/controller?name=Bob&room=HTKM>

Controllers without `?room=…` get a prompt asking for the code the receiver's displaying.
Multiple rooms can run side-by-side on the same server — `…/controller?room=AAAA` and
`…/controller?room=BBBB` land in separate isolated rooms.

Alice is the host (first to connect in her room). Click **START** on her tab; the receiver shows a
countdown bar, then a giant **GO!** The first controller to tap wins 4 pts; next 3, etc.
Early presses get locked out for that round (0 pts). First to 10 pts wins.

## Environment

- `WF_GAME=reaction` (default) — load mini-game 1 (countdown timer).
- `WF_GAME=image` — load mini-game 2 (image recognition).
- `WF_GAME=worst-take-wins` — load mini-game 3 (fill-in-the-blank card game).
- `WF_GAME=none` — run the bare platform (PING → PONG echo only, no game logic).
- `PORT=8080` (default) — HTTP + ws listen port.

### Image-recognition game (`WF_GAME=image`)

Target emoji shown for 3 s ("memorise this"); then a stream of 4–8 distractor
emoji cycles (800 ms each); then the target reappears and the scoring window
opens. First to tap the big button after the target shows wins 4 pts. Presses
before the target → lockout. Same scoring / win condition as the reaction game.

### Worst Take Wins (`WF_GAME=worst-take-wins`)

Fill-in-the-blank card game for 3–10 players. Each round one player is the
Judge; others pick one card from their private 7-card hand to complete a
Prompt card. Judge advances through submissions one at a time on their phone
then taps the winner. First to 8 prompt cards wins. Ships the Cards Against
Humanity base deck (279 prompts, 1270 responses; CC BY-NC-SA 2.0) — see
`games/worst-take-wins/assets/decks/NOTICE.md` for licensing. Drop custom
JSON decks into that directory to add content.

## Tests

```sh
# Platform relay (15) + shell-template (10) + reaction / image / WTW integration (6)
cd party-games/platform/server && npm test

# Reaction-game state machine (15, isolated)
cd party-games/games/reaction && npm test

# Image-game state machine (22, isolated)
cd party-games/games/image && npm test

# Worst Take Wins state machine + deck loader (30, isolated)
cd party-games/games/worst-take-wins && npm test
```

All 98 tests use the built-in `node:test` runner; no Jest / mocha dependency. Server
tests spin up isolated instances on ephemeral ports with an injected fake clock so
all the various timing windows fire instantly.

## Repo structure

```
party-games/
  platform/
    server/              — Node http + ws relay (rooms by 4-letter code)
      createServer.js      — factory; accepts { port, gameFactory, gameName, gamesRoot, ... }
      index.js             — entry; loads games/<WF_GAME>/<WF_GAME>.js at boot
      test/*.test.js       — node:test suite (relay protocol + shell templating + per-game integration)
    receiver-shell/      — TV page — platform-only shell that dynamically loads
                           the active game's receiver module from /game/client/receiver.js
    controller-shell/    — Phone page — platform-only shell that dynamically loads
                           the active game's controller module from /game/client/controller.js
    shell-lib/           — Shared helpers for game clients (served under /shell-lib/)
      scoreboard.js        — renderScoreboard / renderFinalScoreboard (used by reaction + image)
  games/
    reaction/            — mini-game 1: countdown timer (4/3/2/1 pts, first to 10)
      reaction.js          — state machine, plugs into createServer
      client/              — per-game DOM modules loaded by the shells
        controller.js + .css
        receiver.js   + .css
      test/*.test.js
    image/               — mini-game 2: target-emoji recognition (same scoring)
      image.js
      client/
      test/*.test.js
    worst-take-wins/     — mini-game 3: fill-in-the-blank card game
      worst-take-wins.js   — state machine (LOBBY → SHOW_PROMPT → JUDGE_REVEAL → SCORE → GAME_OVER)
      deckLoader.js        — JSON deck glob + per-room shuffled Deck
      client/              — controller (hand strip / judge pick) + receiver (prompt board)
      assets/decks/        — JSON deck files (CAH base + NOTICE.md)
      test/*.test.js
```

## Plugin interface (for new games)

### Server-side plugin

Games implement the `gameFactory` option passed to `createServer({ gameFactory, gameName, ... })`:

```js
const game = {
  name: 'my-game',
  onJoin(player, services)           { /* optional — fresh player arrived */ },
  onReconnect(player, services)      { /* optional — session-resumed player (see below) */ },
  onLeave(player, services)          { /* optional — grace expired or sessionless drop */ },
  onMessage(player, msg, services)   { /* handle non-platform messages */ },
};
```

Where `services` = `{ broadcast(msg), sendTo(playerId, msg), getPlayers(), getHost(), now(), schedule(delayMs, fn) → cancel-fn, random() }`.

Platform messages `HELLO`, `PING`, `STATE`, `WELCOME`, `WELCOME_RECEIVER`, `PONG`,
`NEED_ROOM`, `BAD_ROOM` are reserved; games use distinct type names. `services.sendTo`
is the only way to deliver private-per-player data (e.g. card hands) — the server
filters to one recipient, so other players and receivers never see it.

#### Session-grace reconnect

When a controller sends `HELLO` with a `sessionId` (string matching `/^[A-Za-z0-9_-]{8,64}$/`),
the server remembers that id → playerId mapping. If the WebSocket drops, the player's
slot (id, name, scores, any mid-round state the game is holding) stays alive for
**`SESSION_GRACE_MS` = 20 s**. A reconnect `HELLO` with the same sessionId within
that window resumes the slot — `onReconnect` fires instead of `onJoin`, and the
`WELCOME` response carries `resumed: true`. Grace expiry calls `onLeave` normally.

Games that don't implement `onReconnect` are fine — the hook is optional, and a
bare resume is indistinguishable from "nothing happened" to a game that doesn't
care. Games that hold per-player private state (hands, private reveals) should
implement it to re-broadcast that state via `services.sendTo` so the returning
controller re-renders immediately.

`onJoin` vs `onReconnect` cheat sheet:

| Hook          | Scores / state | Catch-up broadcast          |
|---------------|----------------|-----------------------------|
| `onJoin`      | Initialise     | Fresh-joiner state (maybe empty hand) |
| `onReconnect` | Preserve       | Restore real in-flight state (real hand, current reveal, etc.) |

The shell controller (platform/controller-shell/controller.js) generates a
sessionId on first load (base64url, `crypto.getRandomValues`), persists it
in `sessionStorage`, and sends it on every `HELLO`. A browser refresh reuses
the id and resumes the slot; closing the tab drops the sessionStorage and
a fresh tab gets a new id (a user who walked away shouldn't keep holding
the seat).

### Client-side modules

Each game ships ES modules at `games/<name>/client/controller.js` and
`games/<name>/client/receiver.js`, each exporting:

```js
export function mount(ctx)   { /* build DOM inside ctx.root */ }
export function unmount()    { /* cleanup on reconnect */ }
```

`ctx` surface (shell → game):

```
{
  root:      HTMLElement,                  // <div id="game-root">
  send:      (msg) => void,                // WS send wrapper
  on:        (type, handler) => unsubscribe, // subscribe to server messages
  playerId:  number | null,                // set on controller after WELCOME
  isHost:    () => boolean,                // controller only
  players:   () => Array<{id,name}>,       // roster mirror
  hostId:    () => number | null,          // receiver only
  feedback:  { press, lockout, win, lose, roundStart },   // controller only
  assetUrl:  (name) => string,             // '/game/assets/' + name
  log:       (s) => void,                  // receiver-side event log (no-op on controller)
}
```

Optional CSS at `games/<name>/client/{controller,receiver}.css` is loaded by
the shell if present (link tag is omitted otherwise). Asset files can live
under `games/<name>/client/assets/` and are served from `/game/assets/`.

## Phase plan

See [../docs/plans/2026-04-22-party-games-platform-phase-1.md](../docs/plans/2026-04-22-party-games-platform-phase-1.md) for the full sub-phase plan (Phase 1a–1d platform, 2a–2b reaction, 3+ polish/cards/AWS).

## Design references

- [reaction game](../docs/reference/2026-04-14-party-game.md) — first game consumer; mini-game 1 landed in Phase 2a.
- [card games](../docs/reference/2026-04-14-party-game-cards.md) — queued as Phase 5+ after reaction is solid and platform features (rooms, reconnect) land.
