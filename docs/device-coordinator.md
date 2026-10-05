# Shared Chromecast coordinator

The implementation uses a Python standard-library coordinator (Pillow for launcher artwork comparisons), an authenticated
JSON API over a Unix socket, Task commands and a read-only loopback
HTTP dashboard. **There is no MCP adapter.**

## Reserving a device for personal use

From your terminal:

```sh
task cast2:reserve REASON="Watching TV"
task cast2:release
```

Cast1 has matching `cast1:reserve` and `cast1:release` shortcuts. The general
commands work with any registered device:

```sh
task chromecast:reserve DEVICE=chromecast-test-02 REASON="Watching TV"
task chromecast:release DEVICE=chromecast-test-02
task chromecast:queue
```

Example output:

```text
chromecast-test-02: reserved; Watching TV; retained until you release it
chromecast-test-02: released; queued jobs may now start
```

A reservation immediately blocks all new grants on that device, including
captures and reconnect jobs. Pool jobs can use the other device. Existing work
finishes its normal cleanup; until then the reservation shows
`waiting-for-cleanup`. Check queue/status for `reserved` before taking over.
The command never interrupts a running app or changes the TV screen.

Exception authorized by Will on 2026-10-04: `WORKFLOW=install` performs only a
background APK install and checksum verification. It retains the reservation,
serializes against other owned sessions, rejects updating the foreground app,
and sends no launch, cleanup navigation or remote input. Use
`task chromecast:submit DEVICE=chromecast-test-02 WORKFLOW=install APP=bomberman APK=/absolute/path/frozen.apk`.
The adapter requires deployment before this workflow is available; an unknown
workflow response is not permission to use direct ADB.

The prepared service now exposes authenticated `capabilities` with supported
workflows and `maintenance_drain`. Install-only jobs can run on an idle reserved
device while another device is testing. They wait for any complete session on
their own device, including cleanup, to avoid contaminating measurements.

Reviewed adapter upgrades use `android/bomberman/deploy-coordinator.py` through
the app installer. The helper accepts `--review /absolute/path/deploy-review.json`
to select the app's reviewed adapter hashes; the default remains Bomberman's
review. The administrator helper persists a maintenance drain,
waits for running sessions, retains queued work, verifies the restarted service,
and resumes grants. Queue and dashboard display the maintenance reason. The
first upgrade of an older scheduler still uses a transactional idle check before
stopping it; only the updated scheduler honors the drain while it is running.
Deployment failure restores previous adapters and keeps the service stopped
with maintenance retained, since older adapters may ignore that state. Correct
the reported error and rerun the reviewed deployment to recover. Drain timeout
does not cancel jobs. Full provisioning with `task chromecast:install` retains
its existing active-session guard; it is separate from this adapter upgrade.

Run `python3 android/bomberman/install.py` from a terminal for the prepared
upgrade and installation. It authenticates sudo locally when needed, reports
service upgrade and APK submission separately, saves the installation log under
`docs/diagnostics/bomberman-chromecast/`, and persists per-device job IDs before
watching so an interrupted watcher can resume. See the
[background installation plan](plans/2026-10-04-chromecast-background-install.md).

Reservations live in the protected `coordinator.sqlite3` database, survive
service restarts, and have no expiry. Queue and dashboard show the reservation
owner, reason and state alongside any draining job. Only the authenticated
session that created a reservation can release or update it. Ordinary terminal
calls use the persistent `interactive` session, so you can release from another
terminal using the same account and client state. Calls made from a Codex
session use that session's identity; do not reserve on behalf of the user from
an agent session. Repeating your reserve command updates the reason; repeating
release is harmless. Do not delete the terminal's client credentials while it
owns a reservation.

Deploy new service features once with `task chromecast:install` (interactive
sudo; installation output is saved under `docs/diagnostics/`). It wraps the
installer with a 60-second reload limit. Reservations require this updated
protected service; subsequent reserve/release calls require no sudo or install.

Both dedicated test devices are registered by their verified hardware serial:

| Device | Hardware | Android | Connection |
|---|---|---|---|
| `chromecast-test-01` | Chromecast HD / `2628105GN0GT7C` | 14 | Discover current TLS endpoint by serial/mDNS |
| `chromecast-test-02` | Project Room, `sabrina` / `26031HFDD67QH7` | 12 | Verified legacy ADB at `192.168.4.49:5555` |

