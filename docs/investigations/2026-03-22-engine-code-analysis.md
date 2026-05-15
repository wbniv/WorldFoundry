# WorldFoundry Engine: Code Analysis & Opinions

**Date:** 2026-03-22
**Repo analyzed:** https://github.com/WorldFoundry/WorldFoundry/tree/master/wfsource
**Stats:** ~1,117 files, ~750 C/C++ source files, developed 1994–2003, GPL v2
**Status:** Complete

External code analysis and editorial opinions on the original WorldFoundry engine source. Covers architecture, subsystems, coding standards, and a frank assessment of what holds up and what doesn't.

---

## Architecture Overview

The engine is organized as a hierarchy of 23 loosely-coupled libraries across three groups:

**Platform:** hal (Hardware Abstraction), gfx (PSX/GL/DirectX/Software), input, audio

**Foundation:** pigsys (OS abstraction), cpplib (C++ utilities), memory (LMalloc/MemPool/DMalloc), streams (binary I/O), math (Scalar, Vector3, Matrix34)

**Game Systems:** iff (chunked binary format), asset (room-based streaming), physics (collision + movement), baseobject (game entities), room (spatial partitioning), movement (state machine handlers), scripting (Tcl interpreter), mailbox (register-file comms), game (main loop)

---

## The PIGS Layer

**PIGS = Platform Independence through Good Software.** Two-tier abstraction:

- **HAL** (Hardware Abstraction Layer): C-interface for joysticks, task switching, messaging, platform init. Entry point is `PIGSMain()` instead of `main()` — the HAL owns bootstrap.
- **pigsys** (SAL/Software Abstraction Layer): File I/O, memory, debug streams, portable types (`int32`, `uint32`, `int16`, etc.).

Platform-specific code isolated behind `#if defined(__PSX__)` / `__LINUX__` / `__WIN__` guards. Opinion: the two-tier split (hardware vs. software abstraction) is a pattern many engines of this period got wrong by having too many layers or too few. WorldFoundry got it right.

---

## Fixed-Point Math: The Heart of the Engine

The `Scalar` class (`math/scalar.hp`) is the most important type. It's a 1.15.16 fixed-point number — 1 sign bit, 15 integer bits, 16 fractional bits — stored as a `long`. Also experimental 1.31.32 support for higher precision.

```cpp
#define SCALAR_ONE_LS (1<<16)
#define SCALAR_CONSTANT( x ) Scalar(((long)(SCALAR_ONE_LS * (x))))
```

Provides: full operator overloading, trig functions (`Sin`, `Cos`, `ASin`, `ACos`, `ATan2`), 64-bit intermediate ops (`Sqrt64`, `FastRSqrt64`, `MulDiv`), multiply-accumulate intrinsics (`Mac2`, `Mac3`) critical for matrix ops on PS1, compile-time switching between fixed/float/double via `SCALAR_TYPE_FIXED` / `SCALAR_TYPE_FLOAT` / `SCALAR_TYPE_DOUBLE`.

Opinion: excellent engineering. The `Mac2`/`Mac3` intrinsics map directly to the PS1 GTE coprocessor's multiply-accumulate instructions. The compile-time switching lets you develop on PC with floats and ship on PS1 with fixed-point.

---

## Memory Management: No malloc, No Exceptions, No Mercy

The `Memory` class (`memory/memory.hp`) is an abstract allocator:

```cpp
virtual void* Allocate(size_t size) = 0;
virtual void  Free(const void* mem) = 0;
virtual void  Clear() = 0;  // "warning: all previous allocations are now invalid"
```

Three concrete allocators:

- **LMalloc** — Linear/Arena allocator, O(1) alloc, bulk free. 3.5 MB main pool + 180 KB scratch child pool.
- **MemPool** — Fixed-size pool, O(1) alloc/free. e.g. 500 message ports.
- **DMalloc** — Dynamic heap, free list, general purpose.

Custom placement-new throughout: `new (memory) SomeClass(args)`. Destruction is manual via `destroy()` template and `MEMORY_DELETE` / `MEMORY_DELETE_ARRAY` macros. The array deletion macro has a PSX-specific variant accounting for different memory layout of array allocations (PS1 puts count 2 words before the array; PC puts it 1 word before).

