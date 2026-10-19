---
name: Avoid broad pkill patterns
description: pkill -f "node.*index.js" kills the user's own manually-started servers; use specific PIDs or confirm first
type: feedback
originSessionId: f3a787ff-e88f-44fa-8fd7-2cf3a966f5ee
---
Don't use broad `pgrep -af … | xargs kill` or `pkill -f "node.*index.js"` to clean up before restarting a dev server — the user often has their own copy running from a terminal, and the broad pattern kills it too. Today this happened multiple times; the user only noticed hours later ("i don't know when this happened" with a SIGTERM shutdown log).

**Why:** The user manages their own dev server in a terminal and reasonably assumes I won't touch it. Killing it silently breaks their flow and they don't know why until they look.

**How to apply:** Prefer killing by the specific PID returned from `run_in_background` (I know that PID). If I don't know the exact PID and do need to clear port 8080, check `pgrep -af "node.*index.js"` first and ask before killing anything that isn't mine. Better still: let the user restart their own server — I can just tell them the change is live once the static files are rewritten.
