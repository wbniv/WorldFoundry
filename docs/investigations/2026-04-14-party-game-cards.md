# Investigation: Chromecast Card Games — Fill-in-the-Blank + Comic Strip

**Date:** 2026-04-14  
**Depends on:** `2026-04-14-party-game.md` (same platform stack — Chromecast receiver
+ phone PWA controller + Node.js WebSocket server)

Two game designs are covered here:

1. **"Worst Take Wins"** — fill-in-the-blank card game (Cards Against Humanity model)
2. **"Punchline"** — three-panel comic strip completion game (Joking Hazard model)

---

## Concept

A fill-in-the-blank card game for 3–10 players. One player per round is the **Judge**.
The TV shows a **Prompt card** with one or two blanks. Every other player picks one (or
two) **Response cards** from their private hand on their phone. The Judge reads the
anonymous submissions on the TV and picks the winner. Winner keeps the Prompt card as
a point. First to a configurable number of Prompt cards wins (default: 8).

The game is structurally identical to Cards Against Humanity, which released its
content under **CC BY-NC-SA 2.0** — that card content can be reused for non-commercial
builds, or replaced entirely with a custom deck.

---

## How it differs from the reaction-timer party game

| Concern | Reaction game | Card game |
|---------|--------------|-----------|
| Timing | Sub-second precision critical | Turn-based; no timing pressure |
| Phone UX | One giant button | Scrollable card hand + tap-to-select |
| TV display | Countdown / image stream | Prompt card → anonymous submissions → winner reveal |
| Players | 2–4 | 3–10 |
| Session length | ~15 min | 45–90 min |
| State machine complexity | Low | High (deal → submit → judge → score → rotate) |

---

## Platform targets

Same as the reaction game — no changes needed to the platform decision:

- **Chromecast** (primary) via Google CAF receiver HTML page.
- **Browser on HDMI** (free fallback — same page, no Cast SDK path needed).
- **Apple TV** via AirPlay mirror.
- Phone controller = Browser/PWA — reading cards on a phone screen benefits from a
  proper HTML scroll/tap UI; no install barrier matters even more at 10 players.

---

## State machine

```
LOBBY
  └─ [host starts] ──→ DEAL
        └─ [hands dealt] ──→ SHOW_PROMPT
              └─ [players submit] ──→ JUDGE_REVEAL
                    └─ [judge picks winner] ──→ SCORE
                          ├─ [no winner yet] ──→ DEAL (next round, rotate judge)
                          └─ [player reaches target] ──→ WINNER
```

### States in detail

| State | TV shows | Phone shows (non-judge) | Phone shows (judge) |
|-------|----------|------------------------|---------------------|
| LOBBY | Room code + QR, player list | "Waiting…" + player name entry | Same + "Start Game" button |
| DEAL | Brief "Dealing…" animation | New cards slide in | Same |
| SHOW_PROMPT | Prompt card, submission count `X / N` | Card hand; tap to select; Confirm button | "You are judging this round" |
| JUDGE_REVEAL | Submissions revealed one at a time (anonymous) | "Waiting for judge…" | Each submission tappable; tap to pick winner |
| SCORE | Winner + Prompt card animation; running scoreboard | Confetti if winner | Same |
| WINNER | Final scoreboard; fireworks full-screen | Fireworks if this player won | Same |

---

## Card mechanics

### Prompt cards (black cards)

- Contain one or two blanks (`____`).
- Two-blank prompts: each player submits **two** Response cards, read in order.
- Example single-blank: `"The class field trip was ruined by ____."` 
- Example double-blank: `"____ + ____ = my entire personality."`

### Response cards (white cards)

- Short noun phrases or sentence fragments.
- Player hand size: **7 cards**. After each round, draw back up to 7.
- A player's hand is private — only visible on their own phone.

### Deck size

- A playable game needs roughly **200+ Prompt cards** and **500+ Response cards**.
- CAH's base deck (CC BY-NC-SA 2.0): 90 Prompt + 460 Response. Freely usable for
  non-commercial builds.
- Custom decks: JSON files dropped into `assets/decks/`; the server loads all `.json`
  files in that directory on startup. Format:

