//============================================================================
// movement.cc: Base class and derived classes for  movement handlers
// Copyright ( c ) 1997,1998,1999,2000,2002,2003 World Foundry Group.  
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
//============================================================================
// Documentation:
//
//
//      Abstract:
//      	Provides a base class for movement handlers and derived classes
//          for state-specific handlers.  Actor objects will contain a pointer
//          to the derived movement handler appropriate for their current state.
//
//      History:
//          Created 03/03/97 by Ph5il Torre
//
//============================================================================

#define _movement_CC
#include <math/vector3.hp>
#include <movement/inputmap.hp>
#include "movement.hp"
#include "movementmanager.hp"
#include <input/inputdig.hp>
#include <physics/physical.hp>
#ifdef PHYSICS_ENGINE_JOLT
#include <physics/jolt/jolt_backend.hp>
#endif
#include <cpplib/libstrm.hp>
#include <oas/movement.h>

//#if !defined (__DOOMSTICK__)
// only used by the non-doomstick code
//#include "camera.hp"
//#endif

//#define PHYSICS_TELEMETRY     // Dump player's position and velocity every frame
#define PREMOVEMENT_CHECK		// Make sure objects weren't colliding before any movement occurred
//#define INSANE_COLLISION_ASSERTIONS	// Comprehensive (and very slow) assertions in PreventCollision()

extern bool gDoomStick;

//============================================================================
// Instances of movement handlers
GroundHandler  theGroundHandler;
AirHandler     theAirHandler;
MarbleHandler  theMarbleHandler;
ClimbHandler   theClimbHandler;
NullHandler    theNullHandler;
//
// // Table of pointers to "physics-based" movement handlers
// MovementHandler* physicsHandlerTable[] =
// {
//    &theGroundHandler,
//    &theAirHandler,
//    &theClimbHandler,
//    &theNullHandler
// };


//#if !defined (__DOOMSTICK__)
//============================================================================
// Compute rotation delta for gradually turning an object from one orientation in
// the XZ plane to another.  (Return value is new heading)

Angle MovementHandler::CalcNewHeading(Angle angleFrom, Angle angleTo, Scalar slewRate)
{
	Angle CWDelta, CCWDelta, result;	// ClockWise, CounterClockWise, resultant

	// Check for early bailout
	if (angleFrom == angleTo)
		return angleTo;

	// Make sure we don't overshoot due to low frame rate (high delta-T)
	if ( slewRate > Scalar::one )
		slewRate = Scalar::one;

	// Calculate distance both CW and CCW and use whichever one is shorter
	if (angleTo > angleFrom)
	{
		CCWDelta = angleTo - angleFrom;
		CWDelta  = (angleFrom + Angle::one) - angleTo;
	}
	else
	{
		CCWDelta = (angleTo + Angle::one) - angleFrom;
		CWDelta  = angleFrom - angleTo;
	}

	if ( CWDelta > CCWDelta )
	{
		result = angleFrom + (CCWDelta * slewRate);
		if (result > Angle::one )
			result -= Angle::one;
	}
	else
	{
		result = angleFrom - (CWDelta * slewRate);
		if (result < Angle::zero )
			result += Angle::one;
	}

	return result;
}

//#endif	// __DOOMSTICK__

//============================================================================

void
MovementHandler::SetStunTime(MovementManager& /*movementManager*/, Scalar /*newTime*/ )
{
	// default behaviour is ignore
}

//==============================================================================

size_t
MovementHandler::DataSize()
{
   return sizeof(MovementHandlerData);
}

//============================================================================
//  Collects any pending MOVEMENT_FORCE messages for a MovementObject, sums them into
//  a resultant vector.

Vector3 MovementHandler::SumForceVectors(MovementObject& movementObject)
{
	MsgPort& msgPort = movementObject.GetMsgPort();
   char msgData[msgDataSize];
	Vector3  resultant = Vector3::zero;

	while (msgPort.GetMsgByType(MsgPort::MOVEMENT_FORCE_X, &msgData, msgDataSize))
		resultant += Vector3(( *(Scalar*) &msgData),
							 Scalar::zero,
							 Scalar::zero);

	while (msgPort.GetMsgByType(MsgPort::MOVEMENT_FORCE_Y,  &msgData, msgDataSize))
		resultant += Vector3(Scalar::zero,
							 (*(Scalar*) &msgData),
							 Scalar::zero);

	while (msgPort.GetMsgByType(MsgPort::MOVEMENT_FORCE_Z,  &msgData, msgDataSize))
		resultant += Vector3(Scalar::zero,
							 Scalar::zero,
							 (*(Scalar*) &msgData) );

#if DO_DEBUGGING_INFO
//	if ( !(resultant == Vector3::zero) && (movementObject.kind() == MovementObject::Player_KIND) )
//		breakpoint();
#endif

	return resultant;
}

//============================================================================

void GroundHandler::init(MovementManager& movementManager, MovementObject& movementObject)
{
	assert( movementManager.MovementBlock()->Mobility == MOBILITY_PHYSICS );

	movementObject.MovementStateChanged( MovementObject::Ground_state );
	DBSTREAM3( cmovement << "GroundHandler::Init done" << std::endl; )
}

//============================================================================

bool GroundHandler::check()
{
	assert(0);
//    DBSTREAM3( cmovement << "GroundHandler::Check" << std::endl; )
//    assert(ValidPtr(physicalObject->GetMovementBlockPtr()));
//    return (physcalObject->GetMovementBlockPtr()->Mobility);
   return false;
}

//============================================================================

