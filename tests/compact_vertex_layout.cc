#include <gfx/glpipeline/compact_vertex.hp>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

static void Require(bool ok, const char* what)
{
    if (!ok) { std::fprintf(stderr, "compact_vertex_layout: %s\n", what); std::exit(1); }
}

static bool SameBits(float a, float b)
{
    return std::memcmp(&a, &b, sizeof(float)) == 0;
}

static void CheckNormal(float nx, float ny, float nz)
{
    RBVertex source = {1.25f, -2.5f, 0.125f, 1.f, 1.f, 1.f,
                       0.33333334f, -0.25f};
    wf_compact_vertex::Vertex packed = {};
    Require(wf_compact_vertex::Pack(packed, source, nx, ny, nz), "normal sample did not pack");
    Require(SameBits(source.x, packed.x) && SameBits(source.y, packed.y) &&
            SameBits(source.z, packed.z) && SameBits(source.u, packed.u) &&
            SameBits(source.v, packed.v), "position or UV changed bits");

    float x = float(packed.ox) / 32767.f;
    float y = float(packed.oy) / 32767.f;
    float z = 1.f - std::abs(x) - std::abs(y);
    if (z < 0.f)
    {
        const float oldX = x, oldY = y;
        x = (1.f - std::abs(oldY)) * (oldX >= 0.f ? 1.f : -1.f);
        y = (1.f - std::abs(oldX)) * (oldY >= 0.f ? 1.f : -1.f);
    }
    const double sourceLength = std::sqrt(double(nx)*nx + double(ny)*ny + double(nz)*nz);
    const double decodedLength = std::sqrt(double(x)*x + double(y)*y + double(z)*z);
    const double dot = (double(nx)*x + double(ny)*y + double(nz)*z) /
                       (sourceLength * decodedLength);
    Require(dot > std::cos(0.005 * 3.14159265358979323846 / 180.0),
            "oct16 normal exceeds 0.005 degrees");
}

int main()
{
    for (int value = 0; value <= 255; ++value)
    {
        RBVertex source = {};
        source.r = source.g = source.b = float(value) / 256.f;
        wf_compact_vertex::Vertex packed = {};
        Require(wf_compact_vertex::Pack(packed, source, 0, 0, 1), "byte/256 color did not pack");
        Require(packed.r == value && packed.g == value && packed.b == value &&
                packed.divisor255 == 0, "byte/256 encoding changed");
        source.r = source.g = source.b = float(value) / 255.f;
        Require(wf_compact_vertex::Pack(packed, source, 0, 0, 1), "byte/255 color did not pack");
        Require(packed.r == value && packed.g == value && packed.b == value &&
                packed.divisor255 == (value == 0 ? 0 : 255), "byte/255 encoding changed");
    }

    CheckNormal(0, 0, 1);
    CheckNormal(0, 0, -1);
    CheckNormal(1, 0, 0);
    CheckNormal(0.4f, -0.3f, 0.8660254f);
    CheckNormal(-0.5f, 0.5f, -0.70710678f);

    RBStaticTriangle triangle = {};
    triangle.nz = 1;
    triangle.v[0].r = triangle.v[1].r = triangle.v[2].r = 0.12345f;
    Require(!wf_compact_vertex::CanPack(&triangle, 1), "arbitrary float color must use legacy layout");
    triangle.v[0].r = triangle.v[1].r = triangle.v[2].r = 1.f;
    Require(wf_compact_vertex::CanPack(&triangle, 1), "byte color should use compact layout");
    triangle.nz = 0;
    Require(!wf_compact_vertex::CanPack(&triangle, 1), "zero normal must use legacy layout");
    std::puts("compact_vertex_layout: PASS");
    return 0;
}
