| Date | Change |
|------|--------|
| [2026-09-20](https://github.com/wbniv/WorldFoundry/commit/ce9bf2d9) | docs(plans): record Phase 0 verification for the macOS Metal renderer |
| [2026-09-20](https://github.com/wbniv/WorldFoundry/commit/72f650bd) | docs(plans): scope the macOS Metal renderer port |

<!--history-meta v1
ce9bf2d9	author	Will Norris
ce9bf2d9	added	100
ce9bf2d9	deleted	5
ce9bf2d9	files	1
ce9bf2d9	body	Local steps 1-4 of the plan's §8 pass and carry their raw output. Two of\nthem cite paths that do not exist — build_game.sh (the build is\n`task build`) and build/wf_game (the binary is engine/wf_game, run from\nwfsource/source/game with an absolute -L). Both are recorded as written,\nwith the failure output, then re-run corrected, per the plan-verification\nformat; the steps themselves are left verbatim for a later fix.\n\nCodemagic steps 5-6 are BLOCKED, not failed: no WorldFoundry Codemagic\nAPI token is reachable from this machine (nothing in ~/.config/codemagic,\nno CODEMAGIC_API_TOKEN, no such SSM parameter under any configured AWS\nprofile), and gustos-colores' token must not be borrowed across projects.\nMinting it is the one irreducible manual step. So Phase 0's exit\ncriterion is not met and Phase 1 must not start.\n\nWhat could be checked off-Mac is checked: the WF_HAS_X11 truth table is\npreprocessed per platform, and no other file in the macOS source set\npulls an X11 or desktop-GL header.\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_015ksFy3ZSSz2XMdto3jVA9v
72f650bd	author	Will Norris
72f650bd	added	284
72f650bd	deleted	0
72f650bd	files	1
72f650bd	body	Research + plan only; no code changes.\n\nThe 2026-05-26 investigation assumed macOS could "select the Metal backend\nfor a 4th platform arm" because iOS Metal would be proven first. Tracing the\ncode says otherwise: SetCurrentEncoder/ClearCurrentEncoder in\nhal/ios/backend_metal.mm:342,347 have zero callers, both Apple arms compile\nengine/stubs/renderpoly3d_stubs.cc instead of the real RenderPoly3D methods,\ntextures are disabled (backend_metal.mm:466) and there is no depth attachment\nanywhere. iOS Metal has never drawn a triangle.\n\nThe counterweight: gfx/glpipeline/rend{f,g}{c,t}{l,p}.cc are already\nbackend-agnostic — they include only renderer_backend.hp and end in\nDrawTriangle (rendfcl.cc:13-22,57-63). The CMake comment calling them\n"GL-only" predates the RendererBackend seam. So the remaining Metal work is\nan encoder handoff, a depth attachment, a texture path and a window — three\nof four shared with iOS, and macOS is the better bench for all three\n(Ninja, --frame-step-smoke, engine on the main thread, no simulator).\n\nAlso corrects the TODO item's stale tail: Jolt and the full scripting roster\nare already enabled on macOS since 04061deb; only WAMR remains off.\n\nOpen decisions left for review rather than guessed: CI budget strategy\n(folded into the existing 2026-05-12-codemagic-budget-monitor position),\neditor-vs-runtime scope, texture seam widening vs sidecar, GLFW vs AppKit\nwindow host, and whether iOS gets fixed in this work or after.\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_015ksFy3ZSSz2XMdto3jVA9v
-->
