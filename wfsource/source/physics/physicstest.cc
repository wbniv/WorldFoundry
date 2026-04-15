//=============================================================================
// physicstest.cc:
// Copyright ( c ) 2002,2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// This program is free software; you can redistribute it and/or
// modify it under the terms of the GNU General Public License
// Version 2 as published by the Free Software Foundation
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
// or see www.fsf.org

// ===========================================================================
// Description: Test physics subsystem — ported from ODE to Jolt Physics.
//              Objects fall under gravity, land on a static floor, and are
//              visualised via the WF rendering pipeline.
//              Requires WF_PHYSICS_ENGINE=jolt (-DPHYSICS_ENGINE_JOLT).
// Original Author: Kevin T. Seghetti
// Jolt port: 2026
//=============================================================================

#include <pigsys/pigsys.hp>
#include <baseobject/msgport.hp>
#include "physical.hp"
#include "colbox.hp"
#include "colspace.hp"
#include <list>

#define TEST_TEXTURES 1

//=============================================================================

#include <hal/hal.h>
#include <math/scalar.hp>
#include <math/vector3.hp>
#include <math/angle.hp>
#include <iff/iffread.hp>
#include <gfx/display.hp>
#include <gfx/viewport.hp>
#include <gfx/material.hp>
#include <gfx/rendobj3.hp>
#include <gfx/camera.hp>
#include <gfx/vertex.hp>
#include <gfx/texture.hp>
#include <gfx/pixelmap.hp>
#include <cpplib/stdstrm.hp>
#include <cpplib/strmnull.hp>

#ifdef PHYSICS_ENGINE_JOLT
// Jolt headers — must come after stdint.h / stdbool.h (pulled in above).
// Disable Jolt assertions in release; mirror WF's DO_ASSERTIONS setting.
#if DO_ASSERTIONS
#  define JPH_ENABLE_ASSERTS
#endif
#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Physics/PhysicsSettings.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/PlaneShape.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Body/BodyActivationListener.h>
#include <Jolt/Physics/Character/CharacterVirtual.h>

JPH_SUPPRESS_WARNINGS

// -----------------------------------------------------------------------
// Layer definitions — two layers: STATIC (non-moving) and DYNAMIC (moving).
namespace PhysLayers
{
    static constexpr JPH::ObjectLayer STATIC  = 0;
    static constexpr JPH::ObjectLayer DYNAMIC = 1;
    static constexpr JPH::uint        COUNT   = 2;
}

namespace BPLayers
{
    static constexpr JPH::BroadPhaseLayer NON_MOVING { 0 };
    static constexpr JPH::BroadPhaseLayer MOVING     { 1 };
    static constexpr JPH::uint            COUNT      = 2;
}

class BPLayerInterfaceImpl final : public JPH::BroadPhaseLayerInterface
{
public:
    BPLayerInterfaceImpl()
    {
        mObjectToBP[PhysLayers::STATIC]  = BPLayers::NON_MOVING;
        mObjectToBP[PhysLayers::DYNAMIC] = BPLayers::MOVING;
    }
    JPH::uint          GetNumBroadPhaseLayers() const override { return BPLayers::COUNT; }
    JPH::BroadPhaseLayer GetBroadPhaseLayer(JPH::ObjectLayer l) const override { return mObjectToBP[l]; }
#if defined(JPH_EXTERNAL_PROFILE) || defined(JPH_PROFILE_ENABLED)
    const char* GetBroadPhaseLayerName(JPH::BroadPhaseLayer l) const override
    {
        return (l == BPLayers::NON_MOVING) ? "NON_MOVING" : "MOVING";
    }
#endif
private:
    JPH::BroadPhaseLayer mObjectToBP[PhysLayers::COUNT];
};

class ObjVsBPFilterImpl : public JPH::ObjectVsBroadPhaseLayerFilter
{
public:
    bool ShouldCollide(JPH::ObjectLayer l, JPH::BroadPhaseLayer bl) const override
    {
        switch (l)
        {
            case PhysLayers::STATIC:  return bl == BPLayers::MOVING;
            case PhysLayers::DYNAMIC: return true;
            default: return false;
        }
    }
};

class ObjPairFilterImpl : public JPH::ObjectLayerPairFilter
{
public:
    bool ShouldCollide(JPH::ObjectLayer a, JPH::ObjectLayer b) const override
    {
        switch (a)
        {
            case PhysLayers::STATIC:  return b == PhysLayers::DYNAMIC;
            case PhysLayers::DYNAMIC: return true;
            default: return false;
        }
    }
};

