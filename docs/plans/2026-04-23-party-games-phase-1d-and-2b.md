# Plan: Party Games — Phase 1d Cast verification + Phase 2b redesign

**Date:** 2026-04-23
**Status:** In progress (Phase 1d blocked on Cast Console 48 h propagation; Phase 2b shipped + iterated)
**Branch:** `party-games-platform`
**Parent plan:** [docs/plans/2026-04-22-party-games-platform-phase-1.md](2026-04-22-party-games-platform-phase-1.md)

## Context

Continuation of the Phase 1 platform work on a different laptop from the first session. Goal for today was Phase 1d — end-to-end button round-trip on the registered Google TV. It didn't happen; Google Cast Console propagation for a newly-registered app ID turned out to have an "up to 48 h" window that isn't surfaced anywhere in the UI. We spent the blocked time on Phase 2b (image recognition mini-game) instead, including a full redesign after first play.

## Session state — Phase 1d (Cast)

### Environment this session

- Laptop: Ubuntu 25.10, system Node v20.19.4, Chrome (desktop + Android for phone testing).
- Repo: `/home/will/SRC/WorldFoundry-wbniv/`, branch `party-games-platform`.
- Cast dev account: `wbnorris@gmail.com`.
- TV: Chromecast with Google TV, serial `31191HFGN54Q67` ("th"). You have two units; originally registered + tested the other one (`2628105GN0GT7C` "ch") but swapped to this one when the first was giving problems. Both are registered in the Devices whitelist.

### Running pieces at end of session

- Relay server: `cd party-games/platform/server && WF_GAME=image node index.js` on `:8080` (background PID rotates between test/restart cycles).
- Cloudflare quick tunnel: `cloudflared tunnel --url http://localhost:8080` — currently `https://helped-enjoy-calm-renewable.trycloudflare.com`.
- Cast Console app ID: **`071CDEDD`** — "Party Games Platform (dev)", Custom Receiver, Unpublished, receiver URL pointed at the tunnel, Sender Website URL populated. Originally `A40DF337` but it got wedged (propagation never completed even after hours); recreated with Sender Details populated at creation time.

### What we fixed along the way (committed)

| Commit | Subject |
|--------|---------|
| `bb1a0c5` | Phase 1d — static-asset fix + Cast SDK hardening |
| `3b2b00e` | Phase 2b — image-recognition mini-game (original REVEAL → DISTRACTORS → TARGET shape) |
| `abee593` | image game — keep cycling through TARGET + failsafe round timeout |
| `14a0cd2` | receiver showPanel — de-dup aliased panel elements |
| `c842801` | image game — redesign round as uniform-random 60 s stream |
| `52ca4a4` | image game — press-grace window for late-target presses (later superseded) |
| `0b048ef` | image game — "round arms on first target" rule |
| `2728eb5` | relay — no-store cache headers on static files |
| `bdb4071` | catch late-joining controllers up on the current phase |
| `d8beca9` | controller — auto-reconnect WebSocket |
| `452c015` | quiet console noise — gate CAF by Cast user agent + inline favicon |
| `908deef` | plan — flesh out the Phase 2b state diagram |
| `b6d1d90` | plan — second mermaid diagram for the controller WS lifecycle |

### Root causes uncovered during Phase 1d setup

All of these were surprising enough to merit capturing for the next time (or the next person):

