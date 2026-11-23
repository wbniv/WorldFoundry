#include <oas/globesunringsettings.ht>
#include "globesunringsettings.hp"
GlobeSunRingSettings::GlobeSunRingSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind GlobeSunRingSettings::kind() const { return Actor::GlobeSunRingSettings_KIND; }
void GlobeSunRingSettings::update() {}
bool GlobeSunRingSettings::CanRender() const { return false; }
bool GlobeSunRingSettings::CanUpdate() const { return false; }
Actor* OadGlobeSunRingSettings(const SObjectStartupData* data) { return new (*data->memory) GlobeSunRingSettings(data); }
