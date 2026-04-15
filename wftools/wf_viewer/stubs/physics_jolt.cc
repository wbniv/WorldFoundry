// physics_jolt.cc — Jolt Physics runtime plug for WF.
//
// Owns:
//   JoltRuntimeInit()     — call once at engine startup (after subsystem init)
//   JoltRuntimeShutdown() — call once at engine shutdown (before memory release)
//
// At init time runs a self-contained smoke test: creates a PhysicsSystem,
// drops a sphere from height 10, steps 60 frames at 1/60 s, asserts it
// moved downward, prints "jolt: selftest ok".  If the assertion fails the
// process aborts — a broken Jolt build should never silently continue.
//
// This file is compiled only when WF_PHYSICS_ENGINE=jolt
// (-DPHYSICS_ENGINE_JOLT is in CXXFLAGS via build_game.sh).

#ifdef PHYSICS_ENGINE_JOLT

#include <cstdio>
#include <cassert>
#include <cmath>

// Jolt headers.  Silence all Jolt warnings — vendor code.
// JPH_ENABLE_ASSERTS is intentionally NOT defined here: the assert path
// requires a user-supplied AssertFailed function pointer.  The Jolt lib
// is built with NDEBUG so its JPH_ASSERT is already a no-op; matching
// that here avoids an unresolved-symbol error at link time.
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
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#pragma GCC diagnostic pop

JPH_SUPPRESS_WARNINGS

// ---------------------------------------------------------------------------
// Minimal layer setup (two layers: STATIC / DYNAMIC).

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
    JPH::uint            GetNumBroadPhaseLayers()                           const override { return 2; }
    JPH::BroadPhaseLayer GetBroadPhaseLayer(JPH::ObjectLayer l)             const override { return mMap[l]; }
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
// Selftest: drop a sphere from Z=10, step 60 frames, assert it fell.

static void RunSelftest()
{
    JPH::TempAllocatorImpl   tmpAlloc(2 * 1024 * 1024); // 2 MB
    JPH::JobSystemSingleThreaded jobSys(JPH::cMaxPhysicsJobs);

    WFBPLayerInterface bpIface;
    WFObjVsBPFilter    bpFilter;
    WFObjPairFilter    objFilter;

    JPH::PhysicsSystem ps;
    ps.Init(64, 0, 64, 64, bpIface, bpFilter, objFilter);
    ps.SetGravity(JPH::Vec3(0.0f, 0.0f, -9.81f));

    JPH::BodyInterface& bi = ps.GetBodyInterface();

    // Static floor at Z=0.
    JPH::BodyCreationSettings floorCfg(
        new JPH::BoxShape(JPH::Vec3(50.0f, 50.0f, 0.5f)),
        JPH::RVec3(0.0f, 0.0f, -0.5f),
        JPH::Quat::sIdentity(),
        JPH::EMotionType::Static,
        WFPhysLayers::STATIC
    );
    JPH::BodyID floorID = bi.CreateAndAddBody(floorCfg, JPH::EActivation::DontActivate);

    // Dynamic sphere at Z=10.
    JPH::BodyCreationSettings sphereCfg(
        new JPH::SphereShape(0.5f),
        JPH::RVec3(0.0f, 0.0f, 10.0f),
        JPH::Quat::sIdentity(),
        JPH::EMotionType::Dynamic,
        WFPhysLayers::DYNAMIC
    );
    JPH::BodyID sphereID = bi.CreateAndAddBody(sphereCfg, JPH::EActivation::Activate);

    const float kStep = 1.0f / 60.0f;
    for (int i = 0; i < 60; ++i)
        ps.Update(kStep, 1, &tmpAlloc, &jobSys);

    float finalZ = static_cast<float>(bi.GetPosition(sphereID).GetZ());
    assert(finalZ < 10.0f && "jolt selftest: sphere did not fall");

    bi.RemoveBody(sphereID);  bi.DestroyBody(sphereID);
    bi.RemoveBody(floorID);   bi.DestroyBody(floorID);

    std::fprintf(stderr, "jolt: selftest ok (sphere fell to z=%.3f)\n", finalZ);
}

// ---------------------------------------------------------------------------
// Public lifecycle functions — called by ScriptRouter ctor/dtor pattern.

void JoltRuntimeInit()
{
    std::fprintf(stderr, "jolt: RegisterDefaultAllocator\n");
    JPH::RegisterDefaultAllocator();
    std::fprintf(stderr, "jolt: Factory\n");
    JPH::Factory::sInstance = new JPH::Factory();
    std::fprintf(stderr, "jolt: RegisterTypes\n");
    JPH::RegisterTypes();
    std::fprintf(stderr, "jolt: RunSelftest\n");
    RunSelftest();
    std::fprintf(stderr, "jolt: init complete\n");
}

void JoltRuntimeShutdown()
{
    JPH::UnregisterTypes();
    delete JPH::Factory::sInstance;
    JPH::Factory::sInstance = nullptr;
}

#endif // PHYSICS_ENGINE_JOLT
