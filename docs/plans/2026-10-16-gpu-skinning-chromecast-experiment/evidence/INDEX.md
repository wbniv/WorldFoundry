# GPU-skinning evidence index

**State: partial experiment, not adopted.** This record is recovered from
`origin/gpu-skinning-proposal` at `f50a30059`. Its prototype is not merged
into the current branch. CPU remains the default. Cast2 completed its
controlled population study; the cast1 aquarium campaign stopped before
completion. No two-device adoption decision or GPU-time claim is justified.

## Provenance and interpretation

- Release source revision: `e64e5459660889ec8cda8dcadd059d10688c039c`; native SHA-256 `9ddd539f29600c729c0e26430ca162d61311b242a4c7d6defe0a97e4ff484b80`.
- Corrected profiling source revision: `8f90bba8c65e47b32aca6511a7de9b461b433089`; native SHA-256 `13f604947c1aff3c39dc729c51e650561e55c5fa45f06785cf7f29f15580663c`.
- Full per-variant installed APK SHA-256 values are in each run’s linked `apk-installations.json`. The native hashes above are not APK hashes. Campaign recipe and fixture hashes are in [cast1 campaign](campaign.json) and [cast2 campaign](cast2-populations/campaign.json).
- Cast2 uses the existing DFRM adapter and 1/4/16 bodies, not a general four-weight authoring benchmark. Profiles and release builds use different native cohorts. GPU time and isolated culling time were unavailable. See [results](cast2-populations/results.json), [verification status](verification-status.json) and [panel audit](panel-visibility-audit.json).
- Two diagnostic receipts have their network endpoint fields redacted in this copy. Original local raw logs and captures may contain network details or pairing information and are not included in the committed evidence.

## Cast2 controlled population sessions

Each row covers 1, 4 and 16 bodies. Release rounds support the recorded
presentation comparison; corrected profiles support CPU/counter analysis.
All 16 receipts were validated, but this is one device and is not an adoption decision.

