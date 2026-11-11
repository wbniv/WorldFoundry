#include "fixture_registry.hpp"
#include <game/runtime_property_touch.h>
#include <game/runtime_property_controls.h>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <string>

// Usage: touch <catalog> <id> <type> <show> <expected drawn control> <ui-font.wfga>
static const propertyui::DrawnRow* drawnRow(uint32_t id){for(const auto& row:propertyui::drawnRows())if(row.field==id)return &row;return nullptr;}
static int drawnCount(const std::string& control,int lines=0){int n=0;for(const auto& row:propertyui::drawnRows())if(row.control==control&&(!lines||row.lines==lines))++n;return n;}
int main(int argc,char** argv){
 assert(argc==7);
 const std::string id=argv[2],type=argv[3],expected=argv[5];const int show=std::atoi(argv[4]);
 // wfui::Load keeps a pointer into the atlas bytes: they must outlive every measurement.
 static std::vector<uint8_t> atlas;{std::ifstream font(argv[6],std::ios::binary);atlas.assign(std::istreambuf_iterator<char>(font),{});}
 {const char* fontError=nullptr;assert(wfui::Load(atlas.data(),atlas.size(),fontError));}
 std::ifstream file(argv[1],std::ios::binary);
 std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(file)),{});
 wfprops::Registry registry;std::string error;assert(testfixture::load(registry,bytes.data(),bytes.size(),error));
 auto owners=registry.editableObjects();assert(!owners.empty());
 auto* object=registry.object(owners.front());assert(object);
 object->fields.clear();object->values.clear();
 wfprops::Field field;field.id=301;field.key=field.label=id;field.show=uint8_t(show);
 field.kind=type.find("Float")==0?1:type.find("Enum")==0?2:type.find("Bool")==0?4:
            type.find("Str")==0?3:type.find("FileRef")==0?8:id=="action"?9:id=="spacer"?10:0;
 field.minimum=0;field.maximum=100;field.scale=100;field.width=4;field.maxLength=64;
 field.initial="30";
 if(field.kind==1)field.initial="0.3";
 if(field.kind==2){field.minimum=3;field.maximum=id=="enum-many"?14:5;field.initial="3";field.choices="First|Second|Third";
  if(id=="enum-many")field.choices="A|B|C|D|E|F|G|H|I|J|K|L";
  // Field types' own options: two segments, and labels too long for one line.
  if(id=="enum-radio"){field.maximum=4;field.choices="Freshwater|Saltwater";}
  if(id=="enum-toggle"){field.maximum=4;field.choices="Forward|Reverse";}
  // Wider than a 390 dp sheet at 18 sp, so they must wrap (Field types' own fit there).
  if(id=="enum-long")field.choices="Along the northern wall of the tank, facing the front glass|In the middle of the tank, directly under the main light|Beside the filter intake, tucked behind the large rocks";}
 if(field.kind==4){field.maximum=1;field.initial="0";}
 if(field.kind==3){field.initial="Original";field.maxLength=256;}
 if(id=="str-filename")field.initial="plants/leaf.png";
 if(id=="str-uint32"){field.rule=1;field.initial="713";field.maxLength=10;}
 if(id=="str-multiline")field.rule=2;
 if(id=="int-color"){field.maximum=0xffffff;field.initial="5801868";}
 if(id=="int-readonly"||field.kind==8)field.readonly=1;
 if(field.kind==9){field.key="regenerate";field.initial="";}
 if(id=="int-help"){wfprops::Field group;group.kind=6;group.label="Lighting";object->fields.push_back(group);field.help="Controls scene brightness";}
 object->fields.push_back(field);object->values[field.id]=field.initial;
 if(field.readonly||field.kind==10){wfprops::Field extra;extra.id=302;extra.kind=0;extra.minimum=0;extra.maximum=10;extra.key=extra.label="Editable";extra.initial="1";object->fields.push_back(extra);object->values[extra.id]="1";}
 auto& host=wfprops::host();host.bind(&registry);
 bool acted=false;host.consumer(object->schema,wfprops::Consumer{{},{},[&](const wfprops::Object&,const std::string&){acted=true;}});
 propertyui::touchConfigure(true,2);
 constexpr int w=780,h=1688;
 auto tap=[&](float x,float y,int pointer=7){
  assert(propertyui::touchEvent(propertyui::TouchPhase::Down,pointer,x,y,w,h));
  assert(propertyui::touchEvent(propertyui::TouchPhase::Up,pointer,x,y,w,h));};
 auto entry=propertyui::touchEntryRect(w,h);tap((entry.x0+entry.x1)/2,(entry.y0+entry.y1)/2);
 assert(host.modal&&!host.picker);
 std::vector<PhonepadRect> rects;assert(propertyui::buildTouchHost(w,h,rects,nullptr)&&rects.size()>3);
 // The row draws its own control: segments, switch, checkbox, path, bounds, numbered id...
 const auto* row=drawnRow(301);
 if(!row||row->control!=expected){std::fprintf(stderr,"%s: drawn %s, expected %s\n",id.c_str(),row?row->control.c_str():"nothing",expected.c_str());return 1;}
 const propertyui::DrawnRow rowBox=*row;
 int shows=0;propertyui::TextRequest request;
 propertyui::textHost().show=[&](const propertyui::TextRequest& value){request=value;++shows;return true;};
 propertyui::textHost().hide=[](uint64_t){};
 const std::string before=host.form.value();
 if(expected=="segments"){
  // Tap the second segment: it is chosen directly; no sheet opens.
  const float cw=(rowBox.x1-rowBox.x0-24-10)/2;tap((rowBox.x0+12+cw+10+cw/2)*2,(rowBox.y0+54)*2);
  std::vector<PhonepadRect> after;assert(propertyui::buildTouchHost(w,h,after,nullptr));
  assert(host.form.value()=="4"&&drawnCount("sheet-option")==0);
 }else tap(show==2?700:150,375);
 if(expected=="segments"){}
 else if(field.kind==2&&show!=2){assert(host.form.value()==before);
  // The sheet is open: ids for a numbered list; long options wrap to two lines.
  std::vector<PhonepadRect> sheet;assert(propertyui::buildTouchHost(w,h,sheet,nullptr));
  if(expected=="numbered-choice-list")assert(drawnCount("sheet-option-numbered")>=3);
  else assert(drawnCount("sheet-option")>=3);
  if(id=="enum-long")assert(drawnCount("sheet-option",2)==3);
  else assert(drawnCount("sheet-option",2)+drawnCount("sheet-option-numbered",2)==0);
  if(id=="enum-many"){tap(700,80);tap(700,80);tap(150,1346);assert(host.form.value()=="14");}
  else {tap(150,350);assert(host.form.value()=="4");}}
 else if(field.kind==2&&show==2){assert(host.form.value()!=before);}
 else if(field.kind==4){assert(host.form.value()=="1");}
 else if(id=="int-color"){
  assert(host.form.drawer);tap(130,210);tap(600,1500);assert(!host.form.drawer&&host.form.value()!=before);
 }else if(field.kind==9){assert(!host.modal&&acted);return 0;}
 else if(field.kind==10||field.readonly){assert(host.form.value()==before);}
 else if(show==2&&field.kind<=1){assert(host.form.value()!=before);}
 else {assert(shows==1&&host.form.drawer);
  if(expected=="number-with-bounds")assert(request.label==field.label+" (0 \xe2\x80\x93 100)");
  else assert(request.label==field.label);
  if(expected=="path"){
   // A path that is not relative stays in the draft, as every invalid draft does, and
   // Apply refuses it with the engine's message; the form stays open.
   propertyui::completeText(request.session,request.field,"../outside.png",true);
   assert(host.form.value()=="../outside.png"&&!host.form.drawer);
   assert(!host.apply());
   assert(host.modal&&host.form.edit.error==field.label+": Enter a relative path: names separated by /");
   tap(150,375);assert(shows==2&&host.form.drawer);
  }
  std::string input=field.kind==3?(field.rule==1?"4294967295":field.rule==2?"Line one\nLine two":"Updated"):field.kind==1?"0.75":"55";
  propertyui::completeText(request.session,request.field,input,true);
  assert(!host.form.drawer&&host.form.value()==input);
 }
 const std::string kept=host.form.value();
 tap(600,1545);assert(!host.modal&&acted);
 assert(*object->get(301)==kept);
 if(!field.readonly&&field.kind<5){
  tap((entry.x0+entry.x1)/2,(entry.y0+entry.y1)/2);assert(host.modal);
  if(field.kind==4)host.form.edit.set(301,kept=="1"?"0":"1");
  else if(field.kind==2)host.form.edit.set(301,kept=="3"?"4":"3");
  else if(field.kind==3)host.form.edit.set(301,field.rule==1?"123":"Unsaved");
  else host.form.edit.set(301,field.kind==1?"0.2":"20");
  tap(150,1545);assert(!host.modal);assert(*object->get(301)==kept);
 }
 if(id=="int-number"){
  propertyui::touchInsets(100,50);
  auto safe=propertyui::touchEntryRect(w,h);assert(safe.y0>=100);
  tap((safe.x0+safe.x1)/2,(safe.y0+safe.y1)/2);assert(host.modal);
  rects.clear();assert(propertyui::buildTouchHost(w,h,rects,nullptr));
  assert(!rects.empty()&&rects.front().y0==100);
  host.close();propertyui::touchInsets(0,0);
 }
 propertyui::textHost()=propertyui::TextHost{};
 propertyui::touchConfigure(false,1);
}
