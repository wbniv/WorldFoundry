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

Plant settings, native IME entry, seed precision, regeneration, reconnect and
movement passed on cast2 (job `J-ff04d9b7fe6e`). Cast1 (job `J-9cce86e30842`)
passed the settings assertions and three held directions, then stopped at Down:
the goby had already settled onto the central rock before the test pressed Down.
The [movement samples](acceptance/plant-chromecast-test-01/movement-samples.json)
record identical starting/ending Z=1.365. The corrected test lifts immediately
before Down and checks it starts above the rock. Cast1's remaining direction,
release and lifecycle/exit acceptance awaits that harness deployment/rerun.

Native entry now replaces the retained initial 0 before entering seed 1254.
[v5 deployment](coordinator-deployment-v5.log) and [review](coordinator-review-v5.json)
identify the installed release used by these sessions.
