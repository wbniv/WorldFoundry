\ Director owns three stable slots, sensory memories and two complete feeding actions.
: gf@ gf-i tk@ 16 * 1000 + + tk@ ;
: gf! gf-i tk@ 16 * 1000 + + tk! ;
: gm@ gf-i tk@ 8 * 1050 + + tk@ ;
: gm! gf-i tk@ 8 * 1050 + + tk! ;
: gs@ gf-owner tk@ 1 - 16 * 1200 + + tk@ ;
: gs! gf-owner tk@ 1 - 16 * 1200 + + tk! ;
: gf-live 0 gf@ 0 <> ;
: gf-log-char 0 sys ; : gf-log-num 1 sys ;
\ Rare feeding events: kind, slot, generation, live count, owner, prey XYZ, mouth XYZ/yaw.
\ 1=release, 2=strike, 3=capture, 4=player action snapshot. No per-frame logging.
: gf-event
  71 gf-log-char 70 gf-log-char 32 gf-log-char gf-log-num
  gf-i tk@ gf-log-num 1 gf@ gf-log-num gf-count tk@ gf-log-num gf-owner tk@ gf-log-num
  2 gf@ gf-log-num 3 gf@ gf-log-num 4 gf@ gf-log-num
  gf-mouth-x tk@ gf-log-num gf-mouth-y tk@ gf-log-num gf-mouth-z tk@ gf-log-num
  gf-mouth-yaw tk@ gf-log-num 10 gf-log-char ;
: gf-clamp01 0 max 1 min ;
: gf-ease dup >r - tk-dt@ 4 * gf-clamp01 * r> + ;
: gf-turn dup >r - tk-wrap dup abs .45 > if r@ tk-cos 0 >= if abs negate else abs then then tk-dt@ .5 * dup negate >r min r> max r> + tk-wrap ;
: gf-hide
  0 0 gf! 0 10 gf! 0 11 gf! 0 15 gf!
  gf-target tk@ gf-i tk@ = if -1 gf-target tk! then ;
: gf-distance
  2 gf@ gf-mouth-x tk@ - dup *
  3 gf@ gf-mouth-y tk@ - dup * +
  4 gf@ gf-mouth-z tk@ - dup * + ;
\ Exact segment/AABB slabs, with generated conservative rock bounds.
: gf-slab
  gf-slab-hi tk! gf-slab-lo tk! gf-slab-d tk! gf-slab-o tk!
  gf-slab-d tk@ abs .00001 < if
    gf-slab-o tk@ gf-slab-lo tk@ < gf-slab-o tk@ gf-slab-hi tk@ > |
    if 2 gf-ray-near tk! then
  else
    gf-slab-lo tk@ gf-slab-o tk@ - gf-slab-d tk@ / gf-slab-a tk!
    gf-slab-hi tk@ gf-slab-o tk@ - gf-slab-d tk@ / gf-slab-b tk!
    gf-slab-a tk@ gf-slab-b tk@ min gf-ray-near tk@ max gf-ray-near tk!
    gf-slab-a tk@ gf-slab-b tk@ max gf-ray-far tk@ min gf-ray-far tk!
  then ;
: gf-rock
  >r >r >r >r 0 gf-ray-near tk! 1 gf-ray-far tk!
  gf-mouth-x tk@ 2 gf@ over - 2swap gf-slab
  r> r> gf-mouth-y tk@ 3 gf@ over - 2swap gf-slab
  r> r> gf-mouth-z tk@ 4 gf@ over - 2swap gf-slab
  gf-ray-near tk@ gf-ray-far tk@ <= if 0 gf-ray-clear tk! then ;
\ GENERATED_OBSTACLES
: gf-clear-ray
  1 gf-ray-clear tk!
  gf-mouth-z tk@ 4 gf@ min gf-rock-top <= if gf-obstacles then
  gf-ray-clear tk@ ;
