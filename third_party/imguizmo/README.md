# ImGuizmo (vendored)

3D manipulation gizmo for Dear ImGui — used by `wf-edit` for the viewport
translate/rotate gizmo (see [docs/plans/2026-05-22-viewport-gizmo.md](../../docs/plans/2026-05-22-viewport-gizmo.md)).

- **Upstream:** https://github.com/CedricGuillemet/ImGuizmo
- **Pinned commit:** `be8aa4aeab86b402701c8c1df011bd8cd776760b` (2026-05-16)
- **License:** MIT (see `LICENSE`)

Only the two files needed by the editor are vendored (the upstream `src/` also ships
GraphEditor / ImSequencer / ImCurveEdit / etc., which we don't use):

| File | Source path in upstream | SHA-256 |
|------|-------------------------|---------|
| `ImGuizmo.h`   | `src/ImGuizmo.h`   | `246b069df48f1f25eaad7f495694a8cd437745cec3da9e205449d1943a5dc064` |
| `ImGuizmo.cpp` | `src/ImGuizmo.cpp` | `882eef2d380c82797d8a9e783830ae8ca267e0992933a0927d5ff089afa8f488` |

Compatible with the vendored Dear ImGui 1.92.9 WIP (docking branch). RTTI-free, so it
builds under the editor target's `-fno-rtti`; the target's `-w` silences its warnings.

## Updating

```sh
SHA=<new-commit>
BASE="https://raw.githubusercontent.com/CedricGuillemet/ImGuizmo/$SHA"
curl -sfL "$BASE/src/ImGuizmo.h"   -o third_party/imguizmo/ImGuizmo.h
curl -sfL "$BASE/src/ImGuizmo.cpp" -o third_party/imguizmo/ImGuizmo.cpp
curl -sfL "$BASE/LICENSE"          -o third_party/imguizmo/LICENSE
sha256sum third_party/imguizmo/ImGuizmo.{h,cpp}   # update the table above
```
