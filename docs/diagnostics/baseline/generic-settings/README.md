# Shared generic settings acceptance — 6 October 2026

Baseline default and full gallery passed all 20 coordinator assertions on both
Chromecast HD (cast1) and Android 12 Project Room (cast2). Tests cover held and
released directional input, paused TV picker, both owner identities, stale
sessions, instance isolation, validated Apply/Cancel, reconnect, Home/resume in
the same process and gameplay reset chords. The gallery contains 178 visible
rows across two owners; these sessions test representative scalar/text fields,
not every descriptor presentation.

[Acceptance manifest](acceptance.json) and compact receipts/screenshots under
[acceptance](acceptance/) identify jobs, APK hashes and full local evidence hashes.
The default frozen APK is `baseline-bce22bdf00057ae3.apk`; gallery is
`baseline-b1f91d72ddcf33f5.apk`. Their receipts include the full SHA-256 values.
The installed coordinator release is described by [v4 review](coordinator-review-v4.json)
and [deployment transcript](coordinator-deployment-v4.log).

The default standalone level SHA-256 is
`4aca056094c048b61f2254aec7cb601c60b32a284958cd963c4b20b511d654e5`.
It is appended to the main CD at index 7. [Bundle verification](main-cd/verification.json)
passes all 156 source, bundle and desktop gameplay checks.
[Preservation receipt](main-cd/preservation.json) confirms that the previous shell
and seven entries and bodies are unchanged byte-for-byte. Boot remains level 0.

Eight isolated integration tests passed in [the contract log](isolated-contracts-final.log),
independently compiling the shared host and plant consumer migration without
unrelated colour/native-text/diagnostic enhancements in the shared checkout.
The actual gallery catalog passed two-owner validation and commit in [gallery-host.log](gallery-host.log).

Plant device acceptance is complete on both devices using the same frozen APK
`aquarium-a2b7ecc8478f9809.apk` (SHA-256
`a2b7ecc8478f98097a766efcbce0b4a1310c2e3ed1b1e408ea6e040daa02f4f5`).
Cast2 passed 29 assertions in job `J-ff04d9b7fe6e`; cast1 passed 30 in
`J-83fe8930e6d5`, including the additional Down clearance precondition.
Both verify native text entry and Up without process loss, seed precision,
seed/water regeneration, speed-only generation continuity, stale sessions,
invalid drafts, Cancel, reconnect, all four held/released directions,
same-process Home/resume and selector exit.

Cast1's accepted [movement samples](acceptance/plant-chromecast-test-01/movement-samples.json)
show Down from Z=3.015 to Z=1.367 and subsequent release settling. Its earlier
run stopped because Down began on the rock at Z=1.365; this was corrected by
lifting immediately before that probe and checking clearance.
Native text entry replaces the initial 0 before entering seed 1254.
[v5 deployment](coordinator-deployment-v5.log) identifies cast2's installed
validator. Cast1's final validator uses the [v6 review](coordinator-review-v6.json)
and [deployment transcript](coordinator-deployment-v6.log).
The v6 suite passed 146 tests; its unrelated scheduler timing assertion passed
on [rerun](coordinator-v6-timing-recheck.log). The preceding v5 suite passed all 147.

This acceptance covers the shared generic settings integration and plant
consumer migration. Every gallery descriptor's interactive presentation,
optional motion/room-transition fixtures and slope traversal remain separately
scoped work.
