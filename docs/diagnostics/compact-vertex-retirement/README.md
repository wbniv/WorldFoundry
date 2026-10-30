# Compact vertex checkout comparison

Compared `/home/will/WorldFoundry-wbniv-vertex`, branch `perf/compact-vertex`,
at `68198511`, with the v0.10 port on `2026-new-level` at `d5a686a2`.

- Original `d22a79ab` maps to cherry-pick `23d2ee1e`. The compact vertex
  header and two dedicated test files are byte-identical at those commits.
  The backend patch was adapted to the port's newer shader and palette paths;
  `git range-diff d22a79ab^..68198511 23d2ee1e^..4e036f96` shows the
  differences. The renderer files as a whole are not identical.
- Original `68198511` maps to cherry-pick `4e036f96`, but the port is not
  equivalent: its parent already defined `gActiveDisplay` and
  `Display::GetActive()` in each Metal display implementation. The cherry-pick
  adds another definition in `gfx/display.cc`, which includes those files in
  the same translation unit. It also repeats constructor and destructor
  assignments. This produces redefinitions for iOS and macOS. The fix keeps
  the existing per-platform definitions and removes the duplicate additions.
  Both target translation units passed host C++ syntax checks using Linux GL
  headers as substitutes; this is not a full build against an Apple SDK.
- The seven untracked `.ht` files in the original checkout are byte-identical
  to the corresponding untracked files in the main checkout.
- [The untracked screenshot](wfmut_bridge_regression.png) was copied without
  modification. Both copies have SHA-256
  `7d2178a9c1f5ca1060efc027bb0aa2da2157e5b1a6750ec184deb0961f333e0c`.

The original checkout was retired after the comparison; the local and remote
`perf/compact-vertex` branch refs remain at `68198511`.
