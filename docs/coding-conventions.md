# WorldFoundry Coding Conventions

This document is the authoritative coding conventions guide for the WorldFoundry
C++ runtime under `wfsource/source/`. It absorbs and extends the older
`wfsource/source/codingstandards.txt`.

The rules here describe how code *should* look. Large parts of the existing tree
predate individual rules and don't follow them yet. When modifying old code,
follow the surrounding local style unless you're doing an explicit cleanup
pass. When writing new code, follow this guide.

Scope: the C++ runtime and the OAS authoring system. Tools under `wftools/` are
a separate world (Rust is the default there).

---

## 1. Target envelope

WorldFoundry targets a 2 MB baseline. Primary target is **consoles**;
secondary is **mobile** (phones, tablets). Desktop (Linux, Steam) is supported
but not the foundation the engine is designed for.

Two properties of that target drive most of the rules in this guide:

**Tiny size is a competitive advantage, not a platform constraint.** Treat
every dependency, every vtable, every fallback branch as a withdrawal from
a fixed byte budget. When in doubt, measure.

**You often can't run a debugger on target.** Console devkits vary; shipping
consumer hardware doesn't cooperate; mobile debugging on-device is awkward
at best. When the target won't let you single-step, the code has to
diagnose itself. Write as if you won't get to inspect process state after a
failure — often you won't.

Both constraints push in the same direction and justify the same rules:

- no STL containers or exceptions in runtime code (§4) — size and
  predictability;
- `Validate()` on entry and exit of every member function (§5) — a
  corrupted object trips immediately, not three frames later;
- assertions that name the one broken condition, with min/value/max or
  equality pairs in the message (§6) — the failure *is* the diagnosis;
- no fallbacks for missing or malformed data (§7) — fallbacks hide the
  very bugs a debugger wouldn't have helped you find anyway, and they
  cost bytes forever;
- lookup tables over if-chains (§8) — smaller code, and easier to reason
  about from a single log line;
- streams compile out in release (§12) — in a debug build a stream
  transcript *is* the post-mortem debugger;
- custom allocators with explicit `Memory*` plumbing (§4) — size, and
  ownership is self-documenting at the call site.

---

## 2. File layout and naming

### 2.1 Extensions

| Extension | Purpose |
|---|---|
| `.hp`  | C++ header (equivalent to `.h`, WorldFoundry convention) |
| `.hpi` | Inline implementations, `#include`d at the bottom of the matching `.hp` |
| `.cc`  | Out-of-line implementation |
| `.h`   | C-style headers, generated headers, and platform headers |
| `.oas` | Object attribute source — X-macro file for the OAS system (§9) |
| `.ht`  | Generated OAS header — C struct describing an object's OAD layout |
| `.inc` | X-macro data table (e.g. `libstrm.inc`, `gamestrm.inc`) |
| `.e`   | Generated enum file (OAS object-type enumeration) |

### 2.2 Include guards

Use `#ifndef _NAME_HP` / `#define _NAME_HP`. Do not use `#pragma once`.

```cpp
#ifndef _MEMORY_HP
#define _MEMORY_HP
// ...
#endif // _MEMORY_HP
```

Leading underscores in identifiers are technically reserved by the C++
standard; WorldFoundry uses them anyway for historical reasons. Don't
reintroduce the debate — match the surrounding files.

### 2.3 File-header boilerplate

Every source file opens with a 24-line block: divider, filename + copyright,
GPL v2 license text, divider, Description and Original Author, divider. The
canonical form is in `wfsource/source/memory/memory.hp:1–24`.

Copyright year rule:
- New files get the current year.
- When making a substantive change to an existing file, append the current
  year. Example: `pigsys/assert.hp:2` carries
  `1994,1995,1996,1997,1999,2000,2001,2002,2003,2026`.

### 2.4 File naming

Lowercase, no separators, or `snake_case` for multi-word names. Examples:
`memory.hp`, `lmalloc.cc`, `jolt_backend.hp`. Do not use WikiWord for file
names.

### 2.5 Directory map under `wfsource/source/`