: gf-edible
  gf-distance .0625 <
  2 gf@ gf-mouth-x tk@ - gf-mouth-yaw tk@ tk-cos gf-mouth-pitch tk@ tk-cos * *
  3 gf@ gf-mouth-y tk@ - gf-mouth-yaw tk@ tk-sin gf-mouth-pitch tk@ tk-cos * * +
  4 gf@ gf-mouth-z tk@ - gf-mouth-pitch tk@ tk-sin * + -.07 >= &
  gf-clear-ray & ;
: gf-player-mouth
  tk-heading tk@ gf-mouth-yaw tk! tk-pitch tk@ gf-mouth-pitch tk! 1 gf-mouth-scale tk!
  INDEXOF_X_POS tk-player read-actor-mailbox tk-heading tk@ tk-cos tk-pitch tk@ tk-cos * .56 * + gf-mouth-x tk!
  INDEXOF_Y_POS tk-player read-actor-mailbox tk-heading tk@ tk-sin tk-pitch tk@ tk-cos * .56 * + gf-mouth-y tk!
  INDEXOF_Z_POS tk-player read-actor-mailbox tk-pitch tk@ tk-sin .56 * + gf-mouth-z tk! ;
: gf-resident-mouth
  gf-ryaw tk@ gf-mouth-yaw tk! gf-rpitch tk@ gf-mouth-pitch tk! .75 gf-mouth-scale tk!
  gf-rx tk@ gf-ryaw tk@ tk-cos gf-rpitch tk@ tk-cos * .42 * + gf-mouth-x tk!
  gf-ry tk@ gf-ryaw tk@ tk-sin gf-rpitch tk@ tk-cos * .42 * + gf-mouth-y tk!
  gf-rz tk@ gf-rpitch tk@ tk-sin .42 * + gf-mouth-z tk! ;
: gf-consume
  gf-hide gf-count tk@ 1 - 0 max gf-count tk!
  gf-owner tk@ 1 = if
    gf-consumed-player tk@ 1 + gf-consumed-player tk!
  else gf-consumed-resident tk@ 1 + gf-consumed-resident tk! then 3 gf-event ;
: gf-strike-start
  0 gs@ 0 < 15 gf@ 0 = & if
    0 0 gs! gf-i tk@ 1 gs! 1 gf@ 2 gs! 0 3 gs!
    gf-owner tk@ 15 gf! 2 gf-event
  then ;
: gf-player-eat
  1 gf-owner tk! 0 gs@ 0 < if
    gf-player-mouth -1 gf-best tk! 1000 gf-best-d tk!
    3 0 do i gf-i tk! gf-live 15 gf@ 0 = & if 4 gf-event gf-edible if
      gf-distance dup gf-d tk! gf-best-d tk@ < if i gf-best tk! gf-d tk@ gf-best-d tk! then
    then then loop
    gf-best tk@ 0 >= if gf-best tk@ gf-i tk! gf-strike-start else
      tk-cooldown tk@ 0 <= if .3 tk-dart tk! 1 tk-cooldown tk! then
    then
  then ;
: gf-strike-tick
  0 gf-gape tk!
  0 gs@ 0 >= if
    0 gs@ tk-dt@ + gf-strike-duration min dup 0 gs! gf-elapsed tk!
    1 gs@ gf-i tk!
    gf-live 1 gf@ 2 gs@ = & 15 gf@ gf-owner tk@ = & if
      3 gs@ not if
        gf-owner tk@ 1 = if gf-player-mouth else gf-resident-mouth then
        gf-elapsed tk@ .0001 + gf-capture-time >= if
          gf-edible if gf-consume then
          1 3 gs!
          gf-live if 0 15 gf! then
        else
          \ Short suction draw only while the prey remains in actual mouth reach.
          gf-elapsed tk@ .06 >= gf-edible & if
            2 gf@ gf-mouth-x tk@ over - tk-dt@ 10 * gf-clamp01 * + 2 gf!
            3 gf@ gf-mouth-y tk@ over - tk-dt@ 10 * gf-clamp01 * + 3 gf!
            4 gf@ gf-mouth-z tk@ over - tk-dt@ 10 * gf-clamp01 * + 4 gf!
          then
        then
      then
    then
    gf-elapsed tk@ .08 <= if gf-elapsed tk@ .08 / else
      gf-strike-duration gf-elapsed tk@ - .18 / then gf-clamp01 gf-gape tk!
    gf-elapsed tk@ gf-strike-duration >= if
      gf-live 1 gf@ 2 gs@ = & 15 gf@ gf-owner tk@ = & if 0 15 gf! then
      -1 0 gs! -1 1 gs! 0 gf-gape tk!
    then
  then
  gf-gape tk@ gf-owner tk@ 1 = if gf-bite-player else gf-bite-resident then tk! ;
