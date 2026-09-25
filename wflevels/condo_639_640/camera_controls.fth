\ Camera policy only. Build supplies cc-shot, cc-camera, cc-touch,
\ cc-default-yaw/elevation/range, cc-look-x/y/z and cc-unit-z words.
\ Global mailboxes 110..139 belong to this controller (see README).
: cc-key 111 read-mailbox & 0 <> ;
: cc-was 121 read-mailbox & 0 <> ;
: cc-wrap dup 0 < if 1 + then dup 1 >= if 1 - then ;
: cc-sin
  cc-wrap dup 0.5 > if 0.5 - -1 else 1 then >r
  2 * dup 1 swap - * dup 16 * swap 4 * 5 swap - / r> * ;
: cc-cos 0.25 + cc-sin ;
: cc-stop 0 INDEXOF_INPUT write-mailbox
  0 INDEXOF_XSPEED write-mailbox 0 INDEXOF_YSPEED write-mailbox ;
: cc-reset
  cc-default-yaw 114 write-mailbox
  cc-default-elevation 115 write-mailbox
  cc-default-range 116 write-mailbox
  0 113 write-mailbox 0 112 write-mailbox ;
: cc-init 110 read-mailbox 0 = if
  cc-reset 1 110 write-mailbox then ;
: cc-directions
  JOYSTICK_BUTTON_RIGHT cc-key if 1 else 0 then
  JOYSTICK_BUTTON_LEFT cc-key if 1 else 0 then - 133 write-mailbox
  JOYSTICK_BUTTON_UP cc-key if 1 else 0 then
  JOYSTICK_BUTTON_DOWN cc-key if 1 else 0 then - 134 write-mailbox ;
: cc-touch-input
  \ Chord is latched until BOTH fingers release. It cancels pending taps.
  JOYSTICK_BUTTON_A cc-key JOYSTICK_BUTTON_B cc-key & if
    123 read-mailbox 0 = if 1 120 write-mailbox then
    1 123 write-mailbox 1 124 write-mailbox
  then
  123 read-mailbox 0 <> if
    JOYSTICK_BUTTON_A cc-key JOYSTICK_BUTTON_B cc-key | 0 = if
      0 123 write-mailbox 0 124 write-mailbox 0 122 write-mailbox then
  else
    JOYSTICK_BUTTON_B cc-key if
      122 read-mailbox 117 read-mailbox + 122 write-mailbox
      122 read-mailbox 0.6 >= 124 read-mailbox 0 = & if
        cc-reset 1 124 write-mailbox then
    else
      JOYSTICK_BUTTON_B cc-was 124 read-mailbox 0 = & if
        1 119 write-mailbox then
      0 122 write-mailbox 0 124 write-mailbox
    then
    JOYSTICK_BUTTON_A cc-key 0 = JOYSTICK_BUTTON_A cc-was & if
      112 read-mailbox 1 + dup 3 >= if drop 0 then 112 write-mailbox
    then
  then
  112 read-mailbox 0 <> if 1 135 write-mailbox 1 113 write-mailbox then
  123 read-mailbox 0 = if
    112 read-mailbox 1 = if 1 136 write-mailbox then
    112 read-mailbox 2 = if 134 read-mailbox negate 137 write-mailbox then
  then ;
: cc-desktop-input
  JOYSTICK_BUTTON_C cc-key if 1 120 write-mailbox then
  JOYSTICK_BUTTON_D cc-key if
    1 135 write-mailbox
    JOYSTICK_BUTTON_A cc-key if
      125 read-mailbox 0 = if cc-reset then
      1 125 write-mailbox
    else
      0 125 write-mailbox
      JOYSTICK_BUTTON_B cc-key if
        134 read-mailbox negate 137 write-mailbox
      else 1 136 write-mailbox then
    then
  else
    0 125 write-mailbox
    JOYSTICK_BUTTON_B cc-key JOYSTICK_BUTTON_B cc-was 0 = &
    INDEXOF_HARDWARE_JOYSTICK1_RAW_JUSTPRESSED read-mailbox JOYSTICK_BUTTON_B & 0 <> | if
      1 119 write-mailbox then
  then
  125 read-mailbox 0 = if
    JOYSTICK_BUTTON_F cc-key if 1 else 0 then
    JOYSTICK_BUTTON_E cc-key if 1 else 0 then -
    137 read-mailbox + -1 max 1 min 137 write-mailbox then ;
