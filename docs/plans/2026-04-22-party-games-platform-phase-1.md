# Plan: Party Games Platform — Phase 1 (Chromecast foundation)

**Date:** 2026-04-22
**Status:** In progress
**Branch:** `party-games-platform` (off `2026-ios` HEAD `da9e5ee`), worktree `/home/will/WorldFoundry.party-games-platform`.
**Design refs:** [docs/reference/2026-04-14-party-game.md](../reference/2026-04-14-party-game.md) (reaction game — first consumer), [docs/reference/2026-04-14-party-game-cards.md](../reference/2026-04-14-party-game-cards.md) (future).

## Goal

Reusable Chromecast platform — Node.js relay server + receiver shell (TV) + controller shell (phone). Receiver loads on a real Chromecast; phone controller launches the cast and connects to the same relay; button press on phone appears on TV. **No game logic yet** — the game lives in `games/<name>/` on top of this shell in Phase 2+.

## Prerequisites

### Node.js via fnm (one-time, per-user)

We standardise on **fnm** (Fast Node Manager) for per-user Node version management. Non-privileged install, no `sudo`, trivial version switching.

```sh
# 1. Install fnm (writes to ~/.local/share/fnm/; adds init to ~/.bashrc / ~/.zshrc)
curl -fsSL https://fnm.vercel.app/install | bash

# 2. Re-source the shell (or open a new terminal)
source ~/.bashrc

# 3. Install current LTS Node
fnm install --lts
fnm default lts-latest

# 4. Verify
node --version   # v22.x or v20.x
npm --version
```

If `curl | bash` is blocked in your environment, download the binary release from <https://github.com/Schniz/fnm/releases/latest> (`fnm-linux.zip` / `fnm-macos.zip`) and extract to somewhere on `PATH`.

### Google Cast Developer account

Required for Phases 1b+ (registering the receiver URL and whitelisting your Cast device). See separate [Cast Developer registration notes in the main conversation / README]; one-time $5, ~15 min propagation after adding the test device serial.

### Chromecast on dev network

Any Chromecast 3rd-gen / Ultra / Google TV dongle on the same Wi-Fi as your phone and dev laptop. Needed from Phase 1b onwards; Phase 1a runs entirely in browser tabs.

## Sub-phases

### Phase 1a — platform shell, localhost-only smoke test

Server + receiver page + controller page, all communicating via WebSocket through the server (Architecture B per design: cloud-relay). Cast SDK loaded in receiver but tolerant of non-cast browser contexts. Verified by opening both URLs in browser tabs — button on controller → visible change on receiver.

- `party-games/platform/server/{package.json,index.js}`
- `party-games/platform/receiver-shell/{index.html,receiver.js,receiver.css}`
- `party-games/platform/controller-shell/{index.html,controller.js,controller.css}`
- `party-games/README.md` — how to run.

Protocol (minimal for 1a):

```
client → server                  server → clients
──────────────────────────       ─────────────────────────────────
HELLO(role, name?)           →   STATE({players})              // broadcast to receivers
PING()                       →   PONG(fromPlayerId)             // broadcast to receivers
```

### Phase 1b — HTTPS tunnel + Cast Console receiver app registration ✅

- `cloudflared tunnel --url http://localhost:8080` — live at `https://elderly-ethical-gear-cruises.trycloudflare.com` during dev. Quick tunnel, not persistent across restarts; for named tunnels see Phase 4.
- Cast Console → Applications → Custom Receiver **`A40DF337`** registered as `Party Games Platform (dev)` with URL `https://<tunnel>/receiver`, **unpublished** (only runs on whitelisted test devices — which is what we want).
- Cast Console → Devices → whitelist Chromecast serial: **pending** — user locating the physical device + remote.

### Phase 1c — Cast sender in the controller ✅

Commit `498f6ec`. Controller loads `cast_sender.js?loadCastFramework=1`, initialises `CastContext` with `receiverApplicationId: 'A40DF337'`, exposes a `<google-cast-launcher>` web component for the native device picker. State line reflects `idle / connecting / on <device>`. Receiver logs `SENDER_CONNECTED/DISCONNECTED` to the on-screen event log; status line appends app-data name once CAF's `READY` fires.

### Phase 1d — end-to-end button round-trip on real Cast device (blocked)

Controller PING displays on the TV receiver via actual Cast session. Blocked on device serial (Phase 1b last step) — user locating remote.

### Phase 2a — reaction game state machine (mini-game 1) ✅ (server + tests; end-to-end pending Cast device)

