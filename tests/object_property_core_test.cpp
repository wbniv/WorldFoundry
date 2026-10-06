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
    wfprops::Form form;assert(form.begin(r,1,1));assert(form.sections.size()==1);
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
