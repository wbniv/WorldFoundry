//============================================================================
// dir.cc:  FSN-style directory tower actor. No behaviour — purely visual.
//          Spawned at runtime by the Director Forth script; scale mailboxes
//          3040-3042 set tower height proportional to √(file count in subdir).
//============================================================================

#include "dir.hp"
#include "actor.hp"

//============================================================================

Dir::Dir(const SObjectStartupData* startupData)
	: Actor(startupData)
{
}

//============================================================================

Actor::EActorKind
Dir::kind() const
{
	assert(GetMovementBlockPtr()->MovementClass == Actor::Dir_KIND);
	return Actor::Dir_KIND;
}

//============================================================================

void
Dir::update()
{
	Actor::update();
}

//============================================================================

void
Dir::Collision(PhysicalObject& other, const Vector3& normal)
{
	Actor::Collision(other, normal);
}

//============================================================================

Actor*
OadDir(const SObjectStartupData* startupData)
{
	return new (*startupData->memory) Dir(startupData);
}

//============================================================================
