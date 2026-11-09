| Date | Change |
|------|--------|
| [2026-06-13](https://github.com/wbniv/WorldFoundry/commit/3031c87f) | docs(wf-edit/web): document the browser build + finalize plan as completed record |
| [2026-06-12](https://github.com/wbniv/WorldFoundry/commit/7223ff91) | fix(filesys): base-pivot templates; promote base-pivot to a WF convention |
| [2026-05-16](https://github.com/wbniv/WorldFoundry/commit/987e80fe) | feat(smb): add SMB W1-1 initial level port + fix window X-button close |
| [2026-04-30](https://github.com/wbniv/WorldFoundry/commit/b10d115f) | chore: baseline standardization — hooks, CLAUDE.md, migrate prompts/ |

<!--history-meta v1
3031c87f	author	Will Norris
3031c87f	added	4
3031c87f	deleted	0
3031c87f	files	1
3031c87f	body	- wf-edit-manual.md: new "Running in the browser (WASM/WebGL2)" section (toolchain\n  setup, build/serve tasks, query-string options, join-and-receive co-edit, web Save\n  semantics, headless CDP verification + the simultaneous-seed-race caveat); add a\n  browser row to the v1-scope table; amend the "Linux/X11 only" platform notes; add\n  WF_EDIT_AUTO_SELECT / WF_EDIT_CHAT_SEND to the headless-hooks table; link the plan.\n- 2026-06-12-wf-edit-in-the-browser.md: add an "Outcome (2026-06-13)" summary near the\n  top with the per-phase commit trail and open follow-ups.\n- CLAUDE.md: add build-wf-edit / build-wf-edit-fast / build-web-edit / serve-web-edit\n  to Key Commands.\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
7223ff91	author	Will Norris
7223ff91	added	1
7223ff91	deleted	0
7223ff91	files	1
7223ff91	body	FSN towers/boxes sank through the floor: templates were centered on their\nlocal origin (Z ∈ [-1,+1]), and the scale mailboxes column-multiply about the\norigin (rendacto.cc:481-483), so each scaled box grew symmetrically — half\nbelow z=0. Re-author DirTemplate to local Z [0,2] and FileTemplate to [0,0.5]\n(base at the origin) so scale grows them upward from the floor.\n\nThis is the third time the same sinking bug has been fixed (Mario 2026-05-17,\nqbert Slick/Sam 2026-05-22, now filesys), so promote it from a physics-only\nfootnote to a general authoring rule:\n\n- docs/level-building.md: new "Mesh origin — base (lowest vertex) at local z=0"\n  section under Authoring conventions, with BOTH rationales (placement +\n  scale-about-origin); re-scope the physics-mobility rule #1 to reference it.\n- docs/level-design-troubleshooting.md: add the scale-pivot gotcha to the\n  X/Y/Z_SCALE mailbox note.\n- CLAUDE.md: one-line standard under Conventions.\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
987e80fe	author	Will Norris
987e80fe	added	48
987e80fe	deleted	0
987e80fe	files	1
987e80fe	body	SMB W1-1: player Euler C=π/2 (not 0) so joystick RIGHT maps to +X (screen-right)\ninstead of -Y (toward camera); full movement and jump working. Includes Blender\nscript, compiled .lev/.lvl/.iff, and coordinate-system investigation doc.\n\nWindow close: clicking the title-bar X now closes the game immediately. Two bugs\nfixed: (1) RunGameScript's for(;;) outer loop never checked HALWindowCloseRequested()\nand restarted the level on exit; (2) no XDestroyWindow/XCloseDisplay was ever called\nso the window lingered until OS reclaimed the connection. Added HALCloseWindow() to\nmesa.cc, called from main.cc after RunGameScript() returns, with Display::~Display()\nguarded to skip PageFlip on an already-destroyed window. Android gets a no-op stub.\n\nAlso: coordinate system section in CLAUDE.md, troubleshooting guide entry for player\norientation, investigation doc with mermaid diagrams, mermaid support in md-to-pdf.sh.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
b10d115f	author	Will Norris
b10d115f	added	33
b10d115f	deleted	0
b10d115f	files	1
b10d115f	body	Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
-->
