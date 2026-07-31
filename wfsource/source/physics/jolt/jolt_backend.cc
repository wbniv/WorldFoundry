// jolt_backend.cc — Jolt Physics world singleton implementation.
//
// Owns the PhysicsSystem, TempAllocator, JobSystem, body registry, and the
// per-frame fixed-substep scheduler.  Compiled only with PHYSICS_ENGINE_JOLT.

#ifdef PHYSICS_ENGINE_JOLT

#include <physics/jolt/jolt_backend.hp>
#include <physics/jolt/jolt_math.hp>

#include <vector>
#include <memory>
#include <cstdio>
#include <cassert>
#include <limits>

// Jolt headers — must be included after the WF headers to avoid redefinition
// issues with standard types pulled in by pigsys.
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"
#pragma GCC diagnostic ignored "-Wmissing-field-initializers"
#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Physics/PhysicsSettings.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Collision/Shape/MeshShape.h>
#include <Jolt/Physics/Collision/Shape/ConvexHullShape.h>
#include <Jolt/Physics/Collision/Shape/ScaledShape.h>
#include <Jolt/Physics/Collision/Shape/CapsuleShape.h>
#include <Jolt/Physics/Collision/Shape/RotatedTranslatedShape.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Character/CharacterBase.h>
#include <Jolt/Physics/Character/CharacterVirtual.h>
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseQuery.h>
#include <Jolt/Physics/Vehicle/VehicleConstraint.h>
#include <Jolt/Physics/Vehicle/VehicleCollisionTester.h>
#include <Jolt/Physics/Vehicle/WheeledVehicleController.h>
#pragma GCC diagnostic pop

JPH_SUPPRESS_WARNINGS

// ---------------------------------------------------------------------------
// Layer setup — mirrors the selftest / physicstest pattern.

namespace WFPhysLayers
{
    static constexpr JPH::ObjectLayer STATIC  = 0;
    static constexpr JPH::ObjectLayer DYNAMIC = 1;
}

namespace WFBPLayers
{
    static constexpr JPH::BroadPhaseLayer NON_MOVING { 0 };
    static constexpr JPH::BroadPhaseLayer MOVING     { 1 };
}

class WFBPLayerInterface final : public JPH::BroadPhaseLayerInterface
{
public:
    WFBPLayerInterface()
    {
        mMap[WFPhysLayers::STATIC]  = WFBPLayers::NON_MOVING;
        mMap[WFPhysLayers::DYNAMIC] = WFBPLayers::MOVING;
    }
    JPH::uint            GetNumBroadPhaseLayers()                      const override { return 2; }
    JPH::BroadPhaseLayer GetBroadPhaseLayer(JPH::ObjectLayer l)        const override { return mMap[l]; }
private:
    JPH::BroadPhaseLayer mMap[2];
};

class WFObjVsBPFilter : public JPH::ObjectVsBroadPhaseLayerFilter
{
public:
    bool ShouldCollide(JPH::ObjectLayer l, JPH::BroadPhaseLayer bl) const override
    {
        if (l == WFPhysLayers::STATIC)  return bl == WFBPLayers::MOVING;
        if (l == WFPhysLayers::DYNAMIC) return true;
        return false;
    }
};

class WFObjPairFilter : public JPH::ObjectLayerPairFilter
{
public:
    bool ShouldCollide(JPH::ObjectLayer a, JPH::ObjectLayer b) const override
    {
        if (a == WFPhysLayers::STATIC)  return b == WFPhysLayers::DYNAMIC;
        if (a == WFPhysLayers::DYNAMIC) return true;
        return false;
    }
};

// ---------------------------------------------------------------------------
// Per-body registry entry — stores the Jolt body ID and cached pose/velocity
// so that accessors don't take Jolt locks on every read.

struct BodyEntry
{
    JPH::BodyID joltID;                     // The Jolt-assigned body identifier
    Vector3     posCache = Vector3::zero;   // Refreshed after each JoltWorldStep
    Vector3     velCache = Vector3::zero;
    Euler       rotCache = Euler::zero;
    void*       actor    = nullptr;         // Owning WF Actor; opaque to this layer
    bool        occupied = false;
};

// ---------------------------------------------------------------------------
// Module-level Jolt world state.

static WFBPLayerInterface        gBPLayerInterface;
static WFObjVsBPFilter           gObjVsBPFilter;
static WFObjPairFilter           gObjPairFilter;
static JPH::TempAllocatorImpl*   gTempAllocator = nullptr;
static JPH::JobSystemSingleThreaded* gJobSystem = nullptr;
static JPH::PhysicsSystem*       gPhysicsSystem = nullptr;
static JPH::BodyInterface*       gBodyInterface = nullptr;

static float gAccumulator = 0.0f;
static constexpr float kFixedStep   = 1.0f / 60.0f;
static constexpr int   kMaxSubsteps = 4;

// Body registry — indexed by the handle returned to callers.
static std::vector<BodyEntry> gBodies;

static const Vector3 kZeroVec = Vector3::zero;

// Jolt body-pool size — passed to PhysicsSystem::Init below. Captured as a
// file-scope constant so the pool-exhaustion log message can reference it
// without re-querying the PhysicsSystem.
static constexpr unsigned int kJoltBodyPoolMax = 1024;

// ---------------------------------------------------------------------------
// Internal helpers

static uint32_t AllocEntry()
{
    // Find a free slot.
    for (uint32_t i = 0; i < (uint32_t)gBodies.size(); ++i)
    {
        if (!gBodies[i].occupied)
            return i;
    }
    // Grow the table.
    gBodies.push_back(BodyEntry{});
    return (uint32_t)(gBodies.size() - 1);
}

static bool ValidHandle(uint32_t handle)
{
    return handle < (uint32_t)gBodies.size() && gBodies[handle].occupied;
}

