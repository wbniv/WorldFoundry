#include <oas/fieldtypes.ht>
#include "fieldtypes.hp"
FieldTypes::FieldTypes(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind FieldTypes::kind() const { return Actor::FieldTypes_KIND; }
void FieldTypes::update() {}
bool FieldTypes::CanRender() const { return false; }
bool FieldTypes::CanUpdate() const { return false; }
Actor* OadFieldTypes(const SObjectStartupData* data) { return new (*data->memory) FieldTypes(data); }
