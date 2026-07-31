# Deck content notice

The file `cah-base.json` in this directory contains card text from **Cards
Against Humanity**'s base set, released by Cards Against Humanity LLC under
the **Creative Commons BY-NC-SA 2.0** license
(https://creativecommons.org/licenses/by-nc-sa/2.0/).

## Summary of the license

- **BY** — attribution required (see below)
- **NC** — non-commercial use only
- **SA** — derivatives must be shared under the same license

## Attribution

- **Source:** https://github.com/crhallberg/JSON-against-humanity
  (branch `latest`, file `cah-all-compact.json`, pack "CAH Base Set")
- **Original author:** Cards Against Humanity LLC
- **Transformation:** text content was copied verbatim from the compact
  CAH JSON; the record shape (`id`, `text`, `blanks`, `tags`) was imposed
  by this project's deck loader (`../deckLoader.js`) and the blank marker
  `_` in prompts was normalised to `____` for rendering.

## Reuse in this project

This repository is **not** a commercial product. The Worst Take Wins game
is a demo integrated with the party-games platform for personal /
experimental use. If you fork this repo for a commercial purpose, the
CAH content under this license is **not** redistributable with that
fork — you would need to strip this file and provide your own deck.

## Custom decks

The deck loader (`games/worst-take-wins/deckLoader.js`) globs every
`.json` file in this directory on game start, so drop-in replacement /
addition is trivial:

```json
{
  "name": "My Deck",
  "license": "...",
  "attribution": "...",
  "prompts":   [{ "id": "p001", "text": "____.", "blanks": 1, "tags": [] }],
  "responses": [{ "id": "r001", "text": "...", "tags": [] }]
}
```

Duplicate `id`s across files are silently dropped (first-seen wins), so
custom decks should use a distinct id namespace (e.g. `custom-p001`).
