\ Blue Shrimp: slow crossings of the substrate, with a rest at either end.
: ss-leg 761 ; : ss-rest 762 ;
: ss-target-x ss-leg read-mailbox if -3.8 else 3.8 then ;
: ss-drive
  ss-rest read-mailbox 0 > if
    ss-rest read-mailbox INDEXOF_DELTA_TIME read-mailbox - 0 max ss-rest write-mailbox
    0 760 write-mailbox
  else
    INDEXOF_X_POS read-mailbox ss-target-x - dup abs .4 < if
      drop 1 ss-leg read-mailbox - ss-leg write-mailbox
      2 ss-rest write-mailbox 0 760 write-mailbox
    else
      0 < if JOYSTICK_BUTTON_RIGHT else JOYSTICK_BUTTON_LEFT then
      INDEXOF_Y_POS read-mailbox -.45 < if JOYSTICK_BUTTON_C | then
      INDEXOF_Y_POS read-mailbox -.75 > if JOYSTICK_BUTTON_B | then
      760 write-mailbox
    then
  then ;
