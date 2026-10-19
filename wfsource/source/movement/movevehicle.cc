//============================================================================
// movevehicle.cc — MovementHandler for MOBILITY_VEHICLE (Jolt VehicleConstraint).
//
// On init: creates a Jolt WheeledVehicleController with the Lunar Cruiser
// wheel layout (6 wheels; front pair steerable).
//
// On update: reads this actor's local INPUT mailbox, maps UP/DOWN/LEFT/RIGHT
// bits to throttle/steer/brake, calls JoltVehicleSetInput, then pushes the
// Jolt-resolved position and rotation back to the actor.
//============================================================================

#define _MOVEVEHICLE_CC
#include <movement/inputmap.hp>
#include "movevehicle.hp"
#include "movementmanager.hp"
#include <input/inputdig.hp>
#include <physics/physical.hp>
#include <oas/movement.h>
#include <physics/jolt/jolt_backend.hp>
#include <math/vector3.hp>
#include <math/euler.hp>
#include <baseobject/msgport.hp>

//============================================================================

VehicleHandler theVehicleHandler;

//============================================================================
// Lunar Cruiser wheel layout (WF axes: X=forward, Y=left, Z=up).
// Positions match _build_lunar_cruiser() geometry in blender_create_moon.py.

static const JoltVehicleWheelCfg kCruiserWheels[6] = {
    { 1.9f,  2.6f, true  },   // front-port   (steerable)
    { 1.9f, -2.6f, true  },   // front-stbd   (steerable)
    { 0.0f,  2.6f, false },   // mid-port
    { 0.0f, -2.6f, false },   // mid-stbd
    {-1.9f,  2.6f, false },   // rear-port
    {-1.9f, -2.6f, false },   // rear-stbd
};

static const JoltVehicleConfig kCruiserCfg = {
    /* chassis_hx */ 2.75f,           // half of 5.5 m body length
    /* chassis_hy */ 2.25f,           // half of 4.5 m body width
    /* chassis_hz */ 1.1f,            // half of 2.2 m body height
    /* mass_kg    */ 6000.0f,         // Toyota Lunar Cruiser target mass
    /* gravity_z  */ -1.62f,          // lunar g (m/s²)
    /* wheel_radius    */ 0.7f,
    /* wheel_half_width*/ 0.175f,
    /* max_steer_angle */ 0.436f,     // 25° in radians
    /* max_torque_nm   */ 2000.0f,    // enough to move 6 t on lunar surface
    /* num_wheels */ 6,
    /* wheels     */ kCruiserWheels,
};

//============================================================================

void VehicleHandler::init(MovementManager& movementManager,
                           MovementObject&  movementObject)
{
    assert(movementManager.MovementBlock()->Mobility == MOBILITY_VEHICLE);

    VehicleHandlerData* data =
        (VehicleHandlerData*)movementManager.GetMovementHandlerData();
    assert(ValidPtr(data));

    const Vector3& pos = movementObject.GetPhysicalAttributes().Position();
    const Euler&   rot = movementObject.GetPhysicalAttributes().Rotation();

    data->joltHandle = JoltVehicleCreate(pos, rot, kCruiserCfg);
    if (data->joltHandle == kJoltInvalidBodyID)
        fprintf(stderr, "[movevehicle] JoltVehicleCreate failed\n");
}

//============================================================================

bool VehicleHandler::check()
{
    assert(0);
    return true;
}

//============================================================================

bool VehicleHandler::update(MovementManager& movementManager,
                             MovementObject&  movementObject,
                             const BaseObjectList& /*baseObjectList*/)
{
    // Drain collision messages (match pattern from other handlers).
    {
        char msgData[msgDataSize];
        MsgPort& port = movementObject.GetMsgPort();
        while (port.GetMsgByType(MsgPort::COLLISION, &msgData, msgDataSize))
            ;
    }

    VehicleHandlerData* data =
        (VehicleHandlerData*)movementManager.GetMovementHandlerData();
    assert(ValidPtr(data));
    if (data->joltHandle == kJoltInvalidBodyID) return true;

    // Read INPUT bits from the actor's local mailbox.
    const QInputDigital* input = movementObject.GetInputDevice();
    joystickButtonsF buttons   = input ? input->arePressed() : 0;

    float forward   = (buttons & EJ_BUTTONF_UP)    ? 1.0f
                    : (buttons & EJ_BUTTONF_DOWN)   ? -1.0f : 0.0f;
    float rightward = (buttons & EJ_BUTTONF_RIGHT)  ? 1.0f
                    : (buttons & EJ_BUTTONF_LEFT)   ? -1.0f : 0.0f;
    float brake     = (forward < 0.0f) ? 1.0f : 0.0f;
    if (forward < 0.0f) forward = 0.0f;  // separate reverse from brake

    JoltVehicleSetInput(data->joltHandle, forward, rightward, brake);

    // Push resolved position/rotation back to actor.
    const Vector3& pos = JoltVehicleGetPosition(data->joltHandle);
    Euler          rot = JoltVehicleGetRotation(data->joltHandle);

    movementObject.GetWritablePhysicalAttributes().SetPredictedPosition(pos);
    movementObject.GetWritablePhysicalAttributes().SetRotation(rot);

    return true;
}

//============================================================================

void VehicleHandler::predictPosition(MovementManager& /*movementManager*/,
                                      MovementObject&  movementObject,
                                      const Clock&     /*clock*/,
                                      const BaseObjectList& /*baseObjectList*/)
{
    // Jolt drives the vehicle body; no additional WF prediction needed.
    (void)movementObject;
}

//============================================================================
