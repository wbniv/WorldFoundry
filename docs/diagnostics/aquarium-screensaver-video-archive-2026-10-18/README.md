# Aquarium screensaver video archive — cast1, 2026-10-18

Nine silent, web-ready H.264 MP4 clips cover all eight screensaver tanks, with one freshwater and one saltwater Planted Tank clip. Every archived clip is 1920 × 1080 and at least 60 seconds long. [Open the gallery](index.html) to review them. Each MP4 has a matching PNG poster.

The captures used the screensaver's fullscreen launcher on `chromecast-test-01`. The launcher and Dream share the same live renderer, but these videos do not by themselves verify natural Dream activation. The Planted Tank's settings strip is intentionally visible.

The coordinator's `record` workflow requested 75 seconds after a 5-second warmup. `scripts/archive-aquarium-screensaver-video.py` starts 2 seconds into each downloaded recording, encodes 60.5 seconds as H.264/yuv420p MP4 with fast-start metadata, and extracts a midpoint poster. [manifest.json](manifest.json) records the tank ID, coordinator job, APK SHA-256, source and archived durations, and media checksums. Source recordings and full device evidence can be retrieved by their job IDs with `task chromecast:evidence JOB=J-example OUT=/path`.

The freshwater and saltwater APKs were built from the installed production screensaver by `scripts/build-aquarium-screensaver-video-variants.py`. Only the Planted Tank's authored property catalog differs: seed 713, age 150, growth paused, and the stated water type. The saltwater variant includes six seahorse pairs. The two capture APK checksums are in the manifest. The production APK (SHA-256 `99fdfce1cde44b45f6037aa4048dfb348b18929847feb4bf567acf9490317a94`) was restored on cast1; coordinator readback J‑64645ecd7a3f confirmed the saved tank choice is **Random** and the idle timeout remains 10 minutes. Cast2 was left untouched.

The coordinator marked the freshwater, saltwater, Arowana, and Tiger Barbs record jobs `recovery-required` after their MP4s, screenshots, and logs were saved. Automatic reconnect jobs completed, and the downloaded videos are playable, long enough, and checksum-verified. Their status is preserved in the manifest rather than reported as a successful coordinator run.

Archive validation decoded every MP4 from start to finish without errors, confirmed H.264/yuv420p video and a duration above 60 seconds, and matched every SHA-256 in the manifest. Sample frames at 5, 30, and 55 seconds differ in every clip. Arowana remains camera-centered and freshwater plant movement is subtle, so those sample checks establish changing frames rather than a measured actor path.

| Clip | Coordinator job | Status |
| --- | --- | --- |
| [Clownfish](clownfish.mp4) | J‑c0ade733f45a | Completed |
| [Blue Shrimp](blue-shrimp.mp4) | J‑f0c93168a58b | Completed |
| [Betta](betta.mp4) | J‑649c2b805c3a | Completed |
| [Jellyfish](jellyfish.mp4) | J‑1bffdc2b9cfa | Completed |
| [Lionfish](lionfish.mp4) | J‑c14e159ea5aa | Completed |
| [Planted Tank, freshwater](planted-freshwater.mp4) | J‑014d3a9310c7 | Recovery required after capture |
| [Planted Tank, saltwater](planted-saltwater.mp4) | J‑239d7f5329be | Recovery required after capture |
| [Arowana](arowana.mp4) | J‑8f5b1e020a7d | Recovery required after capture |
| [Tiger Barbs](tiger-barbs.mp4) | J‑774908e4760a | Recovery required after capture |
