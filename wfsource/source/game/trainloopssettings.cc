#include <oas/trainloopssettings.ht>
#include "trainloopssettings.hp"
TrainLoopsSettings::TrainLoopsSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind TrainLoopsSettings::kind() const { return Actor::TrainLoopsSettings_KIND; }
void TrainLoopsSettings::update() {}
bool TrainLoopsSettings::CanRender() const { return false; }
bool TrainLoopsSettings::CanUpdate() const { return false; }
Actor* OadTrainLoopsSettings(const SObjectStartupData* data) { return new (*data->memory) TrainLoopsSettings(data); }
