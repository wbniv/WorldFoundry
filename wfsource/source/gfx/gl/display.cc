//=============================================================================
// gfx/gl/display.cc: display hardware abstraction class, windows openGL specific code
// Copyright ( c ) 1997,1998,1999,2000,2001,2002 World Foundry Group  
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
// Description: The Display class encapsulates data and behavior for a single
//       hardware screen
// Original Author: Kevin T. Seghetti
//============================================================================

#include <hal/hal.h>
#include <hal/lifecycle.h>
#if defined(WF_ENABLE_STEAM)
#  include <hal/linux/steam.h>
#endif
#if defined(__ANDROID__)
#  include <GLES3/gl3.h>
#else
#  define GL_GLEXT_PROTOTYPES 1
#  include <GL/gl.h>
#  include <GL/glext.h>
#endif

#include <memory/memory.hp>
#include <gfx/pixelmap.hp>
#include <gfx/rendobj3.hp>
#include <gfx/renderer_backend.hp>

#if DESIGNER_CHEATS && defined(__LINUX__)
#define STB_EASY_FONT_IMPLEMENTATION
#include "../../../../engine/vendor/stb_easy_font.h"

extern int wf_hud_score;
extern int wf_hud_timer;
extern int wf_hud_lives;
extern int wf_hud_game_over;
extern int wf_hud_entering_initials;
extern char wf_hud_initials[4];
extern int  wf_hud_initials_pos;
// PILOT T:/TH: text (Phase 4).
extern char wf_hud_pilot[4][128];
extern int  wf_hud_pilot_count;

// Moon Site 01 position-display HUD overlay — see docs/plans/2026-05-31-position-display-hud-overlay-on-the-moon-level-tex.md
extern int   wf_moon_overlay_enabled;
extern float wf_moon_player_x_m;
extern float wf_moon_player_y_m;
extern float wf_moon_player_z_m;
extern float wf_moon_player_heading_rev;

#include "hscore.h"

// Forward declarations for the offscreen capture FBO — definitions live in
// the second DESIGNER_CHEATS block below (with CaptureFrame). RenderBegin
// (much earlier in the file) needs to bind the FBO when bRecordVideo.
extern bool bRecordVideo;
extern GLuint gCaptureFBO;
static void EnsureCaptureFBO(int w, int h);

static void DrawHudText(float x, float y, const char* text)
{
    static char vbuf[65536];
    int num_quads = stb_easy_font_print(x, y, (char*)text, nullptr, vbuf, sizeof(vbuf));
    glEnableClientState(GL_VERTEX_ARRAY);
    glVertexPointer(2, GL_FLOAT, 16, vbuf);
    glDrawArrays(GL_QUADS, 0, num_quads * 4);
    glDisableClientState(GL_VERTEX_ARRAY);
}

// Moon Site 01 minimap. Loads wflevels/moon_site01/minimap.tga from cwd on
// first use; if missing, the minimap silently disables (text overlay still
// renders). Hardcoded relative path is a v1 shortcut; proper cd.iff asset
// wiring is a follow-up.
static GLuint gMoonMinimapTex = 0;
static bool   gMoonMinimapTried = false;
static int    gMoonMinimapW = 0, gMoonMinimapH = 0;

static void LoadMoonMinimapTexture()
{
    gMoonMinimapTried = true;
    FILE* fp = fopen("wflevels/moon_site01/minimap.tga", "rb");
    if (!fp) { fprintf(stderr, "moon overlay: minimap.tga not found, minimap disabled\n"); return; }
    fseek(fp, 0, SEEK_END);
    long fsize = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (fsize < 18) { fclose(fp); fprintf(stderr, "moon overlay: minimap.tga truncated\n"); return; }
    uint8_t* buf = (uint8_t*)malloc(fsize);
    if (fread(buf, 1, fsize, fp) != (size_t)fsize) { free(buf); fclose(fp); return; }
    fclose(fp);

    // Minimal TGA reader: uncompressed truecolor (type 2), 24- or 32-bpp, no colormap.
    uint8_t id_len    = buf[0];
    uint8_t cmap_type = buf[1];
    uint8_t img_type  = buf[2];
    int     width     = buf[12] | (buf[13] << 8);
    int     height    = buf[14] | (buf[15] << 8);
    uint8_t bpp       = buf[16];
    uint8_t desc      = buf[17];
    bool    top_down  = (desc & 0x20) != 0;
    if (cmap_type != 0 || img_type != 2 || (bpp != 24 && bpp != 32)) {
        fprintf(stderr, "moon overlay: minimap.tga unsupported format (type=%d bpp=%d)\n", img_type, bpp);
        free(buf); return;
    }
    int channels = bpp / 8;
    int expected = 18 + id_len + width * height * channels;
    if (expected > fsize) { fprintf(stderr, "moon overlay: minimap.tga payload truncated\n"); free(buf); return; }

    const uint8_t* pix = buf + 18 + id_len;
    // Convert BGR(A) → RGB top-down for GL upload.
    uint8_t* rgb = (uint8_t*)malloc(width * height * 3);
    for (int y = 0; y < height; ++y) {
        int src_y = top_down ? y : (height - 1 - y);
        const uint8_t* src_row = pix + src_y * width * channels;
        uint8_t* dst_row = rgb + y * width * 3;
        for (int x = 0; x < width; ++x) {
            dst_row[x*3 + 0] = src_row[x*channels + 2];   // R
            dst_row[x*3 + 1] = src_row[x*channels + 1];   // G
            dst_row[x*3 + 2] = src_row[x*channels + 0];   // B
        }
    }
    free(buf);

    glGenTextures(1, &gMoonMinimapTex);
    glBindTexture(GL_TEXTURE_2D, gMoonMinimapTex);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, GL_RGB, GL_UNSIGNED_BYTE, rgb);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    free(rgb);
    gMoonMinimapW = width; gMoonMinimapH = height;
    fprintf(stderr, "moon overlay: minimap loaded (%dx%d), tex=%u\n", width, height, gMoonMinimapTex);
}

