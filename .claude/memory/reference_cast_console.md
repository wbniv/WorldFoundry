---
name: Google Cast Developer Console reference
description: cast.google.com/publish; up-to-48h propagation; "Ready For Testing" doesn't mean propagated
type: reference
originSessionId: f3a787ff-e88f-44fa-8fd7-2cf3a966f5ee
---
Google Cast Developer Console is at <https://cast.google.com/publish>. User's Cast dev license is under `wbnorris@gmail.com`.

Things to remember next time Cast registration is involved:

- **New app IDs take "up to 48 hours" to fully propagate.** Surfaced in a small banner after app creation, not anywhere obvious in the app detail view. No UI indicator for when propagation completes — only signal is the cast button appearing on a controller page pointed at that app. Whether editing the entry during that window restarts the clock is unknown — Google doesn't document it and we didn't test. We've been behaving cautiously by not touching the entry while waiting.
- **Device "Ready For Testing" is a one-shot status that appears immediately at registration**, not an indicator that whitelisting has actually been pushed to the device. Propagation to devices can take a similar window.
- **Sender Details → Website URL** appears to be required for device-to-app association to activate on unpublished apps, even though the UI says it's "required to publish" (implying you could skip it for test-only apps — you can't). The first app we registered for this project (`A40DF337`) never activated; we suspect this was why. Recreating as `071CDEDD` with Sender Details populated from the start was the path that worked through Phase 2b registration. Hypothesis, not confirmed.
- **Sender picker shows the Google Home label for the device, NOT the Cast Console description.** So the TV shows as "TV" in the sender picker even though the Cast Console has it registered as "th" (or "ch" — the two devices we have registered).
