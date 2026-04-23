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

### What we fixed / shipped along the way (committed)

Phase 1d debugging + Phase 2b build:
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
| `5cfd5b6` | plan — today's session (this file) |
| `9fbd194` | plan — fix device-swap description (two units, not a typo) |
| `57823fe` | plan — soften IPv4 claim + note Home-vs-Console name confusion |
| `cd71811` | plan — flag 'Cast edits restart clock' as unverified |

Phase 2c — end-of-game polish:
| Commit | Subject |
|--------|---------|
| `a4539fa` | iter-1 — end-of-game outcome overlay + podium scoreboard |
| `ce1d4de` | iter-2 — haptic + Web Audio feedback on controller |
| `bbabf44` | iter-3 — live commit indicator on TV during PLAY |
| `cf7b5e6` | iter-4 — mobile tap-delay fix + reaction-game PRESS_RECORDED symmetry |
| `245a502` | iter-5 — REVEAL countdown bar + shared commit indicator |
| `8611f68` | iter-6 — soft descending-tone on losing phones |
| `c9ca6fd` | iter-7 — round-end scoreboard animation (staggered rank reveal + badge pulse) |
| `0a779ea` | iter-8 — 'get ready' chime on round start |
| `802d448` | iter-9 — join/leave events on TV log |
| `4eb763a` | plan — Phase 2c iter-2/3/4 recap |
| `89b933c` | plan — Phase 2c iter-5/6 recap |
| `ad6e271` | plan — expand commit log + flesh out follow-up sections |

Gameplay-rule iterations (post-polish):
| Commit | Subject |
|--------|---------|
| `661bfdc` | diagnose 'first tap not accepted' — optimistic press UI + server log |
| `d791496` | image game — guarantee the target appears within each round (`GUARANTEED_TARGET_BY_SEQ = 40`) |
| `5f0f66c` | image game — LAST_STANDING auto-win when everyone else locks out |

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

Nine iterations shipped today. Mobile + desktop tested via browser tabs; TV-path still pending Phase 1d propagation.

- **iter-1 (`a4539fa`):** end-of-game overlay — winning phone gets gold-gradient "YOU WIN" + confetti, losing phones get a muted "Game over / <winner> won this round" screen, both show a full final scoreboard with winner highlight. TV receiver final scoreboard became an ordered podium list (🥇 on winner). Overlay dismisses on next non-`GAME_OVER` phase.
- **iter-2 (`ce1d4de`):** haptic + Web Audio feedback on the controller. Successful press = 40 ms vibrate + 880 Hz triangle blip. Lockout = descending two-tone sawtooth buzz + 3-pulse vibrate. Win = C-major arpeggio + celebratory haptic pattern. AudioContext lazily constructed on first user-gesture click (iOS Safari requires this to unlock audio).
- **iter-3 (`bbabf44`):** live commit indicator on the TV during PLAY — pills appear in order as players commit (green ✓ = recorded, red ✗ = locked out), clears at next round start. Game side exposes this via a new `PRESS_RECORDED { roundId, playerId, name }` broadcast mirroring the existing `EARLY_PRESS`.
- **iter-4 (`cf7b5e6`):** `touch-action: manipulation` on the controller body + big button kills the 300 ms double-tap-to-zoom delay that iOS Safari and some Android Chrome builds impose by default. Reaction game also broadcasts `PRESS_RECORDED` for protocol symmetry so a shared receiver indicator will work for both games in the future.
- **iter-5 (`245a502`):** REVEAL countdown bar — target emoji now has a thin decaying progress bar underneath during the 3 s reveal. Commit indicator moved from inside the image-game's distractors panel up to a shared location below the stage, so it lights up for reaction-game rounds too (ROUND_COUNTDOWN handler resets the map symmetric with ROUND_REVEAL's existing reset).
- **iter-6 (`8611f68`):** soft descending A4 → F4 triangle sigh on losing phones at GAME_OVER. No haptic — the visual overlay already signals the loss, so an extra buzz felt like piling on.
- **iter-7 (`c9ca6fd`):** round-end scoreboard animation — rank rows reveal 1-by-1 (150 ms stagger), scoring rows get a green `+N` badge that pulses 200 ms after the row lands, locked-out rows dim to 55%, cumulative scoreboard flashes yellow on rows whose score changed this round (delayed ~1 s so the flash lands after the stagger finishes).
- **iter-8 (`0a779ea`):** 'get ready' ascending two-note chime on each `ROUND_COUNTDOWN` / `REVEAL`. Intentionally does NOT play on target appearance — that would turn the image game into an audio-reaction contest.
- **iter-9 (`802d448`):** STATE-diff on the receiver logs `<name> joined` / `<name> left` entries to the event log so the TV audibly/visually acknowledges the roster changing.

