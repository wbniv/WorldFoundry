# Investigation: Multiplayer, voice chat, and mobile-native input

**Date:** 2026-04-14
**Status:** Deferred — plan captured for future work, not scheduled. Depends on the mobile port landing.
**Depends on:** `docs/investigations/2026-04-14-mobile-port-android-ios.md`.
**Related:** `docs/investigations/2026-04-14-jolt-physics-integration.md` (variable tick rate is load-bearing; constrains multiplayer sync model).

## Context

Three related-but-distinct concerns, bundled because they share the mobile-port dependency and because they interact (a multiplayer board game on tablets wants voice; voice needs a transport that the multiplayer sync layer can share; unique input features are what make a mobile multiplayer game feel *mobile* instead of a ported console game):

1. **Multiplayer.** Target reference points: *Mario Party on a phone* — 2–4 players, shared state, mixed turn-based + real-time mini-games — and *board games on tablets* — 2–6 players, mostly turn-based, small state, sometimes hidden information.
2. **Voice chat.** Players not in the same physical room; need usable voice without building a VoIP stack from scratch.
3. **Mobile input.** Mapping the existing joystick-bitmask input to touch, and more interestingly, exposing input channels that don't exist on a joystick at all — gyro, mic, camera, haptics, multi-touch chords.

WF's relevant existing constraints: the tick rate is variable and load-bearing (see memory); the scripting layer is mailbox-based, which is a natural fit for event-stream multiplayer sync; the existing input abstraction is a joystick bitmask (`EJ_BUTTONF_*`) exposed to scripts via mailbox 3024 (`INDEXOF_INPUT`). None of these force specific multiplayer or input decisions, but they shape which designs are cheap and which are expensive.

Intended outcome of this plan: a menu of decisions the project can make, with recommendations for the Mario-Party-scale target. Not a commitment to build any of this — a map of the terrain so when one piece becomes real, the surrounding implications are visible.

---

## Part 1 — Multiplayer

### Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Target scope | **2–4 players (hard cap 6), session-based, synchronous** | Mario-Party / small-group-board-game bracket. Rules out MMO-scale, rules out asynchronous ("play your turn by tomorrow"), keeps session-state model simple. |
| Topology | **Host-authoritative with one player as host**; others are clients | Simpler than full P2P mesh; cheaper than a dedicated server. Host is determined by who creates the lobby. Lost-host recovery is a follow-up concern. |
| Transport | **WebRTC data channels** (primary); WebSocket fallback via a relay for NAT-hostile networks | WebRTC gives P2P + NAT traversal via STUN, + voice on the same connection. Data channels carry game messages; audio tracks carry voice. WebSocket fallback exists when P2P fails (carrier-grade NAT, hostile firewalls). |
| STUN / TURN | **Public STUN (Google / Cloudflare free tier) + self-hosted TURN when we need relays** | STUN is free and stateless. TURN carries actual traffic, costs bandwidth; deferred until measured need. |
| Sync model | **Event-stream over mailbox deltas, host-authoritative** | The mailbox system is already the engine's shared-state abstraction. Host owns truth; "mailbox N changed to V at frame F" is the wire message; clients apply. Small (bytes-per-delta), already-serialised game state. |
| Lockstep sim? | **No** | Lockstep requires deterministic physics + fixed tick rate; WF has neither, and the variable tick is not negotiable. Event-stream sidesteps the problem — only the host runs authoritative physics, clients render what the host reports. |
| Hidden information | **Per-player mailbox scopes** — some mailboxes are private to one client | Host knows everything; clients receive only the deltas they're allowed to see. Lets board games with hidden hands work naturally. |
| Lobby / matchmaking | **Invite codes (6-char) + deep links** for v1; platform-integrated matchmaking (GameKit / Play Games) as a follow-up | Invite code is minimum viable — host shares a code, joiners type it. Deep links let "tap this link in iMessage" join the lobby. Platform matchmaking is polished but ties the game to one store's ecosystem. |
| Session persistence | **Host-side snapshot every N frames; resume on reconnect** | Short drops (tunnel, lock screen) rejoin automatically. Full-session persistence ("finish tomorrow") is a follow-up — needs cloud storage. |
| Anti-cheat | **Trust all peers in v1** | Casual play with friends does not justify the cost. Revisit when the game leaves the trust-your-friend context (public matchmaking, leaderboards). |

