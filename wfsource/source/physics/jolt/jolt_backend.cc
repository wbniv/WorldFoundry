// jolt_backend.cc — Jolt Physics world singleton implementation.
//
// Owns the PhysicsSystem, TempAllocator, JobSystem, body registry, and the
// per-frame fixed-substep scheduler.  Compiled only with PHYSICS_ENGINE_JOLT.

#ifdef PHYSICS_ENGINE_JOLT

#include <physics/jolt/jolt_backend.hp>
#include <physics/jolt/jolt_math.hp>

#include <vector>
#include <cstdio>
#include <cassert>

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
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Character/CharacterBase.h>
#include <Jolt/Physics/Character/CharacterVirtual.h>
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
    JPH::BodyID joltID;       // The Jolt-assigned body identifier
    Vector3     posCache;     // Refreshed after each JoltWorldStep
    Vector3     velCache;
    Euler       rotCache;
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
    JPH::RVec3 bodyPos = ToJph(pos + ctr);
    JPH::Quat  bodyRot = ToJph(rot);

    JPH::BodyCreationSettings cfg(
        new JPH::BoxShape(halfExt),
        bodyPos, bodyRot, motionType, layer
    );

    JPH::EActivation act = (motionType == JPH::EMotionType::Static)
                         ? JPH::EActivation::DontActivate
                         : JPH::EActivation::Activate;
    return gBodyInterface->CreateAndAddBody(cfg, act);
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
    uint32_t handle = AllocEntry();
    BodyEntry& e = gBodies[handle];
    // All actor bodies start as KINEMATIC — Jolt maintains the collision
    // structure but WF drives position/velocity via Update() each frame.
    // When CharacterVirtual is wired (Phase 3), PHYSICS actors will be
    // upgraded to DYNAMIC.
    e.joltID  = CreateJoltBodyKinematic(pos, rot, minPt, maxPt);
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
    uint32_t handle = AllocEntry();
    BodyEntry& e = gBodies[handle];
    e.joltID  = CreateJoltBody(pos, rot, minPt, maxPt, /*isStatic=*/true);
    e.posCache = pos;
    e.velCache = Vector3::zero;
    e.rotCache = rot;
    e.occupied = true;
    return handle;
}

void JoltBodyDestroy(uint32_t handle)
{
    if (!ValidHandle(handle)) return;
    BodyEntry& e = gBodies[handle];
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

    // Substep telemetry: uncomment to debug scheduler stability.
    // if (nSteps > 0) std::fprintf(stderr, "jolt: step x%d (acc=%.4f)\n", nSteps, gAccumulator);
}

// ---------------------------------------------------------------------------
// CharacterVirtual registry — one entry per MOBILITY_PHYSICS actor.

struct CharEntry
{
    JPH::Ref<JPH::CharacterVirtual> character;
    Vector3 posCache;
    Vector3 velCache;
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

static uint32_t AllocCharEntry()
{
    for (uint32_t i = 0; i < (uint32_t)gCharacters.size(); ++i)
        if (!gCharacters[i].occupied) return i;
    gCharacters.push_back(CharEntry{});
    return (uint32_t)(gCharacters.size() - 1);
}

uint32_t JoltCharacterCreate(const Vector3& pos, const Euler& rot,
                              const Vector3& minPt, const Vector3& maxPt)
{
    if (!gPhysicsSystem) return kJoltInvalidBodyID;

    Vector3 half = (maxPt - minPt) * Scalar(0.5f);
    JPH::Vec3 halfExt(
        std::max(0.01f, half.X().AsFloat()),
        std::max(0.01f, half.Y().AsFloat()),
        std::max(0.01f, half.Z().AsFloat())
    );

    JPH::CharacterVirtualSettings settings;
    settings.mUp             = JPH::Vec3::sAxisZ();          // WF is Z-up
    settings.mMaxSlopeAngle  = JPH::DegreesToRadians(45.0f);
    settings.mShape          = new JPH::BoxShape(halfExt);

    uint32_t handle = AllocCharEntry();
    CharEntry& e = gCharacters[handle];
    e.character = new JPH::CharacterVirtual(&settings, ToJph(pos), ToJph(rot),
                                             0, gPhysicsSystem);
    e.posCache  = pos;
    e.velCache  = Vector3::zero;
    e.occupied  = true;
    std::fprintf(stderr, "jolt: character %u created at (%.2f, %.2f, %.2f)\n",
                 handle, pos.X().AsFloat(), pos.Y().AsFloat(), pos.Z().AsFloat());
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
    e.character->SetPosition(ToJph(pos));
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

    JPH::BodyFilter  bodyFilter;
    JPH::ShapeFilter shapeFilter;

    e.character->ExtendedUpdate(dt, gravity, upd,
        gCharBPFilter, gCharObjFilter,
        bodyFilter, shapeFilter,
        *gTempAllocator);

    // Refresh caches from the resolved state.
    JPH::RVec3 p = e.character->GetPosition();
    e.posCache = FromJph(JPH::Vec3(p));
    e.velCache = FromJph(e.character->GetLinearVelocity());
}

bool JoltCharacterIsOnGround(uint32_t handle)
{
    if (handle >= (uint32_t)gCharacters.size() || !gCharacters[handle].occupied) return false;
    return gCharacters[handle].character->GetGroundState() ==
           JPH::CharacterBase::EGroundState::OnGround;
}

// ---------------------------------------------------------------------------
// Init / shutdown — called by JoltRuntimeInit / JoltRuntimeShutdown (physics_jolt.cc)
// These are called from the existing lifecycle in scripting_stub.cc.

void JoltBackendInit()
{
    // 2 MB temp allocator; 1024 physics bodies; large-enough body pairs / constraints.
    gTempAllocator = new JPH::TempAllocatorImpl(2 * 1024 * 1024);
    gJobSystem     = new JPH::JobSystemSingleThreaded(JPH::cMaxPhysicsJobs);
    gPhysicsSystem = new JPH::PhysicsSystem();
    gPhysicsSystem->Init(1024, 0, 4096, 4096,
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
            gBodyInterface->RemoveBody(e.joltID);
            gBodyInterface->DestroyBody(e.joltID);
            e.occupied = false;
        }
    }
    gBodies.clear();
    gCharacters.clear();
    delete gPhysicsSystem; gPhysicsSystem = nullptr;
    delete gJobSystem;     gJobSystem     = nullptr;
    delete gTempAllocator; gTempAllocator = nullptr;
    gBodyInterface = nullptr;
}

#endif // PHYSICS_ENGINE_JOLT
