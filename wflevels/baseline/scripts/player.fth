\ Route ordinary native input; consume baseline control chords before physics.
: base-input
  INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox
  dup JOYSTICK_BUTTON_B JOYSTICK_BUTTON_C | & if drop 0 then
  dup JOYSTICK_BUTTON_A & if
    dup JOYSTICK_BUTTON_UP JOYSTICK_BUTTON_DOWN | & if drop 0 then
  then INDEXOF_INPUT write-mailbox ;
base-input