: gf-spawn-clear
  1 gf-clear tk! gf-player-mouth
  INDEXOF_X_POS tk-player read-actor-mailbox gf-mouth-x tk!
  INDEXOF_Y_POS tk-player read-actor-mailbox gf-mouth-y tk!
  gf-distance 2.1025 < if 0 gf-clear tk! then
  gf-resident if gf-resident-mouth gf-rx tk@ gf-mouth-x tk! gf-ry tk@ gf-mouth-y tk!
    gf-distance 2.1025 < if 0 gf-clear tk! then then
  2 gf@ gf-spawn-x tk! gf-i tk@ gf-spawn-slot tk!
  3 0 do i gf-i tk! gf-live if
    2 gf@ gf-spawn-x tk@ - dup * 3 gf@ dup * + 4 gf@ 3.65 - dup * + .25 <
    if 0 gf-clear tk! then
  then loop gf-spawn-slot tk@ gf-i tk! ;
: gf-spawn-point
  dup 0 = if drop -1 else dup 1 = if drop -.35 else dup 2 = if drop .8
  else dup 3 = if drop 2.8 else dup 4 = if drop -2.8 else 5 = if -4.2 else 4.2 then then then then then then ;
: gf-release-one
  gf-count tk@ 3 < if
    -1 gf-best tk! 3 0 do i gf-i tk! gf-live not gf-best tk@ 0 < & if i gf-best tk! then loop
    gf-best tk@ gf-i tk!
    0 gf-clear tk! 7 0 do gf-clear tk@ not if
      gf-i tk@ i + 7 mod gf-spawn-point 2 gf! 0 3 gf! 3.65 4 gf! gf-spawn-clear
    then loop
    gf-clear tk@ if
      1 gf@ 1 + gf-old tk! 16 0 do 0 i gf! loop
      1 0 gf! gf-old tk@ 1 gf! gf-spawn-x tk@ 2 gf! 0 3 gf! 3.65 4 gf!
      .15 gf-i tk@ .27 * + 5 gf! -.25 8 gf! gf-i tk@ .29 * 9 gf!
      8 0 do 0 i gm! loop -1 4 gm! -1 5 gm!
      gf-count tk@ 1 + gf-count tk! 1 gf-event
    then
  then ;
\ Feeding retains ownership of reservations/capture; movement only receives requests.
: tk-input
  0 tk-action tk!
  JOYSTICK_BUTTON_RIGHT tk-held JOYSTICK_BUTTON_LEFT tk-held - tk-dx tk!
  JOYSTICK_BUTTON_UP tk-held JOYSTICK_BUTTON_DOWN tk-held -
  tk-mode tk@ if tk-dy tk! 0 tk-dz tk! else tk-dz tk! 0 tk-dy tk! then
  tk-touch if
    JOYSTICK_BUTTON_C tk-edge if tk-toggle then
  else
    JOYSTICK_BUTTON_C tk-held JOYSTICK_BUTTON_B tk-held - dup 0 <> if tk-dy tk! else drop then
  then
  JOYSTICK_BUTTON_A tk-edge if
    JOYSTICK_BUTTON_UP tk-held if tk-toggle else
      tk-neutral tk@ 0 = if
        JOYSTICK_BUTTON_DOWN tk-held if 1 gf-release tk! else 1 gf-eat tk! then
      then
    then
  then
  JOYSTICK_BUTTON_A tk-held JOYSTICK_BUTTON_DOWN tk-held & if 0 tk-dz tk! 0 tk-dy tk! then
  INDEXOF_DELTA_TIME tk@ .2 > if 1 tk-neutral tk! 0 tk-drive tk! 0 tk-dart tk! 0 gf-release tk! 0 gf-eat tk! then
  tk-neutral tk@ if
    0 tk-dx tk! 0 tk-dy tk! 0 tk-dz tk!
    INDEXOF_HARDWARE_JOYSTICK1_RAW tk@ 30727 & 0 = if 0 tk-neutral tk! then
  then
  INDEXOF_HARDWARE_JOYSTICK1_RAW tk@ tk-prev tk!
  tk-dart tk@ tk-dt@ - 0 max tk-dart tk!
  tk-cooldown tk@ tk-dt@ - 0 max tk-cooldown tk! ;