| Directory | Role |
|---|---|
| `anim/`          | Animation cycles, channels, paths |
| `asset/`         | Asset ID system, streaming, slot management |
| `baseobject/`    | Base class hierarchy, msgport, common block |
| `cpplib/`        | Custom containers (`Array`, `MinList`, `Int16List`), streams |
| `game/`          | Actor, Level, Director, game objects |
| `gfx/`           | Rendering — display, material, viewport, pipelines |
| `hal/`           | Hardware abstraction — platform, input, disk, timer |
| `iff/`           | IFF file format reader |
| `input/`         | Input mapping |
| `mailbox/`       | Inter-object message passing (§10) |
| `math/`          | `Scalar`, `Vector3`, `Matrix34`, `Quaternion`, `Euler`, `Angle` |
| `memory/`        | `LMalloc`, `DMalloc`, `MemPool` allocators |
| `movement/`      | Movement manager, handlers |
| `oas/`           | OAD — object attribute definition system (§9) |
| `particle/`      | Particle system |
| `physics/`       | `Physical`, collision, physics backends (`jolt/`, `ode/`) |
| `pigsys/`        | `assert`, types, core macros |
| `renderassets/`  | Render-side asset wrappers |
| `room/`          | Room loading and slot management |
| `scripting/`     | Script engine integrations |
| `streams/`       | Binary I/O streams, `DBSTREAMn` verbosity macros |
| `timer/`         | Clock system |

---

## 3. Naming

WF uses two mixed-case styles, distinguished by the case of the first
letter: **WikiWord** (upper first letter, e.g. `ThisIsAClass`) for classes,
methods, and enum types; and **camelCase** (lower first letter, e.g.
`thisIsAVariable`) for variables and accessor getters.

| Kind | Style | Example |
|---|---|---|
| Classes, structs  | `WikiWord`       | `Vector3`, `Actor`, `PhysicalAttributes` |
| Functions (methods) | `WikiWord`     | `GetPosition()`, `SetInputDevice()` |
| Accessor getters (lightweight) | `camelCase` | `currentPos()`, `getHealth()`, `isVisible()` |
| Variables         | `camelCase`      | `mySmallCounter`, `currentFree` |
| Private members and methods | leading underscore + same rule | `_position`, `_Validate()` |
| Constants         | `ALL_CAPS_SNAKE` | `MAX_ACTOR_INDEX`, `SCALAR_ONE_LS` |
| Macros            | `ALL_CAPS_SNAKE` | `MEMORY_DELETE`, `DBSTREAM3` |
| Enum types        | `E` + `WikiWord` | `EActorKind`, `EMovementState` |
| Enum values       | Enum-local; C-style `ALL_CAPS` acceptable for widely-scoped enums | `MODEL_TYPE_MESH`, `MOBILITY_ANCHORED` |
| File-scope statics / globals | `camelCase`, optional `g`/`the` prefix | `theGame`, `gCDEnabled` |

### 3.1 Bit flags

Amiga convention: `B` for bit position, `F` for flag mask. Example:

```cpp
enum {
    JOYSTICKB_LEFT = 1,
    JOYSTICKF_LEFT = 1 << JOYSTICKB_LEFT,
};
```

