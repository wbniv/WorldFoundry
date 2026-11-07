# Reef gameplay verification

The new feather-duster, flowerpot and leather-coral meshes have deformation
curves. The feather-duster proximity and recovery timing and the changing
flowerpot current are exercised by `tests/test_species_movement.py`; the
exported deformation data and posed vertices are checked by
`tests/test_aquarium_thai_reef.py`.

The Pixel's installed Aquarium APK is SHA-256
`91fd64499085fffc86161f8547c0d3216f6b544c15f145fb71326517bf01b8f5`.
The installation was verified, but launcher verification reported the device
locked. The following coordinator jobs were submitted and had not completed
when this note was written:

- J‑66b8b79a4891 compares diagnostic feather-duster views with the fish near
  and far.
- J‑9709aeb79835 runs both ordinary reef styles.
- J‑c325dfbe7700 compares diagnostic clam, guard-crab and cleaner-shrimp views
  with the fish near and far.

Each diagnostic level uses the current reef assets and reaction scripts, starts
the fish at a chosen position, and frames the corresponding animal. These are
controlled observations, not evidence of manually steering the fish through
the tank. The two build scripts record how the comparison packages were
assembled; their `/tmp` inputs are temporary. Each job restores the installed
APK above. Download each completed job with `task chromecast:evidence` and
inspect the images before declaring a visual reaction verified.

## Pixel follow-up, 2026-11-06

J‑9709aeb79835 completed short idle runs in the ordinary realistic and anime
levels. J‑66b8b79a4891 completed the near/far diagnostic feather-duster
comparison: crowns are retracted near the fish and visible when it is away,
although coral obscures part of both views. J‑c325dfbe7700 stopped early with
`target-left-foreground`; it did not complete the clam, crab and shrimp
comparisons.

The clam's
[near](clam-near-pixel-2026-11-06.png) and
[far](clam-far-pixel-2026-11-06.png) views, from J‑025815136940 and
J‑6e6064b8914b respectively, show it closed with the fish nearby and open
with the fish away. These are separate starting positions, not a continuous
recording of reopening. The closed shell still looks unnaturally sharp and
needs visual refinement and an updated catalogue comparison.
The [near-crab view](crab-near-pixel-2026-11-06.png) is blocked by its host
coral, so J‑8efeb8b2f769 does not verify the claw reaction. The
[shrimp view](shrimp-near-pixel-2026-11-06.png), from J‑c3d35188fe32, shows
shrimp below the fish, but this still image does not establish that they
climbed on it and cleaned it. Both reactions need a clearer timed observation.
The ordinary APK was restored and the coordinator reported the Pixel ready
after the checks.

The coordinator agent reports the touch-helper fix deployed as 0.1.69 and
pushed as `0ec8c6d`, with six JVM tests and 3,459 container tests passed
(59 skipped). Live touch acceptance remains open: obtain a coordinator-owned
recording of a continuous joystick hold, direction change, release and
visible reaction. A diagnostic starting position and an idle still do not
replace steering in gameplay. The Lenovo was unavailable at the last check;
the Chromecasts remain out of scope under Will's current instruction.

## Pixel current-build follow-up, 2026‑11‑07

Two 120-second idle profiles used the current polished level assets. Realistic J‑5bf08c0ff7ce measured 59.84 FPS, p95 16.94 ms, and 0.069% missed refreshes; it has a 250 ms sampling hole, making the worst-frame value unreliable. Anime J‑a5fcf83072da measured 59.94 FPS, p95 16.91 ms, and 0.083% missed refreshes, with no reported sampling holes. Each is one idle run on the Pixel and does not establish the separate Chromecast or active-play performance gates.

