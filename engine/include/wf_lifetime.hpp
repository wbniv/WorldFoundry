#ifndef WF_LIFETIME_HPP
#define WF_LIFETIME_HPP
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>

// Ownership diagnostics, independent of DO_ASSERTIONS and NDEBUG. Generation 1
// is explicit process lifetime; 0 is outside the instrumented ownership scope.
namespace wflifetime {
// Keep tokens compatible with the engine arenas' 4-byte ARM32 alignment.
using Owner = std::uint32_t;
constexpr Owner Persistent = 1;
enum class Kind { Object, Pool, Heap, Graphics };
struct Summary { std::size_t records=0, bytes=0, errors=0; };
#ifdef WF_LIFETIME_DIAGNOSTICS
Owner current();
Owner exchange(Owner);
Owner beginLevel(int level);
void acquire(Kind, const void* domain, std::uintptr_t identity, std::size_t bytes,
             const char* type, const char* file, int line, const void* caller=nullptr);
void release(Kind, const void* domain, std::uintptr_t identity, bool require=false);
// Check *before* backing storage is invalidated; retain errors even when the
// corresponding diagnostic records must be retired to avoid address reuse.
bool beforeArenaRelease(const void* arena, const void* begin, const void* end, bool bulkBlocks=false);
void resize(Kind,const void* domain,std::uintptr_t identity,std::size_t bytes);
void discardGraphics(const void* domain); // driver already discarded the context
Summary inspect(Owner, FILE* output=nullptr);
bool endLevel(Owner); // reports, does not discard survivors or reassign ownership
bool shutdown();
std::size_t errors();
#else
inline Owner current(){return 0;}
inline Owner exchange(Owner){return 0;}
inline Owner beginLevel(int){return 0;}
inline void acquire(Kind,const void*,std::uintptr_t,std::size_t,const char*,const char*,int,const void* =nullptr){}
inline void release(Kind,const void*,std::uintptr_t,bool=false){}
inline bool beforeArenaRelease(const void*,const void*,const void*,bool=false){return true;}
inline void resize(Kind,const void*,std::uintptr_t,std::size_t){}
inline void discardGraphics(const void*){}
inline Summary inspect(Owner,FILE* =nullptr){return {};}
inline bool endLevel(Owner){return true;}
inline bool shutdown(){return true;}
inline std::size_t errors(){return 0;}
#endif
inline void* allocateExternal(std::size_t bytes,const char* type,const char* file,int line){
    void* p=std::malloc(bytes);
    acquire(Kind::Heap,nullptr,reinterpret_cast<std::uintptr_t>(p),bytes,type,file,line);
    return p;
}
inline void freeExternal(void* p){release(Kind::Heap,nullptr,reinterpret_cast<std::uintptr_t>(p));std::free(p);}
class Scope {
    Owner previous;
public:
    explicit Scope(Owner owner):previous(exchange(owner)){}
    ~Scope(){exchange(previous);}
    Scope(const Scope&)=delete; Scope& operator=(const Scope&)=delete;
};
#ifdef WF_LIFETIME_DIAGNOSTICS
class Object {
public:
    Object(const char* type,const char* file,int line):type_(type),file_(file),line_(line),owner_(current()?current():Persistent){Scope objectOwner(owner_);acquire(Kind::Object,nullptr,reinterpret_cast<std::uintptr_t>(this),0,type,file,line);}
    ~Object(){release(Kind::Object,nullptr,reinterpret_cast<std::uintptr_t>(this),owner_!=0);}
    Object(const Object& other):Object(other.type_,other.file_,other.line_){}
    Object& operator=(const Object&){return *this;}
private:
    const char* type_; const char* file_; int line_;Owner owner_;
};
static_assert(alignof(Object)<=alignof(void*), "Lifetime tokens must not raise arena object alignment");
#endif
}
#ifdef WF_LIFETIME_DIAGNOSTICS
#define WF_LIFETIME_OBJECT(type) wflifetime::Object _lifetimeObject{type,__FILE__,__LINE__};
#else
#define WF_LIFETIME_OBJECT(type)
#endif
#endif
