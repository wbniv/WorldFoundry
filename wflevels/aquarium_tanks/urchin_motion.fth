\ Urchin contacts: world anchors, bounded recovery, no engine deformation.
\ Travel/distance use 1024x units to retain small increments in 16.16 mailboxes.
\ 800..839 scratch; 840..967 eight contact slots (16 cells each).
: uf-x 800 ; : uf-y 801 ; : uf-z 802 ; : uf-last-x 803 ; : uf-last-y 804 ;
: uf-init 805 ; : uf-reset 806 ; : uf-dx 807 ; : uf-dy 808 ; : uf-travel 809 ;
: uf-dir-x 810 ; : uf-dir-y 811 ; : uf-dt 812 ; : uf-distance 813 ;
: uf-ox 824 ; : uf-oy 825 ; : uf-limit 826 ; : uf-slot 827 ; : uf-actor 828 ;
: uf-fx 829 ; : uf-fy 830 ; : uf-fz 831 ; : uf-horiz 832 ; : uf-elev 833 ;
: uf-length 834 ; : uf-p 835 ; : uf-state 836 ; : uf-vx 837 ; : uf-vy 838 ;
: uf@ uf-slot tk@ 16 * 840 + + tk@ ;
: uf! uf-slot tk@ 16 * 840 + + tk! ;
: uf-hypot
  abs swap abs 2dup max >r dup * swap dup * + r>
  dup .00000001 < if 2drop 0 else
    3 0 do over over / + .5 * loop nip then ;
: uf-oct dup 1 swap - .04345 * .125 + * ;
: uf-atan2
  2dup abs swap abs + .00000001 < if 2drop 0 else
    over abs over abs 2dup > if swap / uf-oct .25 swap - else / uf-oct then
    over 0 < if .5 swap - then rot 0 < if negate then nip then ;
: uf-smooth dup dup * swap 2 * 3 swap - * ;
: uf-progress uf-dt tk@ swap / 5 uf@ + 1 min dup 5 uf! ;
: uf-travel@ uf-travel tk@ 1024 / ;
: uf-begin
  uf-z tk! uf-y tk! uf-x tk! 0 uf-reset tk!
  INDEXOF_DELTA_TIME tk@ dup .2 > if drop 0 else 0 max .1 min then uf-dt tk!
  uf-init tk@ 0 = if 1 uf-init tk! 1 uf-reset tk!
    uf-x tk@ uf-last-x tk! uf-y tk@ uf-last-y tk! then
  uf-x tk@ uf-last-x tk@ - uf-dx tk!
  uf-y tk@ uf-last-y tk@ - uf-dy tk!
  uf-dx tk@ uf-dy tk@ uf-hypot 1024 * uf-travel tk!
  uf-travel@ .08 > if 1 uf-reset tk! 0 uf-travel tk! then
  uf-travel@ .00000001 > if
    uf-dx tk@ uf-travel@ / uf-dir-x tk!
    uf-dy tk@ uf-travel@ / uf-dir-y tk! then
  uf-distance tk@ uf-travel tk@ + uf-distance tk!
  uf-x tk@ uf-last-x tk! uf-y tk@ uf-last-y tk! ;
: uf-start
  0 uf@ 6 uf! 1 uf@ 7 uf!
  uf-x tk@ uf-ox tk@ + uf-dir-x tk@ .014 * + 2 uf!
  uf-y tk@ uf-oy tk@ + uf-dir-y tk@ .014 * + 3 uf!
  1 4 uf! 0 5 uf! ;
: uf-pose
  0 uf@ uf-fx tk! 1 uf@ uf-fy tk!
  uf-z tk@ .218 - 8 uf@ + uf-fz tk!
  uf-x tk@ uf-ox tk@ + uf-fx tk@ - uf-vx tk!
  uf-y tk@ uf-oy tk@ + uf-fy tk@ - uf-vy tk!
  uf-vx tk@ uf-vy tk@ uf-hypot uf-horiz tk!
  uf-z tk@ .114 - uf-fz tk@ - uf-elev tk!
  uf-horiz tk@ uf-elev tk@ uf-hypot uf-length tk!
  uf-fx tk@ INDEXOF_X_POS uf-actor tk@ write-actor-mailbox
  uf-fy tk@ INDEXOF_Y_POS uf-actor tk@ write-actor-mailbox
  uf-fz tk@ INDEXOF_Z_POS uf-actor tk@ write-actor-mailbox
  uf-elev tk@ uf-horiz tk@ uf-atan2 negate INDEXOF_ROTATION_B uf-actor tk@ write-actor-mailbox
  uf-vy tk@ uf-vx tk@ uf-atan2 INDEXOF_ROTATION_C uf-actor tk@ write-actor-mailbox
  uf-length tk@ .1 / INDEXOF_X_SCALE uf-actor tk@ write-actor-mailbox ;
: uf-foot ( ox oy limit slot actor -- )
  uf-actor tk! uf-slot tk! uf-limit tk! uf-oy tk! uf-ox tk!
  9 uf@ 0 = uf-reset tk@ | if
    uf-x tk@ uf-ox tk@ + 0 uf! uf-y tk@ uf-oy tk@ + 1 uf!
    0 4 uf! 0 5 uf! 0 8 uf! 1 9 uf! 0 10 uf! then
  4 uf@ uf-state tk!
  uf-state tk@ 0 = if
    uf-travel@ .00000001 > if
      uf-x tk@ uf-ox tk@ + 0 uf@ -
      uf-y tk@ uf-oy tk@ + 1 uf@ - uf-hypot
      uf-limit tk@ > if uf-start then then
  else uf-state tk@ 1 = if
    .2 uf-progress dup uf-p tk! uf-smooth .016 * 8 uf!
    uf-p tk@ 1 >= if 2 4 uf! 0 5 uf! then
  else uf-state tk@ 2 = if
    .55 uf-progress dup uf-p tk! uf-smooth
    dup 2 uf@ 6 uf@ - * 6 uf@ + 0 uf!
    3 uf@ 7 uf@ - * 7 uf@ + 1 uf!
    uf-p tk@ 1 >= if 3 4 uf! 0 5 uf! then
  else
    .18 uf-progress dup uf-p tk! uf-smooth 1 swap - .016 * 8 uf!
    uf-p tk@ 1 >= if 0 4 uf! 0 5 uf! 0 8 uf! 10 uf@ 1 + 10 uf! then
  then then then uf-pose ;
