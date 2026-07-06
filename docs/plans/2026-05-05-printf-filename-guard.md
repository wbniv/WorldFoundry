# Plan — Guard against printf-style filenames in committed/staged paths

**Status:** PARTIAL — Layer 1 (repo `scripts/git-hooks/pre-commit`) shipped (offending file renamed in `24298e1`); Layer 2 (Claude/tui hook) deferred pending user approval.

**Date:** 2026-05-05

## Context

On 2026-05-05 a Claude session hit `API Error: 400 — Could not process image` when attempting to attach `assets/arcade-roms/reference/auto_%04i.png`. The PNG itself is valid (12 KB, 336×240, well under any size limit). The file came from a screen-grab tool that used `auto_%04i.png` as a sequence template and saved one capture without ever substituting a frame number — leaving the literal `%04i` in the filename.

Any path-handling code that interpolates the filename through printf-style formatting (logging, `f"{path}"` then later `format` again, ImageMagick `-format`, ffmpeg `-i` with internal printf-pattern detection) will interpret `%04i` as a format spec and mangle the path. The downstream tool then opens a wrong/missing file and ships a zero-byte buffer to the API → 400.

We've renamed this specific file to `auto_0000.png` (commit `24298e1`, in flight). This plan adds two layers of defence so it doesn't recur.

## Goals

1. **Prevent committing** new paths that contain printf format specifiers.
2. **Prevent Claude staging** such paths in the first place (defence-in-depth, repo-agnostic).
3. **Document the cause** so a future contributor seeing `auto_%04i.png` in screen-grab settings knows to fix the template.

## Non-goals

- Catching every misuse of `%` in filenames. Format-specifier detection is narrow on purpose: `%04i`, `%d`, `%05x`, etc. are unambiguous; rejecting *any* `%` would block too many legitimate names.
- Rewriting historical commits. The bad file is renamed forward; old commits keep the literal name.
- Auto-renaming. The hook says "rename then retry"; the human chooses the new name.

## Layer 1 — repo-wide git pre-commit hook

**File:** `scripts/git-hooks/pre-commit` (new, executable)

```bash
#!/usr/bin/env bash
set -euo pipefail
# Refuse any staged ADDED path whose name contains a printf format specifier.
# Modified/renamed paths skip the check — only newly introduced filenames
# are flagged, so existing tracked names stay grandfathered.
bad=$(git diff --cached --name-only --diff-filter=A \
      | grep -E '%[-+ #0]?[0-9]*[diouxXeEfgGaAcspn]' || true)
if [[ -n "$bad" ]]; then
  echo "ERROR: refusing to commit paths with printf-style format specifiers:" >&2
  echo "$bad" >&2
  echo "" >&2
  echo "These are filename traps — tools that interpolate paths through" >&2
  echo "printf-style formatting (logging, ImageMagick -format, ffmpeg -i)" >&2
  echo "will mangle the path. Rename before committing, e.g.:" >&2
  echo "  auto_%04i.png  →  auto_0000.png" >&2
  exit 1
fi
```

**Activation per clone:**

```bash
git config core.hooksPath scripts/git-hooks
```

Document this in `README.md` (existing dev-setup section, if there is one) and/or add a one-liner to `task dev-setup` (Taskfile.yml already has a `dev-setup` task). The hook itself lives in the repo; the activation is a one-shot per clone.

**Why scoped to ADDED paths only:** `--diff-filter=A` skips modifications and renames. If anyone has already committed a printf-trap filename historically, the hook won't yell on every subsequent commit that touches an unrelated file. New files only.

**Test fixtures (kept out of automation; manual verification):**
- `touch /tmp/foo_%04i.png && cd <repo> && git add /tmp/foo_%04i.png && git commit -m "test"` → expect rejection.
- `touch /tmp/foo_0000.png && git add ... && git commit -m "test"` → expect success.
- Modify an *existing* tracked file with `%` in its name (the unlikely case) → expect success (the hook is filter-A, not filter-AM).

## Layer 2 — Claude PreToolUse `git add` guard augmentation

**File:** `~/python-tui-lib/hooks/git-add-guard.sh` (existing, extend it)

