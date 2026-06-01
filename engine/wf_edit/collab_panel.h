#pragma once
// engine/wf_edit/collab_panel.h — ImGui "Collaborators" panel for voice+video.

#include <string>

namespace wfedit {

class CollabSession;
class VoiceChat;
class VideoChat;

// Render the "Collaborators" dockable ImGui window. Call once per frame from
// the editor_build callback after ImGui::NewFrame(). show_collab is toggled by
// View→Collaborators; if false the window is not drawn.
//
// relay_connected is the live relay socket state (WsClient::connected()). The
// panel shows a connected/disconnected indicator on the Room line: without it,
// a session whose startup connect failed looked identical to a live one (the
// Room name + "You" tile render from room_id regardless of the socket).
void RenderCollabPanel(bool& show_collab,
                       CollabSession& session,
                       VoiceChat&     voice,
                       VideoChat&     video,
                       const std::string& room_id,
                       bool           relay_connected);

} // namespace wfedit
