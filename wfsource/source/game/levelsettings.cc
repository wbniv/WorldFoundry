#include <oas/levelsettings.ht>
#include "levelsettings.hp"
LevelSettings::LevelSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind LevelSettings::kind() const { return Actor::LevelSettings_KIND; }
void LevelSettings::update() {}
bool LevelSettings::CanRender() const { return false; }
bool LevelSettings::CanUpdate() const { return false; }
Actor* OadLevelSettings(const SObjectStartupData* data) { return new (*data->memory) LevelSettings(data); }
