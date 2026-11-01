#pragma once
#include "runtime_property_presentation.hpp"
namespace wfprops {
// Focus uses authored sections and rows, never screen-coordinate proximity.
struct Form {
    Edit edit;
    std::vector<std::vector<size_t>> sections;
    std::vector<std::string> titles;
    size_t section=0,row=0;bool rail=false,adjust=false,drawer=false,replaceText=false;
    // An open choice list (presentation ChoiceList / NumberedChoiceList): the highlighted
    // option, counted from the field's minimum. Selecting writes the draft only.
    bool list=false;size_t listIndex=0;
    int key=0;uint32_t previous=0;
    std::function<void(const std::string&)> action;
    bool begin(Registry& registry,uint32_t actor,uint32_t openingButtons=0);
    const Field* field() const;
    std::string value() const;
    void change(int direction);
    void input(uint32_t buttons);
    // Returns true when the outer form should apply/close.
    bool back();
    bool command(const std::string& text);
};
}