void
GroundHandler::predictPosition(MovementManager& movementManager, MovementObject& movementObject, const Clock& clock, const BaseObjectList& baseObjectList)
{
	DBSTREAM3( cmovement << "GroundHandler::Predict Position" << std::endl; )
	PhysicalAttributes& actorAttr = movementObject.GetWritablePhysicalAttributes();
	assert(ValidPtr(movementObject.GetMovementBlockPtr()));
	Scalar deltaT = clock.Delta();
	Scalar runningAccel = movementObject.GetMovementBlockPtr()->GetRunningAcceleration();
	const QInputDigital* inputDevice = movementObject.GetInputDevice();
	joystickButtonsF buttons = inputDevice->arePressed();
	Vector3 newVelocity = actorAttr.LinVelocity();
	Vector3 supportingVelocity = Vector3::zero;
	Scalar surfaceFriction = Scalar::zero;
	MovementHandler* newMovementHandler = NULL;

	actorAttr.SetOldLinVelocity( newVelocity );

	MovementHandlerData* handlerData = movementManager.GetMovementHandlerData();
	assert(ValidPtr(handlerData));

	Vector3 wheelVelocity = handlerData->wheelVelocity;
	Vector3 surfaceNormal(Vector3::unitZ);

	// If we are standing on something, get its velocity
	if (handlerData->supportingObject)
	{
      MovementManager& movementManager = handlerData->supportingObject->GetMovementManager();
      movementManager.predictPosition(*handlerData->supportingObject,clock,baseObjectList);           // make sure they've moved already
      supportingVelocity = handlerData->supportingObject->GetPhysicalAttributes().GetDeltaPos() / deltaT;
      surfaceFriction = handlerData->supportingObject->GetMovementBlockPtr()->GetSurfaceFriction();
      if (handlerData->supportingObject->GetPhysicalAttributes().ContainsSlope())
      {
         surfaceNormal = handlerData->supportingObject->GetPhysicalAttributes().SlopeNormal();
         surfaceNormal.Normalize();
      }
	}

	// Apply wheel drag when the joystick isn't pressed.
	Scalar drag = Scalar::one - (movementObject.GetMovementBlockPtr()->GetRunningDeceleration() * deltaT * SCALAR_CONSTANT(30));
	if ( drag < Scalar::zero )
		drag = Scalar::zero;

	joystickButtonsF joyMask;
	if(gDoomStick)
//#if defined (__DOOMSTICK__)
		joyMask = (EJ_BUTTONF_UP | EJ_BUTTONF_DOWN | kBtnStepLeft | kBtnStepRight);
//#else
	else
		joyMask = (EJ_BUTTONF_UP | EJ_BUTTONF_DOWN | EJ_BUTTONF_LEFT | EJ_BUTTONF_RIGHT);
//#endif

	if ( !(buttons & joyMask) )
		wheelVelocity *= drag;

	//=====================================================================
	// This code adds up the effects of running, gravity, and field effects.

	// Are we jumping?
	if (movementObject.GetInputDevice()->justPressed(kBtnJump))
	{
		newMovementHandler = &theAirHandler;
		handlerData->jumpDuration = SCALAR_CONSTANT(0.2);

		movementManager.SetMovementHandler(newMovementHandler,movementObject);
		theAirHandler.predictPosition(movementManager, movementObject, clock, baseObjectList);
		return;
	}



	//--------------------------------------------------------------------------------------------
	// Joystick code

	if(gDoomStick)
	{
//#if defined (__DOOMSTICK__)

	// --------- This code does the Cyberthug "Doom-style" joystick input
	if ( buttons & (joyMask | EJ_BUTTONF_LEFT | EJ_BUTTONF_RIGHT) )
	{
		Scalar turnRate = movementObject.GetMovementBlockPtr()->GetTurnRate() * deltaT;
		Vector3 currentDir = movementObject.currentDir();

		// construct a rotation matrix for currentDir (if surface is sloped)
		Matrix34 slopeMatrix;
		Angle xRot(0), yRot(0), zRot(0);
		if (!(surfaceNormal == Vector3::unitZ))
		{
			// rotate about each axis, as needed
			if (surfaceNormal.Y() != Scalar::zero)
				xRot = -(surfaceNormal.Z().ATan2(surfaceNormal.Y()));

			if (surfaceNormal.X() != Scalar::zero)
				yRot = surfaceNormal.Z().ATan2(surfaceNormal.X());

			slopeMatrix.ConstructEuler( Euler(xRot, yRot, zRot), Vector3::zero );
			currentDir *= slopeMatrix;
		}


		if (buttons & EJ_BUTTONF_UP)	// Move forward at Walk speed
			wheelVelocity += (currentDir * runningAccel * deltaT);

		if (buttons & EJ_BUTTONF_DOWN)	// Move backwards at Walk speed
			wheelVelocity -= (currentDir * runningAccel * deltaT);

		if (buttons & EJ_BUTTONF_LEFT)
		{
			if (turnRate != Scalar::zero)
				actorAttr.AddRotation( Euler(Angle::zero,Angle::zero,Angle::Revolution(turnRate)));
			else
			{	// TurnRate==0: no rotation desired; treat LEFT as strafe-left
				Vector3 stepVector = currentDir * runningAccel * deltaT;
				wheelVelocity += Vector3(-stepVector.Y(), stepVector.X(), Scalar::zero);
			}
		}

		if (buttons & EJ_BUTTONF_RIGHT)
		{
			if (turnRate != Scalar::zero)
				actorAttr.AddRotation( Euler(Angle::zero,Angle::zero,Angle::Revolution(-turnRate)));
			else
			{	// TurnRate==0: no rotation desired; treat RIGHT as strafe-right
				Vector3 stepVector = currentDir * runningAccel * deltaT;
				wheelVelocity += Vector3(stepVector.Y(), -stepVector.X(), Scalar::zero);
			}
		}

		if (buttons & kBtnStepLeft)		// Sidestep left
		{
			Vector3 stepVector = currentDir * runningAccel * deltaT;
			wheelVelocity += Vector3(-stepVector.Y(), stepVector.X(), Scalar::zero);
		}

		if (buttons & kBtnStepRight)		// Sidestep right
		{
			Vector3 stepVector = currentDir * runningAccel * deltaT;
			wheelVelocity += Vector3(stepVector.Y(), -stepVector.X(), Scalar::zero);
		}
	}
	}
	else
	{
   assert(0);           //kts removed 11/29/2002 19:37:22, let me know if anyone wants this style of control
//#else
#if 0
	// --------- This is the "Velocity" style camera-centric joystick code
	if ( buttons & joyMask )
	{
		Scalar turnRate = movementObject.GetMovementBlockPtr()->GetTurnRate() * deltaT;

		const Vector3& cameraLookAt = theLevel->camera()->GetLookAt();
		Angle cameraAngle = cameraLookAt.X().ATan2(cameraLookAt.Y());
		Angle quantizedCameraAngle(Angle::zero);
		Angle boundary(Angle::Degree(SCALAR_CONSTANT(22.5)));
		const Angle rotationQuantum(Angle::Degree(SCALAR_CONSTANT(45)));
		while (cameraAngle > boundary)
		{
			quantizedCameraAngle += rotationQuantum;
			boundary += rotationQuantum;
		}

		// Read joystick and figure out our intended direction
		Vector3 motionVector(Vector3::zero);

		if (buttons & EJ_BUTTONF_UP)	// Movement away from camera
			motionVector += Vector3::unitX;

		if (buttons & EJ_BUTTONF_DOWN)	// Movement toward camera
			motionVector += Vector3::unitNegativeX;

		if (buttons & EJ_BUTTONF_LEFT)	// Movement toward camera's left
			motionVector += Vector3::unitY;

		if (buttons & EJ_BUTTONF_RIGHT)	// Movement toward camera's right
			motionVector += Vector3::unitNegativeY;

		// Transform motionVector by camera angle
		motionVector.Normalize();
		motionVector.RotateZ(quantizedCameraAngle);

		// Rotate Object towards direction of motion
		Angle motionAngle(motionVector.X().ATan2(motionVector.Y()));
      Euler rotation = actorAttr.Rotation();
		rotation.SetC( CalcNewHeading( rotation.GetC(), motionAngle, turnRate ) );
      actorAttr.Rotation(rotation);

		// construct a rotation matrix for motionVector (if surface is sloped)
		Matrix34 slopeMatrix;
		Angle xRot(0), yRot(0), zRot(0);
		if (!(surfaceNormal == Vector3::unitZ))
		{
			// rotate about each axis, as needed
			if (surfaceNormal.Y() != Scalar::zero)
				xRot = -(surfaceNormal.Z().ATan2(surfaceNormal.Y()));

			if (surfaceNormal.X() != Scalar::zero)
				yRot = surfaceNormal.Z().ATan2(surfaceNormal.X());

			slopeMatrix.ConstructEuler( Euler(xRot, yRot, zRot), Vector3::zero );
			motionVector *= slopeMatrix;
		}

		wheelVelocity += (motionVector * runningAccel * deltaT);
	}
#endif
	}
//#endif	// __DOOMSTICK__

	// clip wheelVelocity at maximum speed
	Scalar maxSpeed = movementObject.GetMovementBlockPtr()->GetMaxGroundSpeed();
	Scalar wheelSpeed = wheelVelocity.Length();
	if (wheelSpeed > maxSpeed)
		wheelVelocity *= ( maxSpeed / wheelSpeed );

	// Make friction between wheel and ground happen
	Vector3 planeFriction = ((wheelVelocity + supportingVelocity) - newVelocity) * surfaceFriction;
	planeFriction -= surfaceNormal * (planeFriction.DotProduct(surfaceNormal));
	newVelocity += planeFriction;

	// Add in force vectors from area effects, etc.
	Vector3 forceVector = SumForceVectors(movementObject);
	if ( !(forceVector == Vector3::zero) )
	{
		if (forceVector.Z() == Scalar::zero)				// Special kludge for "top of fan effect"
			newVelocity += (forceVector * deltaT);
		else
		{
			newVelocity += Vector3( (forceVector.X() * deltaT), (forceVector.Y() * deltaT), Scalar::zero );
			newVelocity.SetZ(forceVector.Z());
		}
	}

	// Make gravity happen
	newVelocity += Vector3(Scalar::zero, Scalar::zero, -(movementObject.GetMovementBlockPtr()->GetFallingAcceleration() * deltaT));

	// Apply new velocity to velocity and predicted position
#ifdef PHYSICS_ENGINE_JOLT
	{
		uint32_t charID = actorAttr.JoltCharacterID();
		if (charID != kJoltInvalidBodyID)
		{
			// With Jolt, supportingObject is never set, so planeFriction is zero and
			// wheelVelocity never reaches newVelocity. Apply wheelVelocity directly to
			// the XY components so OAD fields (RunningAcceleration, MaxGroundSpeed,
			// RunningDeceleration) govern ground movement as intended.
			newVelocity = Vector3(wheelVelocity.X(), wheelVelocity.Y(), newVelocity.Z());
			JoltCharacterSetLinVelocity(charID, newVelocity);
			JoltCharacterUpdate(charID, deltaT.AsFloat());
			actorAttr.JoltSyncFromCharacter(JoltCharacterGetPosition(charID));
			actorAttr.SetLinVelocity(JoltCharacterGetLinVelocity(charID));
			// Sync wheelVelocity.Y from actual Jolt character movement.
			// On a slope Jolt constrains our Z-axis gravity input to the surface,
			// producing real Y displacement.  Feeding that back here lets the ball
			// carry slope momentum onto flat terrain.
			wheelVelocity.SetY(JoltCharacterGetLinVelocity(charID).Y());
			handlerData->wheelVelocity = wheelVelocity;
			if (newMovementHandler)
				movementManager.SetMovementHandler(newMovementHandler, movementObject);
			handlerData->supportingObject = NULL;
			return;
		}
	}
#endif // PHYSICS_ENGINE_JOLT
	actorAttr.SetPredictedPosition(actorAttr.Position() +
			((newVelocity + actorAttr.OldLinVelocity()) * Scalar::half * deltaT));

	actorAttr.SetLinVelocity(newVelocity);
	handlerData->wheelVelocity = wheelVelocity;

#ifdef PHYSICS_TELEMETRY
	if (physicalObject->kind() == BaseObject::Player_KIND)
	{
		std::cout << "---- (Ground) New Frame:  T = " << clock.Current();
		if (buttons)
			std::cout << "   * Button Pressed *";
//		std::cout << std::endl << "Delta-T = " << deltaT << std::endl;
//		std::cout << std::endl << "Player's velocity: " << std::endl << newVelocity << std::endl;
//		std::cout << "Player's position: " << std::endl << actorAttr.PredictedPosition() << std::endl << std::endl;
		std::cout << std::endl << actorAttr << std::endl << std::endl;
	}
#endif // PHYSICS_TELEMETRY

	if (newMovementHandler)
		movementManager.SetMovementHandler(newMovementHandler,movementObject);

	handlerData->supportingObject = NULL;	// Clear this and let the collision system set it again
}