: gf-visible
  gf-distance gf-d tk!
  2 gf@ gf-mouth-x tk@ - gf-mouth-yaw tk@ tk-cos gf-mouth-pitch tk@ tk-cos * *
  3 gf@ gf-mouth-y tk@ - gf-mouth-yaw tk@ tk-sin gf-mouth-pitch tk@ tk-cos * * +
  4 gf@ gf-mouth-z tk@ - gf-mouth-pitch tk@ tk-sin * + gf-dot tk!
  gf-d tk@ gf-sight-range2 <
  gf-dot tk@ -.12 >= gf-d tk@ gf-immediate-range2 < | & gf-clear-ray & ;
: gf-acquire
  gf-resident-mouth -1 gf-best tk! 1000 gf-best-d tk! -1 gf-rlook tk!
  3 0 do i gf-i tk! gf-live 15 gf@ 0 = & if
    gf-visible if
      11 gf@ tk-dt@ gf-observe-time / + 1 min 11 gf!
      gf-d tk@ gf-immediate-range2 < if 1 11 gf! then
      2 gf@ 0 gm! 3 gf@ 1 gm! 4 gf@ 2 gm! 0 3 gm!
      gf-rlook tk@ 0 < if i gf-rlook tk! then
    else
      3 gm@ tk-dt@ + gf-memory-time .1 + min 3 gm!
      11 gf@ tk-dt@ gf-memory-time / - 0 max 11 gf!
    then
    11 gf@ .999 >= if gf-distance dup gf-d tk! gf-best-d tk@ < if
      i gf-best tk! gf-d tk@ gf-best-d tk! then then
  else 0 11 gf! then loop
  gf-target tk@ dup 0 >= if gf-i tk!
    gf-live 15 gf@ 0 = & 3 gm@ gf-memory-time < & if
      gf-best tk@ 0 < gf-distance gf-best-d tk@ 1.4 * <= | if gf-i tk@ gf-best tk! then
    then
  else drop then
  gf-best tk@ gf-target tk! ;
