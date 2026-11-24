#include <wf_lifetime.hpp>
#ifdef WF_LIFETIME_DIAGNOSTICS
#include <cstdlib>
#include <new>

namespace wflifetime { void heapTrackingLinked(){} }
namespace {
void* allocate(std::size_t size,std::size_t alignment,const void* caller,bool nothrow=false){
    for(;;){
        void* p=nullptr;
        if(alignment>alignof(std::max_align_t)){
            if(posix_memalign(&p,alignment,size?size:1)!=0)p=nullptr;
        }else p=std::malloc(size?size:1);
        if(p){wflifetime::acquire(wflifetime::Kind::Heap,nullptr,reinterpret_cast<std::uintptr_t>(p),size,"C++ heap","operator new",0,caller);return p;}
        auto handler=std::get_new_handler();
        if(handler){handler();continue;}
        if(nothrow)return nullptr;
#if defined(__cpp_exceptions)
        throw std::bad_alloc();
#else
        std::abort();
#endif
    }
}
void deallocate(void* p) noexcept{
    wflifetime::release(wflifetime::Kind::Heap,nullptr,reinterpret_cast<std::uintptr_t>(p));std::free(p);
}
}
#if defined(__GNUC__) || defined(__clang__)
#define WF_HEAP_CALLER __builtin_return_address(0)
#else
#define WF_HEAP_CALLER nullptr
#endif
void* operator new(std::size_t n){return allocate(n,alignof(std::max_align_t),WF_HEAP_CALLER);}
void* operator new[](std::size_t n){return allocate(n,alignof(std::max_align_t),WF_HEAP_CALLER);}
void* operator new(std::size_t n,std::align_val_t a){return allocate(n,std::size_t(a),WF_HEAP_CALLER);}
void* operator new[](std::size_t n,std::align_val_t a){return allocate(n,std::size_t(a),WF_HEAP_CALLER);}
void operator delete(void* p) noexcept{deallocate(p);}
void operator delete[](void* p) noexcept{deallocate(p);}
void operator delete(void* p,std::size_t) noexcept{deallocate(p);}
void operator delete[](void* p,std::size_t) noexcept{deallocate(p);}
void operator delete(void* p,std::align_val_t) noexcept{deallocate(p);}
void operator delete[](void* p,std::align_val_t) noexcept{deallocate(p);}
void operator delete(void* p,std::size_t,std::align_val_t) noexcept{deallocate(p);}
void operator delete[](void* p,std::size_t,std::align_val_t) noexcept{deallocate(p);}
// Match normal allocation failure semantics when exceptions are available. Engine
// Release builds disable exceptions and deliberately terminate on exhausted heap.
void* operator new(std::size_t n,const std::nothrow_t&) noexcept{
#if defined(__cpp_exceptions)
    try{return allocate(n,alignof(std::max_align_t),WF_HEAP_CALLER,true);}catch(...){return nullptr;}
#else
    return allocate(n,alignof(std::max_align_t),WF_HEAP_CALLER,true);
#endif
}
void* operator new[](std::size_t n,const std::nothrow_t& t) noexcept{return ::operator new(n,t);}
void* operator new(std::size_t n,std::align_val_t a,const std::nothrow_t&) noexcept{
#if defined(__cpp_exceptions)
    try{return allocate(n,std::size_t(a),WF_HEAP_CALLER,true);}catch(...){return nullptr;}
#else
    return allocate(n,std::size_t(a),WF_HEAP_CALLER,true);
#endif
}
void* operator new[](std::size_t n,std::align_val_t a,const std::nothrow_t& t) noexcept{return ::operator new(n,a,t);}
void operator delete(void* p,const std::nothrow_t&) noexcept{deallocate(p);}
void operator delete[](void* p,const std::nothrow_t&) noexcept{deallocate(p);}
void operator delete(void* p,std::align_val_t,const std::nothrow_t&) noexcept{deallocate(p);}
void operator delete[](void* p,std::align_val_t,const std::nothrow_t&) noexcept{deallocate(p);}
#endif
