//=============================================================================
// engine/wf_edit/property_panel.cc — see property_panel.h.
//=============================================================================
#include "property_panel.h"
#include "oad_reader.h"

#include "imgui.h"
#include "imgui_internal.h"          // TablePushBackgroundChannel — group-box border across rows
#include "misc/cpp/imgui_stdlib.h"   // ImGui::InputText(label, std::string&) — editable strings
#include "imgui_markdown.h"          // ImGui::Markdown — Notes leaf rendering (matches chat sidebar)

#include <oas/oad.h>   // BUTTON_* / SHOW_AS_* dispatch codes (named, not magic)

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <string>
#include <unistd.h>
#include <vector>

namespace wfedit {
namespace {

// ── name normalization (for matching only) ───────────────────────────────────
// Trim outer whitespace and drop a trailing " (…)" annotation (e.g. "(S.W.F)")
// so an OAD name and its Doc counterpart compare equal. Case-insensitive.
std::string Normalize(const std::string& raw)
{
    std::string s = raw;
    if (auto p = s.find(" ("); p != std::string::npos) s.erase(p);
    std::size_t a = s.find_first_not_of(" \t");
    std::size_t b = s.find_last_not_of(" \t");
    s = (a == std::string::npos) ? "" : s.substr(a, b - a + 1);
    for (char& c : s) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return s;
}

// ── sequence alignment: Doc field names ↔ OAD entry names ─────────────────────
// LCS over the two ordered, normalized name-lists. Returns, per Doc field, the
// matched OAD entry index (or -1). The CommonBlock flyweight makes Doc order ==
// OAD order, so the LCS recovers long contiguous runs and naturally skips the
// per-instance prefix (Position/Orientation/GBB/Class Name — absent from the
// OAD) and absorbs duplicate names / a minor Script/Notes reorder.
std::vector<int> AlignByName(const std::vector<std::string>& doc,
                             const std::vector<std::string>& oad)
{
    const int n = static_cast<int>(doc.size());
    const int m = static_cast<int>(oad.size());
    std::vector<std::string> dn(n), on(m);
    for (int i = 0; i < n; ++i) dn[i] = Normalize(doc[i]);
    for (int j = 0; j < m; ++j) on[j] = Normalize(oad[j]);

    // dp[i][j] = LCS length of dn[i:] vs on[j:].
    std::vector<std::vector<int>> dp(n + 1, std::vector<int>(m + 1, 0));
    for (int i = n - 1; i >= 0; --i)
        for (int j = m - 1; j >= 0; --j)
            dp[i][j] = (dn[i] == on[j] && !dn[i].empty())
                           ? dp[i + 1][j + 1] + 1
                           : std::max(dp[i + 1][j], dp[i][j + 1]);

    std::vector<int> match(n, -1);
    for (int i = 0, j = 0; i < n && j < m;) {
        if (dn[i] == on[j] && !dn[i].empty()) { match[i] = j; ++i; ++j; }
        else if (dp[i + 1][j] >= dp[i][j + 1]) ++i;
        else ++j;
    }
    return match;
}

// ── .oad location + cache ─────────────────────────────────────────────────────
const std::vector<std::string>& OadSearchDirs()
{
    static std::vector<std::string> dirs = [] {
        std::vector<std::string> d;
        if (const char* env = std::getenv("WF_OAD_DIR"); env && *env) d.emplace_back(env);
        d.emplace_back("wfsource/source/oas");   // editor runs from repo root
        return d;
    }();
    return dirs;
}

// ── value parsing helpers ─────────────────────────────────────────────────────
std::vector<float> Floats(const std::string& s)
{
    std::vector<float> out;
    const char* p = s.c_str();
    char* end = nullptr;
    while (*p) {
        double v = std::strtod(p, &end);
        if (end == p) break;
        out.push_back(static_cast<float>(v));
        p = end;
    }
    return out;
}

long AsLong(const std::string& s) { return std::strtol(s.c_str(), nullptr, 0); }

// A PROPERTY_SHEET / GROUP_START / GROUP_STOP descriptor is a layout marker that
// carries no instance data, so no Doc field corresponds to it — it's interleaved
// by OAD position, never matched.
bool IsHeaderMarker(int bt)
{
    return bt == BUTTON_PROPERTY_SHEET || bt == BUTTON_GROUP_START || bt == BUTTON_GROUP_STOP;
}

// Entries the name-alignment LCS must never consume: the header markers above
// plus the common-block delimiters (their names — "movebloc", "LEVELCONFLAG_…" —
// are non-fields that could otherwise spuriously align).
bool IsUnmatchable(int bt)
{
    return IsHeaderMarker(bt)
        || bt == LEVELCONFLAG_COMMONBLOCK || bt == LEVELCONFLAG_ENDCOMMON;
}

const char* KindName(FieldKind k)
{
    switch (k) {
        case FieldKind::Int:          return "Int";
        case FieldKind::Float:        return "Float";
        case FieldKind::Boolean:      return "Bool";
        case FieldKind::Enum:         return "Enum";
        case FieldKind::Mailbox:      return "Mailbox";
        case FieldKind::Color:        return "Color";
        case FieldKind::Str:          return "Str";
        case FieldKind::MultilineStr: return "MultiStr";
        case FieldKind::ObjRef:       return "ObjRef";
        case FieldKind::FileRef:      return "FileRef";
        case FieldKind::Vec3:         return "Vec3";
        case FieldKind::Euler:        return "Euler";
        case FieldKind::Box3:         return "Box3";
        case FieldKind::Section:      return "Section";
        case FieldKind::GroupStart:   return "GroupStart";
        case FieldKind::GroupEnd:     return "GroupEnd";
        case FieldKind::Raw:          return "Raw";
        case FieldKind::Skip:         return "Skip";
    }
    return "?";
}

}  // namespace

// ── .oad location + cache (public: called by AddActor in level_doc.cc) ─────────
std::string FindOad(const std::string& class_name)
{
    if (class_name.empty()) return "";
    std::string lower = class_name;
    for (char& c : lower) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    for (const std::string& d : OadSearchDirs()) {
        std::string p = d + "/" + lower + ".oad";
        if (access(p.c_str(), R_OK) == 0) return p;
    }
    return "";
}

// Per-class cache: classes repeat across actors (snowgoons has 4 statplats), and
// .oad reads shouldn't recur on every selection. Keyed by class name; the empty
// vector is a cached "no .oad / load failed" so we don't retry each frame.
const std::vector<OadEntry>& OadForClass(const std::string& class_name)
{
    static std::map<std::string, std::vector<OadEntry>> cache;
    auto it = cache.find(class_name);
    if (it != cache.end()) return it->second;

    std::vector<OadEntry> entries;
    if (const std::string path = FindOad(class_name); !path.empty())
        LoadOad(path, entries);   // leaves entries empty on failure (still cached)
    return cache.emplace(class_name, std::move(entries)).first->second;
}

// ── (ButtonType × showAs) → FieldKind dispatch (design-doc table) ─────────────
FieldKind WidgetFor(int bt, int showAs, int option_count,
                    const std::string& chunk_type, bool matched)
{
    if (!matched) {
        // No OAD entry: dispatch on the Doc's IFF chunk type.
        if (chunk_type == "VEC3") return FieldKind::Vec3;
        if (chunk_type == "EULR") return FieldKind::Euler;
        if (chunk_type == "BOX3") return FieldKind::Box3;
        if (chunk_type == "FILE") return FieldKind::FileRef;
        if (chunk_type == "FX32" || chunk_type == "FX16") return FieldKind::Float;
        if (chunk_type == "I32" || chunk_type == "I16" || chunk_type == "I8") return FieldKind::Int;
        if (chunk_type == "STR") return FieldKind::Str;
        return FieldKind::Raw;
    }

    if (showAs == SHOW_AS_HIDDEN) return FieldKind::Skip;

    switch (bt) {
        case BUTTON_INT8: case BUTTON_INT16: case BUTTON_INT32:
            switch (showAs) {
                case SHOW_AS_COLOR:        return FieldKind::Color;
                case SHOW_AS_CHECKBOX:     return (option_count == 2 || option_count == 0)
                                                      ? FieldKind::Boolean : FieldKind::Enum;
                case SHOW_AS_MAILBOX:      return FieldKind::Mailbox;
                case SHOW_AS_DROPMENU:
                case SHOW_AS_RADIOBUTTONS:
                case SHOW_AS_COMBOBOX:     return FieldKind::Enum;
                default:                   return FieldKind::Int;
            }
        case BUTTON_FIXED16: case BUTTON_FIXED32:
            return FieldKind::Float;   // SLIDER vs N_A differ only in draw, not kind
        case BUTTON_STRING:
            return (showAs == SHOW_AS_TEXTEDITOR) ? FieldKind::MultilineStr : FieldKind::Str;
        case BUTTON_OBJECT_REFERENCE:
        case BUTTON_CAMERA_REFERENCE:
        case BUTTON_LIGHT_REFERENCE:
        case BUTTON_CLASS_REFERENCE:
            return FieldKind::ObjRef;
        case BUTTON_FILENAME:
        case BUTTON_MESHNAME:
            return FieldKind::FileRef;
        case BUTTON_XDATA:
        case BUTTON_WAVEFORM:
            return (showAs == SHOW_AS_TEXTEDITOR) ? FieldKind::MultilineStr : FieldKind::Skip;
        case BUTTON_PROPERTY_SHEET:
            return FieldKind::Section;
        case BUTTON_GROUP_START: return FieldKind::GroupStart;
        case BUTTON_GROUP_STOP:  return FieldKind::GroupEnd;
        // Common-block sentinels carry no instance data.
        case LEVELCONFLAG_COMMONBLOCK:
        case LEVELCONFLAG_ENDCOMMON:
            return FieldKind::Skip;
        // The pass-through level/engine flags surface as on/off toggles.
        case LEVELCONFLAG_NOINSTANCES: case LEVELCONFLAG_NOMESH:
        case LEVELCONFLAG_SINGLEINSTANCE: case LEVELCONFLAG_TEMPLATE:
        case LEVELCONFLAG_EXTRACTCAMERA: case LEVELCONFLAG_EXTRACTCAMERANEW:
        case LEVELCONFLAG_ROOM: case LEVELCONFLAG_EXTRACTLIGHT:
        case LEVELCONFLAG_SHORTCUT:
            return FieldKind::Boolean;
        default:
            return FieldKind::Raw;
    }
}

std::vector<PropField> ResolveProperties(const std::vector<ActorField>& doc_fields)
{
    // Class name from the OBJ's own "Class Name" field (self-describing Doc).
    std::string class_name;
    for (const auto& f : doc_fields)
        if (f.name == "Class Name") {
            class_name = !f.data.empty() ? f.data : (!f.value.empty() ? f.value : f.label);
            break;
        }

    const std::vector<OadEntry>& oad = OadForClass(class_name);

    std::vector<std::string> doc_names(doc_fields.size());
    for (std::size_t i = 0; i < doc_fields.size(); ++i) doc_names[i] = doc_fields[i].name;
    // Section/group/common-block markers get a blank name so AlignByName's LCS
    // can't match them to a Doc field (it requires a non-empty name). They reach
    // the panel only via the header interleave below, keyed by OAD position.
    std::vector<std::string> oad_names(oad.size());
    for (std::size_t j = 0; j < oad.size(); ++j)
        oad_names[j] = IsUnmatchable(oad[j].button_type) ? std::string() : oad[j].name;

    std::vector<int> match = oad.empty()
        ? std::vector<int>(doc_fields.size(), -1)
        : AlignByName(doc_names, oad_names);

    // Synthesise a header PropField from a section/group marker. The title comes
    // from `name` — for GROUP_START/STOP the OAD's displayName slot is junk
    // ("displayName"), so it must NOT be used here.
    auto make_header = [](const OadEntry& e) {
        PropField h;
        h.name = e.name;
        h.button_type = e.button_type;
        h.default_open = e.def;   // PROPERTY_SHEET: `active` arg → !=0 defaults the rollout open
        switch (e.button_type) {
            case BUTTON_PROPERTY_SHEET: h.kind = FieldKind::Section;    break;
            case BUTTON_GROUP_START:    h.kind = FieldKind::GroupStart; break;
            case BUTTON_GROUP_STOP:     h.kind = FieldKind::GroupEnd;   break;
            default:                    h.kind = FieldKind::Skip;       break;
        }
        return h;
    };

    std::vector<PropField> out;
    out.reserve(doc_fields.size() + oad.size());
    std::vector<PropField> pending;   // headers buffered, flushed before the next real field
    int last_oad = -1;                // highest OAD index whose headers we've already buffered

    for (std::size_t i = 0; i < doc_fields.size(); ++i) {
        const ActorField& df = doc_fields[i];

        // Buffer any section/group markers between the previous matched OAD entry
        // and this field's match, preserving OAD (== authoring) order.
        if (match[i] >= 0) {
            for (int k = last_oad + 1; k < match[i]; ++k)
                if (IsHeaderMarker(oad[k].button_type))
                    pending.push_back(make_header(oad[k]));
            last_oad = match[i];
        }

        PropField pf;
        pf.name = df.name;
        pf.chunk_type = df.chunk_type;
        pf.data = df.data;
        pf.label = df.label;
        pf.value = df.value;
        pf.child_index = df.child_index;

        if (match[i] >= 0) {
            const OadEntry& e = oad[match[i]];
            pf.matched = true;
            pf.button_type = e.button_type;
            pf.show_as = e.show_as;
            pf.min = e.min;
            pf.max = e.max;
            pf.options = e.options;
            pf.display_label = e.display_name;   // short label; render falls back to name if empty
        }
        pf.kind = WidgetFor(pf.button_type, pf.show_as,
                            static_cast<int>(pf.options.size()), pf.chunk_type, pf.matched);

        // Flush buffered headers immediately before the field they introduce —
        // a header with no following field (the common-block tail) never flushes
        // and is silently dropped, so the panel shows no empty sections.
        for (auto& h : pending) out.push_back(std::move(h));
        pending.clear();
        out.push_back(std::move(pf));
    }
    // Any `pending` left here are trailing empty sections — deliberately dropped.

    // Env-gated alignment dump — kept until the plan completes (debug teardown
    // is all-at-once, not mid-flight): `WF_EDIT_OAD_DEBUG=1 wf-edit …`.
    if (const char* dbg = std::getenv("WF_EDIT_OAD_DEBUG"); dbg && *dbg) {
        int matched = 0;
        for (const auto& p : out) matched += p.matched;
        std::fprintf(stderr, "[oad] class=%s  oad_entries=%zu  doc_fields=%zu  rows=%zu  matched=%d\n",
                     class_name.c_str(), oad.size(), doc_fields.size(), out.size(), matched);
        for (std::size_t i = 0; i < out.size(); ++i) {
            const PropField& p = out[i];
            const bool header = p.kind == FieldKind::Section ||
                                p.kind == FieldKind::GroupStart || p.kind == FieldKind::GroupEnd;
            if (header) {
                std::fprintf(stderr, "  %2zu  ── %-10s %s\n", i, KindName(p.kind), p.name.c_str());
                continue;
            }
            std::fprintf(stderr, "  %2zu  %-28s  label=%-22s  doc=%-5s  %s  %-8s bt=%d showAs=%d\n",
                         i, p.name.c_str(),
                         (p.display_label.empty() ? p.name : p.display_label).c_str(),
                         p.chunk_type.c_str(), p.matched ? "OAD" : "-- ",
                         KindName(p.kind), p.button_type, p.show_as);
        }
    }
    return out;
}

// ── editable widget render (Phase 3): edits commit to the Doc leaf ────────────
namespace {

// Reformat a number-token, preserving its original spelling decorations so the
// edit survives the levtree/levcomp round-trip: a fixed-point token keeps its
// "(1.15.16)" suffix, a long keeps its trailing 'l'. `orig` is the existing
// Doc text for that component; `num` is the new value already formatted.
std::string RespellNumber(const std::string& orig, const std::string& num)
{
    if (auto p = orig.find('('); p != std::string::npos) return num + orig.substr(p);
    if (!orig.empty() && (orig.back() == 'l' || orig.back() == 'L')) return num + "l";
    return num;
}

std::vector<std::string> SplitWS(const std::string& s)
{
    std::vector<std::string> out;
    std::size_t i = 0;
    while (i < s.size()) {
        while (i < s.size() && std::isspace((unsigned char)s[i])) ++i;
        std::size_t j = i;
        while (j < s.size() && !std::isspace((unsigned char)s[j])) ++j;
        if (j > i) out.emplace_back(s.substr(i, j - i));
        i = j;
    }
    return out;
}

std::string FmtFloat(float v) { char b[32]; std::snprintf(b, sizeof b, "%.6f", v); return b; }
std::string FmtInt(long v)    { char b[32]; std::snprintf(b, sizeof b, "%ld", v);  return b; }

// Re-spell an n-component DATA string from new float values, keeping each
// component's original suffix (VEC3/EULR/BOX3/scalar float).
std::string RespellComponents(const std::string& orig_data, const float* vals, int n)
{
    std::vector<std::string> toks = SplitWS(orig_data);
    std::string out;
    for (int i = 0; i < n; ++i) {
        const std::string& o = (i < (int)toks.size()) ? toks[i] : std::string();
        if (i) out += ' ';
        out += RespellNumber(o, FmtFloat(vals[i]));
    }
    return out;
}

// Commit edited DATA and/or STR leaves for `f` and mirror them into the field
// for immediate display (next selection re-reads from the Doc anyway). Returns
// true if any leaf was written.
bool Commit(wfcrdt::Doc& doc, int actor, PropField& f,
            const std::string* data_text, const std::string* str_text)
{
    bool ok = false;
    if (data_text && WriteFieldLeaf(doc, actor, f.child_index, "DATA", *data_text)) {
        f.data = *data_text; ok = true;
    }
    if (str_text && WriteFieldLeaf(doc, actor, f.child_index, "STR", *str_text)) {
        f.label = *str_text; ok = true;
    }
    return ok;
}

int EnumCurrent(const PropField& f)
{
    for (std::size_t k = 0; k < f.options.size(); ++k)
        if (f.options[k] == f.label) return (int)k;
    if (!f.data.empty()) {
        long idx = AsLong(f.data);
        if (idx >= 0 && idx < (long)f.options.size()) return (int)idx;
    }
    return -1;
}

// n editable float components → DATA leaf (revolutions for EULR per WF
// convention; the .lev already stores revolutions, so no conversion needed).
bool DrawComponents(wfcrdt::Doc& doc, int actor, PropField& f,
                    const char* const* labels, int n, const char* suffix)
{
    std::vector<float> v = Floats(f.data);
    v.resize(n, 0.0f);
    bool changed = false;
    for (int i = 0; i < n; ++i) {
        ImGui::SetNextItemWidth(80);
        if (ImGui::InputFloat(labels[i], &v[i], 0.0f, 0.0f, "%.4f",
                              ImGuiInputTextFlags_EnterReturnsTrue))
            changed = true;
        if (i + 1 < n) ImGui::SameLine();
    }
    if (suffix && *suffix) { ImGui::SameLine(); ImGui::TextDisabled("%s", suffix); }
    if (changed) { std::string d = RespellComponents(f.data, v.data(), n); return Commit(doc, actor, f, &d, nullptr); }
    return false;
}

// ── Notes Markdown rendering (editor-only) ────────────────────────────────────
// The "Notes" leaf renders as Markdown when idle (matching the chat sidebar in
// main.cc) and falls back to the InputTextMultiline edit box on click. Only the
// Notes field — every other MultilineStr field (XDATA/WAVEFORM Forth scripts)
// keeps the plain box. Default config = inert links + default fonts, exactly
// like chat's s_md; the wire format stays plaintext (render is display-time).
static ImGui::MarkdownConfig s_notes_md;
// Which Notes field (actor index + child_index) is in edit mode; -1/-1 = none.
static int  s_notes_edit_actor    = -1;
static int  s_notes_edit_child    = -1;
static bool s_notes_focus_pending = false;   // grab keyboard focus the first edit frame only

// Returns true if this field committed an edit to the Doc this frame.
bool DrawValueWidget(wfcrdt::Doc& doc, int actor, PropField& f, int row)
{
    ImGui::PushID(row);
    ImGui::SetNextItemWidth(-FLT_MIN);
    bool edited = false;
    switch (f.kind) {
        case FieldKind::Color: {
            long v = AsLong(f.data.empty() ? f.label : f.data);
            float c[3] = { ((v >> 16) & 0xFF) / 255.0f, ((v >> 8) & 0xFF) / 255.0f, (v & 0xFF) / 255.0f };
            if (ImGui::ColorEdit3("##col", c, ImGuiColorEditFlags_NoInputs | ImGuiColorEditFlags_NoLabel)) {
                long packed = ((long)(c[0] * 255 + 0.5f) << 16) | ((long)(c[1] * 255 + 0.5f) << 8) | (long)(c[2] * 255 + 0.5f);
                std::string d = RespellNumber(f.data, FmtInt(packed));
                edited = Commit(doc, actor, f, &d, nullptr);
            }
            ImGui::SameLine(); ImGui::Text("#%06lX", v & 0xFFFFFF);
            break;
        }
        case FieldKind::Enum: {
            int cur = EnumCurrent(f);
            const char* cur_label = (cur >= 0) ? f.options[cur].c_str()
                                               : (f.label.empty() ? "(unset)" : f.label.c_str());
            if (ImGui::BeginCombo("##enum", cur_label)) {
                for (std::size_t k = 0; k < f.options.size(); ++k) {
                    if (ImGui::Selectable(f.options[k].c_str(), (int)k == cur) && (int)k != cur) {
                        std::string label = f.options[k];
                        std::string idx = RespellNumber(f.data, FmtInt((long)k));
                        // Enum value = STR label always; DATA index too when present.
                        edited = Commit(doc, actor, f, f.data.empty() ? nullptr : &idx, &label);
                    }
                }
                ImGui::EndCombo();
            }
            break;
        }
        case FieldKind::Boolean: {
            bool on = (f.label == "True") || (!f.data.empty() && AsLong(f.data) != 0);
            if (ImGui::Checkbox("##b", &on)) {
                std::string d = RespellNumber(f.data, FmtInt(on ? 1 : 0));
                std::string s = on ? "True" : "False";
                edited = Commit(doc, actor, f, f.data.empty() ? nullptr : &d, &s);
            }
            break;
        }
        case FieldKind::Int:
        case FieldKind::Mailbox: {
            // Mailbox (showAs=MAILBOX) would gain an INDEXOF_*/MB_* autocomplete
            // combo from mailbox.inc; no snowgoons field uses it, so it shares the
            // int spinner for now (TODO: mailbox.inc combo when a level needs it).
            int x = (int)AsLong(f.data.empty() ? f.label : f.data);
            if (ImGui::InputInt("##i", &x, 0, 0, ImGuiInputTextFlags_EnterReturnsTrue)) {
                if (f.matched && f.max != f.min) x = std::max((int)f.min, std::min((int)f.max, x));
                std::string d = RespellNumber(f.data, FmtInt(x));
                std::string s = FmtInt(x);
                edited = Commit(doc, actor, f, f.data.empty() ? nullptr : &d,
                                f.label.empty() ? nullptr : &s);
            }
            break;
        }
        case FieldKind::Float: {
            std::vector<float> v = Floats(f.data.empty() ? f.label : f.data);
            float x = v.empty() ? 0.0f : v[0];
            bool ch;
            if (f.matched && f.show_as == SHOW_AS_SLIDER && f.max != f.min)
                ch = ImGui::SliderFloat("##s", &x, f.min / 65536.0f, f.max / 65536.0f, "%.3f");
            else
                ch = ImGui::InputFloat("##f", &x, 0.0f, 0.0f, "%.4f", ImGuiInputTextFlags_EnterReturnsTrue);
            if (ch) {
                if (f.matched && f.max != f.min) {
                    float lo = f.min / 65536.0f, hi = f.max / 65536.0f;
                    x = std::max(lo, std::min(hi, x));
                }
                std::string d = RespellNumber(f.data, FmtFloat(x));
                std::string s = FmtFloat(x);
                edited = Commit(doc, actor, f, &d, f.label.empty() ? nullptr : &s);
            }
            break;
        }
        case FieldKind::Vec3:  { static const char* k[] = {"x","y","z"}; edited = DrawComponents(doc, actor, f, k, 3, nullptr); break; }
        case FieldKind::Euler: { static const char* k[] = {"a","b","c"}; edited = DrawComponents(doc, actor, f, k, 3, "rev"); break; }
        case FieldKind::Box3:  { static const char* k[] = {"x","y","z","X","Y","Z"}; edited = DrawComponents(doc, actor, f, k, 6, nullptr); break; }
        case FieldKind::FileRef: {
            ImGui::SetNextItemWidth(-60);
            if (ImGui::InputText("##file", &f.label, ImGuiInputTextFlags_EnterReturnsTrue))
                edited = Commit(doc, actor, f, nullptr, &f.label);
            ImGui::SameLine(); ImGui::BeginDisabled(true); ImGui::SmallButton("Browse…"); ImGui::EndDisabled();
            break;
        }
        case FieldKind::ObjRef: {
            if (ImGui::InputTextWithHint("##obj", "(not set)", &f.label, ImGuiInputTextFlags_EnterReturnsTrue))
                edited = Commit(doc, actor, f, nullptr, &f.label);
            break;
        }
        case FieldKind::MultilineStr: {
            // Gate on the *display* name: a real Notes field's identity name is
            // "Cave Logic Studios Notes|" while its OAD display name is "Notes",
            // so match display_label (and name, defensively). This also keeps the
            // Forth Script leaf (display "Script", also TEXTEDITOR) plain.
            // DORMANT: the shipped .oad emits Notes as BUTTON_XDATA + SHOW_AS_N_A
            // (→ FieldKind::Skip), so Notes isn't drawn yet; this path lights up
            // once the OAD carries SHOW_AS_TEXTEDITOR (see TODO: OAS codegen).
            const bool is_notes = Normalize(f.display_label) == "notes" ||
                                  Normalize(f.name) == "notes";
            const bool editing  = is_notes &&
                                  s_notes_edit_actor == actor &&
                                  s_notes_edit_child == f.child_index;
            if (is_notes && !editing) {
                // Idle: render the STR body as Markdown in one group so the
                // variable-height block has a single clickable bounding box.
                ImGui::BeginGroup();
                if (f.label.empty())
                    ImGui::TextDisabled("(click to add notes)");
                else
                    ImGui::Markdown(f.label.c_str(), f.label.size(), s_notes_md);
                ImGui::EndGroup();
                if (ImGui::IsItemHovered()) ImGui::SetTooltip("Click to edit (Markdown)");
                if (ImGui::IsItemClicked()) {
                    s_notes_edit_actor    = actor;
                    s_notes_edit_child    = f.child_index;
                    s_notes_focus_pending = true;
                }
                break;
            }
            // Edit box: Notes in edit mode, or any non-Notes multiline field.
            if (editing && s_notes_focus_pending) {
                ImGui::SetKeyboardFocusHere();   // first edit frame only — else focus can never leave
                s_notes_focus_pending = false;
            }
            if (ImGui::InputTextMultiline("##ml", &f.label, ImVec2(-FLT_MIN, 48)))
                edited = Commit(doc, actor, f, nullptr, &f.label);
            if (editing && ImGui::IsItemDeactivated()) {   // focus left → back to Markdown next frame
                s_notes_edit_actor = -1;
                s_notes_edit_child = -1;
            }
            break;
        }
        case FieldKind::Str:
            if (ImGui::InputText("##s", &f.label, ImGuiInputTextFlags_EnterReturnsTrue))
                edited = Commit(doc, actor, f, nullptr, &f.label);
            break;
        case FieldKind::Raw:
        default:
            ImGui::TextWrapped("%s", f.value.empty() ? "(empty)" : f.value.c_str());
            break;
    }
    ImGui::PopID();
    return edited;
}

}  // namespace

bool RenderProperties(wfcrdt::Doc& doc, int actor_index, std::vector<PropField>& fields,
                      std::vector<int>* committed)
{
    if (!ImGui::BeginTable("props", 2,
            ImGuiTableFlags_Resizable | ImGuiTableFlags_RowBg |
            ImGuiTableFlags_BordersInnerV | ImGuiTableFlags_ScrollY))
        return false;
    ImGui::TableSetupColumn("Field", ImGuiTableColumnFlags_WidthFixed, 150.0f);
    ImGui::TableSetupColumn("Value", ImGuiTableColumnFlags_WidthStretch);

    // Reset Notes edit-mode when the selected actor changes, so a lingering
    // edit slot for a no-longer-shown actor can't resurface as an edit box.
    static int s_last_actor = -1;
    if (actor_index != s_last_actor) {
        s_last_actor          = actor_index;
        s_notes_edit_actor    = -1;
        s_notes_edit_child    = -1;
        s_notes_focus_pending = false;
    }

    // Screenshot aid (env-gated, off by default): scroll the panel so a named
    // field is near the top — lets a headless capture frame a widget that would
    // otherwise be below the fold (e.g. the COLOR swatch ~field 48).
    static const char* s_scroll_to = std::getenv("WF_EDIT_SCROLL_TO");

    // OAS layout markers (faithful to the 3ds Max OAD UI — propshet.cc / group.cc):
    //  • PROPERTY_SHEET (FieldKind::Section) → a collapsible rollout; its default
    //    open/closed is the OAD `def` (the macro's `active` arg), carried in
    //    PropField::default_open via ResolveProperties::make_header.
    //  • GROUP_START..GROUP_STOP → a captioned border box drawn *around* its fields.
    // Authoring UX forbids nesting (no sheet-in-sheet, no group-in-group), so a
    // single `section_open` bool and a depth-≤1 box stack suffice.
    ImGui::PushID(actor_index);           // per-actor: collapse + widget state is per actor
    bool section_open = true;             // before the first sheet, everything is visible
    struct GroupBox { float x0, y0; };    // a GROUP_START's top-left, drawn as a rect at GROUP_STOP
    std::vector<GroupBox> group_boxes;    // open group frames (≤1 deep)

    bool any_edit = false;
    int row = 0;
    for (auto& f : fields) {
        ++row;                            // ALWAYS advance — keeps PushID(row) stable across collapse

        // PROPERTY_SHEET → collapsible header spanning both columns. A new sheet
        // implicitly closes the previous one (PROPERTY_SHEET_FOOTER emits no record).
        if (f.kind == FieldKind::Section) {
            group_boxes.clear();          // a new sheet ends any still-open group
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            ImGui::PushID(row);
            ImGuiTreeNodeFlags flags = ImGuiTreeNodeFlags_SpanAllColumns;
            if (f.default_open != 0) flags |= ImGuiTreeNodeFlags_DefaultOpen;
            section_open = ImGui::CollapsingHeader(f.name.c_str(), flags);
            ImGui::PopID();
            continue;
        }

        if (!section_open) continue;      // collapsed sheet hides its fields, group captions + boxes
        if (f.kind == FieldKind::Skip) continue;

        // GROUP_START → caption + capture the box's top-left; box drawn at GROUP_STOP.
        if (f.kind == FieldKind::GroupStart) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            const ImVec2 p = ImGui::GetCursorScreenPos();
            ImGui::TextUnformatted(f.name.c_str());   // etched-frame caption, top-left
            group_boxes.push_back({ p.x, p.y });
            continue;
        }
        // GROUP_STOP → close the etched frame: a border rect from the captured top
        // down to the current row, drawn in the table's background channel so it
        // frames the rows instead of being clipped to a single cell.
        if (f.kind == FieldKind::GroupEnd) {
            if (!group_boxes.empty()) {
                const GroupBox g = group_boxes.back();
                group_boxes.pop_back();
                const float y1 = ImGui::GetCursorScreenPos().y;
                const float x1 = ImGui::GetWindowPos().x + ImGui::GetWindowContentRegionMax().x;
                ImGui::TablePushBackgroundChannel();
                ImGui::GetWindowDrawList()->AddRect(ImVec2(g.x0 - 2.0f, g.y0 - 2.0f),
                                                    ImVec2(x1, y1),
                                                    ImGui::GetColorU32(ImGuiCol_Border), 3.0f);
                ImGui::TablePopBackgroundChannel();
            }
            continue;
        }

        ImGui::TableNextRow();
        ImGui::TableSetColumnIndex(0);
        // Compact, Max-faithful label: the short OAD displayName, full unique name
        // on hover. `name` stays the identity (scroll target, bridge key).
        ImGui::TextUnformatted(f.display_label.empty() ? f.name.c_str() : f.display_label.c_str());
        if (s_scroll_to && f.name == s_scroll_to) ImGui::SetScrollHereY(0.2f);
        if (ImGui::IsItemHovered()) {
            ImGui::SetTooltip("%s  •  %s  •  %s%s", f.name.c_str(), f.chunk_type.c_str(),
                              f.matched ? "OAD" : "no OAD match",
                              f.matched ? "" : " (chunk-type fallback)");
        }
        ImGui::TableSetColumnIndex(1);
        if (f.child_index >= 0) {
            const bool edited = DrawValueWidget(doc, actor_index, f, row);
            if (edited && committed) committed->push_back(static_cast<int>(&f - fields.data()));
            any_edit |= edited;
        } else
            ImGui::TextWrapped("%s", f.value.empty() ? "(empty)" : f.value.c_str());
    }
    ImGui::PopID();   // balances PushID(actor_index)
    ImGui::EndTable();
    return any_edit;
}

}  // namespace wfedit
