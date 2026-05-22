//=============================================================================
// engine/wf_edit/level_save.cc — see level_save.h.
//=============================================================================
#include "level_save.h"
#include "level_doc.h"   // RunLevtreePrint

#include "wfcrdt.hpp"
#include <nlohmann/json.hpp>

#include <cstdio>
#include <string>

namespace wfedit {
namespace {

using json = nlohmann::json;

// v2 schema (lossless): a chunk map carries `chunk_type`; a literal map carries
// `kind` (+ value/text/id). Doc→JSON is a verbatim copy back to levtree's shape.
bool IsChunkMap(const wfcrdt::Map& m)
{
    return m.valid() && m.get("chunk_type").readString().has_value();
}

json LiteralToJson(const wfcrdt::Map& lit)
{
    json j;
    const std::string kind = lit.get("kind").readString().value_or("");
    j["kind"] = kind;
    if (kind == "str")          j["value"] = lit.get("value").readString().value_or("");
    else if (kind == "num")     j["text"]  = lit.get("text").readString().value_or("");
    else if (kind == "four_cc") j["id"]    = lit.get("id").readString().value_or("");
    return j;
}

// chunk map → { "id": chunk_type, "items": [ chunk|literal … ] }, recursively.
json ChunkToJson(const wfcrdt::Map& chunk)
{
    json j;
    j["id"] = chunk.get("chunk_type").readString().value_or("");
    json items = json::array();
    wfcrdt::Array its = chunk.get("items").asArray();
    if (its.valid()) {
        const int n = its.len();
        for (int i = 0; i < n; ++i) {
            wfcrdt::Map m = its.get(i).asMap();
            if (!m.valid()) continue;
            items.push_back(IsChunkMap(m) ? ChunkToJson(m) : LiteralToJson(m));
        }
    }
    j["items"] = std::move(items);
    return j;
}

}  // namespace

bool SaveDocToLev(wfcrdt::Doc& doc, const std::string& out_path)
{
    // Reconstruct the levtree JSON straight from the Doc — no retained parse JSON
    // (the v2 schema is lossless). The LVL wrapper was lifted at load; rebuild it
    // from meta.root_chunk_type with content[] as its items.
    json tree;
    {
        auto txn = doc.begin();
        // Resolve both roots before the first read opens the write txn (wfcrdt
        // lazy-txn contract: root resolution can't run with a txn already open).
        auto meta = txn.map("meta");
        auto content = txn.array("content");

        const std::string root_type = meta.get("root_chunk_type").readString().value_or("LVL");
        if (!content.valid()) {
            std::fprintf(stderr, "wf-edit: save: Doc has no content array\n");
            return false;
        }
        json root;
        root["id"] = root_type;
        json items = json::array();
        const int n = content.len();
        for (int i = 0; i < n; ++i) {
            wfcrdt::Map m = content.get(i).asMap();
            if (m.valid()) items.push_back(ChunkToJson(m));
        }
        root["items"] = std::move(items);
        tree["root"] = std::move(root);
    }

    std::string lev;
    if (!RunLevtreePrint(tree.dump(), lev)) {
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