#endif // PHYSICS_ENGINE_JOLT

#ifdef MSVC
#pragma warning(disable:4244 4305)
#endif

//=============================================================================
// Forward declaration so TestObject can take a BodyInterface reference.

#ifdef PHYSICS_ENGINE_JOLT
class GFXTester;
#endif

//=============================================================================

struct TestObject
{
#ifdef PHYSICS_ENGINE_JOLT
    TestObject(JPH::BodyInterface& bi,
               const Vector3& position, const Euler& rotation,
               const Vector3& min, const Vector3& max)
        : _bi(&bi)
    {
        _physical.Construct(position, rotation, min, max);

        // Half-extents from the bounding box.
        JPH::Vec3 half(
            ((max.X() - min.X()) * Scalar::half).AsFloat(),
            ((max.Y() - min.Y()) * Scalar::half).AsFloat(),
            ((max.Z() - min.Z()) * Scalar::half).AsFloat()
        );
        JPH::BodyCreationSettings settings(
            new JPH::BoxShape(half),
            JPH::RVec3(position.X().AsFloat(),
                       position.Y().AsFloat(),
                       position.Z().AsFloat()),
            JPH::Quat::sIdentity(),
            JPH::EMotionType::Dynamic,
            PhysLayers::DYNAMIC
        );
        _bodyID = _bi->CreateAndAddBody(settings, JPH::EActivation::Activate);
    }

    ~TestObject()
    {
        if (_bi && !_bodyID.IsInvalid())
        {
            _bi->RemoveBody(_bodyID);
            _bi->DestroyBody(_bodyID);
        }
    }

    // Pull current Jolt position back into WF's PhysicalAttributes.
    void SyncFromJolt()
    {
        if (!_bi || _bodyID.IsInvalid()) return;
        JPH::RVec3 pos = _bi->GetPosition(_bodyID);
        _physical.SetPosition(Vector3(
            Scalar::FromFloat(static_cast<float>(pos.GetX())),
            Scalar::FromFloat(static_cast<float>(pos.GetY())),
            Scalar::FromFloat(static_cast<float>(pos.GetZ()))
        ));
        // Rotation sync omitted for now — physicstest visualises axis-aligned boxes.
    }

    JPH::BodyID       _bodyID;
    JPH::BodyInterface* _bi = nullptr;
#else  // no Jolt — fall-back stub (never compiled in game build)
    TestObject(const Vector3& position, const Euler& rotation,
               const Vector3& min, const Vector3& max)
    {
        _physical.Construct(position, rotation, min, max);
    }
#endif

    RenderObject3D*   object3D = nullptr;
    PhysicalAttributes _physical;
};

//==============================================================================

typedef std::list<TestObject*>::iterator TestObjectIter;

//==============================================================================

class GFXTester
{
public:
    GFXTester();
    ~GFXTester();
    void Update();
    void Render();
    void PageFlip();
    void CreateObject();

    std::list<TestObject*> testObjects;

private:
    Vertex3D* MakeCube(Memory& memory, const Vector3& min, const Vector3& max);

    LMalloc  testMemory;
    Display  display;
    PixelMap vram;
    ViewPort vp;

    IJoystick         joy1, joy2;
    joystickButtonsF  buttons1, buttons2;

    Vertex3D   cubeVertexList[8];
    TriFace    cubeFaceList[13];
    Material   cubeMaterialList[6];
    Material   cube2MaterialList[6];

    RenderCamera camera;
    Vector3      cameraPosition;
    Euler        cameraRotation;

#ifdef PHYSICS_ENGINE_JOLT
    // Jolt world state — owned by GFXTester.
    BPLayerInterfaceImpl               _bpLayerInterface;
    ObjVsBPFilterImpl                  _bpFilter;
    ObjPairFilterImpl                  _objectFilter;
    JPH::TempAllocatorImpl             _tempAllocator;
    JPH::JobSystemSingleThreaded       _jobSystem;
    JPH::PhysicsSystem                 _physicsSystem;
    JPH::BodyID                        _floorBodyID;

    // Accumulated time for fixed-step substepping (see project memory: variable
    // tick rate is load-bearing — never feed Jolt a raw variable dt).
    float _accumulator = 0.0f;
    static constexpr float kFixedStep = 1.0f / 60.0f;
#endif
};