//============================================================================

bool GroundHandler::update(MovementManager& movementManager, MovementObject& movementObject, const BaseObjectList& baseObjectList )
{
	MovementHandlerData* handlerData = movementManager.GetMovementHandlerData();
	assert(ValidPtr(handlerData));

	// Check to see if we are in a non-interruptable animation (stunned, dazed, whatever)
//	if (handlerData->stunnedUntil > theTime)
//	{
//	}

   // kts removed 12/12/2002 11:32:44 while decoupling sub-systems), looks like this was meant to wait 
   // until the current // animation cycle finished to leave the stunned state, if that is desired then 
   // we should // have the animation system send a message to the actor (which would then dispatch it
   // to the movement system) which indicates end of cycle (instead of looking at it directly)
	//if (handlerData->stunnedUntil > theTime)
	//	handlerData->stunnedUntil = theTime + thisActor->_animManager->GetCycleDuration();

#ifdef PHYSICS_ENGINE_JOLT
	{
		const PhysicalAttributes& actorAttr = movementObject.GetPhysicalAttributes();
		uint32_t charID = actorAttr.JoltCharacterID();
		if (charID != kJoltInvalidBodyID)
		{
			// Use Jolt ground detection instead of WF's supportingObject pointer.
			if (!JoltCharacterIsOnGround(charID))
				movementManager.SetMovementHandler(&theAirHandler, movementObject);
			return true;
		}
	}
#endif // PHYSICS_ENGINE_JOLT
	if (handlerData->supportingObject == NULL)
		movementManager.SetMovementHandler(&theAirHandler,movementObject);

	return true;
}

