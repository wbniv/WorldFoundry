//=============================================================================
// engine/wf_edit/level_save.cc — see level_save.h.
//=============================================================================
#include "level_save.h"
#include "level_doc.h"   // RunLevtreePrint

#include "wfcrdt.hpp"
#include <nlohmann/json.hpp>

#include <cctype>
#include <cstdio>
#include <string>
#include <vector>

namespace wfedit {
namespace {

using json = nlohmann::json;

// levtree parse JSON shapes (mirror level_doc): a chunk is {"id","items":[…]};
// a literal is {"kind":"str","value":…} or {"kind":"num","text":…}.
bool IsChunk(const json& it)   { return it.is_object() && it.contains("id") && it.contains("items"); }
bool IsLiteral(const json& it) { return it.is_object() && it.contains("kind"); }

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

// Overwrite a literal's value by kind (str→"value", num→"text"); other kinds
// (none expected) left untouched.
void SetLiteral(json& lit, const std::string& value)
{
    const std::string kind = lit.value("kind", "");
    if (kind == "str")      lit["value"] = value;
    else if (kind == "num") lit["text"]  = value;
}

// Distribute a leaf chunk's Doc `text` across its JSON literals (plan D3):
// N==1 → the whole text is the literal's value (handles strings with spaces);
// N>1 → whitespace-split into N numeric tokens (VEC3/BOX3 components, space-free).
void PatchLeafLiterals(json& items, const std::string& doc_text)
{
    std::vector<json*> lits;
    for (auto& it : items) if (IsLiteral(it)) lits.push_back(&it);
    const std::size_t N = lits.size();
    if (N == 0) return;
    if (N == 1) { SetLiteral(*lits[0], doc_text); return; }
    const std::vector<std::string> toks = SplitWS(doc_text);
    if (toks.size() != N) {
        std::fprintf(stderr, "wf-edit: save: %zu literals != %zu tokens (\"%s\") — leaf left unpatched\n",
                     N, toks.size(), doc_text.c_str());
        return;
    }
    for (std::size_t i = 0; i < N; ++i) SetLiteral(*lits[i], toks[i]);
}

// Patch one JSON chunk from its Doc chunk-map, in lockstep. A Doc chunk with
// `children` is a container (recurse into matching sub-chunks, in order); one
// with `text` is a leaf (overwrite its literals). BuildChunk set exactly one of
// the two, and edits never change structure, so the trees stay congruent.
void PatchChunk(json& json_chunk, const wfcrdt::Map& doc_map)
{
    if (!doc_map.valid() || !json_chunk.contains("items")) return;
    json& items = json_chunk["items"];

    wfcrdt::Array children = doc_map.get("children").asArray();
    if (children.valid()) {
        int j = 0;
        for (auto& it : items) {
            if (!IsChunk(it)) continue;            // literals in a container: untouched
            PatchChunk(it, children.get(j).asMap());
            ++j;
        }
    } else {
        PatchLeafLiterals(items, doc_map.get("text").readString().value_or(""));
    }
}

// Patch `parse_json` (the lossless levtree-parse JSON) with the Doc's current
// leaf values, preserving each literal's kind. The Doc dropped the LVL wrapper,
// so root's chunk-items map 1:1 to the Doc `content` array.
std::string PatchJsonWithDoc(const std::string& parse_json, wfcrdt::Doc& doc)
{
    json tree;
    try { tree = json::parse(parse_json); }
    catch (const std::exception& e) {
        std::fprintf(stderr, "wf-edit: save: re-parse of retained JSON failed: %s\n", e.what());
        return parse_json;
    }
    if (!tree.contains("root") || !IsChunk(tree["root"]) || !tree["root"].contains("items"))
        return parse_json;

    auto txn = doc.begin();
    auto content = txn.array("content");
    if (!content.valid()) return parse_json;

    int j = 0;
    for (auto& it : tree["root"]["items"]) {
        if (!IsChunk(it)) continue;
        PatchChunk(it, content.get(j).asMap());
        ++j;
    }
    return tree.dump();
}

}  // namespace

bool SaveDocToLev(wfcrdt::Doc& doc, const std::string& parse_json,
                  const std::string& out_path)
{
    if (parse_json.empty()) {
        std::fprintf(stderr, "wf-edit: save: no parse JSON retained (load it with the "
                             "out_parse_json arg)\n");
        return false;
    }

    const std::string patched = PatchJsonWithDoc(parse_json, doc);

    std::string lev;
    if (!RunLevtreePrint(patched, lev)) {
        std::fprintf(stderr, "wf-edit: save: levtree print failed\n");
        return false;
    }

    FILE* f = std::fopen(out_path.c_str(), "wb");
    if (!f) {
        std::fprintf(stderr, "wf-edit: save: cannot write %s\n", out_path.c_str());
        return false;
    }
    std::fwrite(lev.data(), 1, lev.size(), f);
    std::fclose(f);

    long lines = 0;
    for (char c : lev) if (c == '\n') ++lines;
    std::printf("wf-edit: saved %s (%ld lines)\n", out_path.c_str(), lines);
    return true;
}

}  // namespace wfedit