```json
{
  "name": "Base Deck",
  "prompts": [
    { "id": "p001", "text": "The class field trip was ruined by ____.", "blanks": 1 },
    { "id": "p002", "text": "____ + ____ = my entire personality.", "blanks": 2 }
  ],
  "responses": [
    { "id": "r001", "text": "A bag of wet hair." },
    { "id": "r002", "text": "Puppets." }
  ]
}
```

---

## Phone UX design

The phone must show 7 cards in a readable, tappable layout. This is the hardest UX
challenge (the reaction game needed only one button).

### Card hand layout options

**A — Horizontal scroll strip (fan)**
Cards laid out horizontally; player swipes left/right. Tap a card to "raise" it
(expand to full-width preview); tap again to select/deselect.

**B — Vertical stack list**
Cards as a scrollable vertical list, full width. Easier to read long text; less
"card game" feel. Better on small screens.

**C — Stacked fan (CSS 3D)**
Cards fanned slightly with CSS transforms. Looks good in screenshots; fiddly to tap
on a 5-inch screen.

**Recommendation:** Option A (horizontal scroll) with a full-width tap-to-preview
gesture. Degrade to Option B on viewports narrower than 360 px.

### Submission flow (non-judge)

1. Prompt appears on TV and phone screen (small, at top).
2. Player scrolls hand, taps card → card "raises" with a full-width preview.
3. Tap "Select" to confirm. For two-blank prompts, repeat for a second card.
4. "Submit" button appears once required cards are selected.
5. Post-submit: phone shows "Waiting for others…" + how many have submitted (`X / N`).
6. If player hasn't submitted within a configurable timeout (default: 90 s), server
   auto-submits a random card from their hand and marks them `AUTO_SUBMITTED`.

### Judge flow

1. Phone shows "You are the Judge this round."
2. During SHOW_PROMPT phase: phone mirrors TV (prompt + submission count).
3. During JUDGE_REVEAL: each anonymous submission appears on TV one by one (judge
   taps "Next" on phone to advance). Final screen: all submissions listed.
4. Judge taps the winning submission on their phone. Server broadcasts winner.

---

## Server state machine — key events

```
Client → Server                     Server → All clients
─────────────────────────────────   ────────────────────────────────────────
JOIN(name)                    →     PLAYER_JOINED(id, name, allPlayers)
START_GAME(settings)          →     GAME_STARTED(judgeId, settings)
                                    DEAL_HAND(cards[])            // private, per-player
                                    SHOW_PROMPT(promptCard)
SUBMIT_CARDS(cardIds[])       →     SUBMISSION_COUNT(x, total)
                                    JUDGE_REVEAL_START(shuffledSubmissions[])
JUDGE_ADVANCE()               →     REVEAL_NEXT(submissionIndex)
JUDGE_PICK(submissionIndex)   →     ROUND_WINNER(playerId, cardIds, promptCard)
                                    SCORE_UPDATE(scores{})
                                    [if game over] GAME_WINNER(playerId)
```

Submissions are stored server-side as `{ submissionId, playerId, cardIds[] }`. Only
`submissionId` and `cardIds` are sent to clients during `JUDGE_REVEAL_START` — the
`playerId` mapping is revealed only after the judge picks a winner.

---

## Anonymity guarantee

The Judge must not know who submitted what until after they pick.

- Server shuffles submissions before broadcasting `JUDGE_REVEAL_START`.
- `playerId` is stripped from the reveal payload; only `submissionId` is sent.
- After `JUDGE_PICK`, server broadcasts the full mapping.
- Server never sends a player's hand to any other player.

---

## Deck / content pipeline

| Source | License | Notes |
|--------|---------|-------|
| Cards Against Humanity base deck | CC BY-NC-SA 2.0 | Free for non-commercial; ~550 cards. Download JSON from `crhallberg/JSON-against-humanity` on GitHub. |
| Custom deck (house rules) | Yours | Drop a JSON file into `assets/decks/`; hot-reloaded on next game start. |
| Themed expansion packs | Varies | Can be added as separate JSON files; server merges all loaded decks. |