//============================================================================

void
GroundHandler::SetStunTime(MovementManager& movementManager,Scalar newTime)
{
	MovementHandlerData* handlerData = movementManager.GetMovementHandlerData();
	handlerData->stunnedUntil = newTime;
}

//============================================================================

void 
AirHandler::init(MovementManager& movementManager, MovementObject& movementObject)
{
	AssertMsg( movementManager.MovementBlock()->Mobility == MOBILITY_PHYSICS, movementObject );

	MovementHandlerData* handlerData = movementManager.GetMovementHandlerData();
	assert(ValidPtr(handlerData));
	handlerData->supportingObject = NULL;

	movementObject.MovementStateChanged( MovementObject::Air_state );
}

//============================================================================

bool
AirHandler::check()
{
	assert(0);
	return false;
}

//============================================================================

bool
AirHandler::update(MovementManager& movementManager,  MovementObject& movementObject, const BaseObjectList& baseObjectList )
{
	const PhysicalAttributes& actorAttr = movementObject.GetPhysicalAttributes();
	actorAttr.Validate();
	MovementHandler* newMovementHandler = NULL;

	MovementHandlerData* handlerData = movementManager.GetMovementHandlerData();
	assert(ValidPtr(handlerData));

#ifdef PHYSICS_ENGINE_JOLT
	{
		uint32_t charID = actorAttr.JoltCharacterID();
		if (charID != kJoltInvalidBodyID)
		{
			// Use Jolt's ground contact result from the most recent JoltCharacterUpdate.
			if (JoltCharacterIsOnGround(charID) && handlerData->jumpDuration <= Scalar::zero)
			{
				handlerData->stunnedUntil = Scalar::zero;
				// TurnRate==0 actors use MarbleHandler; others use GroundHandler.
				MovementHandler* landHandler =
				    (movementManager.MovementBlock()->GetTurnRate() == Scalar::zero)
				    ? (MovementHandler*)&theMarbleHandler
				    : (MovementHandler*)&theGroundHandler;
				Vector3 newWheelVelocity = actorAttr.LinVelocity();
				newWheelVelocity.SetZ(Scalar::zero);
				handlerData->wheelVelocity = newWheelVelocity;
				movementManager.SetMovementHandler(landHandler, movementObject);
			}
			return true;
		}
	}
#endif // PHYSICS_ENGINE_JOLT
	if(handlerData->supportingObject)
	{
		handlerData->stunnedUntil = Scalar::zero;
		Vector3 newWheelVelocity = actorAttr.LinVelocity();
		newWheelVelocity.SetZ( Scalar::zero );
		handlerData->wheelVelocity = newWheelVelocity;
		newMovementHandler = &theGroundHandler;
	}

	if (newMovementHandler != NULL)		// switching out of this handler...
	{
		movementManager.SetMovementHandler(newMovementHandler,movementObject);
		return true;
	}

	return true;
}

//============================================================================
// MarbleHandler — physics-based rolling for sphere actors (TurnRate == 0).
// Unlike GroundHandler the full 3D velocity carries over each frame so
// gravity-driven slope momentum accumulates without button presses.

