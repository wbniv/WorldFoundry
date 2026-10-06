#pragma once
#include "runtime_property_form.hpp"
namespace wfprops {
struct Consumer {
    std::function<void()> beforeOpen;
    std::function<bool(Form&,const std::string&)> beforeCommit;
    std::function<void(const Object&,const std::string&)> committed;
};
struct Owner {uint32_t actor;uint64_t generation;std::string title;};
// One modal/session owner for all level catalogs and selector previews.
class Host {
public:
    Form form;
    bool modal=false,picker=false,phone=false;
    size_t selected=0;
    std::vector<Owner> owners;
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
    uint32_t previous_=0,pickerPrevious_=0;
    float hold_=0;
    bool swallow_=false;
};
Host& host();
}
