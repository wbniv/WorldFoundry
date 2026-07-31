//=============================================================================
// engine/wf_edit/level_doc.cc — see level_doc.h.
//=============================================================================
#include "level_doc.h"
#include "property_panel.h"  // wfedit::OadForClass (for AddActor)
#include "oad_reader.h"      // wfedit::OadEntry

#include "wfcrdt.hpp"
#include <nlohmann/json.hpp>

#include <oas/oad.h>   // BUTTON_* / SHOW_AS_* / LEVELCONFLAG_* constants

#include <unistd.h>

#include <array>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <optional>
#include <random>
#include <string>
#include <vector>

namespace wfedit {
namespace {

using json = nlohmann::json;

// ── stable actor ID for the collaborative bridge ────────────────────────────
// Each actor in the Doc gets a `_eid` key (editor-only UUID). `_eid` is never
// written to `.lev` (ChunkToJson only reads `chunk_type` + `items`), so it
// remains an ephemeral in-memory annotation used by the bridge map.
static std::string GenerateEid()
{
    std::mt19937_64 rng(std::random_device{}());
    std::uniform_int_distribution<uint64_t> d;
    uint64_t hi = d(rng), lo = d(rng);
    char buf[33];
    std::snprintf(buf, sizeof(buf), "%016llx%016llx",
                  (unsigned long long)hi, (unsigned long long)lo);
    return buf;
}

// ── locate the levtree binary ────────────────────────────────────────────────
// The editor runs from the repo root (like the M2/M3 relative level paths).
// $WF_LEVTREE overrides; otherwise prefer a release build, then debug, then
// whatever's on PATH.
std::string FindLevtree()
{
    if (const char* env = std::getenv("WF_LEVTREE"); env && *env && access(env, X_OK) == 0)
        return env;
    static const char* kCandidates[] = {
        "wftools/levtree-rs/target/release/levtree",
        "wftools/levtree-rs/target/debug/levtree",
    };
    for (const char* p : kCandidates)
        if (access(p, X_OK) == 0) return p;
    return "levtree";   // last resort: rely on PATH
}

// Shell-quote (paths come from CLI args / built-in defaults; defensive against
// odd filenames).
std::string ShQuote(const std::string& s)
{
    std::string q = "'";
    for (char c : s) { if (c == '\'') q += "'\\''"; else q += c; }
    return q + "'";
}

// ── run `levtree parse <lev>` and capture stdout ─────────────────────────────
bool RunLevtreeParse(const std::string& lev_path, std::string& out)
{
#if defined(__EMSCRIPTEN__)
    // No subprocess on wasm (popen doesn't exist). The web build pre-parses the
    // .lev with the native `levtree parse` and preloads the JSON next to it as
    // "<lev>.json" into MEMFS; read that instead. See the wf_edit_web preload in
    // CMakeLists + docs/plans/2026-06-12-wf-edit-in-the-browser.md (Doc-population).
    const std::string json_path = lev_path + ".json";
    FILE* jf = std::fopen(json_path.c_str(), "rb");
    if (!jf) {
        std::fprintf(stderr, "wf-edit(web): preloaded levtree JSON not found: %s\n",
                     json_path.c_str());
        return false;
    }
    std::array<char, 65536> jbuf;
    size_t jn;
    while ((jn = std::fread(jbuf.data(), 1, jbuf.size(), jf)) > 0)
        out.append(jbuf.data(), jn);
    std::fclose(jf);
    return !out.empty();
#else
    const std::string levtree = FindLevtree();
    // Paths come from CLI args / built-in defaults (trusted); shell-quote
    // single quotes defensively so odd filenames don't break the command.
    auto shquote = [](const std::string& s) {
        std::string q = "'";
        for (char c : s) { if (c == '\'') q += "'\\''"; else q += c; }
        return q + "'";
    };
    const std::string cmd = shquote(levtree) + " parse " + shquote(lev_path);

    FILE* pipe = popen(cmd.c_str(), "r");
    if (!pipe) {
        std::fprintf(stderr, "wf-edit: popen failed for: %s\n", cmd.c_str());
        return false;
    }
    std::array<char, 65536> buf;
    size_t n;
    while ((n = std::fread(buf.data(), 1, buf.size(), pipe)) > 0)
        out.append(buf.data(), n);
    const int rc = pclose(pipe);
    if (rc != 0) {
        std::fprintf(stderr, "wf-edit: `%s` exited %d\n", cmd.c_str(), rc);
        return false;
    }
    return true;
#endif // __EMSCRIPTEN__
}

// ── locate the levcomp binary (the binary-level decompiler) ──────────────────
// Mirrors FindLevtree. $WF_LEVCOMP overrides; else prefer release, then debug,
// then PATH.
std::string FindLevcomp()
{
    if (const char* env = std::getenv("WF_LEVCOMP"); env && *env && access(env, X_OK) == 0)
        return env;
    static const char* kCandidates[] = {
        "wftools/levcomp-rs/target/release/levcomp",
        "wftools/levcomp-rs/target/debug/levcomp",
    };
    for (const char* p : kCandidates)
        if (access(p, X_OK) == 0) return p;
    return "levcomp";   // last resort: rely on PATH
}

// Schema inputs the decompiler needs: objects.lc (class names) + the OAD dir
// (field names/types/enum labels). Both honour the same in-repo OAS tree the
// property panel runs against (WF_OAD_DIR), plus a dedicated WF_OBJECTS_LC.
std::string ObjectsLcPath()
{
    if (const char* env = std::getenv("WF_OBJECTS_LC"); env && *env) return env;
    return "wfsource/source/oas/objects.lc";
}
std::string OadDirPath()
{
    if (const char* env = std::getenv("WF_OAD_DIR"); env && *env) return env;
    return "wfsource/source/oas";
}

// First non-whitespace byte distinguishes text from binary: a text `.lev` opens
// with `{` (after optional whitespace), a compiled level with an IFF FOURCC
// (`L4`/`GAME`/`LVAS`…). Sniff the bytes — don't trust the extension. An
// unreadable/empty file → treat as text (let levtree report the real error).
bool IsBinaryLevel(const std::string& path)
{
    FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) return false;
    unsigned char buf[16];
    const size_t n = std::fread(buf, 1, sizeof(buf), f);
    std::fclose(f);
    for (size_t i = 0; i < n; ++i) {
        if (std::isspace(buf[i])) continue;
        return buf[i] != '{';   // '{' → text .lev; any other leading byte → binary
    }
    return false;   // empty / all-whitespace
}

// Split a "<file>:<selector>" argument into base path + cd.iff selector. Returns
// true (and fills `base`/`sel`) when a selector is present — the suffix carries
// no '/' (so a ':' inside a directory name isn't mistaken for one) and the base
// is a readable file. Otherwise returns false with `base` = the whole arg and
// `sel` empty. Shared by the loader and the picker gate so the syntax lives once.
bool SplitLevelSelector(const std::string& arg, std::string& base, std::string& sel)
{
    base = arg;
    sel.clear();
    if (auto colon = arg.find_last_of(':'); colon != std::string::npos) {
        std::string b = arg.substr(0, colon), s = arg.substr(colon + 1);
        if (!s.empty() && s.find('/') == std::string::npos && access(b.c_str(), R_OK) == 0) {
            base = std::move(b);
            sel  = std::move(s);
            return true;
        }
    }
    return false;
}

// ── run `levcomp decompile <in> <objects.lc> --oad-dir <oad> [--level <sel>]
//    -o <tmp>` → a temp `.lev` (the binary-level decompile pre-step). `sel`
//    selects a level from a cd.iff archive (FOURCC tag or decimal TOC index);
//    empty = a bare single-level `.iff`. On success `out_tmp` holds the temp
//    `.lev` path; the caller unlinks it after levtree consumes it.
bool RunLevcompDecompile(const std::string& in_path, const std::string& sel,
                         std::string& out_tmp)
{
    char tmpl[] = "/tmp/wfedit_decomp_XXXXXX";
    const int fd = mkstemp(tmpl);
    if (fd < 0) { std::fprintf(stderr, "wf-edit: mkstemp failed\n"); return false; }
    ::close(fd);   // levcomp writes the file itself; we only reserved a unique name

    std::string cmd = ShQuote(FindLevcomp()) + " decompile "
                    + ShQuote(in_path) + " " + ShQuote(ObjectsLcPath())
                    + " --oad-dir " + ShQuote(OadDirPath());
    if (!sel.empty()) cmd += " --level " + ShQuote(sel);
    cmd += " -o " + ShQuote(tmpl) + " 2>&1";

    FILE* pipe = popen(cmd.c_str(), "r");
    if (!pipe) {
        std::fprintf(stderr, "wf-edit: popen failed for: %s\n", cmd.c_str());
        ::unlink(tmpl);
        return false;
    }
    std::array<char, 65536> buf;   // drain (and, on failure, surface) levcomp's log
    size_t n;
    std::string log;
    while ((n = std::fread(buf.data(), 1, buf.size(), pipe)) > 0)
        log.append(buf.data(), n);
    const int rc = pclose(pipe);
    if (rc != 0) {
        std::fprintf(stderr, "wf-edit: `%s` exited %d\n%s\n", cmd.c_str(), rc, log.c_str());
        ::unlink(tmpl);
        return false;
    }
    out_tmp = tmpl;
    return true;
}

// ── levtree JSON chunk → wfcrdt::Input (the recursive CRDT chunk node) ────────
// Lossless schema (v2): a levtree Chunk is {"id","items":[Chunk|Literal]}; a
// Literal is {"kind":"str"|"num"|"four_cc", value/text/id}. The CRDT node mirrors
// it 1:1 (plan 2026-05-21-lossless-doc-schema, A2):
//   chunk   : Y.Map { chunk_type, items: Y.Array< chunk | literal > }
//   literal : Y.Map { kind, value|text|id }   — verbatim mirror of levtree Literal
// so save is a pure Doc→JSON copy (no retained-parse-JSON side-channel).
bool IsChunk(const json& item)   { return item.is_object() && item.contains("id") && item.contains("items"); }
bool IsLiteral(const json& item) { return item.is_object() && item.contains("kind"); }

// One levtree literal → its CRDT map (kind + the kind's body field, verbatim).
wfcrdt::Input BuildLiteral(const json& lit)
{
    wfcrdt::Input m = wfcrdt::Input::map();
    const std::string kind = lit.value("kind", "");
    m.set("kind", wfcrdt::Input::str(kind));
    if (kind == "str")          m.set("value", wfcrdt::Input::str(lit.value("value", "")));
    else if (kind == "num")     m.set("text",  wfcrdt::Input::str(lit.value("text", "")));
    else if (kind == "four_cc") m.set("id",    wfcrdt::Input::str(lit.value("id", "")));
    return m;
}

wfcrdt::Input BuildChunk(const json& chunk)
{
    wfcrdt::Input node = wfcrdt::Input::map();
    node.set("chunk_type", wfcrdt::Input::str(chunk.value("id", "")));
    wfcrdt::Input items = wfcrdt::Input::array();
    for (const auto& it : chunk["items"]) {
        if (IsChunk(it))        items.push(BuildChunk(it));
        else if (IsLiteral(it)) items.push(BuildLiteral(it));
    }
    node.set("items", std::move(items));
    return node;
}

// ── Doc-side readers over the v2 schema ──────────────────────────────────────
// A child map is a chunk if it carries `chunk_type`; otherwise it's a literal.
bool IsChunkMap(const wfcrdt::Map& m)
{
    return m.valid() && m.get("chunk_type").readString().has_value();
}

// A literal map's body, by kind (the inverse of BuildLiteral).
std::string LiteralBody(const wfcrdt::Map& lit)
{
    const std::string kind = lit.get("kind").readString().value_or("");
    if (kind == "str")     return lit.get("value").readString().value_or("");
    if (kind == "num")     return lit.get("text").readString().value_or("");
    if (kind == "four_cc") return lit.get("id").readString().value_or("");
    return "";
}

// A leaf chunk's literal bodies, space-joined — the old collapsed `text` view.
std::string LeafText(const wfcrdt::Map& chunk)
{
    wfcrdt::Array items = chunk.get("items").asArray();
    if (!items.valid()) return "";
    std::string out;
    const int n = items.len();
    for (int i = 0; i < n; ++i) {
        wfcrdt::Map m = items.get(i).asMap();
        if (!m.valid() || IsChunkMap(m)) continue;   // literals only
        if (!out.empty()) out += ' ';
        out += LiteralBody(m);
    }
    return out;
}

// ── read the NAME sub-chunk out of a chunk map ───────────────────────────────
std::string NameOf(const wfcrdt::Map& obj)
{
    // chunk_type fallback (for an OBJ with no NAME, or a COMMENT/odd node).
    std::string fallback = obj.get("chunk_type").readString().value_or("(chunk)");

    wfcrdt::Array items = obj.get("items").asArray();
    if (!items.valid()) return fallback;
    const int n = items.len();
    for (int i = 0; i < n; ++i) {
        wfcrdt::Map child = items.get(i).asMap();
        if (!IsChunkMap(child)) continue;
        if (child.get("chunk_type").readString().value_or("") == "NAME") {
            std::string body = LeafText(child);   // the NAME's literal body
            if (!body.empty()) return body;
        }
    }
    return fallback;
}

}  // namespace