static GFXTester* tester;

//==========================================================================

static Texture dummyTexture = {"",0,320,0,64,64};
PixelMap* testTexture  = nullptr;
PixelMap* test2Texture = nullptr;

class GfxTestCallbacks : public GfxCallbacks
{
public:
    GfxTestCallbacks() {}
    virtual ~GfxTestCallbacks() {}
    virtual LookupTextureStruct LookupTexture(const char* /*name*/, int32 /*userData*/) const
    {
        assert(testTexture);
        return LookupTextureStruct(dummyTexture, *testTexture);
    }
protected:
    virtual void _Validate() const {}
};

//=============================================================================

void
AdjustCameraParameters(Vector3& position, Euler& rotation, joystickButtonsF buttons1)
{
#define ADJUST_ANGLE 1
#define ADJUST_DELTA 0.05

    static int oldButtons = 0;
    int buttonsDown = buttons1 & (oldButtons ^ buttons1);
    oldButtons = buttons1;

    if (buttonsDown & EJ_BUTTONF_A)
        tester->CreateObject();

    if (buttons1 & EJ_BUTTONF_E)
        rotation.SetA(rotation.GetA() + Angle(Angle::Degree(SCALAR_CONSTANT(ADJUST_ANGLE))));
    if (buttons1 & EJ_BUTTONF_D)
        rotation.SetB(rotation.GetB() - Angle(Angle::Degree(SCALAR_CONSTANT(ADJUST_ANGLE))));
    if (buttons1 & EJ_BUTTONF_B)
        rotation.SetB(rotation.GetB() + Angle(Angle::Degree(SCALAR_CONSTANT(ADJUST_ANGLE))));
    if (buttons1 & EJ_BUTTONF_C)
        rotation.SetC(rotation.GetC() - Angle(Angle::Degree(SCALAR_CONSTANT(ADJUST_ANGLE))));
    if (buttons1 & EJ_BUTTONF_F)
        rotation.SetC(rotation.GetC() + Angle(Angle::Degree(SCALAR_CONSTANT(ADJUST_ANGLE))));

    if (buttons1 & EJ_BUTTONF_UP)
        position.SetY(position.Y() + SCALAR_CONSTANT(ADJUST_DELTA));
    if (buttons1 & EJ_BUTTONF_DOWN)
        position.SetY(position.Y() - SCALAR_CONSTANT(ADJUST_DELTA));
    if (buttons1 & EJ_BUTTONF_LEFT)
        position.SetX(position.X() - SCALAR_CONSTANT(ADJUST_DELTA));
    if (buttons1 & EJ_BUTTONF_RIGHT)
        position.SetX(position.X() + SCALAR_CONSTANT(ADJUST_DELTA));
    if (buttons1 & EJ_BUTTONF_G)
        position.SetZ(position.Z() - SCALAR_CONSTANT(ADJUST_DELTA));
    if (buttons1 & EJ_BUTTONF_H)
        position.SetZ(position.Z() + SCALAR_CONSTANT(ADJUST_DELTA));
}

//=============================================================================

#if TEST_TEXTURES

const int BUFFER_SIZE = 100 * 101;
long unsigned int* buffer[BUFFER_SIZE];

#if !DO_DEBUG_FILE_SYSTEM
#include "testtga.c"
#endif

void
LoadTextures(PixelMap& /*vram*/)
{
#if defined(VIDEO_MEMORY_IN_ONE_PIXELMAP)
    testTexture = new PixelMap(vram, 320, 0, 64, 64);
#else
    testTexture = new PixelMap(PixelMap::MEMORY_VIDEO, 64, 64);
#endif

#if !DO_DEBUG_FILE_SYSTEM
    binistream texturestream((const void*)test, testSize);
#else
    binistream texturestream("../gfx/test.tga");
#endif
    LoadTexture(texturestream, *testTexture);

#if !DO_DEBUG_FILE_SYSTEM
    assert(0);
    test2Texture = testTexture;
#else
#if defined(VIDEO_MEMORY_IN_ONE_PIXELMAP)
    test2Texture = new PixelMap(vram, 384, 0, 256, 256);
#else
    test2Texture = new PixelMap(PixelMap::MEMORY_VIDEO, 256, 256);
#endif
    assert(test2Texture);
    binistream texture2stream("../gfx/test2.tga");
    LoadTexture(texture2stream, *test2Texture);
#endif
}
#endif // TEST_TEXTURES

