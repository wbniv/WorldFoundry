#include <oas/bamboopondsettings.ht>
#include "bamboopondsettings.hp"
BambooPondSettings::BambooPondSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind BambooPondSettings::kind() const { return Actor::BambooPondSettings_KIND; }
void BambooPondSettings::update() {}
bool BambooPondSettings::CanRender() const { return false; }
bool BambooPondSettings::CanUpdate() const { return false; }
Actor* OadBambooPondSettings(const SObjectStartupData* data) { return new (*data->memory) BambooPondSettings(data); }