The server randomises draw order at game start (Fisher-Yates shuffle). Discarded
Prompt and Response cards go to a discard pile and are not reshuffled unless the deck
runs dry mid-game.

---

## Chromecast TV display design

### SHOW_PROMPT screen

```
┌────────────────────────────────────────────────────────┐
│  Round 4 · Judge: Alex                                  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │                                                 │   │
│  │   The class field trip was ruined by ____.      │   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│         Submitted: 2 / 4                                │
└────────────────────────────────────────────────────────┘
```

### JUDGE_REVEAL screen (one submission at a time)

```
┌────────────────────────────────────────────────────────┐
│  The class field trip was ruined by ____               │
│  ─────────────────────────────────────────────────     │
│                                                         │
│         "A lukewarm thermos of sadness."               │
│                                                         │
│                          [2 more remaining]             │
└────────────────────────────────────────────────────────┘
```

### SCORE screen (after judge picks)

```
┌────────────────────────────────────────────────────────┐
│  ★  Sam wins this round!                               │
│                                                         │
│  "The class field trip was ruined by                    │
│   a lukewarm thermos of sadness."                       │
│                                                         │
│  SCORES                                                 │
│  Sam ████████ 4   Alex █████ 3   Jordan ███ 2           │
└────────────────────────────────────────────────────────┘
```

---

## Recommended tech stack

Same foundation as the reaction game:

| Layer | Choice |
|-------|--------|
| TV receiver | Vanilla HTML/JS + Google CAF |
| Phone controller | Vanilla HTML/JS PWA; CSS card layout |
| Server | Node.js + `ws`; deck loaded from JSON files at startup |
| Hosting | Fly.io (server) + Cloudflare Pages (static) |
| Card data | JSON files in `assets/decks/`; CAH base deck for bootstrapping |

**No framework for v1.** The phone UX is more complex than the reaction game's single
button, but still manageable in vanilla JS + CSS. If card-hand animation becomes
unwieldy, add a lightweight animation library (Animate.css or Motion One) — not a full
SPA framework.

---

## Proposed file structure

```
card-game/
  server/
    index.js            — WebSocket server, room management
    gameLogic.js        — state machine, deal, shuffle, scoring
    deckLoader.js       — load + merge JSON deck files
  client/
    receiver/
      index.html        — Chromecast receiver (+ browser-on-HDMI)
      receiver.js       — TV display: prompt, reveal, score
      receiver.css
    controller/
      index.html        — Phone controller
      controller.js     — hand display, card select, judge UI
      controller.css
  assets/
    decks/
      base.json         — CAH CC BY-NC-SA 2.0 base deck (or custom)
  README.md
```

---

## Shared infrastructure with the reaction game

Both games use the same:
- WebSocket server pattern (room code, player join, state broadcast)
- Chromecast receiver registration
- PWA phone shell (manifest, service worker skeleton)
- Cloudflare Pages + Fly.io deployment

They can share a **monorepo** with a common `server/lib/room.js` for room/player
management and diverge on game logic. Alternatively, ship as separate deployments
(different Cast App IDs, different URLs) if keeping them fully independent is cleaner.

---

## Open questions (Worst Take Wins)

- **Name / branding:** not "Cards Against Humanity". Working title: *Worst Take Wins*.
  Finalise before Cast App registration (App ID is tied to the name).
- **Content moderation:** CAH content is intentionally offensive. For a custom deck,
  decide the tone. A "family mode" flag (server-side deck filter) is trivial to add.
- **Timer on submissions:** 90 s default feels right; make it configurable in lobby
  settings (30 / 60 / 90 / unlimited).
- **Pick-2 prompts:** two-blank prompts require tracking card order; the server must
  store and display `[card1, card2]` as an ordered pair.
- **Spectator mode:** players who join after game starts could spectate (receive TV
  state but no hand). Deferred.
- **Deck expansion UI:** in-lobby deck picker (checkboxes per loaded JSON file).
  Server reports available decks on JOIN; host selects before START_GAME.
- **Card text length:** long responses can overflow the TV layout. Cap response card
  text at 120 characters; prompt cards at 160.

---

---

# Game 2: "Punchline" — Comic Strip Completion

## Concept

