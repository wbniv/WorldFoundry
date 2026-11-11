#include <oas/jellyfishsettings.ht>
#include "jellyfishsettings.hp"
JellyfishSettings::JellyfishSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind JellyfishSettings::kind() const { return Actor::JellyfishSettings_KIND; }
void JellyfishSettings::update() {}
bool JellyfishSettings::CanRender() const { return false; }
bool JellyfishSettings::CanUpdate() const { return false; }
Actor* OadJellyfishSettings(const SObjectStartupData* data) { return new (*data->memory) JellyfishSettings(data); }
