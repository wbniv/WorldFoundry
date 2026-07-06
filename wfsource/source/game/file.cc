//============================================================================
// file.cc:  FSN-style file box actor. No behaviour — purely visual.
//           Spawned at runtime by the Director Forth script; scale mailboxes
//           3040-3042 set box height proportional to √file_size / 50.
//============================================================================

#include "file.hp"
#include "actor.hp"

//============================================================================

File::File(const SObjectStartupData* startupData)
	: Actor(startupData)
{
}

//============================================================================

Actor::EActorKind
File::kind() const
{
	assert(GetMovementBlockPtr()->MovementClass == Actor::File_KIND);
	return Actor::File_KIND;
}

//============================================================================

void
File::update()
{
	Actor::update();
}

//============================================================================

void
File::Collision(PhysicalObject& other, const Vector3& normal)
{
	Actor::Collision(other, normal);
}

//============================================================================

Actor*
OadFile(const SObjectStartupData* startupData)
{
	return new (*startupData->memory) File(startupData);
}

//============================================================================
