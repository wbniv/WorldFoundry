#include <renderassets/rendacto.hp>
#include <gfx/pixelmap.hp>
#include <gfx/material.hp>
#include <memory/lmalloc.hp>
#include <hal/halbase.h>
#include <streams/binstrm.hp>
#include <cstdio>
#include <chrono>
#include <cstring>
#include <sys/resource.h>
#include <vector>
struct Callbacks : GfxCallbacks {
    PixelMap pixelMap{PixelMap::MEMORY_VIDEO,256,256};
    LookupTextureStruct LookupTexture(const char*,int32) const override { return LookupTextureStruct(emptyTexture,pixelMap); }
protected: void _Validate() const override {}
};
int main(int argc,char** argv) {
    if(argc<2 || argc>3) return 2;
    FILE* f=std::fopen(argv[1],"rb"); if(!f) return 2;
    std::vector<char> bytes; char buf[4096]; size_t n;
    while((n=std::fread(buf,1,sizeof(buf),f))) bytes.insert(bytes.end(),buf,buf+n);
    std::fclose(f);
    std::vector<char> scratch(4<<20), heap(32<<20);
    _HALScratchLmalloc=new LMalloc(scratch.data(),scratch.size() MEMORY_NAMED(COMMA "probe scratch"));
    LMalloc memory(heap.data(),heap.size() MEMORY_NAMED(COMMA "probe heap"));
    Callbacks cb; binistream input(bytes.data(),int32(bytes.size()));
    const auto start=std::chrono::steady_clock::now();
    RenderActor3D actor(memory,input,0,cb);
    const auto end=std::chrono::steady_clock::now();
    std::printf("load_us=%.3f\n",std::chrono::duration<double,std::micro>(end-start).count());
    struct rusage usage{}; getrusage(RUSAGE_SELF,&usage);
    std::printf("peak_rss_kib=%ld\n",usage.ru_maxrss);
    RenderObject3D& object=const_cast<RenderObject3D&>(*actor.GetRenderObject());
    const TriFace* face=object.GetWritableFaceList();
    for(int i=0;argc!=3 && i<object.GetFaceCount();++i) {
        Vector3 n=PSToVector3(face[i].normal);
        std::printf("face=%d normal=(%.9g,%.9g,%.9g)\n",i,n.X().AsFloat(),n.Y().AsFloat(),n.Z().AsFloat());
    }
}
