# Fix: core dump on window close button

## Context
When the user clicks the X / close button, the window manager sends a `ClientMessage` event with the `WM_DELETE_WINDOW` atom. Because `mesa.cc` never registered this protocol via `XSetWMProtocols`, the WM forcibly destroyed the X window while the game was still running. The next frame's `XPending()`/`XNextEvent()` call hit an invalid display connection and crashed.

## Solution (implemented in commit ae678d6)

Three changes to `wfsource/source/gfx/gl/mesa.cc`:

1. Added `static Atom _wmDeleteWindow;` after `HalDisplay halDisplay;`
2. After `XMapRaised()` in `OpenMainWindow()`, registered the protocol:
   ```cpp
   _wmDeleteWindow = XInternAtom(halDisplay.mainDisplay, "WM_DELETE_WINDOW", False);
   XSetWMProtocols(halDisplay.mainDisplay, halDisplay.win, &_wmDeleteWindow, 1);
   ```
3. Added `ClientMessage` handler in `ProcessXEvents()`:
   ```cpp
   case ClientMessage:
       if ((Atom)event.xclient.data.l[0] == _wmDeleteWindow)
           sys_exit(0);
       break;
   ```

Clicking the close button now calls `sys_exit(0)`, matching the existing Escape key path.
