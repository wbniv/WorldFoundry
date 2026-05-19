// engine/mutation/wfmut_smoke.hpp
//
// Embedded smoke runner for the wfmut:: engine mutation API. Driven by
// wf_game's --wfmut-smoke=<level.iff> CLI flag through WFGame::RunWfmutSmoke().
//
// Test cases mirror the matrix in docs/plans/2026-05-19-engine-mutation-api.md.
//
// Editor-stack only — gated by WF_ENABLE_EDITOR. The header provides a no-op
// stub when the flag is off so the WFGame call site compiles cleanly.

#pragma once

class Level;

#ifdef WF_ENABLE_EDITOR

namespace wfmut {

// Run all currently-implemented smoke tests against the given live Level.
// Returns the number of failed assertions (0 = all green).
//
// Each step's commit grows the test set: step 2 adds Transform (T1–T11
// subset), step 3 adds Fields, step 4 adds Spawn/Remove, step 5 adds Mailbox.
int RunSmokeTests(Level& level);

} // namespace wfmut

#else // !WF_ENABLE_EDITOR

namespace wfmut {

inline int RunSmokeTests(Level&) { return 0; }

} // namespace wfmut

#endif // WF_ENABLE_EDITOR
