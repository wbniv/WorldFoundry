| Date | Change |
|------|--------|
| [2026-09-20](https://github.com/wbniv/WorldFoundry/commit/aa1b7072) | feat(macos): disable REST API, stub debug-bridge GL calls for macOS |

<!--history-meta v1
aa1b7072	author	Will Norris
aa1b7072	added	119
aa1b7072	deleted	0
aa1b7072	files	1
aa1b7072	body	REST_API and DEBUG_BRIDGE survived the Forth-only scripting trim, and\nthe next Codemagic build (286/289 files) hit two more real macOS\nbreaks in that surviving code:\n\n- engine/stubs/rest_api.cc: unconditional #include <GL/gl.h> (Linux\n  path, doesn't exist on macOS) backing real immediate-mode GL debug\n  wireframe calls (glBegin/glVertex3f/glEnd/...) not covered by\n  hal/macos/gl_stubs.cc's existing 6 stubs.\n- engine/stubs/debug_server.cc: same header problem (its __ANDROID__/\n  else branch lumped macOS in with Linux), backing glGetIntegerv/\n  glPixelStorei/glReadPixels for the screenshot op -- also unstubbed.\n\nWill's call: disable WF_REST_API on macOS outright (explicitly a PoC\nper its own header comment, already off on every mobile platform, no\nwindow/render context to draw into today regardless). Keep the debug\nbridge -- the feature 04061deb deliberately turned on for macOS -- by\nadding the 3 missing no-op GL stubs, same pattern as pixelmap.cc's\nexisting 6: glGetIntegerv is a true no-op, which correctly falls\nthrough to debug_server.cc's own existing "viewport not initialised"\ngraceful-failure path rather than needing special-casing here.\n\nAlso fixes debug_server.cc's GL header include to branch on\nWF_TARGET_MACOS (matching the established convention in\ngfx/renderer.hp and hal/macos/gl_stubs.cc) instead of lumping macOS\ninto the Linux #else arm.\n\nDocumented as docs/plans/2026-09-20-macos-phase0-green-baseline.md,\nconsolidating everything found live-debugging Phase 0 of\n2026-09-20-macos-metal-renderer.md against real Codemagic runs.\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_015ksFy3ZSSz2XMdto3jVA9v
-->
