#pragma once
// UI-only controls. Core properties and validation remain unchanged.
#include "../../../engine/runtime_property_form.hpp"
#include <algorithm>
#include <cstdio>
#include <cmath>
#include <chrono>
#include <array>
namespace propertyui {
struct TextRequest {
 uint64_t session=0;uint32_t field=0;std::string label,value;int mode=0;uint32_t maxLength=128;
};
struct TextHost {
 std::function<bool(const TextRequest&)> show;
 std::function<void(uint64_t)> hide;
};
inline TextHost& textHost(){static TextHost host;return host;}
struct Controls {
 wfprops::Form* owner=nullptr;uint64_t session=0;uint32_t field=0;int channel=0;bool nativeOpen=false;
 bool colourOpen=false,planeAdjust=false;int page=0,focus=0,textChannel=-1;
 uint32_t original=0,preview=0;double hue=0,saturation=0,value=0;
 uint32_t repeatButtons=0;std::chrono::steady_clock::time_point holdStart{},lastRepeat{};
};
inline Controls& activeControls(){static Controls state;return state;}
inline void dismissText(){auto& ui=activeControls();if(ui.nativeOpen&&textHost().hide)textHost().hide(ui.session);ui.nativeOpen=false;}
inline Controls& controls(wfprops::Form& form){auto& state=activeControls();
 const auto* field=form.field();uint32_t id=field?field->id:0;
 if(state.owner!=&form||state.session!=form.edit.session||state.field!=id){dismissText();state=Controls{};state.owner=&form;state.session=form.edit.session;state.field=id;}
 return state;
}
inline bool colour(const wfprops::Field* field){return field&&field->kind==0&&field->show==7;}
inline bool keyboard(const wfprops::Field* field){return field&&field->kind==3&&field->rule!=1;}
inline uint32_t rgb(const std::string& value){return uint32_t(std::strtoul(value.c_str(),nullptr,10))&0xffffffu;}
inline std::string hex(uint32_t value){char text[8];std::snprintf(text,sizeof(text),"#%06X",value&0xffffffu);return text;}
inline const std::array<uint32_t,16>& palette(){static const std::array<uint32_t,16> values={0xea6f69,0xe59b51,0xded16c,0x87b46c,0x58a78c,0x6eb6c6,0x658cd1,0x8c7dce,0xbe81b7,0xd4a6a1,0xdedad0,0x8f989c,0x9d6555,0x556d3b,0x466d72,0x2d414b};return values;}
inline std::vector<uint32_t>& recentColours(){static std::vector<uint32_t> values;return values;}
inline void rememberColour(uint32_t value){auto& values=recentColours();values.erase(std::remove(values.begin(),values.end(),value),values.end());values.insert(values.begin(),value);if(values.size()>6)values.resize(6);}
inline uint32_t hsv(double h,double s,double v){h=std::fmod(h+360,360)/60;double c=v*s,x=c*(1-std::abs(std::fmod(h,2)-1)),m=v-c;double r=0,g=0,b=0;
 if(h<1){r=c;g=x;}else if(h<2){r=x;g=c;}else if(h<3){g=c;b=x;}else if(h<4){g=x;b=c;}else if(h<5){r=x;b=c;}else{r=c;b=x;}
 return (uint32_t(std::lround((r+m)*255))<<16)|(uint32_t(std::lround((g+m)*255))<<8)|uint32_t(std::lround((b+m)*255));}
inline void colourValues(Controls& ui,uint32_t packed){ui.preview=packed;double r=((packed>>16)&255)/255.,g=((packed>>8)&255)/255.,b=(packed&255)/255.;double high=std::max(r,std::max(g,b)),low=std::min(r,std::min(g,b)),delta=high-low;ui.value=high;ui.saturation=high?delta/high:0;
 if(delta){double h=high==r?(g-b)/delta:high==g?(b-r)/delta+2:(r-g)/delta+4;ui.hue=std::fmod(h*60+360,360);}}
inline void openColour(wfprops::Form& form,Controls& ui){ui.colourOpen=true;ui.page=ui.focus=0;ui.planeAdjust=false;ui.textChannel=-1;ui.original=rgb(form.value());colourValues(ui,ui.original);}
inline void finishColour(wfprops::Form& form,Controls& ui,bool accept){if(accept&&!form.edit.set(ui.field,std::to_string(ui.preview)))return;if(accept)rememberColour(ui.preview);ui.colourOpen=false;ui.planeAdjust=false;form.drawer=false;}
inline void colourText(wfprops::Form& form,Controls& ui,int channel){ui.textChannel=channel;std::string value=channel==3?hex(ui.preview):std::to_string((ui.preview>>((2-channel)*8))&255);const char* names[]={"Red (0-255)","Green (0-255)","Blue (0-255)","Hex (#RRGGBB)"};
 ui.nativeOpen=true;TextRequest request{ui.session,ui.field,names[channel],value,channel==3?0:1,channel==3?7u:3u};
 if(!textHost().show||!textHost().show(request)){ui.nativeOpen=false;ui.textChannel=-1;form.edit.error="Enter exact values using a connected browser";}}
inline void completeText(uint64_t session,uint32_t id,const std::string& value,bool accept){
 auto& ui=activeControls();auto* form=ui.owner;
 if(!form||!ui.nativeOpen||ui.session!=session||ui.field!=id||form->edit.session!=session||!form->edit.open||!form->edit.object())return;
 ui.nativeOpen=false;form->previous=0;
 if(ui.colourOpen&&ui.textChannel>=0){int channel=ui.textChannel;ui.textChannel=-1;
  if(accept){std::string digits=value;if(channel==3&&!digits.empty()&&digits[0]=='#')digits.erase(0,1);
   bool valid=channel==3?digits.size()==6&&digits.find_first_not_of("0123456789abcdefABCDEF")==std::string::npos:!digits.empty()&&digits.find_first_not_of("0123456789")==std::string::npos&&digits.size()<=3;
   unsigned long n=valid?std::strtoul(digits.c_str(),nullptr,channel==3?16:10):0;if(channel!=3&&n>255)valid=false;
   if(valid){uint32_t packed=channel==3?uint32_t(n):(ui.preview&~(255u<<((2-channel)*8)))|(uint32_t(n)<<((2-channel)*8));colourValues(ui,packed);form->edit.error.clear();}else form->edit.error=channel==3?"Enter six hexadecimal digits":"Enter a value from 0 to 255";
  }return;
 }
 form->drawer=false;
 if(accept){if(value.size()<=65536)form->edit.set(id,value);else form->edit.error="Text is too long";}
}
inline void syncText(wfprops::Form& form,bool phone=false){auto& ui=controls(form);const auto* field=form.field();
 if(ui.colourOpen&&(!form.edit.open||phone)){ui.colourOpen=false;ui.planeAdjust=false;if(phone)form.drawer=false;}
 if(ui.colourOpen&&!form.drawer&&form.edit.open){if(ui.planeAdjust){ui.planeAdjust=false;form.drawer=true;}else ui.colourOpen=false;}
 if(ui.nativeOpen&&(!form.edit.open||!form.drawer||phone)){dismissText();form.drawer=false;}
 if(!form.edit.open||!form.drawer||phone||!field||colour(field)||ui.nativeOpen)return;
 int mode=field->kind==3?(field->rule==1?1:field->rule==2?2:0):field->kind==1?4:3;
 TextRequest request{form.edit.session,field->id,field->label,form.value(),mode,field->kind==3?field->maxLength:128};
 ui.nativeOpen=true;
 if(!textHost().show||!textHost().show(request)){ui.nativeOpen=false;form.drawer=false;form.edit.error="Enter text using a connected browser";}
}
inline void input(wfprops::Form& form,uint32_t buttons){auto& ui=controls(form);const auto* field=form.field();syncText(form);
 if(ui.nativeOpen){form.previous=buttons;return;}
 if(!form.edit.open||!form.drawer||!colour(field)){bool before=form.drawer;form.input(buttons);if(!before&&form.drawer){ui.channel=0;if(colour(form.field()))openColour(form,ui);}syncText(form);return;}
 if(!ui.colourOpen)openColour(form,ui);
 uint32_t edge=buttons&~form.previous;form.previous=buttons;
 if(field->readonly){finishColour(form,ui,false);return;}
 const uint32_t up=1u<<11,down=1u<<12,right=1u<<13,left=1u<<14;
 bool adjusting=ui.page==1&&(ui.planeAdjust||ui.focus==1);
 auto now=std::chrono::steady_clock::now();uint32_t directions=buttons&(up|down|right|left);
 if(!adjusting||!directions){ui.repeatButtons=0;}else if(directions!=ui.repeatButtons){ui.repeatButtons=directions;ui.holdStart=ui.lastRepeat=now;}
 else {auto held=std::chrono::duration_cast<std::chrono::milliseconds>(now-ui.holdStart).count();auto since=std::chrono::duration_cast<std::chrono::milliseconds>(now-ui.lastRepeat).count();if(held>=350&&since>=(held>=1200?25:85)){edge|=directions;ui.lastRepeat=now;}}
 if(ui.page==0){
  const int n=int(recentColours().size()),actions=16+n;std::vector<int> rows={4,4,4,4};if(n)rows.push_back(n);rows.push_back(3);
  int row=0,col=ui.focus,offset=0;while(col>=rows[row]){col-=rows[row];offset+=rows[row++];}
  if(edge&left)col=std::max(0,col-1);if(edge&right)col=std::min(rows[row]-1,col+1);
  if(edge&(up|down)){row=std::max(0,std::min(int(rows.size())-1,row+((edge&down)?1:-1)));col=std::min(col,rows[row]-1);}
  offset=0;for(int i=0;i<row;++i)offset+=rows[i];ui.focus=offset+col;
  if(edge&1){if(ui.focus<16)colourValues(ui,palette()[ui.focus]);else if(ui.focus<actions)colourValues(ui,recentColours()[ui.focus-16]);else if(ui.focus==actions){ui.page=1;ui.focus=0;}else finishColour(form,ui,ui.focus==actions+1);}
 }else if(ui.page==1){
  if(ui.planeAdjust){if(edge&left)ui.saturation=std::max(0.,ui.saturation-.01);if(edge&right)ui.saturation=std::min(1.,ui.saturation+.01);if(edge&up)ui.value=std::min(1.,ui.value+.01);if(edge&down)ui.value=std::max(0.,ui.value-.01);if(edge&(up|down|left|right))ui.preview=hsv(ui.hue,ui.saturation,ui.value);if(edge&1)ui.planeAdjust=false;}
  else {if(edge&up)ui.focus=std::max(0,ui.focus-1);if(edge&down)ui.focus=std::min(4,ui.focus+1);
   if(ui.focus==1&&(edge&(left|right))){ui.hue=std::fmod(ui.hue+((edge&right)?1:359),360);ui.preview=hsv(ui.hue,ui.saturation,ui.value);}
   if(edge&1){if(ui.focus==0)ui.planeAdjust=true;else if(ui.focus==2){ui.page=2;ui.focus=0;}else if(ui.focus==3)finishColour(form,ui,true);else if(ui.focus==4){ui.page=0;ui.focus=16+int(recentColours().size());}}
  }
 }else {if(edge&up)ui.focus=std::max(0,ui.focus-1);if(edge&down)ui.focus=std::min(4,ui.focus+1);if(edge&1){if(ui.focus<4)colourText(form,ui,ui.focus);else{ui.page=1;ui.focus=2;}}}
}
}
