# Plan — Move blender plugin to 2026-new-level branch

## Context

The blender asset browser plugin (`wf_asset_provider` Rust crate + `asset_browser.py` +
`asset_threading.py` + `wflevels/licence_policy.toml`) was committed to `party-games-platform`
as `1e1e2ac`. It belongs on a dedicated WF-tooling branch, not the party-games workstream.

Two chromecast commits landed on top of it (`943a14e`, `b18c6a5`), so the blender commit
can't be removed with a simple reset — those commits must be preserved on
`party-games-platform`.

## Steps

1. **On `party-games-platform`**: revert `1e1e2ac`
   ```
   git revert 1e1e2ac --no-edit
   ```
   This creates a new commit that undoes the blender plugin files, leaving the chromecast
   commits intact. No history rewrite, no force-push needed.

2. **Create `2026-new-level`** from the current tip of `party-games-platform` (after the revert):
   ```
   git checkout -b 2026-new-level
   ```

3. **Cherry-pick the blender plugin commit** onto `2026-new-level`:
   ```
   git cherry-pick 1e1e2ac
   ```

## Result

- `party-games-platform`: blender plugin removed (via revert commit), chromecast work intact
- `2026-new-level`: branches from `party-games-platform` tip, has blender plugin as its tip commit

## Files affected

Removed from `party-games-platform`, present on `2026-new-level`:
- `wftools/wf_asset_provider/` (entire Rust crate)
- `wftools/wf_blender/asset_browser.py`
- `wftools/wf_blender/asset_threading.py`
- `wftools/wf_blender/__init__.py` (registration additions)
- `wflevels/licence_policy.toml`
- `docs/plans/2026-04-28-blender-asset-browser-plugin.md`

## Verification

After the operation:
- `git log --oneline party-games-platform | grep asset` → should show only the revert commit
- `git log --oneline 2026-new-level | grep asset` → should show `1e1e2ac` (original) near tip
- `ls wftools/wf_asset_provider/` on `party-games-platform` → directory absent
- `ls wftools/wf_asset_provider/` on `2026-new-level` → directory present
