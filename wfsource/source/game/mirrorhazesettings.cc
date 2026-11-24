#include <oas/mirrorhazesettings.ht>
#include "mirrorhazesettings.hp"
MirrorHazeSettings::MirrorHazeSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind MirrorHazeSettings::kind() const { return Actor::MirrorHazeSettings_KIND; }
void MirrorHazeSettings::update() {}
bool MirrorHazeSettings::CanRender() const { return false; }
bool MirrorHazeSettings::CanUpdate() const { return false; }
Actor* OadMirrorHazeSettings(const SObjectStartupData* data) { return new (*data->memory) MirrorHazeSettings(data); }