static JPH::BodyID CreateJoltBodyImpl(const Vector3& pos, const Euler& rot,
                                       const Vector3& minPt, const Vector3& maxPt,
                                       JPH::EMotionType motionType,
                                       JPH::ObjectLayer layer)
{
    // Half-extents from AABB min/max in local space.
    Vector3 half = (maxPt - minPt) * Scalar(0.5f);
    Vector3 ctr  = minPt + half;

    JPH::Vec3 halfExt(
        std::max(0.01f, half.X().AsFloat()),
        std::max(0.01f, half.Y().AsFloat()),
        std::max(0.01f, half.Z().AsFloat())
    );

    // Body position = actor position + local box centre offset.
    // Rotation: WF's ColSpace is world-axis-aligned (ColBox stores world-space
    // min/max, never rotated), so the authored actor rotation must NOT be
    // applied to the Jolt shape — doing so would produce a larger, rotated
    // world AABB that doesn't match WF's collision geometry. Pass identity.
    (void)rot;
    JPH::RVec3 bodyPos = ToJph(pos + ctr);
    JPH::Quat  bodyRot = JPH::Quat::sIdentity();

    JPH::BodyCreationSettings cfg(
        new JPH::BoxShape(halfExt),
        bodyPos, bodyRot, motionType, layer
    );

    JPH::EActivation act = (motionType == JPH::EMotionType::Static)
                         ? JPH::EActivation::DontActivate
                         : JPH::EActivation::Activate;
    JPH::BodyID id = gBodyInterface->CreateAndAddBody(cfg, act);
    const char* mtName = (motionType == JPH::EMotionType::Static)  ? "STATIC"
                       : (motionType == JPH::EMotionType::Kinematic) ? "KINEMATIC"
                       : "DYNAMIC";
    std::fprintf(stderr, "jolt: body %s pos=(%.2f,%.2f,%.2f) half=(%.2f,%.2f,%.2f) id=%u\n",
        mtName,
        bodyPos.GetX(), bodyPos.GetY(), bodyPos.GetZ(),
        halfExt.GetX(), halfExt.GetY(), halfExt.GetZ(),
        id.GetIndexAndSequenceNumber());
    return id;
}

static JPH::BodyID CreateJoltBody(const Vector3& pos, const Euler& rot,
                                   const Vector3& minPt, const Vector3& maxPt,
                                   bool isStatic)
{
    JPH::EMotionType mt = isStatic ? JPH::EMotionType::Static : JPH::EMotionType::Dynamic;
    JPH::ObjectLayer  ol = isStatic ? WFPhysLayers::STATIC : WFPhysLayers::DYNAMIC;
    return CreateJoltBodyImpl(pos, rot, minPt, maxPt, mt, ol);
}

static JPH::BodyID CreateJoltBodyKinematic(const Vector3& pos, const Euler& rot,
                                            const Vector3& minPt, const Vector3& maxPt)
{
    // Kinematic bodies are moved by explicit SetPosition calls (WF drives them).
    // They don't receive gravity or impulses, but they collide with dynamic bodies.
    // Using DYNAMIC layer so they appear in the MOVING broadphase and collide
    // with static geometry for future ray cast / query use.
    return CreateJoltBodyImpl(pos, rot, minPt, maxPt,
                               JPH::EMotionType::Kinematic, WFPhysLayers::DYNAMIC);
}

// ---------------------------------------------------------------------------
// Public API

uint32_t JoltBodyCreate(const Vector3& pos, const Euler& rot,
                        const Vector3& minPt, const Vector3& maxPt)
{
    if (!gPhysicsSystem) return kJoltInvalidBodyID;
    // All actor bodies start as KINEMATIC — Jolt maintains the collision
    // structure but WF drives position/velocity via Update() each frame.
    // When CharacterVirtual is wired (Phase 3), PHYSICS actors will be
    // upgraded to DYNAMIC.
    JPH::BodyID id = CreateJoltBodyKinematic(pos, rot, minPt, maxPt);
    if (id.IsInvalid()) {
        std::fprintf(stderr,
            "jolt: body pool exhausted (max=%u); returning kJoltInvalidBodyID for JoltBodyCreate\n",
            kJoltBodyPoolMax);
        return kJoltInvalidBodyID;
    }
    uint32_t handle = AllocEntry();
    BodyEntry& e = gBodies[handle];
    e.joltID  = id;
    e.posCache = pos;
    e.velCache = Vector3::zero;
    e.rotCache = rot;
    e.occupied = true;
    return handle;
}

void JoltBodySetDynamic(uint32_t handle)
{
    if (!ValidHandle(handle)) return;
    BodyEntry& e = gBodies[handle];
    gBodyInterface->SetMotionType(e.joltID, JPH::EMotionType::Dynamic,
                                   JPH::EActivation::Activate);
    // Move to the MOVING broadphase layer so it collides with STATIC bodies.
    gBodyInterface->SetObjectLayer(e.joltID, WFPhysLayers::DYNAMIC);
    std::fprintf(stderr, "jolt: body %u → dynamic\n", handle);
}

uint32_t JoltBodyCreateStatic(const Vector3& pos, const Euler& rot,
                               const Vector3& minPt, const Vector3& maxPt)
{
    if (!gPhysicsSystem) return kJoltInvalidBodyID;
    JPH::BodyID id = CreateJoltBody(pos, rot, minPt, maxPt, /*isStatic=*/true);
    if (id.IsInvalid()) {
        std::fprintf(stderr,
            "jolt: body pool exhausted (max=%u); returning kJoltInvalidBodyID for JoltBodyCreateStatic\n",
            kJoltBodyPoolMax);
        return kJoltInvalidBodyID;
    }
    uint32_t handle = AllocEntry();
    BodyEntry& e = gBodies[handle];
    e.joltID  = id;
    e.posCache = pos;
    e.velCache = Vector3::zero;
    e.rotCache = rot;
    e.occupied = true;
    return handle;
}

