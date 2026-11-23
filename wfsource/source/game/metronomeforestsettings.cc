#include <oas/metronomeforestsettings.ht>
#include "metronomeforestsettings.hp"
MetronomeForestSettings::MetronomeForestSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind MetronomeForestSettings::kind() const { return Actor::MetronomeForestSettings_KIND; }
void MetronomeForestSettings::update() {}
bool MetronomeForestSettings::CanRender() const { return false; }
bool MetronomeForestSettings::CanUpdate() const { return false; }
Actor* OadMetronomeForestSettings(const SObjectStartupData* data) { return new (*data->memory) MetronomeForestSettings(data); }