void
MarbleHandler::init(MovementManager& movementManager, MovementObject& movementObject)
{
	AssertMsg(movementManager.MovementBlock()->Mobility == MOBILITY_PHYSICS, movementObject);
	MovementHandlerData* handlerData = movementManager.GetMovementHandlerData();
	assert(ValidPtr(handlerData));
	handlerData->supportingObject = NULL;
	movementObject.MovementStateChanged(MovementObject::Ground_state);
}

bool MarbleHandler::check() { assert(0); return false; }

bool
MarbleHandler::update(MovementManager& movementManager, MovementObject& movementObject,
                      const BaseObjectList& /*baseObjectList*/)
{
#ifdef PHYSICS_ENGINE_JOLT
	{
		const PhysicalAttributes& actorAttr = movementObject.GetPhysicalAttributes();
		uint32_t charID = actorAttr.JoltCharacterID();
		if (charID != kJoltInvalidBodyID)
		{
			if (!JoltCharacterIsOnGround(charID))
				movementManager.SetMovementHandler(&theAirHandler, movementObject);
			return true;
		}
	}
#endif
	return true;
}

void
MarbleHandler::SetStunTime(MovementManager& movementManager, Scalar newTime)
{
	MovementHandlerData* handlerData = movementManager.GetMovementHandlerData();
	handlerData->stunnedUntil = newTime;
}

void
MarbleHandler::predictPosition(MovementManager& movementManager, MovementObject& movementObject,
                                const Clock& clock, const BaseObjectList& baseObjectList)
{
	PhysicalAttributes& actorAttr = movementObject.GetWritablePhysicalAttributes();
	assert(ValidPtr(movementManager.MovementBlock()));
	Scalar dt = clock.Delta();

	// Jump: mirror GroundHandler::predictPosition's branch. Doomstick actors
	// (TurnRate==0) run through MarbleHandler when grounded, so without this
	// they have no path into AirHandler and kBtnJump is silently ignored.
	if (movementObject.GetInputDevice()->justPressed(kBtnJump))
	{
		MovementHandlerData* handlerData = movementManager.GetMovementHandlerData();
		assert(ValidPtr(handlerData));
		handlerData->jumpDuration = SCALAR_CONSTANT(0.2);
		movementManager.SetMovementHandler(&theAirHandler, movementObject);
		theAirHandler.predictPosition(movementManager, movementObject, clock, baseObjectList);
		return;
	}

#ifdef PHYSICS_ENGINE_JOLT
	{
		uint32_t charID = actorAttr.JoltCharacterID();
		if (charID == kJoltInvalidBodyID) return;

		const QInputDigital* inputDevice = movementObject.GetInputDevice();
		joystickButtonsF buttons = inputDevice->arePressed();

		Scalar accel   = movementManager.MovementBlock()->GetRunningAcceleration();
		Scalar decel   = movementManager.MovementBlock()->GetRunningDeceleration();
		Scalar maxSpd  = movementManager.MovementBlock()->GetMaxGroundSpeed();
		Scalar gravity = movementManager.MovementBlock()->GetFallingAcceleration();

		// Carry the full 3D velocity from the last frame.  velCache.Y was corrected
		// from the position delta in JoltCharacterUpdate so slope momentum is real.
		Vector3 vel = actorAttr.LinVelocity();

		// Surface friction on XY only; gravity accumulates freely on Z.
		Scalar friction = decel * dt * SCALAR_CONSTANT(30);
		if (friction > Scalar::one) friction = Scalar::one;
		vel.SetX(vel.X() * (Scalar::one - friction));
		vel.SetY(vel.Y() * (Scalar::one - friction));

		// Gravity — projected onto the floor surface so the marble rolls downhill
		// on slopes instead of pressing straight into the floor (which Jolt blocks).
		// On flat ground the normal is (0,0,1) and this reduces to plain -Z gravity.
		{
			Vector3 N    = JoltCharacterGetGroundNormal(charID); // floor surface normal
			float   gF   = gravity.AsFloat() * dt.AsFloat();    // gravity impulse this frame
			// slope component: G_slope = G - (G·N)N  where G = (0,0,-gF)
			float   GdotN = -gF * N.Z().AsFloat();              // (0,0,-gF)·N = -gF*Nz
			float   slopeX = -GdotN * N.X().AsFloat();          // -(-gF*Nz)*Nx
			float   slopeY = -GdotN * N.Y().AsFloat();
			float   slopeZ = -gF - GdotN * N.Z().AsFloat();     // -gF - (-gF*Nz)*Nz
			vel.SetX(vel.X() + Scalar(slopeX));
			vel.SetY(vel.Y() + Scalar(slopeY));
			vel.SetZ(vel.Z() + Scalar(slopeZ));
		}

		// Player input: impulse in world-XY directions relative to actor facing.
		Vector3 fwd = movementObject.currentDir();          // (sin C, cos C, 0)
		Vector3 right(fwd.Y(), -fwd.X(), Scalar::zero);    // 90° CW in XY

		if (buttons & EJ_BUTTONF_UP)    vel += fwd   * accel * dt;
		if (buttons & EJ_BUTTONF_DOWN)  vel -= fwd   * accel * dt;
		if (buttons & EJ_BUTTONF_LEFT)  vel -= right * accel * dt;
		if (buttons & EJ_BUTTONF_RIGHT) vel += right * accel * dt;

		// Cap XY speed.
		Scalar xySpd = Vector3(vel.X(), vel.Y(), Scalar::zero).Length();
		if (xySpd > maxSpd)
		{
			Scalar scale = maxSpd / xySpd;
			vel.SetX(vel.X() * scale);
			vel.SetY(vel.Y() * scale);
		}

		JoltCharacterSetLinVelocity(charID, vel);
		JoltCharacterUpdate(charID, dt.AsFloat());
		actorAttr.JoltSyncFromCharacter(JoltCharacterGetPosition(charID));
		actorAttr.SetLinVelocity(JoltCharacterGetLinVelocity(charID));
	}
#endif // PHYSICS_ENGINE_JOLT
}

