# Orientation APKs on both casts — 2026‑10‑24

Batch `B-7a3a13ee715a`: the orientation builds of Seahorse Grid (`71b5a1e54e41`) and Aquarium (`75ee120db339`) on `chromecast-test-01` and `chromecast-test-02`, one command. See the [orientation plan](../../plans/2026-10-24-screensaver-landscape-orientation.md).

```sh
task chromecast:submit WORKFLOW=install DEVICE=chromecast-test-01,chromecast-test-02 -- seahorse-orientation.apk aquarium-orientation.apk
task chromecast:evidence BATCH=B-7a3a13ee715a OUT=docs/diagnostics/multi-apk-2026-10-24-orientation-casts/batch
```

| Item | App | Device | Job | Install | Launcher verification |
|---|---|---|---|---|---|
| 1 | seahorse | cast1 | J‑e5eec7f458a5 | installed | `verified` |
| 1 | seahorse | cast2 | J‑83a47bb1c09e | installed | **`failed`**: stale or unverified artwork after bounded recovery |
| 2 | aquarium | cast1 | J‑4bc8fef5d348 | installed | `verified` |
| 2 | aquarium | cast2 | J‑f0f561a9a873 | installed | `verified` |

- Installed 4/4; launcher verified 3/4. The same cast2 Seahorse failure reproduced on batch `B-4f516d57b15d`.
- **Cause:** cast2 draws unfocused launcher tiles under a grey scrim, so the captured tile is about 0.597 × the artwork + 13.2 and the brightness gain (1.325) passes the 1.3 limit. Fixed in coordinator commit `2f3c94b` ("Verify launcher tiles drawn under an unfocused-tile scrim"), deployed 2026‑10‑24 with `1593055`.
- **Re-run with the fixed verifier (2026‑10‑25):** batch `B-3c3d448216fe`, job J‑82f54c20a561, same APK `71b5a1e54e41` on cast2: `verified`, `normalisation: scrim`, MAE 0.779, RMS 1.545, worst region 1.990, scrim gain 0.597, offset 13.2. These match the numbers predicted in `2f3c94b`. Evidence in `rerun-cast2-seahorse/`. Cast1 Seahorse (J‑a176c27ecce6) also verified again. Two earlier attempts on cast2 (J‑d2b5478d6fa1, J‑4ed799902b09) ended `plugin-error` because the cast was dreaming Seahorse; see the coordinator `TODO.md`.
- Only the failed job (cast2 Seahorse) keeps its launcher screenshots; the other jobs keep their JSON and one `verified-tile.png` each. The `expected-*.png` reference images are derived from the APK and are not kept.
