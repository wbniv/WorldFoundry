#include <oas/cuckoovillagesettings.ht>
#include "cuckoovillagesettings.hp"
CuckooVillageSettings::CuckooVillageSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind CuckooVillageSettings::kind() const { return Actor::CuckooVillageSettings_KIND; }
void CuckooVillageSettings::update() {}
bool CuckooVillageSettings::CanRender() const { return false; }
bool CuckooVillageSettings::CanUpdate() const { return false; }
Actor* OadCuckooVillageSettings(const SObjectStartupData* data) { return new (*data->memory) CuckooVillageSettings(data); }
