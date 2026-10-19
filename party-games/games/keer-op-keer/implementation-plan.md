# Keer op Keer Chromecast implementation plan

Date: 2026-10-04  
Status: Draft for Will’s review. Implementation has not started.  
Project: [Keer op Keer](README.md)

Build a couch multiplayer game for 2–6 players. Each player uses a phone
browser to choose dice and mark their own board. Chromecast shows the shared
dice pool, whose turn it is, who is still choosing, completed columns and
colors, and the score. Reuse the existing party-games platform.

Chromecast presents the shared elements: rolled dice, available choices,
turn order, player readiness, bonus claims and results. Phones provide each
player’s board and move controls. All proposed defaults below are open for review. Approval of
this plan is required before starting Phase 0 or changing game/platform code.

## Existing digital versions

Yes: this game already has digital editions. Checked on 2026-10-04 using
developer and storefront listings; these apps have not been installed or
play-tested during planning. Availability may vary by storefront region.

| Product | Platforms | Advertised capabilities |
| --- | --- | --- |
| Outline Development’s officially licensed Encore! Digital Edition, also named Noch mal! / Keer op Keer in regional listings | [Android](https://play.google.com/store/apps/details?id=de.development.outline.nochmal), [iPhone/iPad](https://apps.apple.com/gb/app/encore-digital-edition/id1374587455); the [developer also lists Amazon](https://www.outline-development.com/en/games/) | Solo mode, two players sharing one device, automatic dice selection/turn completion, digital scoresheet and dice modes. The Apple listing additionally supports installation on compatible Apple silicon Macs and Apple Vision. |
| Ster Software’s Keer op Keer Sheet | [Android](https://play.google.com/store/apps/details?id=nl.stersoftware.xopx), [iPhone/iPad](https://apps.apple.com/nl/app/keer-op-keer-sheet/id1597275546) | Digital boards, built-in dice, automatic scoring, sheet editor and multiple modes. The description supports one phone per player but does not establish synchronized network rooms or a shared TV receiver. |

The reviewed listings do not advertise Chromecast coordination with a
separate phone per player. This is a gap in the verified descriptions, not
proof that no such product exists. Browser dice rollers also exist, such as
[Digitale Dobbelsteen](https://digitaledobbelsteen.nl/spellen/keer-op-keer);
they should not be treated as verified full multiplayer adaptations.

The proposed value of this project is the shared TV experience: synchronized
turns, a single authoritative dice pool, simultaneous bonus resolution and
individual phone boards. Phase 0 will compare the existing apps’ board
interaction, confirmation flow and multiplayer features before finalizing
our UI. Any purchase or installation for that comparison happens after plan
approval. A public release’s branding/assets/licensing approach remains a
release decision; existing app licenses do not transfer to this project.

## Proposed experience

| Screen | What players see and do |
| --- | --- |
| TV lobby | Join URL, QR code, room code, connected players and ready status. |
| Phone lobby | Enter name, join room, mark ready; host starts the game. |
| TV during play | Active player, turn number, three color dice and three number dice, reserved pair, remaining shared choices, player submission status, public bonuses and scores. |
| Phone during play | Own 15-column board, dice choices, Joker balance, selected cells, confirmation/pass controls, score breakdown and help. |
| TV turn recap | New columns/colors, bonus awards, score changes, next player. |
| Game over | Ranked results, score breakdown, ties, and host-controlled rematch. |

The phone shows “Roll” only to the active player. The server generates the
roll; TV animation illustrates the returned result. Players select a color
die and a number die, choose Joker values if necessary, tap cells, then
confirm. Selecting cells is a reversible local draft. Confirmation commits
one move; there is no undo after acceptance. Passing is always available.

On ordinary turns the active player commits first. Their two dice are then
unavailable to everyone else. Other players choose concurrently from the
remaining four dice; their selections do not consume dice for one another.
During the first three turns everyone may use all six dice, including the
active player’s pair. An active-player pass leaves all six available.

No default turn timer. Show who is still thinking without penalizing slow
players. The host may pause and explicitly remove an absent player, with a
confirmation explaining that their seat is forfeited for this game.

Show bonus/score summaries publicly. Keep live phone selections private.
Because tabletop players can inspect one another’s boards, provide a public
board overview on the TV during pauses/recaps, selected by the host; this
shows committed marks only. Default TV layout stays focused on coordination.

## Rules and simultaneous resolution

Use the [archived English rulebook](rules/encore-official-rules-en.pdf) and
[text transcription](rules/encore-official-rules-en.txt) as references.

- Use one verified base board for everyone, with columns A–O, start column H,
  five colors, stars, column rewards, color rewards and eight Joker uses.
  Record the board as explicit data and check every cell against the PDF.
- A move marks exactly 1–5 previously unmarked cells of the chosen color.
  They form one orthogonally connected group that touches an existing mark
  or includes a cell in H. Diagonal contact does not qualify.
- Each Joker die consumes one Joker use; using both consumes two. A number
  Joker allows 1–5, never six. No remaining uses means no Joker selection.
- Resolve every player’s accepted move/pass together at the turn boundary.
  Keep the bonus availability from the beginning of that turn. Players who
  complete the same previously unclaimed column that turn all get the higher
  value, regardless of which phone submitted first.
- Proposed ruling: apply that same simultaneous tie treatment to first
  completion of a color. The English text explicitly covers column ties but
  is less explicit about color ties; verify against Dutch rules/publisher
  clarification in Phase 0 and document the final ruling.
- Finish the entire turn when someone completes their second color. Everyone
  still gets their move/pass, then calculate final scores.
- Score completed columns + completed colors + unused Jokers − two per
  unmarked star. Break score ties by unused Jokers, then declare joint winners.

Turn numbers count individual rolls, rather than a full lap of the table.
Player order is fixed at game start; a removed seat is skipped. Late arrivals
wait for the next game. Rematch resets boards, awards and rolls and rotates
the starting player. Solo play and additional sheets are later extensions.

## Architecture and platform changes

Implement a game plugin under this directory, selected with
`WF_GAME=keer-op-keer`. Reuse the Node/WebSocket relay, room codes, Cast
launcher, receiver shell, controller shell and existing feedback helpers.

Proposed files:

```text
keer-op-keer.js             per-room authoritative state machine
rules.js                   move validation and score calculation
boards/base.json            verified board, stars and rewards
client/controller.js/.css   phone board and controls
client/receiver.js/.css     TV lobby, shared pool and recaps
test/                      rules, protocol and room integration tests
```

The server owns dice results, boards, Joker use, submissions, awards and
phase transitions. Phones send intent; they never submit trusted scores.
Assign each die a stable ID so identical results remain distinct physical
dice. Every command carries game ID, turn ID and action ID. Reject stale
commands; retries return the original acknowledgement without applying the
move twice. Version snapshots so reconnects cannot restore an older state.

Proposed flow:

```text
LOBBY → WAIT_FOR_ROLL → ACTIVE_CHOICE → OTHER_CHOICES → RESOLVE → TURN_RECAP
                             ↑                                      |
                             └──── WAIT_FOR_ROLL for next player ───┘
RESOLVE → GAME_OVER when a second color has been completed
```

On the first three turns, the UI may let other players draft immediately,
but commit processing still uses the same turn boundary. Pause preserves
the underlying phase and accepted submissions.

Use game-prefixed messages for roll, submit, pass, pause, resume, rematch,
snapshot request and acknowledgements. Broadcast public state; send personal
boards and validation feedback through `services.sendTo`. Public board
inspection uses an explicit public projection of committed marks.

Required shared-platform work should be small and covered by regressions:

- Explicit receiver-ready/snapshot handshake after its module mounts. A
  reconnecting or newly attached TV must receive current game state without
  waiting for a player action.
- Receiver WebSocket reconnect with retry/backoff and restoration to the
  same room; current receiver code closes without reconnecting.
- Game-specific seat retention beyond the current 20-second grace. Proposed
  default: retain a disconnected seat for the match, pause if it blocks the
  turn, and let the host remove it. Preserve the existing default for other
  games. Use a server-issued resume credential; a name alone cannot reclaim
  a seat. Keep public room codes separate from seat credentials.
- Presence and receiver connectivity notifications, host transfer after
  explicit departure, and late-join handling. Reconnection restores accepted
  submissions; a lost acknowledgement cannot duplicate a move.
- Resolve the launch/join sequence: the existing phone entry gate needs a
  room code, while a fresh receiver creates one. Provide a launch-first host
  entry or sender-to-receiver room binding, and prove that host and TV land
  in the same room. Everyone else joins using the displayed QR/code.

An in-memory server is enough for the first release: phone/TV reconnects
restore the match while the server lives. A server restart ends the match
with a clear message. Durable saves are a later phase, not an implied promise.

## Implementation phases

| Phase | Deliverable | Exit condition |
| --- | --- | --- |
| 0 — Rules and Cast feasibility | Existing-app comparison, verified board data specification, color-tie ruling, phone/TV wireframes, current hosting/app-ID audit, coordinator test-route definition. | Comparison findings and rules/board specification are reviewed; a minimal receiver can launch through a coordinator-owned session and join the same room as its host. |
| 1 — Rules engine | Pure validation/scoring module and deterministic per-room turn engine, without UI. | Tests cover adjacency, H starts, exact counts, Joker limits, first-three-turn exception, pass, simultaneous awards, final-turn completion and ties. |
| 2 — Phone board prototype | Responsive board, selectable dice, Joker choices, draft marks, confirm/pass and contextual help against a local test driver. | A player can make and correct a draft on a small phone; invalid selections explain the rule; the base board matches the reference. |
| 3 — Multiplayer browser game | Plugin integration, room lobby, public/private snapshots and synchronized turns with a browser TV. | Two and six simulated players finish deterministic games; duplicate/stale commands and separate rooms cannot corrupt state. |
| 4 — TV presentation and recovery | TV dice pool, reservations, status, recaps, public board inspection, QR joining, reconnect/pause/removal/rematch behavior. | A full browser playthrough survives lost connections, refreshes and lost acknowledgements; TV restore is immediate and scores agree everywhere. |
| 5 — Real Chromecast validation | Staged HTTPS/WSS deployment and complete sessions on both dedicated Chromecasts with real phone browsers. | Both devices pass launch/join, turns, final scoring, receiver recovery and rematch; captured evidence accompanies results. |
| 6 — Release polish | Guided first turn, accessibility pass, restrained feedback, documentation and approved release deployment. | Fresh users can join and finish a game; required tests pass; release URL/version and known limits are documented. |

Dependencies are sequential. Phase 2 may use fixtures before the multiplayer
protocol is ready. Phase 0 discovers Cast blockers early; browser work may
continue after approval if Cast registration or coordinator support needs
external changes, but device verification remains an explicit open gate.

## Phone usability and TV layout

The board is 15 columns wide, which makes individual cells too small on many
portrait phones. Start with a landscape board that fits the screen and a
portrait view with a scrollable/zoomable board, fixed dice/confirm controls,
and persistent selection count. Preserve the full board overview and start
column marker. Test this in Phase 2 before committing to the interaction.
Use tap-to-toggle cells and a clear-selection action; drag marking is optional
polish because it can conflict with scrolling.

Identify colors with distinct shapes/labels as well as color. Use visible
selection outlines, star/Joker labels, focusable cells and accessible names
such as “H4, blue, star, unmarked.” Disable confirmation until the draft is
valid, but always explain what remains to be selected. Confirmation becomes
“Submitting” until acknowledged, then “Waiting for other players.”

On TV, keep dice large and readable across the room. Mark reserved dice
visibly instead of removing them without explanation. Show “all six dice
available” during the opening turns and active-player passes. Keep the
room code visible, allow for overscan, and test at 720p and 1080p. Draw dice
with CSS/SVG for consistent device rendering; Unicode in the archived text
does not require reliance on TV font coverage.

## Cast delivery and device evidence

Use the existing Custom Web Receiver path. It needs app registration and a
reachable hosted receiver; test devices must be registered for unpublished
receivers. These requirements are described in Google’s
[receiver documentation](https://developers.google.com/cast/docs/web_receiver/basic)
and [registration documentation](https://developers.google.com/cast/docs/registration).
Use HTTPS/WSS for staging/release. Audit the current app ID and hosted URL;
the earlier platform plan leaves physical Cast verification pending.

The coordinator currently documents APK-centric Aquarium/Condo workflows.
Phase 0 must establish a supported Cast-web launch/input/capture workflow
within coordinator ownership. If an adapter is needed, specify and add that
support through the service’s maintained interface. Do not assume an
`APP=keer-op-keer` workflow already exists, or substitute direct ADB/Cast
control. Freeze/version web assets before each job; freeze an APK locally
first if the approved test route requires a packaged launcher.

Use `task chromecast:devices` and `task chromecast:queue`, submit with
`DEVICE=chromecast-test-01` or `DEVICE=chromecast-test-02`, follow with
`task chromecast:watch JOB=...`, and download with
`task chromecast:evidence JOB=... OUT=...`. Installation, launch, input,
capture and cleanup belong to one owned session. Coordinator downtime leaves
device testing pending; there is no direct-control fallback.

Save evidence under this project’s `evidence/` directory, identified by job
and build/version. Include TV captures, phone screenshots, sanitized event
logs and a concise result sheet. Never include seat credentials. Any manual
diagnostic command requested from Will writes to a named file, prints its
destination, and is read directly afterward.

The physical matrix covers both TVs, Android Chrome and iPhone Safari phone
controllers, two-player play and six-controller load. Verify foreground
return, brief network loss, receiver reload/relaunch, host departure and
late joins. iPhone players can join by QR even if launching Cast from their
browser is unavailable; establish a supported host launch route in Phase 0.

## Review decisions

Recommended defaults for approval:

1. Faithful base game, 2–6 players, shared dice choice tiles, one base sheet.
2. Existing web party-game platform and Custom Web Receiver deployment.
3. Untimed turns, explicit confirmation, host pause/removal, retained seats.
4. Simultaneous awards at turn boundaries; verify the color-tie ruling.
5. Public scores/bonuses and optional TV inspection of committed boards.
6. Initial release recovers client connections but does not survive server restart.

After Will reviews this document, revise any requested choices before
implementation. Approval to build does not mean the release is already
published; Phase 6 prepares a concrete release for review before deployment.
