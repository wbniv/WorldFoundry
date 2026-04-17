//=============================================================================
// gfx/glpipeline/backend_legacy.cc: Immediate-mode GL backend for renderer seam
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// One glBegin/glEnd per triangle, same as the pre-seam rendfcp/rendgtp/... TUs
// emitted inline. Drops away once every renderer TU is ported to the modern
// VBO backend for GLES 3.0.
//============================================================================

#include <gfx/renderer_backend.hp>
#include <gfx/pixelmap.hp>
#include <gfx/renderer.hp>

namespace
{

class LegacyRendererBackend : public RendererBackend
{
public:
    void DrawTriangle(const RBVertex& v0,
                      const RBVertex& v1,
                      const RBVertex& v2,
                      float nx, float ny, float nz,
                      const PixelMap* texture) override
    {
        if (texture)
        {
            glEnable(GL_TEXTURE_2D);
            texture->SetGLTexture();
        }
        else
        {
            glDisable(GL_TEXTURE_2D);
        }
        AssertGLOK();

        glBegin(GL_TRIANGLES);
        glNormal3f(nx, ny, nz);

        EmitVertex(v0, texture != nullptr);
        EmitVertex(v1, texture != nullptr);
        EmitVertex(v2, texture != nullptr);

        glEnd();
        AssertGLOK();
    }

private:
    static void EmitVertex(const RBVertex& v, bool textured)
    {
        float color[4] = { v.r, v.g, v.b, 1.0f };
        glMaterialfv(GL_FRONT, GL_AMBIENT, color);
        glMaterialfv(GL_FRONT, GL_DIFFUSE, color);
        if (textured)
            glTexCoord2f(v.u, v.v);
        glVertex4f(v.x, v.y, v.z, 1.0f);
    }
};

LegacyRendererBackend sLegacyBackend;

}  // namespace

RendererBackend& RendererBackendGet()
{
    return sLegacyBackend;
}
