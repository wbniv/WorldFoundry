//============================================================================
// gold.cc:  Collectible Gold coin. Touch by Player -> credit player's GOLD
//           mailbox (3001) + remove self. Pickup-driven despawn (SFX deferred).
//           See docs/plans/2026-05-19-smb-block-generator-coin.md (engine #3).
//
// NOTE: gold.ht is hand-authored as a STOPGAP (= target.ht renamed Target->Gold)
// because the .ht C++ codegen is broken (oadtypes.s + prep emit invalid quoted
// identifiers). Regenerate via the fixed codegen when it lands.
// See TODO.md (BUILD / TOOLCHAIN) for the broken-.ht-codegen tracking.
//============================================================================

#include <oas/gold.ht>					// _Gold oad structure
#include "gold.hp"
#include "actor.hp"						// object enumeration (Player_KIND)
#include "level.hp"						// theLevel->SetPendingRemove
#include <baseobject/baseobject.hp>		// IsActor
#include <mailbox/mailbox.hp>			// EMAILBOX_GOLD

//============================================================================

static const float kGoldTTL = 3.0f;

Gold::Gold(const SObjectStartupData* startupData)
	: Actor(startupData)
	, _despawnTime(startupData->currentTime.Current() + Scalar(kGoldTTL))
{
}

//============================================================================

Actor::EActorKind
Gold::kind() const
{
	assert(GetMovementBlockPtr()->MovementClass == Actor::Gold_KIND);
	return Actor::Gold_KIND;
}

//============================================================================

void
Gold::update()
{
	if (theLevel->LevelClock().Current() >= _despawnTime)
	{
		theLevel->SetPendingRemove(this);
		return;
	}
	Actor::update();
}

//============================================================================

void
Gold::Collision(PhysicalObject& other, const Vector3& normal)
{
	// Preserve base behaviour: per-actor collider mailboxes (3044-3047) +
	// supporting-object bookkeeping.
	Actor::Collision(other, normal);

	// Picked up by the player: add Gold Value (OAD, default 1) to the player's
	// per-actor GOLD count, then vanish. Pickup detection rides the bidirectional
	// Jolt dispatch (engine change #1).
	if (IsActor(&other))
	{
		Actor& player = static_cast<Actor&>(other);
		if (player.kind() == Actor::Player_KIND)
		{
			Mailboxes& pm = player.GetMailboxes();
			pm.WriteMailbox(EMAILBOX_GOLD, pm.ReadMailbox(EMAILBOX_GOLD) + Scalar(getOad()->GoldValue));
			theLevel->SetPendingRemove(this);
		}
	}
}

//============================================================================

Actor*
OadGold(const SObjectStartupData* startupData)
{
	return new (*startupData->memory) Gold(startupData);
}

//============================================================================