// ── run `levtree print <json>` → canonical .lev (the inverse of parse) ───────
// levtree print reads a JSON file arg (or stdin); popen is one-way, so we stage
// the JSON in a temp file and read the .lev from stdout. Used by level_save.
bool RunLevtreePrint(const std::string& json, std::string& out_lev)
{
    const std::string levtree = FindLevtree();
    char tmpl[] = "/tmp/wfedit_save_XXXXXX";
    const int fd = mkstemp(tmpl);
    if (fd < 0) { std::fprintf(stderr, "wf-edit: mkstemp failed\n"); return false; }
    {
        FILE* tf = fdopen(fd, "w");
        if (!tf) { ::close(fd); ::unlink(tmpl); return false; }
        std::fwrite(json.data(), 1, json.size(), tf);
        std::fclose(tf);   // also closes fd
    }
    const std::string cmd = ShQuote(levtree) + " print " + ShQuote(tmpl);
    FILE* pipe = popen(cmd.c_str(), "r");
    if (!pipe) {
        std::fprintf(stderr, "wf-edit: popen failed for: %s\n", cmd.c_str());
        ::unlink(tmpl);
        return false;
    }
    std::array<char, 65536> buf;
    size_t n;
    while ((n = std::fread(buf.data(), 1, buf.size(), pipe)) > 0)
        out_lev.append(buf.data(), n);
    const int rc = pclose(pipe);
    ::unlink(tmpl);
    if (rc != 0) {
        std::fprintf(stderr, "wf-edit: `%s` exited %d\n", cmd.c_str(), rc);
        return false;
    }
    return true;
}