A three-panel comic strip game for 3–10 players. Each round builds a strip from left
to right on the TV. Two panels are dealt from the deck; players compete to supply the
funniest third panel from their hand. The Judge picks the winner. First to a
configurable number of wins (default: 7) takes the game.

Structurally modelled on **Joking Hazard** (Explosm Games), which uses the *Cyanide
& Happiness* comic art. A digital implementation needs custom panel art or a
licensing agreement — see §Art below.

---

## How panels work

Every card in the deck is a single comic panel: one or two characters, a background,
and optional speech/caption text. Cards are visually self-contained but gain meaning
from context.

### Special card type: red-border "setup" card

Some panels have a red border. A red-border card **always goes in position 1** of the
strip. When one is drawn, it sets a stronger, more specific scene — the strip tends to
be funnier and more coherent as a result.

### Round flow

1. **Draw phase:** server draws the top card of the shuffled deck.
   - If it has a red border → it becomes Panel 1; server draws a second card for
     Panel 2.
   - Otherwise → it becomes Panel 2; Panel 1 is empty (players must set the scene).
2. **Play phase:** all non-judge players pick one card from their hand to complete
   the strip (Panel 3 if panels 1+2 exist, or Panel 1 if only panel 2 was drawn).
3. **Reveal phase:** submissions shown anonymously on TV, one at a time. Judge taps
   through them on their phone.
4. **Judge picks:** winner keeps the deck card(s) as their point(s).
5. Rotate judge; draw back up to 7 cards.

---

## State machine

Same skeleton as Worst Take Wins, with one extra branch for the red-card draw:

```
LOBBY → DEAL
  └─ DRAW_PANEL
       ├─ [red border] ──→ SHOW_STRIP(panel1=red, panel2=drawn)
       └─ [normal]     ──→ SHOW_STRIP(panel1=empty, panel2=drawn)
             └─ PLAY_PHASE (players submit panel from hand)
                   └─ JUDGE_REVEAL (one submission at a time)
                         └─ JUDGE_PICK → SCORE → DRAW_PANEL (next round)
```

---

## TV display — the strip

The core visual: three panel slots displayed horizontally across the TV.

```
┌────────────────────────────────────────────────────────────────┐
│  Round 6 · Judge: Sam                                          │
│                                                                │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│   │              │  │              │  │  ???         │        │
│   │  [Panel 1]   │  │  [Panel 2]   │  │              │        │
│   │  (red card)  │  │  (deck draw) │  │  (your card) │        │
│   │              │  │              │  │              │        │
│   └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                │
│              Submitted: 3 / 5                                  │
└────────────────────────────────────────────────────────────────┘
```

During JUDGE_REVEAL, the `???` panel is replaced one submission at a time. The strip
animates left → right to read naturally.

---

## Phone UX

### Hand display

Same horizontal-scroll card hand as Worst Take Wins, but cards are **images** not text
— they must render clearly at phone-screen size (~120×90 px thumbnail in the hand,
full-width on tap-to-preview).

Tap a card → full-width panel preview overlaid on screen. Tap "Play this card" to
submit.

### What the phone shows during SHOW_STRIP

A compact version of the strip (panels 1 + 2 visible, panel 3 shows `?`) at the top
of the screen, above the card hand. Players see the context while choosing.

### Judge phone

During JUDGE_REVEAL: each submission displayed as a full strip (all 3 panels) on the
judge's phone at readable size. "Next" button advances. Final screen: "Pick a winner"
list of all submissions. Judge taps one.

---

## Art: the hard problem

Joking Hazard uses *Cyanide & Happiness* art. A digital implementation of the same
mechanic needs one of:

| Option | Cost | Notes |
|--------|------|-------|
| **Commission original panel art** | $$$$ | One-off cost; own the IP. Need ~250+ panels for a playable deck. At $25–50/panel from a freelancer, ~$6–12 K for 250 panels. |
| **License C&H art** | Negotiate | Explosm has not publicly offered digital licensing. Unlikely/expensive. |
| **AI-generated art** | $ | Generate consistent panel art via Stable Diffusion / DALL-E with a fixed style LoRA. Rapid iteration; style consistency is the challenge. |
| **Stick-figure / simple SVG** | Free | Build a small set of hand-drawn SVG characters and scenes. Faster to produce; charm depends on execution. |
| **Photo collage style** | $ | License stock photos + add caption bubbles. Different vibe; easier to source at scale. |

