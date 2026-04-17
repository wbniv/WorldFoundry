# Plan: Fix COLLISION/SPECIAL_COLLISION message to carry full pointer

**Date:** 2026-04-17  
**Branch:** 2026-first-working-gap  
**Trigger:** 64-bit Android build exposed pointer→int32 truncation in collision dispatch

## The Bug

`DispatchCollisionMessages` (collision.cc:222) was designed to pass the colliding
object's address as message data so receivers can react to specific colliders:

```cpp
object1.sendMsg( msg1, int32(&object2) );  // TRUNCATES on 64-bit
```

Receivers like enemy.cc and explode.cc cast the buffer back to `Actor*`:

```cpp
char msgData[msgDataSize];
while ( _msgPort.GetMsgByType( MsgPort::SPECIAL_COLLISION, &msgData, msgDataSize ) )
{
    Actor* colActor = (Actor*)msgData;   // reads 4 bytes, ptr is 8 — WRONG
```

`SMsg::_data` is only 4 bytes (`int32` / `char binary[sizeof(Scalar)]`), so on
64-bit the pointer is both truncated on send and overflows the receive buffer.
COLLISION receivers that don't use the data are silently broken; SPECIAL_COLLISION
receivers that cast msgData to Actor* are reading garbage.

## Fix

### Step 1 — Expand `SMsg::_data` to pointer size (`msgport.hp`)

```cpp
union _data {
    uintptr_t _message;            // was int32
    char binary[sizeof(uintptr_t)]; // was sizeof(Scalar) = 4
} data;
```

`uintptr_t` is always the right size for a pointer on the current platform.
All existing integer senders (DELTA_HEALTH etc.) work correctly: small signed
ints sign-extend to 64 bits; the receiver reads `*(int32*)msgData` = low 4
bytes = original value (little-endian, same as always).

### Step 2 — Update `PutMsg` / `sendMsg` scalar overload (`msgport.hp`, `msgport.cc`, `baseobject.hp`, `baseobject.cc`)

Change `int32 msgData` → `uintptr_t msgData` in both declarations and definitions.
Callers passing small integers get implicit widening. Callers passing pointers
(only collision.cc) get the full address without truncation.

### Step 3 — Fix sender (`collision.cc`)

```cpp
object1.sendMsg( msg1, reinterpret_cast<uintptr_t>(&object2) );
object2.sendMsg( msg2, reinterpret_cast<uintptr_t>(&object1) );
```

### Step 4 — Fix receivers that cast msgData to Actor* (`enemy.cc`, `explode.cc`, `missile.cc`)

```cpp
Actor* colActor = reinterpret_cast<Actor*>(*(uintptr_t*)msgData);
```

### Step 5 — Receivers that eat COLLISION without reading data

`movement.cc`, `movepath.cc`, `movefoll.cc`, `movecam.cc` — no change needed;
they discard the buffer.

## Files Touched

| File | Change |
|------|--------|
| `baseobject/msgport.hp` | `SMsg::_data`: `int32`→`uintptr_t`, `binary[]` size; `PutMsg` signature |
| `baseobject/msgport.cc` | `PutMsg(int16, int32)` → `PutMsg(int16, uintptr_t)` |
| `baseobject/baseobject.hp` | `sendMsg(int16, int32)` → `sendMsg(int16, uintptr_t)` |
| `baseobject/baseobject.cc` | same |
| `physics/collision.cc` | `reinterpret_cast<uintptr_t>(&objectN)` |
| `game/enemy.cc` | `*(uintptr_t*)msgData` cast |
| `game/explode.cc` | same |
| `game/missile.cc` | same |
