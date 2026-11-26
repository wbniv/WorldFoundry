#include <oas/lavalampsettings.ht>
#include "lavalampsettings.hp"
LavaLampSettings::LavaLampSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind LavaLampSettings::kind() const { return Actor::LavaLampSettings_KIND; }
void LavaLampSettings::update() {}
bool LavaLampSettings::CanRender() const { return false; }
bool LavaLampSettings::CanUpdate() const { return false; }
Actor* OadLavaLampSettings(const SObjectStartupData* data) { return new (*data->memory) LavaLampSettings(data); }
