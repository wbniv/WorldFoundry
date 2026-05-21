# Plan: multi-Blender-version test matrix for the level exporter

## Context

The `worldfoundry-blender-addons` apt metapackage currently strict-pins Blender to `>= 4.0.2, << 4.0.3` because that's the only Blender release the add-on has been validated against. This blocks Ubuntu 26.04+ users (who get Blender ~4.5 by default) from `apt install worldfoundry-blender-addons` — and any future widening of the pin without test coverage risks silent breakage when Blender's Python API evolves.

This plan introduces a CI matrix that installs Blender 4.0.2, 4.2 LTS, 4.5 LTS, runs the `wf_blender` add-on headlessly, exports a fixture `.blend` to `.lev` text IFF, and asserts the output is correct. Green CI on a Blender version unblocks widening the pin to cover it.

## Approach

### Data flow

```
wflevels/qbert_practice/qbert_practice.blend   ← INPUT (existing fixture, already in repo)
  │
  │  blender -b <blend> --python run_export.py
  │  (run_export.py enables wf_blender, calls WF_OT_export_level)
  ▼
$WF_EXPORT_OUT (temp path)                     ← .lev produced by the addon
  │
  │  byte-compare
  ▼
tests/fixtures/qbert_practice-golden.lev       ← committed; produced once on 4.0.2

Test passes if temp output == golden.
```

- **Blender distribution**: download official upstream tarballs from `download.blender.org/release/Blender<MAJOR.MINOR>/blender-<VERSION>-linux-x64.tar.xz`. Unpack to a CI-local prefix. No reliance on Ubuntu's blender package (which ships only one version per release).
- **Input fixture (already in repo)**: `wflevels/qbert_practice/qbert_practice.blend`. Nothing new to create on the input side.
- **Test runner**: pytest test that subprocess-launches Blender in `--background --python` mode, executing a small script (`run_export.py`) that:
  - Adds `wf_blender` to the addons path.
  - Enables the WF add-on.
  - Triggers `WF_OT_export_level` (or calls its `execute()` directly).
  - Saves the `.lev` output to a temp path passed via `$WF_EXPORT_OUT`.
- **Comparison**: byte-identical match against a checked-in golden `tests/fixtures/qbert_practice-golden.lev`. The golden is generated once on a clean 4.0.2 run, reviewed by hand, then committed. If subsequent Blender versions diverge (float-serialisation differs, etc.), capture per-version goldens or normalise before comparison.
- **CI shape**: GitHub Actions matrix in `.github/workflows/blender-addon-tests.yml`, one job per Blender version; each runs the same pytest test against a different Blender install.

## Critical files

| Path | Change |
|---|---|
| `tests/conftest.py` | Extend with a `blender_binary` fixture that resolves to a `$BLENDER_BIN` env var (set per-matrix-job) |
| `tests/test_blender_addon_export.py` | **New**: subprocess-launches Blender, runs export, compares against golden |
| `tests/fixtures/qbert_practice-golden.lev` | **New**: golden output (generate once on a known-good 4.0.2 run, commit after review) |
| `tests/blender_runner/run_export.py` | **New**: the in-Blender script loaded by `blender --python`; enables addon + runs export |
| `scripts/install-blender.sh` | **New**: helper to download + unpack a specific Blender version to a target dir. `-h/--help`, `set -euo pipefail`, idempotent. |
| `.github/workflows/blender-addon-tests.yml` | **New**: matrix CI job (versions 4.0.2, 4.2.0 LTS, 4.5.0 LTS) |

## Implementation steps

### Phase 1 — Local harness, one Blender version

