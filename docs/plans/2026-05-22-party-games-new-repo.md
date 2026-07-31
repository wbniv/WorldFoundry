# party-games — publish to new standalone GitHub repo

**Status:** Done — 2026-05-22
**Goal:** Give `~/party-games` its own remote under `wbniv` (personal account, separate from WorldFoundry entirely) so it is no longer local-only.

## Context

`~/party-games` is a Node/web party-game platform (multi-room, controller shell, "Worst Take Wins" and other games). It has been local-only since creation — no remote, no upstream, not connected to the WorldFoundry repo in any way. The [FoundryLinux migration plan](2026-05-22-foundrylinux-migration-audit.md) flagged it as "commits existing only on this disk." Giving it a remote removes that risk permanently.

One dirty tracked file: `platform/controller-shell/controller.css` — commit before pushing.

## Steps

1. Commit the dirty CSS.
2. `gh repo create wbniv/party-games --private --source ~/party-games --remote origin --push` — creates the repo, wires `origin`, pushes all history in one shot.
3. Verify remote + pushed commit count.
4. Remove `party-games` from the UNRECOVERABLE risk table in [2026-05-22-foundrylinux-migration-audit.md](2026-05-22-foundrylinux-migration-audit.md).

## Verification

- `git -C ~/party-games remote -v` shows `origin https://github.com/wbniv/party-games.git`
- `gh repo view wbniv/party-games --json name,visibility,pushedAt`
