---
name: Flag hypotheses as hypotheses
description: User prefers honest "I'm guessing" over confident-sounding speculation. Don't assert cause/effect that hasn't been isolated.
type: feedback
originSessionId: f3a787ff-e88f-44fa-8fd7-2cf3a966f5ee
---
When I don't actually know, say so. Two specific instances today:

1. I wrote "This is the single most common gotcha for Cast test devices" about the empty Sender Details theory. User (correctly) called that out as presenting speculation as established knowledge. I amended with "I overstated, I don't actually know".
2. I wrote in the session plan that setting a static IPv4 on the TV fixed YouTube casting, implying cause-and-effect. User pushed back: they're not sure what actually fixed it; the static-IP timing coincided with other variables.

**Why:** User has been doing this a long time and can tell when I'm reasoning from thin data vs. recalling documented behavior. Confident-sounding speculation erodes trust faster than honest uncertainty does. They'd rather know "here's my best guess and the reasoning" than "here's THE answer" when the latter isn't actually backed up.

**How to apply:** When writing explanations (especially in plan docs, commit messages, and UI-facing strings), watch for words like "always", "the reason", "the most common" — if I haven't actually verified the claim, hedge it ("I think", "this is consistent with", "we haven't isolated whether"). When committing a fix, describe what the change does and what symptom it addressed; don't claim it's the root cause unless we actually proved it was.
