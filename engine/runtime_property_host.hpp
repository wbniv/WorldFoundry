#pragma once
#include "runtime_property_form.hpp"
#include "object_picker.hpp"
namespace wfprops {
struct Consumer {
    std::function<void()> beforeOpen;
    std::function<bool(Form&,const std::string&)> beforeCommit;
    std::function<void(const Object&,const std::string&)> committed;
};
struct Owner {uint32_t actor;uint64_t generation;std::string title;};
// Pick in 3D (docs/plans/2026-10-16-runtime-object-editing.md, Phase P).
// Off: the chooser list. Scene: arrows move a highlight between candidates on
// screen. Group: a short list of the candidates sharing one bracket.
enum class PickMode {Off,Scene,Group};
// Where candidates are in the world; set by the running level, empty elsewhere.
// Nothing here is called while the picker is closed.
struct PickWorld {
    std::function<bool(wfpick::Camera&)> camera;
    std::function<bool(uint32_t actor,wfpick::Candidate&)> locate;
};
// One modal/session owner for all level catalogs and selector previews.
class Host {
public:
    Form form;
    bool modal=false,picker=false,phone=false;
    size_t selected=0;              // chooser row; row 0 is Pick in 3D
    std::vector<Owner> owners;
    PickMode pick=PickMode::Off;
    PickWorld world;
    std::vector<wfpick::Candidate> pickCandidates; // refreshed each frame while picking
    std::vector<wfpick::Target> pickTargets;
    int highlight=-1;                               // index into pickTargets
    std::vector<uint32_t> group;size_t groupSelected=0;
    // The picker's candidates: (actor id, label). Phase P reads today's owners;
    // the redesign feeds the LevelObj Editable Objects list through here.
    std::vector<wfpick::Entry> candidates() const;
    void enterPick();
    void refreshPick();
    void pickMove(wfpick::Direction direction);
    void pickOk();
    // Mouse: highlight what is under a logical (1920x1080) point; true on a hit.
    bool pickHover(float x,float y);
    void resetPick();
    void bind(Registry* registry);
    Registry* registry() const {return registry_;}
    bool available() const;
    bool open(uint32_t openingButtons=0);
    bool openOwner(uint32_t actor,uint32_t openingButtons=0);
    void close();
    void checkOwner();
    bool apply(const std::string& action="apply");
    bool back();
    void inputPicker(uint32_t buttons);
    // Returns a short OK tap; gameplay consumers may retain their tap action.
    bool gesture(uint32_t buttons,float dt);
    bool waitingForRelease() const {return swallow_;}
    void suspend();
    void consumer(const std::string& schema,Consumer consumer);
    void command(const std::string& text);
    std::string message() const;
    uint64_t session() const {return picker?pickerSession_:form.edit.session;}
private:
    Registry* registry_=nullptr;
    std::map<std::string,Consumer> consumers_;
    uint64_t pickerSession_=0;
    uint32_t previous_=0,pickerPrevious_=0,highlightActor_=0;
    float hold_=0;
    bool swallow_=false;
};
Host& host();
}
