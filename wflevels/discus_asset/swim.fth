\ Discus idle swim: model faces +X, tail is -X. Review scene is scaled x10.
\ Existing swim-deform acts on the common body/tail span in local coordinates.
\ The zero fin-wave amplitude is intentional: this mesh's UVs are photographic,
\ not root-to-tip fin weights. A single body wave keeps fins attached.
: discus-swim
  INDEXOF_TIME read-mailbox .8 * .085 0 0 0 -1.07 .6
  INDEXOF_ACTOR_INDEX read-mailbox swim-deform ;
discus-swim
