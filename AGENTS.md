# Shared Chromecast testing

## Engine changes require explicit permission

Will requires discussion and explicit permission before modifying any World
Foundry engine code. Authorization to implement a level, asset, animation or
plan does not authorize engine changes. Read-only engine investigation is fine;
prepare a concrete proposal describing the required engine changes and obtain
permission before editing engine code. Continue authorized asset/script/tooling
work independently when possible. This applies to every platform/backend.

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
