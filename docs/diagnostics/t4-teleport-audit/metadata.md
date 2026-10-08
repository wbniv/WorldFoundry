# T4 validation metadata

- Base commit: `2b893d484a11cb7398d8ce482ad830cd31b82e22`.
- Branch/worktree: `teleport-audit`, `/home/will/WorldFoundry-wbniv/.worktrees/teleport-audit`.
- Configuration: native Linux Release, Jolt, zForth, Lua 5.4, debug bridge enabled; JavaScript/WASM/Fennel/Wren disabled; ASan off; `WF_TELEPORT_UBSAN=ON` instruments production `room/actrooms.cc`.
- Both `WF_DEBUG_DEFINES=ON` and `OFF` exercised. Final worktree build has assertions off.
- GL display: existing `:0`; each harness owned its process and private loopback port. Xvfb was unavailable.
- Final following-camera standalone fixture SHA-256: `9f452ca4c2102c572104c100aa1d6c95e52ffbee4cd3cf25a506202aac4a4f57`.
- Assertions-on camera/position-mailbox binary SHA-256: `223edefe044454f2813d73d6c62e4f70076ec3640d6450d532825a950556490d` (before the one-line transform notification).
- Final assertions-off binary SHA-256: `fb5141010e1537f464a7eefb1d1412d612ae775e11006f59f852b53a83d2dd91`.

## Evidence layout

| Directory/file | Meaning |
| --- | --- |
| `baseline-transition/` | Real-engine null `Room` member call under UBSan before unbind fix |
| `baseline-scale/` | Independent unloaded scale write with zero teleports; line-buffered stdout |
| `baseline-camera/` | Correctly authored relative camera strands between A/B before camera fix |
| `baseline-mutation/` | Transform API bypasses teleport notification before one-line mutation fix |
| `camera-release/` | 140 script teleports plus single-frame boundary screenshots, assertions off |
| `t4-camera-final-ctest.log` | Final assertions-on full suite, 22/22 including the permanent script-camera regression |
| `final-release/` | Permanent script-camera regression, final release configuration |
| `final-mutation/` | Permanent transform-API regression, final release configuration |
| `chapter-integration/` | 15 level-owned Parmenides scene9 tour transitions; exact level/runtime hashes |
| `fixture-fixed/`, `fixture-follow/`, `fixture-final/` | Baseline and final fixture receipts and historical input levels |
| `*.log` | Configure/build/test output, including failing runs |
| `chapter-probe.py` | Integration probe; accelerates review timer only |
| `review.patch` | Reviewable text diff against the base, including new tests/docs |

Receipts preserve original run paths and commands, including temporary paths. Copies here retain those historical records. Android Release verification subsequently passed on both 32-bit Chromecasts; see [the device review](android-review.md). The assertions-on full suite predates the final one-line transform notification; transform integration was verified in the final assertions-off build with both existing `wfmut` tests.

Generated OAS `.ht` files and the existing `wfmut` test screenshot are build/test products, outside the scoped patch. Engine implementation and regression tooling are committed as `c92ca353`; this evidence accompanies that change. No merge to the main checkout was made.

Frozen device APKs and the original/stripped native libraries are retained locally under `build-teleport/android-verification/` (ignored build artifacts). Their hashes are recorded in the Android input receipts; the coordinator retains its immutable APK inputs and job evidence.