uint32_t JoltBodyCreateStaticMesh(const Vector3& pos,
                                   const JoltMeshVertex* verts, int vertCount,
                                   const JoltMeshFace*   faces, int faceCount)
{
    if (!gPhysicsSystem) return kJoltInvalidBodyID;

    JPH::Vec3 worldOffset = ToJph(pos);
    std::fprintf(stderr, "jolt: mesh actor_pos=(%.3f,%.3f,%.3f)\n",
                 pos.X().AsFloat(), pos.Y().AsFloat(), pos.Z().AsFloat());

    // Use MeshShape — correctly handles flat and sloped surfaces.
    // Vertices are in actor-local space; body is placed at actor world position.
    // Add both windings so the surface is two-sided (ball can approach from either side).
    for (int i = 0; i < vertCount; i++) {
        std::fprintf(stderr, "jolt: mesh v%d local=(%.3f,%.3f,%.3f) world=(%.3f,%.3f,%.3f)\n",
                     i, verts[i].x, verts[i].y, verts[i].z,
                     verts[i].x + worldOffset.GetX(),
                     verts[i].y + worldOffset.GetY(),
                     verts[i].z + worldOffset.GetZ());
    }

    JPH::TriangleList triangles;
    triangles.reserve((size_t)(faceCount * 2));
    for (int i = 0; i < faceCount; i++) {
        const JoltMeshVertex& a = verts[faces[i].v0];
        const JoltMeshVertex& b = verts[faces[i].v1];
        const JoltMeshVertex& c = verts[faces[i].v2];
        triangles.push_back(JPH::Triangle(
            JPH::Float3(a.x, a.y, a.z),
            JPH::Float3(b.x, b.y, b.z),
            JPH::Float3(c.x, c.y, c.z)));
        // reverse winding for two-sided collision
        triangles.push_back(JPH::Triangle(
            JPH::Float3(a.x, a.y, a.z),
            JPH::Float3(c.x, c.y, c.z),
            JPH::Float3(b.x, b.y, b.z)));
    }

    JPH::MeshShapeSettings meshSettings(triangles);
    JPH::Shape::ShapeResult result = meshSettings.Create();
    if (result.HasError()) {
        std::fprintf(stderr, "jolt: MeshShape error: %s — falling back to bbox\n",
                     result.GetError().c_str());
        return kJoltInvalidBodyID;
    }

    // Body placed at actor world pos; shape uses actor-local vertex coords.
    JPH::BodyCreationSettings cfg(
        result.Get(),
        JPH::RVec3(worldOffset), JPH::Quat::sIdentity(),
        JPH::EMotionType::Static, WFPhysLayers::STATIC);

    JPH::BodyID id = gBodyInterface->CreateAndAddBody(cfg, JPH::EActivation::DontActivate);
    if (id.IsInvalid()) {
        std::fprintf(stderr,
            "jolt: body pool exhausted (max=%u); returning kJoltInvalidBodyID for JoltBodyCreateStaticMesh\n",
            kJoltBodyPoolMax);
        return kJoltInvalidBodyID;
    }
    std::fprintf(stderr, "jolt: body MESH_STATIC verts=%d faces=%d id=%u\n",
                 vertCount, faceCount, id.GetIndexAndSequenceNumber());

    uint32_t handle = AllocEntry();
    BodyEntry& e = gBodies[handle];
    e.joltID   = id;
    e.posCache = pos;
    e.velCache = Vector3::zero;
    e.rotCache = Euler(Angle::zero, Angle::zero, Angle::zero);
    e.occupied = true;
    return handle;
}

void JoltBodyDestroy(uint32_t handle)
{
    if (!ValidHandle(handle)) return;
    BodyEntry& e = gBodies[handle];
    // Belt-and-suspenders: if a registered entry's joltID is invalid (which
    // shouldn't be possible after the per-wrapper IsInvalid checks above),
    // skip the Jolt calls — RemoveBody(invalidID) segfaults inside
    // BodyManager::DestroyBodies. Still free the wrapper-handle slot.
    if (e.joltID.IsInvalid()) {
        e.occupied = false;
        return;
    }
    gBodyInterface->RemoveBody(e.joltID);
    gBodyInterface->DestroyBody(e.joltID);
    e.occupied = false;
}

const Vector3& JoltBodyGetPosition(uint32_t handle)
{
    if (!ValidHandle(handle)) return kZeroVec;
    return gBodies[handle].posCache;
}

Euler JoltBodyGetRotation(uint32_t handle)
{
    if (!ValidHandle(handle)) return Euler();
    return gBodies[handle].rotCache;
}

const Vector3& JoltBodyGetLinVelocity(uint32_t handle)
{
    if (!ValidHandle(handle)) return kZeroVec;
    return gBodies[handle].velCache;
}

void JoltBodySetPosition(uint32_t handle, const Vector3& pos)
{
    if (!ValidHandle(handle)) return;
    gBodies[handle].posCache = pos;
    gBodyInterface->SetPosition(gBodies[handle].joltID,
                                ToJph(pos), JPH::EActivation::Activate);
}

void JoltBodySetRotation(uint32_t handle, const Euler& rot)
{
    if (!ValidHandle(handle)) return;
    gBodies[handle].rotCache = rot;
    gBodyInterface->SetRotation(gBodies[handle].joltID,
                                ToJph(rot), JPH::EActivation::Activate);
}

void JoltBodySetLinVelocity(uint32_t handle, const Vector3& vel)
{
    if (!ValidHandle(handle)) return;
    gBodies[handle].velCache = vel;
    gBodyInterface->SetLinearVelocity(gBodies[handle].joltID, ToJph(vel));
}

void JoltBodyAddLinVelocity(uint32_t handle, const Vector3& delta)
{
    if (!ValidHandle(handle)) return;
    gBodies[handle].velCache = gBodies[handle].velCache + delta;
    gBodyInterface->AddLinearVelocity(gBodies[handle].joltID, ToJph(delta));
}

static void UpdateVehicleCaches();   // forward decl — defined after character section