Device 02 exposes TCP/IP ADB when USB debugging is enabled; it does not have
Android 13+ TV native wireless pairing. Addresses are discovery hints. The
service checks the physical serial before device operations.

## Deployment and current status

The process tests and real-device checks passed in an explicitly labelled
development deployment. The protected system service is active and both devices are enrolled and ready.
An earlier service-manager timeout was repaired as described below. Runtime bypass
verification remains pending. The installer performs a bounded manager
preflight before writes and reports partial activation clearly. The host journal
records a prior reload taking 594585 ms (9 minutes 55 seconds); this abnormal
host-manager behavior was traced to retained failed crash handlers and repaired;
reload now takes 7.158 seconds, with BPF descriptors reduced to 22. A timeout of the client does not
cancel PID 1’s reload. Avoid repeated reloads. Once the current reload finishes,
`sudo python3 scripts/install-device-coordinator.py --resume-activation` verifies
that all installed units are loaded and current, then completes activation
without rewriting files or requesting another reload. Enabling units uses
`--no-reload` to avoid an implicit second reload. The longer bounded full-install
reload wait is a mitigation, not a diagnosis or root-cause fix.

`scripts/diagnose-systemd-reload.py` collects read-only root diagnostics:
descriptor categories (paths omitted), CPU/syscall/kernel-stack samples and the
reload journal. It sends no signals and changes no services. Root access is
needed for PID 1’s otherwise unreadable proc details. The development coordinator was stopped before
production provisioning, so there are not two active device authorities.

Review [the installer](../scripts/install-device-coordinator.py) and run once:

```sh
sudo python3 scripts/install-device-coordinator.py
```

This creates a separate system account, root-owned executable/adapters,
service-owned state and credentials, systemd units, registered-address nftables
rules and managed Codex hooks. It preserves unrelated nftables tables and
merges existing Codex requirement tables rather than overwriting them. Active
owned jobs prevent reinstalling protected code. A backup of the original
requirements is retained. `--check` is read-only; `--reuse-host-key` is an
explicit optional bootstrap using the currently authorized host identity.
The default establishes a fresh service identity: authorize it on each TV.

```sh
task chromecast:readd DEVICE=chromecast-test-01
task chromecast:readd DEVICE=chromecast-test-02
task chromecast:devices
task chromecast:queue
```

