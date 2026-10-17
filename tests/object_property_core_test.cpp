#include "runtime_properties.hpp"
#include "runtime_property_form.hpp"
#include <cassert>
#include <fstream>
#include <iterator>
int main(int argc,char** argv){
    assert(argc==2);std::ifstream in(argv[1],std::ios::binary);
    std::vector<uint8_t> data((std::istreambuf_iterator<char>(in)),{});
    wfprops::Registry r;std::string error;assert(r.load(data.data(),data.size(),error));
    auto* a=r.object(1);auto* b=r.object(2);assert(a&&b);
    wfprops::Edit edit;assert(edit.begin(r,1));assert(edit.set(1,"4294967295"));
    assert(*a->get(1)=="0");assert(edit.commit());assert(*a->get(1)=="4294967295"&&*b->get(1)=="0");
    assert(edit.begin(r,1));assert(edit.set(1,"4294967296"));assert(!edit.commit());assert(edit.open);
    assert(*a->get(1)=="4294967295");edit.cancel();
    assert(edit.begin(r,1));assert(edit.set(2,"1"));assert(r.set(1,3,"4",error));assert(!edit.commit());
    assert(*a->get(2)=="0");
    assert(edit.begin(r,2));r.remove(2);assert(!edit.commit());
    auto bad=data;bad.resize(15);assert(!r.load(bad.data(),bad.size(),error));assert(r.object(1));
    assert(wfprops::decode("A%3AB%25",error)&&error=="A:B%");assert(!wfprops::decode("%xy",error));
    wfprops::Form form;assert(form.begin(r,1,1));
    // Two authored sheets (Phase 3). Headers carry id 0, so no row can alias a field.
    assert(form.sections.size()==2&&form.titles.size()==2);
    assert(form.titles[0]=="Plant growth"&&form.titles[1]=="Seahorses");
    auto ids=[&](size_t s){std::vector<uint32_t> out;for(size_t i:form.sections[s])out.push_back(a->fields[i].id);return out;};
    assert((ids(0)==std::vector<uint32_t>{1,2,3,4,5,6,7}));
    assert((ids(1)==std::vector<uint32_t>{8,9,100,101,102})); // Seahorses, Greeting, then the form actions
    {const auto& pairs=a->fields[form.sections[1][0]];assert(pairs.key=="Seahorses"&&pairs.kind==2&&pairs.choices=="None|1 pair|2 pairs"&&pairs.minimum==0&&pairs.maximum==2);}
    {const auto& greeting=a->fields[form.sections[1][1]];assert(greeting.key=="Greeting"&&greeting.kind==2&&greeting.show==8&&greeting.choices=="False|True");}
    for(const auto& f:a->fields)if(f.kind==5||f.kind==6||f.kind==7)assert(f.id==0);
    form.input(1);form.input(1);assert(!form.drawer);assert(form.value()=="4294967295");
    form.input(0);assert(!form.drawer);
    form.input(1);assert(form.drawer);form.input(0);form.input(1);
    assert(form.value()=="1");assert(!form.back());assert(!form.drawer);
    form.input(0);form.input(1u<<12);assert(form.field()->id==2);
    assert(!form.adjust);form.input(0);form.input(1u<<13);assert(form.value()=="1"&&!form.rail);
    form.input(1u<<13);assert(form.value()=="1");
    form.input(0);form.input(1u<<14);assert(form.value()=="0"&&!form.rail);
    form.input(0);form.input(1u<<14);assert(form.value()=="0"&&!form.rail);
    form.input(0);form.input(1u<<12);assert(form.field()->id==3);
    form.input(0);form.input(1u<<13);assert(form.value()=="5"&&!form.adjust);
    auto session=std::to_string(form.edit.session);
    form.command("r:"+session+":set:1:1234567890");assert(form.edit.draft[1]=="1234567890");
    form.command("r:0:set:1:2");assert(form.edit.draft[1]=="1234567890");
    assert(form.back());assert(form.edit.commit());assert(*a->get(1)=="1234567890");
}
