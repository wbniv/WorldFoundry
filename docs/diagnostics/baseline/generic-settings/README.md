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

Plant device acceptance remains pending. The frozen aquarium APK includes the
shared checkout's separate native IME work. Both sessions stopped because native
text entry retained the initial seed 0, so typing 1254 produced 01254. The next
reviewed validator deletes that initial digit before entering the test value.
This does not change the generic host or plant simulation implementation.