1. **Write `scripts/install-blender.sh BL_VERSION TARGET_DIR`** — downloads + unpacks the official tarball; verifies SHA256 against blender.org's checksums; idempotent (skip if `TARGET_DIR/blender` is already that version).
2. **Run it locally for 4.0.2** → `/tmp/blender-4.0.2/`.
3. **Write `tests/blender_runner/run_export.py`** — enables `wf_blender`, runs export to `$WF_EXPORT_OUT` env var path, exits. Headless-safe: no GUI calls, exit-code-based pass/fail.
4. **Write `tests/test_blender_addon_export.py`** — pytest test that:
   - Subprocess: `<blender_bin> -b qbert_practice.blend --python run_export.py`
   - Reads output `.lev`
   - Compares to `tests/fixtures/qbert_practice-golden.lev`
5. **Generate the golden** by running the harness once successfully on 4.0.2. Manually review the output, then commit as the golden.
6. **Verify locally**: `BLENDER_BIN=/tmp/blender-4.0.2/blender pytest tests/test_blender_addon_export.py` → green.

### Phase 2 — Multi-version

7. **Run `install-blender.sh`** for 4.2.0 LTS and 4.5.0 LTS.
8. **Run pytest against each**. Triage divergences:
   - **Byte-identical**: great, the same golden works.
   - **Trivial divergence** (whitespace, float precision): normalise in the comparison step (e.g. strip trailing whitespace, round floats to a fixed precision).
   - **Semantic divergence**: per-version golden files, or pin the version-spread tighter.

### Phase 3 — CI

9. **Write `.github/workflows/blender-addon-tests.yml`** with matrix `blender-version: [4.0.2, 4.2.0, 4.5.0]`. Each job: install Blender via `install-blender.sh`, run pytest.
10. **Trigger on PR + push to main**. Make green-on-all-targeted-versions a merge gate.
11. **Once green**: open a follow-up PR in `worldfoundry.org` to widen the `worldfoundry-blender-addons` pin to `(>= 4.0.2), (<< 4.6)` (or whatever band the matrix has validated).

## Verification

- **Phase 1**: `pytest tests/test_blender_addon_export.py` green locally with `BLENDER_BIN=/tmp/blender-4.0.2/blender`.
- **Phase 2**: same test green for 4.2.0 and 4.5.0 (or documented per-version divergence with per-version goldens).
- **Phase 3**: CI matrix green on push.
- **End-state**: worldfoundry-blender-addons pin widens from `(<< 4.0.3)` to `(<< 4.6)` (or similar tested band). `apt install worldfoundry-blender-addons` works on Ubuntu 26.04.

## Out of scope

- Testing the OTHER add-on (`blender-asset-finder`) — separate effort; it has no level-export logic and is mostly network calls.
- Adding fixtures beyond `qbert_practice`. Start with one; expand if a regression slips through.
- Testing against Blender beta / daily builds. Stable LTS + current point releases only.
- Replacing the strict pin in `worldfoundry-blender-addons` *today*. The pin widening is the **payoff** of this work, not part of it.

## Expected effort

Multi-day. Phase 1 (local harness + golden) is the hardest part — **~1 day**. Phase 2 (multi-version + divergence triage) is the wildcard — **~1 day if clean, more if Blender's API changed between versions**. Phase 3 (CI wire-up) is straightforward — **~half day**.

Total: **~2.5 days** for clean execution; up to a week if Blender API divergences need real work.

## Notes / risk flags

- **Tarball availability**: assumes `download.blender.org` keeps old versions. Verify in step 1 — fetch the 4.0.2 checksum file before committing to the approach. (Blender does archive aggressively, so high confidence.)
- **Headless rendering of GPU-touching code**: if the export path touches any OpenGL/Vulkan state, headless will fail. Inspection of `export_level.py` shows pure data extraction; should be safe — but verify in Phase 1.
- **Golden churn**: if the export format ever changes (e.g., a new attribute type added), every golden needs regenerating. Plan to commit a `regen-goldens.sh` helper in Phase 1 to make this a one-command operation.
- **Storage**: each Blender install is ~300 MB. CI matrix x3 ≈ 1 GB. Cache the tarballs in GitHub Actions cache to avoid re-downloading every run.
