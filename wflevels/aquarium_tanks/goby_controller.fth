\ Rainbow goby: short swims, controlled lift, settle, pelvic-disc perch/graze.
\ Authored bindings supply gb-floor (surface height at the current X), gb-ceiling
\ and gb-limit. Input booleans gb-left/right/up/down are supplied by the caller.
\ gb-blocked is set for modal/focus transitions; held input must be released.
\ Scratch/state 1140..1159 does not overlap urchin contacts or spines.
: gb@ read-mailbox ; : gb! write-mailbox ;
: gb-left 1140 ; : gb-right 1141 ; : gb-up 1142 ; : gb-down 1143 ;
: gb-blocked 1144 ; : gb-neutral 1145 ; : gb-state 1146 ;
: gb-vx 1147 ; : gb-vz 1148 ; : gb-dt 1149 ; : gb-dx 1150 ;
: gb-dz 1151 ; : gb-age 1152 ; : gb-heading 1153 ; : gb-target 1154 ;
: gb-step-time
  INDEXOF_DELTA_TIME gb@ dup .2 > if drop 0 1 gb-neutral gb!
  else 0 max .05 min then gb-dt gb! ;
: gb-stop 0 gb-vx gb! 0 gb-vz gb!
  0 INDEXOF_XSPEED gb! 0 INDEXOF_YSPEED gb! 0 INDEXOF_ZSPEED gb! ;
: gb-reset 1 gb-neutral gb! 0 gb-state gb! 0 gb-age gb! gb-stop ;
: gb-ease >r r@ gb@ - gb-dt gb@ 7 * 1 min * r@ gb@ + r> gb! ;
: gb-facing
  gb-dx gb@ 0 <> if gb-dx gb@ 0 < if .5 else 0 then gb-target gb! then
  gb-target gb@ gb-heading gb@ - dup .5 > if 1 - then
  dup -.5 < if 1 + then gb-dt gb@ negate max gb-dt gb@ min
  gb-heading gb@ + dup 0 < if 1 + then dup 1 >= if 1 - then gb-heading gb! ;
: gb-move
  gb-right gb@ gb-left gb@ - gb-dx gb!
  gb-up gb@ gb-down gb@ - gb-dz gb!
  gb-neutral gb@ if
    gb-left gb@ gb-right gb@ + gb-up gb@ + gb-down gb@ + 0 =
    if 0 gb-neutral gb! then
    0 gb-dx gb! 0 gb-dz gb! then
  gb-dx gb@ abs gb-dz gb@ abs + 0 > if 1 gb-state gb! 0 gb-age gb! then
  gb-dx gb@ .55 * gb-vx gb-ease
  gb-dz gb@ 0 > if .42 else
    gb-dz gb@ 0 < if -.45 else
      gb-state gb@ 0 <> if -.16 else 0 then then then gb-vz gb-ease
  \ At a perch, a lateral swim lifts clear before travelling sideways.
  INDEXOF_Z_POS gb@ gb-floor .025 + <= gb-dx gb@ 0 <> &
  gb-dz gb@ 0 >= & if .24 gb-vz gb! then
  gb-facing
  INDEXOF_X_POS gb@ gb-limit negate max gb-limit min INDEXOF_X_POS gb!
  INDEXOF_Z_POS gb@ gb-floor max gb-ceiling min INDEXOF_Z_POS gb!
  INDEXOF_X_POS gb@ abs gb-limit .001 - >=
  INDEXOF_X_POS gb@ gb-vx gb@ * 0 > & if 0 gb-vx gb! then
  INDEXOF_Z_POS gb@ gb-ceiling .001 - >= gb-vz gb@ 0 > & if 0 gb-vz gb! then
  INDEXOF_Z_POS gb@ gb-floor .003 + <= gb-vz gb@ 0 <= &
  gb-dx gb@ 0 = & gb-up gb@ 0 = & if
    0 gb-vx gb! 0 gb-vz gb!
    gb-state gb@ 1 = if 2 gb-state gb! 0 gb-age gb! then
    gb-age gb@ gb-dt gb@ + 1.2 min gb-age gb!
    gb-age gb@ .35 >= if 3 gb-state gb! then then
  gb-vx gb@ INDEXOF_XSPEED gb!
  0 INDEXOF_YSPEED gb!
  gb-vz gb@ INDEXOF_ZSPEED gb! ;
: gb-player-tick
  0 INDEXOF_INPUT gb! gb-step-time
  gb-blocked gb@ if gb-reset else
    gb-dt gb@ 0 = if gb-stop else gb-move then then ;
