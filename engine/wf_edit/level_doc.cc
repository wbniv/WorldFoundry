//=============================================================================
// engine/wf_edit/level_doc.cc — see level_doc.h.
//=============================================================================
#include "level_doc.h"

#include "wfcrdt.hpp"
#include <nlohmann/json.hpp>

#include <unistd.h>

#include <array>
#include <cctype>
#include <cstdio>
#include <cstdlib>
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

bool LoadLevelTreeIntoDoc(const std::string& lev_path, wfcrdt::Doc& doc)
{
    std::string raw;
    if (!RunLevtreeParse(lev_path, raw)) return false;

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

    // Derive a level name from the path's basename (drop dir + .lev).
    std::string level_name = lev_path;
    if (auto slash = level_name.find_last_of('/'); slash != std::string::npos)
        level_name.erase(0, slash + 1);
    if (auto dot = level_name.rfind(".lev"); dot != std::string::npos)
        level_name.erase(dot);

    auto txn = doc.begin();

    auto meta = txn.map("meta");
    meta.insert("level_name", level_name.c_str());
    meta.insert("format_version", static_cast<long long>(2));
    meta.insert("root_chunk_type", root.value("id", "LVL").c_str());  // for the save inverse

    // content = the top-level OBJ chunks, with the LVL wrapper dropped (its id is
    // kept in meta.root_chunk_type so save can reconstruct the exact tree).
    auto content = txn.array("content");
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
                lev_path.c_str(), objs);
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
                    const char* leaf_type, const std::string& new_text)
{
    auto txn = doc.begin();   // commits on scope exit
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

}  // namespace wfedit
