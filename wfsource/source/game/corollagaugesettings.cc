#include <oas/corollagaugesettings.ht>
#include "corollagaugesettings.hp"
#include "../../../engine/indexed_palette.h"
#include <cstdio>
CorollaGaugeSettings::CorollaGaugeSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind CorollaGaugeSettings::kind() const { return Actor::CorollaGaugeSettings_KIND; }
void CorollaGaugeSettings::update() {
    const auto* settings = static_cast<const _CorollaGaugeSettings*>(_oadData);
    if (settings && settings->Palette >= 0) {
        auto& palette = wfpalette::active();
        const auto selected = static_cast<std::size_t>(settings->Palette);
        if (palette.current() != selected && palette.select(selected))
            std::fprintf(stderr, "COROLLA_PALETTE selection=%zu\n", selected);
    }
}
bool CorollaGaugeSettings::CanRender() const { return false; }
bool CorollaGaugeSettings::CanUpdate() const { return true; }
Actor* OadCorollaGaugeSettings(const SObjectStartupData* data) { return new (*data->memory) CorollaGaugeSettings(data); }