static void DrawHud(int xSize, int ySize)
{
    // The 3D viewport is square (mesa.cc ConfigureNotify clips top/bottom),
    // so force the HUD to render over the full window surface. This ensures
    // text at small y values (e.g. y=8 for the score bar) is actually visible.
    GLint saved_vp[4];
    glGetIntegerv(GL_VIEWPORT, saved_vp);
    glViewport(0, 0, xSize, ySize);

    glUseProgram(0);   // ensure fixed-function pipeline; Flush() may have left a program bound

    glMatrixMode(GL_PROJECTION);
    glPushMatrix();
    glLoadIdentity();
    glOrtho(0, xSize, ySize, 0, -1, 1);
    glMatrixMode(GL_MODELVIEW);
    glPushMatrix();
    glLoadIdentity();

    glDisable(GL_DEPTH_TEST);
    glDisable(GL_TEXTURE_2D);
    glDisable(GL_LIGHTING);
    glColor3f(1.0f, 1.0f, 0.0f);

    char buf[64];
    const float kScale = 2.0f;

    snprintf(buf, sizeof(buf), "SCORE %d", wf_hud_score);
    glPushMatrix(); glTranslatef(8, 8, 0); glScalef(kScale, kScale, 1);
    DrawHudText(0, 0, buf); glPopMatrix();

    int t = wf_hud_timer > 0 ? wf_hud_timer : 0;
    snprintf(buf, sizeof(buf), "TIME %d", t);
    {
        float tw = (float)stb_easy_font_width((char*)buf) * kScale;
        glPushMatrix(); glTranslatef((float)xSize * 0.5f - tw * 0.5f, 8, 0); glScalef(kScale, kScale, 1);
        DrawHudText(0, 0, buf); glPopMatrix();
    }

    snprintf(buf, sizeof(buf), "LIVES %d", wf_hud_lives);
    {
        float lw = (float)stb_easy_font_width((char*)buf) * kScale;
        glPushMatrix(); glTranslatef((float)xSize - lw - 8, 8, 0); glScalef(kScale, kScale, 1);
        DrawHudText(0, 0, buf); glPopMatrix();
    }

    // ── Moon Site 01 position-display HUD overlay ──────────────────────────
    // Text block (top-left, under SCORE) + minimap inset (top-right).
    // Gated on MOON_OVERLAY_ENABLED (mb 1875) so SMB / qbert stay untouched.
    // See docs/plans/2026-05-31-position-display-hud-overlay-on-the-moon-level-tex.md
    if (wf_moon_overlay_enabled)
    {
        // South polar stereographic linearisation at the play-area centre.
        // PGDA crop centre = PS (-11000, -12000) m, lunar R = 1737.4 km.
        // rho = sqrt(11000^2 + 12000^2) ≈ 16278.8 m → c ≈ 0.009370 rad
        // → lat0 = -90 + c·180/π = -89.4632°. Lon0 from README is 227.0381° E.
        // For a 1 km × 1 km patch the per-metre slopes are constant.
        const double LAT0       = -89.4632;
        const double LON0       =  227.0381;
        const double RAD_PER_M  =  180.0 / (3.14159265358979 * 1737400.0);   // ≈ 3.30e-5 °/m
        // d_lat/dY = RAD_PER_M · (Y_ps/rho); d_lon/dX scales by 1/sin(|lat0|)
        const double D_LAT_PER_M = RAD_PER_M * (12000.0 / 16278.8);          // ≈ +2.43e-5 °/m (Y+ ⇒ less negative lat)
        const double D_LON_PER_M = RAD_PER_M / 0.009378;                     // sin(0.5368°), ≈ +3.52e-3 °/m
        // ELEV: player Z is metres above play-area centre; centre is +1944.77 m above lunar reference radius.
        const double ELEV_BASE_M = 1944.77;

        double lat  = LAT0 + (double)wf_moon_player_y_m * D_LAT_PER_M;
        double lon  = LON0 + (double)wf_moon_player_x_m * D_LON_PER_M;
        double elev = ELEV_BASE_M + (double)wf_moon_player_z_m;

        glColor3f(1.0f, 1.0f, 0.0f);
        const float kTxt = 1.5f;
        char  l[80];
        auto draw_line = [&](float y, const char* s) {
            glPushMatrix(); glTranslatef(8.0f, y, 0.0f); glScalef(kTxt, kTxt, 1.0f);
            DrawHudText(0.0f, 0.0f, (char*)s); glPopMatrix();
        };
        draw_line(36.0f, "SITE 01 -- CONNECTING RIDGE");
        snprintf(l, sizeof(l), "LAT %.4f S  LON %.4f E", -lat, lon);
        draw_line(50.0f, l);
        snprintf(l, sizeof(l), "ELEV %+.0f m  (delta %+.1f m)", elev, (double)wf_moon_player_z_m);
        draw_line(64.0f, l);
        snprintf(l, sizeof(l), "POS X%+.0f  Y%+.0f  (m from spawn)",
                 (double)wf_moon_player_x_m, (double)wf_moon_player_y_m);
        draw_line(78.0f, l);

        // Minimap inset, 128×128 px, top-right corner with 8 px margin.
        const float MM = 128.0f;
        const float mm_x = (float)xSize - 8.0f - MM;
        const float mm_y = 8.0f;

        if (!gMoonMinimapTried) LoadMoonMinimapTexture();
        if (gMoonMinimapTex != 0)
        {
            glEnable(GL_TEXTURE_2D);
            glBindTexture(GL_TEXTURE_2D, gMoonMinimapTex);
            glColor3f(1.0f, 1.0f, 1.0f);
            glBegin(GL_QUADS);
                glTexCoord2f(0, 0); glVertex2f(mm_x,      mm_y);
                glTexCoord2f(1, 0); glVertex2f(mm_x + MM, mm_y);
                glTexCoord2f(1, 1); glVertex2f(mm_x + MM, mm_y + MM);
                glTexCoord2f(0, 1); glVertex2f(mm_x,      mm_y + MM);
            glEnd();
            glDisable(GL_TEXTURE_2D);
        }

        // 1-px white border.
        glColor3f(1.0f, 1.0f, 1.0f);
        glBegin(GL_LINE_LOOP);
            glVertex2f(mm_x,      mm_y);
            glVertex2f(mm_x + MM, mm_y);
            glVertex2f(mm_x + MM, mm_y + MM);
            glVertex2f(mm_x,      mm_y + MM);
        glEnd();

        // Game-world (X, Y) ∈ [-500, +500] m → minimap (sx, sy). v is flipped so
        // world +Y (north-ish) maps to up on the minimap; texture is loaded
        // top-down so this matches the visible image orientation.
        const float HALF_M = 500.0f;
        const float SIDE_M = 1000.0f;
        auto world_to_screen = [&](float wx, float wy, float& sx, float& sy) {
            float u = (wx + HALF_M) / SIDE_M;
            float v = (wy + HALF_M) / SIDE_M;
            sx = mm_x + u * MM;
            sy = mm_y + (1.0f - v) * MM;
        };

        float sx, sy;

        // Spawn square — hollow yellow 4-px outline at world (0, 0).
        glColor3f(1.0f, 1.0f, 0.0f);
        world_to_screen(0.0f, 0.0f, sx, sy);
        glBegin(GL_LINE_LOOP);
            glVertex2f(sx - 2.0f, sy - 2.0f);
            glVertex2f(sx + 2.0f, sy - 2.0f);
            glVertex2f(sx + 2.0f, sy + 2.0f);
            glVertex2f(sx - 2.0f, sy + 2.0f);
        glEnd();

        // Lander X — yellow 6-px cross at world (+30, +25) per blender_create_moon.py.
        world_to_screen(30.0f, 25.0f, sx, sy);
        glBegin(GL_LINES);
            glVertex2f(sx - 3.0f, sy - 3.0f); glVertex2f(sx + 3.0f, sy + 3.0f);
            glVertex2f(sx - 3.0f, sy + 3.0f); glVertex2f(sx + 3.0f, sy - 3.0f);
        glEnd();

        // Player dot — filled 3×3 yellow square at live position.
        world_to_screen(wf_moon_player_x_m, wf_moon_player_y_m, sx, sy);
        glBegin(GL_QUADS);
            glVertex2f(sx - 1.0f, sy - 1.0f);
            glVertex2f(sx + 2.0f, sy - 1.0f);
            glVertex2f(sx + 2.0f, sy + 2.0f);
            glVertex2f(sx - 1.0f, sy + 2.0f);
        glEnd();

        // Compass chevron — cyan triangle pointing in heading direction. WF
        // currentDir = (cos C, sin C, 0); heading_rev is C / (2π) in revolutions.
        // Screen Y is flipped (v=1-y), so world +Y heading → screen up.
        float theta = wf_moon_player_heading_rev * 6.28318530718f;
        float cs    = cosf(theta);
        float sn    = sinf(theta);
        auto rot_pt = [&](float fwd, float side, float& ox, float& oy) {
            ox = sx + fwd * cs + side * sn;
            oy = sy - fwd * sn + side * cs;     // -sn because world Y → screen -Y
        };
        float tx, ty, bxL, byL, bxR, byR;
        rot_pt(6.0f,  0.0f, tx,  ty);
        rot_pt(-1.5f, +2.5f, bxL, byL);
        rot_pt(-1.5f, -2.5f, bxR, byR);
        glColor3f(0.0f, 1.0f, 1.0f);   // cyan
        glBegin(GL_TRIANGLES);
            glVertex2f(tx,  ty);
            glVertex2f(bxL, byL);
            glVertex2f(bxR, byR);
        glEnd();
    }

    // Game-over overlay — driven by mb 420 via wf_hud_game_over (game.cc HUD glue).
    // Two centred lines, scaled up over the live pyramid view; red to match the
    // arcade GAME OVER colour (see docs/plans/screenshots/qbert-arcade-game-over-reference.png).
    if (wf_hud_game_over != 0)
    {
        glColor3f(1.0f, 0.0f, 0.0f);
        const float cx = (float)xSize * 0.5f;
        const float cy = (float)ySize * 0.5f;

        // Line 1: "GAME OVER" — large prominence (3x scale).
        char line1[] = "GAME OVER";
        const float scale1 = 3.0f;
        const float w1 = (float)stb_easy_font_width(line1) * scale1;
        glPushMatrix();
        glTranslatef(cx - w1 * 0.5f, cy - 24.0f * scale1, 0.0f);
        glScalef(scale1, scale1, 1.0f);
        DrawHudText(0.0f, 0.0f, line1);
        glPopMatrix();

        // Line 2: restart prompt — smaller (1.5x), below.
        char line2[] = "PRESS ANY BUTTON TO RESTART";
        const float scale2 = 1.5f;
        const float w2 = (float)stb_easy_font_width(line2) * scale2;
        glPushMatrix();
        glTranslatef(cx - w2 * 0.5f, cy + 12.0f, 0.0f);
        glScalef(scale2, scale2, 1.0f);
        DrawHudText(0.0f, 0.0f, line2);
        glPopMatrix();

        // HIGH SCORES table — matches arcade layout:
        //   Entry #1 centered at top; entries 2-23 in two-column pairs.
        HScore_Load();
        const float tscale = 1.0f;
        const float trow = 9.0f * tscale;

        // Header: "HIGH SCORES" in red, centered just below GAME OVER block.
        glColor3f(1.0f, 0.1f, 0.1f);
        {
            char hdr[] = "HIGH SCORES";
            float hw = (float)stb_easy_font_width(hdr) * tscale;
            glPushMatrix();
            glTranslatef(cx - hw * 0.5f, cy + 28.0f, 0.0f);
            glScalef(tscale, tscale, 1.0f);
            DrawHudText(0.0f, 0.0f, hdr);
            glPopMatrix();
        }

        // Entry #1 — centered, yellow.
        glColor3f(1.0f, 1.0f, 0.0f);
        float ty = cy + 38.0f;
        {
            snprintf(buf, sizeof(buf), "1) %s %d", g_hiscores[0].name, g_hiscores[0].score);
            float w = (float)stb_easy_font_width(buf) * tscale;
            glPushMatrix();
            glTranslatef(cx - w * 0.5f, ty, 0.0f);
            glScalef(tscale, tscale, 1.0f);
            DrawHudText(0.0f, 0.0f, buf);
            glPopMatrix();
        }
        ty += trow;

        // Entries 2-23: two columns.  Left col = even rank, right col = odd rank.
        // Each column is 90px wide, centred on cx +/- 55.
        const float colL = cx - 100.0f;
        const float colR = cx + 10.0f;
        int i = 1;  // already rendered index 0
        while (i < HS_COUNT)
        {
            // Left entry
            snprintf(buf, sizeof(buf), "%2d) %s %d", i + 1,
                     g_hiscores[i].name, g_hiscores[i].score);
            DrawHudText(colL, ty, buf);
            i++;
            // Right entry (may be absent if count is odd)
            if (i < HS_COUNT)
            {
                snprintf(buf, sizeof(buf), "%2d) %s %d", i + 1,
                         g_hiscores[i].name, g_hiscores[i].score);
                DrawHudText(colR, ty, buf);
                i++;
            }
            ty += trow;
        }

        // AAA initials picker — white, centered below the table.
        if (wf_hud_entering_initials)
        {
            glColor3f(1.0f, 1.0f, 1.0f);
            char picker[32];
            // Show current position bracketed: e.g.  [A] B C
            snprintf(picker, sizeof(picker), "%c%c%c  %c%c%c  %c%c%c",
                     wf_hud_initials_pos == 0 ? '[' : ' ', wf_hud_initials[0], wf_hud_initials_pos == 0 ? ']' : ' ',
                     wf_hud_initials_pos == 1 ? '[' : ' ', wf_hud_initials[1], wf_hud_initials_pos == 1 ? ']' : ' ',
                     wf_hud_initials_pos == 2 ? '[' : ' ', wf_hud_initials[2], wf_hud_initials_pos == 2 ? ']' : ' ');
            const float scale2 = 2.0f;
            const float pw = (float)stb_easy_font_width(picker) * scale2;
            glPushMatrix();
            glTranslatef(cx - pw * 0.5f, ty + 4.0f, 0.0f);
            glScalef(scale2, scale2, 1.0f);
            DrawHudText(0.0f, 0.0f, picker);
            glPopMatrix();
        }

        glColor3f(1.0f, 1.0f, 0.0f);  // restore HUD yellow for any later draws
    }

    // PILOT T:/TH: text — cyan, stacked from the bottom of the HUD.
    // Ring of 4 lines; start slot = wf_hud_pilot_count % 4 (oldest visible).
    if (wf_hud_pilot_count > 0) {
        glColor3f(0.0f, 1.0f, 1.0f);
        int nlines = wf_hud_pilot_count < 4 ? wf_hud_pilot_count : 4;
        int start  = wf_hud_pilot_count % 4;   // oldest slot in the ring
        float lh   = 11.0f * kScale;           // line height at kScale
        float y0   = (float)ySize - 8.0f - (float)nlines * lh;
        for (int i = 0; i < nlines; ++i) {
            int slot = (start + i) % 4;
            glPushMatrix();
            glTranslatef(8.0f, y0 + (float)i * lh, 0.0f);
            glScalef(kScale, kScale, 1.0f);
            DrawHudText(0.0f, 0.0f, wf_hud_pilot[slot]);
            glPopMatrix();
        }
        glColor3f(1.0f, 1.0f, 0.0f);   // restore HUD yellow
    }

    glEnable(GL_DEPTH_TEST);
    glMatrixMode(GL_PROJECTION);
    glPopMatrix();
    glMatrixMode(GL_MODELVIEW);
    glPopMatrix();

    glViewport(saved_vp[0], saved_vp[1], saved_vp[2], saved_vp[3]);
}
#endif // DESIGNER_CHEATS && __LINUX__

