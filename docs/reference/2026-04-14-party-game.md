# Investigation: Chromecast Party Game — Reaction Timer + Image Recognition

**Date:** 2026-04-14

## Concept

A 2–4 player couch party game. Each player uses their smartphone as a dedicated
button controller. A shared TV screen shows game state. Two mini-games test reaction
speed; first player to 10 points wins.

---

## Platform targets

### Primary: Chromecast

- Google Cast SDK v3 (CAF — Cast Application Framework).
- **Receiver** = an HTML5 web app hosted at a public URL; registered in the Google
  Cast Developer Console ($5 one-time registration fee).
- **Sender** = web page on phone (no install) or native Android/iOS app.
- Supports Chromecast Ultra, Gen 3, and Google TV dongles.

### Other TV platforms

| Platform | SDK / approach | Notes |
|----------|---------------|-------|
| **Browser on HDMI** | None | Player plugs laptop into TV; opens the receiver URL. Zero friction, zero SDK — best fallback. |
| Apple TV | tvOS app or AirPlay mirror | AirPlay mirror: open receiver URL in Safari on iPhone/Mac, mirror to Apple TV — zero extra code. Native tvOS app needs $99/yr dev account. |
| Amazon Fire TV | Android (Fire OS) | App with Leanback UI. Fire OS is Android-based; reuse Android sender code. |
| Roku | BrightScript | Niche scripting language; ~40% of US households. Low ROI for v1. |
| Samsung Tizen / LG webOS | HTML5 Smart TV SDKs | Fragmented APIs. Skip for now. |

**Recommended sequencing:** Chromecast → browser-on-HDMI fallback (free) → Apple TV
AirPlay mirror → Fire TV. Skip Roku/Tizen/webOS for v1.

---

## Phone controller: Browser/PWA vs Native App

| Concern | Browser / PWA | Native app |
|---------|--------------|------------|
| Install friction | None — share URL or QR code | App Store / Play Store required |
| iOS haptics | `navigator.vibrate()` ignored by iOS Safari | Full Taptic Engine |
| Android haptics | Vibration API works | Full haptic patterns |
| Button latency | WebSocket in browser; ~5–15 ms overhead | Minimal |
| Development cost | One HTML/JS codebase | React Native or Flutter (~2× effort) |
| App store approval | None | Days to weeks |

**Recommendation:** Browser/PWA for v1. For a party game where someone joins in 30
seconds, zero-install beats haptics. On iOS, substitute a CSS scale-flash on the button
(Safari blocks `navigator.vibrate()`). Native app is a clean v2 upgrade.

---

## Server architecture

### Option A — Cloud relay (recommended for v1)

A persistent WebSocket server (Node.js + `ws`) hosted on Fly.io. Players connect via
a 4-letter room code shown on TV.

- No install on any device.
- Works even if players are on different Wi-Fi networks (unusual but possible).
- Fly.io free tier handles hundreds of concurrent rooms easily.
- Adds ~20–80 ms of internet round-trip, but **timing adjudication is server-side**
  (see §Timing), so latency is compensated, not a raw disadvantage.

### Option B — Local / LAN

All devices on the same Wi-Fi; no cloud cost. The Chromecast receiver page can't run a
WebSocket server (sandboxed HTML). Options:

