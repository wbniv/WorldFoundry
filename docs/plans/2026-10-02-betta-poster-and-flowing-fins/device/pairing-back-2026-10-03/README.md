# Pairing Back device receipts

`checks.json` and the matching Aquarium/SMB selector and level screenshots record the successful focused pairing/navigation run. The JSON identifies the exact APK hashes and cases checked.

These additional captures come from earlier incomplete attempts and are retained only as historical evidence:

- `betta-fins-a.png` and `betta-fins-b.png`: the sampled changed-pixel count fell below that run's threshold. These images do not establish a passing animation check; the fin implementation was unchanged, and the final focused navigation run excluded this timing-sensitive probe.
- `smb-pairing-above-selector.png`: the filename reflected an incorrect test assumption. SMB provides no phone-controller panel; this screenshot shows its unobstructed selector. The final harness detects whether the APK actually contains phone-controller assets before attempting dismissal.

Later icon-only APKs and their launcher screenshots are documented in the parent plan. These navigation receipts retain their original hashes.
