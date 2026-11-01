// Which control draws a catalog field. Generic: decided from the field's compiled kind,
// showAs code, rule and read-only flag, never from its name or key, and never by scanning
// object types at runtime. The TV form, the phone touch form and the form's key handling
// all ask this one function (docs/plans/2026-11-01-field-presentations.md).
#pragma once
#include "runtime_properties.hpp"
#include <algorithm>
#include <cstring>
namespace wfprops {
enum class Control {
    Number,NumberWithBounds,Slider,Colour,          // kinds 0 and 1
    ChoiceList,NumberedChoiceList,Segments,Chips,SteppedSlider, // kind 2
    Checkbox,Switch,                                // kind 4
    Text,Digits,Multiline,Path,                     // kind 3
    Reference,Action,Spacer,Structure               // 8, 9, 10; 5 to 7
};
// showAs codes from wfsource/source/oas/oad.h.
enum : uint8_t {ShowNA=0,ShowNumber=1,ShowSlider=2,ShowToggle=3,ShowDropMenu=4,ShowRadio=5,ShowHidden=6,
                ShowColor=7,ShowCheckbox=8,ShowMailbox=9,ShowComboBox=10,ShowTextEditor=11,ShowFilename=12};
inline Control presentation(const Field& f){
    const uint8_t show=f.show&0x7f;  // 128 is the VECTOR modifier
    switch(f.kind){
    case 0:return show==ShowSlider?Control::Slider:show==ShowColor?Control::Colour:show==ShowMailbox?Control::NumberWithBounds:Control::Number;
    case 1:return show==ShowSlider?Control::Slider:Control::Number;
    case 2:return show==ShowSlider?Control::SteppedSlider:show==ShowRadio?Control::Chips:show==ShowToggle?Control::Segments:
                  show==ShowNumber?Control::NumberedChoiceList:Control::ChoiceList;
    case 3:return f.rule==1?Control::Digits:f.rule==2?Control::Multiline:show==ShowFilename?Control::Path:Control::Text;
    case 4:return show==ShowToggle?Control::Switch:Control::Checkbox;
    case 8:return Control::Reference;
    case 9:return Control::Action;
    case 10:return Control::Spacer;
    default:return Control::Structure;
    }
}
inline const char* controlName(Control c){
    static const char* names[]={"number","number-with-bounds","slider","colour","choice-list","numbered-choice-list","segments",
        "chips","stepped-slider","checkbox","switch","text","digits","multiline","path","reference","action","spacer","structure"};
    return names[int(c)];
}
// Drawn as a value box that opens a list of its options.
inline bool choiceList(Control c){return c==Control::ChoiceList||c==Control::NumberedChoiceList;}
// How the TV form's keys act on a focused, editable row. This table is the whole row-navigation
// policy; Form::input and the footer hint read nothing else, and the navigation tests
// (tests/test_runtime_property_presentation.py) follow it. Choice rows (Will, 2026-11-01,
// option 6): with up to kCycleChoicesMax options they cycle with Left / Right, clamped, and
// Left on the first option leaves to the section rail; with more they do not cycle and Left
// goes to the rail. A opens the option list either way. Drawing does not depend on the count.
constexpr int kCycleChoicesMax=4;
struct Keys {
    bool leftRightChange=false;   // Left / Right change the value (otherwise Left goes to the rail)
    bool leftOnFirstToRail=false; // ...except Left on the first value goes to the rail
    bool aOpensList=false;        // A opens the option list
};
inline Keys keys(Control c,int options=0){
    Keys k;
    const bool cycling=choiceList(c)&&options>=2&&options<=kCycleChoicesMax;
    k.leftRightChange=c==Control::Slider||c==Control::Chips||c==Control::SteppedSlider||c==Control::Segments||
                      c==Control::Checkbox||c==Control::Switch||cycling;
    k.leftOnFirstToRail=c==Control::Segments||c==Control::Switch||cycling;
    k.aOpensList=choiceList(c);
    return k;
}
inline int optionCount(const Field& f){return f.kind==2?std::max(0,f.maximum-f.minimum+1):0;}
inline Keys keys(const Field& f){return keys(presentation(f),optionCount(f));}
// A relative path of names separated by '/': no leading '/', no '\', no empty, "." or ".."
// segment, no control characters. Used for FILENAME text fields.
inline bool relativePath(const std::string& v){
    if(v.empty()||v.front()=='/'||v.back()=='/')return false;
    size_t start=0;
    for(size_t i=0;i<=v.size();++i){
        if(i<v.size()){unsigned char c=static_cast<unsigned char>(v[i]);if(c<0x20||c==0x7f||c=='\\')return false;if(c!='/')continue;}
        const std::string part=v.substr(start,i-start);if(part.empty()||part=="."||part=="..")return false;start=i+1;
    }
    return true;
}
}
