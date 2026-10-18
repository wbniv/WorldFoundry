\ Arowana: wide turns in its larger tank; no darts.
\ Arowana already owns 760..775, so its input and state are at 780..782.
: ss-leg 781 ; : ss-rest 782 ;
: ss-target-x ss-leg read-mailbox if -8 else 8 then ;
: ss-drive
  ss-rest read-mailbox 0 > if
    ss-rest read-mailbox INDEXOF_DELTA_TIME read-mailbox - 0 max ss-rest write-mailbox
    0 780 write-mailbox
  else
    INDEXOF_X_POS read-mailbox ss-target-x - dup abs 1 < if
      drop 1 ss-leg read-mailbox - ss-leg write-mailbox
      2 ss-rest write-mailbox 0 780 write-mailbox
    else
      0 < if JOYSTICK_BUTTON_RIGHT else JOYSTICK_BUTTON_LEFT then
      INDEXOF_Z_POS read-mailbox 5 < if JOYSTICK_BUTTON_UP | then
      INDEXOF_Z_POS read-mailbox 7 > if JOYSTICK_BUTTON_DOWN | then
      780 write-mailbox
    then
  then ;