extern bool bFullScreen;
extern int _halWindowWidth;
extern int _halWindowHeight;

extern RendererVariables globalRendererVariables;

//#       include <gl/glaux.h>
#       include <gfx/gl/wfprim.h>

#include <math.h>

// Keep track of windows changing width and height
GLfloat windowXPos;
GLfloat windowYPos;
GLfloat windowWidth;
GLfloat windowHeight;
int wfWindowWidth = 640;
int wfWindowHeight = 480;


#if defined(__ANDROID__)
#  include "android_window.cc"
#elif defined(__LINUX__)
#  include "mesa.cc"
#endif
#if defined(__LINUX__) || defined(__ANDROID__)
#  include <sys/time.h>
#  include <unistd.h>
#endif
#if DESIGNER_CHEATS && defined(__LINUX__)
#  include <cstdio>
#  include <cstdlib>
#  include <csignal>
#endif

//==============================================================================


//==============================================================================

void
WFInitGL()
{
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    AssertGLOK();

    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    AssertGLOK();

    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    glClearColor(0.0f, 0.0f, 0.0f, 0.0f);
    AssertGLOK();

    RendererBackendGet().ResetModelView();

    glViewport(0, 0, wfWindowWidth, wfWindowHeight);
    AssertGLOK();

    // Aspect from the actual surface so geometry isn't squished when the
    // window isn't square. Keeps content proportions — on a landscape
    // phone the horizontal field of view widens instead of content
    // stretching. (Was hardcoded 1.0 which combined with the 640×480
    // wfWindow defaults rendered the engine into the top-left corner of
    // anything larger.)
    const float fAspect = float(wfWindowWidth) / float(wfWindowHeight);
    RendererBackendGet().SetProjection(60.0f, fAspect, 1.0f, 1000.0f);
}
//==============================================================================