//============================================================================

void
AirHandler::predictPosition(MovementManager& movementManager, MovementObject& movementObject, const Clock& clock, const BaseObjectList& baseObjectList)
{
	PhysicalAttributes& actorAttr = movementObject.GetWritablePhysicalAttributes();
	const QInputDigital* inputDevice = movementObject.GetInputDevice();
	joystickButtonsF buttons = inputDevice->arePressed();
	assert(ValidPtr(movementManager.MovementBlock()));
	Scalar deltaT = clock.Delta();
	Scalar airAccel = movementManager.MovementBlock()->GetAirAcceleration();
	Vector3 newVelocity = actorAttr.LinVelocity();

	MovementHandlerData* handlerData = movementManager.GetMovementHandlerData();
	assert(ValidPtr(handlerData));


	if(gDoomStick)
	{
   //#if defined (__DOOMSTICK__)
   	//--------------------------------------------------------------------------------------------
   	// This code does the Cyberthug "Doom-style" joystick input
   
   	Scalar turnRate = movementObject.GetMovementBlockPtr()->GetTurnRate() * deltaT;
   
   	if (buttons & EJ_BUTTONF_UP)	// Move forward at Walk speed
   		newVelocity += (movementObject.currentDir() * airAccel * deltaT);
   
   	if (buttons & EJ_BUTTONF_DOWN)	// Move backwards at Walk speed
   		newVelocity -= (movementObject.currentDir() * airAccel * deltaT);
   
   	if (buttons & EJ_BUTTONF_LEFT)	// Rotate counterclockwise at turnRate
         actorAttr.AddRotation( Euler(Angle::zero,Angle::zero,Angle::Revolution(turnRate)));
   
   	if (buttons & EJ_BUTTONF_RIGHT)	// Rotate clockwise at turnRate
         actorAttr.AddRotation( Euler(Angle::zero,Angle::zero,Angle::Revolution(-turnRate)));
   
   	if (buttons & kBtnStepLeft)		// Sidestep left
   	{
   		Vector3 stepVector = movementObject.currentDir() * airAccel * deltaT;
   		newVelocity += Vector3(-stepVector.Y(), stepVector.X(), Scalar::zero);
   	}
   
   	if (buttons & kBtnStepRight)		// Sidestep right
   	{
   		Vector3 stepVector = movementObject.currentDir() * airAccel * deltaT;
   		newVelocity += Vector3(stepVector.Y(), -stepVector.X(), Scalar::zero);
   	}
   
	}
	else
	{
//#else
      assert(0);        // kts removed 1/12/2003 01:12:47, let me know if anyone wants this style of control
#if 0
// --------- This is the "Velocity" style camera-centric joystick code
   	if ( buttons & (EJ_BUTTONF_UP | EJ_BUTTONF_DOWN | EJ_BUTTONF_LEFT | EJ_BUTTONF_RIGHT) )
   	{
   		Scalar turnRate = movementObject.GetMovementBlockPtr()->GetTurnRate() * deltaT;
   
   		const Vector3& cameraLookAt = theLevel->camera()->GetLookAt();
   		Angle cameraAngle = cameraLookAt.X().ATan2(cameraLookAt.Y());
   		Angle quantizedCameraAngle(Angle::zero);
   		Angle boundary(Angle::Degree(SCALAR_CONSTANT(22.5)));
   		const Angle rotationQuantum(Angle::Degree(SCALAR_CONSTANT(45)));
   		while (cameraAngle > boundary)
   		{
   			quantizedCameraAngle += rotationQuantum;
   			boundary += rotationQuantum;
   		}
   
   		// Read joystick and figure out our intended direction
   		Vector3 motionVector(Vector3::zero);
   
   		if (buttons & EJ_BUTTONF_UP)	// Movement away from camera
   			motionVector += Vector3::unitX;
   
   		if (buttons & EJ_BUTTONF_DOWN)	// Movement toward camera
   			motionVector += Vector3::unitNegativeX;
   
   		if (buttons & EJ_BUTTONF_LEFT)	// Movement toward camera's left
   			motionVector += Vector3::unitY;
   
   		if (buttons & EJ_BUTTONF_RIGHT)	// Movement toward camera's right
   			motionVector += Vector3::unitNegativeY;
   
   		// Transform motionVector by camera angle
   		motionVector.Normalize();
   		motionVector.RotateZ(quantizedCameraAngle);
   
   		// Rotate object towards direction of motion
   		Angle motionAngle(motionVector.X().ATan2(motionVector.Y()));
         Euler rotation = actorAttr.Rotation();
   		rotation.SetC( CalcNewHeading( rotation.GetC(), motionAngle, turnRate ) );
         actorAttr.SetRotation(rotation);
   
   		newVelocity += (motionVector * airAccel * deltaT);
   
   		// Add a little upward force if Jump button is held
   		if ( buttons & kBtnJump )
   			newVelocity += Vector3( Scalar::zero, Scalar::zero,
   									movementObject.GetMovementBlockPtr()->GetFallingAcceleration() * deltaT * Scalar::half );
   	}
#endif         // 0
	}
//#endif	// __DOOMSTICK__

	// SMB-style variable jump height: releasing kBtnJump mid-jump truncates
	// remaining upward impulse so a tap is short and a hold reaches full apex.
	if (!(buttons & kBtnJump))
		handlerData->jumpDuration = Scalar::zero;

	if (handlerData->jumpDuration > Scalar::zero)
	{
		Scalar jumpDurToApply( handlerData->jumpDuration.Min(deltaT) );
		newVelocity += Vector3(Scalar::zero, Scalar::zero, movementObject.GetMovementBlockPtr()->GetJumpingAcceleration() * jumpDurToApply);
   		Scalar jumpPct = movementObject.GetMovementBlockPtr()->GetJumpingMomentumTransfer();
		newVelocity += Vector3(Scalar::zero, Scalar::zero, ((actorAttr.LinVelocity().X().Abs() * jumpPct) +
								 (actorAttr.LinVelocity().Y().Abs() * jumpPct)) * jumpDurToApply);
		handlerData->jumpDuration -= jumpDurToApply;
	}

	// Make gravity happen
	newVelocity -= Vector3(Scalar::zero, Scalar::zero, movementObject.GetMovementBlockPtr()->GetFallingAcceleration() * deltaT);

	// Add in force vectors from area effects, etc.
	Vector3 forceVector = SumForceVectors(movementObject);
	newVelocity += (forceVector * deltaT);

	// Clip speed at MaxSpeed
	Scalar maxSpeed = movementObject.GetMovementBlockPtr()->GetMaxAirSpeed();
	Scalar newSpeed = newVelocity.Length();
	if (newSpeed > maxSpeed)
		newVelocity *= (maxSpeed / newSpeed);


	// "Sustain" mode: when AirAcceleration=0 (joystick has no in-air authority
	// to add velocity), holding a Step direction that matches current X motion
	// suppresses horizontal drag for the frame, so takeoff momentum persists
	// while held but decays when released. SMB-style "hold forward to keep
	// sprint speed mid-jump." Currently X-only — sufficient for sideview play;
	// generalize via currentDir() projection if Y-axis sustain becomes needed.
	bool sustainHoriz =
	    airAccel == Scalar::zero &&
	    (((buttons & kBtnStepRight) && newVelocity.X() > Scalar::zero) ||
	     ((buttons & kBtnStepLeft)  && newVelocity.X() < Scalar::zero));

	// Make air drag happen
	Scalar hDrag = sustainHoriz
	                 ? Scalar::one
	                 : Scalar::one - (movementObject.GetMovementBlockPtr()->GetHorizAirDrag() * deltaT );
	Scalar vDrag = Scalar::one - (movementObject.GetMovementBlockPtr()->GetVertAirDrag() * deltaT );
	if ( hDrag < Scalar::zero )
		hDrag = Scalar::zero;
	if ( vDrag < Scalar::zero )
		vDrag = Scalar::zero;

	newVelocity.SetX( newVelocity.X() * hDrag );
	newVelocity.SetY( newVelocity.Y() * hDrag );
	newVelocity.SetZ( newVelocity.Z() * vDrag );

	// Apply new velocity to velocity and predicted position
#ifdef PHYSICS_ENGINE_JOLT
	{
		uint32_t charID = actorAttr.JoltCharacterID();
		if (charID != kJoltInvalidBodyID)
		{
			JoltCharacterSetLinVelocity(charID, newVelocity);
			JoltCharacterUpdate(charID, deltaT.AsFloat());
			actorAttr.JoltSyncFromCharacter(JoltCharacterGetPosition(charID));
			actorAttr.SetLinVelocity(JoltCharacterGetLinVelocity(charID));
			handlerData->supportingObject = NULL;
			return;
		}
	}
#endif // PHYSICS_ENGINE_JOLT
	actorAttr.SetPredictedPosition(actorAttr.Position() +
			((newVelocity + actorAttr.OldLinVelocity()) * Scalar::half * deltaT));

	actorAttr.Validate();
	actorAttr.SetLinVelocity(newVelocity);

#ifdef PHYSICS_TELEMETRY
	if (physicalObject.kind() == BaseObject::Player_KIND)
	{
		std::cout << "---- ( Air ) New Frame:  T = " << clock.Current();
		std::cout << "; DeltaT = " << clock.Delta();
		if (buttons & kBtnStepRight)
			std::cout << "   * Button Pressed *";
		std::cout << std::endl << "Player's velocity: " << newVelocity << std::endl;
		std::cout << "Player's deltaPos: " << actorAttr.GetDeltaPos() << std::endl;
		std::cout << "    deltaPos / deltaT = " << actorAttr.GetDeltaPos() / clock.Delta() << std::endl;
		std::cout << "Player's position: " << actorAttr.PredictedPosition() << std::endl << std::endl;
	}

#endif	// PHYSICS_TELEMETRY

	handlerData->supportingObject = NULL;	// Clear this and let the collision system set it again
}

