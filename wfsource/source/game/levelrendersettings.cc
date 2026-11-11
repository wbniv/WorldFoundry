#include <oas/levelrendersettings.ht>
#include "levelrendersettings.hp"
LevelRenderSettings::LevelRenderSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind LevelRenderSettings::kind() const { return Actor::LevelRenderSettings_KIND; }
void LevelRenderSettings::update() {}
bool LevelRenderSettings::CanRender() const { return false; }
bool LevelRenderSettings::CanUpdate() const { return false; }
Actor* OadLevelRenderSettings(const SObjectStartupData* data) { return new (*data->memory) LevelRenderSettings(data); }