Display::Display(int orderTableSize, int xPos, int yPos, int xSize, int ySize, Memory& memory,bool /*interlace*/) :
_drawPage(0),
#if defined(USE_ORDER_TABLES)
_constructionOrderTableIndex(0),
_renderOrderTableIndex(1),
#endif
_xPos(xPos),
_yPos(yPos),
_xSize(xSize),
_ySize(ySize),
_memory(memory)
{

    _memory.Validate();
    if(!InitWindow(xPos, yPos, _halWindowWidth, _halWindowHeight ))
    {
        printf("Display::Display:doInit Failed!\n");
        sys_exit(1);
    }
    AssertGLOK();

	WFInitGL();

    assert(orderTableSize > 0);
#if defined(USE_ORDER_TABLES)
    for(int index=0;index<ORDER_TABLES;index++)
    {
        _orderTable[index] = new (_memory) OrderTable(orderTableSize,_memory);
        assert(ValidPtr(_orderTable[index]));
    }
#endif

    // set up GL 
   //glLightModelf(GL_LIGHT_MODEL_TWO_SIDE,1);
   //glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE);

    _drawPage = 0;
    ResetTime();


#if defined(VIDEO_MEMORY_IN_ONE_PIXELMAP)
    _videoMemory = new (HALLmalloc) PixelMap( PixelMap::MEMORY_VIDEO, VRAMWidth, VRAMHeight );
    assert( ValidPtr( _videoMemory ) );
#else

// do nothing
#endif
}

//==============================================================================

Display::~Display()
{
    Validate();
    // Skip final PageFlips if the X window was already destroyed by HALCloseWindow().
    if (!HALWindowCloseRequested()) {
        if(_drawPage == 0)
            PageFlip();

        PageFlip();
    }

#if defined(USE_ORDER_TABLES)
    for(int index=ORDER_TABLES-1;index>= 0;index--)
        _memory.Free(_orderTable[index],sizeof(OrderTable));
#endif

#if defined(VIDEO_MEMORY_IN_ONE_PIXELMAP)
    delete _videoMemory;
#else

// do nothing
#endif
}

//============================================================================

#if defined(__LINUX__) || defined(__ANDROID__)
inline Scalar
ConvertTimeToScalar(const struct timeval&  tv)
{
    int16 whole = tv.tv_sec;
    uint16 frac;

    frac = uint16(float(tv.tv_usec)/(15.2587890625));
    assert(tv.tv_sec < USHRT_MAX);
    whole = tv.tv_sec;
    return(Scalar(whole,frac));
}
#endif

//==============================================================================

void
Display::ResetTime()                    // used to reset delta timer for PageFlip
{
    //_clockLastTime = timeGetTime();  	//clock();

#if   defined(__LINUX__) || defined(__ANDROID__)
    struct timeval tv;
    gettimeofday(&tv,NULL);
    _clockLastTime = tv;                
#else
#error platform not supported
#endif
}

//============================================================================

void
Display::RenderBegin()
{
   Validate();
   AssertGLOK();
   AssertMsg( _drawPage == 0 || _drawPage == 1, "_drawPage = " << _drawPage );
#if DESIGNER_CHEATS && defined(__LINUX__)
   if (bRecordVideo)
   {
       EnsureCaptureFBO(_xSize, _ySize);
       glBindFramebuffer(GL_FRAMEBUFFER, gCaptureFBO);
   }
#endif
   glClearColor( _backgroundColorRed, _backgroundColorGreen, _backgroundColorBlue, 1.0 );
   AssertGLOK();
   glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);     // Clear the window with current clearing color
   AssertGLOK();
   RendererBackendGet().SetLightingEnabled(true);
   // Fog enable/disable is driven by camera.cc's SetFog each frame.

