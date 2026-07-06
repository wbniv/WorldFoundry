---
name: Party Games Platform context
description: Cast-based couch party game in party-games/ on branch party-games-platform; current state + where things live
type: project
originSessionId: f3a787ff-e88f-44fa-8fd7-2cf3a966f5ee
---
Party Games Platform lives at `party-games/` on branch `party-games-platform` (off the older `2026-ios` HEAD). Node.js relay + receiver shell (TV) + controller shell (phone). **Three games as plugins** after Phase 5: `games/reaction/`, `games/image/`, `games/worst-take-wins/` (fill-in-the-blank card game, CAH model). Each game ships server-side state machine + `client/` module (controller.js + receiver.js + CSS) loaded dynamically by the shell.

Parent plan: `docs/plans/2026-04-22-party-games-platform-phase-1.md` (has a Phase 5 completion summary appended at the bottom as of 2026-04-23). Phase 5 plan file: `/home/will/.claude/plans/phase-5-atomic-pine.md`.

**Phase 5 (2026-04-23) — landed.** Per-game client-asset plugin seam + retrofit of reaction/image onto it + Worst Take Wins as the third game. Key architectural change: `createServer` now takes `gameName` + `gamesRoot`; shell HTML has `{{GAME_NAME}}` + `{{GAME_STYLESHEET}}` placeholders substituted per request; `/game/client/*`, `/game/assets/*`, `/shell-lib/*` routes route to per-game and shared assets respectively (each with its own path-traversal guard). Game client modules export `mount(ctx)` / `unmount()`; ctx = `{ root, send, on, playerId, isHost, players, hostId, feedback, assetUrl, log }`. Shell JS is ES-module now, loads the game module via dynamic import on WELCOME.

Test count: **98** across four locations (reaction 15, image 22, worst-take-wins 30, platform/server 31). All green.

**Phase 1d (physical Chromecast verification) — still blocked.** Awaiting Google Cast Console propagation of the recreated app (`071CDEDD`); their docs say up to 48 h, no UI indicator for completion. Detection: reload the controller URL, `cast-state` flips from `cast: no devices found` → `cast: ready — tap the button` when it's through. Phase 5 work did not touch Cast integration — Phase 1d verification remains the next gating step whenever propagation completes.

**Why Phase 5 was bundled with the platform refactor:** original scope was "scaffold cards plugin" but exploration showed `createServer({ game })` generalised on the server side while the shells had reaction+image assumptions hardcoded. A third game meant either a third set of hardcoded cases or a real per-game client seam; user picked the largest-scope option (seam refactor + retrofit reaction/image + new game + CAH deck wired in).

**How to apply:** When user returns to Phase 1d, check the Cast picker first; only debug if propagation genuinely is done. Launch commands: `cd party-games/platform/server && WF_GAME=worst-take-wins node index.js` (or reaction / image / none).

**Stable public URL (as of 2026-04-24):** `https://pg.rapid-raccoon.com` — named Cloudflare Tunnel `party-games` on this laptop → `localhost:8080`. Replaces the old rotating trycloudflare.com quick tunnels. Cast Console receiver URL is now `https://pg.rapid-raccoon.com/receiver` (set 2026-04-24). Don't cycle the Cast Console URL any more — stable now, no more restarting the propagation clock. Setup script: `~/SRC/bumper2bumper/scripts/cloudflare-create-named-tunnel.sh`. Config at `~/.cloudflared/config.yml`; tunnel runs by hand (`cloudflared tunnel run party-games`) until Party Games relay moves to an AWS server (TODO in migration plan).

**Explicit castAppId while propagation is pending:** during the propagation window, always include `&castAppId=071CDEDD` on controller test URLs — the explicit param is the only reliable path on-device, not the hardcoded default in `controller.js:22`. URL form: `https://pg.rapid-raccoon.com/controller?name=<n>&castAppId=071CDEDD`. Drop this once Phase 1d hardware acceptance passes. And: do not volunteer laptop-Linux-Chrome-Cast-discovery debugging as a first move — the real constraint is the Cast Console propagation clock, not desktop discovery flakiness.

**Still owed after Phase 5:** live in-browser click-through with 3 controllers + 1 receiver for WTW. Server-side is covered by unit + integration tests; client DOM rendering is only syntax-verified. User should play one round end-to-end in browser to confirm.

Two physical Chromecast-with-Google-TV devices, both whitelisted: `31191HFGN54Q67` ("th", currently plugged in) and `2628105GN0GT7C` ("ch", spare). Google Home labels them "TV" — that's what the sender picker shows, not the Cast Console description.

Cast dev account: wbnorris@gmail.com.
