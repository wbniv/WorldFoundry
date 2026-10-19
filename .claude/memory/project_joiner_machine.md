---
name: project-joiner-machine
description: Second test machine for wf-edit collab testing — IP and SSH access
metadata: 
  node_type: memory
  type: project
  originSessionId: 86622ebf-4e16-4fa3-82a5-70c7afee2bd4
---

Second machine used for joiner-side collab testing.

**IP:** 192.168.4.32
**SSH:** `ssh 192.168.4.32` — Will's SSH keys on the laptop should grant access (no special config needed).
**Role:** Joiner machine — runs `task join` to connect to the host's named tunnel.
**Why:** Both machines share the git repo; no scp needed, just `git pull` to sync.
