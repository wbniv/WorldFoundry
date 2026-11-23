#include <oas/hourtreesettings.ht>
#include "hourtreesettings.hp"
HourTreeSettings::HourTreeSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind HourTreeSettings::kind() const { return Actor::HourTreeSettings_KIND; }
void HourTreeSettings::update() {}
bool HourTreeSettings::CanRender() const { return false; }
bool HourTreeSettings::CanUpdate() const { return false; }
Actor* OadHourTreeSettings(const SObjectStartupData* data) { return new (*data->memory) HourTreeSettings(data); }