void JoltWorldStep(float dt)
{
    if (!gPhysicsSystem) return;

    gAccumulator += dt;
    int nSteps = 0;
    while (gAccumulator >= kFixedStep && nSteps < kMaxSubsteps)
    {
        gPhysicsSystem->Update(kFixedStep, 1, gTempAllocator, gJobSystem);
        gAccumulator -= kFixedStep;
        ++nSteps;
    }

    // Refresh caches for all registered dynamic bodies.
    for (BodyEntry& e : gBodies)
    {
        if (!e.occupied) continue;
        JPH::EMotionType mt = gBodyInterface->GetMotionType(e.joltID);
        if (mt == JPH::EMotionType::Static) continue;

        JPH::RVec3 p = gBodyInterface->GetPosition(e.joltID);
        e.posCache = FromJph(JPH::Vec3(p));
        e.velCache = FromJph(gBodyInterface->GetLinearVelocity(e.joltID));
        e.rotCache = FromJph(gBodyInterface->GetRotation(e.joltID));
    }

    // Refresh vehicle position/rotation caches.
    UpdateVehicleCaches();

    // Substep telemetry: uncomment to debug scheduler stability.
    // if (nSteps > 0) std::fprintf(stderr, "jolt: step x%d (acc=%.4f)\n", nSteps, gAccumulator);
}

// ---------------------------------------------------------------------------
// CharacterVirtual registry — one entry per MOBILITY_PHYSICS actor.

// Forward decl — defined below; each character owns one listener instance
// so contact callbacks can identify their owning WF Actor without an extra
// reverse-lookup.
class WFCharContactListener;

struct CharEntry
{
    JPH::Ref<JPH::CharacterVirtual> character;
    Vector3 posCache = Vector3::zero;   // actor "feet" position (WF convention)
    Vector3 velCache = Vector3::zero;
    Vector3 ctr      = Vector3::zero;   // colspace centre offset: Jolt pos = actor pos + ctr
    void*   actor    = nullptr;         // Owning WF Actor; opaque to this layer
    std::unique_ptr<WFCharContactListener> listener;
    // Statics that enclose the character at spawn — "zone volume" StatPlats
    // wrapping the play area, not walkable geometry. IgnoreMultipleBodiesFilter
    // is non-copyable (CharEntry goes in a vector), so we hold the list and
    // construct a filter per-update.
    std::vector<JPH::BodyID> excludeBodies;
    bool    occupied = false;
};

static std::vector<CharEntry> gCharacters;

// Character only collides with STATIC world geometry (StatPlat bodies).
class WFCharObjLayerFilter : public JPH::ObjectLayerFilter {
public:
    bool ShouldCollide(JPH::ObjectLayer layer) const override {
        return layer == WFPhysLayers::STATIC;
    }
};
class WFCharBPLayerFilter : public JPH::BroadPhaseLayerFilter {
public:
    bool ShouldCollide(JPH::BroadPhaseLayer layer) const override {
        return layer == WFBPLayers::NON_MOVING;
    }
};
static WFCharObjLayerFilter gCharObjFilter;
static WFCharBPLayerFilter  gCharBPFilter;

// ---------------------------------------------------------------------------
// Contact dispatch — see comment in jolt_backend.hp § "Contact dispatch".
// One callback, set once by the engine at startup; each character's listener
// invokes it on every new/persisting contact so per-actor collision mailboxes
// (f4071a3) can be populated for Jolt-managed actors.

static JoltContactCallback gContactCallback = nullptr;

void JoltSetContactCallback(JoltContactCallback cb) { gContactCallback = cb; }

// Find the Actor* registered against a Jolt body ID. Returns nullptr if the
// body isn't tracked by BodyEntry (e.g. a static created outside gBodies).
static void* FindActorForBodyID(JPH::BodyID id)
{
    for (const BodyEntry& be : gBodies)
        if (be.occupied && be.joltID == id) return be.actor;
    return nullptr;
}

class WFCharContactListener : public JPH::CharacterContactListener
{
public:
    void* characterActor = nullptr;   // CharEntry::actor, cached at registration

    void OnContactAdded(const JPH::CharacterVirtual* /*inCharacter*/,
                        const JPH::BodyID&     inBodyID2,
                        const JPH::SubShapeID& /*inSubShapeID2*/,
                        JPH::RVec3Arg          /*inContactPosition*/,
                        JPH::Vec3Arg           inContactNormal,
                        JPH::CharacterContactSettings& /*ioSettings*/) override
    {
        if (!gContactCallback || !characterActor) return;
        void* otherActor = FindActorForBodyID(inBodyID2);
        // Jolt's listener already passes `-mContactNormal` (CharacterVirtual.cpp:516),
        // which equals `+penetrationAxis` — the direction the character pushes
        // against the contacted body. That's the WF convention: bump-from-below
        // delivers normal.Z > 0, landing-on-top delivers normal.Z < 0 (matching
        // Actor::Collision's existing `normal.Z < 0 → supportingObject` test).
        // No re-negation needed.
        Vector3 wfNormal = FromJph(inContactNormal);
        gContactCallback(characterActor, otherActor, wfNormal);
    }

    // OnContactPersisted is deliberately NOT routed to the dispatcher.
    // Persisted contacts fire every frame the contact is held (standing on
    // the ground, rubbing a wall) — if we called Actor::Collision each time
    // we'd continuously re-set Mario's supportingObject and re-write the
    // COLLIDER_IDX / COLLISION_NORMAL_* mailboxes. That over-writes the
    // ground-state tracking that drives GroundHandler ↔ AirHandler transitions
    // and the per-actor collision mailboxes lose their "fresh contact" signal
    // (Actor::StartFrame clears _lastColliderIdx each frame; we want the
    // mailbox to read non-zero only on the edge, not on every persisted tick).
    //
    // Edge-only semantics — only OnContactAdded routes through the dispatcher.
    // For "still in contact this tick" the script can re-derive from Jolt's
    // ground-state if needed.
};

// Public setters — keep the bridge from jolt_backend back to engine-side
// Actor* pointers so the listener can identify both sides.
void JoltCharacterSetActor(uint32_t handle, void* actor)
{
    if (handle >= (uint32_t)gCharacters.size() || !gCharacters[handle].occupied) return;
    gCharacters[handle].actor = actor;
    if (gCharacters[handle].listener)
        gCharacters[handle].listener->characterActor = actor;
}

