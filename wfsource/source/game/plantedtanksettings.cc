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
#include "plant_settings.h"

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

void
PlantedTankSettings::OnPropertiesChanged(const std::uint32_t* fields, size_t count)
{
	const auto& settings = *static_cast<const _PlantedTankSettings*>(_oadData);
	bool seedChanged = false, waterChanged = false;
	auto* registry = wfprops::activeRegistry();
	const auto* object = registry ? registry->object(GetActorIndex()) : nullptr;
	for (size_t i = 0; object && i < count; ++i) {
		const auto* field = object->field(fields[i]);
		if (field && field->key == "Seed") seedChanged = true;
		if (field && field->key == "Water type") waterChanged = true;
	}
	planted::applyActorSettings(uint32_t(settings.Seed), settings.Watertype != 0,
	                            settings.Growthspeed, settings.Textures != 0, settings.Sway != 0,
	                            seedChanged, waterChanged);
}

Actor*
OadPlantedTankSettings(const SObjectStartupData* startupData)
{
	return new (*startupData->memory) PlantedTankSettings(startupData);
}
