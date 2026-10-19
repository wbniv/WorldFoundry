\ Betta: unhurried side-to-side patrol at midwater.
: ss-leg 761 ; : ss-rest 762 ;
: ss-target-x ss-leg read-mailbox if -3.3 else 3.3 then ;
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
      INDEXOF_Z_POS read-mailbox 2.2 < if JOYSTICK_BUTTON_UP | then
      INDEXOF_Z_POS read-mailbox 2.8 > if JOYSTICK_BUTTON_DOWN | then
      760 write-mailbox
    then
  then ;
