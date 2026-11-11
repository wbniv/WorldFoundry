#include <oas/reefsettings.ht>
#include "reefsettings.hp"
ReefSettings::ReefSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind ReefSettings::kind() const { return Actor::ReefSettings_KIND; }
void ReefSettings::update() {}
bool ReefSettings::CanRender() const { return false; }
bool ReefSettings::CanUpdate() const { return false; }
Actor* OadReefSettings(const SObjectStartupData* data) { return new (*data->memory) ReefSettings(data); }
