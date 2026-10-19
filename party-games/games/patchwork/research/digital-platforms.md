# Patchwork digital platform research

Checked: 2026-10-04. Sources are publisher, developer, storefront and platform
pages. No purchase, installation or gameplay test was performed. Listings
confirm advertised availability/features, not current online-service health
or compatibility with every device. Storefront availability can vary by region.

## Findings

**Original Patchwork is digitally available, including on Steam. For
Patchwork Doodle, no current official standalone digital edition was found.**
A community Tabletop Simulator adaptation exists as a historical Workshop
listing, but its page currently displays removal/incompatibility notices.
Further source-code research found two community browser implementations;
the initial search missed them. Neither has yet been tested through a full game.

| Game or adaptation | Platform | Finding and source |
| --- | --- | --- |
| Original Patchwork, developed by DIGIDICED and published by Twin Sails Interactive | Steam: Windows, macOS, Linux | Current [Steam store listing](https://store.steampowered.com/app/528250/Patchwork/). Released December 6, 2016. Advertises single-player, online PvP, shared-screen PvP, cross-platform multiplayer and Remote Play Together. |
| Patchwork The Game | Android | Current [Google Play listing](https://play.google.com/store/apps/details?id=com.digidiced.pxwrelease). Advertises the original two-player game, AI and cross-platform play. |
| Patchwork The Game | iPhone/iPad | Current [App Store listing](https://apps.apple.com/us/app/patchwork-the-game/id1075851197). Advertises the original game, tutorial, replay and AI difficulty settings. |
| Original Patchwork | Browser, Board Game Arena | Current [game page](https://boardgamearena.com/gamepanel?game=patchwork), crediting Lookout Games. Two players; available since August 11, 2021. |
| Patchwork Doodle community adaptation | Tabletop Simulator via Steam Workshop | [Workshop item 2064175638](https://steamcommunity.com/sharedfiles/filedetails/?id=2064175638), posted April 17, 2020, updated April 30, 2020. Creator describes manual play with snap points and no scripting. Page marks the item removed and incompatible. Not verified as currently usable or officially licensed. |
| Patchwork Doodle standalone game | Steam, Android, iOS, browser | No verified current official release found in this search. Do not confuse the original Patchwork listings with Doodle. |
| Patchwork Express, Stack ’n Stuff and other family editions | Standalone digital editions | No separately verified official digital releases found in the searches performed. This is an unresolved availability finding, not proof of absence. |

## Community browser implementations found during implementation research

- [numeri-pedine/patchwork-doodle](https://github.com/numeri-pedine/patchwork-doodle):
  HTML/CSS/JavaScript project with jQuery and card images. The repository links
  a [browser version](https://numeri-pedine.github.io/patchwork-doodle/).
  Source inspection found 24 numbered card images. This alone does not establish
  a complete, faithful implementation of the physical game's 30-card deck.
- [DoreyKiss/patchwork-doodle](https://github.com/DoreyKiss/patchwork-doodle):
  Angular/Firebase implementation with game and drawing-board code, an MIT
  license, ten starting-shape definitions and sixteen patch-shape definitions.
  Its default rules specify a 30-card deck. The relationship between the shape
  definitions and the complete deck still needs verification, as do current
  hosting, multiplayer behavior and rule coverage.

These are community implementations, not evidence of an official standalone
digital edition. Inspect their behavior and data before deciding what can be
reused. Preserve applicable license notices for any reused material.

## Why the edition matters

[Lookout’s official Doodle page](https://www.lookout-spiele.de/en/games/patchworkdoodle.html)
describes a 2019 roll-and-draw game for 1–6+ players. Patch cards represent
shapes, a die determines which to use, and players draw them on their own
boards. It is a different game from the original two-player Patchwork shown
on Steam and Board Game Arena.

Inference for this project: Doodle’s common cards and individual drawing
boards appear well suited to a shared TV and separate phones. Research the
full rules and placement interaction before choosing it as the implementation
target. An original Patchwork app can inform shape-placement UX but cannot
serve as the rules reference for Doodle.

## Search coverage and limits

Searched the exact Doodle name with digital/app/online/Steam terms, checked
Tabletop Simulator Workshop results, and searched Doodle specifically on
Board Game Arena and Tabletopia. Also searched Express and Stack ’n Stuff
for digital releases. Search results did not establish a current playable
Doodle browser edition or a dedicated Chromecast edition.

The [publisher’s family catalog](https://www.lookout-spiele.de/de/games.php)
also lists Revised, Anniversary, Automa, Folklore and seasonal editions.
This first pass does not individually exhaust every reskin, expansion,
community mod or regional storefront. A themed board/skin inside an existing
app would not establish a separate adaptation of that edition’s rules.

Avoid treating printable PDFs, rules pages, video play-alongs, online game-night
organizers or similarly named fabric-art downloads as playable digital games.

## Further research before planning implementation

1. Archive official English Doodle rules, score sheets and any applicable
   corrections. Track Doodle Plus separately from the base game.
2. Verify round structure, shared card selection, special actions, scoring,
   solo rules and simultaneous-play behavior from those documents.
3. Inventory start cards and patch shapes, with verified rotations/reflections.
4. Compare phone placement UX with original Patchwork’s digital interfaces;
   do not assume existing apps synchronize a shared TV session.
5. Design a TV view for the common cards, selected patch, round/scoring status
   and readiness, alongside an accessible phone board.
6. Recheck any promising Doodle digital leads and distinguish official releases
   from community adaptations before drafting a phased build plan.

## Commercial release licensing review (2026-10-04)

Will intends to sell the app through app stores. Repository licensing alone
is insufficient to establish rights to sell a Patchwork Doodle adaptation.

- DoreyKiss: GitHub's license API confirms MIT, copyright 2021 DoreyKiss.
  [Actual license](https://github.com/DoreyKiss/patchwork-doodle/blob/main/LICENSE).
  Commercial use, modification and closed-source distribution of covered code
  are permitted, provided the copyright and permission notice are retained.
  Dependencies and third-party game content need separate review. The author
  cannot license rights they do not own.
- numeri-pedine: no repository-wide license found in inspected files; GitHub's
  license endpoint returned 404. Treat its custom code and card artwork as
  unavailable for reuse until explicit permission is obtained. A bundled
  library's license does not license the rest of the repository.
- Neither repository establishes a commercial license from the game's rights
  holders for the Patchwork Doodle name, artwork, rulebook text or other
  protected game content.

Commercial direction: seek a written digital adaptation agreement, starting
with Lookout Games, or develop a separately branded original game with original
art and instructions and obtain legal review before release. Keep archived
publisher PDFs as research references; do not package them as app assets.

The [US Copyright Office](https://www.copyright.gov/register/tx-games.html)
distinguishes game ideas/methods from protectable rule text and artwork. This
is not clearance for a particular clone or for other jurisdictions. Both
[Apple](https://developer.apple.com/app-store/review/guidelines/#intellectual-property)
and [Google Play](https://support.google.com/googleplay/android-developer/answer/9888072?hl=en)
require appropriate intellectual-property rights.

## DoreyKiss reuse assessment

Decision: Will subsequently rejected reuse. Do not copy or adapt either
community implementation, including its code, shape definitions and assets.
The findings below are research history, not an adoption plan. Source
inspection used upstream main commit `0ee9bca846025ad68ee8522673b692743bd857f1`.
The [MIT notice](licenses/DoreyKiss-MIT.txt) is archived solely as research
evidence. No upstream code has been incorporated into the game runtime. Do
not ship this research archive or add DoreyKiss attribution to the app.

The examined areas included card representation, starting-shape definitions,
action models and room/game concepts. None are approved for reuse. Verify our
own implementation and component data independently against the official
rules. Keep rendering independent of shape data for original artwork and skins.

Findings from `patchworkDoodleGameManager.ts`:
- Cutting remains a TODO; a player-ready guard is commented out.
- `createDeck` cycles through shuffled shape definitions to produce 30 entries;
  this does not verify the physical deck's shape frequencies.
- Die generation uses `random(deckSize)`, giving 0–29 under the default rules,
  rather than the required 1–3 movement range.
- The implemented action switch contains start and draw actions; no scoring or
  later-round progression implementation was found in this manager.

`drawingBoard.ts` mutates cells while validating a placement, so failure can
leave the in-memory board partially changed. Its rotation implementation also
retains initial matrix dimensions across multiple quarter-turns; rectangular
patch rotations need verification before reuse.

Manifests use Angular 11/Firebase and a Node 12 functions target. Do not adopt
that entire stack merely to reuse pure data or algorithms. No dependencies from
these manifests have been installed, and their individual licenses have not
been audited. The existing JavaScript party-games platform remains the host.
