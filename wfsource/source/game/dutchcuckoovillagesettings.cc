#include <oas/dutchcuckoovillagesettings.ht>
#include "dutchcuckoovillagesettings.hp"
DutchCuckooVillageSettings::DutchCuckooVillageSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind DutchCuckooVillageSettings::kind() const { return Actor::DutchCuckooVillageSettings_KIND; }
void DutchCuckooVillageSettings::update() {}
bool DutchCuckooVillageSettings::CanRender() const { return false; }
bool DutchCuckooVillageSettings::CanUpdate() const { return false; }
Actor* OadDutchCuckooVillageSettings(const SObjectStartupData* data) { return new (*data->memory) DutchCuckooVillageSettings(data); }