//==============================================================================

Vertex3D*
GFXTester::MakeCube(Memory& memory, const Vector3& min, const Vector3& max)
{
    Vertex3D* vertexList = new (memory) Vertex3D[8];
    assert(ValidPtr(vertexList));

    memcpy(vertexList, cubeVertexList, sizeof(Vertex3D) * 8);

    vertexList[0].position = Vector3ToPS(Vector3(min.X(), min.Y(), max.Z()));
    vertexList[1].position = Vector3ToPS(Vector3(max.X(), min.Y(), max.Z()));
    vertexList[2].position = Vector3ToPS(Vector3(min.X(), min.Y(), min.Z()));
    vertexList[3].position = Vector3ToPS(Vector3(max.X(), min.Y(), min.Z()));
    vertexList[4].position = Vector3ToPS(Vector3(min.X(), max.Y(), max.Z()));
    vertexList[5].position = Vector3ToPS(Vector3(max.X(), max.Y(), max.Z()));
    vertexList[6].position = Vector3ToPS(Vector3(max.X(), max.Y(), min.Z()));
    vertexList[7].position = Vector3ToPS(Vector3(min.X(), max.Y(), min.Z()));

    return vertexList;
}

//=============================================================================

void
GFXTester::CreateObject()
{
    Vector3 max = Vector3(Scalar::Random(SCALAR_CONSTANT(0.1), SCALAR_CONSTANT(0.35)),
                          Scalar::Random(SCALAR_CONSTANT(0.1), SCALAR_CONSTANT(0.35)),
                          Scalar::Random(SCALAR_CONSTANT(0.1), SCALAR_CONSTANT(0.35)));
    Vector3 min = -max;

    Vector3 position;
    position[0] = Scalar::Random(SCALAR_CONSTANT(-1.0), SCALAR_CONSTANT(1.0));
    position[1] = Scalar::Random(SCALAR_CONSTANT(-1.0), SCALAR_CONSTANT(1.0));
    position[2] = Scalar::Random(SCALAR_CONSTANT( 1.0), SCALAR_CONSTANT(2.0));

    Euler rotation;

#ifdef PHYSICS_ENGINE_JOLT
    TestObject* temp = new TestObject(_physicsSystem.GetBodyInterface(),
                                      position, rotation, min, max);
#else
    TestObject* temp = new TestObject(position, rotation, min, max);
#endif

    Vertex3D* cubeVerts = MakeCube(testMemory, min, max);
    temp->object3D = new (testMemory) RenderObject3D(testMemory, 8, cubeVerts,
                                                     12, cubeFaceList,
                                                     cubeMaterialList);
    assert(ValidPtr(temp->object3D));
    testObjects.push_back(temp);
}

//==============================================================================

extern void test_event_loop();
extern int _halWindowWidth, _halWindowHeight;

GFXTester::GFXTester()
    : testMemory(HALLmalloc, 200000 MEMORY_NAMED(COMMA "GFX test Memory"))
    , display(2, 0, 0, 320, 240, testMemory)
#if defined(VIDEO_MEMORY_IN_ONE_PIXELMAP)
    , vram(PixelMap::MEMORY_VIDEO, Display::VRAMWidth, Display::VRAMHeight)
#else
    , vram(PixelMap::MEMORY_VIDEO, 256, 256)
#endif
    , vp(display, 4000, Scalar(320, 0), Scalar(240, 0), testMemory, 2)
    , camera(vp)
#ifdef PHYSICS_ENGINE_JOLT
    , _tempAllocator(10 * 1024 * 1024)   // 10 MB temp arena
    , _jobSystem(JPH::cMaxPhysicsJobs)
