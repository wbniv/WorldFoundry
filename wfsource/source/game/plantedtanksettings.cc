//============================================================================
// plantedtanksettings.cc: the planted tank's settings holder
// Copyright ( c ) 2026 World Foundry Group
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
//============================================================================

#include <oas/plantedtanksettings.ht>
#include "plantedtanksettings.hp"

PlantedTankSettings::PlantedTankSettings(const SObjectStartupData* startupData)
	: Actor(startupData)
{
}

Actor::EActorKind
PlantedTankSettings::kind() const
{
	assert(GetMovementBlockPtr()->MovementClass == Actor::PlantedTankSettings_KIND);
	return Actor::PlantedTankSettings_KIND;
}

void
PlantedTankSettings::update()
{
}

bool
PlantedTankSettings::CanRender() const
{
	return false;
}

bool
PlantedTankSettings::CanUpdate() const
{
	return false;
}

Actor*
OadPlantedTankSettings(const SObjectStartupData* startupData)
{
	return new (*startupData->memory) PlantedTankSettings(startupData);
}
