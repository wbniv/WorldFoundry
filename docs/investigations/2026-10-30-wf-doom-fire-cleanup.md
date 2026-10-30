# Doom Fire stale worktree cleanup

**Checked:** 2026-10-30. The `/tmp/wf-doom-fire` directory was already absent when this review began, so no checkout or build outputs remained there to remove. Its Git worktree registration was stale and has now been pruned.

The former local branch `fix/doom-fire-cast1` had eight non-merge commits beyond `2026-new-level`, ending at `421df720095017144034daac20dbfda06b5bd320`. The current engine branch does not contain the branch's `wfsource/source/game/doom_fire.{hp,cc}` or `tests/doom_fire_test.cc`; `git cherry -v` also reports all eight patches as unmatched. This is unique engine work, not a completed integration into the current branch.

Before deleting the redundant **local** ref, `git ls-remote --heads origin fix/doom-fire-cast1` confirmed that the server's branch points to exactly `421df720095017144034daac20dbfda06b5bd320`. The local ref was then deleted. `origin/fix/doom-fire-cast1` remains, and the existing [chapter diagnosis](../../../finding-your-way/docs/diagnostics/doom-fire-2026-10-29/README.md) records the device evidence. No remote ref or engine code was changed.

**Disk result:** only a small stale Git registration was removed. The missing `/tmp` checkout had already freed its disk space. Deleting the local branch ref does not free its Git objects because the verified remote branch still retains them. The remaining Doom Fire work should be evaluated for integration separately; deleting the remote branch would risk losing unique code and would not address a present checkout directory.
