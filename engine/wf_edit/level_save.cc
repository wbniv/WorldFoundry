//=============================================================================
// engine/wf_edit/level_save.cc — see level_save.h.
//=============================================================================
#include "level_save.h"
#include "level_doc.h"   // RunLevtreePrint

#include "wfcrdt.hpp"

#include <cstdio>
#include <string>

namespace wfedit {
namespace {

// Patch `parse_json` (the lossless levtree-parse JSON) with the Doc's current
// leaf values, preserving each literal's kind.
//
// M1: no edits applied — passthrough. M2 implements the lockstep walk that, for
// each leaf chunk, overwrites its literals from the Doc `text` (N==1 → whole
// text; N>1 → whitespace-split numeric tokens).
std::string PatchJsonWithDoc(const std::string& parse_json, wfcrdt::Doc& /*doc*/)
{
    return parse_json;
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
