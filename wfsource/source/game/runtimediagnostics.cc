#include <oas/runtimediagnostics.ht>
#include "runtimediagnostics.hp"
RuntimeDiagnostics::RuntimeDiagnostics(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind RuntimeDiagnostics::kind() const { return Actor::RuntimeDiagnostics_KIND; }
void RuntimeDiagnostics::update() {}
bool RuntimeDiagnostics::CanRender() const { return false; }
bool RuntimeDiagnostics::CanUpdate() const { return false; }
Actor* OadRuntimeDiagnostics(const SObjectStartupData* data) { return new (*data->memory) RuntimeDiagnostics(data); }