The diagnostic packages used current mesh assets but an older saved level script; they cannot establish current-controller behavior. The realistic crab recording J‑a1b236a78e25 used an adjusted camera, but the nearby fish clips across the view and the small crab is mostly hidden. It does not verify the claws or climbing. Shrimp recording J‑dcf8b8637fc8 shows the fish stationary near the cleaner station and the shrimp moving underneath it; sampled frames at 5, 15 and 25 seconds do not establish that either shrimp climbed onto or cleaned the fish. These are authored starting positions, not a continuous steering test. Further investigation and clearer, timed verification remain necessary. Full Aquarium was restored by J‑403a12d4ba8b. Lenovo reconnect J‑94fb7d1d2f59 failed because the coordinator did not find the device on the network.

## Current-controller follow-up

Fresh realistic diagnostic J‑2c1f2a82bf1c used a level generated from the current controller, unlike the earlier comparison packages. Sampled frames at 5, 15 and 25 seconds show the stationary fish above the shrimp, but do not show the shrimp climbing onto or cleaning it. This remains a behavioral investigation, not a proven cause. Fresh crab job J‑40ad86d65957 failed during the coordinator installer helper; automatic readd J‑3e893eb7f88b reported ready. Restoration attempts J‑ab03f68082d5 and J‑1451f6af6a2d also failed with installer-related recovery; their automatic readd jobs reported ready. The last known pre-install package hash was `4ade3367edf457acb851148f6fe55ae5efd1f192a497216d34ea45b634b4b888`, the temporary shrimp review APK. The full menu APK restoration has not been verified. Do not treat coordinator ready alone as proof of the installed package.

Timing investigation: in J‑2c1f2a82bf1c the app launch began at 1794054743.062 and screen recording began at 1794054764.800, approximately 21.7 seconds later. The current controller triggers its one-shot cleaning event after two seconds of a stationary visitor and holds it for five seconds, so the event could have occurred before the recording began. The host stationary-visitor test passes (`pytest -q tests/test_species_movement.py -k reef_cleaning`). The observed absence in the recording does not establish a controller defect; the next test must trigger arrival after recording starts and show the event continuously. The full APK restoration retry J‑9e91fc3feb71 again returned an installer `plugin-error` and `cleanup-installer-worker-active`; automatic readd J‑9a51ff94c815 reported ready. The installer probe returned 137, with no diagnostic stderr. The installed package remains unverified; do not infer successful installation from readd.

A controlled delayed-arrival diagnostic has been prepared at `/tmp/reef-current-reaction-fresh/realistic-shrimp-delayed/candidate.apk` (SHA-256 `c4dae81d69c3d92ad751c014515fc51c8b20bbfd7cfbd003d95efb18495fd802`). It uses the current level and assets, starts the fish away from the station, and moves the fish to the station after 35 seconds; a recording longer than that can capture the one-shot reaction after recording begins. This is a diagnostic teleport, not evidence of user steering. It has not been run because the coordinator's installer has repeatedly reported an active worker and uncertain cleanup. The production source was not changed. The host cleaning-controller test passed again (1 passed, 25 deselected).

On the deployed coordinator 0.1.79, full-app restoration J‑9ae87cc027fa passed the previously failing capability probe and recorded session creation, write and the durable commit marker, but returned `plugin-error` during commit. Automatic readd J‑7586f56fdc37 ended `cleanup-installer-commit-unresolved`; the original install journal is not marked restored. The package outcome and full-app restoration therefore remain unverified. Preserve the coordinator's recovery fence and do not submit another install until it reconciles the transaction. The separate coordinator plan records an Android 17 `Active Session` parsing correction awaiting deployment; whether it resolves this particular transaction must be established from its recovery evidence.

Coordinator 0.1.80 includes the Android 17 session parsing correction. After
readd J‑53842b1457c3, full-app installation J‑753b06777f6b timed out during
commit; automatic recovery J‑e826c12152b9 verified the session terminal,
removed its temporary installer files, and observed the installed APK SHA-256
`eaa3059af3144216f42f4eb10cd679566b5699a568e5ddd2b4cc95c581dbe6b1`,
matching the full Aquarium APK. The recovery receipt is in
`restore-coordinator-080-recovery/receipt.json`. This verifies restoration at
that point, despite the install job's error; later diagnostic installs may
change the installed APK again.