void JoltBodySetActor(uint32_t handle, void* actor)
{
    if (handle >= (uint32_t)gBodies.size() || !gBodies[handle].occupied) return;
    gBodies[handle].actor = actor;
}

static uint32_t AllocCharEntry()
{
    for (uint32_t i = 0; i < (uint32_t)gCharacters.size(); ++i)
        if (!gCharacters[i].occupied) return i;
    gCharacters.push_back(CharEntry{});
    return (uint32_t)(gCharacters.size() - 1);
}

uint32_t JoltCharacterCreate(const Vector3& pos, const Euler& rot,
                              const Vector3& minPtIn, const Vector3& maxPtIn)
{
    if (!gPhysicsSystem) return kJoltInvalidBodyID;

    // Belt-and-braces fallback: if the authored ColSpace is still the
    // ColSpace::ColSpace() default (0,0,0)→(1,1,1), substitute a humanoid
    // Physics default. In practice this shouldn't trigger today — wf_blender
    // always exports a Global Bounding Box derived from the visual mesh AABB,
    // which the engine wires into _colSpace via actor.cc:OODMin/OODMax →
    // PhysicalAttributes::Construct → _colSpace.SetBox. Kept as a safety net
    // for hand-authored .lev files. See
    // docs/investigations/2026-05-17-colspace-authoring.md.
    Vector3 minPt = minPtIn;
    Vector3 maxPt = maxPtIn;
    if (minPt == Vector3::zero && maxPt == Vector3::one)
    {
        minPt = Vector3(Scalar(-0.5f), Scalar(-0.5f), Scalar( 0.0f));
        maxPt = Vector3(Scalar( 0.5f), Scalar( 0.5f), Scalar( 1.5f));
        std::fprintf(stderr,
            "jolt: character using physics-default ColSpace (1.0x1.0x1.5, feet-at-origin)"
            " — per-actor ColSpace authoring not yet wired (TODO)\n");
    }

    Vector3 half = (maxPt - minPt) * Scalar(0.5f);
    JPH::Vec3 halfExt(
        std::max(0.01f, half.X().AsFloat()),
        std::max(0.01f, half.Y().AsFloat()),
        std::max(0.01f, half.Z().AsFloat())
    );

    JPH::CharacterVirtualSettings settings;
    settings.mUp             = JPH::Vec3::sAxisZ();          // WF is Z-up
    settings.mMaxSlopeAngle  = JPH::DegreesToRadians(80.0f);

    // Build a Z-up capsule that fills the ColSpace AABB. JPH::CapsuleShape is
    // Y-axis-aligned by default (its cylinder runs along ±Y) — wrap it in a
    // RotatedTranslatedShape that rotates 90° about X so the cylinder runs
    // along ±Z, matching WF's Z-up world. Without this wrap the capsule's
    // height ends up sideways and the character behaves like a sphere of
    // radius=min(halfX,halfY) against the ground (the 2026-05-17 SMB W1-1
    // "Mario sinks to z=-0.67" bug).
    //
    // Total capsule extent (post-rotation) in Z = 2*(halfHeightOfCylinder +
    // radius), so halfHeight = halfZ - radius. If halfZ <= radiusXY (AABB is
    // wider than tall — short rolly actor), degenerate to a sphere of
    // radius=min(halfX,halfY,halfZ) to match the legacy single-radius-sphere
    // behaviour.
    float radiusXY = std::min(halfExt.GetX(), halfExt.GetY());
    if (halfExt.GetZ() > radiusXY)
    {
        float halfHeight = halfExt.GetZ() - radiusXY;
        JPH::Ref<JPH::Shape> capsuleY = new JPH::CapsuleShape(halfHeight, radiusXY);
        // Rotate Y-up capsule about +X by 90° → Z-up capsule.
        JPH::Quat zUp = JPH::Quat::sRotation(JPH::Vec3::sAxisX(), JPH::DegreesToRadians(90.0f));
        settings.mShape = new JPH::RotatedTranslatedShape(JPH::Vec3::sZero(), zUp, capsuleY);
    }
    else
    {
        float radius = std::min({halfExt.GetX(), halfExt.GetY(), halfExt.GetZ()});
        settings.mShape = new JPH::SphereShape(radius);
    }

    // Colspace centre in local space — same offset CreateJoltBodyImpl uses.
    // Jolt character position = actor_feet_pos + ctr.
    Vector3 ctr = minPt + half;
    JPH::RVec3 charPos = ToJph(pos + ctr);

    uint32_t handle = AllocCharEntry();
    CharEntry& e = gCharacters[handle];
    // WF's ColSpace is world-axis-aligned; do not apply the authored actor
    // rotation to the Jolt collision shape (see CreateJoltBodyImpl for the
    // same reasoning). The visual orientation is handled by WF separately.
    (void)rot;
    e.character = new JPH::CharacterVirtual(&settings, charPos, JPH::Quat::sIdentity(),
                                             0, gPhysicsSystem);
    e.posCache  = pos;
    e.velCache  = Vector3::zero;
    e.ctr       = ctr;
    e.occupied  = true;

    // Wire the per-character contact listener; populates the per-actor
    // collision mailboxes (f4071a3) for this Jolt-managed actor. The Actor*
    // is registered later via JoltCharacterSetActor (we don't have it here).
    e.listener = std::unique_ptr<WFCharContactListener>(new WFCharContactListener());
    e.character->SetListener(e.listener.get());
    std::fprintf(stderr, "jolt: character %u created at (%.2f, %.2f, %.2f) ctr=(%.2f,%.2f,%.2f)\n",
                 handle, pos.X().AsFloat(), pos.Y().AsFloat(), pos.Z().AsFloat(),
                 ctr.X().AsFloat(), ctr.Y().AsFloat(), ctr.Z().AsFloat());

    // Exclude "zone volume" StatPlats from this character's collision. WF
    // levels sometimes wrap the play area in a large box StatPlat that's
    // meant as a region marker, not as walkable geometry. Legacy WF's
    // swept-AABB collision resolved these benignly (pre-move overlap +
    // collision event with the real floor), but Jolt's CharacterVirtual
    // penetration recovery would pop the character up and out of the zone,
    // placing them above the real floor.
    //
    // A static that fully encloses the character's spawn AABB can't be a
    // floor or wall for this character — the character is inside the box
    // with clearance on every side. Mark those bodies as ignored for all
    // future character queries; Jolt will then only collide the character
    // with actual floors/walls, and normal penetration recovery + stick-
    // to-floor place the character on the nearest real surface.
    {
        const float charMinX = charPos.GetX() - halfExt.GetX();
        const float charMaxX = charPos.GetX() + halfExt.GetX();
        const float charMinY = charPos.GetY() - halfExt.GetY();
        const float charMaxY = charPos.GetY() + halfExt.GetY();
        const float charMinZ = charPos.GetZ() - halfExt.GetZ();
        const float charMaxZ = charPos.GetZ() + halfExt.GetZ();
        for (const BodyEntry& be : gBodies)
        {
            if (!be.occupied) continue;
            if (gBodyInterface->GetMotionType(be.joltID) != JPH::EMotionType::Static)
                continue;
            JPH::AABox aabb = gBodyInterface->GetTransformedShape(be.joltID).GetWorldSpaceBounds();
            JPH::Vec3 mn = aabb.mMin, mx = aabb.mMax;
            if (mn.GetX() <= charMinX && mx.GetX() >= charMaxX &&
                mn.GetY() <= charMinY && mx.GetY() >= charMaxY &&
                mn.GetZ() <= charMinZ && mx.GetZ() >= charMaxZ)
            {
                e.excludeBodies.push_back(be.joltID);
                std::fprintf(stderr, "jolt: character %u ignoring zone body id=%u\n",
                             handle, be.joltID.GetIndexAndSequenceNumber());
            }
        }
    }

    return handle;
}

