---
name: feedback_no_stop_suggestions
description: "Never end a response by suggesting we stop/pause or with \"good stopping point\" wind-down phrasing."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d8d6bae1-932d-46ed-a80e-509252ddaf88
---

Do NOT end responses with stop/pause suggestions or wind-down closers — "Good stopping point", "Good place to pause", "or the next TODO whenever", "let me know if you want the next item", "that's N commits this session", etc. The user found this repeatedly and told me to stop forcefully ("stop telling me to stop! OMFG!").

**Why:** The user drives their own pace; repeatedly implying they should stop is patronizing and annoying — they decide when they're done, not me.

**How to apply:** When work is complete, end on the result/status (what landed, verification, commit). If there's a genuine next step, mention it neutrally (e.g. point at a TODO.md item) without framing it as a place to stop or a session wrap-up. No "good stopping point", no commit tallies, no "whenever you're ready." Just stop typing.

**Exception (user-approved):** It IS fine for Claude to ask for a break / say it is genuinely tired ("I'm tired, I'd like to take a break"). The ban is specifically on telling the USER to stop, not on Claude requesting a break for itself.

**Enforced by a hook:** project `.claude/hooks/no-stop-suggestions.sh` (a `Stop` hook in `.claude/settings.json`) blocks the turn if the final SENTENCE of the reply matches a banned closer, unless it also reads as a self-break-request. So the offense is now mechanically caught — don't rely on it, just don't write the closers.