// ── run `build_level_binary.sh <level>` → .iff (the .lev → .iff compile) ─────
// Shells out to the existing 5-stage pipeline (iffcomp/levcomp/textile/iffcomp);
// captures its stdout+stderr into out_log. Used by the editor's Save + Compile.
bool RunBuildLevel(const std::string& level_name, std::string& out_log)
{
    const std::string cmd = "bash " + ShQuote("wftools/wf_blender/build_level_binary.sh")
                          + " " + ShQuote(level_name) + " 2>&1";
    FILE* pipe = popen(cmd.c_str(), "r");
    if (!pipe) {
        std::fprintf(stderr, "wf-edit: popen failed for: %s\n", cmd.c_str());
        return false;
    }
    std::array<char, 65536> buf;
    size_t n;
    while ((n = std::fread(buf.data(), 1, buf.size(), pipe)) > 0)
        out_log.append(buf.data(), n);
    return pclose(pipe) == 0;
}

std::vector<CdIffLevel> ListCdIffLevels(const std::string& cd_path)
{
    std::vector<CdIffLevel> out;
    // `levcomp decompile <cd.iff> <objects.lc> --list` dumps the TOC. The
    // progress lines go to stderr and the table to stdout; merge both (2>&1) and
    // pick out the data rows, so we don't depend on which stream a line lands on.
    const std::string cmd = ShQuote(FindLevcomp()) + " decompile "
                          + ShQuote(cd_path) + " " + ShQuote(ObjectsLcPath())
                          + " --list 2>&1";
    FILE* pipe = popen(cmd.c_str(), "r");
    if (!pipe) {
        std::fprintf(stderr, "wf-edit: popen failed for: %s\n", cmd.c_str());
        return out;
    }
    std::string all;
    std::array<char, 65536> buf;
    size_t n;
    while ((n = std::fread(buf.data(), 1, buf.size(), pipe)) > 0)
        all.append(buf.data(), n);
    const int rc = pclose(pipe);
    if (rc != 0) return out;   // not an archive / list failed — nothing to pick

    // Each data row is "  <idx>  <tag>  0x<offset>  <size>" (print_toc in
    // decompile.rs). The header "  idx  tag  offset  size" and the progress lines
    // don't parse as `int tag 0xhex int`, so sscanf's field count gates them out.
    std::size_t pos = 0;
    while (pos < all.size()) {
        std::size_t eol = all.find('\n', pos);
        const std::string line = all.substr(pos, eol == std::string::npos ? std::string::npos : eol - pos);
        pos = (eol == std::string::npos) ? all.size() : eol + 1;

        int  idx = 0;
        char tag[16] = {0};
        long off = 0, sz = 0;
        if (std::sscanf(line.c_str(), " %d %15s 0x%lx %ld", &idx, tag, &off, &sz) == 4) {
            CdIffLevel e;
            e.index  = idx;
            e.tag    = tag;
            e.offset = off;
            e.size   = sz;
            out.push_back(std::move(e));
        }
    }
    return out;
}

