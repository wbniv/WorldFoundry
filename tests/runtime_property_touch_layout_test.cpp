// The touch settings form on a short landscape phone, and its sliders. Will, 2026-11-22: the form "is too big and
// unusable" (one field fitted on a Pixel held sideways) and "range sliders don't have any sort of ticks".
// Usage: touch_layout <catalog> <ui-font.wfga>. Built by tests/test_touch_settings_layout.py.
#include "fixture_registry.hpp"
#include <game/runtime_property_touch.h>
#include <game/runtime_property_controls.h>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>

static const propertyui::DrawnRow* drawnRow(uint32_t id){for(const auto& row:propertyui::drawnRows())if(row.field==id)return &row;return nullptr;}
int main(int argc,char** argv){
 assert(argc==3);
 static std::vector<uint8_t> atlas;{std::ifstream font(argv[2],std::ios::binary);atlas.assign(std::istreambuf_iterator<char>(font),{});}
 {const char* fontError=nullptr;assert(wfui::Load(atlas.data(),atlas.size(),fontError));}
 std::ifstream file(argv[1],std::ios::binary);
 std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(file)),{});
 wfprops::Registry registry;std::string error;assert(testfixture::load(registry,bytes.data(),bytes.size(),error));
 auto owners=registry.editableObjects();assert(!owners.empty());
 auto* object=registry.object(owners.front());assert(object);
 object->fields.clear();object->values.clear();
 // Eight integer sliders 0..4 (five steps each), so there is more to show than a short screen can hold.
 for(uint32_t i=0;i<8;++i){
  wfprops::Field field;field.id=301+i;field.key=field.label="Slider "+std::to_string(i+1);field.show=2;field.kind=0;
  field.minimum=0;field.maximum=4;field.width=4;field.initial="1";
  object->fields.push_back(field);object->values[field.id]=field.initial;
 }
 auto& host=wfprops::host();host.bind(&registry);
 host.consumer(object->schema,wfprops::Consumer{{},{},[](const wfprops::Object&,const std::string&){}});
 // A Pixel 8 Pro as the standalone app saw it held sideways: 2244 x 1008 px at density 2.25, so 997 x 448 dp.
 constexpr int w=2244,h=1008;constexpr float density=2.25f;
 propertyui::touchConfigure(true,density);
 auto tap=[&](float x,float y,int pointer=7){
  assert(propertyui::touchEvent(propertyui::TouchPhase::Down,pointer,x,y,w,h));
  assert(propertyui::touchEvent(propertyui::TouchPhase::Up,pointer,x,y,w,h));};
 auto entry=propertyui::touchEntryRect(w,h);tap((entry.x0+entry.x1)/2,(entry.y0+entry.y1)/2);
 assert(host.modal&&!host.picker);
 std::vector<PhonepadRect> rects;assert(propertyui::buildTouchHost(w,h,rects,nullptr)&&rects.size()>3);

 // 1. More than the single field the unscaled phone layout fitted, and nothing drawn off the screen.
 int shown=0;for(uint32_t i=0;i<8;++i)if(drawnRow(301+i))++shown;
 std::printf("rows shown on a short landscape screen: %d\n",shown);
 assert(shown>=4);
 for(const auto& r:rects){assert(r.y0>=-1&&r.y1<=h+1&&r.x0>=-1&&r.x1<=w+1);}

 // 2. The layout scale the form uses on this screen (propertyui's layoutDensity): usable dp / 600, floor 0.72.
 const float usable=h/density,deff=density*std::max(.72f,usable/600.f);
 assert(deff<density&&deff>=density*.72f-1e-3f);   // shrunk, within the floor

 // 3. Ticks: a narrow tall box at every step of every shown slider (five for 0..4).
 int ticks=0;for(const auto& r:rects){const float tw=r.x1-r.x0,th=r.y1-r.y0;if(std::abs(tw-2*deff)<1.5f&&std::abs(th-18*deff)<1.5f)++ticks;}
 std::printf("tick marks: %d for %d sliders\n",ticks,shown);
 assert(ticks==5*shown);

 // 4. A tap 75% along the bar sets the value to 3 of 0..4: the tap maps along the bar, not along the whole row.
 const auto* row=drawnRow(301);assert(row);
 const float sx=row->x0+(row->x1-row->x0)*.55f,sw=(row->x1-row->x0)*.39f;
 tap((sx+sw*.75f)*deff,(row->y0+57)*deff);
 assert(host.form.edit.draft.count(301));
 std::printf("tap 75%% along the bar sets: %s\n",host.form.edit.draft.at(301).c_str());
 assert(host.form.edit.draft.at(301)=="3");
 // ...and at the left end of the bar it sets the minimum (it set 55% of the range before).
 tap((sx+2)*deff,(row->y0+57)*deff);assert(host.form.edit.draft.at(301)=="0");
 tap((sx+sw-2)*deff,(row->y0+57)*deff);assert(host.form.edit.draft.at(301)=="4");

 host.close();propertyui::textHost()=propertyui::TextHost{};propertyui::touchConfigure(false,1);
 std::printf("touch_layout: ok\n");
 return 0;
}
