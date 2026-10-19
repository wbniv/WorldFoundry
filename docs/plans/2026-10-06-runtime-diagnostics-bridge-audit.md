# Android runtime diagnostics bridge: implementation audit

Date: 2026-10-06. Step 0 of [the diagnostics plan](2026-10-06-runtime-diagnostics-bridge.md).
Read-only source audit completed. Engine implementation awaits explicit approval
of the changes below under the repository's AGENTS.md rule. The plan records
approval of the direction; it does not record approval of this concrete file scope.

## Build and transport findings

`android/app/build.gradle.kts` builds the repository root CMake project.
`CMakeLists.txt` forces `WF_DEBUG_BRIDGE=OFF` for Android and iOS, including
Android Debug builds. Passing `-DWF_DEBUG_BRIDGE=ON` alone cannot enable it.
The desktop Debug override explicitly excludes mobile. Enabling the existing
bridge also adds the mutation implementation and generated OAS map dependencies.
Those dependencies must be checked in the Android link build, even when the
diagnostic protocol denies all mutation operations.

`wfsource/source/game/main.cc` defines port 7777 and loopback binding.
`WFGame::LoadLevel` starts the server; `UnloadLevel` stops it before destroying
the level. Thus a connection currently ends at every level transition. A
process-wide run ID and increasing level generation must outlive the listener;
reconnection must obtain a fresh snapshot. Selector diagnostics require a
snapshot boundary outside the active-level update as well.

The coordinator's `Adapter.adb` in `scripts/wf_device/workflows.py` guards
operations with the owned lease and uses the protected ADB server. There is no
existing bridge forwarding lifecycle in this adapter. Add forwarding there,
using an allocated local port and a fixed remote endpoint; close the socket
and remove only that forwarding during cleanup. Keep this out of install and
capture workflows and expose only fixed validators through request validation.
Do not add caller-supplied commands, ports, scripts or bridge operations.

## Threading and protocol findings

`engine/stubs/debug_server.cc` has unbounded pending commands, input accumulation,
and accepted clients. The parser searches strings rather than validating JSON.
Unknown operations are silently ignored. Replies generally broadcast to every
client and have no request correlation.

`send_all_locked` writes synchronously to sockets under the queue mutex from
game-thread broadcast and command paths. A slow client can stall rendering.
The single write also fails to account for partial writes; ping responses write
from the reader thread, so output has multiple writers. Move transmission to
bounded per-client output queues with one socket writer, partial-write handling,
timeouts and explicit overflow/disconnect behavior. The game thread copies
state and queues a reply without doing socket I/O. Preserve the existing Stop
worker-drain guarantee while changing worker ownership.

The Android diagnostic capability needs an allowlist before any legacy command
dispatch, including listener-thread pause/resume/step paths. Reject mutation,
script/shader reload, input injection and file-writing screenshot operations.
Keep the desktop editor capability separate. Force loopback for diagnostic
builds, regardless of desktop bind configuration.

## State and input findings

`WFGame::StepFrame` drains requests before updating and broadcasts after render.
Increment frame and simulation sequences separately: a property modal skips
`Level::update`, and a suspended frame returns before draining the bridge queue.
Define explicit suspended/unavailable responses and bounded waits rather than
allowing queued requests to appear successful after resume or level replacement.

`engine/runtime_properties.hpp` already provides committed object values,
generation, revision, schema and field IDs through the registry. `wfprops::Edit`
provides session, draft and error state. `wfprops::snapshot(Edit, ...)` serializes
draft UI values and is not a committed-state snapshot. Read committed state from
the registry and expose drafts separately; reuse validation and transaction APIs.
Property generations identify registry objects: verify actor lifetimes independently
for actors without property entries. Do not use an actor slot as an instance ID.

Android receipt hooks belong before the early returns in
`native_app_entry.cc::HandleInputEvent`, including Back interception. Observe
hardware key/analog transitions, phone transitions and lifecycle clears separately
before `Emit` combines their masks. `_HALSetJoystickButtons` in Android `input.cc`
only sees the combined mask and cannot identify its source. Observe routing and
consumption where selector, phone keypad, property form and simulation actually
handle input, including release gates. A successful ADB key command or a changed
hardware mailbox is insufficient to claim gameplay consumption.

## Concrete engine/build proposal for approval

Implement phase 1 first, with the following engine/build scope:

| Files | Proposed change |
|---|---|
| `CMakeLists.txt`, `android/app/build.gradle.kts` | Explicit opt-in Android diagnostic variant; ordinary builds retain bridge disabled; link existing bridge dependencies without editor components |
| `engine/stubs/debug_server.cc`, `.hp` | Versioned, correlated read requests; strict parsing and bounded queues/clients/messages; nonblocking game-thread handoff; diagnostic allowlist; loopback endpoint |
| `engine/runtime_diagnostics.hpp`, `.cpp` (new) | Shared bounded observation state and copied read-only snapshots with run, frame, simulation and generation identity; compile-out hooks when disabled |
| `wfsource/source/game/game.cc`, `.hp` | Frame/simulation boundaries, level identity and snapshot lifecycle, paused/suspended handling |
| `wfsource/source/game/level.cc`, `actor.cc` and corresponding headers if needed | Actor lifetime generations, selected/player state and actual input consumption observations |
| `wfsource/source/hal/android/native_app_entry.cc`, `input.cc` | Hardware/phone receipt and release observations, source attribution, focus/lifecycle clears |
| `wfsource/source/game/level_menu.cc`, `level_menu_host.cc` | Selector routing and snapshots while no level simulation runs |
| `wfsource/source/game/runtime_property_ui.cc`, `plant_ui.cc`, `engine/runtime_property_form.cpp` and corresponding headers if needed | Form/keypad routing, capture/release reasons and read-only modal/edit state access |

Use the existing property registry without adding a second property writer.
No physics, animation, asset-format or gameplay-policy changes are proposed.
Phase 2 completion events and phase 3 inspection/profiling require a subsequent
concrete scope review before engine edits beyond this phase 1 proposal.

Coordinator client, fixed validators, Task wiring, evidence files and tests are
authorized tooling work. Integrate them against the implemented protocol rather
than registering a validator that the current APK cannot satisfy. Existing local
changes in coordinator workflows/service and other tasks must be preserved.

## Required verification after implementation

Build ordinary and diagnostic Android APKs and verify their bridge capability
distinction. Exercise malformed/oversized requests, queue saturation, slow readers,
partial writes, disconnect/Stop, actor reuse, stale generations and modal pauses
with host tests. Check request correlation against immediate replies.

Freeze the diagnostic APK and submit fixed checks through `task chromecast:*`:
held/released input in gameplay, keypad, form and selector; fresh positions tied
to simulation steps; process/level changes; Home/resume; forwarding cleanup on
failure and cancellation. Use cast1 and cast2 when available, respecting personal
reservations. Save acknowledgements, snapshots and assertions as evidence.
Measure disabled/no-client/bounded-subscription pacing, PSS and APK size on the
same device and scene. Host results do not establish Android overhead.