1. **Static-asset 404.** `<script src="receiver.js">` at `/receiver` resolves to `/receiver.js`, not `/receiver/receiver.js`. Old `resolveStatic` only handled the latter. Silent 404, page stuck on default "connecting…" text. Phase 1a's "verified in browser tabs" claim was aspirational — no test covered static serving. Fixed in `bb1a0c5` plus a `relay.test.js` case.
2. **Cast SDK timing quirks.** `window.__onGCastApiAvailable(true)` callback fires before `cast.framework` / `chrome.cast.AutoJoinPolicy` are populated on some browsers. Fixed with a poll-then-init loop, string-literal fallback for `autoJoinPolicy`, and explicit seeding of the cast-state UI from `ctx.getCastState()` (CAST_STATE_CHANGED doesn't always fire initially).
3. **Empty Cast Console Sender Details.** The UI notes "required to publish" but in practice the backend also uses it for device-to-app association on unpublished apps. The first app (`A40DF337`) was registered without Sender Details set — never propagated to the device. Recreating as `071CDEDD` with Sender Details populated at creation time was the path forward.
4. **Device swap during debugging.** Started the day with Chromecast `2628105GN0GT7C` ("ch"). When it kept not working we (reasonably) swapped to the other unit `31191HFGN54Q67` ("th") to rule out a hardware-specific issue. Briefly confusing because the Cast Console still had the first device highlighted as "Ready For Testing" while the physically-plugged-in unit was the second one. Both serials are on the whitelist now.
5. **Missing IPv4 address on TV — not definitively the root cause.** Chromecast's device status page showed only an IPv6 address (Chrome's Cast discovery uses IPv4 mDNS, so this seemed suspicious). Set a static IPv4 (`192.168.4.50`) on the TV and YouTube cast started working shortly after; we never isolated whether the static-IP was actually what fixed it vs. the router / TV happening to recover around the same time from something else. Leaving the static IP in place because it's harmless and removes a variable if discovery regresses.

   Side confusion: the device shows as **"TV"** in the Google Home app but as **"ch"** / **"th"** in the Cast Developer Console (descriptions we typed at registration). When troubleshooting "where's the device in the picker?" the Google Home app label is what the sender SDK shows users, not the dev-console description — worth remembering next time.
6. **48-hour propagation.** Google Cast Console says "it may take up to 48 hours for your Google Cast Developer Console registration to be fully processed". No UI indicator for completion — only signal is the cast button appearing on a controller page. We stopped touching the Cast Console entry on the theory that edits could restart the propagation clock — unverified, behaving cautiously.

### Current state / next actions for Phase 1d

- Tunnel + server + Cast Console registration are pinned. Not touching Cast Console.
- Wait for 071CDEDD to propagate (likely within 48 h of when we re-saved Sender Details; this was mid-afternoon 2026-04-23).
- Detection: periodically reload `https://helped-enjoy-calm-renewable.trycloudflare.com/controller?name=Will` in laptop Chrome; the moment `cast-state` flips from `cast: no devices found` to `cast: ready — tap the button`, propagation is done.
- Once unblocked: tap cast button → select `th` → verify the receiver shell loads on the TV with `cast + server connected` status, then play a reaction round and an image round end-to-end.

## Phase 2b — image-recognition mini-game