#if 0
   static GLfloat cameraZ = -5.0;
   static GLfloat zOffset = 0;
   //cameraZ += 0.1;
   //zOffset += 0.1;
   //cout << "cz: " << cameraZ << ", zo:" << zOffset << endl;

   glMatrixMode (GL_MODELVIEW);
   glLoadIdentity();
   //glTranslatef(0.0,0.0,cameraZ);

    glDisable(GL_BLEND);
    glDisable(GL_POLYGON_SMOOTH);

   GLfloat mat_specular[] = { 1.0, 1.0, 1.0, 1.0 };
   GLfloat mat_shininess[] = { 50.0 };
   GLfloat light_position[] = { 1.0,1.0,1.0,1.0 };
   GLfloat white_light[] = { 1.0,1.0,1.0,1.0 };
   GLfloat mat_ambient_color[] = { 0.8,0.8,0.2,1.0 };
   GLfloat mat_diffuse[] = { 0.1,0.5, 0.8, 1.0 };
   glClearColor(0.0,0.0,0.0,0.0);
   glShadeModel(GL_SMOOTH);
   glMaterialfv(GL_FRONT, GL_DIFFUSE, mat_diffuse);
   glMaterialfv(GL_FRONT, GL_SPECULAR, mat_specular);
   glMaterialfv(GL_FRONT, GL_SHININESS, mat_shininess);
   glLightfv(GL_LIGHT0, GL_POSITION, light_position);
   glLightfv(GL_LIGHT0, GL_DIFFUSE, white_light);
   glLightfv(GL_LIGHT0, GL_SPECULAR, white_light);
   glEnable(GL_LIGHTING);
   glEnable(GL_LIGHT0);
   glEnable(GL_DEPTH_TEST);

    glBegin(GL_TRIANGLES);
    glColor3f(1.0, 1.0, 1.0);
    glVertex3f( 0.9, -0.9, -10.0 + zOffset);
    glVertex3f( 0.9,  0.9, -10.0 + zOffset);
    glVertex3f(-0.9,  0.0, -10.0 + zOffset);
    glColor3f(0.0, 1.0, 0.0);
    glVertex3f(-0.9, -0.9, -20.0 + zOffset);
    glVertex3f(-0.9,  0.9, -20.0 + zOffset);
    glVertex3f( 0.9,  0.0, -5.0 + zOffset);
    glEnd();
#endif
    RendererBackendGet().ResetModelView();
}

//==============================================================================

void
Display::RenderEnd()
{
}

//==============================================================================

extern bool	windowActive;		// Window windowActive Flag Set To TRUE By Default

#if DESIGNER_CHEATS && defined(__LINUX__)

extern bool bRecordVideo;

static FILE* gCapturePipe  = nullptr;
// Offscreen capture target — see docs/plans/2026-05-11-record-video-fbo-capture.md.
// Rendering goes here when bRecordVideo is set, so the captured frame is
// immune to X11 window occlusion (the back buffer's occluded regions on
// non-composited X11 contain whatever the obscuring window painted).
// File-scope (not static) so the forward decl at the top of the file can
// refer to them.
GLuint gCaptureFBO   = 0;
static GLuint gCaptureColor = 0;
static GLuint gCaptureDepth = 0;

static void
CaptureCleanup(int sig)
{
    if (gCapturePipe)
    {
        pclose(gCapturePipe);
        gCapturePipe = nullptr;
    }
    signal(sig, SIG_DFL);
    raise(sig);
}

static void
EnsureCaptureFBO(int w, int h)
{
    if (gCaptureFBO) return;
    glGenFramebuffers(1, &gCaptureFBO);
    glGenRenderbuffers(1, &gCaptureColor);
    glGenRenderbuffers(1, &gCaptureDepth);

    glBindRenderbuffer(GL_RENDERBUFFER, gCaptureColor);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_RGB8, w, h);

    glBindRenderbuffer(GL_RENDERBUFFER, gCaptureDepth);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, w, h);

    glBindFramebuffer(GL_FRAMEBUFFER, gCaptureFBO);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                              GL_RENDERBUFFER, gCaptureColor);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                              GL_RENDERBUFFER, gCaptureDepth);
    GLenum status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
    AssertMsg(status == GL_FRAMEBUFFER_COMPLETE,
              "capture FBO incomplete: 0x" << std::hex << status);
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
}

static void
CaptureFrame(int xSize, int ySize)
{
    if (!gCapturePipe)
    {
        char cmd[256];
        snprintf(cmd, sizeof(cmd),
            "ffmpeg -y -f rawvideo -pixel_format bgr24 "
            "-video_size %dx%d -framerate 30 "
            "-i pipe:0 -vf vflip -c:v libx264 -pix_fmt yuv420p "
            "-movflags frag_keyframe+empty_moov output.mp4",
            xSize, ySize);
        gCapturePipe = popen(cmd, "w");
        signal(SIGABRT, CaptureCleanup);
        signal(SIGSEGV, CaptureCleanup);
        signal(SIGTERM, CaptureCleanup);
        signal(SIGINT,  CaptureCleanup);
    }
    if (!gCapturePipe)
        return;

    const int pixelBytes = xSize * ySize * 3;
    glFinish();

    // When rendering to the offscreen capture FBO, blit it onto the back
    // buffer (so the user still sees the game) and then read from the FBO
    // (still bound as READ) so the captured pixels are immune to X11
    // window occlusion.
    if (gCaptureFBO)
    {
        glBindFramebuffer(GL_READ_FRAMEBUFFER, gCaptureFBO);
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0);
        glBlitFramebuffer(0, 0, xSize, ySize, 0, 0, xSize, ySize,
                          GL_COLOR_BUFFER_BIT, GL_NEAREST);
        // FBO remains bound as the READ framebuffer for glReadPixels below.
    }

    uint8_t* pixels = (uint8_t*)malloc(pixelBytes);
    glReadPixels(0, 0, xSize, ySize, GL_BGR, GL_UNSIGNED_BYTE, pixels);
    fwrite(pixels, 1, pixelBytes, gCapturePipe);

    // Optional one-shot PPM dump (env WF_GAME_SCREENSHOT_PPM=path). The
    // ffmpeg pipe occasionally buffers indefinitely under fragmented mp4 +
    // SIGTERM, leaving a 36-byte header file — PPM bypasses libx264 and
    // mp4 entirely. Wait a few frames so the first textured frame is
    // ready (the FBO blits are immediate, but the level-load cascade can
    // present a partial frame on frame 0).
    static int  gPpmFrame    = 0;
    static bool gPpmDone     = false;
    if (!gPpmDone)
    {
        const char* ppm_path = getenv("WF_GAME_SCREENSHOT_PPM");
        if (ppm_path && ++gPpmFrame >= 30)
        {
            FILE* fp = fopen(ppm_path, "wb");
            if (fp)
            {
                fprintf(fp, "P6\n%d %d\n255\n", xSize, ySize);
                // glReadPixels gives BGR bottom-up; PPM wants RGB top-down.
                uint8_t* row = (uint8_t*)malloc(xSize * 3);
                for (int y = ySize - 1; y >= 0; --y)
                {
                    const uint8_t* src = pixels + y * xSize * 3;
                    for (int x = 0; x < xSize; ++x)
                    {
                        row[x*3+0] = src[x*3+2];   // R = B-channel
                        row[x*3+1] = src[x*3+1];   // G
                        row[x*3+2] = src[x*3+0];   // B = R-channel
                    }
                    fwrite(row, 1, xSize * 3, fp);
                }
                free(row);
                fclose(fp);
                gPpmDone = true;
                std::fprintf(stderr, "wf_game: wrote screenshot %s (%dx%d)\n",
                             ppm_path, xSize, ySize);
            }
        }
    }

    free(pixels);

    if (gCaptureFBO)
        glBindFramebuffer(GL_FRAMEBUFFER, 0);
}

