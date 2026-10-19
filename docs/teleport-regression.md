# Cross-room teleport regression

The four-room fixture uses A at X=0, B=100, C=200 and disconnected D=300. A lists B and C; B and C list A; D has no neighbours. Every room owns a transient mesh. Player and camera use permanent MBR assets. The Player's Forth script performs teleports through ordinary position mailboxes.

Build with the existing engine configuration, `WF_DEBUG_BRIDGE=ON`, zForth enabled and optional `WF_TELEPORT_UBSAN=ON`. The latter instruments the production room-transition translation unit with UBSan. A GL display is required; validation used the desktop display `:0`, an owned process and a private loopback debug port.

```sh
ctest --test-dir build-teleport -R cross_room_teleports --output-on-failure
```

For a longer session:

```sh
python3 tests/verify_cross_room_teleports.py --binary engine/wf_game --level wflevels/teleport_regression-standalone.iff --out /tmp/teleport-regression --laps 20 --require-camera --audit-boundary
```

The test checks script acknowledgement, final Player pose, exact following-camera X, unloaded scale caching and absence of pointer/sanitizer/script diagnostics. It captures a paused single script frame to establish immediate camera arrival, and confirms a small same-room position write does not force a camera jump. It owns and terminates only its own engine process. Receipts and logs survive failures.

`cross_room_teleports_mutation` uses the same fixture with `--mutation`, driving `wfmut::SetActorPos` through `scene:set_transform`. Its main loop checks actual pose rather than the script acknowledgement. Its paused boundary checks still exercise the script entry point.

Regenerate the fixture using existing compiler binaries:

```sh
python3 tests/generate_teleport_level.py --tools /home/will/WorldFoundry-wbniv/wftools --out /tmp/teleport-fixture --camera follow
cp /tmp/teleport-fixture/teleport_regression-standalone.iff wflevels/teleport_regression-standalone.iff
```

The generator records source, tool and output hashes. `--camera fixed` isolates room-memory and scale behavior from camera movement; use that variant for the historical unbind/null and scale-only reproductions. A scale-only run uses `--laps 0` without `--require-camera` or `--audit-boundary`.

The original fixture tests a watched, MBR Player moving between valid rooms,
with a camera shot authored to follow its destination. The additional
`unloaded_actor_teleports` CTest uses `unloaded_actor_regression-standalone.iff`
to verify non-watched MBR actors moved by an active script from inactive rooms:
membership repair, deferred asset binding, exact next-frame updates, inactive
destination scheduling and repeated returns. See the
[fix and evidence](diagnostics/unloaded-actor-fix.md). Ordinary physics walking
retains its current camera behavior. These anchored fixtures do not establish
all dynamic-body collisions or non-MBR relocation. See
[the audit review](teleport-audit.md) for evidence and unresolved boundaries.

For coordinator-owned device testing, generate with `--camera follow --autonomous`. That variant cycles the same seven teleport commands without a debug client and reports actual Player/camera positions and scale on the next actor update. `tests/verify_teleport_device_evidence.py` validates the downloaded coordinator logs offline; it does not access devices. The command-driven fixture remains unchanged. [Android Release verification](diagnostics/t4-teleport-audit/android-review.md) passed on both 32-bit Chromecasts.