1. **WebRTC DataChannel** — Chromecast receiver acts as the "host peer"; phones connect
   peer-to-peer via WebRTC. Needs a free STUN server (Google's public STUN); TURN only
   required for strict NAT (rare on home Wi-Fi). No server to deploy.
2. **Host phone runs a server** — the host player opens a special "host" URL that
   launches a service worker with a WebSocket relay. Limited by service worker socket
   restrictions; tricky on iOS.

**Recommendation:** Cloud relay for v1 (simplest, most reliable). Add WebRTC LAN mode
in v2 for offline play.

---

## Game mechanics

### Shared state machine (server owns all state)

```
LOBBY → ROUND_START → [GAME_1 | GAME_2] → ROUND_END → (LOBBY | WINNER)
```

Clients are dumb: they render what the server tells them and forward button presses.
The server assigns all timestamps. No client is trusted for scoring.

---

### Mini-game 1: Countdown Timer

1. Server picks `T` ∈ [2, 9] seconds (uniform random, **not** sent to clients).
2. TV shows a countdown display ticking down from a visible start (e.g. always starts
   display at 9 and the hidden cut-off fires at T).  
   *Alternative:* show a progress bar that depletes — less readable cheating.
3. At `T = 0`, server broadcasts `TIMER_FIRED`.
4. Server opens a 3 s scoring window. First `BUTTON_PRESS` messages (ranked by
   server-received timestamp) determine 1st–4th place.
5. Any press received before `TIMER_FIRED` → player flagged `LOCKED_OUT` for the round.
   Server enforces; client shows a greyed-out / locked state.

---

### Mini-game 2: Image Recognition

1. Server picks one **target image** from the pool.
2. TV shows the target full-screen for **3 s** (`REVEAL` phase), then clears to a
   solid colour for 0.5 s (palette clears short-term memory cleanly).
3. Server streams `SHOW_IMAGE(id, durationMs)` events. TV displays each image for
   ~800 ms. The target re-appears after a random number of distractors (4–8 images
   shown before the target).
4. Phones receive the same `SHOW_IMAGE` stream — they know when the target is shown
   so the server can adjudicate false presses accurately.
5. When the target's `SHOW_IMAGE` fires: server opens the scoring window. Same
   1st–4th ranking as game 1.
6. Presses before the target's `SHOW_IMAGE` → lockout.

**Image pool:** ~20 flat icons, visually distinct (no text). Phosphor Icons or
Heroicons (both MIT, SVG). Keep them immediately recognisable: 🍎 apple, ⚡ bolt,
🐸 frog, 🚀 rocket, etc.

---

### Scoring and win condition

- Each round: **4 / 3 / 2 / 1** points for 1st–4th place.
- Locked-out player scores **0** that round.
- With fewer than 4 players, unused scoring slots are simply absent.
- First player to **10 points** wins.
- Server broadcasts `WINNER(playerId)`. Winner's phone receives a `FIREWORKS` event
  and plays a full-screen CSS/Canvas fireworks animation. Other phones show a "You
  lost" screen. TV shows a final scoreboard.

---

## Timing accuracy

**The problem:** each phone's clock drifts vs. the server. Client timestamps cannot be
directly compared across players.

**Solution — server-receive adjudication:**
- Client sends `{type: "PRESS", clientTs: Date.now()}` immediately on `touchstart`.
- Server records `serverReceivedTs` on receipt.
- All ranking uses `serverReceivedTs` only. `clientTs` is logged for debugging.
- Network latency is ~5–50 ms LAN, ~20–80 ms cloud — symmetric across same-room
  players, so it's fair in practice.

**False-press check:** server compares `press.serverReceivedTs` against the
`TIMER_FIRED` or `SHOW_IMAGE(target)` server timestamp. If press arrived before the
event, lockout.

**Optional v2 — NTP-style offset estimation:**
Phone sends `T1`; server reflects `T2`, `T3`; phone receives at `T4`.
`offset = ((T2 − T1) + (T3 − T4)) / 2`. Compensate `clientTs` and use that for
sub-20 ms tie-breaking. Only needed if raw server-receive time proves unfair.

---

## Recommended tech stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| TV receiver | Vanilla HTML/JS + Google CAF | Required by Chromecast; same page works in browser-on-HDMI |
| Phone controller | Vanilla HTML/JS PWA | Single large button; no framework overhead needed |
| Server | Node.js + `ws` | Single-file, trivial to deploy |
| Hosting (server) | Fly.io free tier | WebSocket-friendly, zero cost at this scale |
| Hosting (static) | Cloudflare Pages | Free CDN for receiver + controller HTML |
| Images | Phosphor Icons (MIT) | Consistent flat style, SVG, easy to extend |
| Animations | CSS + Canvas 2D | Fireworks on winner phone; countdown ring on TV |

No React, no bundler for v1. The complexity doesn't justify the toolchain cost.

---

## Proposed file structure

```
party-game/
  server/
    index.js          — WebSocket server, room management, state machine
    gameLogic.js      — round logic, scoring, false-press adjudication
  client/
    receiver/
      index.html      — Chromecast receiver (+ browser-on-HDMI)
      receiver.js     — TV display: countdown, image stream, scoreboard
    controller/
      index.html      — Phone controller
      controller.js   — WS connect, big button, lockout UI, fireworks
  assets/
    images/           — 20 flat icon PNGs/SVGs for mini-game 2
  README.md
```

---

## Open questions

- **Image set:** finalise the 20 icons — commission custom art or use Phosphor SVGs
  rendered to PNG at 256×256.
- **Sound:** browser `AudioContext` beeps for countdown ticks; a short fanfare on win.
  Works cross-platform without install.
- **Apple TV AirPlay:** verify the receiver page renders correctly when mirrored —
  likely just a viewport size issue.
- **Chromecast publishing:** $5 registration + Google review (typically 24–48 h).
  During development, whitelist test devices in the Cast Developer Console — no
  registration needed for internal testing.
- **Mobile Safari vibrate:** iOS silently ignores `navigator.vibrate()`. Use a
  `transform: scale(1.15)` flash on the button as a visual substitute.
- **Room persistence on disconnect:** v1 — disconnect clears the room. V2 — 60 s
  rejoin window by room code.
- **Mini-game selection:** random each round, or player vote, or alternating? Simplest:
  server alternates 1 → 2 → 1 → 2 … with a random start.
