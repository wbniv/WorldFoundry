# Chromecast 02 Aquarium refresh — 2026-10-04

Rebuilt the current working-tree Aquarium and installed it through the protected coordinator after the installed APK was reported stale. The rebuilt APK includes the existing FPS overlay and ongoing generative plant implementation; this report records deployment, rather than claiming that the plant implementation is committed here.

- Device: `chromecast-test-02`, serial `26031HFDD67QH7`, verified at `192.168.4.49:5555`.
- Coordinator job: `J-d6b701aa4f34`, completed with cleanup verified.
- Frozen APK SHA-256: `79433b3c5e80625b13b4bf566e8fd941185affd62f779488ad30bab775f7c1d5`; installed package checksum verified before launch.
- Build: `:app:assembleAquariumRelease`, successful for ARM64 and ARM32.
- On-device scene: planted tank; procedural log reports generation 1, seed 3754288627, 384 shoots, 76,256 vertices and 51,256 triangles.
- FPS counter visible at lower right: 60.1 in the [capture](aquarium-cast2-current-evidence/screenshot.png).
- Restored the previous foreground app, YouTube, after testing. The updated Aquarium remains installed.

The deployment used the current working-tree plant and renderer changes, which are maintained separately from the coordinator commit. Full coordinator enforcement certification remains pending.
