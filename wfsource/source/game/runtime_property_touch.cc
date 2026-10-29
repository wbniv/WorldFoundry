#include "runtime_property_touch.h"
#include "runtime_property_controls.h"
#include <algorithm>
#include <cmath>
#include <cstdlib>

namespace propertyui {
namespace {
enum class Kind { Entry, Back, Apply, Cancel, SectionMenu, Section, Row, Slider,
                  Choice, ScrollUp, ScrollDown, Palette, ColourCustom, ColourUse,
                  ColourCancel, ColourValue, ColourDetails, PickScene, Owner, GroupOwner };
struct Target { TouchRect box; Kind kind; int index=0,row=-1; };
struct State {
 bool enabled=false,sectionMenu=false,choiceMenu=false,moved=false;
 float density=1,top=0,bottom=0,downX=0,downY=0,lastY=0;
 int pointer=-1,firstRow=0,firstChoice=0,choiceRow=0;
 uint64_t session=0;
 std::vector<Target> targets;
} state;
constexpr uint32_t bg=0x061014ffu,panel=0x142d25ffu,card=0x233e31ffu,
 selected=0x497b51ffu,ink=0xf1f2e4ffu,muted=0xb6c7baffu,accent=0xefce83ffu;

struct Canvas {
 int width,height;float d,w,h,top;std::vector<PhonepadRect>* rects;std::vector<bitmaptext::Quad>* glyphs;
 void box(float x,float y,float bw,float bh,uint32_t colour){if(rects)rects->push_back({x*d,(y+top)*d,(x+bw)*d,(y+top+bh)*d,colour});}
 void label(float x,float cy,float size,const std::string& value,uint32_t colour=ink,bool bold=false,float maxWidth=0){
  if(!glyphs||!wfui::Loaded())return;
  auto v=bold?wfui::BodyBold:wfui::Body;
  wfui::Transform t;t.s=size*d/36.f;t.ox=x*d;t.oy=(cy+top)*d;
  std::string fitted=value;
  if(maxWidth>0)fitted=wfui::Fit(v,value,maxWidth*36.f/size,"...");
  wfui::Text(*glyphs,0,0,v,colour,fitted,wfui::Middle,wfui::Left,t);
 }
 void hit(float x,float y,float bw,float bh,Kind kind,int index=0,int row=-1){state.targets.push_back({{x,y,x+bw,y+bh},kind,index,row});}
 void button(float x,float y,float bw,float bh,const std::string& title,Kind kind,uint32_t colour=card,int index=0){box(x,y,bw,bh,colour);label(x+14,y+bh*.5f,18,title,ink,false,bw-25);hit(x,y,bw,bh,kind,index);}
};
float density(){return std::max(.5f,state.density);}
int choices(const wfprops::Field& field){return field.kind==2?std::max(0,field.maximum-field.minimum+1):0;}
std::string choiceLabel(const wfprops::Field& field,int index){
 size_t start=0;for(int i=0;i<index;++i){auto p=field.choices.find('|',start);if(p==std::string::npos)return {};start=p+1;}
 auto end=field.choices.find('|',start);return field.choices.substr(start,end==std::string::npos?end:end-start);
}
std::string valueLabel(const wfprops::Form& form,const wfprops::Field& field){
 auto it=form.edit.draft.find(field.id);std::string value=it==form.edit.draft.end()?field.initial:it->second;
 if(field.kind==2)value=choiceLabel(field,std::atoi(value.c_str())-field.minimum);
 if(field.kind==4)value=value=="1"?"On":"Off";
 if(colour(&field))value=hex(rgb(value));
 std::replace(value.begin(),value.end(),'\n',' ');return value;
}
void syncSession(wfprops::Host& host){
 const uint64_t session=host.modal?host.session():0;
 if(session==state.session)return;
 state.session=session;state.sectionMenu=state.choiceMenu=false;
 state.firstRow=state.firstChoice=state.choiceRow=0;state.pointer=-1;state.targets.clear();
}
int visible(float top,float bottom,float height){return std::max(1,int((bottom-top)/height));}
void footer(Canvas& c,bool picker){
 float y=c.h-78,x=16,gap=10,bw=(c.w-42)/2;
 c.box(0,y-9,c.w,87,panel);
 c.button(x,y,bw,55,picker?"Back":"Cancel",picker?Kind::Back:Kind::Cancel);
 c.button(x+bw+gap,y,bw,55,picker?"Close":"Apply",picker?Kind::Cancel:Kind::Apply,selected);
}
void renderChooser(Canvas& c,wfprops::Host& host){
 c.label(18,55,24,host.pick==wfprops::PickMode::Group?"Objects here":"Choose an object",ink,true,c.w-36);
 const bool group=host.pick==wfprops::PickMode::Group;
 int count=group?int(host.group.size()):int(host.owners.size())+1;
 int shown=visible(90,c.h-95,65);
 state.firstChoice=std::max(0,std::min(state.firstChoice,std::max(0,count-shown)));
 for(int i=state.firstChoice;i<count&&i<state.firstChoice+shown;++i){
  float y=90+(i-state.firstChoice)*65;
  std::string title;
  if(group){for(const auto& owner:host.owners)if(owner.actor==host.group[size_t(i)])title=owner.title;}
  else title=i==0?"Pick in 3D":host.owners[size_t(i-1)].title;
  c.button(16,y,c.w-32,56,title,group?Kind::GroupOwner:i==0?Kind::PickScene:Kind::Owner,card,i);
 }
 if(count>shown){c.button(c.w-120,17,48,48,"^",Kind::ScrollUp);c.button(c.w-64,17,48,48,"v",Kind::ScrollDown);}
 footer(c,true);
}
void renderChoice(Canvas& c,wfprops::Form& form){
 const auto* field=form.field();if(!field){state.choiceMenu=false;return;}
 c.label(18,55,24,field->label,ink,true,c.w-36);
 int count=choices(*field),shown=visible(88,c.h-95,62);
 state.firstChoice=std::max(0,std::min(state.firstChoice,std::max(0,count-shown)));
 for(int i=state.firstChoice;i<count&&i<state.firstChoice+shown;++i)
  c.button(16,88+(i-state.firstChoice)*62,c.w-32,54,choiceLabel(*field,i),Kind::Choice,i==std::atoi(form.value().c_str())-field->minimum?selected:card,i);
 if(count>shown){c.button(c.w-120,17,48,48,"^",Kind::ScrollUp);c.button(c.w-64,17,48,48,"v",Kind::ScrollDown);}
 c.button(16,c.h-75,c.w-32,55,"Back to fields",Kind::Back);
}
void renderColour(Canvas& c,wfprops::Form& form){
 auto& ui=controls(form);if(!ui.colourOpen)openColour(form,ui);
 c.label(18,55,24,form.field()?form.field()->label:"Colour",ink,true,c.w-36);
 if(ui.page==0){
  float gap=8,cell=std::min(70.f,(c.w-48-3*gap)/4.f),left=(c.w-4*cell-3*gap)/2;
  for(int i=0;i<16;++i){float x=left+(i%4)*(cell+gap),y=85+(i/4)*(cell+gap);c.box(x,y,cell,cell,(palette()[size_t(i)]<<8)|255u);c.hit(x,y,cell,cell,Kind::Palette,i);}
  float by=85+4*(cell+gap)+9;c.button(16,by,c.w-32,52,"Custom colour",Kind::ColourCustom);
 }else if(ui.page==1){
  float size=std::min(c.w-40,c.h-290.f),left=(c.w-size)/2,top=85;
  for(int y=0;y<24;++y)for(int x=0;x<24;++x)c.box(left+x*size/24,top+y*size/24,size/24+1,size/24+1,(hsv(x*360./24,1-y/23.,ui.value)<<8)|255u);
  c.hit(left,top,size,size,Kind::ColourCustom);
  c.label(18,top+size+30,18,"Brightness: "+std::to_string(int(ui.value*100))+"%");
  c.box(20,top+size+48,c.w-40,16,muted);c.hit(20,top+size+38,c.w-40,40,Kind::ColourValue);
  c.button(16,top+size+95,c.w-32,48,"RGB / Hex details",Kind::ColourDetails);
 }else{
  c.label(18,105,18,"Edit a channel with the system keyboard");
  const char* names[]={"Red (0–255)","Green (0–255)","Blue (0–255)","Hex (#RRGGBB)"};
  for(int i=0;i<4;++i)c.button(16,130+i*62,c.w-32,54,names[i],Kind::ColourDetails,card,i);
 }
 c.box(16,c.h-166,c.w-32,46,(ui.preview<<8)|255u);
 c.button(16,c.h-105,(c.w-42)/2,55,"Cancel",Kind::ColourCancel);
 c.button(26+(c.w-42)/2,c.h-105,(c.w-42)/2,55,"Use colour",Kind::ColourUse,selected);
}
void renderForm(Canvas& c,wfprops::Form& form){
 auto* object=form.edit.object();if(!object)return;
 bool tablet=c.w>=650&&c.h>=500;
 c.label(18,49,24,object->title,ink,true,c.w-36);
 if(form.drawer){if(colour(form.field()))renderColour(c,form);else{c.label(18,125,18,"Editing with the system keyboard");c.button(16,c.h-75,c.w-32,55,"Close editor",Kind::Back);}return;}
 if(state.choiceMenu){renderChoice(c,form);return;}
 if(state.sectionMenu){
  c.label(18,110,18,"Choose a section");
  int shown=visible(130,c.h-95,62);state.firstChoice=std::max(0,std::min(state.firstChoice,std::max(0,int(form.titles.size())-shown)));
  for(int i=state.firstChoice;i<int(form.titles.size())&&i<state.firstChoice+shown;++i)
   c.button(16,130+(i-state.firstChoice)*62,c.w-32,54,form.titles[size_t(i)],Kind::Section,i==int(form.section)?selected:card,i);
  if(int(form.titles.size())>shown){c.button(c.w-120,65,48,48,"^",Kind::ScrollUp);c.button(c.w-64,65,48,48,"v",Kind::ScrollDown);}
  c.button(16,c.h-75,c.w-32,55,"Back to fields",Kind::Back);return;
 }
 float listX=tablet?230.f:16.f,listW=c.w-listX-16,top=tablet?92.f:151.f,bottom=c.h-125;
 if(tablet){
  int shown=visible(92,bottom,60);
  for(int i=0;i<int(form.titles.size())&&i<shown;++i)c.button(16,92+i*60,200,52,form.titles[size_t(i)],Kind::Section,i==int(form.section)?selected:card,i);
 }else c.button(16,74,c.w-32,58,"Section: "+(form.section<form.titles.size()?form.titles[form.section]:"Properties")+"  v",Kind::SectionMenu,selected);
 if(form.section>=form.sections.size()){footer(c,false);return;}
 const auto& rows=form.sections[form.section];int shown=visible(top,bottom,82);
 state.firstRow=std::max(0,std::min(state.firstRow,std::max(0,int(rows.size())-shown)));
 for(int i=state.firstRow;i<int(rows.size())&&i<state.firstRow+shown;++i){
  const auto& field=object->fields[rows[size_t(i)]];float y=top+(i-state.firstRow)*82;
  if(field.kind==10){c.box(listX,y+32,listW,2,muted);continue;}
  c.box(listX,y,listW,74,field.readonly?0x1c302affu:field.kind==9?selected:card);
  std::string group;
  for(size_t j=0;j<rows[size_t(i)];++j){const auto& marker=object->fields[j];if(marker.kind==6)group=marker.label;else if(marker.kind==5||marker.kind==7)group.clear();}
  if(!group.empty())c.label(listX+13,y+12,12,group,accent,false,listW-28);
  float labelY=y+(group.empty()?24:32),valueY=y+(group.empty()?52:59);
  c.label(listX+13,labelY,17,field.label,field.readonly?muted:ink,true,listW-28);
  bool segments=field.kind==2&&(field.show==3||field.show==5)&&choices(field)==2&&!field.readonly;
  if(field.kind!=9&&!segments)c.label(listX+13,valueY,17,valueLabel(form,field)+(field.kind==2&&field.show!=2?"  v":""),muted,false,listW-70);
  if(segments){
   float cw=(listW-34)/2;
   for(int option=0;option<2;++option){float ox=listX+12+option*(cw+10);
    auto v=form.edit.draft.find(field.id);bool active=(v!=form.edit.draft.end()?std::atoi(v->second.c_str()):std::atoi(field.initial.c_str()))==field.minimum+option;
    c.box(ox,y+41,cw,27,active?0xe4efd9ffu:0x19382dffu);
    c.label(ox+8,y+54,14,choiceLabel(field,option),active?panel:ink,false,cw-14);
    c.hit(ox,y+37,cw,35,Kind::Choice,option,i);
   }
  }
  if(field.kind==4){c.box(listX+listW-63,y+35,48,27,valueLabel(form,field)=="On"?selected:muted);}
  if(colour(&field)){auto v=form.edit.draft.find(field.id);c.box(listX+listW-60,y+34,38,29,(rgb(v==form.edit.draft.end()?field.initial:v->second)<<8)|255u);}
  c.hit(listX,y,listW,74,field.show==2&&field.kind<=2&&!field.readonly?Kind::Slider:Kind::Row,i);
  if(field.show==2&&field.kind<=2){c.box(listX+listW*.55f,y+57,listW*.39f,4,muted);}
 }
 if(int(rows.size())>shown){c.button(listX+listW-110,top-55,48,48,"^",Kind::ScrollUp);c.button(listX+listW-54,top-55,48,48,"v",Kind::ScrollDown);}
 const auto* focused=form.field();
 if(!form.edit.error.empty())c.label(18,c.h-104,15,form.edit.error,accent,false,c.w-36);
 else if(focused&&!focused->help.empty())c.label(18,c.h-104,15,focused->help,muted,false,c.w-36);
 footer(c,false);
}
bool paint(int width,int height,std::vector<PhonepadRect>* rects,std::vector<bitmaptext::Quad>* glyphs){
 auto& host=wfprops::host();host.checkOwner();syncSession(host);state.targets.clear();
 if(!state.enabled||!host.modal||width<=0||height<=0)return false;
 if(host.picker&&host.pick==wfprops::PickMode::Scene)return false;
 float d=density(),top=state.top/d;
 Canvas c{width,height,d,width/d,std::max(200.f,(height-state.top-state.bottom)/d),top,rects,glyphs};
 c.box(0,0,c.w,c.h,bg);
 if(host.picker)renderChooser(c,host);else renderForm(c,host.form);
 return true;
}
void slider(wfprops::Form& form,const wfprops::Field& field,float x,float width,float left){
 if(field.readonly)return;
 double fraction=std::max(0.f,std::min(1.f,(x-left)/width));
 if(field.kind==1){double scale=field.scale?field.scale:1;double raw=field.minimum+std::round(fraction*(field.maximum-field.minimum));form.edit.set(field.id,std::to_string(raw/scale));}
 else form.edit.set(field.id,std::to_string(field.minimum+int(std::round(fraction*(field.maximum-field.minimum)))));
}
void activate(const Target& target,float x){
 auto& host=wfprops::host();if(!host.modal)return;
 auto& form=host.form;
 switch(target.kind){
 case Kind::Back: if(state.choiceMenu||state.sectionMenu){state.choiceMenu=state.sectionMenu=false;}else host.back();break;
 case Kind::Apply:host.apply();break;
 case Kind::Cancel:host.close();break;
 case Kind::SectionMenu:state.sectionMenu=true;state.firstChoice=0;break;
 case Kind::Section:form.section=size_t(target.index);form.row=0;state.sectionMenu=false;state.firstRow=0;break;
 case Kind::ScrollUp: if(host.picker||state.choiceMenu||state.sectionMenu)state.firstChoice=std::max(0,state.firstChoice-1);else state.firstRow=std::max(0,state.firstRow-1);break;
 case Kind::ScrollDown: if(host.picker||state.choiceMenu||state.sectionMenu)++state.firstChoice;else ++state.firstRow;break;
 case Kind::PickScene:host.enterPick();break;
 case Kind::Owner:if(target.index>0&&size_t(target.index-1)<host.owners.size())host.openOwner(host.owners[size_t(target.index-1)].actor);break;
 case Kind::GroupOwner:if(size_t(target.index)<host.group.size())host.openOwner(host.group[size_t(target.index)]);break;
 case Kind::Choice:{if(target.row>=0)form.row=size_t(target.row);const auto* field=form.field();if(field&&!field->readonly)form.edit.set(field->id,std::to_string(field->minimum+target.index));state.choiceMenu=false;break;}
 case Kind::Row:
 case Kind::Slider:{
  if(form.section>=form.sections.size()||size_t(target.index)>=form.sections[form.section].size())break;
  form.row=size_t(target.index);const auto* field=form.field();if(!field||field->readonly||field->kind==10)break;
  if(target.kind==Kind::Slider){slider(form,*field,x,target.box.x1-target.box.x0,target.box.x0);break;}
  if(field->kind==9){if(form.action)form.action(field->key);}
  else if(field->kind==4)form.edit.set(field->id,form.value()=="1"?"0":"1");
  else if(field->kind==2){state.choiceMenu=true;state.firstChoice=0;}
  else if(colour(field)){form.drawer=true;openColour(form,controls(form));}
  else if(field->kind!=8){form.drawer=true;syncText(form);}
  break;}
 case Kind::Palette:{auto& ui=controls(form);if(target.index>=0&&target.index<16)colourValues(ui,palette()[size_t(target.index)]);break;}
 case Kind::ColourCustom:{auto& ui=controls(form);if(ui.page==0){ui.page=1;break;}float side=target.box.x1-target.box.x0;
  ui.hue=(x-target.box.x0)/side*360;ui.saturation=1-std::max(0.f,std::min(1.f,(state.lastY-target.box.y0)/side));ui.preview=hsv(ui.hue,ui.saturation,ui.value);break;}
 case Kind::ColourValue:{auto& ui=controls(form);ui.value=std::max(0.f,std::min(1.f,(x-target.box.x0)/(target.box.x1-target.box.x0)));ui.preview=hsv(ui.hue,ui.saturation,ui.value);break;}
 case Kind::ColourDetails:{auto& ui=controls(form);if(ui.page!=2){ui.page=2;break;}colourText(form,ui,target.index);break;}
 case Kind::ColourUse:finishColour(form,controls(form),true);break;
 case Kind::ColourCancel:finishColour(form,controls(form),false);break;
 case Kind::Entry:break;
 }
}
}

void touchConfigure(bool enabled,float densityValue){state.enabled=enabled;state.density=std::max(.5f,densityValue);if(!enabled)touchReset();}
void touchInsets(int topPixels,int bottomPixels){state.top=std::max(0,topPixels);state.bottom=std::max(0,bottomPixels);}
bool touchEnabled(){return state.enabled;}
void touchReset(){state.pointer=-1;state.targets.clear();state.sectionMenu=state.choiceMenu=false;state.session=0;}
TouchRect touchEntryRect(int width,int height){float d=density(),w=width/d,h=(height-state.top-state.bottom)/d,top=state.top/d;return {(w-122)*d,(top+16)*d,(w-12)*d,(top+std::min(h-12,68.f))*d};}
bool buildTouchHost(int width,int height,std::vector<PhonepadRect>& rects,std::vector<bitmaptext::Quad>* glyphs){return paint(width,height,&rects,glyphs);}
bool touchEvent(TouchPhase phase,int pointer,float x,float y,int width,int height){
 if(!state.enabled)return false;
 auto& host=wfprops::host();host.checkOwner();
 if(phase==TouchPhase::Cancel){touchReset();return host.modal;}
 if(!host.modal){
  if(!host.available())return false;
  if(phase==TouchPhase::Down&&touchEntryRect(width,height).contains(x,y)){if(state.pointer<0)state.pointer=pointer;return true;}
  if(pointer!=state.pointer)return false;
  if(phase==TouchPhase::Up){state.pointer=-1;if(touchEntryRect(width,height).contains(x,y)){host.open();return true;}}
  return true;
 }
 if(host.picker&&host.pick==wfprops::PickMode::Scene){
  if(phase==TouchPhase::Up){float d=density();if(y>height-state.bottom-70*d)host.back();else if(host.pickHover(x*1920.f/width,y*1080.f/height))host.pickOk();}return true;
 }
 paint(width,height,nullptr,nullptr);
 float d=density(),px=x/d,py=(y-state.top)/d;
 if(phase==TouchPhase::Down){if(state.pointer<0){state.pointer=pointer;state.downX=px;state.downY=state.lastY=py;state.moved=false;}return true;}
 if(pointer!=state.pointer)return true;
 if(phase==TouchPhase::Move){
  state.lastY=py;
  if(std::abs(py-state.downY)>14)state.moved=true;
  for(const auto& target:state.targets)if(target.box.contains(state.downX,state.downY)&&target.kind==Kind::Slider){activate(target,px);return true;}
  if(state.moved&&std::abs(py-state.downY)>50){int step=std::max(1,int(std::abs(py-state.downY)/60));if(host.picker||state.choiceMenu||state.sectionMenu)state.firstChoice=std::max(0,state.firstChoice+(py<state.downY?step:-step));else state.firstRow=std::max(0,state.firstRow+(py<state.downY?step:-step));state.downY=py;}
  return true;
 }
 state.pointer=-1;
 if(!state.moved){for(auto it=state.targets.rbegin();it!=state.targets.rend();++it)if(it->box.contains(px,py)){activate(*it,px);break;}}
 return true;
}
}