#endif
{
#if TEST_TEXTURES
    LoadTextures(vram);
#endif

    joy1 = JoystickNew(EJW_JOYSTICK1);
    joy2 = JoystickNew(EJW_JOYSTICK2);

    display.SetBackgroundColor(Color(60, 60, 60));
#define SIZE 0.25
    cubeVertexList[0] = Vertex3D(SCALAR_CONSTANT(0), SCALAR_CONSTANT(1), Color(128,128,128), Vector3_PS(PS_SCALAR_CONSTANT(-SIZE), PS_SCALAR_CONSTANT(-SIZE), PS_SCALAR_CONSTANT( SIZE)));
    cubeVertexList[1] = Vertex3D(SCALAR_CONSTANT(1), SCALAR_CONSTANT(1), Color(200,200, 50), Vector3_PS(PS_SCALAR_CONSTANT( SIZE), PS_SCALAR_CONSTANT(-SIZE), PS_SCALAR_CONSTANT( SIZE)));
    cubeVertexList[2] = Vertex3D(SCALAR_CONSTANT(0), SCALAR_CONSTANT(1), Color(128,  0,  0), Vector3_PS(PS_SCALAR_CONSTANT(-SIZE), PS_SCALAR_CONSTANT(-SIZE), PS_SCALAR_CONSTANT(-SIZE)));
    cubeVertexList[3] = Vertex3D(SCALAR_CONSTANT(1), SCALAR_CONSTANT(1), Color(  0,128,  0), Vector3_PS(PS_SCALAR_CONSTANT( SIZE), PS_SCALAR_CONSTANT(-SIZE), PS_SCALAR_CONSTANT(-SIZE)));
    cubeVertexList[4] = Vertex3D(SCALAR_CONSTANT(0), SCALAR_CONSTANT(0), Color(  0,128,  0), Vector3_PS(PS_SCALAR_CONSTANT(-SIZE), PS_SCALAR_CONSTANT( SIZE), PS_SCALAR_CONSTANT( SIZE)));
    cubeVertexList[5] = Vertex3D(SCALAR_CONSTANT(1), SCALAR_CONSTANT(0), Color(  0,  0,  0), Vector3_PS(PS_SCALAR_CONSTANT( SIZE), PS_SCALAR_CONSTANT( SIZE), PS_SCALAR_CONSTANT( SIZE)));
    cubeVertexList[6] = Vertex3D(SCALAR_CONSTANT(1), SCALAR_CONSTANT(0), Color(  0,  0,128), Vector3_PS(PS_SCALAR_CONSTANT( SIZE), PS_SCALAR_CONSTANT( SIZE), PS_SCALAR_CONSTANT(-SIZE)));
    cubeVertexList[7] = Vertex3D(SCALAR_CONSTANT(0), SCALAR_CONSTANT(0), Color(128,128,  0), Vector3_PS(PS_SCALAR_CONSTANT(-SIZE), PS_SCALAR_CONSTANT( SIZE), PS_SCALAR_CONSTANT(-SIZE)));

    cubeFaceList[ 0] = TriFace(0,1,2, 0, cubeVertexList);
    cubeFaceList[ 1] = TriFace(1,3,2, 0, cubeVertexList);
    cubeFaceList[ 2] = TriFace(4,0,2, 1, cubeVertexList);
    cubeFaceList[ 3] = TriFace(2,7,4, 1, cubeVertexList);
    cubeFaceList[ 4] = TriFace(1,5,6, 2, cubeVertexList);
    cubeFaceList[ 5] = TriFace(3,1,6, 2, cubeVertexList);
    cubeFaceList[ 6] = TriFace(4,5,1, 3, cubeVertexList);
    cubeFaceList[ 7] = TriFace(4,1,0, 3, cubeVertexList);
    cubeFaceList[ 8] = TriFace(2,3,6, 4, cubeVertexList);
    cubeFaceList[ 9] = TriFace(6,7,2, 4, cubeVertexList);
    cubeFaceList[10] = TriFace(5,4,7, 5, cubeVertexList);
    cubeFaceList[11] = TriFace(5,7,6, 5, cubeVertexList);
    cubeFaceList[12] = TriFace(0,0,0,-1);

    std::cout << "vram& = " << (void*)&vram << std::endl;

    cubeMaterialList[0] = Material(Color( 40, 40,168), Material::FLAT_SHADED|Material::SOLID_COLOR   |Material::LIGHTING_LIT, dummyTexture, test2Texture);
    cubeMaterialList[1] = Material(Color( 40,168, 40), Material::FLAT_SHADED|Material::SOLID_COLOR   |Material::LIGHTING_LIT, dummyTexture, test2Texture);
    cubeMaterialList[2] = Material(Color( 40,168,168), Material::FLAT_SHADED|Material::SOLID_COLOR   |Material::LIGHTING_LIT, dummyTexture, test2Texture);
    cubeMaterialList[3] = Material(Color(168, 40, 40), Material::FLAT_SHADED|Material::TEXTURE_MAPPED|Material::LIGHTING_LIT, dummyTexture, test2Texture);
    cubeMaterialList[4] = Material(Color(128,128,128), Material::FLAT_SHADED|Material::TEXTURE_MAPPED|Material::LIGHTING_LIT, dummyTexture, test2Texture);
    cubeMaterialList[5] = Material(Color(168, 40,168), Material::FLAT_SHADED|Material::SOLID_COLOR   |Material::LIGHTING_LIT, dummyTexture, test2Texture);

    cube2MaterialList[0] = Material(Color( 40, 40,168), Material::FLAT_SHADED|Material::SOLID_COLOR   |Material::LIGHTING_LIT, dummyTexture, testTexture);
    cube2MaterialList[1] = Material(Color( 40,168, 40), Material::FLAT_SHADED|Material::SOLID_COLOR   |Material::LIGHTING_LIT, dummyTexture, testTexture);
    cube2MaterialList[2] = Material(Color( 40,168,168), Material::FLAT_SHADED|Material::SOLID_COLOR   |Material::LIGHTING_LIT, dummyTexture, testTexture);
    cube2MaterialList[3] = Material(Color(168, 40, 40), Material::FLAT_SHADED|Material::TEXTURE_MAPPED|Material::LIGHTING_LIT, dummyTexture, testTexture);
    cube2MaterialList[4] = Material(Color(128,128,128), Material::FLAT_SHADED|Material::TEXTURE_MAPPED|Material::LIGHTING_LIT, dummyTexture, testTexture);
    cube2MaterialList[5] = Material(Color(168, 40,168), Material::FLAT_SHADED|Material::SOLID_COLOR   |Material::LIGHTING_LIT, dummyTexture, testTexture);

    cameraPosition = Vector3(SCALAR_CONSTANT(0), SCALAR_CONSTANT(0), SCALAR_CONSTANT(5));
    cameraRotation = Euler(Angle::Degree(SCALAR_CONSTANT(90)), Angle::Degree(SCALAR_CONSTANT(0)), Angle::zero);

#ifdef PHYSICS_ENGINE_JOLT
    // Initialise the Jolt world (gravity -0.5 along Z to match the old ODE setup).
    _physicsSystem.Init(
        /*maxBodies=*/     1024,
        /*numBodyMutexes=*/0,       // 0 → pick automatically
        /*maxBodyPairs=*/  1024,
        /*maxContactConstraints=*/ 1024,
        _bpLayerInterface,
        _bpFilter,
        _objectFilter
    );
    _physicsSystem.SetGravity(JPH::Vec3(0.0f, 0.0f, -0.5f));

    // Static floor: a large thin box at Z=0.
    JPH::BodyCreationSettings floorSettings(
        new JPH::BoxShape(JPH::Vec3(100.0f, 100.0f, 0.05f)),
        JPH::RVec3(0.0f, 0.0f, -0.05f),
        JPH::Quat::sIdentity(),
        JPH::EMotionType::Static,
        PhysLayers::STATIC
    );
    _floorBodyID = _physicsSystem.GetBodyInterface().CreateAndAddBody(
        floorSettings, JPH::EActivation::DontActivate);
#endif
}

