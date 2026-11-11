#include "fixture_registry.hpp"
// The TV settings form on the baseline's real Field types catalog: what each row draws, the
// open choice lists, and the keys of the new controls (docs/plans/2026-11-01-field-presentations.md).
// Usage: presentation form <payload> <field-types actor> <ui-font.wfga>
//        presentation load <payload>      (exit 0 when the registry accepts the catalog)
#include <game/runtime_property_ui.h>
#include <game/runtime_property_controls.h>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <set>
#include <string>
static std::vector<uint8_t> slurp(const char* path){std::ifstream f(path,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};}
static constexpr uint32_t A=1,Up=1u<<11,Down=1u<<12,Right=1u<<13,Left=1u<<14;
int main(int argc,char** argv){
 assert(argc>=3);const std::string mode=argv[1];auto bytes=slurp(argv[2]);
 wfprops::Registry registry;std::string error;
 if(mode=="load"){if(!testfixture::load(registry,bytes.data(),bytes.size(),error)){std::printf("load-failed %s\n",error.c_str());return 1;}std::printf("loaded %zu\n",registry.editableObjects().size());return 0;}
 assert(argc==5&&testfixture::load(registry,bytes.data(),bytes.size(),error));
 static std::vector<uint8_t> atlas=slurp(argv[4]);{const char* fontError=nullptr;assert(wfui::Load(atlas.data(),atlas.size(),fontError));}
 const uint32_t actor=uint32_t(std::atoi(argv[3]));
 auto& host=wfprops::host();host.bind(&registry);assert(host.openOwner(actor));auto& f=host.form;
 auto press=[&](uint32_t key){propertyui::input(f,key);propertyui::input(f,0);};
 auto draw=[&](){std::vector<PhonepadRect> rects;propertyui::build(f,false,1920,1080,rects,nullptr);return rects;};
 auto focus=[&](const std::string& key){
  for(size_t s=0;s<f.sections.size();++s)for(size_t r=0;r<f.sections[s].size();++r)
   if(f.edit.object()->fields[f.sections[s][r]].key==key){f.section=s;f.row=r;f.rail=false;f.list=false;return &f.edit.object()->fields[f.sections[s][r]];}
  std::printf("missing %s\n",key.c_str());std::exit(2);};
 // 1. Every row, as drawn: focus each in turn so each section's window shows it.
 std::set<uint32_t> seen;
 for(size_t s=0;s<f.sections.size();++s)for(size_t r=0;r<f.sections[s].size();++r){
  f.section=s;f.row=r;draw();
  for(const auto& row:propertyui::drawnRows()){if(seen.count(row.field))continue;seen.insert(row.field);
   const auto* field=f.edit.object()->field(row.field);std::string key="?";for(const auto& x:f.edit.object()->fields)if(x.id==row.field)key=x.key;(void)field;
   std::printf("tv %s %s %d %.0f %.0f %.0f %.0f %zu\n",key.c_str(),row.control.c_str(),row.lines,row.x0,row.y0,row.x1,row.y1,s);}
 }
 // 2. Keys, through the one rule table (wfprops::keys): for each control, print the rule and
 //    what Left, Right and A did from the first value. The tests derive expectations from it.
 {propertyui::textHost().show=[](const propertyui::TextRequest&){return true;};propertyui::textHost().hide=[](uint64_t){};
  for(const char* key:{"int-number","int-mailbox","enum-default","enum-number","enum-dropdown","enum-combo","enum-long","enum-toggle",
                       "enum-radio","enum-slider","enum-many","bool-checkbox","bool-toggle","str-filename","float-slider"}){
   const auto* field=focus(key);const auto rule=wfprops::keys(*field);
   const std::string first=field->kind==1?std::to_string(field->minimum/double(field->scale?field->scale:1)):std::to_string(field->minimum);
   auto reset=[&](){focus(key);f.drawer=f.list=false;f.edit.set(field->id,first);propertyui::syncText(f);};
   auto changed=[&](){return std::strtod(f.value().c_str(),nullptr)!=std::strtod(first.c_str(),nullptr);};
   reset();press(Left);const bool leftRail=f.rail,leftChanged=changed();
   reset();press(Right);const bool rightChanged=changed();
   reset();press(A);const bool aList=f.list;reset();
   std::printf("keys %s %d %d %d %d probe %d %d %d %d\n",key,wfprops::optionCount(*field),int(rule.leftRightChange),int(rule.leftOnFirstToRail),int(rule.aOpensList),
               int(leftRail),int(leftChanged),int(rightChanged),int(aList));}
  propertyui::textHost()=propertyui::TextHost{};}
 // 2b. A choice row by option count (option 6): re-author Mode with 2, 4, 5 and 12 options and
 //     probe Left on the first option, Left mid-list, Right, A, and closing the open list.
 {auto* object=f.edit.object();wfprops::Field* mode=nullptr;for(auto& x:object->fields)if(x.key=="enum-default")mode=&x;assert(mode);
  const auto saved=*mode;
  for(int n:{2,4,5,12}){
   std::string labels;for(int k=0;k<n;++k)labels+=(k?"|":"")+std::string("Option ")+std::to_string(k+1);
   mode->choices=labels;mode->minimum=0;mode->maximum=n-1;
   const auto rule=wfprops::keys(*mode);
   auto reset=[&](int v){focus("enum-default");f.edit.set(mode->id,std::to_string(v));};
   reset(0);press(Left);const bool firstRail=f.rail;const std::string firstValue=f.value();
   reset(2>n-1?1:2);press(Left);const std::string midValue=f.value();const bool midRail=f.rail;
   reset(0);press(Right);const std::string rightValue=f.value();
   reset(0);press(A);const bool opened=f.list;press(Down);const bool backClosed=!f.back()&&!f.list&&f.value()=="0";
   reset(0);press(A);press(Down);press(Left);const bool leftClosed=!f.list&&!f.rail&&f.value()=="0";
   std::printf("count %d %d %d %d first %d %s mid %s %d right %s open %d back %d left %d\n",n,int(rule.leftRightChange),int(rule.leftOnFirstToRail),int(rule.aOpensList),
               int(firstRail),firstValue.c_str(),midValue.c_str(),int(midRail),rightValue.c_str(),int(opened),int(backClosed),int(leftClosed));
  }
  *mode=saved;f.edit.set(mode->id,"0");}
 // 3. The open list itself: opens on the current option, selects into the draft only, and
 //    Back or Left closes it without closing the form. Ids for a numbered list; wrapping.
 {const auto* mode_=focus("enum-default");const std::string before=f.value();press(A);std::printf("choice-a-opens %d index %zu\n",int(f.list),f.listIndex);
  draw();int options=0;for(const auto& r:propertyui::drawnRows())if(r.control=="list-option")++options;std::printf("choice-options %d\n",options);
  press(Down);press(A);std::printf("choice-selected %s->%s list %d committed %s\n",before.c_str(),f.value().c_str(),int(f.list),f.edit.object()->get(mode_->id)->c_str());
  press(A);bool open=f.list;bool closes=!f.back();std::printf("choice-back-closes %d %d list %d\n",int(open),int(closes),int(f.list));
  press(A);press(Left);std::printf("choice-left-closes %d rail %d\n",int(f.list),int(f.rail));}
 {focus("enum-number");press(A);draw();int numbered=0;for(const auto& r:propertyui::drawnRows())if(r.control=="list-option-numbered")++numbered;std::printf("numbered-options %d\n",numbered);f.back();
  focus("enum-long");press(A);draw();int wrapped=0,all=0;for(const auto& r:propertyui::drawnRows())if(r.control=="list-option"){++all;if(r.lines==2)++wrapped;}std::printf("long-options %d wrapped %d\n",all,wrapped);f.back();}
 // 6. The mailbox editor is titled with its bounds; a FILENAME value must be a relative path.
 {propertyui::TextRequest request;propertyui::textHost().show=[&](const propertyui::TextRequest& r){request=r;return true;};propertyui::textHost().hide=[](uint64_t){};
  focus("int-mailbox");press(A);std::printf("mailbox-editor %s\n",request.label.c_str());propertyui::completeText(request.session,request.field,"100",false);
  const auto* path=focus("str-filename");f.edit.set(path->id,"../outside.png");const bool refused=!f.edit.validate();std::printf("path-refused %d %s\n",int(refused),f.edit.error.c_str());
  f.edit.set(path->id,"plants/leaf.png");std::printf("path-accepted %d\n",int(f.edit.validate()));
  propertyui::textHost()=propertyui::TextHost{};}
 host.close();host.bind(nullptr);std::printf("done\n");
}
