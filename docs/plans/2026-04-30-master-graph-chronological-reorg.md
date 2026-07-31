# Plan: Reorganize master dependency graph for chronological accuracy

## Context

The master overview graph in README.md was built incrementally as game briefs were written, so edges reflect the *order briefs were authored* rather than publication history. Several edges point backward in time by years or decades — the most egregious being `pop (1989) → pitfall (1982)`, where Pitfall! (the genre archetype) is shown as a *descendant* of Prince of Persia. The guiding rule: **publication order wins unless the WF implementation dependency is genuinely non-trivial** (a real shared data structure, physics constraint, or behavioral subsystem — not "broadcast kill-all" or "move toward player").

Four edges need reversing. Each cascades into Table A, Table B, the Climb/scroll family subgraph, and two brief files.

---

## The four reversals

| Current (wrong direction) | Gap | Dependency that was claimed | Verdict |
|---|---|---|---|
| `pop (1989) → pitfall (1982)` | 7 yr | Z-axis lock + snap-cut camera | Trivial (zero Z-velocity + CamShot flag). Pitfall! is the archetype; it introduces this. |
| `geowars (2003) → defender (1981)` | 22 yr | Arena-bomb broadcast (smart bomb) | Trivial broadcast. Defender *invented* the smart bomb. |
| `geowars (2003) → yars (1982)` | 21 yr | Direct stick-as-velocity-impulse | Simple mailbox read. Yars (1982) introduced this control model; Geowars reuses + extends it. |
| `yars (1982) → starcastle (1980)` | 2 yr | Heat-seeker AI | "Move toward player" is trivially simple. Star Castle came first. |

---

## Changes — README.md

### Master graph edges

Remove:
- `pop --> pitfall`
- `geowars --> defender`
- `geowars --> yars`
- `yars --> starcastle`

Add:
- `pitfall --> pop`
- `yars --> geowars`
- `starcastle --> yars` ← starcastle (1980) introduces heat-seeker; yars (1982) reuses for Destroyer Missile

Reposition `pitfall["Pitfall!"]` node declaration to sit alongside `donkey["Donkey Kong"]` in the climb/scroll section (both are now co-roots of that family). Remove it from the trailing donkey-family block.

Update the `%% Asteroids family` comment to reflect that `starcastle --> yars --> geowars` now forms a chain within/across families.

Update `%% Climb family` comment: "Donkey Kong + Pitfall! roots".

### Climb / side-scroll family subgraph

Change `pop --> pitfall[Pitfall!]` → `pitfall[Pitfall!] --> pop`.

Update description paragraph: Pitfall! introduces the Z-lock camera and snap-cut CamShot; PoP reuses those and adds ledge-grab and melee on top.

### Table A — per-brief rows to edit

**pitfall:**
- Introduces: add `side-scroll snap-cut camera + Z-axis lock` (first item)
- Reuses: remove `side-scroll + Z-lock ← prince-of-persia`
- Standalone: `~3–3.5 wk` (was ~2.5–3 wk; Z-lock is now new work here)
- With deps: `~2 wk` (Joust HUD/SFX still needed; Z-lock is now self-owned)

**prince-of-persia:**
- Introduces: remove `side-scroll camera + Z-axis lock` (pitfall owns it now)
- Reuses: add `Z-lock camera ← pitfall`

**bubble-bobble:**
- Reuses: `side-scroll + Z-lock ← prince-of-persia` → `side-scroll + Z-lock ← pitfall`

**lode-runner:**
- Reuses: `side-scroll + Z-lock ← prince-of-persia` → `side-scroll + Z-lock ← pitfall`

**defender:**
- Introduces: add `arena-bomb broadcast (smart bomb)`
- Reuses: remove `arena-bomb broadcast ← geometry-wars`

**geometry-wars:**
- Introduces: remove `arena-bomb broadcast`; remove `direct stick-as-velocity-impulse`
- Reuses: add `arena-bomb broadcast ← defender`; add `direct-stick-velocity ← yars-revenge`

**yars-revenge:**
- Introduces: add `direct stick-as-velocity-impulse`; remove `heat-seeker AI`
- Reuses: remove `stick-velocity ← geometry-wars`; add `heat-seeker AI ← star-castle`

**star-castle:**
- Introduces: add `heat-seeker AI helper`
- Reuses: remove `heat-seeker AI ← yars-revenge (×2 — fireball + mines)`

### Table B — per-subsystem rows to edit

| Row | Change |
|---|---|
| Side-scroll camera + Z-axis lock | Introduced by: `pitfall` (not `prince-of-persia`); Consumed by: `prince-of-persia, bubble-bobble, lode-runner` |
| Heat-seeker AI helper | Introduced by: `star-castle` (not `yars-revenge`); Consumed by: `yars-revenge (×1 — Destroyer Missile)` |
| Arena-bomb broadcast | Introduced by: `defender` (not `geometry-wars`); Consumed by: `geometry-wars` |
| Direct stick-as-velocity-impulse | Introduced by: `yars-revenge` (not `geometry-wars`); Consumed by: `geometry-wars` |
| Aim-from-stick projectile | Consumed by: `—` (yars does not use aim-from-stick; it was listed in error) |

---

## Changes — pitfall.md

**Genre fit line:** remove "lane-locked Z-lock + snap-cut camera from Prince of Persia" → "introduces lane-locked Z-lock + snap-cut camera (consumed by Prince of Persia, Bubble Bobble, Lode Runner)".

**Engine work item 1** (currently "shared with PoP / Bubble Bobble / Lode Runner — free if any ship first"):
Change to: "NEW, introduced here. ~3 days. Consumed by Prince of Persia, Bubble Bobble, Lode Runner — if Pitfall! ships first, those three get it free."

**Cost note at top of Engine work section:** update standalone to ~3–3.5 wk, with-deps to ~2 wk.

---

## Changes — prince-of-persia.md

**Engine work item 2** (side-scroll camera + Z-axis lock):
Change opening from "Two parts: (a)..." to note this is the same subsystem introduced by Pitfall!; ~free if Pitfall! ships first. Keep the implementation detail. Update the "~3 days" standalone estimate to "~free with Pitfall!" and adjust the aggregate standalone cost in the section header accordingly (drops from ~3–4 wk to ~2.5–3 wk if Pitfall! ships first).

---

## Verification

- Render README.md in browser; confirm master graph flows left-to-right without major backward arrows in the asteroids/climb families.
- Confirm pitfall appears as a root (no incoming edges) alongside donkey in the climb section.
- Confirm starcastle → yars → geowars chain is visible.
- Confirm defender has no incoming edge from geowars.
- Spot-check Table A: pitfall row introduces Z-lock; star-castle row introduces heat-seeker; defender row introduces arena-bomb.
- Spot-check Table B: all four changed rows point in the correct historical direction.
