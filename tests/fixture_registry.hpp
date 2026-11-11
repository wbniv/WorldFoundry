// Test-only decoder for the compact synthetic property fixtures used by UI tests.
#pragma once
#include "../engine/runtime_properties.hpp"
#include <cstring>

namespace testfixture {
struct Reader {
    const uint8_t* p; size_t left; bool valid=true;
    uint32_t number(){if(left<4){valid=false;return 0;}uint32_t n=uint32_t(p[0])|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24;p+=4;left-=4;return n;}
    uint8_t byte(){if(!left){valid=false;return 0;}--left;return *p++;}
    std::string text(){uint32_t n=number();if(!valid||n>left||n>65536){valid=false;return {};}std::string s(reinterpret_cast<const char*>(p),n);p+=n;left-=n;return s;}
};
inline bool load(wfprops::Registry& target,const uint8_t* data,size_t size,std::string& error){
    if(size<8||std::memcmp(data,"RP01",4)){error="Unsupported fixture";return false;}
    Reader r{data+4,size-4};uint32_t count=r.number();if(count>4096){error="Too many objects";return false;}
    wfprops::Registry loaded;
    for(uint32_t i=0;i<count&&r.valid;i++){
        wfprops::Object o;o.actor=r.number();o.schema=r.text();o.title=r.text();uint32_t n=r.number();
        if(!o.actor||n>16384){r.valid=false;break;}
        for(uint32_t j=0;j<n&&r.valid;j++){
            wfprops::Field f;f.id=r.number();f.kind=r.byte();f.show=r.byte();f.readonly=r.byte();f.rule=r.byte();
            f.minimum=int32_t(r.number());f.maximum=int32_t(r.number());f.scale=r.number();f.width=r.number();f.maxLength=r.number();
            f.key=r.text();f.label=r.text();f.help=r.text();f.group=r.text();f.choices=r.text();f.initial=r.text();
            if(f.kind>10||f.id>32767||(f.stored()&&(!f.id||o.values.count(f.id)||wfprops::validate(f,f.initial)))){r.valid=false;break;}
            if(f.stored())o.values[f.id]=f.initial;
            o.fields.push_back(std::move(f));
        }
        if(r.valid&&!loaded.add(std::move(o),error))r.valid=false;
    }
    if(!r.valid||r.left){error="Malformed fixture";return false;}
    target=std::move(loaded);error.clear();return true;
}
}
