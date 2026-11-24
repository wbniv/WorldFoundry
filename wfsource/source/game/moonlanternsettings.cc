#include <oas/moonlanternsettings.ht>
#include "moonlanternsettings.hp"
MoonLanternSettings::MoonLanternSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind MoonLanternSettings::kind() const { return Actor::MoonLanternSettings_KIND; }
void MoonLanternSettings::update() {}
bool MoonLanternSettings::CanRender() const { return false; }
bool MoonLanternSettings::CanUpdate() const { return false; }
Actor* OadMoonLanternSettings(const SObjectStartupData* data) { return new (*data->memory) MoonLanternSettings(data); }