Reference: the convention is documented through use in the Amiga ROM Kernel
Reference Manual: *Includes and Autodocs* headers — see e.g.
[Exec Library](https://wiki.amigaos.net/wiki/Exec_Library) (`SIGB_*` /
`SIGF_*`) and
[Intuition Library](https://wiki.amigaos.net/wiki/Intuition_Library)
(`WFLG_*`, `GFLG_*`) on the AmigaOS wiki.

### 3.2 No namespaces

The runtime does not use C++ namespaces. Leading-underscore + class scoping
are the encapsulation mechanisms.

### 3.3 Formatting

Braces and indentation:

- **Braces on their own line, in the same column as their opener.** Nothing
  else on a brace line except comments.
- **Four-character tabs** throughout.

```cpp
for (int index = 0; index < foo; index++)
{
    while (bar)
    {
        stuff;
    }
}
```

Identifiers:

- **Avoid single-letter variable names.** They're impossible to
  search-and-replace and carry no meaning for a reader. Loop indices like
  `i`/`j` are the only tolerated case, and even there a named index is
  usually clearer.

---

## 4. C++ rules

- **No multiple inheritance.** If you think you need it, design differently.
- **Prefer references over pointers** unless NULL / "invalid object" is a
  real value in the contract.
- **`const` wherever possible.** Function parameters, return types, methods,
  members. If you don't do this at the leaves, you can't be `const`-correct
  at the root.
- **No public data.** Inline accessors are free. Data goes private or
  protected; expose only what callers need.
- **Class section order:**
  ```cpp
  public:
      // ctors, dtors, then other functions
  protected:
      // functions, then data (avoid protected data — use accessors)
  private:
      // functions, then data
  ```
- **Preprocessor only for conditional compilation.** Use `enum` or `const`
  for constants, `inline` for small functions.
- **No STL containers in runtime code.** Use `Array<T>`, `MinList`,
  `Int16List` from `cpplib/`. Every container takes an explicit `Memory*`
  allocator (default `HALLmalloc`); see `cpplib/array.hp:44`.
- **No exceptions in runtime code.** Return codes, out-parameters, and
  assertions cover the uses. The one historical exception —
  `WRLExporterException` in `pigsys/assert.hp` — is for tool builds only.
- **Fixed-size integer types.** Use `int8/16/32` and `uint8/16/32`
  throughout — not just for on-disk structures, hardware interfaces, and
  wire formats, but for local variables and loop indices as well. Plain
  `int` / `short` / `long` have platform-dependent sizes (16-bit on some
  targets, 32 on others, 64 on others still) and introduce portability
  hazards for no benefit. For a loop index, match the type of the bound:
  iterating up to a `uint16` count means the index is `uint16`.
- **Don't `#include <cstdint>`** in runtime headers. Use the WF types from
  `pigsys/pigtypes.h` (`uint32`, not `uint32_t`).
- **Fixed-point math: `Scalar`.** On target, `Scalar` is fixed-point
  (Q16.16); on PC dev builds it can be `float` via `SCALAR_TYPE=float`. New
  math code must work in both. See `math/scalar.hp`.

### 4.1 Resource-owning types — canonical form

If a class owns a resource (raw pointer, `FILE*`, lock, handle), define all
four special members explicitly: default constructor, copy constructor,
copy-assignment operator, and destructor. If copying doesn't make sense,
`= delete` both the copy constructor and copy-assignment operator (or declare
them `private` in pre-C++11 style). Never leave copy semantics undefined — the
compiler generates shallow copies silently, which double-frees or corrupts
the resource.

```cpp
class SoundBuffer
{
public:
    SoundBuffer();                                // alloc
    ~SoundBuffer();                               // free
    SoundBuffer(const SoundBuffer&) = delete;
    SoundBuffer& operator=(const SoundBuffer&) = delete;
    // ...
};
```

*(IS C++ §5, "Canonical Form")*

### 4.2 Concrete vs. abstract base classes

A concrete class (non-virtual destructor, public copy) used as a base class
causes **object slicing**: when a derived object is passed or assigned by
value, the derived portion is silently discarded. This is a data-loss bug with
no compile-time warning.

Rule: if a class is intended to be derived from, give it a `virtual`
destructor. If it can also be copied, document that slicing is intentional and
harmless. If it shouldn't be copied (most non-trivial base classes), `= delete`
the copy constructor and copy-assignment operator. If the class is *not*
intended as a base class, mark it `final` in new code.

*(IS C++ §4, "Class Design")*

---

## 5. The `Validate()` discipline

Every class has an inline `void Validate() const;`. In release builds it is
empty and compiles away. In debug builds it asserts every invariant the
class should uphold.

### 5.1 When `Validate()` runs

- **On entry and exit of every member function** — verify the object was
  valid before you operated on it, and that you left it valid after.
- **Constructors:** call `Validate()` at exit only (nothing to validate at
  entry).
- **Destructors:** call `Validate()` at entry only.
- **Inherited:** a derived `Validate()` calls its base's `Validate()`.

### 5.2 Validating inputs

Every member function validates its inputs before using them:

- Other WF objects: `ValidateObject(x)` (calls their `Validate()`).
- Pointers: `ValidatePtr(p)` or `ValidateObjectPtr(p)` (validates pointer
  *and* the pointed-to object).
- Scalars with a known range: `RangeCheck(min, v, max)` or one of its
  inclusive/exclusive variants (§6.1).
- Enums: `RangeCheck(0, enumValue, ENUM_MAX)`.

### 5.3 Canonical examples

`gfx/pixelmap.hpi:30`:

```cpp
inline void
PixelMap::Validate() const
{
    assert(_flags == MEMORY_VIDEO);
    RangeCheck(0, _xPos, Display::VRAMWidth);
    RangeCheck(0, _yPos, Display::VRAMHeight);
    RangeCheckInclusive(0, _xSize, Display::VRAMWidth);
    RangeCheckInclusive(0, _ySize, Display::VRAMHeight);
    RangeCheckInclusive(0, _xPos + _xSize, Display::VRAMWidth);
    RangeCheckInclusive(0, _yPos + _ySize, Display::VRAMHeight);
    if (_pixelBuffer)
        ValidatePtr(_pixelBuffer);
}
```

See also `physics/physical.hpi:37` (`PhysicalAttributes::Validate`) for a
Validate that re-derives a quantity and asserts equality to catch drift.

### 5.4 Compile-time gating

`Validate()` bodies are wrapped in `#if DO_ASSERTIONS` (or use
`ASSERTIONS(...)` from `pigsys/assert.hp:104`). The `Validate...` macros
themselves compile to `(void)0` when `DO_ASSERTIONS=0`.

---

## 6. Assertions — one check per assertion

`pigsys/assert.hp` defines the full family. Use these, not `assert.h`.

### 6.1 The macros

| Macro | Use |
|---|---|
| `assert(expr)` | Standard conditional assertion |
| `AssertMsg(expr, msg)` | Same, but prints a streamed message on failure |
| `AssertMsgFileLine(expr, msg, file, line)` | Override file/line (for helpers that forward) |
| `assertEq(a, b)` | Equality; prints both values on failure |
| `assertNe(a, b)` | Inequality; prints both values on failure |
| `Fail(msg)` | Unconditional failure with message — use at unreachable branches |
| `ValidatePtr(p)` | Asserts `p` is a valid pointer |
| `ValidateObject(x)` | Calls `x.Validate(__FILE__, __LINE__)` |
| `ValidateObjectPtr(p)` | `ValidatePtr(p)` then `p->Validate(...)` |
| `RangeCheck(lo, v, hi)`          | Range assertion (see table below) |
| `RangeCheckInclusive(lo, v, hi)` | Range assertion (see table below) |
| `RangeCheckExclusive(lo, v, hi)` | Range assertion (see table below) |

All macros compile to `(void)0` when `DO_ASSERTIONS=0`.

### 6.2 Rule: one logical condition per assertion

When an assertion fails, its message should name the specific broken
condition. Compound conditions don't — they fail as a whole without
revealing which clause was false.

**Bad:**

```cpp
assert(language >= 0 && language < 6 && kDispatch[language] != nullptr);
```

**Good:**

```cpp
RangeCheck(0, language, 6);
assert(kDispatch[language] != nullptr);
```

The first assertion tells you the range fact; the second tells you the table
fact. A failure in either reports which one.

**Better:**

```cpp
RangeCheck(0, language, 6);
AssertMsg(kDispatch[language] != nullptr, "no dispatch table entry for language " << language);
```

**Better:**
```cpp
RangeCheck(0, language, std::size(kDispatch));
AssertMsg(kDispatch[language] != nullptr, "no dispatch table entry for language " << language);
```


`AssertMsg` streams the value of `language` into the failure output — so
when the table assertion fires on a console log, the message names the
specific language index that had no entry, not just the condition that was
false. Prefer `AssertMsg` whenever there's a relevant value to print.

### 6.3 The one exception: `RangeCheck*`

Range checks *read* as one compound inequality (`lo <= v < hi`) but WF's
`RangeCheck*` macros expand to two asserts internally and report all three
values (`min`, `value`, `max`). They read like the math expression and still
fail with full diagnostic data. Use them.

### 6.4 Bounds table

This is where contributors get it wrong:

| Macro | Lower | Upper | Equivalent to |
|---|---|---|---|
| `RangeCheck(lo, v, hi)`          | inclusive | exclusive | `lo <= v < hi` — C-array index style |
| `RangeCheckInclusive(lo, v, hi)` | inclusive | inclusive | `lo <= v <= hi` |
| `RangeCheckExclusive(lo, v, hi)` | exclusive | exclusive | `lo < v < hi` |

For an enum with values `0..N-1`, write `RangeCheck(0, value, N)`.

---

## 7. No fallbacks for missing or malformed data

Treat the authoring contract as the rule, not a guideline:

- If a field is **required** by contract, missing it is an `Assert` and
  stop. No default-substitution. No silent skip. No "placeholder mesh."
- If a field is **optional with a defined no-op meaning** (e.g.,
  `Script = -1` ⇒ "this object has no script"), absence is a valid input.
  The optional branch is the contract, not a fallback — there is no
  fallback because there is nothing to fall back *from*.

This framing keeps ambiguous cases from collapsing into "maybe it's
optional." Either the contract says it's optional and the code has a clean
no-op path, or it's required and missing data is an assertion.

### 7.1 Why this is stricter than it sounds

Data problems are a *development-time* issue — level authoring, export
pipeline bugs, designer typos. By ship, the data has been debugged.
Fallback code is development-time convenience that ships forever: it costs
bytes, is rarely exercised (so it rots), and hides real bugs behind
plausible-looking placeholder behavior.

On a 2 MB target (§1), a fallback branch is a permanent tax paid for a
transient development problem.

### 7.2 Examples

Good (`game/actor.cc` around line 297):

```cpp
_nonStatPlat->_pScript = startupData->commonBlock->GetBlockPtr(
    GetCommonBlockPtr()->Script);
AssertMsg(ValidPtr(_nonStatPlat->_pScript), "actor = " << *this);
```

Absent data → assert and stop.

Also good (same file, a few lines earlier): `Script == -1` handled as a
first-class optional branch — the script pointer stays `NULL` and the rest
of the code is structured to honor "no script" as a valid state.

Avoid: chains that substitute a made-up default and keep going, or
`if (!ptr) return;` guards protecting required inputs.

### 7.3 Two categories of failure — don't mix them

*(IS C++ §7, "Error Handling")*

| Category | What it means | Correct response |
|---|---|---|
| **Precondition violation** | Programmer error — caller passed an invalid handle, called in wrong state, indexed out of range | `assert` and abort; the program state is undefined |
| **Recoverable condition** | External data, user input, file-not-found, network timeout — something that is expected to fail in production | Return code, out-parameter, or (in tool builds) exception |

Never use `assert` for recoverable conditions — it fires in debug builds and
silently succeeds in release, shipping broken behavior. Never use a return code
for a precondition violation — you're adding a branch to handle something that
shouldn't happen, and callers will omit the check.

WF's §7.1 rationale (data problems are dev-time issues; fallbacks cost bytes
forever) applies specifically to **precondition violations** on authored data.
Conditions that can legitimately occur at runtime — an optional script field
not present, a level file not yet built — are recoverable and handled with
clean optional-branch contracts.

