#include <oas/discussettings.ht>
#include "discussettings.hp"
#include "../../../engine/indexed_palette.h"
#include <cstdio>

DiscusSettings::DiscusSettings(const SObjectStartupData* data) : Actor(data) {}
Actor::EActorKind DiscusSettings::kind() const { return Actor::DiscusSettings_KIND; }
void DiscusSettings::update() {
    const auto* settings = static_cast<const _DiscusSettings*>(_oadData);
    if (settings && settings->Palette >= 0) {
        auto& palette = wfpalette::active();
        const auto selected = static_cast<std::size_t>(settings->Palette);
        if (palette.current() != selected && palette.select(selected))
            std::fprintf(stderr, "INDEXED_PALETTE selection=%zu\n", selected);
    }
}
bool DiscusSettings::CanRender() const { return false; }
bool DiscusSettings::CanUpdate() const { return true; }
Actor* OadDiscusSettings(const SObjectStartupData* data) { return new (*data->memory) DiscusSettings(data); }