: gf-resident-move
  gf-acquire 0 gf-rstate tk!
  gf-target tk@ 0 >= if
    gf-target tk@ gf-i tk! 0 gm@ gf-a tk! 2 gm@ gf-b tk!
    .70 gf-speed tk! 2 gf-rstate tk!
  else gf-rlook tk@ 0 >= if
    gf-rlook tk@ gf-i tk! 0 gm@ gf-a tk! 2 gm@ gf-b tk!
    .12 gf-speed tk! 1 gf-rstate tk!
  else
    gf-idle-x tk@ gf-rphase tk@ tk-sin .3 * + gf-a tk!
    gf-idle-z tk@ gf-rphase tk@ tk-sin .1 * + gf-b tk!
    .30 gf-speed tk!
  then then
  2 gf-owner tk! 0 gs@ 0 >= if 3 gf-rstate tk! .08 gf-speed tk! then
  gf-a tk@ gf-rx tk@ - gf-dx tk!
  .12 gf-ry tk@ - gf-dy tk!
  INDEXOF_X_POS tk-player read-actor-mailbox gf-rx tk@ - dup *
  INDEXOF_Z_POS tk-player read-actor-mailbox gf-rz tk@ - dup * + 1.2 < if
    INDEXOF_Y_POS tk-player read-actor-mailbox 0 >= if -.45 else .45 then
    gf-ry tk@ - gf-dy tk!
  then
  gf-ryaw tk@ tk-steer tk!
  0 gs@ 0 < if gf-dy tk@ gf-dx tk@ tk-atan2 gf-ryaw tk@ gf-turn gf-ryaw tk! then
  gf-ryaw tk@ tk-steer tk@ - tk-wrap tk-dt@ .001 max / -.04 * -.012 max .012 min
  gf-rroll tk@ gf-ease gf-rroll tk!
  \ Pitch is part of propulsion and the mouth frame, not an independent Z pull.
  gf-b tk@ gf-rz tk@ - gf-dx tk@ abs gf-dy tk@ abs + .001 max tk-atan2
  -.0833333 max .0833333 min gf-rpitch tk@ gf-ease gf-rpitch tk!
  gf-dy tk@ gf-dx tk@ tk-atan2 gf-ryaw tk@ - tk-wrap abs .125 > if
    gf-speed tk@ .18 * gf-speed tk!
  then
  gf-speed tk@ gf-rv tk@ gf-ease gf-rv tk!
  gf-ryaw tk@ tk-cos gf-rpitch tk@ tk-cos * tk-fx tk!
  gf-ryaw tk@ tk-sin gf-rpitch tk@ tk-cos * tk-fy tk!
  gf-rpitch tk@ tk-sin tk-fz tk!
  tk-fx tk@ -4.3 4.3 gf-rx tk@ tk-axis-cap
  tk-fy tk@ -.45 .45 gf-ry tk@ tk-axis-cap min
  tk-fz tk@ 2.05 3.6 gf-rz tk@ tk-axis-cap min gf-rv tk@ min gf-rv tk!
  gf-rx tk@ tk-fx tk@ gf-rv tk@ * tk-dt@ * + gf-rx tk!
  gf-ry tk@ tk-fy tk@ gf-rv tk@ * tk-dt@ * + gf-ry tk!
  gf-rz tk@ tk-fz tk@ gf-rv tk@ * tk-dt@ * + gf-rz tk!
  gf-rphase tk@ tk-dt@ gf-rv tk@ 1.2 * .35 + * + tk-frac gf-rphase tk!
  gf-autoeat gf-target tk@ 0 >= & 0 gs@ 0 < & if
    gf-resident-mouth gf-target tk@ gf-i tk! gf-live if gf-edible if gf-strike-start then then
  then
  gf-strike-tick
  gf-rx tk@ tk-x tk! gf-ry tk@ tk-y tk! gf-rz tk@ tk-z tk!
  gf-rv tk@ .70 / 1 min tk-pose-drive tk!
  gf-rpitch tk@ tk-pose-pitch tk! gf-rroll tk@ tk-pose-roll tk!
  gf-ryaw tk@ tk-yaw tk! .75 tk-scale tk! gf-rphase tk@ tk-phase tk!
  gf-bite-resident tk@ gf-bite tk! tk-pose ;
\ Threat requires a visible silhouette and measured closing motion, not button state.
: gf-threat-one
  gf-distance gf-d tk!
  gf-d tk@ gf-last-d tk@ gm!  \ preserve actual previous-distance samples
  gf-old tk@ 0 >= if
    gf-old tk@ gf-d tk@ - tk-dt@ .0001 max / 0 max gf-close tk!
    gf-d tk@ 2.25 <
    gf-mouth-x tk@ 2 gf@ - 5 gf@ tk-cos *
    gf-mouth-y tk@ 3 gf@ - 5 gf@ tk-sin * + -.20 >= & gf-clear-ray & if
      gf-close tk@ .25 > if
        1 12 gf! gf-mouth-x tk@ 6 gm! gf-mouth-z tk@ 7 gm!
        gf-close tk@ 1.2 > gf-d tk@ .64 < & 14 gf@ 0 <= & if
          .22 13 gf! 1.2 14 gf!
        then
      then
    then
  then ;
: gf-threats
  12 gf@ tk-dt@ .8 * - 0 max 12 gf!
  13 gf@ tk-dt@ - 0 max 13 gf! 14 gf@ tk-dt@ - 0 max 14 gf!
  gf-player-mouth 4 gf-last-d tk! 4 gm@ gf-old tk! gf-threat-one
  gf-resident if gf-resident-mouth 5 gf-last-d tk! 5 gm@ gf-old tk! gf-threat-one then ;
