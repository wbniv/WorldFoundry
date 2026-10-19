---
name: feedback-ssh-joiner
description: "For joiner machine tasks, SSH in and run them directly — don't ask the user"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 86622ebf-4e16-4fa3-82a5-70c7afee2bd4
---

When there are commands to run on the joiner machine (192.168.4.32), SSH in with `ssh -i ~/.ssh/wf_debug will@192.168.4.32` and run them directly. Don't ask the user to do it.

**Why:** User explicitly said "you can do that part. remember that."
**How to apply:** git pull, rebuilds, log reads — all done via SSH. Only exception: commands needing a GUI display (task join itself), which still require the user at the machine.