Implements mini-game 1 (countdown timer) as a **game plugin** at `party-games/games/reaction/reaction.js` consumed by the platform via `createServer({ game })`. Plugin interface is minimal: `{onJoin, onLeave, onMessage}` receiving a `services = {broadcast, sendTo, getPlayers, getHost, now, schedule, random}` surface. All clocks are injectable so tests can deterministically fast-forward through countdowns + scoring windows.

State machine: `LOBBY → ROUND_COUNTDOWN → ROUND_OPEN → ROUND_ENDED → (next round | GAME_OVER) → NEW_GAME (LOBBY)`. Server owns all state + timestamps; controllers forward button presses; receiver renders phases + scoreboard.

New messages on top of the platform's HELLO/PING/STATE/WELCOME/PONG:
- Controller → server: `START_GAME` (host only from LOBBY/GAME_OVER), `BUTTON_PRESS {clientTs}`, `NEW_GAME` (host only from GAME_OVER).
- Server → clients: `PHASE {phase, scores}`, `ROUND_COUNTDOWN {roundId, showMs}`, `TIMER_FIRED {roundId, serverTs}`, `EARLY_PRESS {roundId, playerId, name}`, `ROUND_ENDED {roundId, ranks, scores}`, `GAME_OVER {winnerId, name, scores}`.

Scoring: 4/3/2/1 to 1st–4th; first to 10 pts wins. Early press → lockout for that round only, scores 0. Server-receive-timestamp adjudication (design doc §Timing).

Receiver renders: LOBBY player list; countdown with a decaying CSS bar keyed to showMs (9s); giant animated GO! on TIMER_FIRED; per-round rankings + running scoreboard; final winner screen.

Controller button label + action adapts to phase: START/NEW GAME for host in LOBBY/GAME_OVER; GO! (or LOCKED) during ROUND_OPEN.

Test coverage:
- `party-games/platform/server/test/relay.test.js` — 10 tests (platform protocol, hardening).
- `party-games/platform/server/test/reaction-integration.test.js` — 2 tests (game wired through real WebSocket server with fake clock).
- `party-games/games/reaction/test/reaction.test.js` — 13 tests (state machine in isolation).

End-to-end verification on a physical Cast device is still blocked on device-serial registration (Phase 1b).

### Phase 2b — reaction game mini-game 2 (image recognition) — deferred

Needs a pool of ~20 distinct flat icons + preload logic on receiver + same timing-adjudication machinery applied to `SHOW_IMAGE(targetId)` rather than `TIMER_FIRED`. Tackled after Phase 1d unblocks and 2a is hardened on a real device.

### Phase 3+ — UX polish, PWA manifest, mobile CSS, cards game, production hosting

Per the "Out of scope" section below; expanded after Phase 2 lands.

## Proposed repo layout

```
party-games/
  README.md
  platform/
    server/
      package.json
      index.js            — http + ws; static-file server; broadcast relay
    receiver-shell/
      index.html          — loads CAF; opens WS to server; base TV layout
      receiver.js
      receiver.css
    controller-shell/
      index.html          — opens WS; base phone UI (button + name entry)
      controller.js
      controller.css
  games/                  — (empty Phase 1a; per-game subdirs in Phase 2+)
  assets/                 — (empty Phase 1a)
```

No bundler, no framework. Plain HTML/CSS/JS + Node http + `ws`.

## Out of scope for Phase 1

- Game logic (reaction or cards) — Phase 2+.
- AWS production hosting (S3+CloudFront + Lightsail) — Phase 4+.
- PWA manifest / service worker — Phase 3.
- Apple TV / Fire TV / browser-on-HDMI matrix polish — Phase 3.
- Cloudflare Tunnel → named tunnel → zero-trust reserved URL — Phase 4 (trycloudflare random URLs are fine for dev).
- Room codes / multi-room — Phase 2 when reaction game needs isolation.

## Verification

- 1a: browser tabs — receiver at `http://localhost:8080/receiver`, controller at `http://localhost:8080/controller?name=Alice`. Receiver shows `[Alice]`; click button on controller; receiver shows a ping event.
- 1b: phone Chrome → Cast → TV loads receiver via tunnel URL. Status indicator on receiver (WS connected).
- 1c: controller "Cast to TV" button launches receiver on TV without leaving the page.
- 1d: button press on phone → TV displays ping. Commit.

## Follow-up

- Phase 2a: lobby + round scaffolding in `games/reaction/`.
- Phase 2b: mini-game 1 (countdown) end-to-end.
- Phase 2c: mini-game 2 (image recognition).
- Phase 2d: scoring, win condition, fireworks.
- Phase 3: PWA manifest, mobile CSS, browser-on-HDMI verification, accessibility.
- Phase 4: production hosting (AWS S3+CloudFront + Lightsail), custom domain, published Cast app review.
- Phase 5+: cards game on the same platform.
