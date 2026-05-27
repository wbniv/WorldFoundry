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
void RenderCollabPanel(bool& show_collab,
                       CollabSession& session,
                       VoiceChat&     voice,
                       VideoChat&     video,
                       const std::string& room_id);

} // namespace wfedit