| Job | Variant and purpose | Outcome | APK hashes and raw evidence |
| --- | --- | --- | --- |
| J‑248e89210d61 | population/cpu/round-1 | Completed; release round | [Receipt](cast2-populations/population/cpu/round-1/receipt.json), [APK hashes](cast2-populations/population/cpu/round-1/apk-installations.json), [run data](cast2-populations/population/cpu/round-1/) |
| J‑3d882cfd89c5 | population/cpu-no-cull/round-1 | Completed; release round | [Receipt](cast2-populations/population/cpu-no-cull/round-1/receipt.json), [APK hashes](cast2-populations/population/cpu-no-cull/round-1/apk-installations.json), [run data](cast2-populations/population/cpu-no-cull/round-1/) |
| J‑25e202859de6 | population/gpu-no-cull/round-1 | Completed; release round | [Receipt](cast2-populations/population/gpu-no-cull/round-1/receipt.json), [APK hashes](cast2-populations/population/gpu-no-cull/round-1/apk-installations.json), [run data](cast2-populations/population/gpu-no-cull/round-1/) |
| J‑df7ef4cc2a72 | population/gpu/round-1 | Completed; release round | [Receipt](cast2-populations/population/gpu/round-1/receipt.json), [APK hashes](cast2-populations/population/gpu/round-1/apk-installations.json), [run data](cast2-populations/population/gpu/round-1/) |
| J‑f6f316064593 | population/cpu-no-cull/round-2 | Completed; release round | [Receipt](cast2-populations/population/cpu-no-cull/round-2/receipt.json), [APK hashes](cast2-populations/population/cpu-no-cull/round-2/apk-installations.json), [run data](cast2-populations/population/cpu-no-cull/round-2/) |
| J‑36ea7304b79b | population/gpu-no-cull/round-2 | Completed; release round | [Receipt](cast2-populations/population/gpu-no-cull/round-2/receipt.json), [APK hashes](cast2-populations/population/gpu-no-cull/round-2/apk-installations.json), [run data](cast2-populations/population/gpu-no-cull/round-2/) |
| J‑559c1098c7f5 | population/gpu/round-2 | Completed; release round | [Receipt](cast2-populations/population/gpu/round-2/receipt.json), [APK hashes](cast2-populations/population/gpu/round-2/apk-installations.json), [run data](cast2-populations/population/gpu/round-2/) |
| J‑300ce107be2f | population/cpu/round-2 | Completed; release round | [Receipt](cast2-populations/population/cpu/round-2/receipt.json), [APK hashes](cast2-populations/population/cpu/round-2/apk-installations.json), [run data](cast2-populations/population/cpu/round-2/) |
| J‑bb3abdf0e9ab | population/gpu-no-cull/round-3 | Completed; release round | [Receipt](cast2-populations/population/gpu-no-cull/round-3/receipt.json), [APK hashes](cast2-populations/population/gpu-no-cull/round-3/apk-installations.json), [run data](cast2-populations/population/gpu-no-cull/round-3/) |
| J‑1ef5fe06cc2c | population/gpu/round-3 | Completed; release round | [Receipt](cast2-populations/population/gpu/round-3/receipt.json), [APK hashes](cast2-populations/population/gpu/round-3/apk-installations.json), [run data](cast2-populations/population/gpu/round-3/) |
| J‑ad6b36500631 | population/cpu/round-3 | Completed; release round | [Receipt](cast2-populations/population/cpu/round-3/receipt.json), [APK hashes](cast2-populations/population/cpu/round-3/apk-installations.json), [run data](cast2-populations/population/cpu/round-3/) |
| J‑e3573a7cf01f | population/cpu-no-cull/round-3 | Completed; release round | [Receipt](cast2-populations/population/cpu-no-cull/round-3/receipt.json), [APK hashes](cast2-populations/population/cpu-no-cull/round-3/apk-installations.json), [run data](cast2-populations/population/cpu-no-cull/round-3/) |
| J‑9f38d64525e4 | population/cpu/profile | Completed; corrected profile | [Receipt](cast2-populations/population/cpu/profile/receipt.json), [APK hashes](cast2-populations/population/cpu/profile/apk-installations.json), [run data](cast2-populations/population/cpu/profile/) |
| J‑7c79a85acea4 | population/gpu/profile | Completed; corrected profile | [Receipt](cast2-populations/population/gpu/profile/receipt.json), [APK hashes](cast2-populations/population/gpu/profile/apk-installations.json), [run data](cast2-populations/population/gpu/profile/) |
| J‑ca74aa106927 | population/cpu-no-cull/profile | Completed; corrected profile | [Receipt](cast2-populations/population/cpu-no-cull/profile/receipt.json), [APK hashes](cast2-populations/population/cpu-no-cull/profile/apk-installations.json), [run data](cast2-populations/population/cpu-no-cull/profile/) |
| J‑7e279c3194ab | population/gpu-no-cull/profile | Completed; corrected profile | [Receipt](cast2-populations/population/gpu-no-cull/profile/receipt.json), [APK hashes](cast2-populations/population/gpu-no-cull/profile/apk-installations.json), [run data](cast2-populations/population/gpu-no-cull/profile/) |

## Cast1 aquarium sessions

Each completed row covers None, one, two and six seahorse pairs.
These are partial campaign observations, not a complete matched comparison.