### Why mailboxes are the right sync primitive

The existing mailbox system is:
- A uniform shared-state store every script can read/write.
- Already named (`INDEXOF_*`) and enumerated at engine init.
- Per-actor scoped (`MailboxesManager::LookupMailboxes(actorIdx)`), so "player 2's mailbox 3024" is addressable distinctly from "player 1's mailbox 3024".
- Small — each mailbox is a single `Scalar` (f32 today).

The multiplayer wire format is therefore *just*: `(actor_id, mailbox_id, new_value, frame_number)`. No custom serialisation per game-object type, no schema to maintain. Adding a new game feature that needs to sync automatically syncs if it writes to a mailbox.

The host-authoritative flavour means: clients write their *input* mailboxes locally and broadcast the write to the host; the host runs game logic and broadcasts the resulting mailbox deltas back. Clients do not run game logic themselves — they apply deltas and render.

### Implementation phases (multiplayer)

**Phase 1 — single-machine harness.** Two `wf_game` processes on one machine, communicating over local sockets. Host-authoritative mailbox-delta protocol. Snowgoons-with-2-players: player 1 controls one actor via keyboard, player 2 via gamepad. Validates the sync model before any networking complexity.

**Phase 2 — WebRTC transport.** Vendor `libdatachannel` (C++ WebRTC library, MIT). Replace the local socket with a WebRTC data channel. STUN via Google's public servers. Test across two devices on the same Wi-Fi.

**Phase 3 — lobby and invite codes.** Lightweight signalling server (tiny Go/Node service, or serverless Cloudflare Worker) that exchanges WebRTC offers/answers keyed by invite code. 6-char alphanumeric codes; one-time-use.

**Phase 4 — cross-network play.** TURN relay (self-hosted `coturn`, or Twilio/Cloudflare TURN paid tier) for clients that cannot P2P. Measure relay usage to decide hosting approach.

**Phase 5 — hidden information and session snapshots.** Per-mailbox visibility rules (a small bitmask: "players who can see this mailbox"); snapshot every N frames for rejoin.

### Open questions (multiplayer)

- **Frame numbering under variable tick rate.** Clients apply deltas "at frame F" — but variable tick means clients' frame F may not be the host's frame F. Workaround: timestamp deltas in wall-clock ms; interpolate on the client. Simpler than it sounds; the variable-tick constraint costs us lockstep determinism but does not cost us event-stream playability.
- **Mailbox write conflicts.** Two clients write the same mailbox "simultaneously"? Host serialises by receive order. Document that host-order is the tiebreaker; design games so conflicts are rare.
- **Bandwidth envelope.** 4 players × 60 deltas/sec × ~20 B/delta ≈ 5 KB/s per player. Negligible. Voice dominates bandwidth (see Part 2).
- **Reconnection semantics.** If the host drops, game ends? Host-migrates to longest-connected peer? v1 answer: game ends. Host-migration is a follow-up.

---

## Part 2 — Voice chat

### Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Stack | **WebRTC audio tracks on the same peer connection as game data** | One NAT traversal, one TURN relay, one code path. WebRTC has built-in echo cancellation, noise suppression, Opus codec, volume levelling. Free. |
| Codec | **Opus at 24 kbps VoIP profile** | WebRTC default. Fine quality for voice. |
| Push-to-talk vs open mic | **Push-to-talk default, open mic opt-in per player** | Open mic is a privacy hazard (background audio, bystanders captured). PTT is socially and legally cleaner. A dedicated on-screen "talk" button or a held phone gesture. |
| Per-peer mute | **Always available, client-side** | Abuse safety valve. Mute state is local — no host coordination. |
| Spatial audio | **Out of scope** | Cute for some games, not load-bearing for Mario Party. |
| Recording / moderation | **None in v1** | Recording voice creates liability (GDPR, wiretap statutes). Moderation without recording is limited to "mute / block". Revisit if the game reaches scale where abuse reports matter. |
| Platform audio APIs | **Android: OpenSL ES / AAudio (via WebRTC lib). iOS: `AVAudioEngine` (via WebRTC lib).** | WebRTC's audio backends abstract both; no platform-specific audio code in WF. |
| Device permissions | **Request mic permission on first PTT press, not at app launch** | Users grant permissions more willingly in context. Graceful degrade if denied: "Voice chat disabled." |

