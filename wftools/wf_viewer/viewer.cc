// wf_viewer/viewer.cc — Standalone World Foundry MODL .iff viewer
//
// Usage: wf_viewer file1.iff [file2.iff ...]
//
// Reads one or more WF MODL binary IFF files and renders all meshes in a
// GLX window.  No WF engine code is used — the binary format is parsed
// directly (VRTX/MATL/FACE chunks).
//
// Controls:
//   Left mouse drag  — orbit (tumble)
//   Scroll wheel     — zoom
//   Q / Escape       — quit
//   R                — reset view

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <vector>
#include <string>
#include <fstream>

#include <GL/gl.h>
#include <GL/glx.h>
#include <X11/Xlib.h>
#include <X11/keysym.h>

// ---------------------------------------------------------------------------
// IFF / MODL format definitions
// ---------------------------------------------------------------------------

struct ChunkHeader {
    char   tag[4];
    uint32_t size;   // little-endian, payload only (NOT including header or pad)
};

// VRTX entry: u, v, color, x, y, z — all int32, fixed-point ×65536
struct WFVertex {
    int32_t u, v;
    uint32_t color;
    int32_t x, y, z;
};

// MATL entry: flags, color, tex[256]
struct WFMaterial {
    int32_t  flags;
    uint32_t color;
    char     tex[256];
};

// FACE entry
struct WFFace {
    int16_t v1, v2, v3, mat_idx;
};

static const float INV = 1.0f / 65536.0f;

// ---------------------------------------------------------------------------
// Per-mesh geometry stored after parse
// ---------------------------------------------------------------------------

struct Mesh {
    std::string name;
    std::vector<WFVertex>   verts;
    std::vector<WFMaterial> mats;
    std::vector<WFFace>     faces;
};

// ---------------------------------------------------------------------------
// IFF parser helpers
// ---------------------------------------------------------------------------

static uint32_t read_le32(const uint8_t* p) {
    return (uint32_t)p[0] | ((uint32_t)p[1]<<8) | ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}
static int32_t read_lei32(const uint8_t* p) { return (int32_t)read_le32(p); }
static uint32_t read_le32u(const uint8_t* p) { return read_le32(p); }
static int16_t read_lei16(const uint8_t* p) {
    uint16_t v = (uint16_t)p[0] | ((uint16_t)p[1]<<8);
    return (int16_t)v;
}

static bool load_modl(const char* path, Mesh& mesh) {
    std::ifstream f(path, std::ios::binary);
    if (!f) { fprintf(stderr, "Cannot open %s\n", path); return false; }
    f.seekg(0, std::ios::end);
    size_t fsz = f.tellg();
    f.seekg(0);
    std::vector<uint8_t> data(fsz);
    f.read((char*)data.data(), fsz);
    if (!f) { fprintf(stderr, "Read error on %s\n", path); return false; }

    if (fsz < 8) { fprintf(stderr, "%s too small\n", path); return false; }

    // Root chunk: tag='MODL', then LE size
    if (memcmp(data.data(), "MODL", 4) != 0) {
        fprintf(stderr, "%s: not a MODL file (got %.4s)\n", path, (char*)data.data());
        return false;
    }
    uint32_t modl_size = read_le32(data.data() + 4);
    if (modl_size + 8 > fsz) modl_size = (uint32_t)(fsz - 8);

    // Scan sub-chunks inside MODL
    size_t off = 8;
    size_t end = 8 + modl_size;
    while (off + 8 <= end) {
        char tag[5] = {};
        memcpy(tag, data.data() + off, 4);
        uint32_t size = read_le32(data.data() + off + 4);
        uint32_t aligned = size + ((4 - size % 4) % 4);

        const uint8_t* payload = data.data() + off + 8;

        if (memcmp(tag, "VRTX", 4) == 0) {
            size_t n = size / sizeof(WFVertex);
            mesh.verts.resize(n);
            for (size_t i = 0; i < n; ++i) {
                const uint8_t* p = payload + i * 24;
                mesh.verts[i].u     = read_lei32(p);
                mesh.verts[i].v     = read_lei32(p+4);
                mesh.verts[i].color = read_le32u(p+8);
                mesh.verts[i].x     = read_lei32(p+12);
                mesh.verts[i].y     = read_lei32(p+16);
                mesh.verts[i].z     = read_lei32(p+20);
            }
        } else if (memcmp(tag, "MATL", 4) == 0) {
            size_t n = size / 264;
            mesh.mats.resize(n);
            for (size_t i = 0; i < n; ++i) {
                const uint8_t* p = payload + i * 264;
                mesh.mats[i].flags = read_lei32(p);
                mesh.mats[i].color = read_le32u(p+4);
                memcpy(mesh.mats[i].tex, p+8, 256);
                mesh.mats[i].tex[255] = '\0';
            }
        } else if (memcmp(tag, "FACE", 4) == 0) {
            size_t n = size / 8;
            mesh.faces.resize(n);
            for (size_t i = 0; i < n; ++i) {
                const uint8_t* p = payload + i * 8;
                mesh.faces[i].v1      = read_lei16(p);
                mesh.faces[i].v2      = read_lei16(p+2);
                mesh.faces[i].v3      = read_lei16(p+4);
                mesh.faces[i].mat_idx = read_lei16(p+6);
            }
        } else if (memcmp(tag, "NAME", 4) == 0) {
            mesh.name.assign((const char*)payload, size);
            // strip null terminator if present
            while (!mesh.name.empty() && mesh.name.back() == '\0')
                mesh.name.pop_back();
        }

        if (aligned == 0) break;
        off += 8 + aligned;
    }

    fprintf(stderr, "Loaded %s: %zu verts, %zu faces, %zu mats\n",
            path, mesh.verts.size(), mesh.faces.size(), mesh.mats.size());
    fflush(stderr);
    return !mesh.verts.empty() && !mesh.faces.empty();
}