| Job | View, variant and purpose | Outcome | APK hashes and raw evidence |
| --- | --- | --- | --- |
| J‑b772c10c99a3 | close-idle/cpu/round-1 | Completed; partial campaign | [Receipt](close-idle/cpu/round-1/receipt.json), [APK hashes](close-idle/cpu/round-1/apk-installations.json), [run data](close-idle/cpu/round-1/) |
| J‑2676c1a59ed6 | close-idle/gpu/round-1 | Completed; partial campaign | [Receipt](close-idle/gpu/round-1/receipt.json), [APK hashes](close-idle/gpu/round-1/apk-installations.json), [run data](close-idle/gpu/round-1/) |
| J‑310f760c47c1 | close-crawl/cpu/round-1 | Completed; partial campaign | [Receipt](close-crawl/cpu/round-1/receipt.json), [APK hashes](close-crawl/cpu/round-1/apk-installations.json), [run data](close-crawl/cpu/round-1/) |
| J‑8151451b4e91 | close-crawl/gpu/round-1 | Completed; partial campaign | [Receipt](close-crawl/gpu/round-1/receipt.json), [APK hashes](close-crawl/gpu/round-1/apk-installations.json), [run data](close-crawl/gpu/round-1/) |
| J‑084b4f52095d | close-idle/gpu/round-2 | Completed; partial campaign | [Receipt](close-idle/gpu/round-2/receipt.json), [APK hashes](close-idle/gpu/round-2/apk-installations.json), [run data](close-idle/gpu/round-2/) |
| J‑80544ac040b2 | close-idle/cpu/round-2 | Completed; partial campaign | [Receipt](close-idle/cpu/round-2/receipt.json), [APK hashes](close-idle/cpu/round-2/apk-installations.json), [run data](close-idle/cpu/round-2/) |
| J‑89795ac3f6d5 | close-crawl/gpu/round-2 | Completed; partial campaign | [Receipt](close-crawl/gpu/round-2/receipt.json), [APK hashes](close-crawl/gpu/round-2/apk-installations.json), [run data](close-crawl/gpu/round-2/) |
| J‑27fbaa42fc50 | close-crawl/cpu/round-2 | Completed; partial campaign | [Receipt](close-crawl/cpu/round-2/receipt.json), [APK hashes](close-crawl/cpu/round-2/apk-installations.json), [run data](close-crawl/cpu/round-2/) |
| J‑bf2f41ca05e6 | close-idle/cpu/round-3 | Completed; partial campaign | [Receipt](close-idle/cpu/round-3/receipt.json), [APK hashes](close-idle/cpu/round-3/apk-installations.json), [run data](close-idle/cpu/round-3/) |

## Failed, held and superseded attempts

| Job or set | Device and purpose | Disposition |
| --- | --- | --- |
| J‑da19a5050cff | cast1, `close-idle/gpu/round-3` | **uncertain**; Target process was missing during startup after the unverified-panel Back path; job is excluded from measurements. Coordinator fix 8c24437 is deployed. A fresh job will measure the same frozen recipe. [receipt](failed-close-idle-gpu-round-3-J-da19a5050cff/receipt.json). |
| J‑0d2afeba096d | cast1, `close-idle/gpu/round-3` | **held**; Completed with verified hashes and cleanup, but the phone-controller panel covered the scene through measurement in all four cases (coordinator 8c24437 sent no Back). Neither accepted nor dropped; per the user (option b) the same frozen recipe is rerun under a coordinator with verified panel dismissal and the require-hidden harness policy. Its captures show the LAN endpoint and PIN and stay local. [receipt](held-close-idle-gpu-round-3-J-0d2afeba096d/receipt.json). |
| J‑8c4c0f882e93 | cast1, `close-idle/gpu/round-3` | **uncertain**; First require-hidden session (coordinator 47cab46). pair2 and pair6 measured with the panel verified hidden (one Back each, engine hide line, after-capture absent). The third case, close-idle-none-gpu, showed the panel (white 0.638, black 0.353, fill 1.0) 6.4 s after launch; the single Back produced the engine line for a Back with no visible panel (system-back), so the activity left and the session failed under require-hidden. No exit record exists for that process (pid 32381). Cause of the engine treating the panel as hidden is unproven: that process logcat was parsed by the coordinator but not saved. Excluded from timing; not retried. [receipt](failed-close-idle-gpu-round-3-J-8c4c0f882e93/receipt.json). |
| J‑d8577a92e5f5 | cast1, `close-idle/gpu/round-3` | **uncertain**; Not the known crash and not a measurement. The first install (pair2, 25525fcc) and the restore install (3d796c77) were refused with INSTALL_FAILED_VERSION_DOWNGRADE: cast1 already had aquarium versionCode 41 installed (sha 1008aed8...), and the frozen APKs are versionCode 7. Cleanup could not be verified; the coordinator's automatic readd J‑ff796a60b072 ended recovery-required, and cast1 needs an administrator readd. The v41 package came from outside this campaign. [receipt](failed-close-idle-gpu-round-3-J-d8577a92e5f5/receipt.json). |
| J‑1e59129b22a2 | cast1, GPU close-idle round 1 | Excluded after pair-one startup loss; [receipt](failed-gpu-round-1-J-1e59129b22a2/receipt.json) and [startup analysis](startup-exits.json). |
| J‑c4cccc5e4274 | cast1, GPU close-idle round 2 | Excluded after pair-one startup loss; [receipt](failed-gpu-round-2-J-c4cccc5e4274/receipt.json) and [startup analysis](startup-exits.json). |
| J‑3764d1d22e88 | cast1, initial CPU attempt | Installation refused; retain [receipt](failed-cpu-first/receipt.json), not an accepted timing. |
| J‑fd4329e8e0e0 | cast2, earlier GPU check | Installation refused; retain [receipt](failed-cast2-check/receipt.json), not an accepted timing. |
| `superseded-profiles-v1` | cast2, early profiles | Retain provenance, but exclude from CPU acceptance: final-batch accounting was incomplete and per-face clocks perturbed timing. See [campaign](cast2-populations/superseded-profiles-v1/campaign.json). |
| `superseded-campaign-v3` | earlier frozen campaign | Retain [campaign](superseded-campaign-v3/campaign.json) for provenance; v4 supersedes it. |