#endif // DESIGNER_CHEATS && __LINUX__

Scalar
Display::PageFlip()
{
#if 0

    // event_loop( dpy );
    XEvent event;

    while(XCheckMaskEvent(dpy, 0xffffffff,&event))
    {
   //while (1) {
      //XNextEvent( dpy, &event );

        switch(event.type)
        {
            case Expose:
                redraw( dpy, event.xany.window );
                break;
            case ConfigureNotify:
                resize( event.xconfigure.width, event.xconfigure.height );
                break;
        }
    }
#endif

#if defined(__LINUX__) || defined(__ANDROID__)
    XEventLoop();
#endif
#if defined(WF_ENABLE_STEAM)
    _SteamRunCallbacks();
#endif

    Validate();

//FntPrint("\nWorld Foundry Display: page %d\n",_drawPage);
#if 0
        // kts test code
    glColor3f( 1.0, 0.0, 1.0 );
    AssertGLOK();
    glBegin( GL_TRIANGLES );
    glVertex3f(  100.0,  100.0,  -5.0);
    glVertex3f( -100.0,  100.0,  -5.0);
    glVertex3f( -100.0, -100.0,  -5.0);
    glEnd();
    AssertGLOK();

          //glDisable( GL_TEXTURE_2D );

    glBegin( GL_TRIANGLES );
          //glColor3f( 1.0, 1.0, 0.0 );
    glColor3ub( 200, 200, 200 );

    glVertex2i( 200, 200 );
    glVertex2i( 0, 200 );
    glVertex2i( 0, -200 );
    glEnd();
    AssertGLOK();
        // end test code
#endif


#if 0
    static float xRot;
    xRot += 1.0f;
    static float yRot;
    yRot += 1.0f;
    glPushMatrix();
    AssertGLOK();
    glRotatef(xRot,1.0f,0.0f,0.0f);
    AssertGLOK();
    glRotatef(yRot,0.0f,1.0f,0.0f);
    AssertGLOK();

    GLfloat x,y,z,angle;
    glClearColor(0.0f, 0.0f,0.0f,1.0f);
    AssertGLOK();
    glColor3f(0.0f,1.0f,0.0f);
    AssertGLOK();

    glClear(GL_COLOR_BUFFER_BIT);
    AssertGLOK();
    glDisable( GL_TEXTURE_2D );
    AssertGLOK();
    glBegin(GL_TRIANGLES);

    glColor3ub( 128, 128, 0 );
    z = -50.0f;
    for(angle=0.0f; angle <= (2.0f*3.1415)*3.0f; angle += 0.1f)
    {
        x = 50.0f*sin(angle);
        y = 50.0f*cos(angle);
        glVertex3f(0.0f+200.0f,0.0f,0.0f);
        glVertex3f(x+200.0f,y,z);
        x = 50.0f*sin(angle+10.0);
        y = 50.0f*cos(angle+10.0);
        glVertex3f(x+200.0f,y,z);
        z += 0.5f;
    }
    glEnd();
    AssertGLOK();
    glPopMatrix();

#endif // 0


    RendererBackendGet().EndFrame();

#if DESIGNER_CHEATS && defined(__LINUX__)
    // Skip the arcade HUD on levels that don't write the score/timer/lives/
    // game-over mailboxes (game.cc:558-561 refreshes these globals each
    // frame from mb 70/71/72/420). qbert and SMB write LIVES=3 from their
    // Forth startup script so the HUD appears immediately; snowgoons /
    // mm_practice / moon_site01 never touch the mailboxes and stay HUD-less.
    // See docs/plans/2026-05-31-hud-gate-on-level-opt-in.md.
    if (wf_hud_score | wf_hud_timer | wf_hud_lives | wf_hud_game_over
        | wf_hud_entering_initials | wf_moon_overlay_enabled)
    {
        // Use the actual render-target size so HUD coords match the FBO
        // (record_video captures _xSize/_ySize, not wfWindow*). On normal
        // interactive play these are the same; in headless capture they drift.
        DrawHud(_xSize, _ySize);
    }
#endif

    glFlush();
    AssertGLOK();

#if DESIGNER_CHEATS && defined(__LINUX__)
    if (bRecordVideo)
        CaptureFrame(_xSize, _ySize);
#endif

#if defined(__ANDROID__)
    AndroidSwapBuffers();
    AssertGLOK();
#elif defined(__LINUX__)
    glXSwapBuffers(halDisplay.mainDisplay, halDisplay.win);
    AssertGLOK();
         // glFinish();
#else
#error platform not defined
#endif


//	if(!wglMakeCurrent(hardwaredevicecontext,NULL))
//	{
//		assert(0);
//	}
//	wglDeleteContext(hRC);
//	hRC = 0;

    return MeasureDelta();

}

//============================================================================

