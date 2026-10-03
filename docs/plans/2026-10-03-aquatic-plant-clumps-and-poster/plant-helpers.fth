: tip-weight ( height-fraction -- weight ) 0 max 1 min dup * ;
: cluster-j ( uniform-a uniform-b -- centred-offset ) + 1 - ;
: fork-angle ( heading signed-side -- daughter-heading ) .08 * + ;
: leaf-turn ( leaf-index leaf-count -- turns ) / ;
: ease ( current target dt -- next )
  0 max .8 * 1 min >r over - r> * + ;
