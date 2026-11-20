\ Sea Stars: surface id 0 sand, 1 front, 2 right, 3 back, 4 left.
\ All collision/clearance bounds are authored by the exporter.
: st@ read-mailbox ; : st! write-mailbox ;
: st-frac begin dup 1 >= if 1 - 0 else 1 then until
  begin dup 0 < if 1 + 0 else 1 then until ;
: st-sin st-frac dup .5 > if .5 - -1 else 1 then >r
  2 * dup 1 swap - * dup 16 * swap 4 * 5 swap - / r> * ;
: st-mod >r r@ / st-frac r> * ;
: st-cos .25 + st-sin ;
: st-held st-buttons st@ & 0 <> if 1 else 0 then ;
: st-change ( surface -- )
  \ Sand <-> glass flips what the stick means, so the press that caused it is
  \ ignored until it changes; otherwise pushing into the glass would climb and
  \ then step straight back down. Glass <-> glass keeps holding the direction.
  dup 0 = st-surface st@ 0 = | if st-buttons st@ 30727 & else 0 then st-lock st!
  st-surface st@ st-old st! st-surface st! 1.2 st-roll st! ;
: st-reset
  0 st-surface st! 0 st-roll st! 0 st-idle st! 0 st-reach st! 0 st-lock st!
  INDEXOF_X_POS st@ st-x st! INDEXOF_Y_POS st@ st-y st!
  st-bottom st-z st! 1 st-init st! ;
: st-input
  INDEXOF_HARDWARE_JOYSTICK1_RAW st@ st-buttons st!
  INDEXOF_DELTA_TIME st@ .2 > if 1 st-neutral st! then
  st-neutral st@ if
    st-buttons st@ 30727 & 0 = if 0 st-neutral st! then
    0 st-buttons st!
  then
  st-buttons st@ 30727 & if 0 st-idle st! 0 st-auto-step st! else
    st-idle st@ st-dt st@ + st-idle st!
  then
  st-idle st@ 30 >= st-dream | if st-autopilot then
  JOYSTICK_BUTTON_RIGHT st-held JOYSTICK_BUTTON_LEFT st-held - st-dx st!
  JOYSTICK_BUTTON_UP st-held JOYSTICK_BUTTON_DOWN st-held - st-dy st!
  st-lock st@ if
    st-buttons st@ 30727 & st-lock st@ = if 0 st-dx st! 0 st-dy st! else 0 st-lock st! then
  then
  JOYSTICK_BUTTON_A st-held if
    st-prev st@ JOYSTICK_BUTTON_A & 0 = if 2 st-reach st! then
  then
  st-buttons st@ st-prev st! ;
: st-sand
  st-x st@ st-dx st@ st-speed * st-dt st@ * + st-limit-x negate max st-limit-x min st-x st!
  st-y st@ st-dy st@ st-speed * st-dt st@ * + st-limit-y negate max st-limit-y min st-y st!
  st-bottom st-z st!
  st-y st@ st-limit-y negate <= st-dy st@ 0 < & if 1 st-change then
  st-x st@ st-limit-x >= st-dx st@ 0 > & if 2 st-change then
  st-y st@ st-limit-y >= st-dy st@ 0 > & if 3 st-change then
  st-x st@ st-limit-x negate <= st-dx st@ 0 < & if 4 st-change then ;
: st-wall
  st-z st@ st-dy st@ st-speed * st-dt st@ * + st-bottom max st-top min st-z st!
  st-surface st@ 1 = if
    st-limit-y negate st-y st!
    st-x st@ st-dx st@ st-speed * st-dt st@ * + st-x st!
    st-x st@ st-limit-x > if st-limit-x st-x st! 2 st-change then
    st-x st@ st-limit-x negate < if st-limit-x negate st-x st! 4 st-change then
  else st-surface st@ 2 = if
    st-limit-x st-x st!
    st-y st@ st-dx st@ st-speed * st-dt st@ * + st-y st!
    st-y st@ st-limit-y > if st-limit-y st-y st! 3 st-change then
    st-y st@ st-limit-y negate < if st-limit-y negate st-y st! 1 st-change then
  else st-surface st@ 3 = if
    st-limit-y st-y st!
    st-x st@ st-dx st@ st-speed * st-dt st@ * - st-x st!
    st-x st@ st-limit-x negate < if st-limit-x negate st-x st! 4 st-change then
    st-x st@ st-limit-x > if st-limit-x st-x st! 2 st-change then
  else
    st-limit-x negate st-x st!
    st-y st@ st-dx st@ st-speed * st-dt st@ * - st-y st!
    st-y st@ st-limit-y negate < if st-limit-y negate st-y st! 1 st-change then
    st-y st@ st-limit-y > if st-limit-y st-y st! 3 st-change then
  then then then
  st-z st@ st-bottom <= st-dy st@ 0 < & if 0 st-change then ;
: st-tick
  st-init st@ 0 = if st-reset then
  INDEXOF_DELTA_TIME st@ dup .2 > if drop 0 else 0 max .05 min then st-dt st!
  st-clock st@ st-dt st@ + st-clock st!
  st-reach st@ st-dt st@ - 0 max st-reach st!
  st-input
  st-roll st@ 0 > if
    st-roll st@ st-dt st@ - 0 max st-roll st!
  else st-surface st@ 0 = if st-sand else st-wall then then
  st-avoid-rocks
  st-x st@ INDEXOF_X_POS st!
  st-y st@ INDEXOF_Y_POS st!
  st-z st@ INDEXOF_Z_POS st!
  0 INDEXOF_XSPEED st! 0 INDEXOF_YSPEED st! 0 INDEXOF_ZSPEED st! ;
