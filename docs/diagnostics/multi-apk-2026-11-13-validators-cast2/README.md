# Per-app validators in one check batch, cast2 (2026‑11‑13)

Batch `B-be5ba75e20e7`, submitted with one `RECIPE` (`recipe.json` here):

```sh
task chromecast:submit RECIPE=recipe.json ASYNC=true
```

| Item | App / APK | Validator | Job | Install | Result |
|---|---|---|---|---|---|
| 1 | Aquarium show `e2ac53f5…` | `menu-back` | J‑b963977acbb3 | install, `different-hash` (was `635980d9…`) | `succeeded` / `completed`; 8 scenes `start_back_home_resume: PASS`, betta animated (1108 px) |
| 2 | Baseline `5b47e27b…` | `baseline-settings` | J‑63eada1c2dc0 | reuse, `exact-match` | `succeeded` / `completed`; 21 of 21 assertions true |

- Each validator ran against its own app. Item 1's `assertions.json` is the
  `check_menu` output (Aquarium level picker: start, Back, Home, resume for each
  scene). Item 2's `baseline-checks.json` is the `check_baseline` output against
  `org.worldfoundry.wf_game.baseline`.
- **Held and released directional input on cast2 through an owned check:** item 2
  held Up for 2200 ms, then Down, Right and Left for 800 ms each, then OK for 1500 ms
  (`held-keys.txt`). The assertions `hardware_up_moves_positive_y`,
  `hardware_press_release_received`, `released_input_settles` and
  `released_direction_20/22/21` are all true.
- Both cleanups `restored`, restoration `safe`, health `ready`.
- `adb-failure-6.json` (item 1) is the known cleanup step that cannot start the
  launcher's `DispatchActivity` (`SecurityException … not exported`, first seen
  2026‑10‑24). It did not fail the job.
- Item 1 replaced `635980d9…`, which is the other session's runtime-object-editing build
  `aquarium-game-actor-settings-cd6b9e9e.apk`
  ([record](../runtime-object-editing-2026-11-11/cast2/README.md)), with the show build.

Large `*wf.log` files (4 MB each) were dropped. The remaining files are the coordinator evidence as downloaded.
