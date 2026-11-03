// Loaded materials must opt in to both prelighting and Gouraud shading.
#include <gfx/material.hp>
#include <gfx/pixelmap.hp>
#include <cstdio>

int main()
{
    PixelMap texture(PixelMap::MEMORY_MAIN, 1, 1);
    for (int flags = 0; flags < 8; ++flags) {
        const PixelMap* pixelmap = flags & Material::TEXTURE_MAPPED ? &texture : nullptr;
        Material material(Color(255, 255, 255), flags, emptyTexture, pixelmap);
        const int expected = (flags & Material::LIGHTING_PRELIT) ? flags : (flags & ~Material::GOURAUD_SHADED);
        if ((material.GetMaterialFlags() & Material::RENDERER_SELECTION_MASK) != expected) {
            std::fprintf(stderr, "material flags %d became %d, expected %d\n",
                         flags, material.GetMaterialFlags(), expected);
            return 1;
        }
        _MaterialOnDisk disk{};
        disk._materialFlags = flags;
        disk._color = Color(255, 255, 255);
        Material loaded(disk, emptyTexture, pixelmap);
        if ((loaded.GetMaterialFlags() & Material::RENDERER_SELECTION_MASK) != expected) {
            std::fprintf(stderr, "loaded material flags %d became %d, expected %d\n",
                         flags, loaded.GetMaterialFlags(), expected);
            return 1;
        }
    }
    return 0;
}
