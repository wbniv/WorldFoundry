#pragma once
#include "runtime_property_host.hpp"
#include <memory>

namespace wfoptions {
struct Value {
    std::string value;
    bool editable=false;
    std::string reason;
    bool operator==(const Value& other) const {return value==other.value&&editable==other.editable&&reason==other.reason;}
};
using Snapshot=std::map<std::string,Value>;
using Changes=std::map<std::string,std::string>;
struct Backend {
    std::function<Snapshot()> read;
    // Prepare all fallible resources without touching process globals.
    std::function<bool(const Changes&,std::string&)> prepare;
    // Game-thread commit after Edit::commit; all work here must be infallible.
    std::function<void(const Changes&)> apply;
};
inline void install(wfprops::Registry& registry,Backend backend) {
    struct Session {Snapshot snapshot;Changes changes;};
    auto session=std::make_shared<Session>();
    std::map<std::pair<uint32_t,uint32_t>,wfprops::Field> authoredFields;
    for(auto actor:registry.editableObjects()) {
        auto* object=registry.object(actor);
        if(object->schema!="BaselineSettings")continue;
        for(const auto& field:object->fields)
            if(field.id>=1000&&field.id<1200&&field.key.compare(0,8,"runtime_")==0)
                authoredFields[{actor,field.id}]=field;
    }
    auto sync=[&registry,backend,authoredFields](){
        const auto snapshot=backend.read();
        for(auto actor:registry.editableObjects()) {
            auto* object=registry.object(actor);if(object->schema!="BaselineSettings")continue;
            bool changed=false;
            for(auto& field:object->fields) {
                if(field.id<1000||field.id>=1200||field.key.compare(0,8,"runtime_"))continue;
                auto found=snapshot.find(field.key);
                Value effective=found==snapshot.end()?Value{"unavailable",false,"No effective runtime accessor"}:found->second;
                // Restore authored typing when a previously unsupported value
                // returns to range, while retaining its actual diagnostic value.
                auto authoredField=authoredFields.find({actor,field.id});
                if(authoredField==authoredFields.end())continue;
                auto previous=field;
                field=authoredField->second;
                if(wfprops::validate(field,effective.value)){field.kind=3;field.show=0;field.width=256;field.minimum=0;field.maximum=4096;field.maxLength=4096;effective.editable=false;effective.reason="Effective value outside editable range; "+effective.reason;}
                if(object->values[field.id]!=effective.value){object->values[field.id]=effective.value;changed=true;}
                field.readonly=!effective.editable;
                const auto marker=field.help.find(" | Effective: ");
                const auto authored=field.help.substr(0,marker);
                auto help=authored+" | Effective: "+(effective.reason.empty()?"live on Apply":effective.reason);
                field.help=std::move(help);
                if(field.kind!=previous.kind||field.readonly!=previous.readonly||field.help!=previous.help)changed=true;
            }
            if(changed)++object->revision;
        }
    };
    wfprops::Consumer consumer;
    consumer.beforeOpen=[backend,session,sync](){sync();session->snapshot=backend.read();session->changes.clear();};
    consumer.beforeCommit=[backend,session](wfprops::Form& form,const std::string& action){
        if(action!="apply"||!form.edit.validate())return false;
        if(backend.read()!=session->snapshot){form.edit.error="Runtime options changed; reopen the editor";return false;}
        session->changes.clear();
        const auto* object=form.edit.object();
        for(const auto& field:object->fields) {
            if(field.id<1000||field.id>=1200||field.key.compare(0,8,"runtime_"))continue;
            const auto draft=form.edit.draft.find(field.id);const auto original=object->get(field.id);
            if(draft==form.edit.draft.end()||!original)return false;
            if(draft->second==*original)continue;
            auto value=session->snapshot.find(field.key);
            if(field.readonly||value==session->snapshot.end()||!value->second.editable){form.edit.error="Runtime option is read-only";return false;}
            session->changes[field.key]=draft->second;
        }
        return session->changes.empty()||backend.prepare(session->changes,form.edit.error);
    };
    consumer.committed=[backend,session,sync](const wfprops::Object&,const std::string&){
        if(!session->changes.empty())backend.apply(session->changes);
        session->changes.clear();sync();
    };
    wfprops::host().consumer("BaselineSettings",std::move(consumer));
    sync();
}
// Production adapter, registered when a baseline catalog binds to its level.
void surfaceSize(int width,int height);
void registerBaseline(wfprops::Registry& registry);
}
