//==============================================================================
// rendgtl.cc: Renderer for GouraudTextureLit
// Copyright ( c ) 1997,98,99 World Foundry Group
//
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// This program is free software; you can redistribute it and/or
// modify it under the terms of the GNU General Public License
// Version 2 as published by the Free Software Foundation
//==============================================================================

#include <gfx/display.hp>
#include <gfx/rendobj3.hp>
#include <gfx/material.hp>
#include <gfx/renderer.hp>
#include <gfx/renderer_backend.hp>
#include <gfx/prim.hp>
#include <math/vector3.hp>
#include <math/vector3p.hp>
#include <math/scalar.hp>
#include <math/scalarps.hp>

extern RendererVariables globalRendererVariables;

#if defined(USE_ORDER_TABLES)
#error ORDER TABLES not used by glpipeline!
#endif

//==============================================================================

static inline void
CalcUV(unsigned short tpage,
       unsigned char uin, unsigned char vin,
       const PixelMap& texturePixelMap,
       float& uOut, float& vOut)
{
    ulong u(uin + DecodeTPageX(tpage));
    ulong v(vin + DecodeTPageY(tpage));

#if defined(VIDEO_MEMORY_IN_ONE_PIXELMAP)
    uOut = float(u) / VRAM_WIDTHF;
    vOut = float(v) / VRAM_HEIGHTF;
#else
    uOut = float(u) / texturePixelMap.GetBaseXSize();
    vOut = float(v) / texturePixelMap.GetBaseYSize();
#endif
}

//==============================================================================

int
RenderObject3D::RenderPoly3DGouraudTextureLit(Primitive* primitive)
{
    assert(primitive);
    POLY_GT3& poly = (*(POLY_GT3*)primitive);
    assert(ValidPtr(poly.pPixelMap));

    const unsigned char rArr[3] = { poly.r0, poly.r1, poly.r2 };
    const unsigned char gArr[3] = { poly.g0, poly.g1, poly.g2 };
    const unsigned char bArr[3] = { poly.b0, poly.b1, poly.b2 };
    const unsigned char uArr[3] = { poly.u0, poly.u1, poly.u2 };
    const unsigned char vArr[3] = { poly.v0, poly.v1, poly.v2 };

    RBVertex v[3];
    const Vector3_PS* const gte = globalRendererVariables.gteVect;
    for (int i = 0; i < 3; ++i)
    {
        v[i].x = gte[i].X().AsFloat();
        v[i].y = gte[i].Y().AsFloat();
        v[i].z = gte[i].Z().AsFloat();
        v[i].r = float(rArr[i]) / 256.0f;
        v[i].g = float(gArr[i]) / 256.0f;
        v[i].b = float(bArr[i]) / 256.0f;
        CalcUV(poly.tpage, uArr[i], vArr[i], *poly.pPixelMap, v[i].u, v[i].v);
    }

    const Vector3_PS& n = globalRendererVariables.currentRenderFace->normal;
    RendererBackendGet().DrawTriangle(v[0], v[1], v[2],
                                      n.X().AsFloat(),
                                      n.Y().AsFloat(),
                                      n.Z().AsFloat(),
                                      poly.pPixelMap);
    return 1;
}

//============================================================================
