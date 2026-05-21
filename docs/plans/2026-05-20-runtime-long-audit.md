# Plan — Runtime `long` audit (PSX/x86-32 → LP64 width hardening)

**Date:** 2026-05-20
**Status:** **Implementing 2026-05-20 — NOT yet committed (Will reviewing diffs first).** F1 (pigtool.h LP64 guard), F2 (oad.h `_oadHeader`), F3 (mailbox-index API — all 5 overrides **+** the engine callers `wfmut.cpp`/`scripting_lua.cc` **+** members `level.hp`/`generator.hp`/`tool.hp`, caught by the full sweep), F4 (movecam locals), F5 (color.hpi), F6 (collision payload `uintptr_t` + interp fixes). **Flagged suspects also fixed (pass 2):** `rendcrow.cc:155` (`sizeof(long)`→`int32`), `anim/anim.cc` (`long*` copy), `rendobj3.hp`×2, `pixelmap.cc`, `sjoystic.h` (button masks), `lmalloc`/`realmalloc` `_state`, `commonblock.hpi` (`uintptr_t`), `anim/path.cc`, `main.cc`. Reclassified-permitted: `memory.hp:98` (array-new cookie width — correct), `SYS_ULONG`/`SYS_LARGEINT`, `camera.cc`. Comprehensive per-occurrence record: [review doc](../investigations/2026-05-20-long-audit-review.md). Build verifying. Pending: F7 (wfprim — own follow-up), BUGS.md, runtime-verify, commit.
**Owner:** Claude (Will reviewing)
**Branch:** `2026-new-level`

---

## Context