Scalar
Display::MeasureDelta()
{
#if defined(__LINUX__) || defined(__ANDROID__)
    struct timeval tv;
    gettimeofday(&tv,NULL);

    struct timeval deltatime;
    deltatime.tv_usec = tv.tv_usec - _clockLastTime.tv_usec;
    deltatime.tv_sec = tv.tv_sec - _clockLastTime.tv_sec;
    // Game mode: a ≥5 s frame gap genuinely is catastrophic (the world would
    // jump huge amounts while the player stared at a frozen screen), so keep
    // the loud assert. Editor mode: stalls are routine (ASan, Doc-apply, the
    // remote-SYNC apply hot path, debugging breakpoints) — warn and clamp like
    // the > 0.2 s case below, so the editor survives stalls of any length.
    extern bool gEditorMode;   // game/main.cc — set true under --editor
    if (!gEditorMode) {
        assert(deltatime.tv_sec < 5);
    } else if (deltatime.tv_sec >= 5) {
        std::cout << "editor: large frame stall (" << deltatime.tv_sec
                  << " s), clamping" << std::endl;
        deltatime.tv_sec  = 4;
        deltatime.tv_usec = 999999;
    }
    int tempCounter = 0;
    while(deltatime.tv_usec < 0)
    {
        deltatime.tv_usec += 1000000;
        deltatime.tv_sec--;
        tempCounter++;
    }

    assert(tempCounter < 5);

    Scalar delta = ConvertTimeToScalar(deltatime);


    if(delta > SCALAR_CONSTANT(1.0/5.0))            // if delta less than 1/5 of a second, prop it up
    {
        std::cout << "delta too large: " << delta << std::endl;
        std::cout << "timeofday:" << tv.tv_sec << ":" << tv.tv_usec << std::endl;
        std::cout << "lasttimeofday: " << _clockLastTime.tv_sec << ":" << _clockLastTime.tv_usec << std::endl;
        std::cout << "deltatime:" << deltatime.tv_sec << ":" << deltatime.tv_usec << std::endl;
        std::cout << "delta: " << delta << std::endl;
        delta = SCALAR_CONSTANT(1.0/5.0);
    }

    // don't allow framerate to exceed 1200 fps ;-)
    if(delta < Scalar(SCALAR_CONSTANT(1.0/1200)))
    {
        delta = Scalar(SCALAR_CONSTANT(1.0/1200));
    }

    _clockLastTime = tv;
    return(delta);
#else
#error platform not defined
#endif
}

//============================================================================

#if defined(USE_ORDER_TABLES)

inline void
SetTexture(const PixelMap& texturePixelMap)
{
#if defined(VIDEO_MEMORY_IN_ONE_PIXELMAP)
#else
    texturePixelMap.SetGLTexture();
#endif
}

void 
CalcAndSetUV(unsigned short tpage, unsigned char uin, unsigned char vin, const PixelMap& texturePixelMap) 
{
    ulong u(uin+DecodeTPageX(tpage)); 
    ulong v(vin+DecodeTPageY(tpage)); 

#if defined(VIDEO_MEMORY_IN_ONE_PIXELMAP)
    float uResult(float(u)/VRAM_WIDTHF);                            
    float vResult(float(v)/VRAM_HEIGHTF);                           

    // kts temp test code
    //texturePixelMap.SetGLTexture();
#else
    float uResult(float(u)/texturePixelMap.GetBaseXSize());                            
    float vResult(float(v)/texturePixelMap.GetBaseYSize());
#endif
    glTexCoord2f(uResult, vResult);                         
}


//==============================================================================

inline void
GL_3D_VERTEX(const Point3D& point)                                                                         
{                                                                                              
    float fx = float(point.x) / 65536.0;                                                         
    float fy = float(point.y) / 65536.0;                                                         
    float fz = float(point.z) / 65536.0;
    //cout.setf(ios::fixed,ios::basefield);
    //cout << "x:" << x << ", y:" << y << ", wx:" << wx << ", wy:" << wy << ", px:" << float(point.x)/65536.0 << ", py:" << float(point.y)/65536.0 << ", pz:" << point.z << ", fz:" << fz << endl; 
    glVertex4f(fx,-fy,1.0,fz);
}

//==============================================================================

