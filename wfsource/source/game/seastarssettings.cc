#include <oas/seastarssettings.ht>
#include "seastarssettings.hp"
SeaStarsSettings::SeaStarsSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind SeaStarsSettings::kind() const { return Actor::SeaStarsSettings_KIND; }
void SeaStarsSettings::update() {}
bool SeaStarsSettings::CanRender() const { return false; }
bool SeaStarsSettings::CanUpdate() const { return false; }
Actor* OadSeaStarsSettings(const SObjectStartupData* data) { return new (*data->memory) SeaStarsSettings(data); }