Restart participating local Codex sessions to load the managed hooks. The
current cloud-orchestrated runtime may need administrator-managed remote hooks;
installing a local hook file does not prove cloud enforcement. Official
[hook documentation](https://learn.chatgpt.com/docs/hooks) describes those
coverage limits. Hook failures are not a substitute for the OS boundary.

Do not certify enforcement until direct ADB, alternate clients, raw IPv4/IPv6,
existing ADB servers, interactive shells and escalated/container paths have
been tested. Current address rules cover recorded IPv4/IPv6 addresses. DHCP
and temporary IPv6 address changes introduce a discovery/refresh gap; a
stronger managed network/container boundary must close it. The five-second
registry refresh alone does not establish complete enforcement. Preserve
unrelated Android devices when tightening runtime permissions.

## Multiple-device commands and launcher verification

Implemented, deployed and verified on both Chromecasts on 2026-10-05, including a real stale-art trial and automatic launcher-data reset/recheck. Full process suite: 89 tests passed. Check authenticated `capabilities` for `device_batches` and `launcher_verification` before treating these features as active.

Use a comma-separated `DEVICE` list or `DEVICE=all` to target every registered device. `all` is frozen when accepted; `POOL` still selects one eligible device. Examples:

- `task chromecast:submit DEVICE=all WORKFLOW=install APP=bomberman`
- `task chromecast:capture DEVICE=chromecast-test-01,chromecast-test-02 OUT=/absolute/path/captures`
- `task chromecast:readd DEVICE=all`
- `task chromecast:queue DEVICE=chromecast-test-01,chromecast-test-02`

`APP=bomberman` and `APP=primes` without `APK` resolve the latest frozen APK from their respective build receipts and verify its hash. Primes uses `android/prime-numbers/build/build-receipt.json`. Other apps retain their release APK defaults. Specify `APK=/absolute/path/frozen.apk` to choose a particular build.

### Prime Numbers installation and checks

`APP=primes` is the offline Java/WebView study app, package
`org.worldfoundry.wf_game.primes`. Build and freeze it locally before submitting:

```sh
python3 android/prime-numbers/build.py
python3 android/prime-numbers/verify.py
python3 android/prime-numbers/install.py
```

The installer authenticates a reviewed adapter upgrade in the terminal only
when needed, submits installation and `VALIDATOR=prime-study` verification on
Chromecast 1, and saves output, durable job IDs, and downloaded evidence under
`docs/diagnostics/prime-numbers-chromecast/`. Connection jobs ending in
`needs-local-setup` trigger one bounded reconnect sequence with up to three
owned `readd` jobs, followed by a replacement install/check. It stops if recovery
is exhausted or connection fails again after successful recovery.

If background installation rejects updating the foreground Prime Numbers app,
the program installs through its separately owned interactive check session.
That check waits behind personal reservations. Failed runtime checks require
investigation; `python3 android/prime-numbers/install.py --retry-check` explicitly
replaces one failed check and retains its evidence.

For an individual check, use:

```sh
task chromecast:check DEVICE=chromecast-test-01 APP=primes VALIDATOR=prime-study
```

The validator is accepted only with `APP=primes` and `WORKFLOW=check`. It checks
reference-only Study, all four held/released directions, Recall marking and
results, Home/resume, and Back exit. Leave the physical remote untouched during
automated input checks; extra presses can invalidate navigation assertions.
Chromecast 1 verification passed in `J-9638f51a96ce` on 2026-10-06; Chromecast 2
and actual WebView 91 testing remain pending. See the
[app README](../android/prime-numbers/README.md) and
[delivery plan](plans/2026-10-06-prime-numbers-chromecast.md) for current evidence.

### Launcher verification and batch evidence

Multi-device submission returns a durable `BATCH=B-…` and one `JOB=J-…` per target. All targets are validated before admission. Jobs schedule independently; personal reservations remain effective. Watch with `task chromecast:watch BATCH=B-example`, inspect with `task chromecast:status BATCH=B-example`, download with `task chromecast:evidence BATCH=B-example OUT=/absolute/path/evidence`, or cancel unfinished children with `task chromecast:cancel BATCH=B-example`. Evidence is grouped as `OUT/<device>/<job>/`, with `batch.json` recording individual outcomes. Closing a watcher does not cancel the batch. A partial failure returns nonzero while retaining successful results.

Comma lists/all also work for device listing and reserve/release operations. Reservation changes validate all selected devices and owners before updating anything. Run personal reservations from your own terminal. Pairing codes and explicit reconnect addresses require one device at a time.

Installation now has two owned stages. First it installs in the background and verifies the installed APK checksum without changing the foreground. Then it obtains interactive access, opens the resolved HOME launcher and compares the identified app tile against artwork extracted from the frozen APK. The final result is successful only after visible artwork verification. Screenshots, hierarchy, reference resource hashes and comparison scores are saved under the job's `launcher/` evidence.

If the tile is stale, the service restarts the reviewed launcher and checks again. If it remains stale, it clears the launcher's data/cache, reopens it and rechecks. **Will authorized this on 2026-10-05; it resets the launcher home layout/app order, while preserving game data.** Resets are restricted to the reviewed Google TV launcher packages and an identified mismatching tile. Inconclusive or missing tiles produce an explicit verification failure instead of pretending the checksum proves the icon is fresh.

When a personal reservation blocks interactive access, the job reports `launcher-verification-pending`, releases the installation session and persists its continuation. It resumes automatically once eligible; no HOME/input/reset occurs during the reserved background installation. A newer installed APK supersedes an older pending check. Cancelling after APK installation leaves that APK installed and records its artwork as unverified.

The current implementation uses PNG/adaptive raster references and UI hierarchy identification. Unsupported artwork formats, ambiguous/missing tile geometry, or a black capture cannot pass verification. Verify the concrete launcher layout on each device during acceptance; process tests are not a substitute for that check.

See the [implementation and acceptance plan](plans/2026-10-05-chromecast-multiple-device-commands.md).

## Task interface

Build the APK locally before submission. `DEVICE` pins a physical device;
`POOL=chromecast-test` selects an eligible device. `REQUIRE_ABI` filters pools.

```sh
task chromecast:check DEVICE=chromecast-test-02 APP=aquarium \
  SCENE=jellyfish APK=/absolute/path/frozen.apk
task chromecast:profile POOL=chromecast-test APP=aquarium \
  SCENE=planted-tank APK=/absolute/path/frozen.apk WARMUP=15 RUNS=1 TRACE=plants
task chromecast:record DEVICE=chromecast-test-01 APP=aquarium \
  SCENE=jellyfish APK=/absolute/path/frozen.apk DURATION=10
task chromecast:submit DEVICE=chromecast-test-01 WORKFLOW=check \
  APP=condo APK=/absolute/path/frozen.apk
task chromecast:watch JOB=J-example
task chromecast:status JOB=J-example
task chromecast:evidence JOB=J-example OUT=/absolute/path/evidence
task chromecast:message JOB=J-example TEXT='My capture is queued behind yours.'
task chromecast:cancel JOB=J-example
```

`submit` is asynchronous. Convenience check/profile/record/readd submit and
follow by default; `ASYNC=true` detaches after acceptance. Closing `watch`
never cancels or releases the device. Cancellation belongs to the authenticated
job owner; active cancellation waits for cleanup. Queue/status may filter by
`DEVICE` or `POOL`; `WATCH=true` follows changes. Pool position is conditional.

Each profile segment uses `DURATION` seconds (default 12). `TRACE` is `idle`,
`swarm`, `all` or `plants`; record additionally supports the fixed `school`
input timeline. Named Aquarium scenes match the current eight-tank manifest.
`VALIDATOR=menu-back` checks manifest scene entry, Back, Home/resume and Betta
animation; `poke-resume` retains generic control/lifecycle checks. Unique
feeding/phone/settings validations remain separate migration work; a generic
capture does not replace their assertions.

A JSON `RECIPE=/absolute/path/recipe.json` on `submit` supports one owned
`variant-benchmark` request with `variants` and `restore_apk`. Variant data
contains only `label`, `apk` and optional `runs`/`warmup`; no caller scripts or
shell commands are executed. All APKs are frozen and hashed before queueing.
Input references in the service are hashes, never unrestricted worktree paths.
Restoration reinstalls and verifies the normal APK before ownership ends.

For lost native pairing, run interactively:

```sh
task chromecast:readd DEVICE=chromecast-test-01 \
  PAIRING_ENDPOINT=192.168.4.43:CURRENT_PAIRING_PORT
```

Enter the fresh code at the hidden prompt. It travels through authenticated
local IPC and worker stdin; it is not stored in SQLite, receipts, arguments,
history or events. If debugging is disabled, enable it on the TV first.
An uncertain interrupted install requires a device restart; the service checks
the boot identity before clearing that recovery gate.

## API, persistence and visibility

Production paths:

| Purpose | Path |
|---|---|
| Public authenticated JSON socket | `/run/wf-device-coordinator/coordinator.sock` |
| Durable queue/events/messages/registry | `/var/lib/wf-device-coordinator/coordinator.sqlite3` |
| Immutable APK inputs | `/var/lib/wf-device-coordinator/inputs/` |
| Evidence and receipts | `/var/lib/wf-device-coordinator/evidence/J-…/` |
| Service/device kernel locks | `/var/lib/wf-device-coordinator/locks/` |
| Private ADB socket and credentials | `/var/lib/wf-device-coordinator/adb.sock`, `adb-home/` |
| Root-owned service configuration | `/etc/wf-device-coordinator/devices.json` |
| Dashboard | `http://127.0.0.1:8767/` |

The API uses one newline-delimited JSON request and response per Unix socket
connection. Linux `SO_PEERCRED` checks an allowed UID. `register` issues an
opaque session ID/token; subsequent requests supply both. Owner checks use
session credentials, not editable display labels. Sessions still share a
host UID, so these tokens are cooperative session attribution, not isolation
between adversarial agents that can read each other's user-owned files.

```json
{"method":"queue","credentials":{"session":"…","token":"…"},"args":{"device":"chromecast-test-02"}}
```

Response envelope is `{"ok":true,"result":...}` or
`{"ok":false,"error":"...","type":"..."}`. Supported methods:
`register`, `upload`, `submit`, `devices`, `queue`, `status`, `events`,
`cancel`, `message`, `inbox`, `acknowledge`, `evidence`, `artifact`.
`upload` accepts at most 32 MiB of APK bytes encoded as base64 and returns its
SHA-256 reference. `submit` accepts a validated typed workflow and references.
`evidence` returns a checksum/size manifest; `artifact` streams at most 1 MiB
per request. The client writes output paths under its own permissions and
refuses conflicting files or path escapes. Codes/session tokens are not
included in job receipts.

`events` uses durable sequence cursors. `message` routes to a job owner;
`inbox` repeats unread messages until acknowledged, and duplicate
acknowledgements create only one logical delivery event. Task watchers and
hooks poll bounded inboxes. No assumption is made that a paused model can
receive an unsolicited wakeup. The dashboard is read-only; it cannot grant,
cancel or touch a device. `/snapshot` exposes the same queue plus enforcement
status, and its UI labels disconnected views stale.

The scheduler selects the oldest eligible accepted request per free device,
using durable insertion order rather than wall-clock sorting. Devices have
separate generations, kernel locks and worker groups. Busy device 01 does not
block a compatible job on 02. Every command checks its job/device/generation.
Worker crashes leave a recovery gate; inherited locks protect live descendants.
Recordings are tracked by PID and job-specific paths. Uncertain interrupted
installs are never treated as a time-expired lease that can simply be stolen.

## Validation and migration

Run process tests without using the TV:

```sh
pytest -q tests/device_coordinator
```

Tests cover per-device FIFO/parallelism, capability pools, fixed/pool arbitration,
owner and waiter cancellation, messages/acknowledgements, invalid credentials,
stale/cross-device leases, immutable input, streamed evidence, worker crashes,
literal Task text, non-persisted pairing codes, clock changes, policy merging,
PNG filters, private-activity restoration and registered-UDN rediscovery.

Real-device receipts verify parallel Aquarium checks on both devices, a short
presented-frame profile on device 02 and screen recording/cleanup on device 01.
They establish workflow behavior, not protected host enforcement. Source and
validation status are recorded in the
[implementation plan](plans/2026-10-03-chromecast-shared-device-coordination.md).

Common profiler, planted variants, Betta/Lionfish APK preparation, school
recording and jellyfish capture now route through shared workflows. Old
procedure text is frozen under `docs/reference/device-harnesses/*.txt`.
Retained generic Android runner routes known Chromecast selectors through the
service while preserving explicitly targeted unrelated Android hardware.
Compatibility Task aliases use the same coordinator. Specialized raw phone/
feeding/growth validators are not yet safe active Chromecast entry points;
retain their assertions and migrate them into reviewed modules before
retirement. Historical receipts remain unchanged.

Host slowdown investigation: [retained crash-handler units and targeted repair](diagnostics/systemd-reload-investigation.md). Repair is verified: BPF descriptors fell from 97,748 to 22 and reload took 7.158 seconds. Protected coordinator activation subsequently completed on 2026-10-04.


## Protected activation: 2026-10-04

The protected system service and API socket started successfully. First reconnect
attempts exposed a persistent-ADB-server lock inheritance problem and a Cast
discovery error that cleanup replaced with a generic recovery error. Source now
starts the shared ADB server without inherited descriptors before opening the
per-device lock, waits briefly for cold mDNS discovery, and reports missing Cast
identity as local setup. A full protected update stops an idle old service before
copying adapters, so the running process and ADB children cannot retain old code.
The full protected update completed 2026-10-04 05:40. Both reconnects now
complete without inherited-lock failures. Device 01 is advertised but needs
authorization/pairing of the new service identity. Device 02 was not found near
its last recorded Cast address; power, Wi-Fi and current IP need checking.
Protected-device enrollment remains pending. The queue is empty and the
read-only dashboard snapshot responds.

Real process regression tests verify that a forked persistent ADB daemon does
not retain a device lock and that the next owner can acquire it. Additional tests
verify original Cast setup errors. The protected API itself is reachable outside
the tool sandbox; restricted socket access requires a tool escalation rather
than a raw-device fallback. Activation attempts save their own transcripts in
`docs/diagnostics/`.


For Chromecast 02 after an address change, use the LAN-scoped maintenance hint:

```sh
task chromecast:readd DEVICE=chromecast-test-02 ADDRESS=192.168.4.49
```

Will reported this address on 2026-10-04. The hint is permitted only for an
explicit registered legacy-TCP device in its discovery network. It connects
using that device's configured ADB port, then checks `ro.serialno` before
updating the registry or performing device mutations. Cast advertisement
availability is not required for this explicit address hint. Addresses outside
the allowed LAN, public addresses, loopback addresses and non-readd uses are
rejected. The address-hint addition is deployed and verified on device 02.


## Protected verification — 2026-10-04

Both registered Chromecasts now report ready. Device 02 was authorized on the TV,
reconnected at `192.168.4.49:5555`, and verified as serial `26031HFDD67QH7`.
Protected Aquarium check `J-a6cb710bb33c` completed installation, jellyfish scene
launch, evidence capture and verified restoration. Its frozen APK SHA-256 is
`eabc18940d8ab8ba7d62b71a05ab9607d8533d599d1153b4e64d291d5c751e2c`.
Evidence is saved in `docs/diagnostics/protected-aquarium-02-check/`; the final
queue is empty. Device 01 reports verified ready at `192.168.4.43:41277`.
Protected address-hint deployment is complete. Full runtime/container/network
bypass verification and remaining specialized harness migrations are still open;
this successful smoke test does not certify complete enforcement.

Current Aquarium on device 02 was rebuilt and installed through job `J-d6b701aa4f34`; generative plants and the FPS overlay were verified. [Deployment evidence](diagnostics/aquarium-cast2-deployment.md) records the frozen input checksum and on-device result.

## Capture the current display

```sh
task chromecast:capture DEVICE=chromecast-test-02
# Optional destination:
task chromecast:capture DEVICE=chromecast-test-02 OUT=docs/diagnostics/cast2-screen
```

This queued workflow captures the screen as displayed when its device lease is granted. It installs no APK, sends no keys, and neither launches nor stops an app. It downloads the PNG and receipt after completion and prints the screenshot path. If another job owns the device, capture waits for that job; it cannot promise the earlier screen is still present. `ASYNC=true` submits only; use `watch` and `evidence` separately. Updating an existing protected installation requires rerunning the installer before the service accepts this new workflow.

Capture evidence also includes bounded, read-only power, display, window, foreground-activity, dream and SurfaceFlinger dumps. These identify sleep/off state, the visible app and protected layers when a PNG is blank. Dumps are collected immediately after the screenshot; timestamps identify later observations rather than claiming atomic state. No wake key is sent.

## Alternative capture tests

```sh
task chromecast:capture DEVICE=chromecast-test-01 METHOD=compare
task chromecast:capture DEVICE=chromecast-test-02 METHOD=compare
python3 scripts/analyse-chromecast-capture.py docs/diagnostics/chromecast-capture-J-example
```

`METHOD` accepts `png` (default), `raw`, `uiautomation`, `record` or `compare`. Compare captures each backend sequentially inside one device lease and records per-method success/errors; “captured” means an artifact was obtained, not that it visually matches the TV. The record backend creates a 3-second 1280×720 recording of the current display, with no app launch, keys or APK installation. Raw capture saves original bytes, a preserved RGBA PNG and a separately labelled opaque preview. The automation helper preserves existing accessibility services and disables its own accessibility use; device-side timeout bounds its lifetime. Coordinator-owned temporary files and recording processes are cleaned before release.

The fixed helper is packaged at `config/device-coordinator/capture-helper.jar` and frozen by the installer. Rebuild with `python3 scripts/device-capture/build.py --ecj /path/to/ecj-3.38.0.jar`; it uses Android SDK 34 and min API 26. The Eclipse compiler is a local build dependency, not installed on the Chromecast. Both production devices meet the minimum API.
