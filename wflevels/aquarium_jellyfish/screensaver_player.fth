\ Jellyfish: long pulse-and-drift traversals with a vertical change on return.
: ss-leg 761 ; : ss-rest 762 ;
: ss-target-x ss-leg read-mailbox if -2.8 else 2.8 then ;
: ss-target-z ss-leg read-mailbox if 3.2 else 2.2 then ;
: ss-zbuttons
  INDEXOF_Z_POS read-mailbox ss-target-z - dup .3 > if drop JOYSTICK_BUTTON_DOWN
  else -.3 < if JOYSTICK_BUTTON_UP else 0 then then ;
: ss-drive
  ss-rest read-mailbox 0 > if
    ss-rest read-mailbox INDEXOF_DELTA_TIME read-mailbox - 0 max ss-rest write-mailbox
    0 760 write-mailbox
  else
    INDEXOF_X_POS read-mailbox ss-target-x - dup abs .35 < if
      drop 1 ss-leg read-mailbox - ss-leg write-mailbox
      1 ss-rest write-mailbox 0 760 write-mailbox
    else
      0 < if JOYSTICK_BUTTON_RIGHT else JOYSTICK_BUTTON_LEFT then
      ss-zbuttons |
      760 write-mailbox
    then
  then ;
