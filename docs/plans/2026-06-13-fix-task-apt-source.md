# Fix the broken `task` apt source — migrate to the live cloudsmith path (Option B)

**Date:** 2026-06-13
**Status:** DONE 2026-06-14 — manual binary moved aside (`task` now resolves to `/usr/bin/task` 3.51.1); dead artefacts already absent; verification V2–V6 PASS. Remaining: one sudo `apt update` (V1) + delete the move-aside backup (step 6), both `[user]`.
**Topic:** `apt update` fails on the go-task (Taskfile) cloudsmith source; re-point at the live repo via the official setup script, and make apt the owner of `task`.

> **Mid-execution discovery (2026-06-13):** `task` is **already packaged in the foundry repo** (`apt.foundrylinux.org resolute/main`) as `3.51.1-1foundry1` — the self-hosting I'd filed as a deferred follow-up was already done. After the setup script ran, `task` is now installed via dpkg at `/usr/bin/task` from **foundry** (it wins the version race vs cloudsmith's `3.51.1` because of the `-1foundry1` revision). **Decision (user, "Keep both"):** keep the now-fixed cloudsmith source *and* the foundry source — cloudsmith auto-delivers upstream updates, foundry stays the self-hosted winner. Cloudsmith's `questing` path is live (`…/deb/ubuntu/dists/questing/Release` → 200), so `apt update` is clean. Accepted trade-off: cloudsmith path/layout churn could break `apt update` again. The original "remove the redundant cloudsmith source" branch was **not** taken.

---

## Context — what's actually broken (verified)

`apt update` errors with:

```
Error: The repository 'https://dl.cloudsmith.io/public/task/task/deb/any-distro any-version Release' does not have a Release file.
```

Diagnosis (all probed 2026-06-13):

- **go-task is NOT abandoned.** The cloudsmith repo's current `task` is **v3.51.1**, Release file dated **2026-05-16**. (Local binary is 3.49.1 — a couple versions behind.)
- **The cloudsmith repo is NOT shut down or moved off cloudsmith.** It is alive — full component set, arches `amd64 arm64 armhf i386 riscv64`.
- **Root cause:** cloudsmith **retired the `any-distro` catch-all distro segment**. They now serve under per-distro paths. Evidence:

  | URL | HTTP |
  |-----|------|
  | `…/deb/any-distro/dists/any-version/Release` (what `task.list` pointed at) | **404** |
  | `…/deb/ubuntu/dists/any-version/Release` | **200** |
  | `…/deb/debian/dists/any-version/Release` | **200** |

  The `any-version` codename is still a valid catch-all suite; only the distro segment is stale. The old `task.list` was written by a previous version of cloudsmith's `setup.deb.sh` (or hand-copied) before the layout migration. Matches go-task issue [#2585](https://github.com/go-task/task/issues/2585) (cloudsmith mirror sync/layout problems, 2026).

### Current machine state (2026-06-13)

- `/etc/apt/sources.list.d/task.list` was already renamed to **`task.list.bak`** (earlier in this session), so `apt update` is currently unblocked but `task` gets no apt updates.
- `task` binary in use: **`/home/will/.local/bin/task` v3.49.1** — a hand-placed static Go binary, never managed by apt.
- **PATH ordering:** `~/.local/bin` precedes `/usr/bin`. ⚠️ This means a future `/usr/bin/task` from apt would be **shadowed** by the manual binary unless the manual one is removed.
- Orphan-to-be: old key `/etc/apt/keyrings/task.gpg` (referenced only by the now-`.bak` source).
- Distro: Ubuntu 25.10 (`questing`), so the setup script will auto-detect `distro=ubuntu`.

---

## Goal

Make **apt** the owner of `task`, upgrading the effective `task` from 3.49.1 → 3.51.1, with no **dead** sources or shadowing binaries left behind. (The cloudsmith + foundry source *pair* is intentional per the "Keep both" decision, not a duplicate to clean up.)

## Decision

**Option B — re-run the official cloudsmith setup script**, rather than hand-patching `any-distro` → `ubuntu` in the old file. Rationale: it's the canonical, self-correcting path (writes the current source + key the way upstream maintains it), and it gets us current. Trade-off accepted: it writes a *new* file `task-task.list`, so we must remove the old dead `.bak` + orphan key, and we must remove the manual `~/.local/bin/task` to defeat PATH shadowing.

**Revised after the foundry discovery (user chose "Keep both"):** `task` is already self-hosted in the foundry repo and now installed from it, so the cloudsmith source is *redundant* but kept anyway as the auto-updating upstream feed; foundry stays the self-hosted winner. We therefore do **not** remove the cloudsmith source/key (`task-task.list`, `task-task-archive-keyring.gpg`) — only the genuinely dead artefacts from the original `any-distro` setup (`task.list.bak`, `/etc/apt/keyrings/task.gpg`).

