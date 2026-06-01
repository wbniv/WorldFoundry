# Plan — Add polygon count + texture resolution to asset browser preview

## Context

The existing plan doc at `docs/plans/2026-04-28-blender-asset-browser-plugin.md` is
verified complete. The user wants to add two new metadata fields to the UI preview:
how many polygons an asset has, and what texture resolution(s) it ships with.

Provider API research findings:
- **Poly Haven**: reliable LOD triangle counts in `lods[]`; `max_resolution` field;
  user-selectable resolution tiers (1K, 2K, 4K, 8K) at download time.
- **AmbientCG**: NO poly count (texture/material library, not primarily models);
  resolution tiers up to 8K/16K selectable at download time.
- **Kenney**: NO API at all; no poly or texture metadata exposed.
- **Quaternius**: NO API; fixed baked texture resolution, unknown at query time.
- **OpenGameArt**: occasionally poly count in text description only; no resolution
  selection; not structured.

## What to change in the plan doc

Three targeted edits to `docs/plans/2026-04-28-blender-asset-browser-plugin.md`:

### Edit 1 — `candidate.rs` description (line ~39)
Append three new fields to the inline field list:

```
poly_count: Option<u32>           Triangle count for the default (highest) LOD.
                                  Populated by Poly Haven only; None for all others.
texture_max_res: Option<u32>      Max texture dimension in pixels (4096 = 4K).
                                  Populated by Poly Haven (max_resolution) and
                                  AmbientCG (highest available tier). None for
                                  Kenney / Quaternius / OpenGameArt.
texture_resolutions: Vec<u32>     Download-time selectable tiers, sorted ascending
                                  (e.g. [1024, 2048, 4096, 8192]).
                                  Non-empty only for Poly Haven and AmbientCG.
                                  Empty = no user choice; download at provider default.
```

### Edit 2 — UI mockup (lines ~199-221)
Update result rows to show poly count and texture resolution. Add a "Selected asset"
detail pane below the list (avoids cramming everything into a narrow row). The list
rows show abbreviated values; the detail pane shows the resolution dropdown when
applicable.

```
┌─ WF Asset Browser ─────────────────────┐
│ Search: [tree                       ]🔍 │
│                                         │
│ Providers:                              │
│  ☑ Poly Haven   ☑ Kenney    ☑ AmbCG    │
│  ☑ Quaternius   ☑ OpenGameArt           │
│                                         │
│ Policy: wflevels/licence_policy.toml    │
│ Accept: CC0-1.0, CC-BY-4.0, ...         │
│                                         │
│ ┌─ Results (12 / 12 after filter) ──┐  │
│ │ [▣] Oak tree    CC0  Poly  1.2K▲ 4K│ │
│ │ [▣] Pine tree   CC0  Quat  0.8K▲ — │ │
│ │ [▣] Bare tree   CC0  Kenny  0.5K▲ — │ │
│ │ ... (lazy-loaded on scroll)       │  │
│ └──────────────────────────────────┘  │
│                                         │
│ ┌─ Oak tree (Poly Haven) ───────────┐  │
│ │  Triangles: 1,248   Licence: CC0   │  │
│ │  Texture res: [4K ▾] (1K 2K 4K 8K)│  │
│ │  Attribution: not required         │  │
│ └───────────────────────────────────┘  │
│                                         │
│ [Import Selected]  [Cancel]            │
└────────────────────────────────────────┘
```

Column key in result rows: `[thumb] name  licence  provider  poly-count  tex-res`
- Poly count shown as `1.2K▲` (triangles, abbreviated; `—` if unknown).
- Tex res shown as `4K` (max available; `—` if unknown).
- When provider offers resolution tiers, the detail pane shows a dropdown.
- Detail pane appears only when a row is selected.

### Edit 3 — Download flow step 1 (lines ~229-234)
Add a step 1a between "Designer clicks Import Selected" and the
`WF_OT_import_asset.execute()` call:

> 1a. **Resolution selection** (Poly Haven and AmbientCG only). If
>     `candidate.texture_resolutions` is non-empty, the import operator
>     reads the value of a `wf_asset_texture_res` scene property
>     (populated from the detail-pane dropdown, default = largest available
>     tier). The selected resolution is passed to `download()` as a hint;
>     the provider adapter appends the appropriate query param (Poly Haven:
>     `?res=4k`, AmbientCG: `resolution=4096`) before fetching.
>     Kenney / Quaternius / OpenGameArt ignore the hint (no server-side
>     resolution selection; they download the single available bundle).

## Critical files to modify

- `docs/plans/2026-04-28-blender-asset-browser-plugin.md` — the only file to edit

## Verification

After editing, confirm:
1. `candidate.rs` description lists the three new fields with provider-availability notes.
2. UI ASCII art is updated and columns are still legible.
3. Download flow has the 1a resolution-selection step.
4. No other sections need updates (Rust API surface, estimated effort, Out of scope).
5. Run `task md -- docs/plans/2026-04-28-blender-asset-browser-plugin.md` to regenerate PDF.
