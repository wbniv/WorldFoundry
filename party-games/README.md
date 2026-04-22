# Party Games Platform

Chromecast-based couch party game platform. Individual games plug into a shared shell:
relay server (Node.js + `ws`) + receiver (HTML page running on a Chromecast or browser)
+ controller (HTML page running on each player's phone).

**Current state: Phase 1a — platform shell only.** No game logic yet. The PING button
on the controller round-trips through the relay to the receiver, proving the pipe works.

## Run locally (Phase 1a smoke test)

```sh
cd platform/server
npm install
node index.js
```

Server logs `party-games platform ready on http://localhost:8080`.

Open two browser tabs:

- Receiver: <http://localhost:8080/receiver>
- Controller: <http://localhost:8080/controller?name=Alice>

The receiver should show `[#1 · Alice]` in its player list. Tap the big PING button
on the controller; the receiver's event log picks up a `PONG from Alice` line with a
client→server latency estimate. Open additional controller tabs with `?name=Bob` etc.
to see multi-player behaviour.

## Repo structure

```
party-games/
  platform/
    server/             — Node http + ws relay (single room; no persistence)
    receiver-shell/     — TV page (Cast Application Framework + browser fallback)
    controller-shell/   — Phone page (vanilla HTML/CSS/JS)
  games/                — (empty — game-specific state + renderers land here in Phase 2+)
  assets/               — (empty — per-game art / audio / decks)
```

## Phase plan

See [../docs/plans/2026-04-22-party-games-platform-phase-1.md](../docs/plans/2026-04-22-party-games-platform-phase-1.md).

## Design references

- [reaction game](../docs/reference/2026-04-14-party-game.md) — first game consumer.
- [card games](../docs/reference/2026-04-14-party-game-cards.md) — follows after reaction game is solid.
