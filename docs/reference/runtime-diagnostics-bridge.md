# Android runtime diagnostics protocol v1

The opt-in `AquariumDiagnostic` APK supplies coherent, read-only game snapshots.
Ordinary Android Debug and Release APKs compile the diagnostics out. The existing
desktop editor bridge keeps its mutation protocol. The diagnostic adapter uses
the existing `DebugServer_*` interface and port, with bounded socket ownership;
it does not link the desktop mutation implementation or editor.

Build with `task build-apk-diagnostic`. Run the fixed acceptance validator:

```sh
task chromecast:check DEVICE=chromecast-test-01 APP=aquarium VALIDATOR=runtime-diagnostics APK=/absolute/path/frozen-diagnostic.apk
```

The protected coordinator must have the reviewed `diagnostics.py`, `service.py`
and `workflows.py` upgrade installed first. Forwarding, connection, input,
assertions and cleanup stay inside that job. There is no caller-selected bridge
endpoint or command-script entry point. The endpoint binds only to device
loopback, regardless of desktop bind flags.

## Request and reply

Transport is newline-delimited UTF-8 JSON. A request is one flat object:

```json
{"v":1,"request":42,"op":"snapshot","run":"process-id","level_generation":2,"after_simulation_step":802,"since_input":54,"draft":true,"timeout_ms":2000}
```

Every reply includes `v`, `request`, `run`, `level_generation`, `monotonic_us`,
`frame` and `simulation_step`. `monotonic_us` timestamps the copied game-thread
boundary using the engine's monotonic clock; it is not the coordinator clock.
Frame and simulation sequences persist across level transitions. The run ID
changes on process restart. The diagnostic listener persists through selectors
and level unload/load and stops when the game exits.

| Request field | Meaning |
|---|---|
| `v`, `request`, `op` | Required: version 1, positive exact JSON integer request ID, `snapshot` |
| `run` | Optional process fence; the coordinator client sends it after its first snapshot |
| `level_generation` | Optional level/selector fence; required for actor or frame/simulation waits |
| `after_frame`, `after_simulation_step` | Wait for a strictly greater sequence in the specified generation |
| `min_input` | Wait for this exact receipt's consumption; a later receipt cannot substitute for it |
| `since_input` | Return only input-history entries greater than this sequence; default 0 |
| `actor`, `actor_generation` | Select a live actor by slot and lifetime generation; both required together |
| `draft` | Include the existing edit session's drafts and error separately; default false |
| `timeout_ms` | 1..5000, default 1000; expiration produces an explicit error |

Replies use `op: snapshot` or `op: error`. Error codes include `stale-run`,
`stale-level`, `stale-actor`, `actor-unavailable`, `simulation-paused`, `suspended`,
`input-gap`, `timeout`, `queue-full` and parser/capability errors. A paused
simulation wait fails immediately; a snapshot of the paused state still works.
Process exit disconnects the socket. Reconnect obtains a new snapshot, with no
command replay. Duplicate in-flight request IDs terminate the ambiguous connection.

## Snapshot groups

`game` reports level index (selector: -1), mode, focus, paused/suspended status,
modal kind (`none`, `form`, `keypad`, `phone-form`), edit session and selector
cursor. Selector frames advance without simulation updates. During suspension,
the event-pumping path still services diagnostic snapshots.

`player` and `selected` report actor slot, unique lifetime generation, world
position, velocity, active update-list membership and the actor's visibility
mailbox result. Visibility here means enabled by that mailbox, not proof that
the actor was drawn or visible to the camera. Unavailable actors are null.
Without an explicit actor, selected defaults to the player.

`properties` reads committed values from the generic runtime registry. It
reports registry object generation, revision, schema and qualified field IDs
(`schema:field-number`). Registry generation and actor lifetime generation are
distinct. An explicit actor chooses its registry entry; otherwise the open edit
object, player properties or current planted-tank settings are selected.
Optional drafts include only the matching live edit session. Diagnostics never
call a property setter. An absent registry entry is null. Field lists are capped
at 128 with an explicit truncation flag; oversized values fail explicitly.

`input` reports received/routed/consumed sequences, receipt-derived held masks
per source, last press/release sequence and a bounded history. Each history
entry includes source, held/pressed/released bits, Android key code when present,
receipt time, route, reason, consumption boundary and actor/mailbox consumers.
Hardware, touch, phone masks, phone property commands and lifecycle observations
remain distinguishable. Android auto-repeats are receipts; mask samplers record
transitions only. Focus loss is recorded without inventing a hardware release.

Receipt precedes routing. Game routing and hardware sampling do not assert
consumption: an actor's actual input-mailbox read supplies the consumer actor,
lifetime generation and mailbox. Form, keypad, selector and Android interception
acknowledge at their actual handling paths, including selector release gates.
Consumption means a handler read/handled the input, not proof of movement.
Tests compare subsequent player positions in the same actor and level generation.

History retains 128 receipts and up to eight actor/mailbox consumers per receipt.
`oldest_receipt` and `gap` identify missing history. An acknowledgement wait for
an evicted receipt returns `input-gap` rather than accepting a later sequence.

## Bounds and threading

Limits: eight clients, 64 total in-flight requests, 16 per client, 4096 request
bytes, 65536 reply bytes and 256 KiB pending output per client. Overlong lines
disconnect. Strict JSON validation rejects duplicate/unknown fields, nesting,
wrong types and unsupported operations, including pause, input injection,
mutation, script/shader reload and file-writing screenshot requests.

At most four requests copy actor/property state per game-thread boundary.
The socket worker exclusively accepts, reads, serializes copied replies and
writes, including partial writes. Full output queues or a two-second write
deadline disconnect a slow reader. Stop joins the worker before closing the
listener. Request expiration remains bounded even if no game boundary occurs.
Actor pointers are used only by the game-thread lifetime registry and adapter.

## Verification and overhead

`tests/test_runtime_diagnostics.py` runs the real socket implementation against
a small C++ state fixture. Coordinator tests cover lease guards, fixed-validator
admission, immediate reply correlation, failure/cancellation cleanup and recovery
of only an ended job's recorded forwarding. Device acceptance additionally
covers all four held/released directions, actual actor consumers, selector and
keypad routing, committed/draft separation, invalid edits, phone input, Home/resume,
level transitions and socket reconnect.

The fixed `runtime-diagnostics-overhead` validator runs through the existing
`variant-benchmark` workflow. Its recipe must select Aquarium's `planted-tank`,
idle trace, one run per variant and these ordered labels: `disabled`,
`enabled-no-client`, `subscribed`. Supply the ordinary APK for the disabled
variant and restore input; supply the diagnostic APK for the other two. It
sets seed 713, freshwater, growth speed 0 and the initial wide camera before
each measurement. The subscribed variant samples at at most 5 Hz.

Evidence includes SurfaceFlinger presentation intervals, PSS/meminfo, thermal
state, fixture/property state, subscription samples, screenshots, protocol JSONL,
assertions and an owned-forwarding cleanup receipt. APK receipts must show the
same game assets and different diagnostic capabilities. Device measurements, not desktop load or the game-loop delta, establish overhead.

Completion-event streams, mesh/material/texture inspection, actor pagination
and measured subsystem profiling remain phases 2 and 3 of the implementation
plan. They are not represented as completed by phase-one snapshots.