---

## Steps

Commands marked **[user]** need `sudo` (password required) — run them in-session with the `!` prefix. Commands marked **[claude]** are read-only verification Claude runs.

1. ~~**[user]** Run the official setup script (detects `ubuntu`/`questing`, writes `/etc/apt/sources.list.d/task-task.list` + installs the current cloudsmith key, runs `apt update`).~~ **DONE** — wrote `task-task.list` (`…/deb/ubuntu questing main`, `signed-by=/usr/share/keyrings/task-task-archive-keyring.gpg`). (`sudo -E` warned `-E ignored` under sudo-rs — harmless, default env is fine.)
   ```
   ! curl -1sLf 'https://dl.cloudsmith.io/public/task/task/setup.deb.sh' | sudo -E bash
   ```

2. ~~**[user]** Install/upgrade `task`.~~ **DONE (via foundry, not cloudsmith)** — `task 3.51.1-1foundry1` installed at `/usr/bin/task` from `apt.foundrylinux.org` (won the version race vs cloudsmith's `3.51.1`).
   ```
   ! sudo apt install task
   ```

3. **[user] ⟵ REMAINING.** Remove the manual binary so the apt-managed `/usr/bin/task` wins PATH (⚠️ required — `command -v task` still resolves to the old `~/.local/bin/task` 3.49.1 until this runs). Move-aside first for reversibility:
   ```
   ! mv /home/will/.local/bin/task /home/will/.local/bin/task.manual-bak && hash -r
   ```

4. **[user] ⟵ REMAINING.** Clean up the genuinely dead artefacts from the original `any-distro` setup (do **not** touch the new cloudsmith source/key — "Keep both"):
   ```
   ! sudo rm -f /etc/apt/sources.list.d/task.list.bak /etc/apt/keyrings/task.gpg
   ```

5. **[claude]** Run the verification section below; paste raw output under each step.

6. **[user]** Once verified, delete the move-aside manual binary:
   ```
   ! rm -f /home/will/.local/bin/task.manual-bak
   ```

---

## Verification

Run each step; paste raw output in the code block, then PASS/FAIL.

### 1. `apt update` is clean (no Release-file error on the task source)
```
[ command: sudo apt update 2>&1 | grep -iE "task|error|release file" ]
( pending — needs sudo; run in-session: ! sudo apt update )
```
PASS/FAIL: PENDING (sudo)

### 2. The active source points at the live `ubuntu` path, and the dead `.bak` is gone
```
deb [signed-by=/usr/share/keyrings/task-task-archive-keyring.gpg] https://dl.cloudsmith.io/public/task/task/deb/ubuntu questing main
deb-src [signed-by=…] …/deb/ubuntu questing main
/etc/apt/sources.list.d/task-task.list      # only file; no task.list.bak
```
PASS/FAIL: **PASS** (2026-06-14)

### 3. `task` is now the apt-managed binary at `/usr/bin/task`
```
/usr/bin/task
task: /usr/bin/task
```
PASS/FAIL: **PASS** (2026-06-14)

### 4. Version is current (3.51.1), not the old 3.49.1
```
3.51.1
```
PASS/FAIL: **PASS** (2026-06-14)

### 5. No manual binary left shadowing it
```
# manual binary moved aside to /home/will/.local/bin/task.manual-bak (step 6 deletes it).
# `which -a task` → /usr/bin/task, /bin/task  (no .local/bin entry)
```
PASS/FAIL: **PASS** (move-aside; step 6 deletes the backup)

### 6. Project tasks still run against the new binary
```
task: Available tasks for this project:
* android-sdk-install:   …
* asset-browser-install: …
( full Taskfile list, no errors )
```
PASS/FAIL: **PASS** (2026-06-14)

---

## Rollback

- **Restore the manual binary:** `mv ~/.local/bin/task.manual-bak ~/.local/bin/task && hash -r` (before step 6 deletes it).
- **Remove the apt-managed package:** `sudo apt remove task`.
- The old `any-distro` source is intentionally not restorable — it was dead (404). If apt itself misbehaves, `sudo rm /etc/apt/sources.list.d/task-task.list` returns you to "no task apt source," and the restored manual binary keeps `task` working.

---

## References

- Official install docs: [taskfile.dev/installation](https://taskfile.dev/installation/)
- go-task issue (cloudsmith mirror layout/sync, 2026): [go-task/task#2585](https://github.com/go-task/task/issues/2585)
- Live repo Release: `https://dl.cloudsmith.io/public/task/task/deb/ubuntu/dists/any-version/Release`