Test count 46 → 49 across runners after Phase 2c (one new image-game test in iter-3, one new reaction-game test in iter-4; iter-5/6/7/8/9 are UI-only).

## Gameplay-rule iterations (post-polish)

Landed after the initial polish pass, in response to live-playtest feedback on the image game:

- **`661bfdc` — diagnostic + optimistic press UI.** Will reported that his first tap of a round was being silently ignored. Added (a) server-side `console.log` on every `BUTTON_PRESS` with phase + whether the target has been revealed + whether the player is already in presses/lockedOut, and (b) client-side `pressedThisRound` tracking — after firing `BUTTON_PRESS` the button immediately flips to `✓` disabled, so the player gets proof their tap left the tab even if the server rejects it. Also logs a DevTools `[click] ignored` warning when the `ws.readyState !== OPEN` guard drops a tap.
- **`d791496` — guaranteed target appearance.** A round happened where the target never appeared at all (math: with a 20-emoji pool at 5%/frame, ~2% of 60 s rounds produce no target, and one did). Added `GUARANTEED_TARGET_BY_SEQ = 40` (~32 s in): if the natural random hasn't surfaced the target by frame 40, the next frame is forced to be the target.
- **`5f0f66c` — LAST_STANDING auto-win.** Per user: "if there's only 1 player who hasn't been locked out, that player should win that round by default". After any EARLY_PRESS lockout (in REVEAL or PLAY), if exactly one player remains un-locked (and at least one lockout has occurred — solo-play exemption), that player gets an auto-recorded press → 4 pts and a new `LAST_STANDING { roundId, playerId, name }` broadcast announces it. `endRound`'s phase guard relaxed so REVEAL-phase auto-wins can close the round.

**Rule walk-back that didn't ship:** mid-iteration the user asked "first person who gets it right should end the round (not waiting for other players)" — I implemented it, then the user remembered the 4/3/2/1 ranking was deliberate and the "waiting feels wrong" was an artifact of 2-player playtesting. Reverted before commit, so the current rule remains: all successful presses within a round rank 4/3/2/1 by serverTs, round ends when everyone has committed or `maxRoundMs` elapses (or LAST_STANDING short-circuits).

Test count after these three = **51 across runners** (22 image unit + 14 reaction unit + 15 platform-server = 11 relay + 2 reaction integration + 2 image integration).

Queued for future iterations:

- **Post-first-commit grace timer.** After the first player commits, start a shorter clock (10-15 s) that force-ends the round even if stragglers haven't tapped. Caps the worst-case round duration below the 60 s `maxRoundMs`. User asked about it earlier but hasn't decided; open question.
- **Reaction game parity on LAST_STANDING + GUARANTEED_TARGET_BY_SEQ.** Only wired into the image game right now. The reaction-game countdown has a different structure (pre-committed real timer window) but the "last standing" concept would still apply.

## Follow-up

**Phase 2c polish, still queued:**
- Round-end scoreboard animation (point-delta badges `+4 / +3 / +2 / +1` flying from rank rows into the cumulative scoreboard).
- Sound cue on target appearance during PLAY (subtle rise-tone so players who were looking away mid-stream get an audio hint). Design question: does this give an unfair advantage to the first player who hears it, or is the whole point that everyone's on the same broadcast? Probably fine since all clients get the SHOW_IMAGE at the same server tick.
- Tune the reveal countdown-bar duration so it exits with a beat of silence before PLAY (currently shrinks to 0 exactly when CLEAR begins; could end earlier and hold at 0 briefly for visual "beat").

**After Phase 1d unblocks:**
- Mark 1d ✅ in the parent phase-1 plan doc and the party-games README.
- Play-test on real Cast hardware with 2-4 phones. Likely surfaces mobile issues the browser-tab rehearsal doesn't (actual Cast session quirks, screen-lock-mid-round behaviour, multi-sender disagreement).
- Any gameplay tuning that real hardware play surfaces (image timing, reveal duration, distractor density) — the existing constants are guesses.

**Longer horizon (Phase 3-5):**
- Phase 3 mobile polish: `viewport-fit=cover` is already set; add a PWA manifest + service worker so "Add to Home Screen" works; safe-area insets; landscape layout check.
- Phase 3 room codes so multiple groups can play on the same server without colliding (currently single-room).
- Phase 4 production: named Cloudflare tunnel (stops the Cast Console URL being a moving target every restart), S3+CloudFront for the static shells, Lightsail for the WS relay, published Cast app review.
- Phase 4 session IDs so a reconnecting player rejoins as their original id rather than forfeiting mid-round scores.
- Phase 5 cards game — third plugin under `games/` exercising a different mechanic (turn-based, not reaction-based) to stress-test the plugin interface.