// ---------------------------------------------------------------------------
// Matrix helpers (replaces gluPerspective / gluLookAt)
// ---------------------------------------------------------------------------

static void mat_perspective(double fovy_deg, double aspect, double znear, double zfar) {
    double f = 1.0 / tan(fovy_deg * M_PI / 360.0);
    double d = znear - zfar;
    GLdouble m[16] = {
        f/aspect, 0,  0,                          0,
        0,        f,  0,                          0,
        0,        0,  (zfar+znear)/d,            -1,
        0,        0,  (2.0*zfar*znear)/d,         0
    };
    glMultMatrixd(m);
}

static void mat_look_at(float ex, float ey, float ez,
                        float cx, float cy, float cz,
                        float ux, float uy, float uz) {
    // forward = normalize(eye - center)
    float fx=ex-cx, fy=ey-cy, fz=ez-cz;
    float fl = sqrtf(fx*fx+fy*fy+fz*fz);
    fx/=fl; fy/=fl; fz/=fl;
    // right = normalize(up × forward)
    float rx=uy*fz-uz*fy, ry=uz*fx-ux*fz, rz=ux*fy-uy*fx;
    float rl=sqrtf(rx*rx+ry*ry+rz*rz);
    rx/=rl; ry/=rl; rz/=rl;
    // new up = forward × right
    float vx=fy*rz-fz*ry, vy=fz*rx-fx*rz, vz=fx*ry-fy*rx;
    GLfloat m[16] = {
         rx,  vx,  fx, 0,
         ry,  vy,  fy, 0,
         rz,  vz,  fz, 0,
          0,   0,   0, 1
    };
    glMultMatrixf(m);
    glTranslatef(-ex, -ey, -ez);
}

// ---------------------------------------------------------------------------
// Bounding-box helper (for auto-fit camera)
// ---------------------------------------------------------------------------

