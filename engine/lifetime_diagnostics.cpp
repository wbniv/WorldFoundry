#include <wf_lifetime.hpp>
#ifdef WF_LIFETIME_DIAGNOSTICS
#include <cstdlib>
#include <mutex>
#include <new>
#include <dlfcn.h>
#include <cstring>

namespace wflifetime {
void heapTrackingLinked();
namespace {
struct Record {
    Kind kind; const void* domain; std::uintptr_t identity; std::size_t bytes;
    Owner owner; const char* type; const char* file; int line; const void* caller;
    Record* next;
    char image[160];std::uintptr_t offset;
};
// malloc-backed metadata bypasses intercepted C++ new. The registry deliberately
// has process lifetime, including late deletes during C++ static destruction.
struct Registry { std::mutex mutex; Record* buckets[4096]{}; Owner next=1; std::size_t failures=0; };
Registry& registry(){
    heapTrackingLinked();
    static Registry* value=[](){void* p=std::malloc(sizeof(Registry));if(!p)std::abort();return new(p) Registry; }();
    return *value;
}
thread_local Owner owner=0;
std::size_t bucket(Kind k,const void* domain,std::uintptr_t id){return ((id>>3) ^ (reinterpret_cast<std::uintptr_t>(domain)>>3) ^ unsigned(k))%4096;}
const char* kindName(Kind k){switch(k){case Kind::Object:return "object";case Kind::Pool:return "pool";case Kind::Heap:return "heap";case Kind::Graphics:return "graphics";}return "?";}
void print(FILE* out,const Record& r,const char* event){
    std::fprintf(out,"LIFETIME %s owner=%llu kind=%s type=%s identity=%p domain=%p bytes=%zu source=%s:%d caller=%p image=%s offset=0x%zx\n",event,
                 (unsigned long long)r.owner,kindName(r.kind),r.type,(void*)r.identity,r.domain,r.bytes,r.file?r.file:"?",r.line,r.caller,r.image,std::size_t(r.offset));
}
}
Owner current(){return owner;}
Owner exchange(Owner v){Owner old=owner;owner=v;return old;}
Owner beginLevel(int level){auto& s=registry();std::lock_guard<std::mutex> lock(s.mutex);if(s.next==UINT32_MAX){std::fprintf(stderr,"LIFETIME generation-space-exhausted\n");std::abort();}Owner result=++s.next;
    std::fprintf(stderr,"LIFETIME begin owner=%llu level=%d\n",(unsigned long long)result,level);return result;}
void acquire(Kind kind,const void* domain,std::uintptr_t identity,std::size_t bytes,const char* type,const char* file,int line,const void* caller){
    if(!identity||!owner)return;
    char image[160]{};std::uintptr_t offset=0;
    if(caller){Scope resolver(0);Dl_info info{};if(dladdr(caller,&info)&&info.dli_fname){
        const char* name=std::strrchr(info.dli_fname,'/');name=name?name+1:info.dli_fname;
        std::strncpy(image,*name?name:"<main>",sizeof(image)-1);
        offset=reinterpret_cast<std::uintptr_t>(caller)-reinterpret_cast<std::uintptr_t>(info.dli_fbase);
    }}
    auto& s=registry();std::lock_guard<std::mutex> lock(s.mutex);auto index=bucket(kind,domain,identity);
    for(auto* r=s.buckets[index];r;r=r->next)if(r->kind==kind&&r->domain==domain&&r->identity==identity){
        ++s.failures;print(stderr,*r,"duplicate-acquire");return;}
    auto* r=static_cast<Record*>(std::malloc(sizeof(Record)));
    if(!r){std::fprintf(stderr,"LIFETIME tracking-metadata-out-of-memory\n");std::abort();}
    *r={kind,domain,identity,bytes,owner,type,file,line,caller,s.buckets[index],{},0};
    std::memcpy(r->image,image,sizeof(image));r->offset=offset;
    s.buckets[index]=r;
}
void release(Kind kind,const void* domain,std::uintptr_t identity,bool require){
    if(!identity)return;
    auto& s=registry();std::lock_guard<std::mutex> lock(s.mutex);auto** link=&s.buckets[bucket(kind,domain,identity)];
    while(*link){auto* r=*link;if(r->kind==kind&&r->domain==domain&&r->identity==identity){*link=r->next;std::free(r);return;}link=&r->next;}
    // Optional release is needed for allocations created outside tracked scopes.
    if(require){++s.failures;std::fprintf(stderr,"LIFETIME unknown-release kind=%s identity=%p domain=%p\n",kindName(kind),(void*)identity,domain);}
}
bool beforeArenaRelease(const void* arena,const void* begin,const void* end,bool bulkBlocks){
    auto& s=registry();std::lock_guard<std::mutex> lock(s.mutex);bool clean=true;
    const auto low=reinterpret_cast<std::uintptr_t>(begin),high=reinterpret_cast<std::uintptr_t>(end);
    for(auto& head:s.buckets){auto** link=&head;while(*link){auto* r=*link;
        bool invalidated=(r->kind==Kind::Pool&&r->domain==arena)||(r->kind==Kind::Object&&r->identity>=low&&r->identity<high);
        if(invalidated){
            if(r->kind!=Kind::Pool||!bulkBlocks){clean=false;++s.failures;print(stderr,*r,"arena-survivor");}
            *link=r->next;std::free(r);
        }else link=&r->next;
    }}
    return clean;
}
void resize(Kind kind,const void* domain,std::uintptr_t identity,std::size_t bytes){
    auto& s=registry();std::lock_guard<std::mutex> lock(s.mutex);
    for(auto* r=s.buckets[bucket(kind,domain,identity)];r;r=r->next)
        if(r->kind==kind&&r->domain==domain&&r->identity==identity){r->bytes=bytes;return;}
}
void discardGraphics(const void* domain){
    auto& s=registry();std::lock_guard<std::mutex> lock(s.mutex);
    for(auto& head:s.buckets){auto** link=&head;while(*link){auto* r=*link;if(r->kind==Kind::Graphics&&r->domain==domain){
        print(stderr,*r,"context-discard");*link=r->next;std::free(r);}else link=&r->next;}}
}
Summary inspect(Owner wanted,FILE* output){auto& s=registry();std::lock_guard<std::mutex> lock(s.mutex);Summary result;result.errors=s.failures;
    for(auto* head:s.buckets)for(auto* r=head;r;r=r->next)if(r->owner==wanted){++result.records;result.bytes+=r->bytes;if(output)print(output,*r,"survivor");}
    return result;
}
bool endLevel(Owner wanted){auto summary=inspect(wanted,stderr);auto persistent=inspect(Persistent);
    std::fprintf(stderr,"LIFETIME end owner=%llu live=%zu bytes=%zu errors=%zu persistent-live=%zu persistent-bytes=%zu\n",(unsigned long long)wanted,summary.records,summary.bytes,summary.errors,persistent.records,persistent.bytes);
    return !summary.records&&!summary.errors;
}
std::size_t errors(){auto& s=registry();std::lock_guard<std::mutex> lock(s.mutex);return s.failures;}
bool shutdown(){auto& s=registry();std::lock_guard<std::mutex> lock(s.mutex);std::size_t live=0;
    for(auto* head:s.buckets)for(auto* r=head;r;r=r->next){++live;print(stderr,*r,"shutdown-survivor");}
    std::fprintf(stderr,"LIFETIME shutdown live=%zu errors=%zu\n",live,s.failures);return !live&&!s.failures;
}
}
#endif

#ifdef WF_LIFETIME_DIAGNOSTICS
namespace {
// Register before ordinary C++ static objects, so this callback runs after
// their destructors. Never assert: Release diagnostics must fail too.
struct LifetimeShutdown {
    LifetimeShutdown(){}
    ~LifetimeShutdown(){if(!wflifetime::shutdown()){std::fflush(stderr);std::_Exit(86);}}
};
#if defined(__GNUC__) || defined(__clang__)
__attribute__((init_priority(101)))
#endif
LifetimeShutdown lifetimeShutdown;
}
#endif
