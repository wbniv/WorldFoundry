// shared_geometry_loader: native test of the shared model geometry loader
// (gfx/rendobj3.cc, GREF + UVCL appearances naming a GEOM asset).
//
// Loads the real Temple pier pair (plain and shared forms, as the chapter
// pass wrote them) and the generated cube fixtures through RenderObject3D's
// on-disk constructor with fake callbacks, and checks:
//   - a shared appearance decodes to the vertices and faces of its plain model
//     (exactly for a reference/cube, as the same triangle set for a
//     re-indexed variant), material sort and normals included;
//   - collision's raw read (ReadSharedGeometry) equals the plain VRTX/FACE;
//   - one record per geometry asset: read once, reused, released by the last
//     holder, rebuilt on the next acquire, and an old
//     record under the same packed id is not reused for different bytes;
//   - every defect in tests/fixtures/shared_geometry/cube/bad fails loudly,
//     naming the model and the geometry (each in a forked child).
//
//   shared_geometry_loader <tests/fixtures/shared_geometry>
#include <gfx/rendobj3.hp>
#include <gfx/pixelmap.hp>
#include <gfx/material.hp>
#include <memory/lmalloc.hp>
#include <hal/halbase.h>
#include <streams/binstrm.hp>

#include <sys/wait.h>
#include <unistd.h>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <tuple>
#include <vector>

namespace {

int failures = 0;
#define CHECK(cond, ...) do { if (!(cond)) { ++failures; std::fprintf(stderr, "FAIL %s:%d: %s: ", __FILE__, __LINE__, #cond); std::fprintf(stderr, __VA_ARGS__); std::fprintf(stderr, "\n"); } } while (0)

std::vector<char> ReadFile(const std::string& path)
{
    std::vector<char> bytes;
    FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) { std::fprintf(stderr, "shared_geometry_loader: cannot open %s\n", path.c_str()); std::exit(2); }
    char buffer[65536];
    size_t n;
    while ((n = std::fread(buffer, 1, sizeof(buffer), f)) > 0) bytes.insert(bytes.end(), buffer, buffer + n);
    std::fclose(f);
    return bytes;
}

int32 Pack(int room, int index) { return int32((3u << 24) | (uint32(room & 0xFFF) << 12) | uint32(index & 0xFFF)); }
int RoomOf(int32 id) { return (uint32(id) >> 12) & 0xFFF; }

// Stands in for GameGfxCallbacks + AssetManager: assets by (room, name).
struct FakeAssets : public GfxCallbacks
{
    // A 256x256 texture filling the bound map, so every UV in [0,1] is in bounds
    // (emptyTexture sits at u=320, outside any small test map).
    PixelMap pixelMap{PixelMap::MEMORY_VIDEO, 256, 256};
    Texture texture = {"fake", 0, 0, 0, 256, 256, 0, 0, 0, 16};
    struct Asset { std::string name; std::vector<char> bytes; };
    std::map<int32, Asset> assets;
    mutable int streams = 0;

    void Add(int32 id, const std::string& name, const std::string& path) { assets[id] = {name, ReadFile(path)}; }

    LookupTextureStruct LookupTexture(const char*, int32) const override { return LookupTextureStruct(texture, pixelMap); }
    int32 LookupGeometry(const char* name, int32 userData) const override
    {
        for (const auto& [id, asset] : assets)
            if (RoomOf(id) == RoomOf(userData) && asset.name == name) return id;
        return 0;
    }
    binistream GetGeometryStream(int32 id) const override
    {
        ++streams;
        const Asset& asset = assets.at(id);
        return binistream(asset.bytes.data(), int32(asset.bytes.size()));
    }
    const char* LookupAssetName(int32 userData) const override
    {
        auto it = assets.find(userData);
        return it == assets.end() ? "" : it->second.name.c_str();
    }
protected:
    void _Validate() const override {}
};

LMalloc* gMemory = nullptr;

RenderObject3D* Load(const FakeAssets& callbacks, int32 id, const std::vector<char>& bytes)
{
    binistream input(bytes.data(), int32(bytes.size()));
    return new (*gMemory) RenderObject3D(*gMemory, input, id, callbacks);
}

RenderObject3D* Load(const FakeAssets& callbacks, int32 id) { return Load(callbacks, id, callbacks.assets.at(id).bytes); }

