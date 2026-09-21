\ wf
\ Global mb 2: deadline; 3: race state (0 init, 1 racing, 2 won, 3 timeout)
\ 4..6: checkpoint; 7: restart edge; global 70/71 score/time; 73 falls.
: stop-ball
  0 INDEXOF_XSPEED write-mailbox
  0 INDEXOF_YSPEED write-mailbox
  0 INDEXOF_ZSPEED write-mailbox ;
: controls
  INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox 30720 &
  dup 16384 & if 64 | then
  dup 8192 & if 128 | then ;
: respawn
  4 read-mailbox INDEXOF_X_POS write-mailbox
  5 read-mailbox INDEXOF_Y_POS write-mailbox
  6 read-mailbox INDEXOF_Z_POS write-mailbox
  stop-ball ;
: reset-race
  INDEXOF_TIME read-mailbox 60 + 2 write-mailbox
  1 3 write-mailbox 0 70 write-mailbox 60 71 write-mailbox
  0 72 write-mailbox 0 73 write-mailbox
  0 4 write-mailbox 0 5 write-mailbox 0.53 6 write-mailbox
  respawn ;
3 read-mailbox 0 = if reset-race then
INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox 1 & if
  7 read-mailbox 0 = if reset-race then
  1 7 write-mailbox
else 0 7 write-mailbox then
3 read-mailbox 1 = if
  2 read-mailbox INDEXOF_TIME read-mailbox - dup 71 write-mailbox
  0 <= if 3 3 write-mailbox then
  controls INDEXOF_INPUT write-mailbox
  INDEXOF_Z_POS read-mailbox -11 < if
    73 read-mailbox 1 + 73 write-mailbox respawn
  then
  INDEXOF_X_POS read-mailbox 47 >
  INDEXOF_X_POS read-mailbox 51 < &
  INDEXOF_Y_POS read-mailbox 55 > &
  INDEXOF_Y_POS read-mailbox 57 < &
  INDEXOF_Z_POS read-mailbox -2 < &
  INDEXOF_Z_POS read-mailbox -5.5 > &
  3 read-mailbox 1 = & if
    2 3 write-mailbox 71 read-mailbox 100 * 1000 + 70 write-mailbox
  then
else
  0 INDEXOF_INPUT write-mailbox stop-ball
then

3 read-mailbox 1770 write-mailbox
73 read-mailbox 1771 write-mailbox
