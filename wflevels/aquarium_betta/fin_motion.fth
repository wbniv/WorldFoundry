\ Fin roots use UV weight zero; native motion bends free edges from cached rest poses.
\ Game tuning, not measured biological frequencies. Independent bounded clocks.
: bf-motion
  5 profile-begin
  tk-vx tk@ abs tk-vy tk@ abs + tk-vz tk@ abs + tk-speed / 1 min
  bf-drive tk@ - tk-dt@ 4 * 1 min * bf-drive tk@ + bf-drive tk!
  tk-yaw tk@ bf-last-yaw tk@ - tk-wrap tk-dt@ .001 max / -.65 max .65 min
  bf-turn tk@ - tk-dt@ 6 * 1 min * bf-turn tk@ + bf-turn tk!
  tk-yaw tk@ bf-last-yaw tk!
  bf-swim-phase tk@ tk-dt@ .55 bf-drive tk@ 1.4 * + * + tk-frac bf-swim-phase tk!
  bf-pect-phase tk@ tk-dt@ 1.8 bf-drive tk@ .8 * + * + tk-frac bf-pect-phase tk!
  bf-drive tk@ .075 * bf-sweep tk@ - tk-dt@ 3 * 1 min * bf-sweep tk@ + bf-sweep tk!
  bf-spread tk@ 0 <= if .72 bf-spread tk! then
  .72 bf-drive tk@ .12 * - bf-turn tk@ abs .30 * +
  tk-dart tk@ 0 > if drop 1.03 then
  bf-spread tk@ - tk-dt@ 4 * 1 min * bf-spread tk@ + bf-spread tk!
  5 profile-end ;
: bf-fins
  bf-swim-phase tk@ .065 bf-drive tk@ .040 * + bf-sweep tk@ bf-spread tk@ 651 tk@ fin-deform
  bf-swim-phase tk@ .18 + .035 bf-drive tk@ .025 * + bf-sweep tk@ .20 * bf-spread tk@ .85 * .15 + 652 tk@ fin-deform
  bf-swim-phase tk@ .39 + .040 bf-drive tk@ .032 * + bf-sweep tk@ .35 * bf-spread tk@ .75 * .25 + 653 tk@ fin-deform
  bf-pect-phase tk@ .028 bf-turn tk@ .024 * + bf-sweep tk@ .3 * .85 654 tk@ fin-deform
  bf-pect-phase tk@ .5 + .028 bf-turn tk@ .024 * - bf-sweep tk@ .3 * .85 655 tk@ fin-deform
  bf-swim-phase tk@ .29 + .038 bf-drive tk@ .030 * + bf-sweep tk@ .6 * 1 656 tk@ fin-deform
  bf-swim-phase tk@ .56 + .038 bf-drive tk@ .030 * + bf-sweep tk@ .6 * 1 657 tk@ fin-deform ;