WF started on **PSX (MIPS)** and **x86-32**, where `long` == 32 bits == `int32`. On **LP64** (x86-64 Linux / modern Android) `long` is 64 bits, so every WF-authored bare `long` that *meant* a 32-bit value is a latent width bug. Surfaced 2026-05-20 while building the editor's OAD reader: `oad.h`'s `_oadHeader` `long`s made the C++ `oaddump` reader misread `.oad` files on x86-64 (the Rust `wf_oad` reads field-by-field, so it's correct). Spot-fixes already landed piecemeal (`ba3bbcb` IFF chunk-size, `06373f5` COLLISION-msg pointer); this is the first **systematic** pass over `wfsource/source`.

Survey — `grep -rnE '\blong\b' wfsource/source` (excluding comments / `long long` / `belong`), by file (top), ~240 lines total:

```
  38  math/scalar.cc            6  mailbox/mailbox.hp        4  oas/oad.h
  24  math/linux/scalar.cc      6  game/movecam.cc           4  math/scalar.hp
  17  math/linux/scalar.hpi     5  pigsys/pigsys.cc          4  gfx/gl/rendobj3.hp
  12  math/scalar.hpi           5  gfx/gl/wfprim.h           4  gfx/glpipeline/rendobj3.hp
  10  math/vector2.cc           5  cpplib/cpptest.cc         4  game/mailbox.hp
  10  gfx/color.hpi             4  pigsys/pigtypes.h         4  game/mailbox.cc
   9  math/mathtest.cc          4  particle/particle.cc      4  game/actor.cc
   8  math/vector3.cc           4  oas/pigtool.h             4  game/actor.cc
```

**49 files, 240 occurrences.** The mass is in the head (fixed-point math: `scalar.cc` 38, `linux/scalar.cc` 24). The **tail is 26 files with 1–3 each** (~50 occurrences) — mostly likely-permitted (stdio/HAL interop in `pigsys`/`hal`, allocator *sizes* in `memory/*`, `anim/*` + `gfx` fixed-point, `*test.cc`) but **unverified**; a few worth an eyeball (`game/level.cc`, `game/main.cc`, `baseobject/commonblock.hpi`, `anim/path.cc`). This audit fixes the **concentrated genuine bugs** (the clusters below); classifying the 26-file tail is a bounded follow-up.

Most are **permitted** or **already-safe**; a small set are genuine bugs.

### Permitted / already-safe (leave alone)
- **`scalar.cc`/`scalar.hpi` + `vector2.cc`/`vector3.cc`** — 64-bit intermediates for 16.16 fixed-point **multiply / divide / sqrt / dot** — *required*, not optional (audited below: [§ Fixed-point math intermediates](#fixed-point-math-64-bit-intermediates--audited)). Arguably clearer as `int64_t`; low-priority style, not in scope.
- **`pigsys.cc`** — `sys_fseek(long off)` etc. match the C stdio `ftell`/`fseek` signatures. Correct interop.
- **`pigtypes.h`** — `SYS_ULONG`/`SYS_LARGEINT` *are* `long` by definition; `SYS_INT32 signed long` only in the non-LP64 else-branch (the `__LINUX__`/`__ANDROID__` branch already uses `signed int`). Correct.
- **`particle.cc`** — `long` only inside `/* … */` min/max comments.
- **`oad.h` `FIXED32(n)` macro** — compile-time literal cast; harmless (could be `int32` for tidiness).

---

## Fixed-point math 64-bit intermediates — audited

Will's question (2026-05-20): *"16.16 math only needs 32-bit intermediates; all 64-bit intermediates should be reviewed skeptically (they'd only be needed for 32.32 math)."* Audited the Scalar/vector core against that. **Verdict: half-right — and the half that's wrong is load-bearing.**

- **Add / sub: 32-bit is enough** ✓ — it's modular `int32 + int32`. `Scalar::operator+`/`-`/`+=`/`-=` ([scalar.hpi:259-299](../../wfsource/source/math/scalar.hpi)) use **no `long`**.
- **Multiply: 64-bit is *required*.** A 16.16 value is `V·2^16` in 32 bits; the product `a_int·b_int = (A·B)·2^32` is up to **64 bits** (operands near ±32768 → ~`2^62`), then `>>16` back to 16.16. A 32-bit product **overflows and drops the high word → garbage**. **That 64-bit intermediate *is* the "32.32" — it's the unavoidable product width of a 16.16 multiply, not a separate "32.32 mode."**
- **Divide / reciprocal: 64-bit required** — the dividend is pre-shifted `<<16` (to ~48 bits) before the divide.

The verified 64-bit sites are *all* mul/div/reciprocal/muldiv (or the sqrt/dot helpers built from them):
- `operator*=` → `(int32)(((long)_value * (long)other._value) >> 16)` ([scalar.hpi:42](../../wfsource/source/math/linux/scalar.hpi))
- `operator/=` → `(int32)(((long)_value << 16) / (long)other._value)` (scalar.hpi:64)
- reciprocal `0x100000000L / (long)_value` (:32); muldiv `(long)a*(long)b/(long)c` (:75)
- `Sqrt64`/`FastRSqrt64`/`JoinHiLo`/`SignedDivide64`/`UnSignedDivide64` + the `out0..out3` accumulators — the 64-bit emulation PSX did with 32-bit register pairs (no native 64-bit on MIPS); the 2026 rework replaced the asm with native `long` since LP64 `long` *is* 64-bit.

**None** are in an add/sub, compare, or storage path. So they pass the skeptical test rather than fail it — **do not downgrade them** (that would silently overflow every multiply).

**Adopted rule (the right form of Will's instinct):** a 64-bit intermediate is justified **iff** the operation's exact result can exceed 32 bits — **multiply, pre-shifted divide, sqrt, accumulated dot/cross**. Any 64-bit in an **add / sub / compare / storage** path is a bug → demote to `int32`. By this rule the math core is clean.

---

## Fixes

| # | Site | Change | Notes |
|---|---|---|---|
| F1 | **`oas/pigtool.h`** `SYS_INT32`/`SYS_UINT32` | Add the `__LINUX__`/`__ANDROID__` LP64 guard (use `signed int`/`unsigned int`), mirroring `pigtypes.h`; or `#include`/defer to `pigtypes.h`. | **Systemic root cause** — unguarded `signed long` makes `int32` 8 bytes in any Linux TU that pulls `pigtool.h` (via `oad.h`) before `pigtypes.h`; that's the measured `typeDescriptor` 1503-vs-1491 bloat (3× `int32` × +4). Dormant in the full engine build (include order), latent landmine otherwise. |
| F2 | **`oas/oad.h` `_oadHeader`** | `long chunkId/chunkSize/version` → `int32`/`uint32`. | Serialized 32-bit IFF header fields; the bug that bit the OAD reader. |
| F3 | **Mailbox API** — `mailbox/mailbox.hp`, `game/mailbox.{hp,cc}`, `actor.cc` `ActorMailboxes` | `ReadMailbox(long)`/`WriteMailbox(long,…)` params, `long _mailboxBase`/`numberOfLocalMailboxes` → `int32`. | Mailbox **indices** (small ints ≤999). Touches a **virtual** interface — change base + every override consistently (`Mailboxes`, `MailboxesWithStorage`, `LevelMailboxes`, `GameMailboxes`, `ActorMailboxes`) + callers. |
| F4 | **`game/movecam.cc`** | `long idxShot`/`shotIndex = …WholePart()` → `int32`. | Index locals. |
| F5 | **`gfx/color.hpi`** | `long temp` (8-bit colour add/sub) → `int`/`int32`. | 64-bit unnecessary; 32-bit ample. |
| F6 | **Collision-message payload** (`actor.cc`, `warp.cc`) | **Keep the pointer (perf), fix the *interpretation* bugs.** Retype the invalidation `*(long*)msgData = 0` → `*(uintptr_t*)msgData = 0` (honest pointer-width, not `long`), and fix the two receivers that wrongly cast the **buffer address** as an Actor (`((Actor*)msgData)->…` in `actor.cc:1701`, `(Actor*)msgData` in `warp.cc:113`) → `reinterpret_cast<Actor*>(*(uintptr_t*)msgData)`, matching the correct `enemy.cc`/`explode.cc`. | The payload genuinely *is* a pointer (`collision.cc:227` posts `reinterpret_cast<uintptr_t>(&object)`; `06373f5` made it carry a full pointer). It's `uintptr_t`, not a mis-sized `int32`, so it's correct as-is — the real bugs were the inconsistent casts. Same-frame consumption keeps the pointer valid. The `COLLISION` (non-special) consumers (`movement`/`movepath`/`movecam:656`/`movefoll`) only **drain** the queue (no deref) — unaffected. |
| F7 | **`gfx/gl/wfprim.h`** PSX-GPU-primitive `long x,y,z`/`tag`/`code[]` | **TODO (not done here) — but it's LIVE, not dead** (determined 2026-05-20): retype `Point3D{long x,y,z}` → `int32` (16.16 fixed-point coords, used by `GL_3D_VERTEX`) and the `SPRT_16`/`DR_MODE` `tag`/`code` PSX packed-words → `(u)int32` (vestigial 32-bit words living in `rendmatt` order-table arrays). Layout-sensitive — verify fill-site strides. `GfxLoadImage`/`OTag` are genuinely dead → removable. | Earlier "dead PSX path" assumption was **wrong**: `display.cc`/`rendmatt`/`pixelmap`/`otable` all use these. Deferred (rendering-hot, separate care) — [TODO](../../TODO.md) § Engine Robustness. |

### Deferred follow-up — collision payload by actor index (not pointer)
Converting the `SPECIAL`/`COLLISION` message payload from a pointer to an **`int32` actor index** (sender posts `GetObjectIndex(&other)`; receivers `GetObject(idx)`) would retire all the `reinterpret_cast`/`uintptr_t` handling and the bug class with it, and matches how the **mailbox** path already exposes the collider (`COLLIDER_IDX` 3044 = `GetActorIndex()` → a `Scalar`, *because a 32-bit fixed-point mailbox can't hold a pointer*). **Tradeoff:** the pointer is a real optimization (direct deref vs a per-message `GetObject` lookup + bounds-check) on the hot collision path / embedded targets; the index is safer (bounds-checked, width-safe, no dangling) at a small lookup cost. Two clean channels today — **message-port = pointer (C++-internal), mailbox = index (script-facing)** — never cross. Lean: index, but it deserves a profile or a deliberate "safety > micro-opt" call, not a snap decision; its own plan.

---

## Diff (applied — full `git diff` of every long-audit change; NOT committed)

> `actor.cc` shows **only my audit hunks** (collision `@@ -1697`, mailbox `@@ -1858/-1875/-1885`); the in-flight SMB hunks (`@@ -521/-650/-786`) are deliberately excluded. `commonblock.hpi` is absent — reverted (reclassified permitted). Everything below is in the working tree only.

```diff
diff --git a/engine/mutation/wfmut.cpp b/engine/mutation/wfmut.cpp
index b17a288..306cdc8 100644
--- a/engine/mutation/wfmut.cpp
+++ b/engine/mutation/wfmut.cpp
@@ -408,7 +408,7 @@ bool SetMailbox(Level& level, ActorIdx idx, int mailboxIndex, double value)
         return fail("wfmut::SetMailbox: mailboxIndex must be >= 0");
     // Actor exposes its mailbox bank via GetMailboxes(); backing storage is
     // bounds-checked by MailboxesWithStorage in DBSTREAM builds.
-    actor->GetMailboxes().WriteMailbox(static_cast<long>(mailboxIndex), Scalar::FromDouble(value));
+    actor->GetMailboxes().WriteMailbox(mailboxIndex, Scalar::FromDouble(value));   // int -> int32 mailbox index
     ok();
     return true;
 }
@@ -419,7 +419,7 @@ std::optional<double> GetMailbox(const Level& level, ActorIdx idx, int mailboxIn
     if (!actor) return std::nullopt;
     if (mailboxIndex < 0)
         return failopt<double>("wfmut::GetMailbox: mailboxIndex must be >= 0");
-    Scalar v = actor->GetMailboxes().ReadMailbox(static_cast<long>(mailboxIndex));
+    Scalar v = actor->GetMailboxes().ReadMailbox(mailboxIndex);   // int -> int32 mailbox index
     ok();
     return static_cast<double>(v.AsFloat());
 }
diff --git a/engine/stubs/scripting_lua.cc b/engine/stubs/scripting_lua.cc
index 4d7099a..f6831bc 100644
--- a/engine/stubs/scripting_lua.cc
+++ b/engine/stubs/scripting_lua.cc
@@ -74,14 +74,14 @@ static int lua_set_music_volume(lua_State* L)
 
 static int lua_read_mailbox(lua_State* L)
 {
-    long mailbox  = static_cast<long>(luaL_checkinteger(L, 1));
+    int  mailbox  = static_cast<int>(luaL_checkinteger(L, 1));   // int32 mailbox index
     int  actorIdx = gCurrentObject;
     if (lua_gettop(L) >= 2)
         actorIdx = static_cast<int>(luaL_checkinteger(L, 2));
     Mailboxes& mb = gMailboxes->LookupMailboxes(actorIdx);
     Scalar v = mb.ReadMailbox(mailbox);
 #ifdef WF_SCRIPT_DEBUG
-    std::fprintf(stderr, "  lua read_mailbox(%ld, actor=%d) -> %g\n",
+    std::fprintf(stderr, "  lua read_mailbox(%d, actor=%d) -> %g\n",
                  mailbox, actorIdx, (double)v.AsFloat());
 #endif
     lua_pushnumber(L, v.AsFloat());
@@ -90,14 +90,14 @@ static int lua_read_mailbox(lua_State* L)
 
 static int lua_write_mailbox(lua_State* L)
 {
-    long   mailbox  = static_cast<long>(luaL_checkinteger(L, 1));
+    int    mailbox  = static_cast<int>(luaL_checkinteger(L, 1));   // int32 mailbox index
     double value    = luaL_checknumber(L, 2);
     int    actorIdx = gCurrentObject;
     if (lua_gettop(L) >= 3)
         actorIdx = static_cast<int>(luaL_checkinteger(L, 3));
     Mailboxes& mb = gMailboxes->LookupMailboxes(actorIdx);
 #ifdef WF_SCRIPT_DEBUG
-    std::fprintf(stderr, "  lua write_mailbox(%ld, %g, actor=%d)\n",
+    std::fprintf(stderr, "  lua write_mailbox(%d, %g, actor=%d)\n",
                  mailbox, value, actorIdx);
 #endif
     mb.WriteMailbox(mailbox, Scalar::FromFloat(static_cast<float>(value)));
diff --git a/wfsource/source/anim/anim.cc b/wfsource/source/anim/anim.cc
index 7440b8a..89647b7 100644
--- a/wfsource/source/anim/anim.cc
+++ b/wfsource/source/anim/anim.cc
@@ -157,8 +157,8 @@ AnimateRenderObject3D::Animate(Scalar time,RenderObject3D& renderObject)
 
 	int frame = (time*_rate).WholePart() % _frameCount;
 
-	long* source = (long*)&_animArray[frame*vertexCount];
-	long* dest = (long*)vertexList;
+	int32* source = (int32*)&_animArray[frame*vertexCount];
+	int32* dest = (int32*)vertexList;
 	assert(((vertexCount*sizeof(Vertex3D)) % 4) == 0);
 	int count = (vertexCount*sizeof(Vertex3D)) / 4;
 	for(int memIndex=0;memIndex<count;memIndex++)
diff --git a/wfsource/source/anim/path.cc b/wfsource/source/anim/path.cc
index a35486a..509516b 100644
--- a/wfsource/source/anim/path.cc
+++ b/wfsource/source/anim/path.cc
@@ -150,9 +150,9 @@ Path::Rotation( const Scalar time )
 
 
    // kts why is channel rotation data stored as Radians?
-	rotation.SetA( Angle::Radian( Scalar::FromFixed32( _rotationAChannel->Value(time, long(SCALAR_ONE_LS * PI * 2.0)))) );
-	rotation.SetB( Angle::Radian( Scalar::FromFixed32( _rotationBChannel->Value(time, long(SCALAR_ONE_LS * PI * 2.0)))) );
-	rotation.SetC( Angle::Radian( Scalar::FromFixed32( _rotationCChannel->Value(time, long(SCALAR_ONE_LS * PI * 2.0)))) );
+	rotation.SetA( Angle::Radian( Scalar::FromFixed32( _rotationAChannel->Value(time, int32(SCALAR_ONE_LS * PI * 2.0)))) );
+	rotation.SetB( Angle::Radian( Scalar::FromFixed32( _rotationBChannel->Value(time, int32(SCALAR_ONE_LS * PI * 2.0)))) );
+	rotation.SetC( Angle::Radian( Scalar::FromFixed32( _rotationCChannel->Value(time, int32(SCALAR_ONE_LS * PI * 2.0)))) );
 
 	rotation += _baseRot;	// Add offset for relative path or zero for absolute path
 	return rotation;
diff --git a/wfsource/source/game/actor.hp b/wfsource/source/game/actor.hp
index c810f1b..90cc316 100644
--- a/wfsource/source/game/actor.hp
+++ b/wfsource/source/game/actor.hp
@@ -73,10 +73,10 @@ class Actor;
 class ActorMailboxes : public MailboxesWithStorage
 {
 public:
-   ActorMailboxes(Actor& actor, long mailboxesBase, long numberOfLocalMailboxes, Mailboxes* parent);
+   ActorMailboxes(Actor& actor, int32 mailboxesBase, int32 numberOfLocalMailboxes, Mailboxes* parent);
    virtual ~ActorMailboxes();
-   virtual Scalar ReadMailbox(long mailbox) const;
-   virtual void WriteMailbox(long mailbox, Scalar value);
+   virtual Scalar ReadMailbox(int32 mailbox) const;
+   virtual void WriteMailbox(int32 mailbox, Scalar value);
 private:
     Actor& _actor;          // kts temporary, eventually I will just put the mbox storage in here
 };
diff --git a/wfsource/source/game/generator.hp b/wfsource/source/game/generator.hp
index 678cd1a..7ed8a45 100644
--- a/wfsource/source/game/generator.hp
+++ b/wfsource/source/game/generator.hp
@@ -59,7 +59,7 @@ private:
 
 	Scalar _delayBetweenGeneration;	// delay, in seconds, between object generation
 	Scalar _timeToGenerate;			// temp variable, contains time at which next object should be generated
-	long _generateMailBox;						// mailbox which activates generation
+	int32 _generateMailBox;						// mailbox index which activates generation (was long)
 	Vector3 _vect;						// initial vector of created object
 };
 
diff --git a/wfsource/source/game/level.hp b/wfsource/source/game/level.hp
index 936d01e..441cadd 100644
--- a/wfsource/source/game/level.hp
+++ b/wfsource/source/game/level.hp
@@ -249,8 +249,8 @@ private:
 	SObjectStartupData **		_templateObjects;						// pointer to array of template object pointers, in levelcon order
 	int							_numTemplateObjects;
 	// system mailboxes requiring storage
-	long						_camRollMailBox;						// kts is there a better way?
-	long						_camShotMailBox;						// kts is there a better way?
+	int32						_camRollMailBox;						// mailbox index (was long → 8 bytes on LP64)
+	int32						_camShotMailBox;						// mailbox index (was long → 8 bytes on LP64)
 
    PointerContainer<Memory> _memory;
 
diff --git a/wfsource/source/game/mailbox.cc b/wfsource/source/game/mailbox.cc
index 30aad60..791ee0c 100644
--- a/wfsource/source/game/mailbox.cc
+++ b/wfsource/source/game/mailbox.cc
@@ -38,7 +38,7 @@ _level(level)
 //==============================================================================
                      
 Scalar
-LevelMailboxes::ReadMailbox(long mailbox) const
+LevelMailboxes::ReadMailbox(int32 mailbox) const
 {
    DBSTREAM1(cmailbox << "LevelMailboxes::ReadMailbox: mailbox = " << mailbox << std::endl; )
 
@@ -51,7 +51,7 @@ LevelMailboxes::ReadMailbox(long mailbox) const
 //==============================================================================
 
 void
-LevelMailboxes::WriteMailbox(long mailbox, Scalar value)
+LevelMailboxes::WriteMailbox(int32 mailbox, Scalar value)
 {
     if(mailbox >= EMAILBOX_GLOBAL_SYSTEM_START && mailbox < EMAILBOX_GLOBAL_SYSTEM_MAX)
         _level.WriteSystemMailbox(mailbox, value);
@@ -76,7 +76,7 @@ _game(game)
 //==============================================================================
 
 Scalar
-GameMailboxes::ReadMailbox(long mailbox) const
+GameMailboxes::ReadMailbox(int32 mailbox) const
 {
    DBSTREAM1(cmailbox << "GameMailboxes::ReadMailbox: mailbox = " << mailbox << std::endl; )
 
@@ -89,7 +89,7 @@ GameMailboxes::ReadMailbox(long mailbox) const
 //==============================================================================
 
 void
-GameMailboxes::WriteMailbox(long mailbox, Scalar value)
+GameMailboxes::WriteMailbox(int32 mailbox, Scalar value)
 {
    if(mailbox >= EMAILBOX_PERSISTENT_SYSTEM_START && mailbox < EMAILBOX_PERSISTENT_SYSTEM_MAX)
        _game.WriteSystemMailbox(mailbox, value);
diff --git a/wfsource/source/game/mailbox.hp b/wfsource/source/game/mailbox.hp
index 78a3ccd..2b783ec 100644
--- a/wfsource/source/game/mailbox.hp
+++ b/wfsource/source/game/mailbox.hp
@@ -33,8 +33,8 @@ class LevelMailboxes : public MailboxesWithStorage
 {
 public:
     LevelMailboxes(Level& level, Mailboxes* parent);
-   virtual Scalar ReadMailbox(long mailbox) const;
-   virtual void WriteMailbox(long mailbox, Scalar value); 
+   virtual Scalar ReadMailbox(int32 mailbox) const;
+   virtual void WriteMailbox(int32 mailbox, Scalar value); 
 private:
    Level& _level;
 };
@@ -43,8 +43,8 @@ class GameMailboxes : public MailboxesWithStorage
 {
 public:
     GameMailboxes(WFGame& game);
-   virtual Scalar ReadMailbox(long mailbox) const;
-   virtual void WriteMailbox(long mailbox, Scalar value); 
+   virtual Scalar ReadMailbox(int32 mailbox) const;
+   virtual void WriteMailbox(int32 mailbox, Scalar value); 
 private:
    WFGame& _game;
 };
diff --git a/wfsource/source/game/main.cc b/wfsource/source/game/main.cc
index 336ddea..ecac3fe 100755
--- a/wfsource/source/game/main.cc
+++ b/wfsource/source/game/main.cc
@@ -284,7 +284,7 @@ ParseCommandLine(int argc, char** argv)
 			AssertMsg( strlen(argv[index]+1) > 10, "The -breaktime= option requires a time" );
 			extern Scalar WALL_CLOCK_BREAKPOINT_VALUE;
 #if defined(SCALAR_TYPE_FIXED)
-         long value = atoi( argv[index] + 1 + 10 );
+         int32 value = atoi( argv[index] + 1 + 10 );
         WALL_CLOCK_BREAKPOINT_VALUE = Scalar::FromFixed32(value);
 #elif defined(SCALAR_TYPE_FLOAT) || defined(SCALAR_TYPE_DOUBLE)
          double value;
diff --git a/wfsource/source/game/movecam.cc b/wfsource/source/game/movecam.cc
index c4ba615..3937959 100644
--- a/wfsource/source/game/movecam.cc
+++ b/wfsource/source/game/movecam.cc
@@ -474,7 +474,7 @@ NormalCameraHandler::_update(MovementObject& movementObject,cameraPosition& dest
 
 	cameraData& cd  = GetCameraMovementData(movementObject);
 
-	long idxShot = theLevel->GetMailboxes().ReadMailbox(EMAILBOX_CAMSHOT).WholePart();
+	int32 idxShot = theLevel->GetMailboxes().ReadMailbox(EMAILBOX_CAMSHOT).WholePart();
 	DBSTREAM3( ccamera << "idxShot = " << idxShot << std::endl; )
 	AssertMsg(idxShot != 0, "Camera " << movementObject << " found no ActBoxOR, possible cause: Player is not in any actboxor");
 	assert(idxShot > 0);
@@ -672,7 +672,7 @@ PanCameraHandler::update(MovementManager& /*movementManager*/,  MovementObject&
 	assert(cd.panStartTime <= theLevel->LevelClock().Current());
 	assert(cd.idxCamShotActor);
 
-	long shotIndex = theLevel->GetMailboxes().ReadMailbox(EMAILBOX_CAMSHOT).WholePart();
+	int32 shotIndex = theLevel->GetMailboxes().ReadMailbox(EMAILBOX_CAMSHOT).WholePart();
 	assert(shotIndex);
 	const CamShot* camShot = (CamShot*)theLevel->getActor(shotIndex);
 	assert(ValidPtr(camShot));
@@ -799,7 +799,7 @@ DelayCameraHandler::check()
 {
 	assert(0);
 	DBSTREAM3( ccamera << "DelayCameraHandler check function called." << std::endl; )
-	long shotIndex = theLevel->GetMailboxes().ReadMailbox(EMAILBOX_CAMSHOT).WholePart();
+	int32 shotIndex = theLevel->GetMailboxes().ReadMailbox(EMAILBOX_CAMSHOT).WholePart();
 	return(shotIndex <= 0);						// only activate if there is no camshot right now
 //	return true;
 }
@@ -822,7 +822,7 @@ DelayCameraHandler::update(MovementManager& movementManager, MovementObject& mov
 	DBSTREAM3( ccamera << "DelayCameraHandler::update function called." << std::endl; )
 	assert( ValidPtr( theLevel ) );
 
-	long shotIndex = theLevel->GetMailboxes().ReadMailbox(EMAILBOX_CAMSHOT).WholePart();
+	int32 shotIndex = theLevel->GetMailboxes().ReadMailbox(EMAILBOX_CAMSHOT).WholePart();
 	//std::cout << "shotIndex = " << shotIndex << std::endl;
 	if(shotIndex > 0)
 	{
@@ -886,7 +886,7 @@ BungeeCameraHandler::init(MovementManager& movementManager, MovementObject& move
 
 	cameraData& cd = GetCameraMovementData(movementObject);
 
-	long shotIndex = theLevel->GetMailboxes().ReadMailbox(EMAILBOX_CAMSHOT).WholePart();
+	int32 shotIndex = theLevel->GetMailboxes().ReadMailbox(EMAILBOX_CAMSHOT).WholePart();
 	AssertMsg(shotIndex != 0, "Camera " << movementObject << " found no ActBoxOR, possible cause: Player is not in any actboxor");
 	assert(shotIndex > 0);
 
@@ -930,7 +930,7 @@ BungeeCameraHandler::predictPosition(MovementManager& /*movementManager*/, Movem
 	Scalar deltaT = theLevel->LevelClock().Delta();
 
 	// Get climbRate and Elasticity from camShot data
-	long idxShot = theLevel->GetMailboxes().ReadMailbox(EMAILBOX_CAMSHOT).WholePart();
+	int32 idxShot = theLevel->GetMailboxes().ReadMailbox(EMAILBOX_CAMSHOT).WholePart();
 	RangeCheck( 1, idxShot, theLevel->GetMaxObjectIndex() );
 
 	CamShot* camShotActor = (CamShot*)(theLevel->getActor( idxShot ));
diff --git a/wfsource/source/game/tool.hp b/wfsource/source/game/tool.hp
index 4b461b4..887f914 100644
--- a/wfsource/source/game/tool.hp
+++ b/wfsource/source/game/tool.hp
@@ -101,7 +101,7 @@ protected:
 
 	inline const _Tool* getOad() const;
 	_Tool _toolOAD;				// copy of original data
-	long _objectToGenerate;		// which template object to spew
+	int32 _objectToGenerate;	// template-object index to spew (was long; matches _owner below)
 	int32 _owner;				// actor index of owner
 	Scalar _timeAvailableToFire;
    const void* _pScript;
diff --git a/wfsource/source/game/warp.cc b/wfsource/source/game/warp.cc
index 4240ee7..5e71727 100644
--- a/wfsource/source/game/warp.cc
+++ b/wfsource/source/game/warp.cc
@@ -110,7 +110,7 @@ Warp::update()
 				break;
 			case MsgPort::SPECIAL_COLLISION:
 			{
-				Actor* colActor = (Actor*)msgData;
+				Actor* colActor = reinterpret_cast<Actor*>(*(uintptr_t*)msgData);   // pointer is stored IN msgData, not the buffer's address
 				DBSTREAM4( cdebug << "Warp::update: collision with actor  " << colActor << std::endl; )
 				if ( activation.Activated(theLevel->GetActiveRooms().GetObjectIter(ROOM_OBJECT_LIST_COLLIDE), (struct _Activation*)&GetActivateBlockPtr()->ActivatedBy, colActor, *GetActivationBlockPtr(), theLevel->GetObjectList()) )
 				{
diff --git a/wfsource/source/gfx/color.hpi b/wfsource/source/gfx/color.hpi
index 81f8d9b..2afa362 100644
--- a/wfsource/source/gfx/color.hpi
+++ b/wfsource/source/gfx/color.hpi
@@ -138,15 +138,15 @@ INLINE Color
 Color::operator+(const Color& other) const
 {
 	Color result;
-	register long temp = long(Red())+long(other.Red());
+	register int temp = int(Red())+int(other.Red());
 	if(temp > 255)
 		temp = 255;
 	result.SetRed(temp);
-	temp = long(Green())+long(other.Green());
+	temp = int(Green())+int(other.Green());
 	if(temp > 255)
 		temp = 255;
 	result.SetGreen(temp);
-	temp = long(Blue())+long(other.Blue());
+	temp = int(Blue())+int(other.Blue());
 	if(temp > 255)
 		temp = 255;
 	result.SetBlue(temp);
@@ -160,15 +160,15 @@ INLINE Color
 Color::operator-(const Color& other) const
 {
 	Color result;
-	register long temp = long(Red())-long(other.Red());
+	register int temp = int(Red())-int(other.Red());
 	if(temp < 0)
 		temp = 0;
 	result.SetRed(temp);
-	temp = long(Green())-long(other.Green());
+	temp = int(Green())-int(other.Green());
 	if(temp < 0)
 		temp = 0;
 	result.SetGreen(temp);
-	temp = long(Blue())-long(other.Blue());
+	temp = int(Blue())-int(other.Blue());
 	if(temp < 0)
 		temp = 0;
 	result.SetBlue(temp);
@@ -193,15 +193,15 @@ INLINE Color
 Color::operator*(const Color& other) const
 {
 	Color result;
-	register long temp = (long(Red())*long(other.Red()))/128;
+	register int temp = (int(Red())*int(other.Red()))/128;
 	if(temp > 255)
 		temp = 355;
 	result.SetRed(temp);
-	temp = (long(Green())*long(other.Green()))/128;
+	temp = (int(Green())*int(other.Green()))/128;
 	if(temp > 255)
 		temp = 355;
 	result.SetGreen(temp);
-	temp = (long(Blue())*long(other.Blue()))/128;
+	temp = (int(Blue())*int(other.Blue()))/128;
 	if(temp > 255)
 		temp = 355;
 	result.SetBlue(temp);
@@ -282,7 +282,7 @@ INLINE
 Color48::operator Color () const
 {
 	Color result;
-	long temp = _color[0]>>4;
+	int temp = _color[0]>>4;
 	if(temp > 255)
 		temp = 255;
 	result.SetRed(temp);
diff --git a/wfsource/source/gfx/gl/rendobj3.hp b/wfsource/source/gfx/gl/rendobj3.hp
index a05ce7e..abcbbb6 100644
--- a/wfsource/source/gfx/gl/rendobj3.hp
+++ b/wfsource/source/gfx/gl/rendobj3.hp
@@ -31,10 +31,10 @@
 struct RendererVariables
 {
 	ViewPort* viewPort;
-	long flags;
-	long zflag;
-	long sz[3];
-	long ir0[3];
+	int32 flags;
+	int32 zflag;
+	int32 sz[3];
+	int32 ir0[3];
 	const TriFace* currentRenderFace;
 	const Material* currentRenderMaterial;
 	const RotatedVector* rotatedVectorList;
diff --git a/wfsource/source/gfx/glpipeline/rendobj3.hp b/wfsource/source/gfx/glpipeline/rendobj3.hp
index 35fe74c..a7b28ab 100644
--- a/wfsource/source/gfx/glpipeline/rendobj3.hp
+++ b/wfsource/source/gfx/glpipeline/rendobj3.hp
@@ -31,10 +31,10 @@
 struct RendererVariables
 {
 	ViewPort* viewPort;
-	long flags;
-	long zflag;
-	long sz[3];
-	long ir0[3];
+	int32 flags;
+	int32 zflag;
+	int32 sz[3];
+	int32 ir0[3];
 	const TriFace* currentRenderFace;
 	const Material* currentRenderMaterial;
 	const RotatedVector* rotatedVectorList;
diff --git a/wfsource/source/gfx/pixelmap.cc b/wfsource/source/gfx/pixelmap.cc
index 24f3658..6e88031 100755
--- a/wfsource/source/gfx/pixelmap.cc
+++ b/wfsource/source/gfx/pixelmap.cc
@@ -146,7 +146,7 @@ PixelMap::Load(const void* memory, int xOffset, int yOffset, int xSize, int ySiz
     rect.w = xSize;
     rect.h = ySize;
 
-    long unsigned int * _p = (long unsigned int *)memory;
+    uint32 * _p = (uint32 *)memory;
     ValidatePtr(_pixelBuffer);
     GLubyte* pPB = _pixelBuffer;
 
diff --git a/wfsource/source/hal/sjoystic.h b/wfsource/source/hal/sjoystic.h
index 4a2e6fe..74de15a 100644
--- a/wfsource/source/hal/sjoystic.h
+++ b/wfsource/source/hal/sjoystic.h
@@ -110,7 +110,7 @@
 #	error Unknown platform -- how are the joystick buttons mapped?
 #endif
 
-typedef long joystickButtons;
+typedef uint32 joystickButtons;
 
 // joystickButtonsF
 #define	EJ_BUTTONF_NONE 0
@@ -147,7 +147,7 @@ typedef long joystickButtons;
 #define	EJ_BUTTONF_1 (1<<EJ_BUTTONB_1)
 #define	EJ_BUTTONF_2 (1<<EJ_BUTTONB_2)
 
-typedef long joystickButtonsF;
+typedef uint32 joystickButtonsF;
 
 typedef enum
 {
diff --git a/wfsource/source/mailbox/mailbox.cc b/wfsource/source/mailbox/mailbox.cc
index 37722c0..7887eb1 100644
--- a/wfsource/source/mailbox/mailbox.cc
+++ b/wfsource/source/mailbox/mailbox.cc
@@ -51,7 +51,7 @@ Mailboxes::_Print( std::ostream& s ) const
 
 //==============================================================================
 
-MailboxesWithStorage::MailboxesWithStorage(long mailboxBase, long numberOfLocalMailboxes, Mailboxes* parent, Memory* memory) :
+MailboxesWithStorage::MailboxesWithStorage(int32 mailboxBase, int32 numberOfLocalMailboxes, Mailboxes* parent, Memory* memory) :
     _mailboxBase(mailboxBase),
     // Default `memory` is HALLmalloc, which is fine for the long-lived
     // global/persistent/scratch instances created in deterministic order at
@@ -76,7 +76,7 @@ MailboxesWithStorage::~MailboxesWithStorage()
 }
 
 Scalar 
-MailboxesWithStorage::ReadMailbox(long mailbox) const
+MailboxesWithStorage::ReadMailbox(int32 mailbox) const
 {
     if(mailbox >= _mailboxBase && mailbox < _localMailboxes.Size()+_mailboxBase)
     {
@@ -93,7 +93,7 @@ MailboxesWithStorage::ReadMailbox(long mailbox) const
 }
 
 void 
-MailboxesWithStorage::WriteMailbox(long mailbox, Scalar value)
+MailboxesWithStorage::WriteMailbox(int32 mailbox, Scalar value)
 {
     if(mailbox >= _mailboxBase && mailbox < _localMailboxes.Size()+_mailboxBase)
     {
diff --git a/wfsource/source/mailbox/mailbox.hp b/wfsource/source/mailbox/mailbox.hp
index 183807a..3329e91 100644
--- a/wfsource/source/mailbox/mailbox.hp
+++ b/wfsource/source/mailbox/mailbox.hp
@@ -59,8 +59,8 @@ class Mailboxes
 {
 public:
    virtual ~Mailboxes();
-   virtual Scalar ReadMailbox(long mailbox) const = 0;
-   virtual void WriteMailbox(long mailbox, Scalar value) = 0;
+   virtual Scalar ReadMailbox(int32 mailbox) const = 0;
+   virtual void WriteMailbox(int32 mailbox, Scalar value) = 0;
 #if SW_DBSTREAM
 	friend std::ostream& operator <<( std::ostream& s, const Mailboxes& mailboxes );
 #endif
@@ -80,16 +80,16 @@ public:
    // mailboxes. Per-actor ActorMailboxes (created mid-Level-construction and
    // destroyed mid-teardown) MUST pass the per-level pool so HALLmalloc's
    // LIFO discipline stays intact — see actor.cc.
-   MailboxesWithStorage(long mailboxBase, long numberOfLocalMailboxes, Mailboxes* parent, Memory* memory = &HALLmalloc);
+   MailboxesWithStorage(int32 mailboxBase, int32 numberOfLocalMailboxes, Mailboxes* parent, Memory* memory = &HALLmalloc);
    ~MailboxesWithStorage();
-   virtual Scalar ReadMailbox(long mailbox) const;
-   virtual void WriteMailbox(long mailbox, Scalar value);
+   virtual Scalar ReadMailbox(int32 mailbox) const;
+   virtual void WriteMailbox(int32 mailbox, Scalar value);
 protected:
 #if SW_DBSTREAM
     virtual void _Print(std::ostream& s) const;
 #endif
 private:
-   long _mailboxBase;
+   int32 _mailboxBase;
    Array<Scalar>  _localMailboxes;
    Mailboxes* _parent;
 };
diff --git a/wfsource/source/memory/lmalloc.cc b/wfsource/source/memory/lmalloc.cc
index 30920ef..553e6a8 100644
--- a/wfsource/source/memory/lmalloc.cc
+++ b/wfsource/source/memory/lmalloc.cc
@@ -55,7 +55,7 @@ struct FileLine
 		FREED = 'FREE',
 		CANARY_VALUE = (int32)0xDEADBEEF
 	};
-	long _state;
+	int32 _state;
 	int _size;			                // size of allocation (includes FileLine header + canary)
 #if LMALLOC_TRACK_LINE_AND_FILE
 	char* _file;						// file and line allocation occured on
diff --git a/wfsource/source/memory/realmalloc.cc b/wfsource/source/memory/realmalloc.cc
index d2e5ca0..eecfc9e 100755
--- a/wfsource/source/memory/realmalloc.cc
+++ b/wfsource/source/memory/realmalloc.cc
@@ -46,7 +46,7 @@ struct FileLine
 		ALLOCATED = 'ALOC',
 		FREED = 'FREE'
 	};
-	long _state;
+	int32 _state;
 	int _size;			                // size of allocation
 #if REALMALLOC_TRACK_LINE_AND_FILE
 	char* _file;						// file and line allocation occured on
diff --git a/wfsource/source/oas/oad.h b/wfsource/source/oas/oad.h
index aa2a287..303c72d 100644
--- a/wfsource/source/oas/oad.h
+++ b/wfsource/source/oas/oad.h
@@ -107,10 +107,10 @@ typedef enum
 
 typedef struct _oadHeader
 {
-	long chunkId;
-	long chunkSize;
+	int32 chunkId;		// 32-bit on disk (PSX/x86-32 origin); `long` was 8 bytes
+	int32 chunkSize;	// on LP64 and mis-sized the header (80 vs 92 bytes).
 	char name[72-4];
-	long version;
+	int32 version;
 } oadHeader;
 
 /*============================================================================*/
diff --git a/wfsource/source/oas/pigtool.h b/wfsource/source/oas/pigtool.h
index 1ecc059..aaa3cab 100644
--- a/wfsource/source/oas/pigtool.h
+++ b/wfsource/source/oas/pigtool.h
@@ -29,11 +29,24 @@
 #endif	/*!defined(SYS_UINT16)*/
 
 #ifndef	SYS_INT32
+#if defined(__LINUX__) || defined(__ANDROID__)
+// LP64: `long` is 8 bytes on x86-64 Linux/Android — use `int` so int32 stays
+// 32 bits (mirrors pigtypes.h). PSX/x86-32 had long==32, which is why the
+// original `long` worked there. Without this guard, any TU pulling pigtool.h
+// (via oad.h) before pigtypes.h gets a 64-bit int32 — e.g. it bloated
+// typeDescriptor by 12 bytes (3× int32 min/max/def), breaking .oad reads.
+#define	SYS_INT32		signed int
+#else
 #define	SYS_INT32		signed long
+#endif
 #endif	/*!defined(SYS_INT32)*/
 
 #ifndef	SYS_UINT32
+#if defined(__LINUX__) || defined(__ANDROID__)
+#define	SYS_UINT32		unsigned int
+#else
 #define	SYS_UINT32		unsigned long
+#endif
 #endif	/*!defined(SYS_UINT32)*/
 
 #ifndef	SYS_UCHAR
diff --git a/wfsource/source/renderassets/rendcrow.cc b/wfsource/source/renderassets/rendcrow.cc
index a66a11a..6693419 100755
--- a/wfsource/source/renderassets/rendcrow.cc
+++ b/wfsource/source/renderassets/rendcrow.cc
@@ -152,7 +152,7 @@ RenderActorScarecrow::RenderActorScarecrow(Memory& memory, binistream& input,int
 //				std::cout << " bitmapList = [" << bitmapList << ']' << std::endl;
 
 #if defined( USE_ASSET_ID )
-				_nTextures = chunkIter->Size() / sizeof( long );
+				_nTextures = chunkIter->Size() / sizeof( int32 );
 				_texture = new( memory )( Texture*[ _nTextures ] );
 				assert( ValidPtr( _texture ) );
 #else
diff --git a/wfsource/source/game/actor.cc b/wfsource/source/game/actor.cc
index f05dafd..30680e5 100644
--- a/wfsource/source/game/actor.cc
+++ b/wfsource/source/game/actor.cc
@@ -1676,10 +1697,15 @@ Actor::GetSpecialCollisionMessage(void * msgData, int32 maxsize)
 {
 	if ( GetMsgPort().GetMsgByType( MsgPort::SPECIAL_COLLISION, msgData,maxsize) )
 	{
-		// re-check this collision to make sure it's still valid
-		const PhysicalAttributes& colAttr = ((Actor*)msgData)->GetPhysicalAttributes();
+		// re-check this collision to make sure it's still valid.
+		// msgData holds an Actor* posted by collision.cc as
+		// reinterpret_cast<uintptr_t>(&object) — read the pointer FROM the
+		// buffer, not (Actor*)msgData (which mis-read the buffer bytes as an
+		// Actor). Keep the pointer optimization (06373f5); just interpret it
+		// correctly, and invalidate via the pointer-width word, not `long`.
+		const PhysicalAttributes& colAttr = reinterpret_cast<Actor*>(*(uintptr_t*)msgData)->GetPhysicalAttributes();
 		if ( !(_physicalAttributes.CheckCollision(colAttr)) )
-			*(long*)msgData = 0;
+			*(uintptr_t*)msgData = 0;
 		return true;
 	}
 	else
@@ -1832,7 +1858,7 @@ Actor::GetMailboxes() const
 }
 
 
-ActorMailboxes::ActorMailboxes(Actor& actor,long mailboxesBase, long numberOfLocalMailboxes, Mailboxes* parent) :
+ActorMailboxes::ActorMailboxes(Actor& actor,int32 mailboxesBase, int32 numberOfLocalMailboxes, Mailboxes* parent) :
 // Route _localMailboxes through the per-level _memory pool (DMalloc), not
 // the default HALLmalloc. Actors are constructed mid-Level-loading and
 // destroyed mid-Level-teardown — their HALLmalloc-backed sub-allocations
@@ -1849,7 +1875,7 @@ ActorMailboxes::~ActorMailboxes()
 }
 
 Scalar 
-ActorMailboxes::ReadMailbox(long mailbox) const
+ActorMailboxes::ReadMailbox(int32 mailbox) const
 {
     if(mailbox >= EMAILBOX_LOCAL_SYSTEM_START && mailbox < EMAILBOX_LOCAL_SYSTEM_MAX)
         return _actor.ReadSystemMailbox(mailbox);
@@ -1859,7 +1885,7 @@ ActorMailboxes::ReadMailbox(long mailbox) const
 
 
 void 
-ActorMailboxes::WriteMailbox(long mailbox, Scalar value)
+ActorMailboxes::WriteMailbox(int32 mailbox, Scalar value)
 {
     if(mailbox >= EMAILBOX_LOCAL_SYSTEM_START && mailbox < EMAILBOX_LOCAL_SYSTEM_MAX)
         _actor.WriteSystemMailbox(mailbox,value);
```

## Verification
- Full engine build (`task build`, ASan-default) green; **snowgoons + qbert boot and run** (the mailbox virtual-signature change is the delicate part — confirm scripts still read/write mailboxes correctly). Screenshot.
- OAD reader: after F1+F2, `sizeof(typeDescriptor)` is **1491** in a standalone `oad.h` compile (matches on-disk stride); the editor reader (explicit offsets) is unaffected either way.
- NDK/Android build green (LP64 there too).

## BUGS.md
Add an entry (per [feedback_bugs_md_pre2026_only](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_bugs_md_pre2026_only.md) — these `long`s originate in the 1995–99 PSX/x86-32 code, pre-2026; verify originating commit via `git blame`): the PSX/x86-32 `long`==32 assumption breaking on LP64, the systemic `pigtool.h` `int32`-width landmine, and the per-site fixes (F1–F6) + the `wfprim.h` dead-path TODO (F7).

## Cross-references
- **[Per-occurrence review](../investigations/2026-05-20-long-audit-review.md)** — every one of the 240 `long`s with context + disposition (✅changed / ⚪kept / ⚠️flagged / 💬false-positive), so the changes are checkable line-by-line. The ⚠️ section lists ~22 suspicious `long`s **not** changed this pass (e.g. `rendcrow.cc:155` `sizeof(long)` texture count, `pixelmap.cc:149`, `anim.cc:160-161`, `rendobj3.hp`, `sjoystic.h` button masks, `memory/*` allocator headers).
- Triggered by [editor property-panel plan](2026-05-20-editor-property-panel.md) (OAD reader). Prior spot-fixes: `ba3bbcb`, `06373f5`, `a743515`.
- Memory: [feedback_root_cause_not_symptom](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_root_cause_not_symptom.md), [feedback_bugs_md_pre2026_only](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_bugs_md_pre2026_only.md), [feedback_log_discoveries_in_todo](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_log_discoveries_in_todo.md), [project_mailboxes_fixed_point](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_mailboxes_fixed_point.md).