### Implementation phases (voice)

Voice is mostly a WebRTC configuration concern — once Part 1 Phase 2 has WebRTC data channels, adding audio tracks is ~100 lines of glue.

**Phase 1 — plumb an audio track.** Add `libdatachannel`'s audio track to the existing peer connection. Capture from mic via platform audio backend (WebRTC handles this). Route received audio to the platform speaker. Hardcode open mic first; no UI.

**Phase 2 — PTT UI.** On-screen button; holding sends, releasing stops. Debounce fast presses.

**Phase 3 — mute matrix.** Per-peer mute toggle in a simple roster UI.

**Phase 4 — permission handling + fallback.** Graceful denial handling; surface "voice unavailable" without failing the game.

### Open questions (voice)

- **Echo in small rooms.** If two players in the same physical room both have mics open, feedback loop. WebRTC's echo cancellation handles same-device loops but not cross-device. Mitigation: "are you in the same room?" toggle disables voice for co-located peers.
- **Bandwidth on cellular.** 24 kbps × 3 peers ≈ 72 kbps inbound. Fine on 4G. Users on metered plans notice. Consider a "voice off" default on cellular.
- **Legal / store policy.** Some app stores require a code-of-conduct + reporting for apps with voice. Research before submission.

---

## Part 3 — Mobile input

### Joystick-to-touch mapping

The mobile-port plan already covers the floor: an on-screen dpad + buttons emitting the existing `EJ_BUTTONF_*` bitmask. That's viable but lowest-common-denominator. Options ranked by fit:

| Mapping | Fit | Notes |
|---------|-----|-------|
| **Fixed on-screen dpad + buttons** | Minimum viable | Works for every joystick game. Universally disliked by players. |
| **Floating virtual thumbstick** (stick spawns where you touch on the left half) | **Recommended default for directional games** | Better than fixed dpad. Used by most modern mobile action games. Tracks thumb drift. |
| **Tap-to-move + gestures** | For top-down / point-and-click only | Not compatible with joystick-bitmask semantics directly; would need a higher-level input event. |
| **Tilt-to-steer** (accelerometer/gyro) | **Recommended for racing-style mini-games** | Maps naturally to left/right as tilt angle ∈ [-1, +1]; piggybacks on existing joystick axes. Fun, tactile. |
| **External gamepad (MFi / Android gamepad)** | **Support as first-class alongside touch** | Plumbing through iOS GameController / Android InputDevice is one-day-of-work per platform. Plenty of players have a controller paired. |
| **Keyboard (iPadOS with keyboard)** | Free if we're already Linux-keyboard-aware | iPadOS keyboard events arrive through the same input layer as external controllers. |

Decision: **support floating virtual thumbstick + on-screen buttons + external gamepad simultaneously.** Detect which input device produced the last event; pick UI accordingly (hide the touch dpad when a gamepad is active).

### Unique phone features — menu with fit notes

Not "must use all of these" — a menu the game designer picks from per mini-game. Catalogued because the showcase value is real and the engine should not accidentally close doors on any of them.