//=============================================================================

GFXTester::~GFXTester()
{
    for (TestObjectIter iter = testObjects.begin(); iter != testObjects.end(); ++iter)
    {
        MEMORY_DELETE(testMemory, (*iter)->object3D, RenderObject3D);
        delete *iter;
    }

#ifdef PHYSICS_ENGINE_JOLT
    if (!_floorBodyID.IsInvalid())
    {
        _physicsSystem.GetBodyInterface().RemoveBody(_floorBodyID);
        _physicsSystem.GetBodyInterface().DestroyBody(_floorBodyID);
    }
#endif

    JoystickDelete(joy1);
    JoystickDelete(joy2);
}

//=============================================================================

void
GFXTester::Update()
{
    buttons1 = JoystickGetButtonsF(joy1);
    buttons2 = JoystickGetButtonsF(joy2);

    AdjustCameraParameters(cameraPosition, cameraRotation, buttons1);

#ifdef PHYSICS_ENGINE_JOLT
    // Fixed-step substepping: accumulate frame time and drain into 1/60 s steps.
    // Capped at 4 substeps to prevent spiral-of-death on stalled frames.
    // (See project memory: WF variable tick rate is load-bearing.)
    // physicstest has no WF clock; use a nominal 1/60 s per frame.
    _accumulator += kFixedStep;
    int substeps = 0;
    while (_accumulator >= kFixedStep && substeps < 4)
    {
        _physicsSystem.Update(kFixedStep, /*collisionSteps=*/1,
                              &_tempAllocator, &_jobSystem);
        _accumulator -= kFixedStep;
        ++substeps;
    }

    // Sync Jolt body positions → WF PhysicalAttributes for rendering.
    for (TestObjectIter iter = testObjects.begin(); iter != testObjects.end(); ++iter)
        (*iter)->SyncFromJolt();

#else
    for (TestObjectIter iter = testObjects.begin(); iter != testObjects.end(); ++iter)
        (*iter)->_physical.Update();
#endif
}