void JoltCharacterDestroy(uint32_t handle)
{
    if (handle >= (uint32_t)gCharacters.size() || !gCharacters[handle].occupied) return;
    gCharacters[handle].character = nullptr;
    gCharacters[handle].occupied  = false;
}

const Vector3& JoltCharacterGetPosition(uint32_t handle)
{
    if (handle >= (uint32_t)gCharacters.size() || !gCharacters[handle].occupied) return kZeroVec;
    return gCharacters[handle].posCache;
}

const Vector3& JoltCharacterGetLinVelocity(uint32_t handle)
{
    if (handle >= (uint32_t)gCharacters.size() || !gCharacters[handle].occupied) return kZeroVec;
    return gCharacters[handle].velCache;
}

void JoltCharacterSetLinVelocity(uint32_t handle, const Vector3& vel)
{
    if (handle >= (uint32_t)gCharacters.size() || !gCharacters[handle].occupied) return;
    CharEntry& e = gCharacters[handle];
    e.velCache = vel;
    e.character->SetLinearVelocity(ToJph(vel));
}

void JoltCharacterSetPosition(uint32_t handle, const Vector3& pos)
{
    if (handle >= (uint32_t)gCharacters.size() || !gCharacters[handle].occupied) return;
    CharEntry& e = gCharacters[handle];
    e.posCache = pos;
    e.character->SetPosition(ToJph(pos + e.ctr));
}

void JoltCharacterUpdate(uint32_t handle, float dt)
{
    if (handle >= (uint32_t)gCharacters.size() || !gCharacters[handle].occupied) return;
    if (!gPhysicsSystem || !gTempAllocator) return;

    CharEntry& e = gCharacters[handle];

    // WF drives gravity via linVelocity — pass zero to Jolt so it isn't double-counted.
    JPH::Vec3 gravity = JPH::Vec3::sZero();

    JPH::CharacterVirtual::ExtendedUpdateSettings upd;
    // Z-up world: override the Y-up defaults.
    upd.mStickToFloorStepDown = JPH::Vec3(0.0f, 0.0f, -0.5f);
    upd.mWalkStairsStepUp     = JPH::Vec3(0.0f, 0.0f,  0.4f);

    JPH::ShapeFilter shapeFilter;

    JPH::IgnoreMultipleBodiesFilter bodyFilter;
    if (!e.excludeBodies.empty())
    {
        bodyFilter.Reserve((uint)e.excludeBodies.size());
        for (JPH::BodyID id : e.excludeBodies) bodyFilter.IgnoreBody(id);
    }

    e.character->ExtendedUpdate(dt, gravity, upd,
        gCharBPFilter, gCharObjFilter,
        bodyFilter, shapeFilter,
        *gTempAllocator);

    // Refresh caches: convert Jolt centre position back to WF actor feet position.
    JPH::RVec3 p = e.character->GetPosition();
    Vector3 newPos = FromJph(JPH::Vec3(p)) - e.ctr;

    // CharacterVirtual::GetLinearVelocity returns the input velocity we set, not the
    // Jolt-resolved velocity after floor/slope contact.  Use position delta to derive
    // actual velocity when grounded so gravity doesn't accumulate into the floor.
    e.velCache = FromJph(e.character->GetLinearVelocity());
    if (dt > 0.0f && e.character->GetGroundState() == JPH::CharacterBase::EGroundState::OnGround)
    {
        // On the ground, all three axes come from actual displacement.
        float invDt = 1.0f / dt;
        e.velCache.SetX((newPos.X() - e.posCache.X()) * Scalar(invDt));
        e.velCache.SetY((newPos.Y() - e.posCache.Y()) * Scalar(invDt));
        e.velCache.SetZ((newPos.Z() - e.posCache.Z()) * Scalar(invDt));
    }
    else if (dt > 0.0f)
    {
        // Airborne: all three axes from position delta so contacts (wall on
        // X/Y, ceiling/block-underside on +Z) zero out the blocked component
        // instead of letting the character stay welded to the surface with
        // a ghost input velocity. WF-side gravity then accumulates from the
        // actual post-contact state (0 on a fresh contact frame), so the
        // very next frame is already falling.
        float invDt = 1.0f / dt;
        e.velCache.SetX((newPos.X() - e.posCache.X()) * Scalar(invDt));
        e.velCache.SetY((newPos.Y() - e.posCache.Y()) * Scalar(invDt));
        e.velCache.SetZ((newPos.Z() - e.posCache.Z()) * Scalar(invDt));
    }

    e.posCache = newPos;

    // Log ball position every 30 ticks (~1 s at 30 fps).
    static uint32_t sTick = 0;
    if (handle == 0 && (++sTick % 30) == 0)
        std::fprintf(stderr, "ball pos: (%.3f, %.3f, %.3f)\n",
            newPos.X().AsFloat(), newPos.Y().AsFloat(), newPos.Z().AsFloat());
}

