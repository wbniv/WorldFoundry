\ Waypoints are authored: front wall, up, clockwise round to back, down,
\ a sand waypoint and a seeded pause. Both Dream and idle use this driver.
: st-autopilot
  0 st-buttons st!
  \ Glass climbing Off: skip the glass legs and go straight to the sand waypoint.
  st-glass-on 0 = st-auto-step st@ 4 < & if 4 st-auto-step st! then
  st-auto-step st@ 0 = if
    JOYSTICK_BUTTON_DOWN st-buttons st!
    st-surface st@ 1 = if 1 st-auto-step st! then
  else st-auto-step st@ 1 = if
    JOYSTICK_BUTTON_UP st-buttons st!
    st-z st@ 3 >= if 2 st-auto-step st! then
  else st-auto-step st@ 2 = if
    JOYSTICK_BUTTON_RIGHT st-buttons st!
    st-surface st@ 3 = if 3 st-auto-step st! then
  else st-auto-step st@ 3 = if
    JOYSTICK_BUTTON_DOWN st-buttons st!
    st-surface st@ 0 = if 4 st-auto-step st! then
  else st-auto-step st@ 4 = if
    \ Landing from the back wall latches the DOWN that brought it here (st-change), and a latch
    \ clears only when the buttons change. Press nothing until it clears, or the star never leaves.
    st-lock st@ 0 = if JOYSTICK_BUTTON_DOWN st-buttons st! then
    st-y st@ .3 < if 5 st-auto-step st! 20 st-auto-wait st! then
  else
    st-auto-wait st@ st-dt st@ - 0 max dup st-auto-wait st!
    0 <= if 0 st-auto-step st! then
  then then then then then ;
