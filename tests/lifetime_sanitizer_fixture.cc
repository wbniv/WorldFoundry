// Deliberate faults OUTSIDE the engine registry prove the independent sanitizer
// build detects C heap leaks and invalid accesses. Never run in ordinary tests.
#include <cstdlib>
#include <cstring>
#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
void leak(){
    void* p=std::malloc(231);std::memset(p,7,231);
#if defined(__GNUC__) || defined(__clang__)
    asm volatile("" : : "r"(p) : "memory");
#endif
}
int main(int argc,char** argv){
    if(argc!=2)return 2;
    if(!std::strcmp(argv[1],"leak")){leak();return 0;}
    if(!std::strcmp(argv[1],"use-after-free")){
        volatile int* p=static_cast<int*>(std::malloc(sizeof(int)));*p=12;std::free(const_cast<int*>(p));return *p;
    }
    return 2;
}
