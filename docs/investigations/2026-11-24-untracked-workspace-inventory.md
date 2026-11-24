# Untracked workspace inventory

**Updated survey: 24 November 2026.** At commit `5d34b1f82` on `2026-new-level`, the branch was two commits ahead of `origin/2026-new-level`; this inventory was modified in the working tree. `git ls-files --others --exclude-standard` reported **11,936 untracked files**. This is a snapshot, not a judgment that these files are disposable. Ignored files, including build caches, are outside this count.

**Changes since the original survey:** Commit `114c0c51e` added the five previously untracked top-level plans, their linked supporting files and this report. The 193 superseded GPU profiles that had briefly been archived locally were restored and checked byte-for-byte; their backup archive remains under `build/coordinator-artifacts/2026-11-24-aquarium-clocks/rebuild-audit/`. Commit `5d34b1f82` added curated GPU-skinning experiment evidence recovered from the experiment branch, its analysis tools, and an [evidence index](../plans/2026-10-16-gpu-skinning-chromecast-experiment/evidence/INDEX.md). The remaining untracked raw captures were retained locally; some contain pairing information or network details and need review before sharing. The plan now records that cast2 was measured, while the cast1 campaign remains incomplete.

| Location | Files | Observed contents |
| --- | ---: | --- |
| `docs/diagnostics/` | 9,590 | Diagnostic records, captures, logs, videos, APKs and worktree archives |
| `docs/plans/` | 1,566 | Plan-associated evidence and supporting material; no untracked top-level plan Markdown files |
| `docs/transcripts/` | 55 | Transcript files |
| `docs/reference/` | 2 | Reference files |
| `wflevels/` | 710 | Level assets, generated level outputs, prototype scripts and review material |
| `wfsource/`, `dev/` and root/local configuration | 13 | Generated OAS headers, coordinator recipes and local state files |

Counts by extension include 5,083 JSON, 3,515 text, 1,474 PNG, 708 log, 412 IFF, 172 CSV, 90 MP4, 89 TGA, 70 Markdown, 17 Python and 16 APK files. These are filename-based counts: an extension does not establish whether a particular file is generated, needed, safe to publish or safe to remove.

## Largest groups

The following are apparent file sizes from `lstat`, not deduplicated disk usage; values are approximate. Some directories may also contain tracked files, which are not counted here.

| Untracked group | Files | Apparent size |
| --- | ---: | ---: |
| `docs/diagnostics/worktree-archives/` | 16 | 8.49 GiB |
| `docs/diagnostics/reef-gameplay-verification-2026-11-05/` | 799 | 1.55 GiB |
| `docs/plans/2026-10-16-gpu-skinning-chromecast-experiment/` | 1,409 | 0.72 GiB |
| `docs/diagnostics/reef-triangle-normal-2026-11-06/` | 933 | 0.37 GiB |
| `docs/plans/2026-11-14-snowgoon-character/` | 99 | 0.25 GiB |
| `docs/diagnostics/parmenides/` | 192 | 0.14 GiB |

## Source and work requiring review

The five previously identified top-level plans and their linked supporting files were added in `114c0c51e`. No top-level plan Markdown files were untracked at this survey. The property-catalog plan still references a missing `scripts/build-object-properties.py`; its two links need separate investigation.

The level inventory includes 118 files under `wflevels/discus_asset/`, 76 under `wflevels/cuckoo_village_layout/`, and 42 under `wflevels/cuckoo_village_assets/`. The latter two include build and inspection scripts, and the layout includes `village_layout.blend`; do not treat those directories as wholly disposable output. Other sets include deformation benchmarks, reef variants and style-geometry builds. `dev/coordinator-recipes/` contains two untracked recipes. Seven untracked `.ht` files in `wfsource/source/oas/` appear to be generated headers and should be compared with the header generator before disposition.

## Rebuild status and next steps

The Aquarium and 3D Clocks build inputs identified in the preceding audit were committed and merged into `2026-new-level`. Both APKs built from a separate clean source snapshot; the level bundles matched the installed APKs, but the native libraries were not byte-identical. See [the rebuild guide](../howto/rebuild-aquarium-and-clocks.md). That verification does not prove every other level, plan, evidence capture or untracked source in this inventory is represented in Git.

1. Investigate the property-catalog plan's missing script references.
2. Inventory prototype source and assets by level, compare them with tracked equivalents and generator outputs, and preserve unique work before removing or ignoring generated files.
3. Review diagnostic directories and worktree archives for unique evidence, secrets, active use and retention needs before moving, deleting or publishing anything. Preserve useful evidence and references.
4. Re-run the inventory after each disposition. Do not use a blanket `git clean` on this checkout.

The updated NUL-delimited path list is stored locally at `build/coordinator-artifacts/2026-11-24-aquarium-clocks/rebuild-audit/remaining-untracked-paths.nul`. That file is itself a local build artifact and is not part of the pushed repository. The earlier rebuild recovery snapshot is in the same `rebuild-audit/` directory; it can contain local configuration and should be reviewed before sharing.