---

## 8. Lookup tables over if-chains

If each branch of a `switch` or `if/else` ladder only differs in *which*
constant, asset, or function it uses, collapse the ladder into a table
indexed by the discriminator. Tables are smaller in code size, faster, and
easier to extend.

### 8.1 Canonical examples

**Function-pointer table** — `gfx/material.cc:58`:

```cpp
pRenderObj3DFunc
Material::Get3DRenderObjectPtr() const
{
    static const pRenderObj3DFunc _rendererList[] = {
        #include <gfx/glpipeline/renderer.ext>
    };
    ValidateRenderMask(_materialFlags);
    return _rendererList[_materialFlags & RENDERER_SELECTION_MASK];
}
```

The renderer list is an included `.ext` file, which makes adding a new
renderer a one-line data edit instead of a switch edit.

**2D interaction matrix** — `game/level.cc:1537` using
`collisionInteractionTable[type][kind]`.

**Script engine dispatch** — `ScriptRouter::RunScript` in
`wftools/wf_viewer/stubs/scripting_stub.cc`. An integer language tag (read
from an OAS field per §9) indexes a function-pointer table, replacing an
older leading-byte sigil sniff. The entries are thin lambdas that normalize
each engine's call signature into a uniform `(const char*, int) → float`
shape. Every `RunScript` has exactly that signature, so the function name
decays directly to a `RunFn` pointer — no lambda wrapper needed. Engines
gated behind compile-time switches are `nullptr` in the disabled slots,
keeping indices stable across builds so the authored-on-disk language tag
always means the same slot:

```cpp
Scalar ScriptRouter::RunScript(const void* script, int objectIndex, int language)
{
    using RunFn = float(*)(const char*, int);
    static const RunFn kDispatch[6] = {
#ifdef WF_ENABLE_LUA
        /* 0 lua    */ lua_engine::RunScript,
#else
        /* 0 lua    */ nullptr,
#endif
#ifdef WF_ENABLE_FENNEL
        /* 1 fennel */ fennel_engine::RunScript,
#else
        /* 1 fennel */ nullptr,
#endif
#ifdef WF_ENABLE_WREN
        /* 2 wren   */ wren_engine::RunScript,
#else
        /* 2 wren   */ nullptr,
#endif
#ifdef WF_ENABLE_FORTH
        /* 3 forth  */ forth_engine::RunScript,
#else
        /* 3 forth  */ nullptr,
#endif
#if defined(WF_JS_ENGINE_QUICKJS) || defined(WF_JS_ENGINE_JERRYSCRIPT)
        /* 4 js     */ js_engine::RunScript,
#else
        /* 4 js     */ nullptr,
#endif
#if defined(WF_WASM_ENGINE_WAMR) || defined(WF_WASM_ENGINE_WASM3)
        /* 5 wasm   */ wasm3_engine::RunScript,
#else
        /* 5 wasm   */ nullptr,
#endif
    };
    RangeCheck(0, language, 6);
    AssertMsg(kDispatch[language] != nullptr, "no dispatch entry for language " << language);
    return Scalar::FromFloat(kDispatch[language](static_cast<const char*>(script), objectIndex));
}
```

