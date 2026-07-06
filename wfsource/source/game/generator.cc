//============================================================================
// Generator.cc:
// Copyright ( c ) 1995,1996,1997,1999,2000,2002l,2003 World Foundry Group  
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

//=============================================================================
//	Abstract:
//	History:
//			Created	From object.ccs using Prep
//
//	Class Hierarchy:
//			none
//
//	Dependancies:
//
//	Restrictions:
//
//	Example:
//
//============================================================================

#include <cstdio>
#include <oas/generator.ht>		// get oad structure information
#include "generator.hp"
#include "actor.hp"
#include "gamestrm.hp"
#include "level.hp"

//============================================================================

Generato::Generato( const SObjectStartupData* startupData ) : Actor( startupData )
{
	_generateMailBox = getOad()->ActivationMailBox;
	_delayBetweenGeneration = getOad()->GetGenerationRate();
	_delayBetweenGeneration = _delayBetweenGeneration.Invert();

	_timeToGenerate = startupData->currentTime.Current();				// generate one object immediatly

	_vect = Vector3( getOad()->GetObjectXVelocity(), getOad()->GetObjectYVelocity(), getOad()->GetObjectZVelocity() );
}

//============================================================================

/*virtual*/ Actor::EActorKind
Generato::kind() const
{
	return Actor::Generator_KIND;
}

//============================================================================

void
Generato::update()
{
	if( theLevel->LevelClock().Current() >= _timeToGenerate )
	{
		if( GetMailboxes().ReadMailbox(_generateMailBox) == Scalar::zero )
		{
			_timeToGenerate = theLevel->LevelClock().Current();				// reset timer so when goes on doesn't generate tons of objects
			// Engine change #2: was `return;` here. Dropped so Actor::update()
			// below (and thus this generator's own wf_Script) runs every tick,
			// like every other Actor subclass — the block-IS-generator self-detect
			// script lives there. The timer reset above still preserves the kts
			// anti-over-generation guarantee; only the incidental script skip is gone.
		}
		else
		{
		//[UNUSED]const _Movement* _movementData = GetMovementBlockPtr();
		int32 objectToGenerate = getOad()->ObjectToThrow;
		assert(objectToGenerate > 0);

		DBSTREAM1( cactor << "generating object " << objectToGenerate << std::endl; )
		_timeToGenerate += _delayBetweenGeneration;
		// kts added 4/9/96 7:04PM to prevent over-generation if it has been a while since we ran
		while(_timeToGenerate < theLevel->LevelClock().Current())
		{
			DBSTREAM1( cactor << "Generato::update: fast forward" << std::endl; )
			_timeToGenerate += _delayBetweenGeneration;
		}

		Scalar xRandomDisplacement = getOad()->GetRandomXRange();
		if ( xRandomDisplacement.AsBool() )
			//xRandomDisplacement = random( xRandomDisplacement ) - xRandomDisplacement/Scalar::two;
			xRandomDisplacement = Scalar::Random( -xRandomDisplacement, xRandomDisplacement );
		Scalar yRandomDisplacement = getOad()->GetRandomYRange();
		if ( yRandomDisplacement.AsBool() )
			//yRandomDisplacement = random( yRandomDisplacement );
			yRandomDisplacement = Scalar::Random( -yRandomDisplacement, yRandomDisplacement );
		Scalar zRandomDisplacement = getOad()->GetRandomZRange() - yRandomDisplacement/Scalar::two;
		if ( zRandomDisplacement.AsBool() )
			//zRandomDisplacement = random( zRandomDisplacement ) - zRandomDisplacement/Scalar::two;
			zRandomDisplacement = Scalar::Random( -zRandomDisplacement, zRandomDisplacement );

		Vector3 displacement( xRandomDisplacement, yRandomDisplacement, zRandomDisplacement );
		// Spawn at the XY centre but the TOP of the colspace so objects emerge
		// above the generator body (e.g. coins pop out of a ?-block top).
		Vector3 center = _physicalAttributes.GetColSpace().GetCenter( currentPos() );
		Scalar  topZ   = _physicalAttributes.GetColSpace().UnExpMax( currentPos() ).Z();
		// Offset spawn Z by the template's half-height so the spawned object's BOTTOM
		// lands at topZ rather than its centre (avoids Jolt depenetration ejection).
		SObjectStartupData* tmplData =
			(SObjectStartupData*)theLevel->FindTemplateObjectData(objectToGenerate);
		Scalar tmplHalfZ = Scalar::zero;
		if (tmplData)
		{
			Scalar tMinZ = Scalar::FromFixed32(tmplData->objectData->coarse.minZ);
			Scalar tMaxZ = Scalar::FromFixed32(tmplData->objectData->coarse.maxZ);
			tmplHalfZ = (tMaxZ - tMinZ) / Scalar::two;
		}
		Vector3 pos = Vector3( center.X(), center.Y(), topZ + tmplHalfZ ) + displacement;

		// generate an object
		std::fprintf(stderr, "Generato::FIRING obj=%d spawn=(%.2f,%.2f,%.2f) vel=(%.2f,%.2f,%.2f)\n",
			objectToGenerate, pos.X().AsFloat(), pos.Y().AsFloat(), pos.Z().AsFloat(),
			_vect.X().AsFloat(), _vect.Y().AsFloat(), _vect.Z().AsFloat());
		Actor* createdObject = theLevel->ConstructTemplateObject(objectToGenerate, _idxActor, pos,_vect);
		std::fprintf(stderr, "Generato: ConstructTemplateObject -> %s\n",
			createdObject ? "non-NULL" : "NULL");

		if(createdObject) {
			theLevel->AddObject( createdObject, pos );
			std::fprintf(stderr, "Generato: AddObject ok, coin actor_idx=%d\n",
				createdObject->GetActorIndex());
		}
		}		// end else (mailbox active) — engine change #2
	}
	Actor::update();		// always runs now (was skipped by the idle `return`)
}

//============================================================================
//============================================================================

Actor*
OadGenerator( const SObjectStartupData* startupData )
{
	return new (*startupData->memory) Generato(startupData);
}

//============================================================================