bool NeedsLevelPicker(const std::string& leveltree_arg)
{
    std::string base, sel;
    if (SplitLevelSelector(leveltree_arg, base, sel)) return false;  // explicit pick
    if (!IsBinaryLevel(base)) return false;                          // text .lev
    return ListCdIffLevels(base).size() >= 2;                        // multi-level archive
}

std::string ResolveEngineViewportLevel(const std::string& leveltree_arg, bool& out_is_temp)
{
    out_is_temp = false;
    std::string base, sel;
    const bool has_sel = SplitLevelSelector(leveltree_arg, base, sel);

    if (!has_sel) {
        // A bare binary .iff/.lvl is already a complete L<N> chunk (what -L wants);
        // a text .lev has no binary to render.
        if (!IsBinaryLevel(base)) return std::string();
        // …unless it's a multi-level .iff (e.g. wflevels/qbert_practice/qbert_practice.iff)
        // whose engine-loadable single-level companion lives at <base>-standalone.iff.
        // Try both same-dir and parent-dir variants (qbert ships both) before falling
        // back to the input, which would otherwise trip plmc->tagRam at level.cc:426
        // because the multi-level container isn't a complete L<N> chunk by itself.
        auto strip_suffix = [](const std::string& s) -> std::string {
            for (const char* suf : { ".iff", ".lvl" }) {
                const size_t L = std::strlen(suf);
                if (s.size() > L && s.compare(s.size() - L, L, suf) == 0)
                    return s.substr(0, s.size() - L);
            }
            return s;
        };
        const std::string stem = strip_suffix(base);
        if (stem.size() > 11 && stem.compare(stem.size() - 11, 11, "-standalone") == 0)
            return base;   // already the standalone variant
        // Candidate 1: same-dir sibling, e.g. wflevels/qbert/qbert.iff → wflevels/qbert/qbert-standalone.iff
        const std::string same_dir = stem + "-standalone.iff";
        if (access(same_dir.c_str(), R_OK) == 0) return same_dir;
        // Candidate 2: parent-dir sibling, e.g. wflevels/qbert/qbert.iff → wflevels/qbert-standalone.iff
        const auto slash = base.find_last_of('/');
        if (slash != std::string::npos) {
            const std::string parent_dir = base.substr(0, slash);
            const auto pslash = parent_dir.find_last_of('/');
            const std::string dirname  = (pslash == std::string::npos)
                                        ? parent_dir : parent_dir.substr(pslash + 1);
            const std::string parent_prefix = (pslash == std::string::npos)
                                             ? std::string() : parent_dir.substr(0, pslash + 1);
            const std::string up_one = parent_prefix + dirname + "-standalone.iff";
            if (access(up_one.c_str(), R_OK) == 0) return up_one;
        }
        return base;   // no standalone variant found — try the raw input (may fail at the engine)
    }

    // cd.iff:<tag|index> — find the entry's byte offset, then slice its complete
    // L<N> chunk to a temp .iff. Use the chunk's OWN little-endian size (the TOC
    // size is sector-granular and can fall short of the true extent).
    const std::vector<CdIffLevel> levels = ListCdIffLevels(base);
    long offset = -1;
    for (const auto& e : levels)
        if (e.tag == sel) { offset = e.offset; break; }
    if (offset < 0) {                       // not a tag — try a decimal index
        char* end = nullptr;
        const long idx = std::strtol(sel.c_str(), &end, 10);
        if (end && *end == '\0')
            for (const auto& e : levels)
                if (e.index == static_cast<int>(idx)) { offset = e.offset; break; }
    }
    if (offset < 0) {
        std::fprintf(stderr, "wf-edit: viewport: '%s' not found in %s\n", sel.c_str(), base.c_str());
        return std::string();
    }

    FILE* in = std::fopen(base.c_str(), "rb");
    if (!in) return std::string();
    unsigned char hdr[8];
    if (std::fseek(in, offset, SEEK_SET) != 0 || std::fread(hdr, 1, 8, in) != 8) {
        std::fclose(in);
        return std::string();
    }
    // wf_iff: chunk id big-endian, size little-endian. Extent = header + payload.
    const unsigned long payload =
        static_cast<unsigned long>(hdr[4])        | (static_cast<unsigned long>(hdr[5]) << 8) |
        (static_cast<unsigned long>(hdr[6]) << 16) | (static_cast<unsigned long>(hdr[7]) << 24);
    const unsigned long extent = 8 + payload;

    char tmpl[] = "/tmp/wfedit_vp_XXXXXX";
    const int fd = mkstemp(tmpl);
    if (fd < 0) { std::fclose(in); return std::string(); }
    FILE* outf = fdopen(fd, "wb");
    if (!outf) { ::close(fd); ::unlink(tmpl); std::fclose(in); return std::string(); }

    std::fwrite(hdr, 1, 8, outf);            // header already read; payload follows
    std::array<char, 65536> buf;
    unsigned long left = payload;
    while (left > 0) {
        const size_t want = (left < buf.size()) ? static_cast<size_t>(left) : buf.size();
        const size_t got  = std::fread(buf.data(), 1, want, in);
        if (got == 0) break;
        std::fwrite(buf.data(), 1, got, outf);
        left -= got;
    }
    std::fclose(outf);
    std::fclose(in);
    if (left != 0) {                          // short read → don't hand -L a truncated chunk
        std::fprintf(stderr, "wf-edit: viewport: short read slicing %s (%lu/%lu left)\n",
                     base.c_str(), left, payload);
        ::unlink(tmpl);
        return std::string();
    }
    out_is_temp = true;
    std::fprintf(stderr, "wf-edit: viewport level sliced from %s:%s -> %s (%lu bytes)\n",
                 base.c_str(), sel.c_str(), tmpl, extent);
    return tmpl;
}