Today the hook rejects only `git add -A / --all / .`. Add a second check: if any of the explicit path arguments contains a printf format specifier, deny with an explanatory message.

Sketch:

```bash
# After the existing -A/--all/. check, also flag printf-trap paths:
if echo "$cmd" | grep -qE '%[-+ #0]?[0-9]*[diouxXeEfgGaAcspn]'; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Path contains a printf-style format specifier (e.g. %%04i). Rename before staging — tools that interpolate paths through printf will mangle these. See docs/plans/2026-05-05-printf-filename-guard.md."}}'
fi
```

**Why second:** the python-tui-lib hooks are in the user's home dir, shared across projects. Editing them affects every Claude session, so this is a wider blast radius than the per-repo git hook. Layer 1 covers the WorldFoundry-specific need; Layer 2 is opt-in defence across all projects the user works on.

Recommend: land Layer 1 unconditionally, ask before editing the python-tui-lib hook.

## Layer 3 — fix the source

The original screen-grab tool that produced `auto_%04i.png` had `%04i` as its filename template. We don't know which tool — could be `gnome-screenshot`, `flameshot`, `scrot`, OBS, MAME's frame-dump (likely, given the `assets/arcade-roms/reference/` location), or a custom Python script.

For this repo's MAME workflow specifically: the most likely source is MAME's `-aviwrite` / frame-dump options. If so, configure the dump-pattern to include a frame counter (or leading literal text) so even an unsubstituted save lands at e.g. `auto_frame_0000.png`.

Out of scope for this plan to chase down which tool — flagged as a cleanup for whoever next encounters it in the MAME research scripts.

## Files to add / modify

| File | Action | Layer |
|---|---|---|
| `scripts/git-hooks/pre-commit` | **add** (new, executable) | 1 |
| `README.md` (or `docs/dev-setup.md` if that's where setup lives) | append one line about `git config core.hooksPath scripts/git-hooks` | 1 |
| `Taskfile.yml` `dev-setup` task | **optional**: append the `git config` line so fresh clones get it | 1 |
| `~/python-tui-lib/hooks/git-add-guard.sh` | extend with printf-trap regex | 2 |

## Verification

- Layer 1: stage a sentinel file `frame_%05d.png` in a scratch branch; `git commit -m test` must fail with the expected rejection message; `git mv frame_%05d.png frame_00000.png && git commit -m test` must succeed. After verification, drop the sentinel.
- Layer 2: ask Claude to run `git add some_%04i.png` in any project — the PreToolUse hook must reject before the command runs. (Manual verification only; no automated harness for the python-tui-lib hooks today.)
- Existing checked-in paths with `%` (none today, per `git ls-files | grep '%'` returning empty) keep working.

## Risks

- **False positives**: a path like `100%discount.txt` would not trigger (no format-letter follows). A path like `data_%s_v2.csv` would (per regex), which is correct — `%s` *is* a format specifier and a real trap.
- **Human bypass**: `git commit --no-verify` skips Layer 1. Acceptable; the hook is a guardrail, not a lock.
- **Layer 2 blast radius**: editing the shared `~/python-tui-lib/hooks/git-add-guard.sh` affects every Claude session in every project. If anyone has a legitimate reason to stage a `%`-format-trap file (unlikely), they'd need to bypass via raw bash. Worth asking before landing Layer 2.

## Acceptance criteria

1. `scripts/git-hooks/pre-commit` exists in the repo; chmod +x; rejects new printf-trap paths.
2. README (or equivalent) tells a fresh contributor to run `git config core.hooksPath scripts/git-hooks` once after clone.
3. The python-tui-lib `git-add-guard.sh` rejects printf-trap paths in the `git add` command line — **gated on user approval before landing.**

## Out of scope

- Tracking down which screen-grab/MAME tool produced `auto_%04i.png`. Flagged in Layer 3.
- Catching `%` in non-format positions (e.g. `100%saved.txt`). Hook regex is targeted at format specifiers only.
- Pushing the four already-existing unpushed local commits (`74008c5`, `78da6f3`, `fd67ea8`, `172ae4d`) — separate decision, awaiting user.