The message port pool (`MSGPORTPOOLSIZE = 500`) is a fixed-size pool for inter-object communication — pre-allocated, no runtime allocation.

Opinion: this is how you do memory management on a system with 2 MB of RAM and no virtual memory. The `Clear()` method with its ominous warning is a bulk-free for level transitions — the arena allocator pattern that modern engines have rediscovered (Zig's allocator interface, Rust's `bumpalo`). WorldFoundry was doing it in 1996.

---

## Object System: Data-Driven by Necessity

### BaseObject

All game objects derive from `BaseObject`, providing:
- OAD (Object Attribute Descriptor) data pointer — read-only, shared between identical objects to save memory
- Mailbox system for script communication
- Message port for inter-object events
- Room binding/unbinding for asset management
- Manual RTTI via `virtual EActorKind kind() const` — with a TODO comment "investigate removing"

The object type enumeration is generated from `oas/objects.e`, an include file produced by the content pipeline. Object types aren't hardcoded; they're defined by the toolchain.

### OAS/OAD (Object Attribute Sheets/Descriptors)

The data-driven design layer:
- **OAS** files define object classes — what attributes a type of object has
- **OAD** files define per-instance attribute values
- The `prep` tool compiles these into binary data and generated C++ headers
- At runtime, objects read their attributes from the compiled OAD data, not from member variables

Opinion: this is a genuine entity/component system from 1996, before the term existed. The OAS/OAD split cleanly separates schema from data. Identical objects sharing the same OAD pointer is a flyweight pattern applied to save memory on PS1.

---

## Scripting: Tcl, Not Scheme

The documentation says "Scheme-based scripting" but the actual implementation (`scripting/tcl.cc`) embeds a full Tcl interpreter. The `ScriptInterpreterFactory` currently hardcodes `TCLInterpreter` with a comment from Kevin Seghetti: *"kts right now the factory always makes TCL interpreters, I need to decide how the designer will specify which language each script is in."*

Tcl integration is minimal and purposeful:
- Two custom commands: `read-mailbox` and `write-mailbox`
- Mailbox indices and joystick button constants registered as Tcl variables
- Scripts communicate with the engine exclusively through mailboxes
- Script results converted back to `Scalar` via `atof()`

There is also a Perl interpreter implementation (`scripting/perl/`), confirming the multi-language intent. Opinion: the mailbox-only communication model is the right design — scripts can't reach into engine internals, only read and write numbered mailboxes. Clean, sandboxed, entirely data-driven.

---

## Physics and Movement: State Machine Handlers

### PhysicalAttributes

The physics system (`physics/physical.hp`) tracks: position, rotation (Euler or Matrix34, compile-time selectable), linear velocity (current and previous frame, for interpolation), predicted position (speculative collision), axis-aligned collision spaces (`ColSpace`), multi-tier collision (coarse → fine → swept/temporal with slopes). There's also a hook for ODE (Open Dynamics Engine) via `#if defined PHYSICS_ENGINE_ODE`, showing an attempted integration with a real rigid-body physics library that was never fully integrated.

### Movement Handlers

State pattern with singleton handlers:

```cpp
extern GroundHandler theGroundHandler;  // walking, running, standing
extern AirHandler    theAirHandler;     // jumping, falling
extern ClimbHandler  theClimbHandler;   // climbing surfaces
extern NullHandler   theNullHandler;    // catch-all, indicates a bug if reached
```

Each handler implements `init()`, `check()`, `update()`, `predictPosition()`. `MovementHandlerData` uses a union to share storage between states. State transitions: spawn → Ground; jump/fall off edge → Air; grab climbable → Climb; reach bottom/land → Ground; error state → Null.

Opinion: zero-allocation design — no `new` when transitioning between states. The union trick saves a few bytes per object, which matters when you have dozens of actors in 2 MB. The predict-then-resolve approach is a standard game physics pattern still used today.

---

## Rendering: Order Tables and Double Buffering