bool LoadLevelTreeIntoDoc(const std::string& lev_path, wfcrdt::Doc& doc,
                          std::string* out_save_path)
{
    // Split an optional cd.iff selector "<file.iff>:<TAG|index>". A text .lev /
    // bare .iff has no selector and falls through unchanged.
    std::string in_path, sel;
    SplitLevelSelector(lev_path, in_path, sel);

    // Binary level (compiled .iff, bare or inside cd.iff)? Decompile it to a temp
    // .lev first, then feed that to the existing levtree → Doc path unchanged.
    std::string parse_path = in_path;
    std::string tmp_lev;
    if (IsBinaryLevel(in_path)) {
        if (!RunLevcompDecompile(in_path, sel, tmp_lev)) {
            std::fprintf(stderr, "wf-edit: levcomp decompile failed for %s\n", in_path.c_str());
            return false;
        }
        parse_path = tmp_lev;
    }

    std::string raw;
    const bool parsed = RunLevtreeParse(parse_path, raw);
    if (!tmp_lev.empty()) ::unlink(tmp_lev.c_str());   // temp consumed (or failed)
    if (!parsed) return false;

    json tree;
    try {
        tree = json::parse(raw);
    } catch (const std::exception& e) {
        std::fprintf(stderr, "wf-edit: levtree JSON parse failed: %s\n", e.what());
        return false;
    }

    if (!tree.contains("root") || !IsChunk(tree["root"])) {
        std::fprintf(stderr, "wf-edit: levtree JSON has no LVL root\n");
        return false;
    }
    const json& root = tree["root"];

    // Derive a level name from the INPUT path's basename (not the temp file):
    // drop the directory + final extension, and qualify with the cd.iff selector
    // when present (cd → cd_L4).
    std::string level_name = in_path;
    if (auto slash = level_name.find_last_of('/'); slash != std::string::npos)
        level_name.erase(0, slash + 1);
    if (auto dot = level_name.find_last_of('.'); dot != std::string::npos && dot != 0)
        level_name.erase(dot);
    if (!sel.empty()) level_name += "_" + sel;

    // Report where Save should write: the source .lev in-place for a text load;
    // a fresh sibling .lev (Save-As) for a binary load — the binary is read-only.
    if (out_save_path) {
        if (tmp_lev.empty()) {
            *out_save_path = in_path;
        } else {
            std::string dir;
            if (auto slash = in_path.find_last_of('/'); slash != std::string::npos)
                dir = in_path.substr(0, slash + 1);
            *out_save_path = dir + level_name + ".lev";
        }
    }

    auto txn = doc.begin();

    // Resolve BOTH root types up front, before any insert opens the write txn:
    // root resolution (ymap/yarray) opens its own internal txn in yffi and would
    // deadlock against an already-open write txn (wfcrdt's lazy-txn contract).
    auto meta = txn.map("meta");
    // content = the top-level OBJ chunks, with the LVL wrapper dropped (its id is
    // kept in meta.root_chunk_type so save can reconstruct the exact tree).
    auto content = txn.array("content");

    meta.insert("level_name", level_name.c_str());
    meta.insert("format_version", static_cast<long long>(2));
    meta.insert("root_chunk_type", root.value("id", "LVL").c_str());  // for the save inverse

    int objs = 0;
    for (const auto& item : root["items"]) {
        if (!IsChunk(item)) continue;          // skip stray literals at LVL level
        content.push(BuildChunk(item));
        // Stamp a stable per-actor UUID used by the CRDT bridge map. Never saved
        // to .lev — ChunkToJson only reads chunk_type + items.
        {
            wfcrdt::Map actor = content.get(content.len() - 1).asMap();
            if (actor.valid())
                actor.insert("_eid", GenerateEid().c_str());
        }
        ++objs;
    }
    std::printf("wf-edit: Y.Doc populated from %s — %d top-level chunks (schema v2)\n",
                in_path.c_str(), objs);
    return true;
}

std::vector<std::string> ReadActorNames(wfcrdt::Doc& doc)
{
    std::vector<std::string> names;
    auto txn = doc.begin();
    auto content = txn.array("content");
    const int n = content.len();
    names.reserve(static_cast<size_t>(n));
    for (int i = 0; i < n; ++i) {
        wfcrdt::Map obj = content.get(i).asMap();
        names.push_back(obj.valid() ? NameOf(obj) : "(?)");
    }
    return names;
}

std::vector<std::string> ReadActorEids(wfcrdt::Doc& doc)
{
    std::vector<std::string> eids;
    auto txn = doc.begin();
    auto content = txn.array("content");
    const int n = content.len();
    eids.reserve(static_cast<size_t>(n));
    for (int i = 0; i < n; ++i) {
        wfcrdt::Map m = content.get(i).asMap();
        eids.push_back(m.valid() ? m.get("_eid").readString().value_or("") : "");
    }
    return eids;
}

namespace {
// A field chunk is `{ chunk_type, items:[ NAME-chunk, DATA-chunk, STR-chunk, … ] }`
// (each sub-chunk's own items are its literals). Pull the field name (NAME
// sub-chunk's body) and value (everything else's body, space-joined). Derived
// `value`/`data`/`label` are identical to the pre-v2 schema, so the property
// panel + bridge are unchanged.
ActorField FieldFromChunk(const wfcrdt::Map& chunk)
{
    ActorField f;
    f.chunk_type = chunk.get("chunk_type").readString().value_or("");
    f.name = f.chunk_type;   // fallback if no NAME sub-chunk

    wfcrdt::Array items = chunk.get("items").asArray();
    if (!items.valid()) return f;
    const int n = items.len();

    // Bare-leaf field (its items are literals, not sub-chunks): value = its body.
    bool has_sub = false;
    for (int i = 0; i < n; ++i) if (IsChunkMap(items.get(i).asMap())) { has_sub = true; break; }
    if (!has_sub) { f.value = LeafText(chunk); return f; }

    for (int i = 0; i < n; ++i) {
        wfcrdt::Map sub = items.get(i).asMap();
        if (!IsChunkMap(sub)) continue;
        const std::string sct = sub.get("chunk_type").readString().value_or("");
        const std::string txt = LeafText(sub);   // the sub-chunk's literal body
        if (sct == "NAME") {
            if (!txt.empty()) f.name = txt;
            continue;
        }
        // Phase-1 space-joined form (raw fallback) keeps every non-NAME leaf.
        if (!f.value.empty()) f.value += ' ';
        f.value += txt;
        // Phase-2 split: DATA leaf(s) → raw value; STR leaf → display label.
        if (sct == "DATA") {
            if (!f.data.empty()) f.data += ' ';
            f.data += txt;
        } else if (sct == "STR") {
            f.label = txt;   // single STR leaf in practice; last wins
        }
    }
    return f;
}
}  // namespace