## Other checks

These checks were not part of the controlled performance comparison. Their
linked receipts record available artifact and device provenance; where a receipt
does not identify an APK or source revision, that provenance is unavailable.

| Job or evidence | Purpose and outcome | Supports |
| --- | --- | --- |
| J‑49a2f4008d65 | Cast1 GPU one-pair rendering check; receipt state `succeeded` | GPU path check; [receipt](cast1-gpu-pair1-check/receipt.json). |
| J‑807d69af58af | Cast2 GPU six-pair rendering check; receipt state `succeeded` | GPU path check; [receipt](cast2-gpu-check/receipt.json). |
| J‑39b77ea8097b | Cast1 home/resume and context reuse; receipt state `succeeded` | Lifecycle observation; [receipt](cast1-gpu-resume/receipt.json). |
| J‑81b37ed86d58 | Cast2 home/resume and context reuse; receipt state `succeeded` | Lifecycle observation; [receipt](cast2-gpu-resume/receipt.json). |
| J‑801ec1d61d72 | Cast1 held/released directional diagnostic; receipt state `uncertain` | Directional input only; full UI validation failed; [receipt](cast1-diagnostic-input/receipt.json). |
| J‑56c41a027869 | Cast2 held/released directional diagnostic; receipt state `uncertain` | Directional input only; full UI validation failed; [receipt](cast2-diagnostic-input/receipt.json). |
| J‑64ad5b5d0707 | Cast1 coordinator recovery; receipt state `succeeded` | Recovery, not performance; [receipt](cast1-recovered/receipt.json). |
| J‑be114610d338 | Cast2 corrected one-body profile check; receipt state `succeeded` | Profile validation; [receipt](cast2-profile-v2-one-body-check/receipt.json). |

GL parity evidence is in [gl/](gl/). The Apple offscreen gates are
[metal/](metal/), [metal-counters/](metal-counters/) and
[metal-profile-v2/](metal-profile-v2/); they establish correctness checks
on the recorded Apple environment, not Apple device performance.

## Reproduce the cast2 analysis

```sh
python3 scripts/gpu_skinning_evidence/analyze-gpu-skinning.py \
  --evidence docs/plans/2026-10-16-gpu-skinning-chromecast-experiment/evidence/cast2-populations \
  --out /tmp/gpu-cast2-results.json --population-study --device chromecast-test-02
```

The strict analyzer was rerun on the curated data: it verified 36 release
runs and 12 corrected profile runs. Numerical `views` and native cohorts
match the saved results; the rerun additionally emits the panel-audit field.
Retained historical paths and hashes identify original artifacts; they do not
imply that the APKs or experiment code are present in this branch.
