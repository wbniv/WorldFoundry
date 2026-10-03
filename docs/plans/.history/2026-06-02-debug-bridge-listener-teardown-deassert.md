| Date | Change |
|------|--------|
| [2026-06-02](https://github.com/wbniv/WorldFoundry/commit/15801ebc) | fix(debug-bridge): detach listener threads so asserts arent terminate-masked |

<!--history-meta v1
15801ebc	author	Will Norris
15801ebc	added	93
15801ebc	deleted	0
15801ebc	files	1
15801ebc	body	An engine AssertMsg -> _sys_assert -> exit(-1) runs C++ static destructors\nbefore the sys_atexit Stop handlers join -- destroying a still-joinable static\nstd::thread calls std::terminate(), tacking "terminate called without an active\nexception" + SIGABRT onto every assert and burying the real cause.\n\nBoth offenders detached (the only static std::thread/.join() in wf_game-dev):\ndebug_server.cc gListenerThread and rest_api.cc gServerThread (which even\ncommented the hazard but used an unreliable atexit-join). RestApi_Stop now leaks\ngServer instead of delete+join, since the detached thread may still be unwinding\nlisten().\n\nVerified (tests/test_assert_no_terminate_mask.py): the out-of-range-mailbox\ntrigger goes from exit -6 + "terminate called" (masked) to clean exit 255 with\nthe ASSERTION FAILED box as the legible last output.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
-->