bool JoltCharacterIsOnGround(uint32_t handle)
{
    if (handle >= (uint32_t)gCharacters.size() || !gCharacters[handle].occupied) return false;
    return gCharacters[handle].character->GetGroundState() ==
           JPH::CharacterBase::EGroundState::OnGround;
}

Vector3 JoltCharacterGetGroundNormal(uint32_t handle)
{
    if (handle >= (uint32_t)gCharacters.size() || !gCharacters[handle].occupied)
        return Vector3(Scalar::zero, Scalar::zero, Scalar::one);
    JPH::Vec3 n = gCharacters[handle].character->GetGroundNormal();
    if (n.LengthSq() < 1e-6f) return Vector3(Scalar::zero, Scalar::zero, Scalar::one);
    return FromJph(n);
}

// ---------------------------------------------------------------------------
// WheeledVehicleController registry — one entry per MOBILITY_VEHICLE actor.

struct VehicleEntry
{
    JPH::Ref<JPH::VehicleConstraint> constraint;
    JPH::BodyID                      bodyID;
    Vector3 posCache = Vector3::zero;
    Euler   rotCache = Euler::zero;
    bool    occupied = false;
};

static std::vector<VehicleEntry> gVehicles;

static uint32_t AllocVehicleEntry()
{
    for (uint32_t i = 0; i < (uint32_t)gVehicles.size(); ++i)
        if (!gVehicles[i].occupied) return i;
    gVehicles.push_back(VehicleEntry{});
    return (uint32_t)(gVehicles.size() - 1);
}

uint32_t JoltVehicleCreate(const Vector3& pos, const Euler& rot,
                            const JoltVehicleConfig& cfg)
{
    if (!gPhysicsSystem) return kJoltInvalidBodyID;

    // Chassis rigid body.
    JPH::Vec3 halfExt(cfg.chassis_hx, cfg.chassis_hy, cfg.chassis_hz);
    JPH::BoxShapeSettings boxSettings(halfExt);
    boxSettings.mDensity = cfg.mass_kg / (8.0f * cfg.chassis_hx * cfg.chassis_hy * cfg.chassis_hz);
    JPH::ShapeRefC shape = boxSettings.Create().Get();

    // Raise the body so the wheel rest positions sit at terrain level.
    // The chassis origin is the geometric centre of the box; wheels attach
    // below it. We offset the spawn Z up by the wheel radius + a little.
    float spawnZ = pos.Z().AsFloat() + cfg.chassis_hz + cfg.wheel_radius * 0.5f;
    JPH::RVec3 jphPos(pos.X().AsFloat(), pos.Y().AsFloat(), spawnZ);
    JPH::Quat  jphRot = ToJph(rot);

    JPH::BodyCreationSettings bodySettings(
        shape, jphPos, jphRot,
        JPH::EMotionType::Dynamic,
        (JPH::ObjectLayer)WFPhysLayers::DYNAMIC);
    bodySettings.mGravityFactor      = fabsf(cfg.gravity_z) / 9.81f;
    bodySettings.mLinearDamping      = 0.2f;
    bodySettings.mAngularDamping     = 0.4f;
    bodySettings.mFriction           = 0.6f;

    JPH::Body* body = gBodyInterface->CreateBody(bodySettings);
    if (!body) { fprintf(stderr,"[jolt_vehicle] body create failed\n"); return kJoltInvalidBodyID; }
    gBodyInterface->AddBody(body->GetID(), JPH::EActivation::Activate);

    // VehicleConstraint settings.
    JPH::VehicleConstraintSettings vehicle;
    vehicle.mUp      = JPH::Vec3(0,0,1);
    vehicle.mForward = JPH::Vec3(1,0,0);

    // Suspension direction: downward (-Z in WF/Jolt).
    JPH::Vec3 suspDir(0.f, 0.f, -1.f);

    auto* ctrl = new JPH::WheeledVehicleControllerSettings;
    ctrl->mEngine.mMaxTorque  = cfg.max_torque_nm;
    ctrl->mEngine.mMinRPM     = 500.f;
    ctrl->mEngine.mMaxRPM     = 3000.f;
    ctrl->mTransmission.mGearRatios = { 3.0f };       // single forward gear
    ctrl->mTransmission.mReverseGearRatios = { -2.0f };
    ctrl->mTransmission.mMode = JPH::ETransmissionMode::Manual;
    vehicle.mController = ctrl;

    // Add wheels.
    for (int i = 0; i < cfg.num_wheels; ++i)
    {
        const JoltVehicleWheelCfg& wc = cfg.wheels[i];
        JPH::WheelSettingsWV* ws = new JPH::WheelSettingsWV;
        // Wheel attachment point: at the bottom of the chassis box minus clearance.
        ws->mPosition             = JPH::Vec3(wc.x, wc.y, -cfg.chassis_hz + 0.05f);
        ws->mSuspensionDirection  = suspDir;
        ws->mSteeringAxis         = JPH::Vec3(0,0,1);
        ws->mWheelUp              = JPH::Vec3(0,0,1);
        ws->mWheelForward         = JPH::Vec3(1,0,0);
        ws->mSuspensionMinLength  = 0.0f;
        ws->mSuspensionMaxLength  = cfg.wheel_radius * 0.8f;
        ws->mRadius               = cfg.wheel_radius;
        ws->mWidth                = cfg.wheel_half_width * 2.0f;
        ws->mMaxSteerAngle        = wc.steer ? cfg.max_steer_angle_rad : 0.0f;
        ws->mMaxHandBrakeTorque   = wc.steer ? 0.0f : 4000.f;
        vehicle.mWheels.push_back(ws);
    }

    JPH::Ref<JPH::VehicleConstraint> constraint = new JPH::VehicleConstraint(*body, vehicle);

    // Ray-cast collision tester: projects a ray from each wheel attachment point
    // downward to find the road surface. Layer filter: only hit STATIC geometry.
    auto* tester = new JPH::VehicleCollisionTesterRay(
        (JPH::ObjectLayer)WFPhysLayers::STATIC);
    constraint->SetVehicleCollisionTester(tester);

    gPhysicsSystem->AddConstraint(constraint);

    uint32_t handle = AllocVehicleEntry();
    VehicleEntry& e = gVehicles[handle];
    e.constraint = constraint;
    e.bodyID     = body->GetID();
    e.posCache   = Vector3(Scalar(pos.X()), Scalar(pos.Y()), Scalar(pos.Z()));
    e.rotCache   = rot;
    e.occupied   = true;
    return handle;
}

