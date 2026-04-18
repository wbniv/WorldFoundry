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
#include <gfx/display.hp>           // LoadGLMatrixFromMatrix34
#include <math/matrix34.hp>

// GLU is only pulled in for gluPerspective here; pure GL otherwise.
#include <GL/glu.h>

namespace
{

class LegacyRendererBackend : public RendererBackend
{
public:
    void SetProjection(float fovDegY, float aspect,
                       float nearZ, float farZ) override
    {
        glMatrixMode(GL_PROJECTION);
        glLoadIdentity();
        gluPerspective(fovDegY, aspect, nearZ, farZ);
        glMatrixMode(GL_MODELVIEW);
        AssertGLOK();
    }

    void SetModelView(const Matrix34& m) override
    {
        glMatrixMode(GL_MODELVIEW);
        LoadGLMatrixFromMatrix34(m);
        AssertGLOK();
    }

    void ResetModelView() override
    {
        glMatrixMode(GL_MODELVIEW);
        glLoadIdentity();
        AssertGLOK();
    }

    void SetAmbient(float r, float g, float b) override
    {
        GLfloat c[4] = { r, g, b, 1.0f };
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, c);
    }

    void SetDirLight(int index,
                     float dirX, float dirY, float dirZ,
                     float r, float g, float b) override
    {
        static const GLenum kIds[3] = { GL_LIGHT0, GL_LIGHT1, GL_LIGHT2 };
        GLfloat pos[4]   = { dirX, dirY, dirZ, 0.0f };   // w=0 → directional
        GLfloat col[4]   = { r, g, b, 1.0f };
        GLfloat black[4] = { 0.0f, 0.0f, 0.0f, 1.0f };
        glLightfv(kIds[index], GL_POSITION, pos);
        glLightfv(kIds[index], GL_AMBIENT,  black);
        glLightfv(kIds[index], GL_DIFFUSE,  col);
        glLightfv(kIds[index], GL_SPECULAR, black);
        AssertGLOK();
    }

    void SetLightingEnabled(bool enabled) override
    {
        if (enabled)
        {
            glEnable(GL_LIGHTING);
            glEnable(GL_LIGHT0);
            glEnable(GL_LIGHT1);
            glEnable(GL_LIGHT2);
        }
        else
        {
            glDisable(GL_LIGHTING);
        }
        AssertGLOK();
    }

    void SetFog(float r, float g, float b,
                float start, float end) override
    {
        GLfloat color[4] = { r, g, b, 1.0f };
        glFogfv(GL_FOG_COLOR, color);
        glFogf(GL_FOG_START, start);
        glFogf(GL_FOG_END, end);
        glFogi(GL_FOG_MODE, GL_LINEAR);
        AssertGLOK();
    }

    void SetFogEnabled(bool enabled) override
    {
        if (enabled) glEnable(GL_FOG);
        else         glDisable(GL_FOG);
        AssertGLOK();
    }

    void EndFrame() override
    {
        // No batching in fixed-function mode; nothing to flush.
    }

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

RendererBackend* LegacyBackendInstance()
{
    return &sLegacyBackend;
}