What *not* to write: a six-branch `if`/`else` on `language`, each branch
calling a different engine's `RunScript`. That's bigger code, slower, and
every new engine requires a new `else if`. The table makes adding an
engine a one-row edit — and the `nullptr` sentinel in disabled slots is
exactly what the §6 assertion example catches at the call site.

### 8.2 When a switch is still right

Keep the switch when each branch does *structurally different* work
(different types of effect, different control flow, different allocation
shape). A switch that reads as a type analysis is fine; a switch where
every branch allocates the same thing with a different constant is a table.

---

## 9. Designer-tunable vs. code-only — OAS / OAD

The central question in WorldFoundry when adding a new parameter: **where
should this value live?**

### 9.1 Decision tree

- Designer might tune it per-level or per-object? → **OAS field.** Authored
  in a `.oas` file, appears in the editor UI, read at runtime through the
  object's OAD data block.
- Script-authored, read at runtime? → **Mailbox** (§10).
- Global knob that differs per build (`debug` vs `release`, platform,
  feature flag)? → **Compile-time switch** — add to
  `docs/compile-time-switches.md`.
- Code-internal constant with no authoring surface (loop bound, buffer
  size, enum range)? → `const` or `enum` in the header.

The bias is toward OAS. A number hard-coded in a `.cc` is a number only the
programmer can change; a number exposed via OAS is a number the designer
owns. On a runtime tuned by designers, not programmers, that difference
compounds.

### 9.2 How OAS works

An `.oas` file is an X-macro template. When compiled, it expands to:

1. A binary `.oad` structure used by the level editor (historically 3DS
   MAX; going forward Blender) to render the attribute UI.
2. A C struct in a generated `.ht` file that the runtime reads at load
   time via `BaseObject::_oadData` (`baseobject/baseobject.hp:85`).

The macros are defined in `oas/iff.s` and `oas/oadtypes.s`. Common field
macros:

| Macro | Field type |
|---|---|
| `TYPEENTRYINT32(name, displayName, min, max, def, buttons, showas, help, enable)` | 32-bit int, range-checked |
| `TYPEENTRYFIXED32(name, displayName, min, max, def, showas, help, enable)`         | Q16.16 fixed-point |
| `TYPEENTRYBOOLEAN(name, displayName, def, showas, help)`                            | Boolean |
| `TYPEENTRYCOLOR(name, displayName, def, help)`                                      | Packed color |
| `TYPEENTRYFILENAME(name, displayName, filespec, help)`                              | Asset reference |
| `TYPEENTRYOBJREFERENCE(name, displayName, help)`                                    | Reference to another level object |
| `PROPERTY_SHEET_HEADER(name, pageNum)` / `PROPERTY_SHEET_FOOTER`                    | Grouped page |
| `GROUP_START(name, ...)` / `GROUP_STOP()`                                           | Sub-group within a sheet |

### 9.3 Canonical examples

**Simple** — `oas/actor.oas` (trivial definition, everything inherited from
`actor.inc`):

```
TYPEHEADER(Actor)
    @include actor.inc
TYPEFOOTER
```

**With ranges and groups** — `oas/camera.oas`:

```
TYPEHEADER(Camera)
    @include actor.inc
    PROPERTY_SHEET_HEADER(Camera,1)
    GROUP_START(Stereogram,)
    TYPEENTRYFIXED32(EyeDistance,,FIXED32(0),FIXED32(10),FIXED32(0.025))
    TYPEENTRYFIXED32(EyeAngle,,FIXED32(0),FIXED32(360),FIXED32(2.5))
    GROUP_STOP()
    PROPERTY_SHEET_FOOTER
    PROPERTY_SHEET_HEADER(Fogging,0)
    TYPEENTRYCOLOR(FoggingColor,Color,0)
    TYPEENTRYFIXED32(FoggingStartDistance,Start Distance,FIXED32(0),FIXED32(1000),FIXED32(10))
    TYPEENTRYFIXED32(FoggingCompleteDistance,Complete Distance,FIXED32(0),FIXED32(1000),FIXED32(20))
    PROPERTY_SHEET_FOOTER
TYPEFOOTER
```