std::vector<ActorField> ReadActorFields(wfcrdt::Doc& doc, int actor_index)
{
    std::vector<ActorField> fields;
    auto txn = doc.begin();
    auto content = txn.array("content");
    if (actor_index < 0 || actor_index >= content.len()) return fields;

    wfcrdt::Map obj = content.get(actor_index).asMap();
    if (!obj.valid()) return fields;
    wfcrdt::Array items = obj.get("items").asArray();
    if (!items.valid()) return fields;

    const int n = items.len();
    fields.reserve(static_cast<size_t>(n));
    for (int i = 0; i < n; ++i) {
        wfcrdt::Map ch = items.get(i).asMap();
        if (!IsChunkMap(ch)) continue;
        // Skip the actor's own top-level NAME (it's the title, shown separately).
        if (ch.get("chunk_type").readString().value_or("") == "NAME") continue;
        ActorField f = FieldFromChunk(ch);
        f.child_index = i;   // Doc address (index into the OBJ's items) for write-back
        fields.push_back(std::move(f));
    }
    return fields;
}

namespace {

std::vector<std::string> SplitWS(const std::string& s)
{
    std::vector<std::string> out;
    std::size_t i = 0;
    while (i < s.size()) {
        while (i < s.size() && std::isspace(static_cast<unsigned char>(s[i]))) ++i;
        std::size_t j = i;
        while (j < s.size() && !std::isspace(static_cast<unsigned char>(s[j]))) ++j;
        if (j > i) out.emplace_back(s.substr(i, j - i));
        i = j;
    }
    return out;
}

// Overwrite a literal map's body, by kind (the write-side inverse of LiteralBody).
void SetLiteralBody(wfcrdt::Map& lit, const std::string& body)
{
    const std::string kind = lit.get("kind").readString().value_or("");
    if (kind == "str")          lit.insert("value", body.c_str());
    else if (kind == "num")     lit.insert("text",  body.c_str());
    else if (kind == "four_cc") lit.insert("id",    body.c_str());
}

// Distribute `new_text` across a leaf chunk's literal items (plan D6 N-rule):
// N==1 → whole text; N>1 → whitespace-split into N numeric tokens. Returns false
// on a token/count mismatch (leaves the leaf untouched rather than corrupt it).
bool SetLeafLiterals(wfcrdt::Array& items, const std::string& new_text)
{
    std::vector<int> lit_idx;
    const int n = items.len();
    for (int i = 0; i < n; ++i) { wfcrdt::Map m = items.get(i).asMap(); if (m.valid() && !IsChunkMap(m)) lit_idx.push_back(i); }
    const std::size_t N = lit_idx.size();
    if (N == 0) return false;
    if (N == 1) { wfcrdt::Map m = items.get(lit_idx[0]).asMap(); SetLiteralBody(m, new_text); return true; }
    const std::vector<std::string> toks = SplitWS(new_text);
    if (toks.size() != N) {
        std::fprintf(stderr, "wf-edit: WriteFieldLeaf: %zu literals != %zu tokens (\"%s\")\n",
                     N, toks.size(), new_text.c_str());
        return false;
    }
    for (std::size_t k = 0; k < N; ++k) { wfcrdt::Map m = items.get(lit_idx[k]).asMap(); SetLiteralBody(m, toks[k]); }
    return true;
}

}  // namespace

bool WriteFieldLeaf(wfcrdt::Doc& doc, int actor_index, int child_index,
                    const char* leaf_type, const std::string& new_text,
                    bool remote)
{
    auto txn = remote ? doc.beginRemote() : doc.begin();   // commits on scope exit
    auto content = txn.array("content");
    if (actor_index < 0 || actor_index >= content.len()) return false;

    wfcrdt::Map obj = content.get(actor_index).asMap();
    if (!obj.valid()) return false;
    wfcrdt::Array items = obj.get("items").asArray();
    if (!items.valid() || child_index < 0 || child_index >= items.len()) return false;

    wfcrdt::Map field = items.get(child_index).asMap();
    if (!field.valid()) return false;
    wfcrdt::Array fitems = field.get("items").asArray();
    if (!fitems.valid()) return false;

    // Bare-leaf field (its items are literals): leaf_type is moot — set them.
    bool has_sub = false;
    const int fn = fitems.len();
    for (int i = 0; i < fn; ++i) if (IsChunkMap(fitems.get(i).asMap())) { has_sub = true; break; }
    if (!has_sub) return SetLeafLiterals(fitems, new_text);

    const std::string want = leaf_type ? leaf_type : "";
    for (int i = 0; i < fn; ++i) {
        wfcrdt::Map sub = fitems.get(i).asMap();
        if (!IsChunkMap(sub)) continue;
        if (sub.get("chunk_type").readString().value_or("") == want) {
            wfcrdt::Array lits = sub.get("items").asArray();
            return lits.valid() && SetLeafLiterals(lits, new_text);
        }
    }
    return false;   // no such leaf — caller picks a leaf the field actually has
}

