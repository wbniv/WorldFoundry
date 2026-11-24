#include <wf_lifetime.hpp>
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <new>
#include <thread>
#include <vector>

// GL shim tests drive the same wrappers as the real backend, with deterministic
// names. A name reused in another GL namespace must not hide a survivor.
using GLenum=unsigned;using GLuint=unsigned;using GLsizei=int;using GLbitfield=unsigned;
using GLsizeiptr=std::ptrdiff_t;using GLint=int;using GLsync=void*;
constexpr GLenum GL_ARRAY_BUFFER=1,GL_ELEMENT_ARRAY_BUFFER=2,GL_ARRAY_BUFFER_BINDING=3,GL_ELEMENT_ARRAY_BUFFER_BINDING=4;
static GLuint nextName=1;
void glGenBuffers(GLsizei n,GLuint* p){while(n--)*p++=nextName++;}
void glDeleteBuffers(GLsizei,const GLuint*){}
void glGenTextures(GLsizei n,GLuint* p){glGenBuffers(n,p);}
void glDeleteTextures(GLsizei,const GLuint*){}
void glGenVertexArrays(GLsizei n,GLuint* p){glGenBuffers(n,p);}
void glDeleteVertexArrays(GLsizei,const GLuint*){}
GLuint glCreateShader(GLenum){return nextName++;}
void glDeleteShader(GLuint){}
GLuint glCreateProgram(){return nextName++;}
void glDeleteProgram(GLuint){}
GLsync glFenceSync(GLenum,GLbitfield){return reinterpret_cast<void*>(std::uintptr_t(nextName++));}
void glDeleteSync(GLsync){}
void glBufferData(GLenum,GLsizeiptr,const void*,GLenum){}
void glGetIntegerv(GLenum,GLint* p){*p=1;}
#include <wf_lifetime_gl.hpp>

struct TrackedObject { WF_LIFETIME_OBJECT("TestObject") };
struct alignas(128) Aligned { char data[128]; };
static void require(bool ok){if(!ok)std::abort();}

int main(int argc,char** argv){
    require(argc==2);const char* mode=argv[1];using namespace wflifetime;
    Owner generation=beginLevel(7);
    if(!std::strcmp(mode,"clean")){
        for(int cycle=0;cycle<3;++cycle){
            generation=beginLevel(7);
            {Scope level(generation);TrackedObject a;TrackedObject b=a;
                std::vector<int> values(256);auto* aligned=new Aligned;
                require(reinterpret_cast<std::uintptr_t>(aligned)%128==0);delete aligned;
                auto* array=new(std::nothrow) int[3];require(array);delete[] array;
                GLuint buffer;glGenBuffers(1,&buffer);glBufferData(GL_ARRAY_BUFFER,4096,nullptr,0);glDeleteBuffers(1,&buffer);
                auto fence=glFenceSync(0,0);glDeleteSync(fence);
                // Release on another thread must find the original owner.
                auto* p=new int(5);std::thread worker([p](){delete p;});worker.join();
                // A constructor failure unwinds the token and heap allocation.
                struct Throws{WF_LIFETIME_OBJECT("Throws") Throws(){throw 7;}};
                try{new Throws;}catch(int){}
            }
            require(endLevel(generation));
        }
        require(shutdown());return 0;
    }
    if(!std::strcmp(mode,"unscoped-object")){
        void* memory=::operator new(sizeof(TrackedObject));new(memory) TrackedObject;
        require(inspect(Persistent).records==1);return shutdown()?0:86;
    }
    if(!std::strcmp(mode,"persistent")){
        int* cache;
        {Scope process(Persistent);cache=static_cast<int*>(::operator new[](8*sizeof(int)));}
        require(inspect(Persistent).records==1);require(endLevel(generation));
        ::operator delete[](cache);require(shutdown());return 0;
    }
    if(!std::strcmp(mode,"bulk-arena")){
        char arena[128];{Scope level(generation);acquire(Kind::Pool,arena,reinterpret_cast<std::uintptr_t>(arena),128,"LMalloc","fixture",1);}
        require(beforeArenaRelease(arena,arena,arena+128,true));require(endLevel(generation));return 0;
    }
    if(!std::strcmp(mode,"context-loss")){
        {Scope level(generation);GLuint id;glGenTextures(1,&id);wflifetime_gl::contextLost();glGenTextures(1,&id);glDeleteTextures(1,&id);}
        require(endLevel(generation));return 0;
    }
    if(!std::strcmp(mode,"missing-destructor")){
        alignas(TrackedObject) unsigned char arena[sizeof(TrackedObject)];
        {Scope level(generation);new(arena) TrackedObject;}
        require(!beforeArenaRelease(arena,arena,arena+sizeof(arena),true));
        require(inspect(generation).records==0); // evidence was reported, errors survive reclamation
    }else if(!std::strcmp(mode,"missing-free")){
        char arena[128];
        {Scope level(generation);acquire(Kind::Pool,arena,reinterpret_cast<std::uintptr_t>(arena),128,"DMalloc","fixture",17);}
        require(!beforeArenaRelease(arena,arena,arena+128));
    }else if(!std::strcmp(mode,"missing-heap-delete")){
        Scope level(generation);auto* p=static_cast<char*>(::operator new[](1024));p[0]=1;require(inspect(generation).bytes>=1024);
    }else if(!std::strcmp(mode,"missing-gl-delete")){
        Scope level(generation);GLuint id;glGenBuffers(1,&id);
        // Same numeric name in another namespace, correctly deleted there.
        nextName=id;GLuint texture;glGenTextures(1,&texture);glDeleteTextures(1,&texture);
        require(inspect(generation).records==1);
    }else if(!std::strcmp(mode,"persistent-leak")){
        Scope process(Persistent);auto* leaked=::operator new[](15*sizeof(int));require(leaked);
        require(endLevel(generation)); // only the process check must fail
        return shutdown()?0:86;
    }else if(!std::strcmp(mode,"duplicate")){
        Scope level(generation);acquire(Kind::Object,nullptr,123,0,"Duplicate","fixture",23);
        acquire(Kind::Object,nullptr,123,0,"Duplicate","fixture",24);release(Kind::Object,nullptr,123,true);
    }else if(!std::strcmp(mode,"unknown-release")){
        release(Kind::Object,nullptr,123,true);
    }else return 2;
    return endLevel(generation)?0:86;
}
