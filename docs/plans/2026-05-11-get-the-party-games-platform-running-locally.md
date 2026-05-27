# Get the party-games platform running locally

**Status:** DONE (ephemeral) — server runs locally, npm deps install clean, game loop operational; live-browser verify is out-of-repo.

## Context

The repo at `/home/will/party-games/` is a Chromecast-style couch party-game
platform (relay server + receiver page + phone controllers). Three games are
plugged in already (reaction, image, worst-take-wins) and tests are green
per the README. The user just wants to actually launch it and play —
specifically the **reaction** game (the default `WF_GAME=reaction`).

The only blocker right now is that `platform/server/node_modules/` is empty —
deps have never been installed in this checkout. Once `npm install` runs,
`node index.js` boots the server and the three URLs in the README work.

## Steps

1. **Install deps** in `platform/server/`:
   ```sh
   cd /home/will/party-games/platform/server && npm install
   ```
2. **Start the server** (foreground, so logs stream into the conversation):
   ```sh
   cd /home/will/party-games/platform/server && node index.js
   ```
   Expect: `party-games platform ready on http://localhost:8080` +
   `game plugin: reaction`. I'll launch this as a background bash task
   so the user can keep going while it runs, and surface the log line.
3. **Open the three browser tabs** (user does this — they have the
   browser, I don't):
   - Receiver: <http://localhost:8080/receiver> — note the 4-letter
     room code in the header.
   - Host controller: `http://localhost:8080/controller?name=Alice&room=<CODE>`
   - Second controller: `http://localhost:8080/controller?name=Bob&room=<CODE>`
4. **Play.** Alice taps START → countdown → GO. First tap = 4 pts.
   First to 10 wins.

## Critical files (no edits planned)

- `platform/server/index.js` — entry, reads `WF_GAME` env (defaults to reaction)
- `platform/server/package.json` — declares the `ws` dep that `npm install` pulls
- `games/reaction/reaction.js` — state machine for the default game

## Verification

- Server log shows `party-games platform ready on http://localhost:8080`
  and `game plugin: reaction`.
- Receiver page renders a 4-letter room code in its header.
- A controller URL with that room code transitions the receiver to the
  lobby view and lists the player's name.
- Tapping START kicks off the countdown → GO sequence; tapping during GO
  awards points; first to 10 ends the round with a winner banner.

## Optional follow-ups (only if user asks)

- Switch game via `WF_GAME=image node index.js` or
  `WF_GAME=worst-take-wins node index.js`.
- Run the test suites listed in `README.md` §Tests.
