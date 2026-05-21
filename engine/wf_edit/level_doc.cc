//=============================================================================
// engine/wf_edit/level_doc.cc — see level_doc.h.
//=============================================================================
#include "level_doc.h"

#include "wfcrdt.hpp"
#include <nlohmann/json.hpp>

#include <unistd.h>

#include <array>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace wfedit {
namespace {

using json = nlohmann::json;

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
// A levtree Chunk is {"id","items":[Chunk|Literal]}; a Literal is
// {"kind":"str"|"num"|"four_cc", value/text/id}. The CRDT node is
//   Y.Map { chunk_type, (children: Y.Array<chunk>)  XOR  (text: "...") }
// — container if it has any sub-chunk, else a leaf whose text is the literal
// bodies joined by spaces (NAME→"House", VEC3→"0.5 1.0 2.0", …).
std::string LiteralText(const json& lit)
{
    const std::string kind = lit.value("kind", "");
    if (kind == "str")     return lit.value("value", "");
    if (kind == "num")     return lit.value("text", "");
    if (kind == "four_cc") return lit.value("id", "");
    return "";
}

bool IsChunk(const json& item)   { return item.is_object() && item.contains("id") && item.contains("items"); }
bool IsLiteral(const json& item) { return item.is_object() && item.contains("kind"); }

wfcrdt::Input BuildChunk(const json& chunk)
{
    wfcrdt::Input node = wfcrdt::Input::map();
    node.set("chunk_type", wfcrdt::Input::str(chunk.value("id", "")));

    const json& items = chunk["items"];
    bool has_subchunk = false;
    for (const auto& it : items) if (IsChunk(it)) { has_subchunk = true; break; }

    if (has_subchunk) {
        wfcrdt::Input children = wfcrdt::Input::array();
        for (const auto& it : items)
            if (IsChunk(it)) children.push(BuildChunk(it));
        node.set("children", std::move(children));
    } else {
        std::string text;
        for (const auto& it : items) {
            if (!IsLiteral(it)) continue;
            if (!text.empty()) text += ' ';
            text += LiteralText(it);
        }
        node.set("text", wfcrdt::Input::str(std::move(text)));
    }
    return node;
}

// ── read the NAME leaf out of a chunk map ────────────────────────────────────
std::string NameOf(const wfcrdt::Map& obj)
{
    // chunk_type fallback (for an OBJ with no NAME, or a COMMENT/odd node).
    std::string fallback = obj.get("chunk_type").readString().value_or("(chunk)");

    wfcrdt::Array children = obj.get("children").asArray();
    if (!children.valid()) return fallback;
    const int n = children.len();
    for (int i = 0; i < n; ++i) {
        wfcrdt::Map child = children.get(i).asMap();
        if (!child.valid()) continue;
        if (child.get("chunk_type").readString().value_or("") == "NAME") {
            auto t = child.get("text").readString();
            if (t && !t->empty()) return *t;
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

bool LoadLevelTreeIntoDoc(const std::string& lev_path, wfcrdt::Doc& doc,
                          std::string* out_parse_json)
{
    std::string raw;
    if (!RunLevtreeParse(lev_path, raw)) return false;
    if (out_parse_json) *out_parse_json = raw;   // retain the lossless JSON for save

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
    meta.insert("format_version", static_cast<long long>(1));

    // content = the top-level OBJ chunks, with the LVL wrapper dropped.
    auto content = txn.array("content");
    int objs = 0;
    for (const auto& item : root["items"]) {
        if (!IsChunk(item)) continue;          // skip stray literals at LVL level
        content.push(BuildChunk(item));
        ++objs;
    }
    std::printf("wf-edit: Y.Doc populated from %s — %d top-level chunks\n",
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
// A field chunk is `{ chunk_type, children:[ NAME-leaf, DATA-leaf, … ] }`.
// Pull the field name (NAME child's text) and value (everything else's text,
// space-joined — DATA, or a bare leaf, or multi-part).
ActorField FieldFromChunk(const wfcrdt::Map& chunk)
{
    ActorField f;
    f.chunk_type = chunk.get("chunk_type").readString().value_or("");
    f.name = f.chunk_type;   // fallback if no NAME sub-chunk

    wfcrdt::Array kids = chunk.get("children").asArray();
    if (!kids.valid()) {
        // Leaf chunk (text directly) — value is its text.
        f.value = chunk.get("text").readString().value_or("");
        return f;
    }
    const int n = kids.len();
    for (int i = 0; i < n; ++i) {
        wfcrdt::Map sub = kids.get(i).asMap();
        if (!sub.valid()) continue;
        const std::string sct = sub.get("chunk_type").readString().value_or("");
        const std::string txt = sub.get("text").readString().value_or("");
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
    wfcrdt::Array kids = obj.get("children").asArray();
    if (!kids.valid()) return fields;

    const int n = kids.len();
    fields.reserve(static_cast<size_t>(n));
    for (int i = 0; i < n; ++i) {
        wfcrdt::Map ch = kids.get(i).asMap();
        if (!ch.valid()) continue;
        // Skip the actor's own top-level NAME (it's the title, shown separately).
        if (ch.get("chunk_type").readString().value_or("") == "NAME") continue;
        ActorField f = FieldFromChunk(ch);
        f.child_index = i;   // Doc address for write-back (Phase 3)
        fields.push_back(std::move(f));
    }
    return fields;
}

bool WriteFieldLeaf(wfcrdt::Doc& doc, int actor_index, int child_index,
                    const char* leaf_type, const std::string& new_text)
{
    auto txn = doc.begin();   // commits on scope exit
    auto content = txn.array("content");
    if (actor_index < 0 || actor_index >= content.len()) return false;

    wfcrdt::Map obj = content.get(actor_index).asMap();
    if (!obj.valid()) return false;
    wfcrdt::Array kids = obj.get("children").asArray();
    if (!kids.valid() || child_index < 0 || child_index >= kids.len()) return false;

    wfcrdt::Map field = kids.get(child_index).asMap();
    if (!field.valid()) return false;

    wfcrdt::Array leaves = field.get("children").asArray();
    if (!leaves.valid()) {
        // Bare-leaf field (text directly): leaf_type is moot — set its text.
        field.insert("text", new_text.c_str());
        return true;
    }
    const std::string want = leaf_type ? leaf_type : "";
    const int n = leaves.len();
    for (int i = 0; i < n; ++i) {
        wfcrdt::Map leaf = leaves.get(i).asMap();
        if (!leaf.valid()) continue;
        if (leaf.get("chunk_type").readString().value_or("") == want) {
            leaf.insert("text", new_text.c_str());   // YMap insert overwrites
            return true;
        }
    }
    return false;   // no such leaf — caller picks a leaf the field actually has
}

}  // namespace wfedit
