//=============================================================================
// engine/wf_edit/property_panel.cc — see property_panel.h.
//=============================================================================
#include "property_panel.h"
#include "oad_reader.h"

#include "imgui.h"

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

// ── read-only widget render (Phase 2: display state; Phase 3 makes editable) ──
namespace {

void DrawColor(const PropField& f)
{
    const long v = AsLong(f.data.empty() ? f.label : f.data);
    const ImVec4 col(((v >> 16) & 0xFF) / 255.0f, ((v >> 8) & 0xFF) / 255.0f,
                     (v & 0xFF) / 255.0f, 1.0f);
    ImGui::ColorButton("##sw", col, ImGuiColorEditFlags_NoTooltip, ImVec2(20, 20));
    ImGui::SameLine();
    ImGui::Text("#%06lX", v & 0xFFFFFF);
}

void DrawEnum(const PropField& f)
{
    // Current option = the Doc's STR label; fall back to data-as-index.
    int cur = -1;
    for (std::size_t k = 0; k < f.options.size(); ++k)
        if (f.options[k] == f.label) { cur = static_cast<int>(k); break; }
    if (cur < 0 && !f.data.empty()) {
        long idx = AsLong(f.data);
        if (idx >= 0 && idx < static_cast<long>(f.options.size())) cur = static_cast<int>(idx);
    }
    const char* cur_label = (cur >= 0) ? f.options[cur].c_str()
                                       : (f.label.empty() ? "(unset)" : f.label.c_str());

    ImGui::BeginDisabled(true);
    if (f.options.size() >= 1 && f.options.size() <= 4) {
        // ≤4 → button row (Blender refinement).
        for (std::size_t k = 0; k < f.options.size(); ++k) {
            if (k) ImGui::SameLine();
            const bool on = (static_cast<int>(k) == cur);
            if (on) ImGui::PushStyleColor(ImGuiCol_Button, ImGui::GetStyleColorVec4(ImGuiCol_ButtonActive));
            ImGui::SmallButton(f.options[k].c_str());
            if (on) ImGui::PopStyleColor();
        }
    } else if (f.options.size() >= 5) {
        // 5+ → compact preview combo (the 2-col grid is a Phase-3 edit affordance).
        ImGui::SetNextItemWidth(-FLT_MIN);
        if (ImGui::BeginCombo("##enum", cur_label)) {
            for (std::size_t k = 0; k < f.options.size(); ++k)
                ImGui::Selectable(f.options[k].c_str(), static_cast<int>(k) == cur);
            ImGui::EndCombo();
        }
    } else {
        ImGui::TextUnformatted(cur_label);   // matched enum but no option list
    }
    ImGui::EndDisabled();
}

void DrawComponents(const PropField& f, const char* const* labels, int n, const char* suffix)
{
    std::vector<float> v = Floats(f.data);
    ImGui::BeginDisabled(true);
    for (int i = 0; i < n; ++i) {
        float x = (i < static_cast<int>(v.size())) ? v[i] : 0.0f;
        ImGui::SetNextItemWidth(90);
        ImGui::InputFloat(labels[i], &x, 0.0f, 0.0f, "%.4f");
        if (i + 1 < n) ImGui::SameLine();
    }
    ImGui::EndDisabled();
    if (suffix && *suffix) { ImGui::SameLine(); ImGui::TextDisabled("%s", suffix); }
}

void DrawValueWidget(const PropField& f, int row)
{
    ImGui::PushID(row);
    ImGui::SetNextItemWidth(-FLT_MIN);
    switch (f.kind) {
        case FieldKind::Color:   DrawColor(f); break;
        case FieldKind::Enum:    DrawEnum(f);  break;
        case FieldKind::Boolean: {
            bool on = (f.label == "True") || (!f.data.empty() && AsLong(f.data) != 0);
            ImGui::BeginDisabled(true); ImGui::Checkbox("##b", &on); ImGui::EndDisabled();
            break;
        }
        case FieldKind::Mailbox: {
            ImGui::BeginDisabled(true);
            char buf[64]; std::snprintf(buf, sizeof(buf), "%s", f.data.empty() ? f.label.c_str() : f.data.c_str());
            ImGui::InputText("##mb", buf, sizeof(buf));
            ImGui::EndDisabled();
            break;
        }
        case FieldKind::Float: {
            std::vector<float> v = Floats(f.data.empty() ? f.label : f.data);
            float x = v.empty() ? 0.0f : v[0];
            ImGui::BeginDisabled(true);
            if (f.matched && (f.show_as == SHOW_AS_SLIDER) && f.max != f.min) {
                float lo = f.min / 65536.0f, hi = f.max / 65536.0f;
                ImGui::SliderFloat("##s", &x, lo, hi, "%.3f");
            } else {
                ImGui::InputFloat("##f", &x, 0.0f, 0.0f, "%.4f");
            }
            ImGui::EndDisabled();
            break;
        }
        case FieldKind::Int: {
            int x = static_cast<int>(AsLong(f.data.empty() ? f.label : f.data));
            ImGui::BeginDisabled(true); ImGui::InputInt("##i", &x, 0, 0); ImGui::EndDisabled();
            break;
        }
        case FieldKind::Vec3: {
            static const char* kXYZ[] = {"x", "y", "z"};
            DrawComponents(f, kXYZ, 3, nullptr); break;
        }
        case FieldKind::Euler: {
            static const char* kABC[] = {"a", "b", "c"};
            DrawComponents(f, kABC, 3, "rev"); break;
        }
        case FieldKind::Box3: {
            static const char* kMin[] = {"x", "y", "z"};
            static const char* kMax[] = {"X", "Y", "Z"};
            std::vector<float> v = Floats(f.data);
            PropField lo = f, hi = f;
            // first 3 components → min, last 3 → max.
            { std::string a, b; std::vector<float> all = v;
              for (int i = 0; i < 3 && i < (int)all.size(); ++i) { if(i)a+=' '; a+=std::to_string(all[i]); }
              for (int i = 3; i < 6 && i < (int)all.size(); ++i){ if(i>3)b+=' '; b+=std::to_string(all[i]); }
              lo.data = a; hi.data = b; }
            DrawComponents(lo, kMin, 3, "min"); DrawComponents(hi, kMax, 3, "max");
            break;
        }
        case FieldKind::FileRef: {
            ImGui::BeginDisabled(true);
            char buf[256]; std::snprintf(buf, sizeof(buf), "%s", f.label.c_str());
            ImGui::SetNextItemWidth(-60); ImGui::InputText("##file", buf, sizeof(buf));
            ImGui::SameLine(); ImGui::SmallButton("Browse…");
            ImGui::EndDisabled();
            break;
        }
        case FieldKind::ObjRef: {
            const std::string& tgt = !f.label.empty() ? f.label : f.data;
            if (tgt.empty()) ImGui::TextDisabled("(not set)");
            else { ImGui::TextUnformatted(tgt.c_str()); ImGui::SameLine(); ImGui::TextDisabled("⚠?"); }
            break;
        }
        case FieldKind::MultilineStr: {
            std::string s = !f.label.empty() ? f.label : f.value;
            ImGui::BeginDisabled(true);
            char buf[1024]; std::snprintf(buf, sizeof(buf), "%s", s.c_str());
            ImGui::InputTextMultiline("##ml", buf, sizeof(buf), ImVec2(-FLT_MIN, 48));
            ImGui::EndDisabled();
            break;
        }
        case FieldKind::Str: {
            std::string s = !f.label.empty() ? f.label : (!f.data.empty() ? f.data : f.value);
            ImGui::BeginDisabled(true);
            char buf[512]; std::snprintf(buf, sizeof(buf), "%s", s.c_str());
            ImGui::InputText("##s", buf, sizeof(buf));
            ImGui::EndDisabled();
            break;
        }
        case FieldKind::Raw:
        default:
            ImGui::TextWrapped("%s", f.value.empty() ? "(empty)" : f.value.c_str());
            break;
    }
    ImGui::PopID();
}

}  // namespace

void RenderProperties(const std::vector<PropField>& fields)
{
    if (!ImGui::BeginTable("props", 2,
            ImGuiTableFlags_Resizable | ImGuiTableFlags_RowBg |
            ImGuiTableFlags_BordersInnerV | ImGuiTableFlags_ScrollY))
        return;
    ImGui::TableSetupColumn("Field", ImGuiTableColumnFlags_WidthFixed, 150.0f);
    ImGui::TableSetupColumn("Value", ImGuiTableColumnFlags_WidthStretch);

    // Screenshot aid (env-gated, off by default): scroll the panel so a named
    // field is near the top — lets a headless capture frame a widget that would
    // otherwise be below the fold (e.g. the COLOR swatch ~field 48).
    static const char* s_scroll_to = std::getenv("WF_EDIT_SCROLL_TO");

    int row = 0;
    for (const auto& f : fields) {
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
        DrawValueWidget(f, row);
    }
    ImGui::EndTable();
}

}  // namespace wfedit
