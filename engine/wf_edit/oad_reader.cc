//=============================================================================
// engine/wf_edit/oad_reader.cc — see oad_reader.h.
//
// This is the ONE editor TU that pulls in the dumper's oad.hp (and its
// `<iostream>`/pigsys/`using namespace std` baggage). Everything downstream
// (property_panel.cc) sees only the clean POD `OadEntry` — no ImGui clash.
//=============================================================================
#include "oad_reader.h"

#include <fstream>
#include <sstream>

// The shared reader (factored from the oaddump tool; entries now exposed via
// the Entries()/Descriptor() accessors added for the editor).
#include "oad.hp"   // wftools/oaddump/oad.hp — QObjectAttributeData
#include <cpplib/stdstrm.hp>   // cstats / cdebug / cnull (dumper's debug streams)

namespace wfedit {
namespace {

// The shared reader logs every entry to cstats/cdebug (useful in the dumper,
// ~1.5k lines/class in the editor). Mute those two streams across a load and
// restore them after — real errors (cerror/cfatal) are left alone.
struct QuietDumperStreams {
    std::streambuf* saved_stats;
    std::streambuf* saved_debug;
    QuietDumperStreams() : saved_stats(cstats.rdbuf()), saved_debug(cdebug.rdbuf()) {
        cstats.rdbuf(cnull.rdbuf());
        cdebug.rdbuf(cnull.rdbuf());
    }
    ~QuietDumperStreams() { cstats.rdbuf(saved_stats); cdebug.rdbuf(saved_debug); }
};

// Split the OAD `string` field on '|' into enum option labels. Faithful: keeps
// the segment order; a lone trailing '|' (seen on some STRING defaults) yields
// a trailing empty, harmless since only enum widgets consult `options`.
std::vector<std::string> SplitOptions(const std::string& s)
{
    std::vector<std::string> out;
    if (s.empty()) return out;
    std::size_t start = 0;
    for (std::size_t i = 0; i <= s.size(); ++i) {
        if (i == s.size() || s[i] == '|') {
            out.emplace_back(s.substr(start, i - start));
            start = i + 1;
        }
    }
    // A string with no '|' is a single segment (the whole thing) — not an enum
    // list. Drop that case so callers can treat a >1 size as "has options".
    if (out.size() == 1) out.clear();
    return out;
}

}  // namespace

bool LoadOad(const std::string& oad_path, std::vector<OadEntry>& out)
{
    out.clear();

    std::ifstream in(oad_path, std::ios::binary);
    if (!in) return false;

    QObjectAttributeData oad;
    std::ostringstream err;
    {
        QuietDumperStreams quiet;
        if (!oad.Load(in, err))
            return false;
    }

    const auto& entries = oad.Entries();
    out.reserve(entries.size());
    for (const auto& e : entries) {
        const _typeDescriptor& d = e.Descriptor();
        OadEntry oe;
        oe.button_type = static_cast<int>(d.type);
        // Bound the name/option reads to their fixed buffers (defensive: the
        // on-disk strings should be NUL-terminated, but don't run off the end).
        oe.name = std::string(d.name, ::strnlen(d.name, sizeof(d.name)));
        oe.show_as = static_cast<int>(d.showAs);
        oe.min = static_cast<long>(d.min);
        oe.max = static_cast<long>(d.max);
        oe.def = static_cast<long>(d.def);
        oe.option_string = std::string(d.string, ::strnlen(d.string, sizeof(d.string)));
        oe.options = SplitOptions(oe.option_string);
        out.push_back(std::move(oe));
    }
    return true;
}

}  // namespace wfedit