void JoltVehicleDestroy(uint32_t handle)
{
    if (handle >= (uint32_t)gVehicles.size() || !gVehicles[handle].occupied) return;
    VehicleEntry& e = gVehicles[handle];
    gPhysicsSystem->RemoveConstraint(e.constraint);
    gBodyInterface->RemoveBody(e.bodyID);
    gBodyInterface->DestroyBody(e.bodyID);
    e.constraint = nullptr;
    e.occupied   = false;
}

void JoltVehicleSetInput(uint32_t handle, float forward, float rightward, float brake)
{
    if (handle >= (uint32_t)gVehicles.size() || !gVehicles[handle].occupied) return;
    auto* ctrl = static_cast<JPH::WheeledVehicleController*>(
        gVehicles[handle].constraint->GetController());
    ctrl->SetDriverInput(forward, rightward, brake, 0.0f);
}

const Vector3& JoltVehicleGetPosition(uint32_t handle)
{
    if (handle >= (uint32_t)gVehicles.size() || !gVehicles[handle].occupied)
        return kZeroVec;
    return gVehicles[handle].posCache;
}

Euler JoltVehicleGetRotation(uint32_t handle)
{
    if (handle >= (uint32_t)gVehicles.size() || !gVehicles[handle].occupied)
        return Euler::zero;
    return gVehicles[handle].rotCache;
}

// Cache position/rotation each world step (called inside JoltWorldStep below).
static void UpdateVehicleCaches()
{
    for (VehicleEntry& e : gVehicles)
    {
        if (!e.occupied) continue;
        JPH::RVec3 p = gBodyInterface->GetCenterOfMassPosition(e.bodyID);
        JPH::Quat  q = gBodyInterface->GetRotation(e.bodyID);
        e.posCache = Vector3(Scalar(p.GetX()), Scalar(p.GetY()), Scalar(p.GetZ()));
        // Extract heading (Z-axis rotation) from quaternion → WF Euler C.
        e.rotCache = FromJph(q);
    }
}

// ---------------------------------------------------------------------------
// Init / shutdown — called by JoltRuntimeInit / JoltRuntimeShutdown (physics_jolt.cc)
// These are called from the existing lifecycle in scripting_stub.cc.

void JoltOptimizeBroadPhase()
{
    if (!gPhysicsSystem) return;
    gPhysicsSystem->OptimizeBroadPhase();
    std::fprintf(stderr, "jolt: OptimizeBroadPhase done (%zu static bodies)\n",
        []{
            size_t n = 0;
            for (const BodyEntry& e : gBodies)
                if (e.occupied) ++n;
            return n;
        }());
}

void JoltBackendInit()
{
    // 10 MB temp allocator (Jolt's recommended default); 1024 physics bodies;
    // large-enough body pairs / constraints. ContactConstraintManager grows
    // with body count + step substeps; 2 MB was not enough for snowgoons.
    // Bumped to 4096 on 2026-05-10 for qbert 1344-cube fan-out; reverted to
    // 1024 same day after Phase 1 cube consolidation dropped to 28 bodies.
    gTempAllocator = new JPH::TempAllocatorImpl(10 * 1024 * 1024);
    gJobSystem     = new JPH::JobSystemSingleThreaded(JPH::cMaxPhysicsJobs);
    gPhysicsSystem = new JPH::PhysicsSystem();
    gPhysicsSystem->Init(kJoltBodyPoolMax, 0, 4096, 4096,
                         gBPLayerInterface, gObjVsBPFilter, gObjPairFilter);
    gPhysicsSystem->SetGravity(JPH::Vec3(0.0f, 0.0f, -9.81f));
    gBodyInterface = &gPhysicsSystem->GetBodyInterface();
    gAccumulator   = 0.0f;
    gBodies.clear();
    std::fprintf(stderr, "jolt: backend ready (gravity -Z)\n");
}

void JoltBackendShutdown()
{
    // Destroy all registered bodies.
    for (BodyEntry& e : gBodies)
    {
        if (e.occupied)
        {
            if (!e.joltID.IsInvalid()) {
                gBodyInterface->RemoveBody(e.joltID);
                gBodyInterface->DestroyBody(e.joltID);
            }
            e.occupied = false;
        }
    }
    gBodies.clear();
    gCharacters.clear();
    gVehicles.clear();
    delete gPhysicsSystem; gPhysicsSystem = nullptr;
    delete gJobSystem;     gJobSystem     = nullptr;
    delete gTempAllocator; gTempAllocator = nullptr;
    gBodyInterface = nullptr;
}

#endif // PHYSICS_ENGINE_JOLT