RenderObject3D* LoadPlain(const std::string& path)
{
    // Leaked on purpose: ~PixelMap at static destruction calls into a backend
    // that is already gone ("pure virtual method called").
    static FakeAssets* none = new FakeAssets;
    static std::vector<std::vector<char>>* keep = new std::vector<std::vector<char>>;
    keep->push_back(ReadFile(path));
    return Load(*none, Pack(0, 1), keep->back());
}

// As Actor::UnBindAssets does: run the destructor, leave the arena block to the
// slot's wholesale free (LMalloc frees are LIFO, which out-of-order release is not).
void Destroy(RenderObject3D* object) { object->~RenderObject3D(); }

bool SameVertex(const Vertex3D& a, const Vertex3D& b)
{
    return std::memcmp(&a.u, &b.u, sizeof(a.u)) == 0 && std::memcmp(&a.v, &b.v, sizeof(a.v)) == 0 &&
           std::memcmp(&a.color, &b.color, sizeof(a.color)) == 0 &&
           std::memcmp(&a.position, &b.position, sizeof(a.position)) == 0;
}

bool SameFace(const TriFace& a, const TriFace& b)
{
    return a.v1Index == b.v1Index && a.v2Index == b.v2Index && a.v3Index == b.v3Index &&
           a.materialIndex == b.materialIndex && std::memcmp(&a.normal, &b.normal, sizeof(a.normal)) == 0;
}

// Exact equality: same vertex array, same material-sorted faces with normals.
void ExpectIdentical(const char* what, RenderObject3D& shared, RenderObject3D& plain)
{
    CHECK(shared.GetVertexCount() == plain.GetVertexCount(), "%s vertex count %d vs %d", what, shared.GetVertexCount(), plain.GetVertexCount());
    CHECK(shared.GetFaceCount() == plain.GetFaceCount(), "%s face count", what);
    if (shared.GetVertexCount() != plain.GetVertexCount() || shared.GetFaceCount() != plain.GetFaceCount()) return;
    const Vertex3D* sv = shared.GetWrittableVertexList();
    const Vertex3D* pv = plain.GetWrittableVertexList();
    int vertexDiffs = 0, faceDiffs = 0;
    for (int i = 0; i < shared.GetVertexCount(); ++i) vertexDiffs += !SameVertex(sv[i], pv[i]);
    for (int i = 0; i < shared.GetFaceCount(); ++i) faceDiffs += !SameFace(shared.GetFaceList()[i], plain.GetFaceList()[i]);
    CHECK(vertexDiffs == 0, "%s: %d vertices differ", what, vertexDiffs);
    CHECK(faceDiffs == 0, "%s: %d faces differ", what, faceDiffs);
    CHECK(shared.GetFaceList()[shared.GetFaceCount()].materialIndex == -1, "%s dummy face", what);
    CHECK(shared.GetMaterialCount() == plain.GetMaterialCount(), "%s material count", what);
    std::printf("  identical  %-28s %d vertices, %d faces\n", what, shared.GetVertexCount(), shared.GetFaceCount());
}

// Same rendered triangles (corner position/UV/colour, corner order, material,
// normal), in any face order: a variant re-indexed onto the reference slots.
using Corner = std::vector<unsigned char>;
std::vector<std::vector<unsigned char>> Triangles(RenderObject3D& object)
{
    std::vector<std::vector<unsigned char>> out;
    const Vertex3D* v = object.GetWrittableVertexList();
    for (int f = 0; f < object.GetFaceCount(); ++f) {
        const TriFace& face = object.GetFaceList()[f];
        std::vector<unsigned char> key;
        auto put = [&](const void* p, size_t n) { const unsigned char* b = static_cast<const unsigned char*>(p); key.insert(key.end(), b, b + n); };
        for (int i : {face.v1Index, face.v2Index, face.v3Index}) { put(&v[i].u, sizeof v[i].u); put(&v[i].v, sizeof v[i].v); put(&v[i].color, sizeof v[i].color); put(&v[i].position, sizeof v[i].position); }
        put(&face.materialIndex, sizeof face.materialIndex);
        put(&face.normal, sizeof face.normal);
        out.push_back(key);
    }
    std::sort(out.begin(), out.end());
    return out;
}