: gf-swim
  10 gf@ tk-dt@ + 1 min 10 gf!
  gf-threats
  12 gf@ .1 > if
    0 2 gf@ 6 gm@ - tk-atan2 gf-want tk! .55 gf-speed tk!
    13 gf@ 0 > if 1.30 gf-speed tk! then
  else 9 gf@ tk-sin .08 * 5 gf@ + tk-wrap gf-want tk! .35 gf-speed tk! then
  2 gf@ 4.35 > if .5 gf-want tk! then
  2 gf@ -4.35 < if 0 gf-want tk! then
  gf-want tk@ 5 gf@ gf-turn 5 gf!
  5 gf@ tk-cos gf-speed tk@ * 6 gf@ gf-ease 6 gf!
  0 7 gf@ gf-ease 7 gf!
  10 gf@ .6 < if -.35 else 12 gf@ .1 > if
    4 gf@ 7 gm@ - -.3 max .3 min
  else 9 gf@ tk-sin .06 * then then 8 gf@ gf-ease 8 gf!
  2 gf@ 6 gf@ tk-dt@ * + -4.65 max 4.65 min 2 gf!
  3 gf@ 7 gf@ tk-dt@ * + -.25 max .25 min 3 gf!
  4 gf@ 8 gf@ tk-dt@ * + 1.85 max 3.75 min 4 gf!
  9 gf@ tk-dt@ gf-speed tk@ 3 * 2 + * + tk-frac 9 gf!
  \ Bend, then reverse stroke, within the existing single-mesh deformation path.
  13 gf@ 0 > if
    13 gf@ .11 > if .25 else -.25 then gf-threat tk! .12 gf-gape tk!
  else 9 gf@ gf-threat tk! gf-speed tk@ .02 * .025 + gf-gape tk! then
  gf-threat tk@ gf-gape tk@ gf-actor fish-deform ;
: gf-pose
  2 gf@ INDEXOF_X_POS gf-actor write-actor-mailbox
  3 gf@ INDEXOF_Y_POS gf-actor write-actor-mailbox
  4 gf@ INDEXOF_Z_POS gf-actor write-actor-mailbox
  0 INDEXOF_ROTATION_A gf-actor write-actor-mailbox
  8 gf@ negate .12 * INDEXOF_ROTATION_B gf-actor write-actor-mailbox
  5 gf@ INDEXOF_ROTATION_C gf-actor write-actor-mailbox ;
: gf-setup
  -1 gf-target tk! 0 gf-count tk! 0 gf-release tk! 0 gf-eat tk!
  0 gf-consumed-player tk! 0 gf-consumed-resident tk!
  0 gf-bite-player tk! 0 gf-bite-resident tk!
  3 0 do i gf-i tk! 16 0 do 0 i gf! loop 8 0 do 0 i gm! loop -1 4 gm! -1 5 gm! loop
  2 0 do i 1 + gf-owner tk! 16 0 do 0 i gs! loop -1 0 gs! -1 1 gs! loop
  gf-resident if
    800 tk@ gf-rx tk! 801 tk@ gf-ry tk! 802 tk@ gf-rz tk!
    809 tk@ gf-ryaw tk! .1 gf-rv tk! 807 tk@ gf-rphase tk!
    800 tk@ gf-idle-x tk! 802 tk@ gf-idle-z tk!
  then
  0 gf-rstate tk! -1 gf-rlook tk!
  gf-initial 0 > if gf-initial 0 do gf-release-one loop then ;
: gf-tick
  4 profile-begin
  gf-release tk@ if gf-release-one 0 gf-release tk! then
  gf-eat tk@ if gf-player-eat 0 gf-eat tk! then
  3 0 do i gf-i tk! gf-live if gf-swim then loop
  \ Start the player strike first; reservations prevent duplicate resident claims.
  1 gf-owner tk! gf-strike-tick
  gf-resident if gf-resident-move then
  3 0 do i gf-i tk! gf-live if gf-pose then loop
  4 profile-end ;
