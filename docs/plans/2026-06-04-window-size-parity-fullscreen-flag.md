# Plan: Window size parity + fullscreen flag

## Context

Two problems discovered during `WF_RECORD=1 task run-moon`:

1. **Recording window is 512×384** — the engine always defaults to 512×384
   (`platform_init.cc:171-175`). Without recording the user resizes the window
   manually each session, so it feels larger. With recording the FBO is fixed at
   `_xSize × _ySize = 512×384` (set from `_halWindowWidth/_halWindowHeight` at
   construction), so the output video is always tiny regardless of window size.

2. **No fullscreen/maximize option** — `bFullScreen` global exists
   (`display.cc:602`, default `true` in `platform_init.cc:64`) but is never wired
   to any X11 call. The `-width=`/`-height=`/`-fullscreen`/`-window` args that
   would fix this are all inside a `#if 0` block in `platform_init.cc:93`.

## What to implement

### 1. Re-enable `-width=N`, `-height=N`, `-fullscreen` in `platform_init.cc`

Remove the `#if 0` / `#endif` around the existing arg-parsing block
(`platform_init.cc:93–177`). The code already handles `-width=N` → `_halWindowWidth`
and `-height=N` → `_halWindowHeight`.

Add one new case inside the same block: when `-fullscreen` is seen, query the
X11 screen dimensions and store them as the window size:

```cpp
else if (strcmp(argv[i], "-fullscreen") == 0) {
    bFullScreen = true;
    ::Display* d = XOpenDisplay(NULL);
    if (d) {
        _halWindowWidth  = DisplayWidth(d, DefaultScreen(d));
        _halWindowHeight = DisplayHeight(d, DefaultScreen(d));
        XCloseDisplay(d);
    }
}
```

`platform_init.cc` already includes `<X11/Xlib.h>` indirectly; add it explicitly
if the build fails.

This means `_xSize/_ySize` (and therefore the recording FBO) will match the
chosen window size at construction time.

### 2. Wire fullscreen in `mesa.cc` — `OpenMainWindow()`

After `XMapRaised()`, if `bFullScreen` is set, send the EWMH fullscreen
`ClientMessage` to the root window so the WM makes the window truly fullscreen
(no title bar, covers entire screen):

```cpp
extern bool bFullScreen;
if (bFullScreen) {
    Atom wm_state  = XInternAtom(halDisplay.mainDisplay, "_NET_WM_STATE", False);
    Atom fs_atom   = XInternAtom(halDisplay.mainDisplay, "_NET_WM_STATE_FULLSCREEN", False);
    XEvent ev = {};
    ev.type = ClientMessage;
    ev.xclient.window       = halDisplay.win;
    ev.xclient.message_type = wm_state;
    ev.xclient.format       = 32;
    ev.xclient.data.l[0]    = 1;        // _NET_WM_STATE_ADD
    ev.xclient.data.l[1]    = fs_atom;
    XSendEvent(halDisplay.mainDisplay,
               DefaultRootWindow(halDisplay.mainDisplay),
               False,
               SubstructureNotifyMask | SubstructureRedirectMask,
               &ev);
    XFlush(halDisplay.mainDisplay);
}
```

Place this immediately after the existing `XSetWMProtocols()` call and before
`glXMakeCurrent()`.

### 3. Add `WF_FULLSCREEN=1` to Taskfile run-* tasks

Same pattern as `WF_RECORD`. Add to each of `run-snowgoons`, `run-qbert`,
`run-smb`, `run-moon`, and update `run-level` / `run-debug` descs:

```bash
FSFLAG=""
if [ -n "${WF_FULLSCREEN:-}" ]; then FSFLAG="-fullscreen"; fi
# pass $FSFLAG to engine alongside $RECFLAG
```

Update desc strings to say `WF_FULLSCREEN=1 for fullscreen`.

## TODO.md entry to add

```
- [ ] macOS window management: implement -width=N, -height=N, -fullscreen in the macOS
      platform HAL using AppKit (NSWindow frame sizing, toggleFullScreen:/NSWindowStyleMaskFullScreen).
      Linux uses X11/_NET_WM_STATE_FULLSCREEN; macOS needs the same flags wired to AppKit equivalents.
```

## Files changed

| File | Change |
|------|--------|
| `wfsource/source/hal/linux/platform_init.cc` | Remove `#if 0`, add `-fullscreen` case that queries screen dimensions |
| `wfsource/source/gfx/gl/mesa.cc` | Send `_NET_WM_STATE_FULLSCREEN` after `XMapRaised()` when `bFullScreen` |
| `Taskfile.yml` | Add `WF_FULLSCREEN=1` → `-fullscreen` to all run-* tasks |

`main.cc` needs no changes — `-fullscreen` parsing goes in `platform_init.cc`
where the other window-size args live.

## Verification

```bash
# Normal (512×384 default window):
task run-moon

# Fullscreen (queries screen dims, FBO matches, no title bar):
WF_FULLSCREEN=1 task run-moon

# Record at fullscreen resolution:
WF_FULLSCREEN=1 WF_RECORD=1 task run-moon
# → output mp4 is at screen resolution (e.g. 1920×1080)

# Record at custom size:
# (requires passing -width/-height directly via run-level for now)
task run-level -- wflevels/moon_site01-standalone.iff -width=1280 -height=720 -record_video
```

Also rebuild the engine (`task build`) and confirm the window opens fullscreen
on :0 before recording.