void
DrawOTag( ORDER_TABLE_ENTRY* __orderTable )
{
    Primitive* _orderTable = (Primitive*)__orderTable;

    assert( _orderTable );
    Primitive* _orderTableEnd = _orderTable;

    assert( CODE_NOP == 0 );

    // kts temp
//   glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
//	glClear( GL_COLOR_BUFFER_BIT );

    //glVertex2f( (float)x, (float)-y );

// #define checkImageWidth 64
// #define checkImageHeight 64
// extern GLubyte checkImage[checkImageHeight][checkImageWidth][4];


    for(; !isendprim( _orderTable ); _orderTable = (Primitive*)nextPrim( _orderTable ))
    {
        ValidatePtr(_orderTable);
        Primitive* pTag = _orderTable;
        uint8 code = pTag->base.code;
#if 0
        std::cout << "otable code = " << int(_orderTable->code) << std::endl;
        std::cout << "code = " << int(code) << std::endl;
#endif
        //cout << "new poly:" << endl;
        if(code)
        {
            switch(code)
            {
                case CODE_POLY_F3:
                    {
                        glDisable( GL_TEXTURE_2D );
                        AssertGLOK();
                        glBegin( GL_TRIANGLES );
//					assert(0);
                        POLY_F3& pPoly = _orderTable->f3;

                        glColor3ub( pPoly.r0, pPoly.g0, pPoly.b0 );
                    //glColor3ub( rand() % 255, rand() % 255, rand() % 255 );
#if defined(GFX_ZBUFFER)
                        GL_3D_VERTEX(pPoly.point0);
                        GL_3D_VERTEX(pPoly.point1);
                        GL_3D_VERTEX(pPoly.point2);
#else /* defined(GFX_ZBUFFER) */
                        glVertex2i( pPoly.x0, -pPoly.y0 );
                        glVertex2i( pPoly.x1, -pPoly.y1 );
                        glVertex2i( pPoly.x2, -pPoly.y2 );
#endif /* defined(GFX_ZBUFFER) */
                        glEnd();
                        AssertGLOK();
                        glEnable( GL_TEXTURE_2D );
                        AssertGLOK();
                        break;
                    }

                case CODE_POLY_FT3:
                    {
//					assert(0);
                        POLY_FT3& pPoly = _orderTable->ft3;
                        assert(pPoly.pPixelMap);
                        SetTexture(*pPoly.pPixelMap);
                        glBegin( GL_TRIANGLES );

                    //glColor3ub( rand() % 255, rand() % 255, rand() % 255 );
                    //assert( theTexture );
                    //glCallList( theTexture );
                        glColor3ub( 255, 0, 0 );
                        assert(pPoly.pPixelMap);
#if defined( GFX_ZBUFFER )
                        CalcAndSetUV(pPoly.tpage, pPoly.u0,pPoly.v0,*pPoly.pPixelMap);
                        GL_3D_VERTEX(pPoly.point0);
                        CalcAndSetUV(pPoly.tpage, pPoly.u1,pPoly.v1,*pPoly.pPixelMap);
                        GL_3D_VERTEX(pPoly.point1);
                        CalcAndSetUV(pPoly.tpage, pPoly.u2,pPoly.v2,*pPoly.pPixelMap);
                        GL_3D_VERTEX(pPoly.point2);
#else /* GFX_ZBUFFER */
                        CalcAndSetUV(pPoly.tpage, pPoly.u0,pPoly.v0,*pPoly.pPixelMap);
                        glVertex2i( pPoly.x0, -pPoly.y0 );
                        CalcAndSetUV(pPoly.tpage, pPoly.u1,pPoly.v1,*pPoly.pPixelMap);
                        glVertex2i( pPoly.x1, -pPoly.y1 );
                        CalcAndSetUV(pPoly.tpage, pPoly.u2,pPoly.v2,*pPoly.pPixelMap);
                        glVertex2i( pPoly.x2, -pPoly.y2 );
#endif /* GFX_ZBUFFER */
                        glEnd();
                        AssertGLOK();
                        break;
                    }

                case CODE_POLY_G3:
                    {
                        glDisable( GL_TEXTURE_2D );
                        AssertGLOK();
                        glBegin( GL_TRIANGLES );
                        POLY_G3& pPoly = _orderTable->g3;

#if defined ( GFX_ZBUFFER )
//					glVertex2i( pPoly.x0, - (pPoly.y0) );
                        glColor3f( float(pPoly.r0)/128, float(pPoly.g0)/128, float(pPoly.b0)/128 );
                        GL_3D_VERTEX(pPoly.point0);
                        glColor3f( float(pPoly.r1)/128, float(pPoly.g1)/128, float(pPoly.b1)/128 );
                        GL_3D_VERTEX(pPoly.point1);
                        glColor3f( float(pPoly.r2)/128, float(pPoly.g2)/128, float(pPoly.b2)/128 );
                        GL_3D_VERTEX(pPoly.point2);
#else /* GFX_ZBUFFER */
                        glColor3f( float(pPoly.r0)/128, float(pPoly.g0)/128, float(pPoly.b0)/128 );
                        glVertex2i( pPoly.x0, -pPoly.y0 );
                        glColor3f( float(pPoly.r1)/128, float(pPoly.g1)/128, float(pPoly.b1)/128 );
                        glVertex2i( pPoly.x1, -pPoly.y1 );
                        glColor3f( float(pPoly.r2)/128, float(pPoly.g2)/128, float(pPoly.b2)/128 );
                        glVertex2i( pPoly.x2, -pPoly.y2 );
#endif /* GFX_ZBUFFER */
                        glEnd();
                        AssertGLOK();
                        glEnable( GL_TEXTURE_2D );
                        AssertGLOK();
                        break;
                    }

                case CODE_POLY_GT3:
                    {
                        POLY_GT3& pPoly = _orderTable->gt3;
                        assert(pPoly.pPixelMap);
                        SetTexture(*pPoly.pPixelMap);
                        glBegin( GL_TRIANGLES );
                        CalcAndSetUV(pPoly.tpage, pPoly.u0,pPoly.v0,*pPoly.pPixelMap);
#if defined ( GFX_ZBUFFER )
                        glColor3f( float(pPoly.r0)/128, float(pPoly.g0)/128, float(pPoly.b0)/128 );
                        GL_3D_VERTEX(pPoly.point0);
                        CalcAndSetUV(pPoly.tpage, pPoly.u1,pPoly.v1,*pPoly.pPixelMap);
                        glColor3f( float(pPoly.r1)/128, float(pPoly.g1)/128, float(pPoly.b1)/128 );
                        GL_3D_VERTEX(pPoly.point1);
                        CalcAndSetUV(pPoly.tpage, pPoly.u2,pPoly.v2,*pPoly.pPixelMap);
                        glColor3f( float(pPoly.r2)/128, float(pPoly.g2)/128, float(pPoly.b2)/128 );
                        GL_3D_VERTEX(pPoly.point2);
#else /* GFX_ZBUFFER */
                        glColor3f( float(pPoly.r0)/128, float(pPoly.g0)/128, float(pPoly.b0)/128 );
                        glVertex2i( pPoly.x0, -pPoly.y0 );
                        CalcAndSetUV(pPoly.tpage, pPoly.u1,pPoly.v1,*pPoly.pPixelMap);
                        glColor3f( float(pPoly.r1)/128, float(pPoly.g1)/128, float(pPoly.b1)/128 );
                        glVertex2i( pPoly.x1, -pPoly.y1 );
                        CalcAndSetUV(pPoly.tpage, pPoly.u2,pPoly.v2,*pPoly.pPixelMap);
                        glColor3f( float(pPoly.r2)/128, float(pPoly.g2)/128, float(pPoly.b2)/128 );
                        glVertex2i( pPoly.x2, -pPoly.y2 );
#endif /* GFX_ZBUFFER */
                        glEnd();
                        AssertGLOK();
                        break;
                    }

                case CODE_SPRT_16:
                    {
                        glDisable( GL_TEXTURE_2D );
                        AssertGLOK();
                        glBegin( GL_TRIANGLES );
                        SPRT_16& pPoly = _orderTable->sp16;

//					float u0 = pPoly.u0;
//					float v0 = pPoly.v0;
//					u0 /= VRAM_WIDTHF;
//					v0 /= VRAM_HEIGHTF;
//					glTexCoord2f( u0, v0 );
                        glColor3f( float(pPoly.r0)/128, float(pPoly.g0)/128, float(pPoly.b0)/128 );
#if defined( GFX_ZBUFFER )
// nlin: uh, what does this do?	need to change to use 3d coords for persp. correction				glVertex2i( pPoly.x0, - (pPoly.y0) );
#else /* GFX_ZBUFFER */
                        glVertex2i( pPoly.x0, -pPoly.y0 );
#endif /* GFX_ZBUFFER */

//					float u1 = pPoly.u0 + 16;
//					float v1 = pPoly.v0 + 16;
//					u1 /= VRAM_WIDTHF;
//					v1 /= VRAM_HEIGHTF;
//					glTexCoord2f( u1, v1 );
                        glColor3f( float(pPoly.r0)/128, float(pPoly.g0)/128, float(pPoly.b0)/128 );
#if defined ( GFX_ZBUFFER )

// nlin: uh, what does this do?need to change to use 3d coords for persp. correction					glVertex2i( pPoly.x0 + 16, - (pPoly.y0 + 16) );
#else /* GFX_ZBUFFER */
                        glVertex2i( pPoly.x0 + 16,  -pPoly.y0 + 16 );
#endif /* GFX_ZBUFFER */
                        glEnd();
                        AssertGLOK();
                        glEnable( GL_TEXTURE_2D );
                        AssertGLOK();
                        break;
                    }

                default:
                    {
                        DBSTREAM1( std::cout << "code = " << int( code ) << std::endl; )
                        break;
                    }
            }
        }
    }
    AssertGLOK();
    glDisable(GL_TEXTURE_2D);
    AssertGLOK();
}

//==============================================================================

#endif									// defined(USE_ORDER_TABLES)


//==============================================================================

