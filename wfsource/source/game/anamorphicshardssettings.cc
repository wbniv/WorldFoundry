#include <oas/anamorphicshardssettings.ht>
#include "anamorphicshardssettings.hp"
AnamorphicShardsSettings::AnamorphicShardsSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind AnamorphicShardsSettings::kind() const { return Actor::AnamorphicShardsSettings_KIND; }
void AnamorphicShardsSettings::update() {}
bool AnamorphicShardsSettings::CanRender() const { return false; }
bool AnamorphicShardsSettings::CanUpdate() const { return false; }
Actor* OadAnamorphicShardsSettings(const SObjectStartupData* data) { return new (*data->memory) AnamorphicShardsSettings(data); }
