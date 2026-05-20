// engine/mutation/wfmut_smoke.hpp
//
// Embedded smoke runner for the wfmut:: engine mutation API. Driven by
// wf_game's --wfmut-smoke=<level.iff> CLI flag through WFGame::RunWfmutSmoke().
//
// Test cases mirror the matrix in docs/plans/2026-05-19-engine-mutation-api.md.
//
// Same gate as wfmut: UNION of WF_DEBUG_BRIDGE and WF_ENABLE_EDITOR. The
// smoke is a CLI tool useful to both designers (verify the bridge wires up
// wfmut correctly) and editor devs (verify the CRDT bridge path).

#pragma once

class Level;

#if defined(WF_DEBUG_BRIDGE) || defined(WF_ENABLE_EDITOR)

namespace wfmut {

// Run all currently-implemented smoke tests against the given live Level.
// Returns the number of failed assertions (0 = all green).
//
// Each step's commit grows the test set: step 2 adds Transform (T1–T11
// subset), step 3 adds Fields, step 4 adds Spawn/Remove, step 5 adds Mailbox.
int RunSmokeTests(Level& level);

// X5 cross-thread guard death-test: calls wfmut from a non-game thread and
// expects the guard's AssertMsg to abort. Driven by --wfmut-thread-test.
int RunThreadGuardDeathTest(Level& level);

} // namespace wfmut

#else // neither WF_DEBUG_BRIDGE nor WF_ENABLE_EDITOR — lean builds.

namespace wfmut {

inline int RunSmokeTests(Level&) { return 0; }

} // namespace wfmut

#endif // WF_DEBUG_BRIDGE || WF_ENABLE_EDITOR
