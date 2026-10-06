\ Reset and camera selection only; no adventure state or dialogue.
: base-reset
  base-spawn-x INDEXOF_X_POS base-player write-actor-mailbox
  base-spawn-y INDEXOF_Y_POS base-player write-actor-mailbox
  base-spawn-z INDEXOF_Z_POS base-player write-actor-mailbox
  0 INDEXOF_XSPEED base-player write-actor-mailbox
  0 INDEXOF_YSPEED base-player write-actor-mailbox
  0 INDEXOF_ZSPEED base-player write-actor-mailbox
  base-spawn-heading INDEXOF_ROTATION_C base-player write-actor-mailbox ;
: base-held INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox & 0 <> ;
: base-edge dup base-held swap base-previous-input read-mailbox & 0 = & ;
: base-tick
  base-init read-mailbox 0 = if
    1 base-init write-mailbox 0 base-camera-mode write-mailbox base-reset
  then
  JOYSTICK_BUTTON_B base-edge if base-reset then
  JOYSTICK_BUTTON_C base-edge if base-camera-mode read-mailbox if 0 else 1 then base-camera-mode write-mailbox then
  JOYSTICK_BUTTON_A base-edge if
    JOYSTICK_BUTTON_UP base-held if base-reset then
    JOYSTICK_BUTTON_DOWN base-held if base-camera-mode read-mailbox if 0 else 1 then base-camera-mode write-mailbox then
  then
  INDEXOF_Z_POS base-player read-actor-mailbox -8 < if base-reset then
  base-camera-mode read-mailbox if base-firstperson else base-follow then INDEXOF_CAMSHOT write-mailbox
  INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox base-previous-input write-mailbox ;
base-tick
