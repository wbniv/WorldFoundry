//==============================================================================
// rendfcl.cc: Renderer for FlatColorLit
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

int
RenderObject3D::RenderPoly3DFlatColorLit(Primitive* primitive)
{
    assert(primitive);
    POLY_F3& poly = (*(POLY_F3*)primitive);

    const float r = float(poly.r0) / 256.0f;
    const float g = float(poly.g0) / 256.0f;
    const float b = float(poly.b0) / 256.0f;

    RBVertex v[3];
    const Vector3_PS* const gte = globalRendererVariables.gteVect;
    for (int i = 0; i < 3; ++i)
    {
        v[i].x = gte[i].X().AsFloat();
        v[i].y = gte[i].Y().AsFloat();
        v[i].z = gte[i].Z().AsFloat();
        v[i].r = r;
        v[i].g = g;
        v[i].b = b;
        v[i].u = 0.0f;
        v[i].v = 0.0f;
    }

    const Vector3_PS& n = globalRendererVariables.currentRenderFace->normal;
    RendererBackendGet().DrawTriangle(v[0], v[1], v[2],
                                      n.X().AsFloat(),
                                      n.Y().AsFloat(),
                                      n.Z().AsFloat(),
                                      nullptr);
    return 1;
}

//============================================================================