//============================================================================

void 
ClimbHandler::init(MovementManager& movementManager, MovementObject& movementObject)
{
#define CLIMB_RATE SCALAR_CONSTANT(1.5)

#define GROUND_DIR_L		SCALAR_CONSTANT(0.75)
#define GROUND_DIR_D		Scalar::zero
#define GROUND_DIR_R		SCALAR_CONSTANT(0.25)
#define GROUND_DIR_U		Scalar::half

	assert( movementManager.MovementBlock()->Mobility == MOBILITY_PHYSICS );

	movementObject.MovementStateChanged( MovementObject::Climb_state );

	MovementHandlerData* handlerData = movementManager.GetMovementHandlerData();
	assert(ValidPtr(handlerData));
	assert(ValidPtr(handlerData->objectClimbing));

	PhysicalAttributes& actorAttr = movementObject.GetWritablePhysicalAttributes();
	const PhysicalAttributes& otherAttr = handlerData->objectClimbing->GetPhysicalAttributes();
	actorAttr.Validate();
	otherAttr.Validate();

#if 0
	Scalar distance = ((actorAttr.MaxZ() - otherAttr.MaxZ()) * SCALAR_CONSTANT(10));
	int32 tableIndex;
	memcpy(&tableIndex, &distance, sizeof(int32));
	tableIndex = tableIndex >> 16;
	Scalar time = CLIMB_FRAME_TABLE[tableIndex];
	if (time > thisActor->anim->Duration())
		time = thisActor->anim->Duration();
	thisActor->anim->ApplyTime(time);
#endif

	actorAttr.SetLinVelocity(handlerData->objectClimbing->GetPhysicalAttributes().LinVelocity());

#pragma message("Replace this code with something in AirHandler!")
//	switch (handlerData->whichDir)
//	{
//		case CLIMB_DIR_U:
//			actorAttr.SetRotationC( Angle::Revolution( GROUND_DIR_D ) );
//			break;
//		case CLIMB_DIR_D:
//			actorAttr.SetRotationC( Angle::Revolution( GROUND_DIR_U ) );
//			break;
//		case CLIMB_DIR_L:
//			actorAttr.SetRotationC( Angle::Revolution( GROUND_DIR_R ) );
//			break;
//		case CLIMB_DIR_R:
//			actorAttr.SetRotationC( Angle::Revolution( GROUND_DIR_L ) );
//			break;
//		default:
//			AssertMsg(0, "Climb direction is invalid");
//	}
}

