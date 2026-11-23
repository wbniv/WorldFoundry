#include <oas/lavalampdigitssettings.ht>
#include "lavalampdigitssettings.hp"
LavaLampDigitsSettings::LavaLampDigitsSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind LavaLampDigitsSettings::kind() const { return Actor::LavaLampDigitsSettings_KIND; }
void LavaLampDigitsSettings::update() {}
bool LavaLampDigitsSettings::CanRender() const { return false; }
bool LavaLampDigitsSettings::CanUpdate() const { return false; }
Actor* OadLavaLampDigitsSettings(const SObjectStartupData* data) { return new (*data->memory) LavaLampDigitsSettings(data); }
