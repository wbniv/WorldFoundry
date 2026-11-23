#include <oas/tourbillonsettings.ht>
#include "tourbillonsettings.hp"
TourbillonSettings::TourbillonSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind TourbillonSettings::kind() const { return Actor::TourbillonSettings_KIND; }
void TourbillonSettings::update() {}
bool TourbillonSettings::CanRender() const { return false; }
bool TourbillonSettings::CanUpdate() const { return false; }
Actor* OadTourbillonSettings(const SObjectStartupData* data) { return new (*data->memory) TourbillonSettings(data); }
