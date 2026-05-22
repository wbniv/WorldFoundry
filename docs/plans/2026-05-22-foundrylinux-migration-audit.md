# FoundryLinux migration — pre-reformat audit & backup plan

**Status:** Not started — 2026-05-22
**Goal:** Wipe `will-ME-mini` and install [FoundryLinux](https://foundrylinux.org/) without losing anything, by first *proving* every git repo is recoverable and pre-emptively backing up everything that isn't.

## Context

[FoundryLinux](https://foundrylinux.org/) is an [Ubuntu](https://ubuntu.com/) 26.04 LTS desktop with the WorldFoundry GDK (plus Blender, MAME, Ghidra, audio tools) baked in from first boot — so reformatting onto it is partly dogfooding our own project's distro. The worry driving this plan is that the disk holds something not yet safely in git. Because a reformat is **irreversible**, the plan front-loads a read-only audit and a [git bundle](https://git-scm.com/docs/git-bundle) safety net before anything is wiped.

Editions: Anvil (3.7 GB base), Sprite (5.0 GB +graphics/audio), Atelier (18.3 GB everything). Minimum: 20 GB free, 4 GB RAM (8 GB rec.), Vulkan 1.2 GPU. It can also install on top of an existing Ubuntu 26.04 via its apt repo, or run from prebuilt VirtualBox/VMware/QEMU images — worth a VM dry-run before committing the metal.

## Decisions

- **Safety net = home-dir archive, NO OS disk image.** `tar | zstd` of `~/` *after* the cleanup below, excluding regenerable caches/build dirs/the 4 GB Chrome model (and optionally the re-clonable git object stores). OS and apps get reinstalled fresh on FoundryLinux. Paired with git bundles for local-only history.
- **Single destination: Google Drive via [rclone](https://rclone.org/).** Home archive + bundles + encrypted secrets all upload there; no external drive. The cleanup is what keeps the archive Drive-practical (~5–9 GB).
- **Secrets encrypted with [age](https://github.com/FiloSottile/age) before upload** (SSH keys, GnuPG, keyrings, WiFi/VPN creds) — never plaintext in cloud.
- Migration scripts staged in `~/foundrylinux-migration/`, committed into the `~/homedir` repo (it has a remote → survives the wipe).

## Findings — live audit (read-only, 2026-05-22)

Disk: `/dev/nvme0n1p2` 915 GB, **53 GB used**. `~/` = 27 GB. **Single ext4 data partition** — no second disk, no extra mounts.

### Repo topology — the `WorldFoundry.*` siblings are git *worktrees*

Six worktrees share one object store (`~/WorldFoundry/.git`). A naïve `find -type d -name .git` misses them (a worktree's `.git` is a *file*, not a dir). The audit script handles both.

### Commits / refs that exist ONLY on this disk (the real risk)

| Repo / branch | Risk |
|---|---|
| `WorldFoundry.spike` → `spike/nongeom-zero-bbox` | branch never pushed (no upstream) |
| `WorldFoundry.iff-ydoc-translator` → `2026-iff-ydoc-translator` | branch never pushed (no upstream) |
| `WorldFoundry` (main) | **3 stashes** — not on any branch, lost on wipe |
| `WorldFoundry.2026-ios` | 21 unpushed commits |
| `wf-games` | 9 unpushed |
| `parking-space` | 5 unpushed |
| `~` (home repo) | 3 unpushed |
| `worldfoundry.org` | 1 unpushed |

**Uncommitted work** (recoverable only if files are backed up): this worktree (`2026-new-level`) has 12 modified tracked files (incl. `wf-status.md`, `wfsource/source/gfx/camera.cc`, `backend_modern.cc`, the smb `.iff/.lev/.lvl`) + 14 untracked **valuable** docs under `docs/{plans,investigations,transcripts}`. `iff-ydoc-translator` has 5 dirty.

### Biggest regenerable space hogs — delete before archiving

| Path | Size | Note |
|---|---|---|
| `.config/google-chrome/OptGuideOnDeviceModel/.../weights.bin` | **4.07 GB** | Chrome on-device AI model, re-downloads |
| `.rustup` / `.gradle` / `.cache` / `.cargo` | 2.3 / 1.2 / 0.8 / 0.4 GB | toolchain caches |
| `snap/firefox/common/.cache` | 1.3 GB | browser cache |
| `~/tmp/mame-snaps` + `mame_output` | 1.5 GB | scratch captures |
| `build-editor` + `cmake-build-asan` (this worktree) | 2.2 GB | ×6 worktrees → many GB |
| `worldfoundry.org/node_modules` | 0.24 GB | pnpm-regenerable |
| `.local/share/claude/versions/*` (4 kept) | ~0.9 GB | keep current only |
| `.local/share/Trash` | 0.14 GB | empty it |

### Genuinely not-in-git, not-regenerable — back up

`~/.ssh` (has `id_rsa` + legacy `id_dsa` private keys), `~/.gnupg`, `~/.local/share/keyrings` (GNOME keyring → Chrome/login passwords), `~/.gitconfig`, browser bookmarks/logins (Chrome `Default/`, Firefox `o0fv5h2g.default` incl. WhatsApp-Web session), `~/Documents/Obsidian Vault`, `~/Pictures` (54 MB), `~/Downloads` (203 MB, triage). The judgment-call media is **tiny** (gameplay mp4s 3.5 MB, arcade ROM zips 336 KB, polyhaven/opengameart ~5 MB) → keep all. The existing `wf-backup-2026-05-11.bundle` shows this bundle pattern is already in use.

## Outside `~/` — what else to capture (this box, specifically)

A home-only archive misses root-owned config. On `will-ME-mini` the gap is **small and specific** (single ext4 data partition, only user `will`, `/usr/local/bin` empty, no Docker/VMs/databases, no custom system services or cron). Capture these — secret ones into the **encrypted** archive:

- **WiFi + [Surfshark](https://surfshark.com/) VPN credentials** — `/etc/NetworkManager/system-connections/*.nmconnection` (root:root 0600, holds PSKs). The item most likely to lock you out post-install. → encrypted archive.
- **SSH server identity** (optional) — `/etc/ssh/sshd_config` + `/etc/ssh/ssh_host_*`; keep only if other hosts trust this box as a server, else regenerate. → encrypted archive.
- **Third-party apt repo** — `/etc/apt/sources.list.d/tailscale.list` (re-add the [Tailscale](https://tailscale.com/) repo + key on the new box). → `system-metadata/` (not secret).
- **Tailscale node state** (optional) — `/var/lib/tailscale/`; or just `sudo tailscale up` to re-auth.
- **`/etc` reference snapshot** — `sudo tar czf etc-2026-05-22.tar.gz /etc` for consulting hosts/hostname/fstab/netplan; don't restore wholesale onto FoundryLinux.

Already covered by the home archive (no extra action): the Obsidian vault, [Thunderbird](https://www.thunderbird.net/)/Firefox/Surfshark snap data (`~/snap/`), and the custom `screenshot-cleanup` **user** systemd timer (`~/.config/systemd/user/`).

## Deliverable scripts

### `~/foundrylinux-migration/audit-before-wipe.sh` (read-only)

Proves recoverability. **Exits non-zero** while anything lives only on this disk, writing `UNRECOVERABLE.txt`.

```bash
#!/usr/bin/env bash
# audit-before-wipe.sh — pre-reformat safety audit (READ-ONLY).
set -euo pipefail
ROOT="${ROOT:-$HOME}"
OUT="${OUT:-$HOME/foundrylinux-migration}"; mkdir -p "$OUT/system-metadata"
REPORT="$OUT/audit-report.txt"; RED="$OUT/UNRECOVERABLE.txt"; : >"$REPORT"; : >"$RED"
say(){ printf '%s\n' "$*" | tee -a "$REPORT"; }
red(){ printf '%s\n' "$*" >>"$RED"; }
say "FoundryLinux migration audit — $(date -Is) — host $(hostname)"; say "============"

say "A. GIT REPOSITORIES & WORKTREES (find matches .git dirs AND worktree .git files)"
mapfile -t WTS < <(find "$ROOT" -name .git -prune 2>/dev/null | sed 's#/\.git$##' | sort -u)
declare -A SEEN
for wt in "${WTS[@]}"; do
  git -C "$wt" rev-parse --is-inside-work-tree >/dev/null 2>&1 || continue
  rel="${wt#$ROOT/}"; [ "$wt" = "$ROOT" ] && rel="~"
  dirty=$(git -C "$wt" status --porcelain 2>/dev/null | grep -vc '^??' || true)
  untrk=$(git -C "$wt" status --porcelain 2>/dev/null | grep -c '^??' || true)
  say ""; say "WORKTREE $rel  (dirty=$dirty untracked=$untrk)"
  [ "$dirty" -gt 0 ] && say "  ! uncommitted tracked changes — commit or back up files"
  common=$(cd "$wt" && readlink -f "$(git rev-parse --git-common-dir)")
  [ -n "${SEEN[$common]:-}" ] && continue; SEEN[$common]=1   # shared store: refs once
  [ -z "$(git -C "$wt" remote)" ] && { say "  !! NO REMOTE — repo lives only here"; red "$rel : NO REMOTE (bundle it)"; }
  while IFS='|' read -r br up track; do
    if [ -z "$up" ]; then say "  !! branch '$br' NO UPSTREAM (never pushed)"; red "$rel : branch $br no upstream";
    elif printf '%s' "$track" | grep -q ahead; then say "  ! branch '$br' $track vs $up"; red "$rel : branch $br $track"; fi
  done < <(git -C "$wt" for-each-ref --format='%(refname:short)|%(upstream:short)|%(upstream:track)' refs/heads)
  ns=$(git -C "$wt" stash list 2>/dev/null | wc -l)
  if [ "$ns" -gt 0 ]; then say "  !! $ns STASH(es) — lost on wipe:"; git -C "$wt" stash list | sed 's/^/      /' | tee -a "$REPORT"; red "$rel : $ns stash(es)"; fi
done

say ""; say "B. NON-GIT DATA under $ROOT (top level by size)"
du -h -d1 "$ROOT" 2>/dev/null | sort -h | sed 's/^/  /' | tee -a "$REPORT"
say ""; say "B1. REGENERABLE — delete before backup:"
for p in .cache .gradle .rustup .cargo .npm .local/share/Trash \
         ".local/share/claude/versions" "snap/firefox/common/.cache" \
         ".config/google-chrome/OptGuideOnDeviceModel" tmp/mame-snaps tmp/mame_output; do
  for g in "$ROOT/"$p; do [ -e "$g" ] && say "  rm  ${g#$ROOT/}  ($(du -sh "$g" 2>/dev/null|cut -f1))"; done
done
say "  + build dirs across worktrees: build-editor cmake-build-asan objs_game node_modules"

say ""; say "C. SECRETS to ENCRYPT before any cloud upload:"
for d in .ssh .gnupg .gitconfig .local/share/keyrings; do [ -e "$ROOT/$d" ] && say "  $d ($(du -sh "$ROOT/$d" 2>/dev/null|cut -f1))"; done

say ""; say "D. PROVISIONING CAPTURE -> $OUT/system-metadata/"
M="$OUT/system-metadata"
apt-mark showmanual >"$M/apt-manual.txt" 2>/dev/null||true
dpkg --get-selections >"$M/dpkg-selections.txt" 2>/dev/null||true
snap list >"$M/snap-list.txt" 2>/dev/null||true; flatpak list >"$M/flatpak-list.txt" 2>/dev/null||true
command -v rustup>/dev/null && rustup toolchain list >"$M/rustup.txt" 2>/dev/null||true
crontab -l >"$M/crontab.txt" 2>/dev/null||true; lsblk -f >"$M/lsblk.txt" 2>/dev/null||true
cp -r /etc/apt/sources.list.d "$M/" 2>/dev/null||true   # third-party apt repos (tailscale)
say "  (apt-manual, dpkg-selections, snap, flatpak, rustup, crontab, lsblk, sources.list.d)"

say ""; say "E. OUTSIDE \$HOME — grab with sudo at backup time (root-only):"
say "  /etc/NetworkManager/system-connections/  WiFi + Surfshark VPN creds   -> ENCRYPT"
say "  /etc/ssh/ssh_host_*                       SSH server identity (optional) -> ENCRYPT"
say "  /etc (reference: hosts hostname fstab netplan sshd_config)"
say "  /var/lib/tailscale (optional; 'sudo tailscale up' re-auths instead)"

say ""; say "============"
if [ -s "$RED" ]; then
  say "RESULT: NOT SAFE TO WIPE — $(wc -l <"$RED") item(s) only on this disk:"; sed 's/^/  /' "$RED" | tee -a "$REPORT"
  say "Run bundle-all-repos.sh, push what you can, then re-run until clean."; exit 1
else say "RESULT: all git history reachable on a remote. Proceed to backup + archive."; fi
```

### `~/foundrylinux-migration/bundle-all-repos.sh`

Captures local-only history. Per shared object store, it **snapshots each stash to a `stashbak/N` tag** so `--all` includes them, then `git bundle create … --all`. Restore later via `git clone <bundle>` / `git fetch`; stashes recovered from the `stashbak/*` tags.

```bash
#!/usr/bin/env bash
set -euo pipefail
OUT="${OUT:-$HOME/foundrylinux-migration/bundles}"; mkdir -p "$OUT"
mapfile -t WTS < <(find "$HOME" -name .git -prune 2>/dev/null | sed 's#/\.git$##' | sort -u)
declare -A DONE
for wt in "${WTS[@]}"; do
  git -C "$wt" rev-parse --is-inside-work-tree >/dev/null 2>&1 || continue
  common=$(cd "$wt" && readlink -f "$(git rev-parse --git-common-dir)")
  [ -n "${DONE[$common]:-}" ] && continue; DONE[$common]=1
  name=$(basename "$(dirname "$common")"); [ "$name" = "$(basename "$HOME")" ] && name="home"
  n=$(git -C "$wt" stash list | wc -l)
  for ((i=0;i<n;i++)); do git -C "$wt" tag -f "stashbak/$i" "stash@{$i}" 2>/dev/null || true; done
  git -C "$wt" bundle create "$OUT/$name-$(date +%F).bundle" --all
  echo "bundled $name -> $OUT/$name-$(date +%F).bundle"
done
echo "Verify any bundle later: git bundle verify <file>"
```

## Execution checklist

1. **Commit & push** valuable work: commit this worktree's modified files + the untracked `docs/{plans,investigations,transcripts}` (they belong in the WF repo); push `2026-ios` (21), `wf-games` (9), `parking-space` (5), `worldfoundry.org` (1), `~` home (3).
2. Run `audit-before-wipe.sh` → fix until `UNRECOVERABLE.txt` is empty (or consciously accept bundle-only).
3. Run `bundle-all-repos.sh` → captures `party-games` (no remote), the two no-upstream branches, all 3 stashes.
4. **Cleanup** the B1 regenerable list (~15–20 GB reclaimed) so the archive stays Drive-sized.
5. **Encrypt secrets** (incl. root-owned net creds):
   `sudo tar czf - -C "$HOME" .ssh .gnupg .local/share/keyrings .gitconfig -C / etc/NetworkManager/system-connections etc/ssh/ssh_host_* | age -p > secrets-2026-05-22.tar.age`
   Also keep a plain `sudo tar czf etc-2026-05-22.tar.gz /etc` reference.
6. **Archive home** (after cleanup):
   `tar -C "$HOME" --exclude-from=home-excludes.txt -cf - . | zstd -T0 -19 > oldbox-home-2026-05-22.tar.zst`
   where `home-excludes.txt` lists the B1 paths + `*/build-editor */cmake-build-asan */node_modules */objs_game` (+ optionally the re-clonable repos, since remotes+bundles already cover them). Write a `.sha256` and a `tar tf` manifest beside it.
7. **Upload to Drive:**
   `rclone copy --progress oldbox-home-2026-05-22.tar.zst secrets-2026-05-22.tar.age bundles/ system-metadata/ gdrive:backup/oldbox-will-ME-mini-2026-05-22/`
   then `rclone check` to confirm integrity.

## How to retrieve the home archive later

- It's one Drive folder: `gdrive:backup/oldbox-will-ME-mini-2026-05-22/`. List with `rclone ls …`; pull with `rclone copy … ./restore/`.
- **Browse before downloading the whole thing:** grep the manifest sidecar, or stream-list: `zstd -dc oldbox-home-2026-05-22.tar.zst | tar tvf - | less`.
- Extract one path: `zstd -dc …tar.zst | tar xf - path/inside/home`. Decrypt secrets: `age -d secrets-….tar.age | tar xz`.
- The Drive folder name (`oldbox-<host>-<date>`) *is* the reference; keep the `.sha256` + manifest in it.

## Verification (before wiping)

- Re-run `audit-before-wipe.sh` → exit 0, empty `UNRECOVERABLE.txt`.
- `git bundle verify <each>.bundle`; spot-clone one into `/tmp` and confirm a stash recovers from its `stashbak/0` tag.
- `age -d secrets-….tar.age | tar tz` lists `.ssh/`, `.gnupg/`, keyrings, `etc/NetworkManager/…` — proves the encrypted archive is intact and decryptable.
- `zstd -t oldbox-home-2026-05-22.tar.zst` (integrity) and `zstd -dc …tar.zst | tar tf - | grep -E 'Pictures|Obsidian|docs/plans|\.bashrc'` — proves expected files are inside.
- `rclone ls …` shows expected sizes; `rclone check` confirms upload integrity.

## Post-install (FoundryLinux) restore

Clone repos from remotes; `git fetch` the bundles for local-only branches / `party-games`; `age -d` + untar secrets (including WiFi/VPN connection files into `/etc/NetworkManager/system-connections/`, `chmod 600`); pull `oldbox-home-…tar.zst` from Drive and extract non-repo files (Obsidian vault, Pictures, triaged Downloads, configs); re-add the Tailscale apt repo; reinstall packages from `system-metadata/apt-manual.txt`; reinstall toolchains via `rustup` / `pnpm` (deliberately not backed up). FoundryLinux ships Blender/MAME/Ghidra/WorldFoundry GDK, so much of `~/opt` won't need rebuilding.
