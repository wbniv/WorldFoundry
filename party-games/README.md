# Party Games Platform

Chromecast-based couch party game platform. Individual games plug into a shared shell:
relay server (Node.js + `ws`) + receiver (HTML page running on a Chromecast or browser)
+ controller (HTML page running on each player's phone).

**Current state: Phase 2a — reaction game (mini-game 1) playable end-to-end in browser.**
Physical Cast device verification is pending device-serial registration (Phase 1b last step).

## Run locally

**Prerequisites:** Node.js LTS via `fnm` — see [Prerequisites in the phase-1 plan](../docs/plans/2026-04-22-party-games-platform-phase-1.md#prerequisites).

```sh
cd platform/server
npm install
node index.js
```

Server logs `party-games platform ready on http://localhost:8080` and `game plugin: reaction`.

Open three browser tabs:

- Receiver: <http://localhost:8080/receiver>
- Host controller: <http://localhost:8080/controller?name=Alice>
- Second controller: <http://localhost:8080/controller?name=Bob>

Alice is the host (first to connect). Click **START** on her tab; the receiver shows a
countdown bar, then a giant **GO!** The first controller to tap wins 4 pts; next 3, etc.
Early presses get locked out for that round (0 pts). First to 10 pts wins.

## Environment

- `WF_GAME=reaction` (default) — load mini-game 1 (countdown timer).
- `WF_GAME=image` — load mini-game 2 (image recognition).
- `WF_GAME=none` — run the bare platform (PING → PONG echo only, no game logic).
- `PORT=8080` (default) — HTTP + ws listen port.

### Image-recognition game (`WF_GAME=image`)

Target emoji shown for 3 s ("memorise this"); then a stream of 4–8 distractor
emoji cycles (800 ms each); then the target reappears and the scoring window
opens. First to tap the big button after the target shows wins 4 pts. Presses
before the target → lockout. Same scoring / win condition as the reaction game.

## Tests

```sh
# Platform relay (11) + reaction-integration (2) + image-integration (2)
cd party-games/platform/server && npm test

# Reaction-game state machine (13, isolated)
cd party-games/games/reaction && npm test

# Image-game state machine (15, isolated)
cd party-games/games/image && npm test
```

All 43 tests use the built-in `node:test` runner; no Jest / mocha dependency. Server
tests spin up isolated instances on ephemeral ports with an injected fake clock so
the 2–9 s countdown, 3 s reveal, 800 ms per-image stream, and 3 s scoring window all
fire instantly.

## Repo structure

```
party-games/
  platform/
    server/              — Node http + ws relay (single room; no persistence)
      createServer.js      — factory; accepts { port, game, now, schedule, random, quiet }
      index.js             — entry; loads games/<WF_GAME>/<WF_GAME>.js at boot
      test/*.test.js       — node:test suite (relay protocol + per-game integration)
    receiver-shell/      — TV page (Cast Application Framework + browser fallback)
    controller-shell/    — Phone page (vanilla HTML/CSS/JS + Cast Sender SDK)
  games/
    reaction/            — mini-game 1: countdown timer (4/3/2/1 pts, first to 10)
      reaction.js          — state machine, plugs into createServer
      test/*.test.js       — state machine tested in isolation with mocked services
    image/               — mini-game 2: target-emoji recognition (same scoring)
      image.js             — state machine (REVEAL → DISTRACTORS → TARGET)
      test/*.test.js       — state-machine tests with controllable random + clock
  assets/                — (empty — per-game art / audio / decks)
```

## Plugin interface (for new games)

Games implement the `game` option passed to `createServer({game, ...})`:

```js
const game = {
  name: 'my-game',
  onJoin(player, services)           { /* optional */ },
  onLeave(player, services)          { /* optional */ },
  onMessage(player, msg, services)   { /* handle non-platform messages */ },
};
```

Where `services` = `{ broadcast(msg), sendTo(playerId, msg), getPlayers(), getHost(), now(), schedule(delayMs, fn) → cancel-fn, random() }`.

Platform messages `HELLO`, `PING`, `STATE`, `WELCOME`, `PONG` are reserved; games use distinct type names.

## Phase plan

See [../docs/plans/2026-04-22-party-games-platform-phase-1.md](../docs/plans/2026-04-22-party-games-platform-phase-1.md) for the full sub-phase plan (Phase 1a–1d platform, 2a–2b reaction, 3+ polish/cards/AWS).

## Design references

- [reaction game](../docs/reference/2026-04-14-party-game.md) — first game consumer; mini-game 1 landed in Phase 2a.
- [card games](../docs/reference/2026-04-14-party-game-cards.md) — queued as Phase 5+ after reaction is solid and platform features (rooms, reconnect) land.