static void mesh_bounds(const std::vector<Mesh>& meshes,
                         float& cx, float& cy, float& cz, float& radius) {
    float mn[3] = {1e30f, 1e30f, 1e30f};
    float mx[3] = {-1e30f, -1e30f, -1e30f};
    for (const auto& m : meshes) {
        for (const auto& v : m.verts) {
            float x = v.x * INV, y = v.y * INV, z = v.z * INV;
            mn[0]=std::min(mn[0],x); mn[1]=std::min(mn[1],y); mn[2]=std::min(mn[2],z);
            mx[0]=std::max(mx[0],x); mx[1]=std::max(mx[1],y); mx[2]=std::max(mx[2],z);
        }
    }
    cx = (mn[0]+mx[0])*0.5f;
    cy = (mn[1]+mx[1])*0.5f;
    cz = (mn[2]+mx[2])*0.5f;
    float dx = mx[0]-mn[0], dy = mx[1]-mn[1], dz = mx[2]-mn[2];
    radius = sqrtf(dx*dx+dy*dy+dz*dz)*0.5f + 0.001f;
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

static void render_meshes(const std::vector<Mesh>& meshes) {
    for (const auto& mesh : meshes) {
        // Group faces by material for coloring
        glBegin(GL_TRIANGLES);
        for (const auto& face : mesh.faces) {
            // Pick material colour
            float r=0.8f, g=0.8f, b=0.8f;
            int mi = face.mat_idx;
            if (mi >= 0 && mi < (int)mesh.mats.size()) {
                uint32_t col = mesh.mats[mi].color;
                r = ((col >> 16) & 0xFF) / 255.0f;
                g = ((col >>  8) & 0xFF) / 255.0f;
                b = ((col      ) & 0xFF) / 255.0f;
                // Use slightly brightened: if too dark, show light grey
                if (r+g+b < 0.15f) { r=0.7f; g=0.7f; b=0.7f; }
            }
            glColor3f(r, g, b);

            auto emit = [&](int16_t vi) {
                if (vi < 0 || vi >= (int)mesh.verts.size()) return;
                const auto& v = mesh.verts[vi];
                glVertex3f(v.x * INV, v.y * INV, v.z * INV);
            };
            emit(face.v1);
            emit(face.v2);
            emit(face.v3);
        }
        glEnd();

        // Wireframe overlay (darker)
        glColor3f(0.2f, 0.2f, 0.2f);
        for (const auto& face : mesh.faces) {
            glBegin(GL_LINE_LOOP);
            auto emit = [&](int16_t vi) {
                if (vi < 0 || vi >= (int)mesh.verts.size()) return;
                const auto& v = mesh.verts[vi];
                glVertex3f(v.x * INV, v.y * INV, v.z * INV);
            };
            emit(face.v1);
            emit(face.v2);
            emit(face.v3);
            glEnd();
        }
    }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

int main(int argc, char** argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: wf_viewer file1.iff [file2.iff ...]\n");
        return 1;
    }

    // Load all meshes
    std::vector<Mesh> meshes;
    for (int i = 1; i < argc; ++i) {
        Mesh m;
        if (load_modl(argv[i], m))
            meshes.push_back(std::move(m));
    }
    if (meshes.empty()) {
        fprintf(stderr, "No meshes loaded\n");
        return 1;
    }

    // Compute bounding sphere
    float cx, cy, cz, radius;
    mesh_bounds(meshes, cx, cy, cz, radius);
    float dist = radius * 2.5f;

    // X11 + GLX setup
    Display* dpy = XOpenDisplay(nullptr);
    if (!dpy) { fprintf(stderr, "Cannot open display\n"); return 1; }

    int glx_attrs[] = {
        GLX_RGBA, GLX_DOUBLEBUFFER,
        GLX_RED_SIZE, 8, GLX_GREEN_SIZE, 8, GLX_BLUE_SIZE, 8,
        GLX_DEPTH_SIZE, 24,
        None
    };
    XVisualInfo* vi = glXChooseVisual(dpy, DefaultScreen(dpy), glx_attrs);
    if (!vi) { fprintf(stderr, "glXChooseVisual failed\n"); return 1; }

    GLXContext ctx = glXCreateContext(dpy, vi, nullptr, GL_TRUE);
    if (!ctx) { fprintf(stderr, "glXCreateContext failed\n"); return 1; }

    Colormap cmap = XCreateColormap(dpy, RootWindow(dpy, vi->screen),
                                    vi->visual, AllocNone);
    XSetWindowAttributes swa;
    swa.colormap   = cmap;
    swa.event_mask = ExposureMask | KeyPressMask | ButtonPressMask |
                     ButtonReleaseMask | PointerMotionMask | StructureNotifyMask;

    int win_w = 800, win_h = 600;
    Window win = XCreateWindow(dpy, RootWindow(dpy, vi->screen),
                               0, 0, win_w, win_h, 0, vi->depth, InputOutput,
                               vi->visual, CWColormap | CWEventMask, &swa);

    // Build title from first filename
    std::string title = "wf_viewer";
    if (argc >= 2) { title += ": "; title += argv[1]; }
    XStoreName(dpy, win, title.c_str());

    // Intercept WM_DELETE_WINDOW
    Atom wm_delete = XInternAtom(dpy, "WM_DELETE_WINDOW", False);
    XSetWMProtocols(dpy, win, &wm_delete, 1);

    XMapWindow(dpy, win);
    glXMakeCurrent(dpy, win, ctx);

    // GL state
    glEnable(GL_DEPTH_TEST);
    glClearColor(0.15f, 0.15f, 0.20f, 1.0f);

    // Camera orbit state
    float yaw = 30.0f, pitch = -20.0f;   // degrees
    bool  dragging = false;
    int   last_mx = 0, last_my = 0;

    bool running = true;
    while (running) {
        // Process all pending events
        while (XPending(dpy)) {
            XEvent ev;
            XNextEvent(dpy, &ev);
            switch (ev.type) {
            case ConfigureNotify:
                win_w = ev.xconfigure.width;
                win_h = ev.xconfigure.height;
                glViewport(0, 0, win_w, win_h);
                break;
            case KeyPress: {
                KeySym ks = XLookupKeysym(&ev.xkey, 0);
                if (ks == XK_q || ks == XK_Q || ks == XK_Escape)
                    running = false;
                else if (ks == XK_r || ks == XK_R) {
                    yaw = 30.0f; pitch = -20.0f;
                    dist = radius * 2.5f;
                }
                break;
            }
            case ButtonPress:
                if (ev.xbutton.button == 1) {
                    dragging = true;
                    last_mx = ev.xbutton.x;
                    last_my = ev.xbutton.y;
                } else if (ev.xbutton.button == 4) {
                    dist *= 0.9f;
                } else if (ev.xbutton.button == 5) {
                    dist *= 1.1f;
                }
                break;
            case ButtonRelease:
                if (ev.xbutton.button == 1) dragging = false;
                break;
            case MotionNotify:
                if (dragging) {
                    yaw   += (ev.xmotion.x - last_mx) * 0.5f;
                    pitch += (ev.xmotion.y - last_my) * 0.5f;
                    pitch = std::max(-89.0f, std::min(89.0f, pitch));
                    last_mx = ev.xmotion.x;
                    last_my = ev.xmotion.y;
                }
                break;
            case ClientMessage:
                if ((Atom)ev.xclient.data.l[0] == wm_delete)
                    running = false;
                break;
            }
        }

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

        // Projection
        glMatrixMode(GL_PROJECTION);
        glLoadIdentity();
        mat_perspective(45.0, (double)win_w / win_h, radius * 0.01, dist * 10.0);

        // Camera: orbit around centroid
        glMatrixMode(GL_MODELVIEW);
        glLoadIdentity();
        // Position eye along direction determined by yaw/pitch
        float yr = yaw   * (float)(M_PI / 180.0);
        float pr = pitch * (float)(M_PI / 180.0);
        float eye_x = cx + dist * cosf(pr) * sinf(yr);
        float eye_y = cy + dist * sinf(pr);
        float eye_z = cz + dist * cosf(pr) * cosf(yr);
        mat_look_at(eye_x, eye_y, eye_z,
                    cx, cy, cz,
                    0.0f, 1.0f, 0.0f);

        // Simple directional light (no textures, just flat colour shading)
        render_meshes(meshes);

        glXSwapBuffers(dpy, win);

        // Don't busy-spin: sleep ~16ms (~60fps) when no events
        if (!XPending(dpy)) {
            struct timespec ts = {0, 16000000};
            nanosleep(&ts, nullptr);
        }
    }

    glXMakeCurrent(dpy, None, nullptr);
    glXDestroyContext(dpy, ctx);
    XDestroyWindow(dpy, win);
    XCloseDisplay(dpy);
    return 0;
}