//============================================================================

void
GFXTester::Render()
{
    display.RenderBegin();

    Matrix34 camRot(cameraRotation, Vector3::zero);
    Matrix34 camPos(cameraPosition);
    Matrix34 camMat = camPos * camRot;
    camera.SetPosition(camMat);

    camera.SetFog(Color(60,60,60), SCALAR_CONSTANT(10), SCALAR_CONSTANT(18));
    camera.SetAmbientColor(Color(128,128,128));
    camera.SetDirectionalLight(0, Vector3(SCALAR_CONSTANT(1),SCALAR_CONSTANT(0),SCALAR_CONSTANT(0)),
                               Color48(PS_SCALAR_CONSTANT12(1),PS_SCALAR_CONSTANT12(0),PS_SCALAR_CONSTANT12(0)));
    camera.SetDirectionalLight(1, Vector3(SCALAR_CONSTANT(0),SCALAR_CONSTANT(1),SCALAR_CONSTANT(0)),
                               Color48(PS_SCALAR_CONSTANT12(0),PS_SCALAR_CONSTANT12(1),PS_SCALAR_CONSTANT12(0)));
    camera.SetDirectionalLight(2, Vector3(SCALAR_CONSTANT(0),SCALAR_CONSTANT(0),SCALAR_CONSTANT(1)),
                               Color48(PS_SCALAR_CONSTANT12(0),PS_SCALAR_CONSTANT12(0),PS_SCALAR_CONSTANT12(1)));

    vp.Clear();
    camera.RenderBegin();

    for (TestObjectIter iter = testObjects.begin(); iter != testObjects.end(); ++iter)
    {
        TestObject* o = *iter;
        camera.RenderObject(*o->object3D, o->_physical.Matrix());
    }

    camera.RenderEnd();
    vp.Render();
    display.RenderEnd();
}

//============================================================================

void
GFXTester::PageFlip()
{
    display.PageFlip();
}

//==============================================================================

void
TestGFXInit()
{
    printf("Test gfx init\n");
#ifdef PHYSICS_ENGINE_JOLT
    JPH::RegisterDefaultAllocator();
    JPH::Factory::sInstance = new JPH::Factory();
    JPH::RegisterTypes();
    printf("jolt: registered types\n");
#else
    printf("physicstest: no physics engine compiled in — build with PHYSICS_ENGINE_JOLT\n");
#endif

    tester = new (HALLmalloc) GFXTester;
    assert(ValidPtr(tester));
}

void
TestGFXUnInit()
{
    printf("Test gfx uninit\n");
    MEMORY_DELETE(HALLmalloc, tester, GFXTester);

#ifdef PHYSICS_ENGINE_JOLT
    JPH::UnregisterTypes();
    delete JPH::Factory::sInstance;
    JPH::Factory::sInstance = nullptr;
#endif
}

void
TestGFXLoop()
{
    tester->Update();
    tester->Render();
}

void
TestGFXPageFlip()
{
    tester->PageFlip();
}

//=============================================================================

void
PIGSMain(int argc, char* argv[])
{
    (void)argc;
    (void)argv;
    std::cout << "PhysicsTest (Jolt backend):" << std::endl;

    printf("Test gfx\n");
    TestGFXInit();
    printf("Test gfx init done\n");

    for (;;)
    {
        TestGFXLoop();
        TestGFXPageFlip();
    }

    printf("shutting down\n");
    TestGFXUnInit();
    printf("physics test complete\n");

    std::cout << "physicstest Done" << std::endl;
    PIGSExit();
}

//==============================================================================
