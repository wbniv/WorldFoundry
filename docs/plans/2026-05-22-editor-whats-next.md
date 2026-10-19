# What's Next for the Editor

**Status:** Reference doc (2026-05-22 session snapshot) — most items since shipped; see the [plan-status sweep](2026-05-25-plan-status-sweep.md) for current editor state.

**Date:** 2026-05-22

## Open editor items (priority order)

| # | Item | Why now | Effort |
|---|------|---------|--------|
| 1 | **Live structural sync** — Add/Delete/Duplicate reflect in live viewport without reload | Direct UX gap surfaced by today's Add-Actor ship; `structural_dirty` hint is visible every time you use the new button | ~2–3 h |
| 2 | **Gizmo scale** — third axis of the translate+rotate gizmo | Deferred explicitly in 2026-05-22-viewport-gizmo plan; translate+rotate already done | ~1 h |
| 3 | **True Doc observer** — `wfcrdt::observe_deep` so remote/undo edits propagate to viewport without a panel re-commit | Needed for collab + undo live preview; currently only local panel commits drive the bridge | ~2 h |
| 4 | **Collab two-instance undo GUI check** — origin-gating covered by wrapper test; needs two live instances to verify Ctrl+Z doesn't un-do the peer | Parked in 2026-05-22-yrs-upgrade plan | ~1 h |
| 5 | **HAL decomposition** — separate HALInit / HALStart so editor owns the loop | Trigger: when callback inversion chafes or multiple viewports needed | unknown |

## Recommended next: Live structural sync (#1)

`AddActor`/`DeleteActor`/`DuplicateActor` all set `structural_dirty=true` and show "(reload for live preview)" — the actor appears/disappears only after the user triggers a level reload. Live sync would call `wfmut::SpawnActor` / `RemoveActor` immediately and replace the positional `content[i] ↔ engine i+1` map with a stable `_eid ↔ engine idx` lookup.

**Gating question:** `SpawnActor` needs to exist and be callable from `engine_bridge.cc`. If it doesn't, this may require confirming the runtime path first (quick grep).

Gizmo scale (#2) is smaller and self-contained if you prefer a quick win first.
