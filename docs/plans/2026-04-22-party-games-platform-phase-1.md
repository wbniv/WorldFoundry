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

### Phase 1b — HTTPS tunnel + Cast Console receiver app registration

- `cloudflared tunnel --url http://localhost:8080` (or equivalent) → note the `https://<rand>.trycloudflare.com` URL.
- Cast Console → Applications → Add Custom Receiver → URL = `https://<tunnel>/receiver` → save, note App ID.
- Cast Console → Devices → verify Chromecast serial is registered (needs ~15 min propagation after add).
- On phone: Chrome → `⋮` → Cast → pick Chromecast → TV loads the receiver page. Still talks to server via WS through the tunnel.

### Phase 1c — Cast sender in the controller

Replace the manual "cast via Chrome menu" with an in-page "Cast to TV" button (Cast Sender SDK v3). Session management: first controller to connect starts the cast; subsequent controllers join the same room.

### Phase 1d — end-to-end button round-trip on real Cast device

Controller PING displays on the TV receiver via actual Cast session. Commit Phase 1 complete.

### Phase 2+ — reaction game

Implements the reaction game on top of the platform shell (`party-games/games/reaction/`). Phases per the design doc: mini-game 1 (countdown), mini-game 2 (image recognition), 10-point win condition, fireworks.

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