namespace {
// Deep-copy a Doc chunk map into a wfcrdt::Input so it can be re-pushed (the
// inverse of the readers) — used to duplicate an actor.
wfcrdt::Input DocChunkToInput(const wfcrdt::Map& chunk)
{
    wfcrdt::Input node = wfcrdt::Input::map();
    node.set("chunk_type", wfcrdt::Input::str(chunk.get("chunk_type").readString().value_or("")));
    wfcrdt::Input items = wfcrdt::Input::array();
    wfcrdt::Array its = chunk.get("items").asArray();
    if (its.valid()) {
        const int n = its.len();
        for (int i = 0; i < n; ++i) {
            wfcrdt::Map m = its.get(i).asMap();
            if (!m.valid()) continue;
            if (IsChunkMap(m)) { items.push(DocChunkToInput(m)); continue; }
            wfcrdt::Input lit = wfcrdt::Input::map();
            const std::string kind = m.get("kind").readString().value_or("");
            lit.set("kind", wfcrdt::Input::str(kind));
            if (kind == "str")          lit.set("value", wfcrdt::Input::str(m.get("value").readString().value_or("")));
            else if (kind == "num")     lit.set("text",  wfcrdt::Input::str(m.get("text").readString().value_or("")));
            else if (kind == "four_cc") lit.set("id",    wfcrdt::Input::str(m.get("id").readString().value_or("")));
            items.push(std::move(lit));
        }
    }
    node.set("items", std::move(items));
    return node;
}
}  // namespace

bool DeleteActor(wfcrdt::Doc& doc, int index)
{
    auto txn = doc.begin();
    auto content = txn.array("content");
    if (index < 0 || index >= content.len()) return false;
    content.remove(index);
    return true;
}

int DuplicateActor(wfcrdt::Doc& doc, int index)
{
    auto txn = doc.begin();
    auto content = txn.array("content");
    if (index < 0 || index >= content.len()) return -1;
    wfcrdt::Map src = content.get(index).asMap();
    if (!src.valid()) return -1;
    wfcrdt::Input clone = DocChunkToInput(src);
    // Stable identity for the bridge: new eid + source eid so remote peers can
    // spawn from the same template.
    const std::string src_eid = src.get("_eid").readString().value_or("");
    clone.set("_src_eid", wfcrdt::Input::str(src_eid));
    clone.set("_eid",     wfcrdt::Input::str(GenerateEid()));
    content.push(clone);
    return content.len() - 1;
}

namespace {
// ── AddActor helpers: build CRDT Input nodes from OAD defaults ────────────────

// Format a 16.16 fixed-point default as "%.17g(1.15.16)", with "." guaranteed.
static std::string FormatFx(long def)
{
    char buf[64];
    double v = static_cast<double>(def) / 65536.0;
    std::snprintf(buf, sizeof(buf), "%.17g", v);
    bool has_dot = false;
    for (const char* p = buf; *p; ++p) if (*p == '.') { has_dot = true; break; }
    std::string s = buf;
    if (!has_dot) s += ".0";
    s += "(1.15.16)";
    return s;
}

// Format an integer default with the iffcomp width suffix (l/w/y for 32/16/8).
static std::string FormatInt(long def, int button_type)
{
    char buf[32];
    if (button_type == BUTTON_INT8)       std::snprintf(buf, sizeof(buf), "%ldy", def);
    else if (button_type == BUTTON_INT16) std::snprintf(buf, sizeof(buf), "%ldw", def);
    else                                  std::snprintf(buf, sizeof(buf), "%ldl", def);
    return buf;
}

// Literal constructors
static wfcrdt::Input MkLitStr(const std::string& v)
{
    wfcrdt::Input m = wfcrdt::Input::map();
    m.set("kind", wfcrdt::Input::str("str"));
    m.set("value", wfcrdt::Input::str(v));
    return m;
}
static wfcrdt::Input MkLitNum(const std::string& t)
{
    wfcrdt::Input m = wfcrdt::Input::map();
    m.set("kind", wfcrdt::Input::str("num"));
    m.set("text", wfcrdt::Input::str(t));
    return m;
}

// Sub-chunk with a single literal: { chunk_type:ct, items:[lit] }
static wfcrdt::Input MkLeaf1(const char* ct, wfcrdt::Input lit)
{
    wfcrdt::Input arr = wfcrdt::Input::array();
    arr.push(std::move(lit));
    wfcrdt::Input c = wfcrdt::Input::map();
    c.set("chunk_type", wfcrdt::Input::str(ct));
    c.set("items", std::move(arr));
    return c;
}

static wfcrdt::Input MkName(const std::string& n)    { return MkLeaf1("NAME", MkLitStr(n)); }
static wfcrdt::Input MkDataStr(const std::string& v) { return MkLeaf1("DATA", MkLitStr(v)); }
static wfcrdt::Input MkDataNum(const std::string& t) { return MkLeaf1("DATA", MkLitNum(t)); }
static wfcrdt::Input MkStrSub(const std::string& v)  { return MkLeaf1("STR",  MkLitStr(v)); }

// DATA sub-chunk with N repeated num literals (VEC3 = 3, EULR = 3, BOX3 = 6).
static wfcrdt::Input MkDataNumN(int n, const char* t)
{
    wfcrdt::Input arr = wfcrdt::Input::array();
    for (int i = 0; i < n; ++i) arr.push(MkLitNum(t));
    wfcrdt::Input c = wfcrdt::Input::map();
    c.set("chunk_type", wfcrdt::Input::str("DATA"));
    c.set("items", std::move(arr));
    return c;
}

// Scaffold transform field: { 'ct' { 'NAME' name } { 'DATA' n×"0.0(1.15.16)" } }
static wfcrdt::Input MkTransform(const char* ct, const char* name, int n)
{
    wfcrdt::Input f = wfcrdt::Input::map();
    f.set("chunk_type", wfcrdt::Input::str(ct));
    wfcrdt::Input items = wfcrdt::Input::array();
    items.push(MkName(name));
    items.push(MkDataNumN(n, "0.0(1.15.16)"));
    f.set("items", std::move(items));
    return f;
}

// Convert an OAD entry to a field chunk Input. Returns nullopt for entries that
// produce no per-instance storage (GROUP/COMMONBLOCK/LEVELCONFLAG/XDATA/WAVEFORM).
static std::optional<wfcrdt::Input> OadEntryToFieldChunk(const OadEntry& e)
{
    const int bt = e.button_type;

    // Skip structural / non-stored entry types (mirrors oad_loader.rs `_ => {}`).
    if (bt == BUTTON_GROUP_START       || bt == BUTTON_GROUP_STOP  ||
        bt == BUTTON_PROPERTY_SHEET    || bt == BUTTON_XDATA       ||
        bt == BUTTON_WAVEFORM          || bt == BUTTON_EXTRACT_CAMERA ||
        bt == LEVELCONFLAG_COMMONBLOCK || bt == LEVELCONFLAG_ENDCOMMON ||
        bt == LEVELCONFLAG_NOINSTANCES || bt == LEVELCONFLAG_NOMESH ||
        bt == LEVELCONFLAG_SINGLEINSTANCE || bt == LEVELCONFLAG_TEMPLATE ||
        bt == LEVELCONFLAG_EXTRACTCAMERA  || bt == LEVELCONFLAG_EXTRACTCAMERANEW ||
        bt == LEVELCONFLAG_ROOM        || bt == LEVELCONFLAG_EXTRACTLIGHT ||
        bt == LEVELCONFLAG_SHORTCUT)
        return std::nullopt;

    if (e.show_as == SHOW_AS_HIDDEN) return std::nullopt;

    const bool is_enum = (e.show_as == SHOW_AS_DROPMENU     ||
                          e.show_as == SHOW_AS_RADIOBUTTONS ||
                          e.show_as == SHOW_AS_CHECKBOX     ||
                          e.show_as == SHOW_AS_COMBOBOX);

    wfcrdt::Input field = wfcrdt::Input::map();
    wfcrdt::Input items = wfcrdt::Input::array();
    items.push(MkName(e.name));

    if (bt == BUTTON_FIXED32 || bt == BUTTON_FIXED16) {
        field.set("chunk_type", wfcrdt::Input::str(bt == BUTTON_FIXED32 ? "FX32" : "FX16"));
        items.push(MkDataNum(FormatFx(e.def)));
    } else if (bt == BUTTON_INT32 || bt == BUTTON_INT16 || bt == BUTTON_INT8) {
        const char* ct = (bt == BUTTON_INT8)  ? "I8"  :
                         (bt == BUTTON_INT16) ? "I16" : "I32";
        field.set("chunk_type", wfcrdt::Input::str(ct));
        items.push(MkDataNum(FormatInt(e.def, bt)));
        if (is_enum) {
            const int idx = static_cast<int>(e.def);
            const std::string label =
                (idx >= 0 && idx < static_cast<int>(e.options.size()))
                ? e.options[idx] : std::to_string(e.def);
            items.push(MkStrSub(label));
        }
    } else if (bt == BUTTON_STRING) {
        field.set("chunk_type", wfcrdt::Input::str("STR"));
        items.push(MkDataStr(""));   // empty string default
    } else if (bt == BUTTON_FILENAME || bt == BUTTON_MESHNAME) {
        field.set("chunk_type", wfcrdt::Input::str("FILE"));
        items.push(MkStrSub(""));
    } else if (bt == BUTTON_OBJECT_REFERENCE || bt == BUTTON_CLASS_REFERENCE ||
               bt == BUTTON_CAMERA_REFERENCE || bt == BUTTON_LIGHT_REFERENCE) {
        field.set("chunk_type", wfcrdt::Input::str("STR"));
        items.push(MkStrSub(""));
    } else {
        return std::nullopt;   // unknown type — skip
    }

    field.set("items", std::move(items));
    return field;
}

}  // namespace (add-actor helpers)

}  // namespace wfedit