| Feature | API path | Fit for Mario-Party-style | Showcase idea |
|---------|----------|---------------------------|---------------|
| **Gyro** | `CMMotionManager` / Android `SensorEvent.TYPE_GAME_ROTATION_VECTOR` | High | Tilt-based maze mini-game; golf aim refinement |
| **Accelerometer** | Same sensor stacks | High | Shake to roll dice (literally), pour drinks, scramble eggs |
| **Multi-touch** (up to 10 fingers) | Native on both | High | Cooperative "everyone touches a spot at once" mini-games; chord-based rhythm games |
| **Microphone (non-voice)** | Audio input APIs | Medium-high | Blow to inflate balloons / propel sailboats (Wii / Zelda: PH precedent); loudest-singer mini-game |
| **Front camera + face tracking** | `ARKit` / `ARCore Face` | Medium | "Don't laugh" or "make this face" mini-games; expression-driven avatars |
| **Back camera (AR)** | `ARKit` / `ARCore` | Medium | Project the game board onto the player's real table; treasure-hunt mini-games |
| **Haptics** | iOS `UIImpactFeedbackGenerator` / `CHHapticEngine`; Android `Vibrator` / `VibrationEffect` | High (feel, not gameplay) | Distinctive "you just stepped on a banana peel" taps; rhythm-game pulse |
| **GPS / location** | Standard platform APIs | Low (for this scope) | Asynchronous "where-in-the-world" party prompts |
| **Bluetooth / proximity** | Core Bluetooth / Nearby Share | Medium | "Tap phones to trade items"; proximity-only mini-games |
| **NFC** | iOS NFC / Android NFC | Low | Figurine-based unlocks (amiibo-style); outside scope unless product has physical merch |
| **Push notifications** | APNs / FCM | High (for turn-based) | "It's your turn" poke for long-session board games |
| **Share sheet / universal links** | Platform | **Must-have** for invite-code flow | "Join my game" link shares to any messaging app |
| **Taptic / rich haptics** | iOS Core Haptics; Android `VibrationEffect.Composition` | Medium | Texture feedback under finger; drum-roll anticipation |
| **Pencil / stylus (iPad)** | `UIPencilInteraction` | Low for Mario Party; high for drawing games | Pictionary-style drawing mini-games |
| **Split-screen / two-player-one-device** | iPad or landscape phone; just render two viewports | High | Pass-the-device is classic Mario Party vibe |

### Implementation phases (mobile input)

**Phase 1 — floating virtual thumbstick + on-screen buttons.** Replaces the fixed dpad from the mobile port plan. Thumbstick spawns where the player's thumb lands on the left half; tracks drift. Scripts see the same `INDEXOF_INPUT` mailbox.

**Phase 2 — external gamepad support.** iOS `GCController`, Android `InputDevice`. Events route into the same joystick bitmask. UI hides touch controls when a gamepad is live.

**Phase 3 — sensor inputs (gyro / accelerometer).** Expose as new joystick axes — `INDEXOF_TILT_X`, `INDEXOF_TILT_Y`, `INDEXOF_SHAKE_MAGNITUDE`. Mini-games read these the same way they read stick axes today. Normalised to revolutions for tilt angle (applying the WF-wide revolution-unit convention).

**Phase 4 — microphone amplitude (non-voice).** A single `INDEXOF_MIC_LEVEL` mailbox, 0.0–1.0 RMS over the last ~50 ms. Supports blow-to-win mini-games without needing speech recognition.

**Phase 5 — haptics.** A new `write_mailbox(INDEXOF_HAPTIC_EVENT, preset_id)` surface where `preset_id` maps to a small library (`TAP_LIGHT`, `TAP_HEAVY`, `SUCCESS`, `FAILURE`, `ROLL_DICE`). Per-platform implementations translate to Core Haptics / VibrationEffect compositions.

**Phase 6 — front-camera face-expression channel (stretch).** `INDEXOF_FACE_SMILE` (0–1), `INDEXOF_FACE_MOUTH_OPEN` (0–1), etc. ARKit / ARCore Face Tracking surface common blendshapes. Opt-in per mini-game — camera permission prompt.

**Phase 7 — AR / back-camera scenarios (stretch).** Deep enough to be its own plan; placeholder here. Likely only a subset of mini-games use it.

### Open questions (mobile input)

- **Sensor-axis units.** Tilt in revolutions is the obvious call (WF convention). Shake magnitude: normalised 0–1 or raw m/s²? Lean normalised so scripts do not need to know device-specific gravity calibration.
- **Haptic latency and abstraction level.** Core Haptics lets you author custom patterns; Android's equivalent is thinner. The "library of preset IDs" surface is the lowest common denominator; custom patterns are a follow-up.
- **Permission fatigue.** Mic, camera, motion sensors, location — each is a permission prompt. Cluster them: only ask when a mini-game uses that channel, not at launch.
- **Calibration.** Gyro and accelerometer need per-device calibration for consistency (orientation at start of tilt mini-game = "neutral"). A calibration step per mini-game is a UX cost; consider a single at-launch calibration.

