\ Eight rigid basal pivots; sparse move/hold/recover envelopes.
\ 1000..1095 slots (12 cells each); 1100..1111 scratch.
: us-slot 1100 ; : us-actor 1101 ; : us-ox 1102 ; : us-oy 1103 ; : us-oz 1104 ;
: us-rest-b 1105 ; : us-rest-c 1106 ; : us-wait 1107 ; : us-sign 1108 ;
: us-state 1109 ; : us-p 1110 ; : us-dot 1111 ;
: us@ us-slot tk@ 12 * 1000 + + tk@ ;
: us! us-slot tk@ 12 * 1000 + + tk! ;
: us-interpolate ( progress -- )
  uf-smooth dup 4 us@ 6 us@ - * 6 us@ + 2 us!
  5 us@ 7 us@ - * 7 us@ + 3 us! ;
: us-spine ( ox oy oz rest-b rest-c wait sign slot actor -- )
  us-actor tk! us-slot tk! us-sign tk! us-wait tk!
  us-rest-c tk! us-rest-b tk! us-oz tk! us-oy tk! us-ox tk!
  9 us@ 0 = uf-reset tk@ | if
    0 0 us! 0 1 us! us-rest-b tk@ 2 us! us-rest-c tk@ 3 us!
    us-sign tk@ 8 us! 1 9 us! then
  1 us@ us-state tk! 0 us@ uf-dt tk@ + 0 us!
  us-state tk@ 0 = if
    0 us@ us-wait tk@ >= if
      2 us@ 6 us! 3 us@ 7 us!
      0 us-dot tk!
      uf-travel@ .00000001 > if
        uf-dir-x tk@ us-ox tk@ * uf-dir-y tk@ us-oy tk@ * + .302 / us-dot tk! then
      us-rest-b tk@ 8 us@ .008 * + us-dot tk@ .012 * + 4 us!
      us-rest-c tk@ 8 us@ .009 * + 5 us!
      1 1 us! 0 0 us! then
  else us-state tk@ 1 = if
    0 us@ .7 / 1 min dup us-p tk! us-interpolate
    us-p tk@ 1 >= if 2 1 us! 0 0 us! then
  else us-state tk@ 2 = if
    0 us@ 1.25 >= if
      3 1 us! 0 0 us! 2 us@ 6 us! 3 us@ 7 us!
      us-rest-b tk@ 4 us! us-rest-c tk@ 5 us! then
  else
    0 us@ 1 / 1 min dup us-p tk! us-interpolate
    us-p tk@ 1 >= if 0 1 us! 0 0 us! 8 us@ negate 8 us! then
  then then then
  uf-x tk@ us-ox tk@ + INDEXOF_X_POS us-actor tk@ write-actor-mailbox
  uf-y tk@ us-oy tk@ + INDEXOF_Y_POS us-actor tk@ write-actor-mailbox
  uf-z tk@ us-oz tk@ + INDEXOF_Z_POS us-actor tk@ write-actor-mailbox
  2 us@ INDEXOF_ROTATION_B us-actor tk@ write-actor-mailbox
  3 us@ INDEXOF_ROTATION_C us-actor tk@ write-actor-mailbox ;
