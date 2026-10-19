#include <game/runtime_property_controls.h>
#include <game/runtime_property_ui.h>
#include <cassert>
#include <fstream>
#include <iterator>
#include <set>
int main(int argc,char** argv){
 assert(argc==3);std::ifstream file(argv[1],std::ios::binary);std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(file)),{});
 wfprops::Registry registry;std::string error;assert(registry.load(bytes.data(),bytes.size(),error));auto* object=registry.object(1);assert(object);
 object->fields.clear();object->values.clear();wfprops::Field field;field.id=201;field.kind=0;field.show=7;field.width=4;field.maximum=0xffffff;field.key=field.label="Tint";field.initial="5801868";object->fields.push_back(field);object->values[field.id]=field.initial;
 field=wfprops::Field{};field.id=202;field.kind=3;field.maxLength=32;field.key=field.label="Name";field.initial="Original name";object->fields.push_back(field);object->values[field.id]=field.initial;
 field.id=205;field.rule=2;field.maxLength=4096;field.key=field.label="Notes";field.initial="First line\nSecond line";object->fields.push_back(field);object->values[field.id]=field.initial;
 wfprops::Form form;assert(form.begin(registry,1));auto press=[&](uint32_t button){propertyui::input(form,0);propertyui::input(form,button);};
 press(1);assert(form.drawer);auto& ui=propertyui::controls(form);assert(ui.colourOpen&&ui.preview==0x58878c&&ui.focus==0);press(1);assert(ui.preview==propertyui::palette()[0]&&form.value()=="5801868");
 assert(!form.back());propertyui::syncText(form);assert(!form.drawer&&form.value()=="5801868");
 press(1);ui.focus=16+int(propertyui::recentColours().size());press(1);assert(ui.page==1);press(1);assert(ui.planeAdjust);press(1u<<13);assert(ui.preview!=ui.original&&form.value()=="5801868");
 // Repeat is time-based and release stops it without affecting the form draft.
 ui.repeatButtons=1u<<13;ui.holdStart=ui.lastRepeat=std::chrono::steady_clock::now()-std::chrono::milliseconds(1400);double oldH=ui.hue;propertyui::input(form,1u<<13);assert(ui.hue>oldH);propertyui::input(form,0);oldH=ui.hue;propertyui::input(form,0);assert(ui.hue==oldH);
 assert(!form.back());propertyui::syncText(form);assert(form.drawer&&!ui.planeAdjust);double beforeV=ui.value,beforeH=ui.hue,beforeS=ui.saturation;ui.focus=1;press(1u<<13);assert(ui.value>beforeV&&ui.hue==beforeH&&ui.saturation==beforeS);press(1u<<14);assert(std::abs(ui.value-beforeV)<1e-9);assert(!form.back());propertyui::syncText(form);assert(!form.drawer&&form.value()=="5801868");
 // Palette confirmation updates only the form draft; Cancel leaves the object alone.
 press(1);ui.focus=4;press(1);assert(ui.preview==0x58a78c);ui.focus=17+int(propertyui::recentColours().size());press(1);assert(!form.drawer&&propertyui::rgb(form.value())==0x58a78c&&*object->get(201)=="5801868");assert(form.edit.commit());assert(*object->get(201)==std::to_string(0x58a78c));
 // Preserve hue through grey/black and do not change RGB just by opening.
 propertyui::colourValues(ui,0xff0000);double hue=ui.hue;propertyui::colourValues(ui,0);assert(ui.hue==hue);assert(propertyui::hsv(0,1,1)==0xff0000&&propertyui::hsv(120,1,1)==0x00ff00&&propertyui::hsv(240,1,1)==0x0000ff);
 std::vector<PhonepadRect> rects;
 auto capture=[&](const char* name){rects.clear();propertyui::build(form,false,960,540,rects);std::ofstream out(std::string(argv[2])+"/"+name+".svg");out<<"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 960 540'>";for(const auto& r:rects){assert(r.x0>=0&&r.y0>=0&&r.x1<=960&&r.y1<=540);char color[8];std::snprintf(color,sizeof(color),"#%06X",r.rgba>>8);out<<"<rect x='"<<r.x0<<"' y='"<<r.y0<<"' width='"<<r.x1-r.x0<<"' height='"<<r.y1-r.y0<<"' fill='"<<color<<"'/>";}out<<"</svg>";};
 assert(form.begin(registry,1));press(1);capture("tv-colour");ui.page=1;ui.focus=0;capture("tv-custom-colour");assert(rects.size()<10000);form.edit.cancel();
 propertyui::TextRequest request;int shows=0,hides=0;
 propertyui::textHost().show=[&](const propertyui::TextRequest& r){request=r;++shows;return true;};
 propertyui::textHost().hide=[&](uint64_t){++hides;};
 assert(form.begin(registry,1));press(1);ui.page=2;ui.focus=3;press(1);assert(ui.nativeOpen&&request.mode==0&&request.value=="#58A78C");
 propertyui::completeText(form.edit.session,201,"#123abc",true);assert(form.drawer&&ui.preview==0x123abc&&propertyui::rgb(form.value())==0x58a78c);
 press(1);propertyui::completeText(form.edit.session,201,"xyz",true);assert(ui.preview==0x123abc&&!form.edit.error.empty());
 ui.focus=0;press(1);propertyui::completeText(form.edit.session,201,"256",true);assert(ui.preview==0x123abc);press(1);propertyui::completeText(form.edit.session,201,"255",true);assert(ui.preview==0xff3abc);form.edit.cancel();shows=0;
 assert(form.begin(registry,1));form.row=1;press(1);assert(form.drawer&&request.mode==0&&request.maxLength==32&&shows==1);
 auto session=form.edit.session;press(1u<<13);assert(shows==1&&form.value()=="Original name");
 propertyui::completeText(session-1,202,"Stale",true);assert(form.drawer&&form.value()=="Original name");
 propertyui::completeText(session,202,"Goby: 50% caf\xc3\xa9!",true);assert(!form.drawer&&form.value()=="Goby: 50% caf\xc3\xa9!");
 press(1);propertyui::completeText(session,202,"Discard",false);assert(form.value()=="Goby: 50% caf\xc3\xa9!");form.edit.cancel();assert(*object->get(202)=="Original name");
 assert(form.begin(registry,1));form.row=2;press(1);assert(request.mode==2&&request.value=="First line\nSecond line");
 propertyui::completeText(form.edit.session,205,"Notes\n 50% \xf0\x9f\x8c\xb1",true);assert(!form.drawer);assert(form.edit.commit());assert(*object->get(205)=="Notes\n 50% \xf0\x9f\x8c\xb1");
 assert(form.begin(registry,1));form.row=1;press(1);propertyui::syncText(form,true);assert(!form.drawer&&hides==1);propertyui::completeText(form.edit.session,202,"Late",true);assert(form.value()=="Original name");
 assert(form.begin(registry,1));form.row=1;press(1);auto stale=form.edit.session;assert(form.begin(registry,1));propertyui::syncText(form);propertyui::completeText(stale,202,"Old form",true);assert(form.edit.draft[202]=="Original name");
 object->fields[0].readonly=1;assert(form.begin(registry,1));press(1);assert(!form.drawer&&form.value()==std::to_string(0x58a78c));assert(!form.edit.set(201,"0"));
 propertyui::textHost()=propertyui::TextHost{};form.row=1;press(1);assert(!form.drawer&&form.edit.error=="Enter text using a connected browser");
}
