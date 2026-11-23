#include <oas/lighthousesettings.ht>
#include "lighthousesettings.hp"
LighthouseSettings::LighthouseSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind LighthouseSettings::kind() const { return Actor::LighthouseSettings_KIND; }
void LighthouseSettings::update() {}
bool LighthouseSettings::CanRender() const { return false; }
bool LighthouseSettings::CanUpdate() const { return false; }
Actor* OadLighthouseSettings(const SObjectStartupData* data) { return new (*data->memory) LighthouseSettings(data); }