void ExpectSameTriangles(const char* what, RenderObject3D& shared, RenderObject3D& plain)
{
    CHECK(Triangles(shared) == Triangles(plain), "%s triangle sets differ", what);
    std::printf("  same tris  %-28s %d faces\n", what, shared.GetFaceCount());
}

struct Raw { std::vector<int32> positions; std::vector<std::tuple<int, int, int>> faces; };

// What actor.cc feeds JoltMakeStaticMesh for a plain MODL: VRTX xyz and FACE, as stored.
Raw PlainRaw(const std::vector<char>& file)
{
    Raw raw;
    size_t i = 8;
    while (i + 8 <= file.size()) {
        uint32 size; std::memcpy(&size, &file[i + 4], 4);
        const char* p = &file[i + 8];
        if (!std::memcmp(&file[i], "VRTX", 4))
            for (size_t o = 0; o < size; o += 24) { int32 xyz[3]; std::memcpy(xyz, p + o + 12, 12); raw.positions.insert(raw.positions.end(), xyz, xyz + 3); }
        if (!std::memcmp(&file[i], "FACE", 4))
            for (size_t o = 0; o < size; o += 8) { int16 f[4]; std::memcpy(f, p + o, 8); raw.faces.emplace_back(f[0], f[1], f[2]); }
        i += 8 + size;
    }
    return raw;
}

// ...and for a GREF appearance: the GREF's geometry through ReadSharedGeometry.
Raw SharedRaw(const std::vector<char>& appearance, const std::vector<char>& geometry)
{
    Raw raw;
    size_t i = 8;
    GeometryReferenceOnDisk gref{};
    while (i + 8 <= appearance.size()) {
        uint32 size; std::memcpy(&size, &appearance[i + 4], 4);
        if (!std::memcmp(&appearance[i], "GREF", 4)) CHECK(ParseGeometryReference(&appearance[i + 8], int(size), gref) == nullptr, "GREF parses");
        i += 8 + size;
    }
    binistream stream(geometry.data(), int32(geometry.size()));
    std::vector<_TriFaceOnDisk> faces;
    const char* why = ReadSharedGeometry(stream, gref, raw.positions, faces);
    CHECK(why == nullptr, "ReadSharedGeometry: %s", why ? why : "");
    for (const auto& f : faces) raw.faces.emplace_back(f.v1Index, f.v2Index, f.v3Index);
    return raw;
}

// Run `body` in a child; expect it to die with a message containing every needle.
void ExpectDeath(const char* what, const std::vector<std::string>& needles, void (*body)(const char*), const char* arg)
{
    int pipefd[2];
    if (pipe(pipefd) != 0) { std::perror("pipe"); std::exit(2); }
    std::fflush(nullptr);
    pid_t pid = fork();
    if (pid == 0) {
        close(pipefd[0]);
        dup2(pipefd[1], 2);
        dup2(pipefd[1], 1);
        body(arg);
        _exit(0);			// survived: the parent reports it
    }
    close(pipefd[1]);
    std::string out;
    char buffer[4096];
    ssize_t n;
    while ((n = read(pipefd[0], buffer, sizeof buffer)) > 0) out.append(buffer, size_t(n));
    close(pipefd[0]);
    int status = 0;
    waitpid(pid, &status, 0);
    const bool died = !(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    CHECK(died, "%s: loaded without failing", what);
    for (const std::string& needle : needles) CHECK(out.find(needle) != std::string::npos, "%s: message lacks \"%s\": %s", what, needle.c_str(), out.c_str());
    const size_t start = out.find("shared geometry");
    std::printf("  rejected   %-16s %s\n", what,
                start == std::string::npos ? "(no message)" : out.substr(start, out.find('\n', start) - start).c_str());
}

std::string gRoot;

void LoadBad(const char* name)
{
    FakeAssets assets;
    const std::string dir = gRoot + "/cube/bad/" + name;
    assets.Add(Pack(1, 1), "cube_a.iff", dir + "/cube_a.iff");
    assets.Add(Pack(1, 2), "cube_geo.iff", dir + "/cube_geo.iff");
    Load(assets, Pack(1, 1));
}

void WriteSharedFaces(const char*)
{
    FakeAssets assets;
    assets.Add(Pack(1, 1), "cube_a.iff", gRoot + "/cube/shared/cube_a.iff");
    assets.Add(Pack(1, 2), "cube_geo.iff", gRoot + "/cube/shared/cube_geo.iff");
    Load(assets, Pack(1, 1))->GetWritableFaceList();
}

void GeometryInOtherRoom(const char*)
{
    FakeAssets assets;
    assets.Add(Pack(1, 1), "cube_a.iff", gRoot + "/cube/shared/cube_a.iff");
    assets.Add(Pack(2, 1), "cube_geo.iff", gRoot + "/cube/shared/cube_geo.iff");	// wrong room
    Load(assets, Pack(1, 1));
}

} // namespace

