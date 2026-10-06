# Baseline desktop verification

6 October 2026. `python3 wflevels/baseline/verify.py --desktop` passed all recorded checks against the hashes in [build-receipt.json](build-receipt.json). [verification.json](verification.json) records exact observations and debug-assisted setup.

Injected input waits for the director to observe both press and release, including after screenshot stalls. The session checked native Forth compilation, grounded spawn, held/released movement in +Y, heading-zero movement in +X, reset, first-person and return-to-follow switching, unit-cube collision, support at four floor quadrants, fall recovery and remote reset chord without jumping. Captures show [spawn](spawn.png), [follow view](follow.png), [first-person view](first-person.png) and [cube collision](cube-collision.png).

This is desktop gameplay and source/compiled catalog evidence. Interactive settings, Chromecast behavior, optional slope traversal and main CD integration remain pending. No engine files were changed by the baseline implementation. The tested executable incorporates other work in this shared checkout; its hash is recorded for reproducibility.

Saved engine log lines have trailing whitespace removed.