**Recommendation for v1 (prototype):** stick-figure SVG or AI-generated art in a
consistent flat style — fast to produce, easy to iterate, no licensing risk. Commission
polished art as a v2 investment once the mechanic is validated.

### Panel content design

Each panel needs:
- A **scene** (background or setting cue)
- One or two **characters** (expressions matter — they carry the joke)
- Optional **speech bubble** or **caption** text

Panels should be ambiguous enough to combine in unexpected ways. Avoid panels that are
only funny in one specific combination. The best panels work as setup, middle, *and*
punchline depending on context.

---

## Card data format

Unlike Worst Take Wins (text strings), panels are image assets. The JSON deck
references image files:

```json
{
  "name": "Punchline Base Deck",
  "panels": [
    {
      "id": "pnl001",
      "image": "panels/pnl001.png",
      "redBorder": false,
      "caption": "Meanwhile, at the office…",
      "tags": ["office", "mild"]
    },
    {
      "id": "pnl002",
      "image": "panels/pnl002.png",
      "redBorder": true,
      "caption": null,
      "tags": ["setup", "family"]
    }
  ]
}
```

`tags` support optional content filtering (e.g. a "family mode" that excludes panels
tagged `adult`).

---

## Key technical differences vs Worst Take Wins

| Concern | Worst Take Wins | Punchline |
|---------|----------------|-----------|
| Card content | Text strings | Image files (PNG/WebP) |
| Card hand on phone | CSS text cards | `<img>` thumbnails, tap-to-preview |
| TV layout | Prompt + submissions list | 3-panel strip layout |
| Deck format | JSON text arrays | JSON with `image` paths; assets served statically |
| Asset size | ~50 KB JSON | ~5–20 KB per panel × 250+ panels = 1–5 MB total |
| Image loading | N/A | Preload all panel images on game start to avoid mid-round flicker |

### Image preloading strategy

On GAME_STARTED, server sends the full panel manifest (IDs + image URLs). Client
preloads all images into `<img>` elements off-screen. With ~250 panels at ~15 KB each
≈ 3.75 MB — acceptable over Wi-Fi in ~2–5 s. Show a loading bar in LOBBY state.

---

## Shared infrastructure with Worst Take Wins

Both games share:
- Room / player management (`server/lib/room.js`)
- WebSocket server skeleton
- Chromecast receiver shell (different game-state rendering logic)
- PWA phone shell (different card-hand rendering)
- Lobby flow (room code, player list, host START_GAME)
- Judge rotation, anonymous submission reveal, scoring display

A monorepo with `games/worst-take-wins/` and `games/punchline/` sharing
`server/lib/` and `client/lib/` is the cleanest structure.

---

## Open questions (Punchline)

- **Art direction:** SVG stick-figure vs AI-generated flat art vs commissioned art?
  Needs a decision before any content production starts.
- **Red-border frequency:** Joking Hazard uses ~10–15% red-border cards. Tune this
  empirically; too many makes rounds feel repetitive.
- **Panel count for a playable deck:** 150 panels is a minimum for 10-player sessions
  without repeats over ~2 hours. 250 is comfortable. Build to 150 for v1.
- **Caption text on panels:** pre-baked into the image (simpler) vs rendered as an
  HTML overlay on the `<img>` (allows localisation and font consistency). HTML overlay
  recommended — keeps art assets simpler and text searchable.
- **Strip direction:** Joking Hazard always reads left-to-right, punchline last. A
  variant where the middle panel is the wild card (player fills panel 2, not panel 3)
  adds strategic interest. Consider as a configurable round-type.
- **Same Cast App ID or separate?** Worst Take Wins and Punchline could be two modes
  of one app (lobby screen lets host pick the game type) or two separate Cast apps.
  One app is simpler for players ("open the same thing"); two apps allows independent
  updates. Lean toward one app with a game-select lobby.
