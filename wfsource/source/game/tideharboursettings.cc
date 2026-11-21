#include <oas/tideharboursettings.ht>
#include "tideharboursettings.hp"
TideHarbourSettings::TideHarbourSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind TideHarbourSettings::kind() const { return Actor::TideHarbourSettings_KIND; }
void TideHarbourSettings::update() {}
bool TideHarbourSettings::CanRender() const { return false; }
bool TideHarbourSettings::CanUpdate() const { return false; }
Actor* OadTideHarbourSettings(const SObjectStartupData* data) { return new (*data->memory) TideHarbourSettings(data); }