### 9.4 Two distinct ordering / compatibility rules

Contributors conflate these. They are not the same rule.

- **The `BUTTON_*` enum in `oas/oad.h:22` is the wire format for `.oad`
  files.** Do not reorder, renumber, or delete entries. Adding new entries
  at the end is fine.
- **Per-OAS-type struct fields.** New fields go *after* existing ones so
  that old serialized level data still parses. This compat concession can
  be broken once Blender export is the primary authoring pipeline; until
  then, append.

---

## 10. Mailboxes — the script-to-code data surface

The mailbox system (`mailbox/`) is the contract between scripts and C++.
Scripts write to mailboxes; C++ reads. C++ writes to mailboxes; scripts
read.

Rules:

- **Fixed-point on the real target, float on PC dev.** Any new mailbox
  field must work in fixed-point. Floats are a PC-dev convenience, not the
  contract.
- **Angles are in revolutions** (0 ≤ r < 1) at mailbox boundaries and in
  authored data. Convert to/from radians or degrees only at the API
  boundary where a specific math library needs it.
- **Scripts are not "trivial mailbox pokes."** Real gameplay code (AI,
  dialogue, state machines, cutscenes) is substantial. Don't pick data
  shapes based on short demo scripts.

---

## 11. Variable tick rate and substepping

WorldFoundry's game loop uses a **variable `dt`**. This is load-bearing —
it took significant work to get right and many systems rely on it.

When wrapping a fixed-step library (physics, animation, audio), the
adapter **substeps internally and never exposes the raw variable `dt`
upward.** The caller hands the adapter `dt`; the adapter slices it into
whatever fixed step the library wants.

Canonical example: `JoltWorldStep(float dt)` in the Jolt physics backend
subdivides into fixed 1/60-second substeps (capped at 4 per frame to
protect against spiral-of-death).

---

## 12. Streams — the only way to print

Direct `printf`, `std::cout`, `std::cerr`, or `fprintf` are **forbidden in
runtime code.** Everything that prints goes through a named stream.

Streams are *debug infrastructure*, not a general logging framework. The
entire `stdstrm.hp` block is gated on `#if SW_DBSTREAM`, so in builds with
`SW_DBSTREAM=0` there are no standard streams at all and every
`DBSTREAMn(...)` wrapper compiles to nothing.

### 12.1 Stream categories

**Standard streams** (`cpplib/stdstrm.hp:72–80`):

| Stream | Use |
|---|---|
| `cnull`     | Null sink (discard) |
| `cprogress` | Startup/progress reporting (disabled by default) |
| `cstats`    | Statistics output |
| `cdebug`    | Internal debug output (disabled by default) |
| `cwarn`     | Warnings about processed data |
| `cerror`    | Errors in processed data |
| `cfatal`    | Bad-data-file-scale failures |
| `cver`      | Program version and startup info |
| `cuser`     | User-facing messages |

**Library streams** (`STREAMENTRY` lines in the top-level
`wfsource/source/libstrm.inc`):

| Stream | Letter | Purpose |
|---|---|---|
| `canim`       | `a` | animation / path system |
| `casset`      | `A` | asset ID system |
| `cgfx`        | `g` | graphics system |
| `ciff`        | `i` | IFF reader |
| `cmailbox`    | `I` | mailbox system |
| `cmem`        | `m` | memory system |
| `cmovement`   | `M` | movement handlers |
| `ccollision`  | `c` | collision system |
| `croom`       | `r` | room system |
| `croomslots`  | `R` | room slot assets |
| `cscripting`  | `s` | scripting engines |

**Game streams** (`game/gamestrm.inc`):

| Stream | Letter | Purpose |
|---|---|---|
| `cactor`     | `a` | actor system |
| `cflow`      | `f` | main game flow |
| `clevel`     | `l` | level system |
| `ctool`      | `t` | tool set code |
| `ccamera`    | `e` | camera |
| `cframeinfo` | `n` | frame timing / info |

### 12.2 Writing to a stream

Wrap every stream emission in a `DBSTREAMn(...)` macro. The number selects
the verbosity level at which the emission survives:

| Macro | Enabled when `SW_DBSTREAM >=` | Use for |
|---|---|---|
| `DBSTREAM1` | 1 | Startup and shutdown only — nothing in the game loop |
| `DBSTREAM2` | 2 | Game modules only (no generic subsystems) |
| `DBSTREAM3` | 3 | All subsystems, non-loop code (construct/destruct) |
| `DBSTREAM4` | 4 | All subsystems including inner loops |
| `DBSTREAM5` | 5 | Everything |