The `Display` class (`gfx/display.hp`) reveals the PS1 heritage:
- **Order tables** for depth sorting (PS1 GPU renders back-to-front using linked lists)
- **Double buffering** with explicit draw/display page management
- **VRAM** modeled as 1024×512 (the PS1's actual VRAM dimensions)
- **Four pluggable renderer pipelines** selected at compile time: PSX (GTE coprocessor, inline asm macros, order table linked lists), GL (OpenGL, Mesa/native), DirectX (Direct3D 5+), Software (CPU rasterization)

The order table system is the PS1 GPU's native rendering model. Emulating this on a Z-buffered GPU (OpenGL) means the abstraction is doing unnecessary work on PC, but it guarantees visual parity with the target hardware. There is also a stereogram mode (`DO_SLOW_STEREOGRAM`) — PSX-only, an early 3D stereoscopic rendering experiment.

---

## Room System: Spatial Partitioning for 2 MB

The `Room` class (`room/room.hp`) implements spatial partitioning:
- Rooms have physical bounds (collision spaces)
- Objects belong to rooms; rooms have adjacency lists
- Asset binding/unbinding happens per-room (load assets on entry, free on leave)
- Collision checking scoped to same-room and adjacent-room objects

Each room maintains categorized object lists: COLLIDE, RENDER, UPDATE, LIGHT, ACTIVATION_BOX. Max 200 assets per room, 5 adjacent rooms active at once. Memory layout: permanent slot (always loaded) + room slots for current + up to 4 adjacent rooms, loaded from `cd.iff` via `LoadRoomSlot()` / `FreeRoomSlot()`.

Opinion: this is the classic portal/room system from 90s 3D engines (Build, Quake, etc.), but applied to memory management as much as rendering. On PS1 with 2 MB of RAM, you can't have all level assets loaded simultaneously. The same idea behind modern open-world streaming (chunks, cells), just at a much smaller granularity dictated by the hardware.

---

## Mailbox System: The Universal Bus

The `Mailboxes` class is deceptively simple:

```cpp
virtual Scalar ReadMailbox(long mailbox) const = 0;
virtual void   WriteMailbox(long mailbox, Scalar value) = 0;
```

But it's the communication backbone of the entire engine: scripts read/write mailboxes to communicate with the engine, system mailboxes have side effects (writing triggers engine behavior), local mailboxes are per-object storage, global mailboxes are shared across all objects, `MailboxesWithStorage` chains to a parent creating a scope hierarchy. From the comments: *"think of the engine as a coprocessor to the script, and the system mailboxes as registers."*

Opinion: a register-file model for game logic — elegant and surprisingly modern. The same pattern as shader uniform buffers, ECS component data, or blackboard AI systems.

---

## Content Pipeline: The Real Product

WorldFoundry isn't just an engine — it's a production environment. The pipeline tools:

| Tool | Purpose |
|------|---------|
| `prep` | Compiles OAS files into C++ headers and binary data |
| `textile` | Processes TGA/BMP textures for target platform |
| `levelcon` | Converts 3D editor exports to engine level format |
| `iffcomp` | Compiles assets into IFF binary archives |
| `iff2lvl` | Final level packaging |

The final output is `cd.iff` — a single binary file containing all game data, named after the CD-ROM it would be burned to. IFF (Interchange File Format) usage is period-appropriate — it was the standard chunked binary format from the Amiga era. 3D editors supported: Innovation3D, 3DS Max.

Opinion: the content pipeline is arguably more impressive than the runtime engine. Having a complete path from 3D editor to PS1 binary, with schema-driven object attributes, generated code, texture processing, and level packaging — that's a production-quality toolchain.

---

## Coding Standards: Ahead of Their Time

From `source/codingstandards.txt`:
- Every class must have a `Validate()` method (empty in release, active in debug)
- Every member function calls `Validate()` on entry AND exit
- Multiple inheritance is forbidden
- No public data members — use inline accessors
- References preferred over pointers unless NULL is needed
- Preprocessor only for conditional compilation; use `enum`/`const` for constants
- Amiga-style bit flag naming (`JOYSTICKB_LEFT` for bit number, `JOYSTICKF_LEFT` for flag value)
- Required reading: "Effective C++" by Scott Meyers, "Writing Solid Code" by Steve Maguire

Opinion: the `Validate()` pattern is a poor man's design-by-contract, applied universally. On PS1 where a memory corruption bug could take days to track down, this systematic validation would catch a huge class of errors early. Modern equivalents would be `assert()` macros or Rust's borrow checker.

---

## Game Loop: Seven Phases

1. **Input** — Read joystick/keyboard
2. **Script/AI** — Run Tcl scripts via mailboxes
3. **Movement** — Handler state machine update
4. **Predict Position** — Speculative next-frame positions
5. **Collision** — Coarse AABB → Fine ColSpace → Swept temporal (most expensive); PageFlip() on the right side
6. **Animation** — Update cycles, vertex interpolation
7. **Render** — Order table sort → GPU submit

---

## Object Hierarchy

```
BaseObject
  +const void* _oadData
  +sendMsg(), BindAssets(), UnBindAssets()
  +kind() : EActorKind
  +GetMsgPort() : MsgPort
  +GetMailboxes() : Mailboxes
  +KillSelf()
    └── PhysicalObject
          +GetPhysicalAttributes()
          +Collision(other, normal)
            └── MovementObject
                  +predictPosition()
                  +update()
                  +GetMovementManager()
                  +MovementStateChanged()
                    └── Actor
                          -PhysicalAttributes _physical
                          -RenderActor _renderActor
                          -AnimationManager _animationManager
                          -MsgPort _msgPort
                          -Tool _currentTool
                          -Shield _currentShield
                          +Update(clock)
                          +Render(viewport)
```

---

## Collision: Three-Tier Pipeline

```
Coarse (AABB overlap, cheapest)
  → overlap? → Fine (ColSpace check, per-axis)
                → overlap? → Swept (temporal overlap + slope normals, most expensive)
                               → Resolve (reflect velocity, dispatch messages)
                → no → skip
  → no → skip
```

---

## What's Remarkable

1. **It's complete.** Not a renderer or a physics demo — a full engine with scripting, content pipeline, editor integration, audio, save games, and multi-platform support. You could make a game with this.
2. **Memory discipline.** Every allocation is explicit. Every pool is sized. Every temporary is accounted for. The codebase shows a team that internalized those constraints rather than fighting them.
3. **Clean abstraction boundaries.** Scripts talk through mailboxes. Objects talk through message ports. Platforms are behind HAL. Rendering is behind Display. Nothing reaches across layers.
4. **Data-driven design before it was fashionable.** The OAS/OAD system, generated object types, and content pipeline mean adding a new object type doesn't require C++ code changes — you modify the attribute sheets and the pipeline generates everything.
5. **Honest self-assessment.** The TODO files and code comments are refreshingly candid ("texture handling is a mess", "this should eventually go away", "investigate removing"). The team knew where the bodies were buried.

---

## What's Dated

1. **The build system.** OpusMake, 4DOS, 8-character path limits, batch files. Seven build modes × three streaming modes × three platforms = a combinatorial explosion. Object directories encode the full config in their name: `objdebugfixedso.linux`. Already painful in 1999.
2. **Single-threaded throughout.** There's a `DO_MULTITASKING` flag in HAL but it's clearly vestigial. Correct for PS1, limits it on modern hardware.
3. **No scene graph.** Objects are in rooms, rooms are flat lists. No spatial hierarchy (octree, BVH) for large-scale collision or rendering. Fine for PS1-scale levels, wouldn't scale.
4. **Header file conventions.** The `.hp` / `.hpi` / `.hps` naming is unusual and would confuse modern tooling. `.hpi` files contain inline implementations that are `#include`d at the bottom of the header — a pattern that predates link-time optimization.
5. **Tcl dependency.** Embedding Tcl for game scripting adds significant binary size and memory overhead. A custom bytecode VM (like Lua, which was emerging in this era) would have been lighter. The Tcl 8.3/8.4 compatibility shims suggest ongoing maintenance burden.

---

## Final Thought

WorldFoundry is a serious, professional engine built by people who understood their target hardware and their production constraints. The code quality is consistently high — not flashy, but disciplined. The architecture decisions (fixed-point math, arena allocators, mailbox communication, data-driven objects) were the right calls for the PS1 era and many of them remain good ideas today.

*It's the kind of codebase that deserves to be studied, not just preserved.*
