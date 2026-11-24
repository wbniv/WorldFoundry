# Engine object, allocation and resource lifetime diagnostics

## Authorization and purpose

Will requested this plan and implementation, explicitly including engine changes.
Use both engine ownership diagnostics and host ASan/UBSan/LeakSanitizer. The
Planted PSS graphs show process accounting variation, not proof that constructors,
destructors or external resources balance. Keep the recorded soak verdicts.

## Contract

An opt-in `WF_LIFETIME_DIAGNOSTICS` build assigns each level load a monotonically
increasing 32-bit generation (fail on exhaustion, never wrap). Diagnostic tokens
must not increase the engine arenas' 4-byte ARM32 alignment. Track live objects (Actor, ScriptInterpreter, RenderActor and PixelMap), WF pool allocations, C++ heap allocations made in a tracked ownership
scope, and modern-renderer texture/static-mesh resources. Record type/category,
identity, bytes where meaningful, generation and creation file/line or heap caller.
Never use a matching count alone: distinct surviving identities must be reported.

Check arena contents **before** releasing/resetting their backing memory. A lost
object destructor remains an error even if releasing the arena returns its bytes.
LMalloc asset/scratch arenas explicitly allow bulk release of raw blocks; live
object tokens inside them still fail. DMalloc remains strict about outstanding
allocations. After level teardown, report outstanding level-owned records. An error fails the
diagnostic run independently of assertion/Release settings. Preserve original
failure evidence when arena records must be retired to avoid stale addresses.
Persistent resources have an explicit process owner, appear separately in reports,
and must be released at their own shutdown boundary. Do not silently classify all
first-cycle allocations as a cache or move survivors into the next generation.

The tracker must not allocate through its own intercepted C++ heap, deadlock on
reentry, or mistake identical GPU names in different backends for one resource.
Constructor unwinding, address reuse, cross-thread release, duplicate registration,
unknown destruction and context loss need deliberate handling. Tracking metadata
allocation failure is a diagnostic failure, never a silent loss of coverage.

## Implementation sequence

1. Add standalone ownership registry, object tokens and persistent/level scopes,
   structured stderr reports, and a CMake gate (off by default).
2. Connect real level load/unload, actor/interpreter destruction and arena
   allocate/free/reset/destruction. Check objects before arena storage vanishes.
3. Track C++ new/delete (including arrays/aligned/nothrow forms), plant/render
   allocations and modern-renderer resource creation/deletion/context loss. Identify
   intentional persistent caches explicitly and check their release separately.
4. Run registry and real allocator fault tests: missing destructor, missing free,
   missing graphics release, reused identities, explicit persistent ownership,
   constructor failure and metadata consistency. Run repeated real level cycles.
5. Run host sanitizer builds through repeated level load/unload and clean process
   shutdown with leak detection enabled. Record commands/results and limits here.

## Validation and limits

The independent tests intentionally leak tracked objects/resources and must report
failures before arena reclamation. A balanced cycle and clean persistent shutdown
must pass. Integration must execute the engine lifecycle, not only a mock registry.
Use the existing container workflow; save diagnostic output under docs/diagnostics/.
Run sanitizers in a **separate build with lifetime tracking disabled**: the
registry stores live allocation addresses and could otherwise make a real leak
appear reachable to LSan. ASan/LSan catch heap paths the ownership registry cannot see, especially direct C
malloc/free inside third-party libraries. They do not establish GPU-driver release;
engine graphics handles cover the instrumented backend APIs. GPU byte figures are
requested payload sizes, not a measurement of driver residency. Worker allocations
need an explicit ownership scope; unscoped allocations are not called leak-free.
GL entry points run in an external-driver ownership scope: Mesa/LLVM's internal
C++ caches are not engine-level allocations. GPU handle creation/deletion is
tracked on either side of that boundary. PixelMap records texture ownership at
construction, so delayed uploads do not transfer a game-owned atlas to a level.
Linux and Android GL are the initial diagnostic targets; CMake rejects enabling
this mode on the other backends rather than implying that their resources are
covered. Production mode keeps its allocator; no scene-format change or new PSS
threshold. The existing static-mesh C scratch cache gains an explicit shutdown
release instead of relying on OS reclamation.

## Status

Implemented and host-validated on 2026-11-13. The tracker and the independent
ASan/UBSan/LSan build each passed five load/frame/unload cycles of Qbert and the
planted tank, followed by clean process shutdown. The tracker reported zero
level survivors on all ten cycles and zero persistent survivors at shutdown.
Eight deliberate registry failures and two real pool faults were detected;
separate sanitizer fixtures detected a C malloc leak and use-after-free.
The debug listener restart and FPS overlay regressions also passed.

Integration exposed a real teardown omission: dynamic actors' NonStatPlatData
was arena-reclaimed without destruction. Actor teardown now destroys it and its
owned input device (which already owns its input script). Jolt handles have
logical resource records; character destruction releases its listener and stale
actor references. Worker completion is signalled after worker-local destruction.
Known persistent caches retain explicit owners and release at shutdown.

Validation used a committed-source snapshot plus these changes because unrelated
unfinished rendering changes in the shared worktree do not compile. The tested
configuration is Linux Debug, Jolt and zforth, with other script engines disabled.
Android NDK 26.2 ARM32 and ARM64 syntax checks passed for the tracker, heap
interposition and GLES shim, including the arena-alignment assertion. Android
runtime acceptance and other script/backend combinations have not been tested.
This completes the host implementation; it does not change the historical PSS
soak verdict or prove universal constructor coverage.

Commands, curated output and binary identities are in the
[validation record](../diagnostics/engine-lifetime-2026-11-13/README.md).
