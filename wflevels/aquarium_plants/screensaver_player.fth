\ Planted tank: the urchin explores a short section of substrate.
: ss-leg 761 ; : ss-rest 762 ;
: ss-target-x ss-leg read-mailbox if -.8 else .8 then ;
: ss-drive
  ss-rest read-mailbox 0 > if
    ss-rest read-mailbox INDEXOF_DELTA_TIME read-mailbox - 0 max ss-rest write-mailbox
    0 760 write-mailbox
  else
    INDEXOF_X_POS read-mailbox ss-target-x - dup abs .08 < if
      drop 1 ss-leg read-mailbox - ss-leg write-mailbox
      3 ss-rest write-mailbox 0 760 write-mailbox
    else
      0 < if JOYSTICK_BUTTON_RIGHT else JOYSTICK_BUTTON_LEFT then
      INDEXOF_Y_POS read-mailbox -.65 < if JOYSTICK_BUTTON_UP | then
      INDEXOF_Y_POS read-mailbox -.95 > if JOYSTICK_BUTTON_DOWN | then
      760 write-mailbox
    then
  then ;
