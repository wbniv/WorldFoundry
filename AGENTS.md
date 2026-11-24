# Shared Chromecast testing

In human-readable prose, tables and rendered job labels, write coordinator
job IDs with a nonbreaking hyphen (U+2011), for example `J‑0692359b671d`,
so the ID cannot split across lines. Preserve ASCII `J-` in commands,
machine-readable data, filenames, paths and URLs because those bytes are part
of the executable identifier or reference.

## Engine changes require explicit permission

Will's standing authorization (2026-11-24): new level settings objects and
their settings fields, registration and generated schema/header files are
pre-approved. This authorization covers the established level-settings
mechanism; unrelated engine changes still require explicit permission.

Will requires discussion and explicit permission before modifying any World
Foundry engine code. Authorization to implement a level, asset, animation or
plan does not authorize engine changes. Read-only engine investigation is fine;
prepare a concrete proposal describing the required engine changes and obtain
permission before editing engine code. Continue authorized asset/script/tooling
work independently when possible. This applies to every platform/backend.
Prior authorization for engine changes already made on a branch carries through
when merging those same changes; do not request it again merely for the merge.
New engine changes beyond the authorized branch work still require permission.

## Worktree lifecycle

Work in the main checkout and on the mainline development branch by default.
Create a separate branch or worktree only when needed to avoid conflicting
parallel feature work in the same project. When creating one, record its purpose
and intended integration branch.

A request to merge signals that development should return to the integration
branch, even if further testing or refinements remain. After merging, preserve
unique changes and useful evidence, check ignored files and active use, and
remove the temporary worktree and merged local branch once accounted for.
Continue subsequent testing and refinements on the integration branch. Report
anything that prevents cleanup, with a reason and next step.

A topic change alone is not a signal that work is complete, paused permanently,
or ready to merge or delete; Will may switch between topics and return later.
Preserve unfinished work and avoid disruptive cleanup when its status is unclear.

For JavaScript/CSS shipped in TV WebViews, support Chromium/WebView 91 as the
current minimum: cast2 was measured at 91.0.4472.114 on 2026-10-05. Do not infer
browser API support from Android version, target SDK or desktop browser tests.
Avoid unguarded post-91 APIs (including Array/String/TypedArray `.at()`); use
compatible operations or tested feature-detected fallbacks. Consult
[the WebView compatibility reference](docs/reference/chromecast-webview-compatibility.md)
and test actual gameplay on cast2, including held/released directional input.

When asking Will to run a diagnostic command, save its output to a file (prefer
`docs/diagnostics/`), print the destination, and read it directly afterward.
Do not require Will to copy large terminal output into the conversation.

Will permanently authorizes ordinary app installation, launch, input, capture,
profiling and lifecycle tests on these dedicated devices. Do not ask Will for
recurring permission to use them. Coordinate complete sessions through the
shared service, using `task chromecast:*`.

Will can reserve devices for personal use with `task cast1:reserve` or
`task cast2:reserve` and release them with the corresponding `:release` command.
Respect reservations shown in queue/status. Do not release or create personal
reservations on Will's behalf from an agent session; his terminal owns them.
Will authorizes background installation during video playback (2026-10-04).
Use only `WORKFLOW=install`: it preserves the reservation, rejects updates to
the foreground app, and never launches an app or sends input. All interactive
test workflows remain blocked by a personal reservation.

- `chromecast-test-01`: Chromecast HD, Android 14, serial `2628105GN0GT7C`.
- `chromecast-test-02`: Project Room, Chromecast (`sabrina`), Android 12,
  serial `26031HFDD67QH7`.

Build/freeze the APK locally before submission. Select `DEVICE=...` or
`POOL=chromecast-test`; submit/check/profile/record uses a single owned session,
including cleanup. Check `task chromecast:queue`, follow `task chromecast:watch
JOB=...`, and download with `task chromecast:evidence JOB=... OUT=...`.
Communicate with the owner using `task chromecast:message JOB=... TEXT='...'`.
Closing a watcher does not cancel a job. Cancel only your own submitted job.
Do not use raw Chromecast ADB, parallel worktree locks, copied device harnesses,
or direct phone-controller commands outside coordinator ownership. An
unavailable coordinator does not authorize a direct-control fallback.

For reconnect use `task chromecast:readd DEVICE=...`. Device 01 uses native
wireless debugging; device 02 uses USB debugging and verified TCP/IP ADB.
Pairing codes must be entered at a secure interactive prompt, never committed,
logged or placed in Task arguments. Factory reset, account changes, unrelated
data deletion and security disabling are outside ordinary test authorization.

Deployment/verification status and temporary development instructions:
[coordinator documentation](docs/device-coordinator.md). The instructions here
are guidance; protected service access and runtime policies enforce ownership.
Do not call the deployment enforced until its bypass checks pass.
