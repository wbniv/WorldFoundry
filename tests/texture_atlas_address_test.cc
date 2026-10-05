// Exercise production Material::InitPrimitive, including both textured paths.
// Only the test sees the private primitive builder; no production API changes.
#include <pigsys/pigsys.hp>
#include <gfx/color.hp>
#include <gfx/vertex.hp>
#include <gfx/rmuv.hp>
#include <gfx/math.hp>
#include <gfx/renderer.hp>
#define private public
#include <gfx/material.hp>
#undef private
#include <gfx/prim.hp>
#include <gfx/pixelmap.hp>
#include <gfx/vmem.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>

static void require(bool ok, const char* message)
{
    if (!ok) { std::fprintf(stderr, "%s\n", message); std::exit(1); }
}

int main()
{
    Display::VRAMWidth=2048;
    Display::VRAMHeight=2048;
    // A permanent map must not be limited by a smaller transient slot.
    VideoMemory::VRAMTransientWidth=256;
    VideoMemory::VRAMTransientHeight=256;
    int cases=0;
    for (int width : {1024,2048}) {
        // Allocation does not create a GL texture until Load(), so this test
        // exercises production coordinates without requiring a display.
        PixelMap map(PixelMap::MEMORY_VIDEO,width,2048);
        for (int x : {0,64,768,1024,1536}) {
            if (x+256>width) continue;
            for (int y : {0,256,768,1024,1536}) {
                Texture texture{};
                std::strcpy(texture.szTextureName,"atlas-probe");
                texture.u=x;texture.v=y;texture.w=256;texture.h=112;
                texture.bitdepth=15;
                for (int shading : {Material::FLAT_SHADED,Material::GOURAUD_SHADED}) {
                    int flags=shading|Material::TEXTURE_MAPPED|Material::LIGHTING_PRELIT;
                    Material material(Color(255,255,255),flags,texture,&map);
                    // Construct defaults to flat; explicitly exercise GT3 as well.
                    material.SetMaterialFlags(flags);
                    Vertex3D a,b,c;
                    a.u=Scalar::zero;a.v=Scalar::zero;
                    b.u=Scalar::one;b.v=Scalar::zero;
                    c.u=Scalar::one;c.v=Scalar::one;
                    a.color=b.color=c.color=Color(255,255,255);
                    Primitive primitive;
                    material.InitPrimitive(primitive,a,b,c);
                    if (shading==Material::FLAT_SHADED) {
                        const auto& p=*reinterpret_cast<POLY_FT3*>(&primitive);
                        int baseX=DecodeTPageX(p.tpage),baseY=DecodeTPageY(p.tpage);
                        require(p.u0+baseX==x && p.v0+baseY==y && p.u1+baseX==x+255 && p.v1+baseY==y && p.u2+baseX==x+255 && p.v2+baseY==y+111,"FT3 atlas address truncated");
                        require(p.pPixelMap==&map,"FT3 bound the wrong atlas");
                    } else {
                        const auto& p=*reinterpret_cast<POLY_GT3*>(&primitive);
                        int baseX=DecodeTPageX(p.tpage),baseY=DecodeTPageY(p.tpage);
                        require(p.u0+baseX==x && p.v0+baseY==y && p.u1+baseX==x+255 && p.v1+baseY==y && p.u2+baseX==x+255 && p.v2+baseY==y+111,"GT3 atlas address truncated");
                        require(p.pPixelMap==&map,"GT3 bound the wrong atlas");
                    }
                    ++cases;
                }
            }
        }
    }
    std::printf("PASS: %d production FT3/GT3 atlas cases, origins through 1536 on both axes, permanent/room sizes independent of transient settings\n",cases);
}