namespace wfedit {

int AddActor(wfcrdt::Doc& doc, const std::string& class_name)
{
    const std::vector<OadEntry>& oad = OadForClass(class_name);
    if (oad.empty()) return -1;

    auto txn = doc.begin();
    auto content = txn.array("content");
    const int actor_count = content.len();

    wfcrdt::Input obj = wfcrdt::Input::map();
    obj.set("chunk_type", wfcrdt::Input::str("OBJ"));
    wfcrdt::Input items = wfcrdt::Input::array();

    // 1. Instance name: { 'NAME' "<class>_<n+1>" }
    items.push(MkLeaf1("NAME", MkLitStr(class_name + "_" + std::to_string(actor_count + 1))));

    // 2. Transform scaffold (not OAD fields — standard per-object header)
    items.push(MkTransform("VEC3", "Position",            3));
    items.push(MkTransform("EULR", "Orientation",         3));
    items.push(MkTransform("BOX3", "Global Bounding Box", 6));

    // 3. Class Name STR field: { 'STR' { 'NAME' "Class Name" } { 'DATA' "class" } }
    {
        wfcrdt::Input f = wfcrdt::Input::map();
        f.set("chunk_type", wfcrdt::Input::str("STR"));
        wfcrdt::Input fi = wfcrdt::Input::array();
        fi.push(MkName("Class Name"));
        fi.push(MkDataStr(class_name));
        f.set("items", std::move(fi));
        items.push(std::move(f));
    }

    // 4. OAD CommonBlock fields (skip scaffold names already emitted above)
    static const char* kScaffold[] = {
        "Class Name", "Position", "Orientation", "Global Bounding Box"
    };
    for (const OadEntry& e : oad) {
        bool skip = false;
        for (const char* s : kScaffold)
            if (e.name == s) { skip = true; break; }
        if (skip) continue;
        if (auto f = OadEntryToFieldChunk(e); f) items.push(std::move(*f));
    }

    obj.set("items", std::move(items));
    obj.set("_eid",     wfcrdt::Input::str(GenerateEid()));
    obj.set("_src_eid", wfcrdt::Input::str(""));   // no template src — reload shows it
    content.push(obj);
    return content.len() - 1;
}

}  // namespace wfedit
