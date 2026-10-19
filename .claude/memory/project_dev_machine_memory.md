---
name: project_dev_machine_memory
description: Dev laptop is 16GB (not 32); ASan wf-edit OOMs running 2 collab instances — use the non-ASan build
metadata: 
  node_type: memory
  type: project
  originSessionId: b8485c42-7c33-41ff-923d-cd60b01d804b
---

The WorldFoundry dev laptop (Dell Inspiron 14 7445 2-in-1, AMD) has **16 GB RAM** — 2×8 GB, both slots populated and healthy (`sudo dmidecode -t 17`: DIMM 0 Channel A 8 GB + DIMM 0 Channel B 8 GB). The OS reports only ~14.4 GB `MemTotal` / ~15.5 GB online — that's normal (integrated-GPU UMA reservation + kernel), **not** a missing/failed stick. Will may say "32 GB" — it's 16; don't chase phantom RAM or a hardware fault.

RAM is **upgradeable**: 2× **SODIMM** slots (DDR5-5600 / PC5-44800, 262-pin, Non-ECC, 1.1 V), both currently filled with 8 GB → upgrading means *replacing* both. Sweet spot 2×16 = 32 GB; max **64 GB** (2×32). Per Crucial + Dell owner's manual.

**Why:** the `wf-edit` editor built by `task build-wf-edit` is Debug **+ AddressSanitizer** (ASan is the Debug default), which ~2–3×'s RSS (~700 MB+ per instance). Running **two** ASan editors for a collab test, alongside Chrome + Claude, exhausts 16 GB + swap → the **OOM killer SIGKILLs** the editor mid-startup (terminal shows `Killed` right after `collab room … started`, before the relay-connect verdict). `oom_kill` in `/proc/vmstat` confirms it fires.

**How to apply:** for actual collaboration/multi-instance testing use the **non-ASan** build — `task build-wf-edit-fast` → `build-editor-fast/wf-edit` (~103 MB on disk, ~156 MB RSS, fits comfortably). Reserve the ASan `build-editor/wf-edit` for memory-debugging. Note also: the editor runs X11/GLX under **XWayland** (Wayland session, `DISPLAY=:0`), so its GL/`HALStart` startup can stall for several seconds and GNOME flags "WF Editor Is Not Responding" — it usually **recovers**; click Wait, don't Force Quit. See [[reference_wf_build_pipeline]] and [[project_world_foundry]].
