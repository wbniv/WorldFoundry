// engine/wf_edit/collab_panel.cc — ImGui "Collaborators" panel: video
// thumbnails, audio level meters, mute/camera controls.

#include "collab_panel.h"
#include "collab_session.h"
#include "voice_track.h"
#include "video_track.h"

#include "imgui.h"

#include <cstdio>
#include <cmath>

namespace wfedit {

// Draw a small colored initials avatar (for when no video frame is available).
static void DrawInitialsAvatar(const std::string& display_name, float size)
{
    ImVec2 pos = ImGui::GetCursorScreenPos();
    ImDrawList* dl = ImGui::GetWindowDrawList();

    // Hash the name to a hue.
    uint32_t h = 0;
    for (char c : display_name) h = h * 31 + static_cast<unsigned char>(c);
    float hue = static_cast<float>(h % 360) / 360.f;

    float r, g, b;
    ImGui::ColorConvertHSVtoRGB(hue, 0.7f, 0.8f, r, g, b);
    dl->AddRectFilled(pos, { pos.x + size, pos.y + size },
                      IM_COL32(static_cast<int>(r * 255), static_cast<int>(g * 255),
                               static_cast<int>(b * 255), 255));

    // Draw initials.
    char initials[3] = { ' ', ' ', '\0' };
    bool got_first = false;
    for (char c : display_name) {
        if (c == ' ') { got_first = false; continue; }
        if (!got_first) { initials[0] = c; got_first = true; }
        else            { initials[1] = c; break; }
    }
    initials[1] = '\0';  // show one initial only (font may not render second)
    ImVec2 ts = ImGui::CalcTextSize(initials);
    dl->AddText({ pos.x + (size - ts.x) * 0.5f,
                  pos.y + (size - ts.y) * 0.5f }, 0xFFFFFFFF, initials);

    ImGui::Dummy({ size, size });
}

void RenderCollabPanel(bool& show_collab,
                       CollabSession& session,
                       VoiceChat&     voice,
                       VideoChat&     video,
                       const std::string& room_id,
                       bool           relay_connected)
{
    if (!show_collab) return;

    ImGui::SetNextWindowSizeConstraints({ 280, 180 }, { 1000, 800 });
    if (!ImGui::Begin("Collaborators", &show_collab)) {
        ImGui::End();
        return;
    }

    // Room ID / invite line.
    ImGui::TextDisabled("Room: %s", room_id.empty() ? "(none)" : room_id.c_str());
    // Relay socket status. A dropped connection now auto-reconnects in the
    // background (ServiceRelayReconnect), and `relay_connected` reflects
    // RelayUsable() — false while a reconnect is in flight — so this dot honestly
    // tracks whether edits/presence are actually flowing right now (🔴 while
    // down/reconnecting, 🟢 once re-joined), independent of the rest of the panel.
    if (!room_id.empty()) {
        ImGui::SameLine(0, 12);
        const ImU32 dot = relay_connected ? IM_COL32( 76, 217, 100, 255)   // green
                                          : IM_COL32(230,  90,  76, 255);  // red
        const float lh  = ImGui::GetTextLineHeight();
        const float rad = lh * 0.30f;
        const ImVec2 p  = ImGui::GetCursorScreenPos();
        ImGui::GetWindowDrawList()->AddCircleFilled(
            { p.x + rad, p.y + lh * 0.5f }, rad, dot);
        ImGui::Dummy({ rad * 2 + 6, lh });
        ImGui::SameLine(0, 0);
        ImGui::TextColored(relay_connected ? ImVec4(0.30f, 0.85f, 0.40f, 1.f)
                                           : ImVec4(0.90f, 0.35f, 0.30f, 1.f),
                           relay_connected ? "connected" : "disconnected");
    }
    ImGui::Separator();

    // ── Self preview ────────────────────────────────────────────────────────
    ImGui::Text("You");
    ImGui::SameLine(0, 16);

    if (!video.IsCameraEnabled()) {
        ImGui::TextDisabled("[cam off]");
    } else {
        const auto& sp = video.SelfPreview();
        if (sp.empty()) {
            ImGui::TextDisabled("[waiting for camera...]");
        } else {
            // Self-preview is a raw RGB buffer; ImGui::Image needs a texture ID.
            // We skip a GL texture for self-preview (nice-to-have); just show
            // a placeholder size rect in the UI so layout is consistent.
            ImGui::Dummy({ static_cast<float>(kThumbW), static_cast<float>(kThumbH) });
            ImGui::SameLine();
            ImGui::TextDisabled("(live)");
        }
    }

    ImGui::Spacing();

    // ── Controls ────────────────────────────────────────────────────────────
    bool muted = voice.IsMuted();
    if (ImGui::Button(muted ? "Unmute mic" : "Mute mic")) {
        voice.SetMuted(!muted);
    }
    ImGui::SameLine();

    bool cam_on = video.IsCameraEnabled();
    if (ImGui::Button(cam_on ? "Cam off" : "Cam on")) {
        video.SetCameraEnabled(!cam_on);
    }

    ImGui::Separator();

    // ── Peer list ────────────────────────────────────────────────────────────
    const auto& peers = session.Peers();
    if (peers.empty()) {
        ImGui::TextDisabled("No peers in room yet.");
        ImGui::TextDisabled("Share the room ID above to invite collaborators.");
    }

    constexpr float kThumbF   = static_cast<float>(kThumbW);
    constexpr float kThumbFH  = static_cast<float>(kThumbH);
    constexpr float kMeterH   = 8.f;

    for (const auto& p : peers) {
        ImGui::PushID(p.peer_id.c_str());
        ImGui::BeginGroup();

        // Video thumbnail or initials avatar.
        unsigned int tex = video.PeerTexture(p.peer_id);
        {
            static int s_pt = 0;
            if (++s_pt % 120 == 0)
                std::fprintf(stderr, "panel: PeerTexture(%.8s) = %u\n", p.peer_id.c_str(), tex);
        }
        if (tex) {
            ImGui::Image(static_cast<ImTextureID>(tex),
                         { kThumbF, kThumbFH });
        } else {
            DrawInitialsAvatar(p.display_name, kThumbF);
        }

        // Name + audio level meter.
        ImGui::TextUnformatted(p.display_name.c_str());
        float level = voice.PeerLevel(p.peer_id);
        ImGui::PushStyleColor(ImGuiCol_PlotHistogram, ImVec4(0.3f, 0.9f, 0.3f, 1.f));
        ImGui::ProgressBar(level, { kThumbF, kMeterH }, "");
        ImGui::PopStyleColor();

        ImGui::EndGroup();
        ImGui::SameLine(0, 12);
        ImGui::PopID();
    }

    if (!peers.empty()) ImGui::NewLine();  // end the horizontal row

    ImGui::End();
}

} // namespace wfedit