//============================================================================
bool
ClimbHandler::check()
{
	assert(0);
  	return false;
}

//============================================================================

bool
ClimbHandler::update(MovementManager& movementManager, MovementObject& movementObject, const BaseObjectList& baseObjectList )
{
	PhysicalAttributes& actorAttr = movementObject.GetWritablePhysicalAttributes();
	actorAttr.Validate();
	joystickButtonsF buttons = movementObject.GetInputDevice()->arePressed();

	MovementHandlerData* handlerData = movementManager.GetMovementHandlerData();
	assert(ValidPtr(handlerData));

	if (!(buttons & kBtnJump))
	{
		handlerData->jumpDuration = Scalar::zero;
		movementManager.SetMovementHandler(&theAirHandler,movementObject);
		return true;
	}

	PhysicalObject* objectClimbing = handlerData->objectClimbing;
	assert(ValidPtr(objectClimbing));
	const PhysicalAttributes& otherAttr = objectClimbing->GetPhysicalAttributes();
	otherAttr.Validate();

	if (actorAttr.Min().Z() >= otherAttr.Max().Z())		// Climb up on top
	{
#define OFFSET_AMOUNT SCALAR_CONSTANT( 0.15 )
		Vector3 offsetVector = movementObject.currentDir() * OFFSET_AMOUNT;

		actorAttr.AddLinVelocity(offsetVector);
		handlerData->stunnedUntil = Scalar::zero;
		handlerData->wheelVelocity = Vector3::zero;
		movementManager.SetMovementHandler(&theGroundHandler,movementObject);
		return true;
	}

#if 0
	Scalar distance = ((actorAttr.MaxZ() - otherAttr.MaxZ()) * SCALAR_CONSTANT(10));

	if (distance <= Scalar::zero)		// go to hang animation if fully extended
	{
		thisActor->anim->SetAnimationCycle( MovementObject::HANG );
		thisActor->anim->ApplyDeltaTime( deltaT );
	}
	else	// continue climbing
	{
		int32 tableIndex;
		memcpy(&tableIndex, &distance, sizeof(int32));
		tableIndex = tableIndex >> 16;
		Scalar time = CLIMB_FRAME_TABLE[tableIndex];
		thisActor->anim->SetAnimationCycle( MovementObject::CLIMB_PULL_UP );
		if (time > thisActor->anim->Duration())
			time = thisActor->anim->Duration();
		thisActor->anim->ApplyTime(time);
	}

#endif
	return true;
}

//============================================================================

void
ClimbHandler::predictPosition(MovementManager& movementManager, MovementObject& movementObject, const Clock& clock, const BaseObjectList& baseObjectList)
{
	PhysicalAttributes& actorAttr = movementObject.GetWritablePhysicalAttributes();
	const PhysicalAttributes& otherAttr = movementManager.GetMovementHandlerData()->objectClimbing->GetPhysicalAttributes();
	actorAttr.Validate();
	otherAttr.Validate();
	joystickButtonsF buttons = movementObject.GetInputDevice()->arePressed();
	Vector3 motionVector = Vector3::zero;
	Vector3 supportingVelocity = otherAttr.LinVelocity();

	if ( buttons & EJ_BUTTONF_UP )
	{
		motionVector.SetZ( CLIMB_RATE );
	}
	else if ( (actorAttr.Max().Z() >= otherAttr.Max().Z()) && (buttons & EJ_BUTTONF_DOWN) )
	{
		motionVector.SetZ( -CLIMB_RATE );
	}

	actorAttr.SetPredictedPosition(actorAttr.Position() + supportingVelocity +
										   	(motionVector * clock.Delta()));

	actorAttr.SetLinVelocity(motionVector + (supportingVelocity / clock.Delta()));
}

//============================================================================

void
NullHandler::init(MovementManager& /*movementManager*/,  MovementObject& /*movementObject*/)
{
	//assert( movementManager.MovementBlock()->Mobility == MOBILITY_ANCHORED );
}

//============================================================================

bool
NullHandler::check()
{
	assert(0);
	return true;
}

//============================================================================

bool
NullHandler::update( MovementManager& /*movementManager*/, MovementObject& movementObject, const BaseObjectList& baseObjectList )
{
   char msgData[msgDataSize];

	MsgPort& msgPort =  movementObject.GetMsgPort();

	// EAT ALL COLLISION MESSAGES
	while( msgPort.GetMsgByType(MsgPort::COLLISION, &msgData,msgDataSize))		// Receive a message
		;

	return true;
}

//============================================================================

void
NullHandler::predictPosition(MovementManager&, MovementObject& /*movementObject*/, const Clock& , const BaseObjectList& baseObjectList )
{

}

//==============================================================================

size_t
NullHandler::DataSize()
{
   return 0;            // no data
}

//==============================================================================

