\ wf
\ shell-menu.fth: the shell of level-menu bundles (task build-cd-iff-smb-menu). Same as shell.fth,
\ except that the first pass writes -1 ("ask the player") instead of level 0: the engine
\ (game.cc, level_menu.cc) then shows the bundle's MENU chunk and writes the chosen level.
\ Plan: docs/plans/2026-10-01-level-menu-selector.md
6000 read-mailbox 0 =
if  1 6000 write-mailbox
    -1 INDEXOF_LEVEL_TO_RUN write-mailbox
then