int main(int argc, char** argv)
{
    if (argc != 2) { std::fprintf(stderr, "usage: shared_geometry_loader <tests/fixtures/shared_geometry>\n"); return 2; }
    gRoot = argv[1];
    static std::vector<char> scratch(4 << 20), heap(64 << 20);
    _HALScratchLmalloc = new LMalloc(scratch.data(), scratch.size() MEMORY_NAMED(COMMA "shared-geometry-scratch"));
    gMemory = new LMalloc(heap.data(), heap.size() MEMORY_NAMED(COMMA "shared-geometry-heap"));

    // --- real pier pair -----------------------------------------------------
    std::puts("pier (real chapter output):");
    RenderObject3D* plain0 = LoadPlain(gRoot + "/pier-plain/temple_pier_0.iff");
    RenderObject3D* plain1 = LoadPlain(gRoot + "/pier-plain/temple_pier_1.iff");
    CHECK(!plain0->UsesSharedGeometry() && RenderObject3D::SharedGeometryLiveCount() == 0, "plain models share nothing");

    FakeAssets room2;
    room2.Add(Pack(2, 1), "temple_pier_0.iff", gRoot + "/pier-shared/temple_pier_0.iff");
    room2.Add(Pack(2, 2), "temple_pier_1.iff", gRoot + "/pier-shared/temple_pier_1.iff");
    room2.Add(Pack(2, 3), "temple_pier_0_geo.iff", gRoot + "/pier-shared/temple_pier_0_geo.iff");
    RenderObject3D* shared0 = Load(room2, Pack(2, 1));
    CHECK(RenderObject3D::SharedGeometryLiveCount() == 1 && room2.streams == 1, "first user builds the record");
    RenderObject3D* shared1 = Load(room2, Pack(2, 2));
    CHECK(RenderObject3D::SharedGeometryLiveCount() == 1 && room2.streams == 1, "second user reuses it (streams=%d)", room2.streams);
    CHECK(shared0->GetFaceList() == shared1->GetFaceList(), "one shared TriFace array");
    CHECK(shared0->GetWrittableVertexList() != shared1->GetWrittableVertexList(), "own vertex arrays");
    ExpectIdentical("temple_pier_0 (reference)", *shared0, *plain0);
    ExpectSameTriangles("temple_pier_1 (re-indexed)", *shared1, *plain1);

    // Collision reads: POSN/FACE as stored == the plain model's VRTX/FACE.
    const std::vector<char> geo = ReadFile(gRoot + "/pier-shared/temple_pier_0_geo.iff");
    Raw p0 = PlainRaw(ReadFile(gRoot + "/pier-plain/temple_pier_0.iff"));
    Raw s0 = SharedRaw(room2.assets.at(Pack(2, 1)).bytes, geo);
    CHECK(p0.positions == s0.positions && p0.faces == s0.faces, "pier_0 collision input identical");
    Raw p1 = PlainRaw(ReadFile(gRoot + "/pier-plain/temple_pier_1.iff"));
    Raw s1 = SharedRaw(room2.assets.at(Pack(2, 2)).bytes, geo);
    auto corners = [](const Raw& r) {
        std::vector<std::vector<int32>> t;
        for (auto [a, b, c] : r.faces) { std::vector<int32> k; for (int i : {a, b, c}) k.insert(k.end(), &r.positions[i * 3], &r.positions[i * 3] + 3); t.push_back(k); }
        std::sort(t.begin(), t.end());
        return t;
    };
    CHECK(corners(p1) == corners(s1), "pier_1 collision triangles identical");
    std::printf("  collision  pier_0 identical input, pier_1 same %zu triangles\n", s1.faces.size());

    // Release order and re-acquire.
    Destroy(shared0);
    CHECK(RenderObject3D::SharedGeometryLiveCount() == 1, "record survives while pier_1 holds it");
    // The copy constructor (particles) would take its own reference here, but
    // it cannot run in this build for any model: without USE_ORDER_TABLES it
    // never allocates _primList and ApplyMaterials asserts on it (pre-existing).
    Destroy(shared1);
    CHECK(RenderObject3D::SharedGeometryLiveCount() == 0, "last holder frees the record");
    shared0 = Load(room2, Pack(2, 1));
    CHECK(RenderObject3D::SharedGeometryLiveCount() == 1 && room2.streams == 2, "re-acquire rebuilds (streams=%d)", room2.streams);
    ExpectIdentical("temple_pier_0 re-acquired", *shared0, *plain0);
    std::printf("  lifetime   release order, re-acquire: live=%d streams=%d\n", RenderObject3D::SharedGeometryLiveCount(), room2.streams);

    // --- cube: exact equality for both appearances, material sort exercised --
    std::puts("cube (generated):");
    // Same packed id as the live pier geometry, different bytes: another
    // level's asset. The pier record must not be reused for it.
    FakeAssets level2;
    level2.Add(Pack(2, 1), "cube_a.iff", gRoot + "/cube/shared/cube_a.iff");
    level2.Add(Pack(2, 2), "cube_b.iff", gRoot + "/cube/shared/cube_b.iff");
    level2.Add(Pack(2, 3), "cube_geo.iff", gRoot + "/cube/shared/cube_geo.iff");
    RenderObject3D* cubeA = Load(level2, Pack(2, 1));
    RenderObject3D* cubeB = Load(level2, Pack(2, 2));
    CHECK(RenderObject3D::SharedGeometryLiveCount() == 2 && level2.streams == 1, "stale id not reused; cube built once");
    RenderObject3D* plainA = LoadPlain(gRoot + "/cube/cube_a.iff");
    RenderObject3D* plainB = LoadPlain(gRoot + "/cube/cube_b.iff");
    ExpectIdentical("cube_a", *cubeA, *plainA);
    ExpectIdentical("cube_b", *cubeB, *plainB);
    bool sorted = true, reordered = false;
    for (int f = 1; f < cubeA->GetFaceCount(); ++f) sorted &= cubeA->GetFaceList()[f - 1].materialIndex <= cubeA->GetFaceList()[f].materialIndex;
    reordered = cubeA->GetFaceList()[2].v1Index != 4;	// on disk, face 2 is side 1's (material 1), first vertex 4
    CHECK(sorted && reordered, "material sort applied (sorted=%d reordered=%d)", sorted, reordered);
    Destroy(cubeA); Destroy(cubeB); Destroy(shared0);
    CHECK(RenderObject3D::SharedGeometryLiveCount() == 0, "all released");

    // --- rejections ------------------------------------------------------------
    std::puts("rejections:");
    const std::vector<std::pair<const char*, const char*>> bad = {
        {"pos-crc", "CRC"}, {"face-crc", "CRC"}, {"vertex-count", "counts"}, {"uvcl-count", "UVCL"},
        {"face-index", "vertex index"}, {"version", "version"}, {"missing", "no asset"},
        {"material-index", "material index"}, {"lrig", "LRIG"},
    };
    for (const auto& [name, needle] : bad) {
        std::vector<std::string> needles = {"shared geometry: model cube_a.iff", needle};
        if (std::strcmp(name, "version")) needles.push_back(std::strcmp(name, "missing") ? "geometry cube_geo.iff" : "geometry cube_gone.iff");
        ExpectDeath(name, needles, LoadBad, name);
    }
    ExpectDeath("other-room", {"cube_a.iff", "geometry cube_geo.iff", "no asset of that name in the model's room"}, GeometryInOtherRoom, "");
    ExpectDeath("write-faces", {"GetWritableFaceList"}, WriteSharedFaces, "");

    Destroy(plain0); Destroy(plain1); Destroy(plainA); Destroy(plainB);
    if (failures) std::printf("FAIL: %d check(s)\n", failures);
    else std::puts("PASS: shared geometry loader");
    std::fflush(nullptr);
    _exit(failures ? 1 : 0);		// skip static destructors (see LoadPlain)
}