Designed, shipped, and iterated three times today. Final shape + state diagram are documented inline in [2026-04-22-party-games-platform-phase-1.md §Phase 2b](2026-04-22-party-games-platform-phase-1.md#phase-2b--image-recognition-mini-game-playable-end-to-end-in-browser-commits-3b2b00e-abee593-14a0cd2-later-reshape). Summary of the design evolution:

1. **Original (shipped `3b2b00e`):** Strict REVEAL → DISTRACTORS → TARGET sequence; target appeared at a pre-determined position in the stream; 3 s scoring window opened when target fired.
2. **Feedback after first play:** Stream stopped feeling alive the moment the target appeared. Redesigned (`c842801`) into a single PLAY phase with uniform-random image picks and press-on-target adjudication.
3. **"Grace window" half-step (`52ca4a4`):** Added a 250 ms grace period to catch presses that arrived just after a target frame transitioned. Addressed a race condition but didn't match the actual intended rule.
4. **"Round arms on first target" rule (`0b048ef`):** The real rule. Target appearing at any point in the stream arms the round; any subsequent press counts, ranked by serverTs order; current-frame adjudication gone entirely. Much simpler; matches the user's mental model.

Plus robustness fixes on the same branch:

- `bdb4071` — `onJoin` sends the current `PHASE` to late joiners so they aren't stranded on `phase='LOBBY'` with a disabled button.
- `d8beca9` — controller WebSocket auto-reconnects (mobile browsers aggressively drop inactive sockets; Bob's Android Chrome tab kept dying during testing).
- `2728eb5` — `Cache-Control: no-store` on static files (prevent cached pre-PLAY controller.js from making Bob's tab sit in a phase case that doesn't exist any more).
- `452c015` — gate CAF `ctx.start()` on a Cast-capable user agent; silences `ws://localhost:8008/v2/ipc` spam when the receiver runs in a plain browser.

Test counts at session end: **47** across three `npm test` locations (image-game 18, reaction-game 13, platform+integration 15+1 static).

## Verification

Phase 1d acceptance (pending propagation):

1. Laptop Chrome at the controller URL shows `cast: ready — tap the button`, cast icon visible.
2. Tap cast → `th` in device picker → select.
3. TV flips to receiver shell; status `cast + server connected (Party Games Platform (dev))`.
4. Two controllers joined; `PING` round-trip reflects on TV event log.
5. Reaction round: countdown → GO → first press wins 4 pts.
6. Image round: memorise reveal → stream → tap once target has flashed.

Phase 2b acceptance (in-browser, achieved today):

1. Multi-tab browser session. All tabs get fresh JS on reload (no-cache).
2. Host starts game; all players see REVEAL emoji full-screen.
3. PLAY streams emoji at 800 ms. Target appears naturally every ~16 frames (1/20 per frame with 20-emoji pool).
4. Early taps (pre-target) show `EARLY_PRESS` on receiver and flip the pressing player's button to `LOCKED`.
5. First target appearance arms the round. Any subsequent tap ranks by order. Round ends when all players have committed or 60 s, whichever first.
6. First to 10 points → `GAME_OVER` with winner banner. Host can `NEW GAME` to reset.

## Phase 2c — end-of-game polish

Four iterations shipped today. Mobile + desktop tested via browser tabs; TV-path still pending Phase 1d propagation.

- **iter-1 (`a4539fa`):** end-of-game overlay — winning phone gets gold-gradient "YOU WIN" + confetti, losing phones get a muted "Game over / <winner> won this round" screen, both show a full final scoreboard with winner highlight. TV receiver final scoreboard became an ordered podium list (🥇 on winner). Overlay dismisses on next non-`GAME_OVER` phase.
- **iter-2 (`ce1d4de`):** haptic + Web Audio feedback on the controller. Successful press = 40 ms vibrate + 880 Hz triangle blip. Lockout = descending two-tone sawtooth buzz + 3-pulse vibrate. Win = C-major arpeggio + celebratory haptic pattern. AudioContext lazily constructed on first user-gesture click (iOS Safari requires this to unlock audio).
- **iter-3 (`bbabf44`):** live commit indicator on the TV during PLAY — pills appear in order as players commit (green ✓ = recorded, red ✗ = locked out), clears at next round start. Game side exposes this via a new `PRESS_RECORDED { roundId, playerId, name }` broadcast mirroring the existing `EARLY_PRESS`.
- **iter-4 (`cf7b5e6`):** `touch-action: manipulation` on the controller body + big button kills the 300 ms double-tap-to-zoom delay that iOS Safari and some Android Chrome builds impose by default. Reaction game also broadcasts `PRESS_RECORDED` for protocol symmetry so a shared receiver indicator will work for both games in the future.

Test count bumped 46 → 49 across runners (one new image-game test in iter-3, one new reaction-game test in iter-4).

Queued for future iterations:

- **Round-end scoreboard animation.** Fade in new rankings; animate `+4 / +3 / +2 / +1` point-delta badges from the rank row into the running scoreboard.
- **REVEAL drama.** A 3-2-1 countdown overlay or a decaying ring around the target emoji would cue "game starts NOW". Currently just a static emoji + "memorise" hint.
- **Shared commit-indicator panel on receiver.** Right now the pills only render inside the image game's panel. Moving to a shared overlay would light up in reaction-game rounds too (iter-4 already sends `PRESS_RECORDED` for both games).
- **Win/lose sound cue on losing phones.** Sonically, losing phones are silent. A soft "womp-womp" or just a muted closing chord would feel more complete.

## Follow-up after Phase 1d unblocks

- Commit marking 1d ✅ in the parent phase-1 plan doc and the party-games README.
- Phase 3 (mobile polish): viewport + no-zoom, full-screen friendly, add-to-home-screen manifest.
- Phase 4 (production): named Cloudflare tunnel so the Cast Console URL stops being a moving target; S3+CloudFront for static; Lightsail for the WS server; published Cast app review.
- Session IDs so a reconnecting player rejoins as the same id (currently reconnect forfeits current-round score).
