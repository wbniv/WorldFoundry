// Isolated floating-point prototypes; neither function is the engine loader.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <random>
#include <vector>
struct V { float x,y,z; };
struct T { V a,b; };
static bool normal(const T& t, int mode, V& out) {
    float x=t.a.y*t.b.z-t.a.z*t.b.y, y=t.a.z*t.b.x-t.a.x*t.b.z, z=t.a.x*t.b.y-t.a.y*t.b.x;
    float n=std::sqrt(x*x+y*y+z*z);
    if (mode==1 || (mode==2 && !(n>4.0f/65536))) {
        float m=std::max(std::fabs(x),std::max(std::fabs(y),std::fabs(z)));
        if (!(m>0)) return false;
        x/=m; y/=m; z/=m;
        n=std::sqrt(x*x+y*y+z*z);
    }
    if (!(n > (mode ? 0.0f : 4.0f/65536))) return false;
    out={x/n,y/n,z/n}; return true;
}
int main() {
    std::mt19937 rng(10457); std::uniform_real_distribution<float> d(-1,1);
    std::vector<T> mesh; mesh.reserve(200000);
    for(int i=0;i<200000;++i) mesh.push_back({{d(rng),d(rng),d(rng)},{d(rng),d(rng),d(rng)}});
    volatile double sink=0;
    std::puts("sample,variant,ns_per_triangle,checksum");
    for (int round=-2; round<20; ++round) for (int j=0;j<3;++j) {
        int mode=(round+j+3)%3; auto start=std::chrono::steady_clock::now(); double sum=0;
        for (int repeat=0;repeat<5;++repeat) for (const T& t:mesh) { V n{}; if(normal(t,mode,n)) sum+=n.x+n.y+n.z; }
        auto end=std::chrono::steady_clock::now(); sink+=sum;
        if(round>=0) std::printf("%d,%s,%.4f,%.8f\n",round,mode==0?"baseline":mode==1?"always-scaled":"conditional",std::chrono::duration<double,std::nano>(end-start).count()/1000000,sum);
    }
    for(float edge:{1.0f,0.01f,0.001f,0.0f}) { T t{{edge,0,0},{0,edge,0}}; V a{},b{}; bool aa=normal(t,0,a),bb=normal(t,2,b); std::fprintf(stderr,"edge=%.9g cross=%.9g baseline=%d conditional=%d conditional_z=%.9g\n",edge,edge*edge,aa,bb,b.z); }
    return sink==123456789;
}
