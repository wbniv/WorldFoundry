#pragma once
#include "../../../engine/runtime_property_host.hpp"
#include <hal/phonepad/phonepad_overlay.h>
namespace propertyui {
using FormInput=void(*)(wfprops::Form&,uint32_t);
FormInput& inputHandler();
void inputHost(uint32_t buttons);
void buildHost(int w,int h,std::vector<PhonepadRect>& out);
void build(wfprops::Form& editor,bool phone,int w,int h,std::vector<PhonepadRect>& out);}
