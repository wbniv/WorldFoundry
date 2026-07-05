# TODO

## Open

### Repo / branch hygiene

- [ ] **Reconcile the forked `2026-new-level` histories (local vs `origin/2026-new-level`).** The two lines split at `71727ab4` (2026-04-14) and both carry real, non-overlapping work: this local line has 593 commits since the split (through 2026-05-19; docs/tooling work — md-to-pdf, python-tui-lib, memory stub), while the remote line has 1657 commits (through 2026-06-26) including the entire `engine/` tree and the `wf_edit` collaborative editor (native ImGui + wasm web build, CRDT sync via yffi, WebRTC voice/video, presence/chat, one-click `.lev` export). 592 of the 593 local commits have no patch-equivalent upstream, so this needs a deliberate merge (or a rename of one line) — not a fast-forward, and definitely not a reset. Note: the remote line already has its own root `TODO.md`, so expect a (trivial) conflict on this file when reconciling.