Delayed-arrival recording J‑65b7f5245144 is queued for the Pixel and requires
it to be unlocked. Its result and subsequent restoration must be verified
separately.
The host crab and cleaning controller tests both pass (`pytest -q
 tests/test_species_movement.py -k 'reef and (crab or cleaning)'`: 2 passed,
24 deselected); this does not replace visual gameplay verification.

J‑65b7f5245144 eventually ended in a coordinator plugin error after waiting for
the device to unlock; its automatic recovery completed. J‑79635116193f recorded
55 seconds but failed during transfer of the 137 MB recording; cleanup removed
the device-side file, so no video was retained. The shorter J‑5eed6de04cda
completed and captured the fish's delayed arrival and the cleaning reaction.
The fish moved at about 13 seconds into the recording, after the 22-second gap
between app launch and recording start. The shrimp moved to the fish, but their
bodies visibly intersected it.

A temporary placement variant in J‑7f48661fb04a raised the cleaning position
from 0.08 below to 0.24 above the fish origin. Its recording shows the shrimp
above the fish with their legs near its back. The change is now in the reef
generator and both saved style levels, with before-and-after Pixel images in the
refinement catalogue. The comparison uses a diagnostic teleport and one fish
orientation in realistic style; anime, other orientations, and user-steered
interactions remain unverified. The full, previously built Aquarium APK was
restored by J‑5ee2379d90b0; it predates this placement change and must be rebuilt
to include it.

Crab recording J‑9301c89dfe91 used the current controller, but its host coral
and passing fish still obscure the crab, so it does not verify the claws or
climbing. A clearer continuous observation remains necessary.

The full app was rebuilt at `/tmp/reef-shrimp-full-build/aquarium-shrimp.apk`
(SHA-256 `2792101601d3e2e5c51f9b62ca5942f21e5e8ba20629a4409baf0d9e1e8bea04`).
The packaging comparison found only the two reef entries changed in its CD
bundle; the other entries were preserved from the previously verified APK.
The recipe is `package-shrimp-full.py` and uses temporary build inputs.
Pixel job J‑df19f5642e98 installed the APK and its screenshot shows Aquarium
running in the clownfish tank. The coordinator nevertheless reported
`runtime-log-failure`: the collected `wf.log` contains accumulated older crash
records, while the screenshot shows the app running; this job does not establish
whether the reported log failure originated in this launch. It also does not
verify either reef selection in the full app. Full-app reef launch and the
remaining interaction checks are still open. The complete movement test suite
passed (26 tests).

Correction: the first full-app repack accidentally truncated eight bytes from
the SHEL startup script. Its log shows a Forth compile error and it fell back
to the clownfish tank, explaining J‑df19f5642e98. The packaging recipe now
preserves the entire SHEL chunk and its distinct TOC length convention.
Corrected APK SHA-256 is
`9440b8eda115e48d8977e19e508dbb3339cfd3ddad320690a497996a55478974`.
Installation was verified by J‑5845aad10cb3, and J‑6afb216871ee showed the
selector and completed without a runtime-log failure. In J‑b0301d24abd7 a
coordinator-owned touch sequence selected the realistic Gulf reef in that
full APK; the resulting screenshot shows the reef. The coordinator restores
the prior foreground screen after the session. Anime selection, the crab,
and the other shrimp orientation and steering checks are still open.

J‑e63f3f009eb1 used the corrected full APK's selector to launch the anime reef;
its recording and screenshot show the outlined style. J‑c72b7fe4f198 selected
the realistic reef and held then released the on-screen joystick: the boxfish
visibly moved left and remained stationary after release. This route stopped
above the shrimp and did not verify cleaning. J‑6faec5f14dc5 is a queued
follow-up route toward the shrimp; it has not run while the Pixel is locked.
