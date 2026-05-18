// engine/wf_host_gl_test/mesa_stub.cc — minimal mesa.cc replacement so the
// host GL context smoke test can link without pulling in the whole engine
// (no Display, no WFGame, no main() collision against game/main.cc).
//
// Provides exactly the two symbols the registry side needs:
//   _closeRequested (atomic int) — defined here, set by HALRequestClose in
//                                  gfx/gl/host_gl_context.cc.
//   HALWindowCloseRequested      — reads the atomic.
//
// The real mesa.cc also defines HALCloseWindow, XEventLoop, OpenMainWindow,
// InitWindow, InitWithExistingContext etc. — none of which the smoke test
// exercises, so stubbing them out (or omitting them) is fine.

#include <atomic>

std::atomic<int> _closeRequested{0};

extern "C" int HALWindowCloseRequested(void)
{
    return _closeRequested.load();
}
