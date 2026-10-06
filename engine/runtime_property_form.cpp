#include "runtime_property_form.hpp"
#include <algorithm>
#include <cstdlib>
namespace wfprops {
bool Form::begin(Registry& registry,uint32_t actor){
    if(!edit.begin(registry,actor))return false;
    sections.clear();titles.clear();section=row=0;rail=adjust=drawer=false;previous=0;key=0;
    auto* object=edit.object();
    for(size_t i=0;i<object->fields.size();++i){const auto& f=object->fields[i];
        if(f.kind==5){sections.emplace_back();titles.push_back(f.label);}
        else if(f.kind==6||f.kind==7)continue;
        else {if(sections.empty()){sections.emplace_back();titles.push_back("Properties");}sections.back().push_back(i);}
    }
    for(size_t i=sections.size();i>0;--i)if(sections[i-1].empty()){sections.erase(sections.begin()+i-1);titles.erase(titles.begin()+i-1);}
    return true;
}
const Field* Form::field() const {auto* o=edit.object();if(!o||section>=sections.size()||row>=sections[section].size())return nullptr;return &o->fields[sections[section][row]];}
std::string Form::value() const {const auto* f=field();if(!f)return {};auto i=edit.draft.find(f->id);return i==edit.draft.end()?"":i->second;}
void Form::change(int direction){const auto* f=field();if(!f||f->readonly)return;
    if(f->kind==4){edit.set(f->id,value()=="1"?"0":"1");return;}
    if(f->kind==2||f->kind==0){long long n=std::strtoll(value().c_str(),nullptr,10);n=std::max<long long>(f->minimum,std::min<long long>(f->maximum,n+direction));edit.set(f->id,std::to_string(n));}
    else if(f->kind==1){double scale=f->scale?f->scale:1;double n=std::strtod(value().c_str(),nullptr)+direction/scale;n=std::max(f->minimum/scale,std::min(f->maximum/scale,n));edit.set(f->id,std::to_string(n));}
}
bool Form::back(){if(drawer){drawer=false;adjust=false;return false;}return true;}
void Form::input(uint32_t buttons){uint32_t edge=buttons&~previous;previous=buttons;if(!edit.open||sections.empty())return;
    const uint32_t up=1u<<11,down=1u<<12,right=1u<<13,left=1u<<14;
    if(drawer){int x=key%3,y=key/3;if(edge&left)x=std::max(0,x-1);if(edge&right)x=std::min(2,x+1);if(edge&up)y=std::max(0,y-1);if(edge&down)y=std::min(4,y+1);key=y*3+x;
        if(edge&1){const auto* f=field();if(!f)return;std::string text=value();if(key<9||key==10||key==12||key==13){if(replaceText){text.clear();replaceText=false;}char c=key<9?'1'+key:key==10?'0':key==12?'-':'.';if(text.size()<f->maxLength)text+=c;edit.set(f->id,text);}else if(key==9){if(!text.empty())text.pop_back();replaceText=false;edit.set(f->id,text);}else if(key==11){replaceText=false;edit.set(f->id,"");}else drawer=false;}
        return;
    }
    if(adjust&&(edge&(left|right))){change(edge&right?1:-1);return;}
    if(edge&(up|down)){adjust=false;int delta=edge&down?1:-1;if(rail){section=size_t(std::max(0,std::min(int(sections.size())-1,int(section)+delta)));row=0;}else if(section<sections.size()){int next=int(row)+delta;while(next>=0&&next<int(sections[section].size())){auto* o=edit.object();if(o&&o->fields[sections[section][next]].kind!=10)break;next+=delta;}row=size_t(std::max(0,std::min(int(sections[section].size())-1,next)));}}
    if(edge&left)rail=true;if(edge&right)rail=false;
    if(!(edge&1))return;if(rail){rail=false;return;}const auto* f=field();if(!f||f->readonly)return;
    if(f->kind==9){if(action)action(f->key);return;}
    if(f->kind==10)return;
    if(f->kind==4)change(1);
    else if(f->kind==2||f->show==2)adjust=!adjust;
    else {drawer=true;replaceText=true;key=0;}
}
bool Form::command(const std::string& text){
    if(text.compare(0,2,"r:")!=0)return false;
    size_t first=text.find(':',2),second=first==std::string::npos?first:text.find(':',first+1);
    if(first==std::string::npos)return true;
    auto token=text.substr(2,first-2);if(token!=std::to_string(edit.session)||!edit.open)return true;
    std::string verb=text.substr(first+1,second==std::string::npos?std::string::npos:second-first-1);
    if(verb=="set"&&second!=std::string::npos){size_t third=text.find(':',second+1);if(third==std::string::npos)return true;std::string id=text.substr(second+1,third-second-1),decoded;if(id.empty()||id.find_first_not_of("0123456789")!=std::string::npos||id.size()>5||!decode(text.substr(third+1),decoded))return true;edit.set(uint32_t(std::strtoul(id.c_str(),nullptr,10)),decoded);}
    else if(verb=="action"&&second!=std::string::npos){auto* o=edit.object();std::string id=text.substr(second+1);if(o)for(const auto& f:o->fields)if(f.kind==9&&std::to_string(f.id)==id){if(action)action(f.key);break;}}
    else if(verb=="apply"){if(action)action("apply");}
    else if(verb=="cancel"){if(action)action("cancel");}
    return true;
}
}
