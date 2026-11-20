#include <oas/seastarssettings.ht>
#include "seastarssettings.hp"
#include "camera.hp"
#include "level.hp"
#include <random>
SeaStarsSettings::SeaStarsSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind SeaStarsSettings::kind() const { return Actor::SeaStarsSettings_KIND; }
bool SeaStarsSettings::CanRender() const { return false; }
// Runs every frame, but only the first does anything: it writes this entry's random seed.
bool SeaStarsSettings::CanUpdate() const { return true; }

RenderCamera* SeaStarsSettings::renderCamera() const {
    return (theLevel && theLevel->camera()) ? &theLevel->camera()->GetRenderCamera() : nullptr;
}

// The camera's own strength is the authored "On" value, so remember it before the first edit.
void SeaStarsSettings::captureAuthoredCaustics(RenderCamera& camera) {
    if (_captured) return;
    _authoredCaustics = camera.CausticStrength();
    _captured = true;
}

void SeaStarsSettings::update() {
    if (!_entrySeeded) {
        _entrySeeded = true;
        std::random_device entropy;
        GetMailboxes().WriteMailbox(kSeaStarsEntrySeedMailbox, Scalar(float(1 + entropy() % 32767)));
    }
    if (RenderCamera* camera = renderCamera()) captureAuthoredCaustics(*camera);
}

void SeaStarsSettings::OnPropertiesChanged(const std::uint32_t*, size_t) {
    RenderCamera* camera = renderCamera();
    if (!camera) return;
    captureAuthoredCaustics(*camera);
    const auto& settings = *static_cast<const _SeaStarsSettings*>(_oadData);
    camera->SetCausticStrength(settings.Caustics != 0 ? _authoredCaustics : 0.f);
}
Actor* OadSeaStarsSettings(const SObjectStartupData* data) { return new (*data->memory) SeaStarsSettings(data); }
