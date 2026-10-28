#include <game/doom_fire.hp>
#include <game/actor.hp>
#include <game/level.hp>
#include <renderassets/rendacto.hp>
#include <unordered_map>
#include <memory>

extern Level* theLevel;

namespace {
std::unordered_map<int, std::unique_ptr<DoomFireField> > g_fields;
}

bool WFUpdateDoomFire(int actorIndex, int x, int y, int width, int height,
                      double clockSeconds, bool reducedMotion, bool modal)
{
    if (!theLevel || actorIndex <= 0 || actorIndex >= theLevel->GetMaxObjectIndex() ||
        width <= 0 || height <= 0 || width > 128 || height > 128)
        return false;
    Actor* actor = theLevel->GetActorNoTemplate(actorIndex);
    if (!actor || !actor->AssetsBound()) return false;
    auto found = g_fields.find(actorIndex);
    if (found == g_fields.end()) {
        const uint32_t seed = 0x9e3779b9u ^ (uint32_t)actorIndex * 0x85ebca6bu;
        found = g_fields.emplace(actorIndex,
            std::unique_ptr<DoomFireField>(new DoomFireField(width, height, seed))).first;
    }
    DoomFireField& field = *found->second;
    if (field.Width() != width || field.Height() != height) return false;
    if (!field.Advance(clockSeconds, reducedMotion, modal)) return true;
    return actor->GetRenderActor().UpdateMaterialTextureRGBA8(0, x, y, width, height,
                                                              field.Pixels());
}