(See `streams/dbstrm.hp:43–77`.)

Example:

```cpp
DBSTREAM3(cflow << "Level::Level: loaded " << numRooms
                << " rooms" << std::endl;)
```

The entire argument compiles out when `SW_DBSTREAM` is below the level.

### 12.3 Runtime redirection

Standard and library streams accept a command-line switch to redirect them.
The switch format is `-<letter><dest>`, where `<dest>` is:

| Destination | Meaning |
|---|---|
| `n`         | null (discard) |
| `s`         | `std::cout` |
| `e`         | `std::cerr` |
| `f<path>`   | file at `<path>` |

Dispatch: `RedirectLibraryStream` / `RedirectStandardStream` in
`cpplib/stdstrm.cc` and `cpplib/libstrm.cc`.

### 12.4 How to add a new stream — the non-obvious procedure

There are two `libstrm.inc` locations that look interchangeable but aren't:

- **Per-subsystem** `wfsource/source/<subsys>/libstrm.inc` — lists the
  streams owned by that subsystem. Useful for locality and grep.
- **Top-level** `wfsource/source/libstrm.inc` — the **union** of every
  library stream. `cpplib/libstrm.hp` resolves `../libstrm.inc` relative to
  its own directory, so it always picks up this file regardless of which
  subdir is building. A `STREAMENTRY` that doesn't appear in the union is
  invisible to the build.

Procedure:

1. Pick a short `c`-prefixed name and an unused command-line switch
   letter.
2. Add `STREAMENTRY(cMyThing, NULL_STREAM, 'x', "one-line purpose")` to
   your subsystem's `wfsource/source/<subsys>/libstrm.inc`.
3. **Also** add the same line to the top-level
   `wfsource/source/libstrm.inc` so the build sees it.
4. `#include <cpplib/libstrm.hp>` in your `.cc`.
5. Write `DBSTREAMn(cMyThing << "..." << std::endl;)`.

Example: to add `cjolt` for Jolt physics debugging, the `STREAMENTRY` goes
in both `physics/libstrm.inc` and `wfsource/source/libstrm.inc`.

---

## 13. Foreign-library interop boundary

When wrapping a third-party library — Jolt, Lua, Fennel, WASM runtimes,
JavaScript engines — a module-level C-style free-function API at the
boundary is **acceptable and often preferable**:

- The public header uses **only WF types** (`Vector3`, `Euler`, `uint32`,
  `Scalar`). Foreign types stay in the `.cc`.
- Foreign headers must not leak through the public `.hp`.
- Opaque handles (e.g., `uint32` body IDs) are preferred over exposing
  foreign pointer types.
- This is the one place where "not class-shaped" is fine. Inside WF
  proper, still classes.

More broadly: **member functions that don't need access to private data
should be free functions.** This rule (IS C++ §3) reduces coupling — clients
depend only on the public header surface, not the entire class. At an interop
boundary it's mandatory; inside WF proper it's a signal to reconsider whether
a function belongs to a class at all.

The rest of the rules in this guide (Validate, streams, assertions,
no-fallbacks, file-header boilerplate, WF integer types, include guards)
still apply to the wrapper.

---

## Appendix A — Recommended reading

- **Effective C++** (ISBN 0-201-56364-9) and **More Effective C++**
  (ISBN 0-201-63371-X), Scott Meyers — essential.
- **Writing Solid Code** (ISBN 1-55615-551-4), Steve Maguire. When you
  find a bug, ask: (1) how could I have detected this automatically? (2)
  how could I have prevented it? Apply recursively.
- **Debugging the Development Process** (ISBN 1-55615-650-2), Steve
  Maguire — team dynamics.
- **No Bugs**, David Thielen (ISBN 0-201-6080-1) — origin of the
  redirectable-streams idea used in §12.
- **Industrial Strength C++**, Henricson / Nyquist (ISBN 0-13-120965-5).
  WorldFoundry follows most of it. Cited directly in this guide: canonical
  form for resource-owning types (§4.1), concrete vs. abstract base class
  rules (§4.2), free functions at boundary (§13), and the precondition vs.
  recoverable-error distinction (§7.3). Biggest WF deviation: underscore-
  prefixed private members are used where IS C++ would prefer no underscore.
- **The C++ Programming Language**, 3rd ed., Stroustrup
  (ISBN 0-201-88954-4).

