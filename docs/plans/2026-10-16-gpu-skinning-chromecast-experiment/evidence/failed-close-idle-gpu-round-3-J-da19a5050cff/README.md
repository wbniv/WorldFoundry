# Excluded close-idle GPU round 3 attempt

Coordinator job `J‑da19a5050cff` exited during startup and reported an uncertain result with recovery required. The coordinator restored the selector foreground and original restore APK; there were no surviving owned effects. This job is excluded from performance results. Its evidence is retained unchanged here.

The coordinator startup fix `8c24437` is now deployed. The same frozen recipe is being submitted as a new job; that result will use the canonical `close-idle/gpu/round-3/` path.
