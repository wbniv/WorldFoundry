//=============================================================================
// engine/wf_edit/property_panel.cc — see property_panel.h.
//=============================================================================
#include "property_panel.h"
#include "oad_reader.h"

#include "imgui.h"
#include "misc/cpp/imgui_stdlib.h"   // ImGui::InputText(label, std::string&) — editable strings

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

}  // namespace

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
    std::vector<std::string> oad_names(oad.size());
    for (std::size_t j = 0; j < oad.size(); ++j) oad_names[j] = oad[j].name;

    std::vector<int> match = oad.empty()
        ? std::vector<int>(doc_fields.size(), -1)
        : AlignByName(doc_names, oad_names);

    std::vector<PropField> out;
    out.reserve(doc_fields.size());
    for (std::size_t i = 0; i < doc_fields.size(); ++i) {
        const ActorField& df = doc_fields[i];
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
        }
        pf.kind = WidgetFor(pf.button_type, pf.show_as,
                            static_cast<int>(pf.options.size()), pf.chunk_type, pf.matched);
        out.push_back(std::move(pf));
    }

    // Env-gated alignment dump — kept until the plan completes (debug teardown
    // is all-at-once, not mid-flight): `WF_EDIT_OAD_DEBUG=1 wf-edit …`.
    if (const char* dbg = std::getenv("WF_EDIT_OAD_DEBUG"); dbg && *dbg) {
        int matched = 0;
        for (const auto& p : out) matched += p.matched;
        std::fprintf(stderr, "[oad] class=%s  oad_entries=%zu  doc_fields=%zu  matched=%d\n",
                     class_name.c_str(), oad.size(), doc_fields.size(), matched);
        for (std::size_t i = 0; i < out.size(); ++i)
            std::fprintf(stderr, "  %2zu  %-28s  doc=%-5s  %s  bt=%d showAs=%d opts=%zu\n",
                         i, out[i].name.c_str(), out[i].chunk_type.c_str(),
                         out[i].matched ? "OAD" : "-- ", out[i].button_type,
                         out[i].show_as, out[i].options.size());
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
        case FieldKind::MultilineStr:
            if (ImGui::InputTextMultiline("##ml", &f.label, ImVec2(-FLT_MIN, 48)))
                edited = Commit(doc, actor, f, nullptr, &f.label);
            break;
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

    // Screenshot aid (env-gated, off by default): scroll the panel so a named
    // field is near the top — lets a headless capture frame a widget that would
    // otherwise be below the fold (e.g. the COLOR swatch ~field 48).
    static const char* s_scroll_to = std::getenv("WF_EDIT_SCROLL_TO");

    bool any_edit = false;
    int row = 0;
    for (auto& f : fields) {
        ++row;
        if (f.kind == FieldKind::Skip) continue;

        // Section / group headers span both columns.
        if (f.kind == FieldKind::Section || f.kind == FieldKind::GroupStart) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            ImGui::SeparatorText(f.name.c_str());
            continue;
        }
        if (f.kind == FieldKind::GroupEnd) continue;

        ImGui::TableNextRow();
        ImGui::TableSetColumnIndex(0);
        ImGui::TextUnformatted(f.name.c_str());
        if (s_scroll_to && f.name == s_scroll_to) ImGui::SetScrollHereY(0.2f);
        if (ImGui::IsItemHovered()) {
            ImGui::SetTooltip("%s  •  %s%s", f.chunk_type.c_str(),
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
    ImGui::EndTable();
    return any_edit;
}

}  // namespace wfedit
