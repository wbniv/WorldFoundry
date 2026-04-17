//==============================================================================
// rendgtp.cc: Renderer for GouraudTexturePreLit
// Copyright ( c ) 1997,98,99 World Foundry Group
//
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// This program is free software; you can redistribute it and/or
// modify it under the terms of the GNU General Public License
// Version 2 as published by the Free Software Foundation
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
// or see www.fsf.org

// ===========================================================================
// Description: GouraudTexturePreLit — per-vertex color + texture, no lighting.
// Original Author: Kevin T. Seghetti
//============================================================================

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
RenderObject3D::RenderPoly3DGouraudTexturePreLit(Primitive* primitive)
{
    assert(primitive);
    POLY_GT3& poly = (*(POLY_GT3*)primitive);
    assert(ValidPtr(poly.pPixelMap));

    RBVertex v[3];
    const Vector3_PS* const gte = globalRendererVariables.gteVect;

    v[0].x = gte[0].X().AsFloat();
    v[0].y = gte[0].Y().AsFloat();
    v[0].z = gte[0].Z().AsFloat();
    v[0].r = float(poly.r0) / 256.0f;
    v[0].g = float(poly.g0) / 256.0f;
    v[0].b = float(poly.b0) / 256.0f;
    CalcUV(poly.tpage, poly.u0, poly.v0, *poly.pPixelMap, v[0].u, v[0].v);

    v[1].x = gte[1].X().AsFloat();
    v[1].y = gte[1].Y().AsFloat();
    v[1].z = gte[1].Z().AsFloat();
    v[1].r = float(poly.r1) / 256.0f;
    v[1].g = float(poly.g1) / 256.0f;
    v[1].b = float(poly.b1) / 256.0f;
    CalcUV(poly.tpage, poly.u1, poly.v1, *poly.pPixelMap, v[1].u, v[1].v);

    v[2].x = gte[2].X().AsFloat();
    v[2].y = gte[2].Y().AsFloat();
    v[2].z = gte[2].Z().AsFloat();
    v[2].r = float(poly.r2) / 256.0f;
    v[2].g = float(poly.g2) / 256.0f;
    v[2].b = float(poly.b2) / 256.0f;
    CalcUV(poly.tpage, poly.u2, poly.v2, *poly.pPixelMap, v[2].u, v[2].v);

    const Vector3_PS& n = globalRendererVariables.currentRenderFace->normal;
    RendererBackendGet().DrawTriangle(v[0], v[1], v[2],
                                      n.X().AsFloat(),
                                      n.Y().AsFloat(),
                                      n.Z().AsFloat(),
                                      poly.pPixelMap);
    return 1;
}

//============================================================================
