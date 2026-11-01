# Planted Tank PERM pool check, 2026-11-02

The frozen diagnostic Planted Tank APK (SHA-256 `a04321b9c6fe0796300a9941a4f022c3a2aa85bf5fa5e5efd77177bf91ebb893`) ran on cast1 in coordinator job J‑e7fb1d15e7c4. At level load, the app reported:

```text
PERM_POOL used_bytes=2792 total_bytes=1000000 free_bytes=997208
```

That is **2,792 bytes used (0.28%)**, with **997,208 bytes free**. The log timestamp precedes the first `PLANTS generation` line by 261 ms, so this reading covers permanent assets loaded for the level; the generated foliage uses the separate `ROOM` pool. The Dream started with its saved defaults (`speed=3`, `hold=120`); all five coordinator process samples were stable on PID 15573, the job completed successfully, and the device returned to a ready state.

[Coordinator timeline](planted-perm-diagnostic/interactive-timeline.json) and the corresponding [captured logcat](planted-perm-diagnostic/input-sample-001-logcat.txt). The two earlier launches without the diagnostic line are retained under [first attempt](planted-perm/interactive-timeline.json) and [early capture attempt](planted-perm-early-2/interactive-timeline.json).
