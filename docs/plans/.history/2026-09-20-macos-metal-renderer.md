| Date | Change |
|------|--------|
| [2026-09-20](https://github.com/wbniv/WorldFoundry/commit/72f650bd) | docs(plans): scope the macOS Metal renderer port |

<!--history-meta v1
72f650bd	author	Will Norris
72f650bd	added	284
72f650bd	deleted	0
72f650bd	files	1
72f650bd	body	Research + plan only; no code changes.\n\nThe 2026-05-26 investigation assumed macOS could "select the Metal backend\nfor a 4th platform arm" because iOS Metal would be proven first. Tracing the\ncode says otherwise: SetCurrentEncoder/ClearCurrentEncoder in\nhal/ios/backend_metal.mm:342,347 have zero callers, both Apple arms compile\nengine/stubs/renderpoly3d_stubs.cc instead of the real RenderPoly3D methods,\ntextures are disabled (backend_metal.mm:466) and there is no depth attachment\nanywhere. iOS Metal has never drawn a triangle.\n\nThe counterweight: gfx/glpipeline/rend{f,g}{c,t}{l,p}.cc are already\nbackend-agnostic — they include only renderer_backend.hp and end in\nDrawTriangle (rendfcl.cc:13-22,57-63). The CMake comment calling them\n"GL-only" predates the RendererBackend seam. So the remaining Metal work is\nan encoder handoff, a depth attachment, a texture path and a window — three\nof four shared with iOS, and macOS is the better bench for all three\n(Ninja, --frame-step-smoke, engine on the main thread, no simulator).\n\nAlso corrects the TODO item's stale tail: Jolt and the full scripting roster\nare already enabled on macOS since 04061deb; only WAMR remains off.\n\nOpen decisions left for review rather than guessed: CI budget strategy\n(folded into the existing 2026-05-12-codemagic-budget-monitor position),\neditor-vs-runtime scope, texture seam widening vs sidecar, GLFW vs AppKit\nwindow host, and whether iOS gets fixed in this work or after.\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_015ksFy3ZSSz2XMdto3jVA9v
-->
