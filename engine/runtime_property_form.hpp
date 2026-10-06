#pragma once
#include "runtime_properties.hpp"
namespace wfprops {
// Focus uses authored sections and rows, never screen-coordinate proximity.
struct Form {
    Edit edit;
    std::vector<std::vector<size_t>> sections;
    std::vector<std::string> titles;
    size_t section=0,row=0;bool rail=false,adjust=false,drawer=false,replaceText=false;
    int key=0;uint32_t previous=0;
    std::function<void(const std::string&)> action;
    bool begin(Registry& registry,uint32_t actor);
    const Field* field() const;
    std::string value() const;
    void change(int direction);
    void input(uint32_t buttons);
    // Returns true when the outer form should apply/close.
    bool back();
    bool command(const std::string& text);
};
}