: cc-adjust
  136 read-mailbox 0 <> if
    133 read-mailbox 0 <> 134 read-mailbox 0 <> | if
      1 113 write-mailbox
      114 read-mailbox 133 read-mailbox 117 read-mailbox * 6 / + cc-wrap 114 write-mailbox
      115 read-mailbox 134 read-mailbox 117 read-mailbox * 12 / +
      0.097222222 max 0.222222222 min 115 write-mailbox
    then
  then
  137 read-mailbox 0 <> if
    1 113 write-mailbox
    116 read-mailbox 137 read-mailbox 117 read-mailbox * 3 * + 116 write-mailbox
  then ;
: cc-pose
  113 read-mailbox 0 <> if
    115 read-mailbox 0.097222222 max 0.222222222 min 115 write-mailbox
    115 read-mailbox cc-sin 128 write-mailbox
    \ Clearance and room-top constraints are coupled to elevation.
    116 read-mailbox 4 max 12 min
    3.2 128 read-mailbox / max
    27.5 INDEXOF_Z_POS read-mailbox - cc-look-z - 3.2 max
    10.8 min 128 read-mailbox / min 116 write-mailbox
    115 read-mailbox cc-cos 116 read-mailbox * 129 write-mailbox
    114 read-mailbox cc-sin 129 read-mailbox * cc-look-x + 130 write-mailbox
    114 read-mailbox cc-cos 129 read-mailbox * negate cc-look-y + 131 write-mailbox
    128 read-mailbox 116 read-mailbox * cc-look-z + 132 write-mailbox
  else
    cc-default-x 130 write-mailbox cc-default-y 131 write-mailbox cc-default-z 132 write-mailbox
  then
  130 read-mailbox INDEXOF_X_POS cc-shot write-actor-mailbox
  131 read-mailbox INDEXOF_Y_POS cc-shot write-actor-mailbox
  132 read-mailbox cc-unit-z + INDEXOF_Z_POS cc-shot write-actor-mailbox ;
: cc-input
  cc-init INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox 111 write-mailbox
  INDEXOF_DELTA_TIME read-mailbox 0 max 0.05 min 117 write-mailbox
  0 119 write-mailbox 0 120 write-mailbox
  0 135 write-mailbox 0 136 write-mailbox 0 137 write-mailbox
  cc-directions
  cc-touch if cc-touch-input else cc-desktop-input then
  cc-adjust cc-pose
  111 read-mailbox 30720 & 118 write-mailbox
  cc-touch 0 = 135 read-mailbox 0 = & if
    118 read-mailbox JOYSTICK_BUTTON_A cc-key if 1 else 0 then | 118 write-mailbox then
  135 read-mailbox 0 <> if 0 118 write-mailbox cc-stop then
  111 read-mailbox 121 write-mailbox ;

: cc-label
  >r dup 112 read-mailbox = swap 140 + write-mailbox
  INDEXOF_X_POS read-mailbox INDEXOF_X_POS r@ write-actor-mailbox
  INDEXOF_Y_POS read-mailbox INDEXOF_Y_POS r@ write-actor-mailbox
  INDEXOF_Z_POS read-mailbox 3.2 + INDEXOF_Z_POS r@ write-actor-mailbox
  114 read-mailbox INDEXOF_ROTATION_C r@ write-actor-mailbox
  r> drop ;
: cc-labels cc-touch if
  0 cc-label-0 cc-label 1 cc-label-1 cc-label 2 cc-label-2 cc-label
  then ;
