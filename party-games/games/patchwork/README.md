# Quilt Night / Patchwork Doodle development project

An independent JavaScript prototype of the researched Doodle rules, with
original visuals and interchangeable skins. No code, shape definitions or
assets from the community implementations have been copied into the runtime.
Commercial naming remains undecided. The archived publisher PDF is a research
reference, not a distributable app asset.

## Play locally

From the repository root:

```sh
npm ci --prefix party-games/platform/server
WF_GAME=patchwork PORT=8096 node party-games/platform/server/index.js
```

Open [the phone interface](http://localhost:8096/controller), enter a name and
choose Create game. Open its shared-display link in another browser window,
or use [the shared display](http://localhost:8096/receiver) first to create a room.
The shared display shows a room code and join QR. Open the displayed join URL on each phone
(or in separate browser tabs), enter names, then start from the first player's
phone. Both portrait and landscape are supported. Only the host advances turns;
every active player and the shared display must be online.

Phones on the same LAN can use the computer's LAN hostname/IP instead of
`localhost`. If running behind HTTPS or a proxy, set `WF_PUBLIC_ORIGIN` to the
public HTTPS origin so QR codes use the reachable address. Do not publish this
development server as a production service without deployment hardening.

## Automated playthrough

From the repository root:

```sh
task patchwork:playthrough
task patchwork:playthrough HEADED=1
```

This starts an isolated local server on an available port, plays all 18 turns
through two browser phone interfaces, runs scoring, checks portrait/landscape
and refresh recovery, and saves screenshots plus `playthrough.log` and
`server.log`. It prints a timestamped destination under `docs/diagnostics/`
and stops its server afterward. Use `OUT=...` to choose a destination,
`SLOW_MS=...` to change visible-play speed, or `ORIGIN=...` to use an existing
server. Requirements: installed server dependencies, Python Playwright and
Google Chrome. The command returns nonzero on a failed assertion.

For a physical Chromecast using an already running HTTPS game host:

```sh
task patchwork:playthrough:tv
```

This builds and freezes automated and ordinary APKs locally, uses normal
coordinator pool allocation, runs a full game with a randomly chosen 2–6 simulated controllers
inside the owned TV session, shows every player’s committed quilt together
for four seconds after each turn, downloads evidence, then restores and checks the
ordinary play build on the allocated device. Build receipts, source hashes,
watch logs and both session receipts are archived in the printed directory.
The command defaults to the temporary development host at
`https://collections-timing-riding-computing.trycloudflare.com`.
Override it with `ORIGIN=https://your-game-host` when the hosting URL changes.
`POOL=...` and `OUT=...` are optional. No raw device commands are used.
Interrupting a watcher leaves its job running; the saved submission identifies
the job to follow through `task chromecast:watch JOB=...`.

## Implemented

After every committed turn, the TV shows all active players’ finished quilts
on one screen. The host taps Continue on their phone to reveal the next turn
or enter scoring preparation. This shared phase survives display/controller
refreshes; autoplay uses the same Continue command after four seconds.

- Independent geometry: rotation/reflection, atomic placement, connected cuts.
- Per-room server authority; one to six players; late joiners wait for next game.
- Starting patches, three six-turn rounds, die movement, discard/carry-over,
  final three-card choice, passing, four special actions and editable readiness.
- Draft revisions, stage identities and duplicate-action handling.
- Rectangle scoring, historical round boards, empty-cell deduction and shared
  victories. The host controls each player's six-step TV score presentation.
- Phone placement by tap, drag or directional buttons; undo the current draft;
  original linen/night/paper visual themes independent of game state.
- TV common card pool, selected patch, readiness, intermediate score boards,
  join QR, final score counting and standings.
- Server-issued reconnect credentials, five-minute seat retention, connected
  host transfer, offline-seat withdrawal and receiver snapshot/reconnect hooks.
- Configurable Cast application ID and room-binding namespace. Actual Cast
  launch remains unverified.

## Explicit development limitations

`cards.js` generates our own deterministic connected shapes: ten seven-cell
starting fixtures and thirty patch fixtures. **This is not the verified physical
card inventory.** All game screens label it as a development deck. Replace it
with independently verified data before claiming fidelity to the edition.

Rules interpretations in this prototype allow compatible specials together,
including a repeated action already used earlier in the same draft. During
scoring, a neighbor/cut placement is allowed after passing the last patch;
extra-cell actions remain available. These interpretations need review against
publisher clarifications before a faithful release.

The game is stored in server memory. A server restart ends existing games.
Phone credentials are retained in sessionStorage, so reload/reconnect can
resume, but closing the tab and opening a fresh one creates a new seat. No
account system, durable saves, native app-store packages, paid content or
production hosting have been implemented. Themes are early visual treatments,
not finished artwork packs.

## Chromecast testing

A complete [TV state screenshot gallery](../../../docs/diagnostics/patchwork-tv-review/index.html)
contains 106 frames from physical Chromecast job J-2104f8e72e64 and 318 browser
state/skin previews. The six-player long-name check exposed overflow in the
lobby, readiness, round results and standings; these layouts now fit the HD
TV's 960×540 CSS viewport. Browser replay checks text bounds and footer overlap
in all three skins. Physical recording completed the full game and ceremony,
and cleanup was verified. The ordinary play APK was restored afterward.


Use the shared coordinator with normal pool allocation; it honors device
reservations. The [thin Android TV launcher](tv/README.md) is built, signed and
registered in the installed service. A complete two-player, 18-turn physical
session on Chromecast HD passed, including the final shared score ceremony and
verified cleanup: [receipt](../../../docs/diagnostics/patchwork-tv-J-f62e22b4423d/receipt.json)
and [TV screenshot](../../../docs/diagnostics/patchwork-tv-J-f62e22b4423d/screenshot.png).
The ordinary launcher also passed remote keys and Home/resume with the same
process: [receipt](../../../docs/diagnostics/patchwork-tv-J-bbb786952d30/receipt.json).
The simulated controllers run inside the owned TV session; physical phone
validation remains outstanding. This is an Android TV app; the Google Cast
sender-button path still requires receiver registration and stable hosting.

The current test origin uses temporary HTTPS hosting. Direct LAN hosting from
the user-owned Node server timed out on the TV; the coordinator's protected
address rules also reject user-owned server replies to TV addresses. No network
policy was weakened and no direct device control was used.

For a registered Cast custom receiver hosted at this server's `/receiver` URL,
set `WF_CAST_APP_ID` to the eight-digit application ID. The sender binds the room
using `urn:x-cast:org.worldfoundry.party` / `BIND_ROOM`, following
[Google’s custom-message receiver API](https://developers.google.com/cast/docs/web_receiver/core_features). Until registration is
configured, use a browser display; the game does not assume the old development
application ID launches this receiver.

## Validation

```sh
node party-games/games/patchwork/test/game.test.js
node party-games/games/patchwork/test/relay.test.js
npm test --prefix party-games/platform/server
# With the local game server running, Python Playwright and Chrome installed:
python3 party-games/games/patchwork/test/browser-check.py
```

The browser test plays two players through all 18 turns and three scoring
rounds, refreshes a phone and receiver, and checks the final TV ceremony.
Screenshots are in [test/evidence](test/evidence/). Browser tests do not launch
or control any physical Chromecast or phone. Dependency notices for server
bundles are in [THIRD_PARTY_NOTICES.md](../../platform/server/THIRD_PARTY_NOTICES.md).

See the [implementation plan](implementation-plan.md) and its
[visual browser version](implementation-plan.html). Research findings remain
in [digital platform research](research/digital-platforms.md).
