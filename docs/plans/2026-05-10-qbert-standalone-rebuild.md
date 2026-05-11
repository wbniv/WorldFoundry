# Rebuild `wflevels/qbert_practice-standalone.iff` from source

**Status:** Not started

## Context

`wflevels/qbert_practice-standalone.iff` is the engine-loadable L4-wrapped form that `task run-level -- wflevels/qbert_practice-standalone.iff` loads. Today it has no automated rebuild step — the existing build pipeline ([wftools/wf_blender/build_level_binary.sh](../../wftools/wf_blender/build_level_binary.sh)) stops at step `[4/4]` producing the inner `wflevels/qbert_practice.iff` (45 KB post Phase-1 consolidation). The L4 wrapper around that inner has, per a doc note from today, been "hand-built by a small Python wrap" because of a suspected `iffcomp-rs` inlining bug.

**Finding: there is no iffcomp-rs bug at the current 45 KB inner size.** Running `iffcomp -binary -o=/tmp/qbert_test_standalone.iff wflevels/qbert_practice/qbert_practice-standalone.iff.txt` and `cmp`'ing against the committed `wflevels/qbert_practice-standalone.iff` reports **byte-identical** output (49152 bytes both). The notes in [qbert_practice-standalone.iff.txt](../../wflevels/qbert_practice/qbert_practice-standalone.iff.txt) and [docs/investigations/2026-05-10-qbert-engine-caps.md](../investigations/2026-05-10-qbert-engine-caps.md) appear to be misdiagnoses (probably from the pre-Phase-1 1.93 MB regime, possibly conflated with the OBJD/ROOM pool-size drift fixed earlier today).

So the rebuild is a one-line `iffcomp` invocation; the work is to wire it into the build script and clean up the misleading doc claims.

## Approach

Append a `[5/5]` step to [wftools/wf_blender/build_level_binary.sh](../../wftools/wf_blender/build_level_binary.sh) that runs `iffcomp -binary` on `<level>-standalone.iff.txt` and writes the resulting binary one directory up next to the inner `<level>.iff`. Then `bash wftools/wf_blender/build_level_binary.sh qbert_practice` becomes the single command that produces both `wflevels/qbert_practice.iff` and `wflevels/qbert_practice-standalone.iff`.

### Critical files

| File | Change |
|------|--------|
| [wftools/wf_blender/build_level_binary.sh](../../wftools/wf_blender/build_level_binary.sh) | Append step `[5/5] iffcomp-rs <level>-standalone.iff.txt → ../<level>-standalone.iff`, guarded by `[[ -f "$LEVEL_DIR/$LEVEL-standalone.iff.txt" ]]` so levels without a standalone wrapper still work. |
| [wflevels/qbert_practice/qbert_practice-standalone.iff.txt](../../wflevels/qbert_practice/qbert_practice-standalone.iff.txt) | Strike the "iffcomp-rs inlining bug" NOTE block (lines 3–11) and "Build (when iffcomp-rs inlining works)" caveat — replace with a clean build recipe pointing at `build_level_binary.sh`. |
| [docs/investigations/2026-05-10-qbert-engine-caps.md](../investigations/2026-05-10-qbert-engine-caps.md) | Append a follow-up note: iffcomp-rs verified byte-identical to committed standalone at 45 KB inner; the earlier `_chunkID.Valid()` symptom is unreproduced at Phase-1 size and may have been a pool-size / engine-side overflow, not an iffcomp-rs bug. |
| `wflevels/qbert_practice/qbert_practice-standalone.iff` (stale 1.93 MB cached copy) | **Delete** (`git rm`) — primary lives at `wflevels/qbert_practice-standalone.iff`; the in-dir copy is a leftover from the May-4-era build path. |

### Concrete step `[5/5]` body

```bash
STANDALONE_TXT="$LEVEL-standalone.iff.txt"
if [[ -f "$STANDALONE_TXT" ]]; then
  echo "[5/5] iffcomp-rs  $STANDALONE_TXT  →  ../$LEVEL-standalone.iff"
  "$IFFCOMP" -binary -o="../$LEVEL-standalone.iff" "$STANDALONE_TXT" >/dev/null
  SIZE_S=$(stat -c %s "$REPO/wflevels/$LEVEL-standalone.iff")
  echo "✓ built $REPO/wflevels/$LEVEL-standalone.iff ($SIZE_S bytes)"
fi
```

`$IFFCOMP`, `$LEVEL`, `$LEVEL_DIR`, `$REPO` are already defined. The `cd "$LEVEL_DIR"` earlier in the script means `$STANDALONE_TXT` resolves correctly. The `if -f` guard keeps the script working for levels that don't have a `*-standalone.iff.txt` (snowgoons does have one, so this generalizes too).

## Verification

1. **Byte-identity sanity (already done):**
   ```
   cmp wflevels/qbert_practice-standalone.iff /tmp/qbert_test_standalone.iff
   # → exit 0 (byte-identical, 49152 bytes)
   ```

2. **End-to-end one-command rebuild:**
   ```
   bash wftools/wf_blender/build_level_binary.sh qbert_practice
   ```
   Expect `[1/5]…[5/5]` log lines and both `wflevels/qbert_practice.iff` (45 KB) and `wflevels/qbert_practice-standalone.iff` (49 KB) refreshed.

3. **Identity against HEAD when sources at HEAD:**
   ```
   git diff --stat -- wflevels/qbert_practice-standalone.iff wflevels/qbert_practice.iff
   ```
   Empty if reproducible.

4. **Engine load:**
   ```
   task run-level -- wflevels/qbert_practice-standalone.iff
   ```
   Boots into Q*bert; no `_chunkID.Valid()` assertion, no DMalloc OOM.

5. **Snowgoons regression** (shared build script):
   ```
   bash wftools/wf_blender/build_level_binary.sh snowgoons-blender
   ```
   With `snowgoons-blender-standalone.iff.txt` present, step 5 runs cleanly; otherwise the `if -f` guard short-circuits and the level builds as before.

## Out of scope

- **Fixing a presumed iffcomp-rs inlining bug** — none reproduced. If a future level pushes the inner past some real threshold and `_chunkID.Valid()` returns, dig in then with a concrete reproducer.
- **The Python "hand wrap" script** described in the original doc note — no longer needed.
- **Generalizing the build script across all levels via a dispatcher** — the `if -f` guard already does this.
