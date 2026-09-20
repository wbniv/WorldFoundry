# How to play the macOS build over VNC (no Mac needed)

You will start a Codemagic build, open a remote desktop onto the Mac that ran it, launch `wf_game` there, and try a few things. Budget: about **20 minutes** of Mac time. Total hands-on time: about **30 minutes**.

## Before you start (one time, on this laptop)

Install a VNC viewer:

```bash
sudo apt install -y tigervnc-viewer
```

Keep this page open in one browser tab and Codemagic in another.

## Step 1 — Start the build with remote access ON

1. Open [codemagic.io/app/6aafa6886ab3f21cf431a6cb](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb).
2. Click the blue **Start new build** button (top right).
3. In the dialog:
    - **Select branch** → `2026-new-level`
    - **Select workflow** → **macOS Desktop (Debug, headless)**
    - Tick the checkbox **Enable SSH/VNC access** ← this is the important one
4. Click **Start new build**.

The build page opens and the steps start ticking through. It takes about 4 minutes.

## Step 2 — Get the VNC login details

While the build is running (or within 10 minutes after it finishes), look **above the list of build steps** for a link that says:

> **Explore build machine via SSH or VNC/RDP client**

Click it. A panel opens showing two things:

- An **SSH command** (a long `ssh …` line with a **Copy** button)
- **VNC** details: **Host**, **Port**, **Username**, **Password**

Don't close this panel — you'll copy from it in the next two steps. The details are only good for this one build.

## Step 3 — Open the remote desktop

In a terminal on this laptop:

```bash
vncviewer HOST:PORT
```

Replace `HOST:PORT` with the two values from the panel, joined by a colon — for example `vncviewer 192.159.66.83:16543`. When it asks, enter the **Username** and **Password** from the panel.

A macOS desktop appears in a window. That is the Mac that just built the game.

If the picture looks stretched or tiny, that's fine — it's a virtual display.

## Step 4 — Open a terminal on the Mac and launch the game

Easiest: in the VNC desktop, open **Terminal** (⌘Space, type `Terminal`, Enter — or Finder → Applications → Utilities → Terminal). Then paste:

```bash
cd ~/clone/wfsource/source/game
../../../engine/wf_game.app/Contents/MacOS/wf_game --windowed -L"$HOME/clone/wflevels/snowgoons-blender/snowgoons-standalone.iff"
```

(If `~/clone` doesn't exist, run `echo $CM_BUILD_DIR` in the terminal and use that folder instead of `~/clone`.)

A 640×480 window titled WorldFoundry should open showing the snowgoons level — the house, the hedges, the tree. The terminal prints a line like
`macos: window 640x480 points, 640x480 pixels (scale 1.0), CAMetalLayer attached` — that's the confirmation the window is real.

Alternative if the VNC desktop is awkward: run the **SSH command** from Step 2 in a terminal on this laptop instead. You get a shell on the Mac; the same launch commands work, and the game window still appears on the VNC desktop.

## Step 5 — Try things (this is the actual test)

Do these in order and note what happens for each. "It didn't work" is a useful answer too — just say what you saw.

1. **Move.** Arrow keys / WASD. Does the player move? Does the camera follow? Walk into the house — does it stop you?
2. **Quit with Esc.** Does the window close cleanly? In the terminal, run `echo $?` — it should print `0`.
3. **Launch again, quit with ⌘Q.** Same check.
4. **Launch again, click the red close button** (top-left of the window). Same check.
5. **Different size.** Launch with `-width=800 -height=600` added before `-L…`. Is the window bigger? The terminal line should say `800x600`.
6. **Fullscreen.** Launch with `-fullscreen` added. Does it take over the whole display? Does quitting bring the desktop back? (On a virtual display this may do something odd — just describe it.)
7. **Double-click.** In the VNC desktop, open Finder → go to `clone/engine/` → double-click `wf_game.app`. Does anything open? (It may open no window at all — that's expected today and still worth knowing.)

If you have a game controller you can plug into this laptop, it will **not** reach the remote Mac over VNC — skip gamepad.

Take screenshots of anything interesting: on the Mac, `screencapture ~/shot1.png` in the terminal, then from this laptop
`scp -P PORT USERNAME@HOST:~/shot1.png .` (same HOST/PORT/USERNAME as VNC; password when asked).

## Step 6 — Finish

Back on the Codemagic build page, click **Cancel build**. Otherwise the Mac keeps running (and billing) until the 60-minute limit.

## Step 7 — Tell me what happened

Paste your notes from Step 5 into the chat (screenshots too, or drop them into `docs/plans/2026-09-21-macos-human-verification/`). I'll record the results in the plan and close the TODO items.

## If something goes wrong

- **No "Explore build machine" link** — the checkbox in Step 1 wasn't ticked. Start another build.
- **VNC connection refused** — more than 10 minutes passed after the build finished. Start another build.
- **The game window opens but is black** — tell me; that is a real finding.
- **`vncviewer` not found** — the `apt install` in the first section.