---

## Critical files (across all three parts)

| File | Change |
|------|--------|
| `wfsource/source/net/` (new tree) | Mailbox-delta protocol, WebRTC peer wrapper |
| `wftools/vendor/libdatachannel-<ver>/` | New — WebRTC library (MIT) |
| `wfsource/source/scripting/` (mailbox manager) | Per-mailbox visibility bitmask for hidden-info |
| `wfsource/source/hal/android/`, `wfsource/source/hal/ios/` | New sensor and mic input impls |
| `wfsource/source/hal/` (interface) | Haptic output surface |
| Lobby signalling server (language TBD) | New, out of the WF repo — its own small service |
| Docs | `docs/multiplayer.md` (wire protocol), `docs/mobile-input.md` (input surface) |

## Verification

1. **Two-process local parity.** Phase 1 of Part 1: two `wf_game` processes on the same box play snowgoons together; desync-free over a 10-minute session.
2. **Two-device Wi-Fi.** Phase 2 of Part 1: two phones on the same Wi-Fi, WebRTC P2P, snowgoons together.
3. **Cross-NAT play.** Phase 4 of Part 1: one phone on home Wi-Fi, one on cellular; TURN relay kicks in; works.
4. **Voice round-trip latency.** Part 2 Phase 1: measured mouth-to-ear latency on the same Wi-Fi; target < 200 ms. Above that, feels bad.
5. **Gamepad + touch hybrid.** Part 3 Phase 2: pair a controller, remove it, re-pair; touch UI shows/hides correctly.
6. **Sensor mini-game.** Part 3 Phase 3: a tilt-maze snowgoons variant runs; reads `INDEXOF_TILT_X/Y`; plays as expected.
7. **Invite-code flow.** End-to-end: host creates code, shares via iMessage deep link, joiner opens link, game begins. No account signup.

## Follow-ups (out of scope)

1. **Host migration.** If host drops, longest-connected peer becomes host. Non-trivial: needs state snapshot and election protocol.
2. **Asynchronous play.** "Play your turn by tomorrow." Requires server-side state storage. Own plan.
3. **Platform matchmaking.** GameKit (iOS) and Play Games (Android) integration for friend lists + invites without a custom signalling server.
4. **Public lobbies / random matchmaking.** Requires backend; trust model changes; moderation becomes real.
5. **Anti-cheat.** Host verification, physics-rule checking, replay auditing.
6. **Spectator mode.** Read-only peer that receives deltas but can't write inputs.
7. **Cross-platform multiplayer.** Android + iOS + (future) desktop in the same lobby. Protocol is transport-agnostic; the real work is feature parity.
8. **Per-mini-game feature gating.** A mini-game that uses the back camera should not even list on a device without one.
9. **In-game chat (text).** Easier than voice; lower latency requirements; moderation still applies.
10. **Moderation, abuse reporting, code of conduct.** Required to ship in most stores once voice is involved.

## Open questions (cross-cutting)

- **Minimum network for "playable."** 4G? 3G? Wi-Fi only? Affects whether voice is a core feature or an opt-in.
- **Session length.** 20-minute Mario Party vs 3-hour board game changes the reconnection-semantics bar.
- **Story for "one device, multiple humans."** Pass-the-phone for turn-based is classic party-game fare. Does it compete with or complement the multi-device story? Both are cheap to support; let designers choose per game mode.
- **Server hosting responsibility.** Signalling + TURN + (future) session persistence require someone running a service. WF is GPL source; hosting is a commercial concern. Decide whose problem this is before shipping anything that can't work fully P2P.
- **Does WF need a real replay format?** Event-stream sync already implies "every session is a replay log." Persisting it to disk enables bug repro, bragging clips, and deterministic analytics. Near-free capability; would be a small follow-up plan.
