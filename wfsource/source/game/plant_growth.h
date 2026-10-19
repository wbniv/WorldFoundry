#ifndef WF_PLANT_GROWTH_H
#define WF_PLANT_GROWTH_H
// Deterministic, bounded colony construction. Units match the aquarium tank.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <vector>
namespace plantgrowth {
constexpr float pi=3.14159265358979323846f;
struct Point { float x,y,z; };
struct Vertex { Point rest,root; float birth,duration; uint32_t color,textureColor; float u,v; };
struct Face { uint16_t a,b,c; float birth; };
struct Chunk { std::vector<Vertex> vertices; std::vector<Face> faces; };
struct Shoot { float x,y,height,heading,birth; int kind,parent; };
struct Random { uint32_t value; explicit Random(uint32_t seed):value(seed^0xa511e9b3u) {} uint32_t next(){value=value*1664525u+1013904223u;return value;} float unit(){return (next()>>8)*(1.f/16777216.f);} float between(float a,float b){return a+(b-a)*unit();} };
inline Point add(Point a,Point b){return {a.x+b.x,a.y+b.y,a.z+b.z};}
inline Point mul(Point a,float b){return {a.x*b,a.y*b,a.z*b};}
inline Point sub(Point a,Point b){return {a.x-b.x,a.y-b.y,a.z-b.z};}
inline float smooth(float v){v=std::max(0.f,std::min(1.f,v));return v*v*(3-2*v);}
inline bool route(float x,float y){return y<-.75f && std::fabs(x-.5f*std::sin(y*3))<.48f;}
inline std::vector<Shoot> colonies(uint32_t seed,bool salt){
 Random r(seed);std::vector<Shoot> shoots;shoots.reserve(384);const int founders=16;
 for(int k=0;k<founders;k++){
  int kind=k%3;float x=r.between(-4.9f,4.9f),y=r.between(-.65f,1.05f);
  shoots.push_back({x,y,r.between(.7f,1.f),r.between(0,2*pi),0,kind,-1});
 }
 // Expand each lineage locally, with unequal colony populations and spacing.
 for(int attempts=0;shoots.size()<384 && attempts<16000;attempts++){
  int parent=int(r.unit()*shoots.size());const Shoot p=shoots[parent];
  float step=(p.kind==0?r.between(.17f,.34f):p.kind==1?r.between(.25f,.58f):r.between(.10f,.23f));
  float a=p.heading+r.between(-1.25f,1.25f);float x=p.x+std::cos(a)*step,y=p.y+std::sin(a)*step*.75f;
  if(x<-5.22f||x>5.22f||y<-1.24f||y>1.12f||route(x,y))continue;
  bool crowded=false;for(const auto& n:shoots)if((n.x-x)*(n.x-x)+(n.y-y)*(n.y-y)<.0144f){crowded=true;break;}if(crowded)continue;
  float birth=p.birth+r.between(2.5f,6.8f);shoots.push_back({x,y,r.between(.65f,1.f),a,birth,p.kind,parent});
 }
 for(auto& p:shoots){float h=p.kind==0?r.between(.9f,1.8f):p.kind==1?r.between(2.2f,3.7f):r.between(.35f,1.3f);if(salt)h=p.kind==0?r.between(1.3f,2.9f):p.kind==1?r.between(2.2f,3.8f):r.between(.24f,.48f);p.height*=h;p.birth*=2.f;}
 return shoots;
}
inline void triangle(Chunk& c,uint16_t a,uint16_t b,uint16_t d,float birth){c.faces.push_back({a,b,d,birth});}
inline void blade(Chunk& c,Point root,Point base,Point tip,float width,int sections,float birth,uint32_t color,int tile=0){
 // One closed curved blade. Independent rest geometry permits anchored unfurling.
 if(c.vertices.size()+unsigned((sections+1)*4)>30000)return;
 uint16_t first=uint16_t(c.vertices.size());Point axis=sub(tip,base);float mag=std::sqrt(axis.x*axis.x+axis.z*axis.z);if(mag<.01f)return;Point side={axis.z/mag,0,-axis.x/mag};
 for(int back=0;back<2;back++)for(int j=0;j<=sections;j++)for(int k=0;k<2;k++){
  float t=float(j)/sections,q=k?1.f:-1.f,b=std::sin(pi*t),span=width*b*q;
  Point v=add(add(base,mul(axis,t)),mul(side,span));v.y+=.09f*b+width*.18f*q*b*(t-.35f)+(back?.006f:-.006f)*b;v.x=std::max(-5.90f,std::min(5.90f,v.x));v.y=std::max(-1.43f,std::min(1.43f,v.y));v.z=std::min(4.79f,std::max(root.z,v.z+.04f*b));
  // Tile interiors are 72 x 112 texels with four-texel extruded gutters.
  // Native UVs follow Blender convention; textile flips the packed page vertically.
  float u=(float((tile%3)*80+4)+float(k)*71.f)/255.f;
  float uv=(255.f-float((tile/3)*120+4)-(1.f-t)*111.f)/255.f;
  // Albedo supplies pigment. Keep modest authored leaf variation and an underside tint.
  uint32_t tint=uint32_t((color==0x829957u?245:232)*(back?.83f:1.f));
  c.vertices.push_back({v,root,birth,18.f+(tip.z-root.z)*6.f,color,(tint<<16)|(tint<<8)|tint,u,uv});
 }
 int stride=(sections+1)*2;
 for(int back=0;back<2;back++)for(int j=0;j<sections;j++){
  uint16_t a=first+back*stride+j*2,b=a+2,d=a+1,e=a+3;
  // Skip collapsed endpoint triangles, retaining both front and back surfaces.
  if(back){if(j>0)triangle(c,a,b,d,birth);if(j<sections-1)triangle(c,d,b,e,birth);}
  else{if(j>0)triangle(c,d,b,a,birth);if(j<sections-1)triangle(c,e,b,d,birth);}
 }
}
inline void axis(Chunk& c,Point root,Point a,Point b,float width,float birth,uint32_t color){blade(c,root,a,b,width,2,birth,color,2);}
inline void algae(Chunk& c,Point root,Point base,float angle,float length,int depth,float birth){
 Point tip={base.x+std::sin(angle)*length,base.y+.015f,base.z+std::cos(angle)*length};
 blade(c,root,base,tip,.06f+.02f*depth,3,birth,0x927847u,5);
 if(depth){algae(c,root,tip,angle-.40f,length*.64f,depth-1,birth+4);algae(c,root,tip,angle+.47f,length*.70f,depth-1,birth+5);}
}
// Smooth directional shading from the curved rest surfaces, baked once per generation.
inline void shade(Chunk& c){
 std::vector<Point> normals(c.vertices.size(),{0,0,0});
 for(const auto& f:c.faces){Point a=sub(c.vertices[f.b].rest,c.vertices[f.a].rest),b=sub(c.vertices[f.c].rest,c.vertices[f.a].rest);Point n={a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};float length=std::sqrt(n.x*n.x+n.y*n.y+n.z*n.z);if(length<1e-8f)continue;n=mul(n,1.f/length);for(auto v:{f.a,f.b,f.c})normals[v]=add(normals[v],n);}
 for(size_t i=0;i<c.vertices.size();i++){auto n=normals[i];float length=std::sqrt(n.x*n.x+n.y*n.y+n.z*n.z);if(length>1e-8f)n=mul(n,1.f/length);float light=.26f+.74f*std::max(0.f,-.32f*n.x-.67f*n.y+.67f*n.z);auto shadeColor=[&](uint32_t color){auto channel=[&](int shift){return uint32_t(std::min(255.f,((color>>shift)&255)*light));};return (channel(16)<<16)|(channel(8)<<8)|channel(0);};c.vertices[i].color=shadeColor(c.vertices[i].color);c.vertices[i].textureColor=shadeColor(c.vertices[i].textureColor);}
}
inline std::array<Chunk,8> meshes(uint32_t seed,bool salt,const std::vector<Shoot>& shoots){
 std::array<Chunk,8> chunks;Random r(seed^0x7204e813u);
 std::vector<const Shoot*> ordered;for(const auto& p:shoots)ordered.push_back(&p);std::stable_sort(ordered.begin(),ordered.end(),[](const Shoot* a,const Shoot* b){return a->birth<b->birth;});
 for(const auto* shoot:ordered){const auto& p=*shoot;int col=std::min(3,std::max(0,int((p.x+5.5f)/2.75f)));Chunk& c=chunks[col+(p.y<.1f?4:0)];Point root={p.x,p.y,.635f};float h=p.height;
  if(salt&&p.kind==0){algae(c,root,root,.12f*std::sin(p.heading),h*.40f,3,p.birth);continue;}
  if(p.kind==1){for(int j=0;j<7;j++){float a=p.heading+j*2*pi/7.f,len=h*r.between(.72f,1.f);Point tip={p.x+std::cos(a)*.26f,p.y+std::sin(a)*.16f,.635f+len};blade(c,root,root,tip,.04f+r.between(0,.025f),6,p.birth+j*1.4f,0x72a24du,salt?3:1);}continue;}
  if(p.kind==0){for(int j=0;j<7;j++){float a=p.heading+j*2*pi/7.f;Point tip={p.x+std::cos(a)*.60f,p.y+std::sin(a)*.18f,.635f+h*r.between(.58f,1.f)};blade(c,root,root,tip,.15f+r.between(0,.08f),5,p.birth+j*1.6f,j%3?0x518444u:0x829957u);}continue;}
  if(salt){for(int j=0;j<4;j++){float a=p.heading+j*.48f;Point base={p.x+std::cos(a)*.10f*j,p.y+std::sin(a)*.06f*j,.64f};for(int side:{-1,1}){Point tip={base.x+side*.13f,base.y,.635f+h};blade(c,root,base,tip,.075f,3,p.birth+j*2.f,0x83aa62u,4);}}continue;}
  Point top={p.x+.12f*std::sin(p.heading),p.y,.635f+h};axis(c,root,root,top,.015f,p.birth,0x597647u);
  for(int node=0;node<5;node++){float t=.16f+node*.17f;Point base=add(root,mul(sub(top,root),t));for(int j=0;j<5;j++){float a=p.heading+j*2*pi/5+node*.37f;Point tip={base.x+std::cos(a)*.24f,base.y+std::sin(a)*.10f,base.z+.15f};blade(c,root,base,tip,.022f,3,p.birth+node*1.2f,0x73aa73u,2);}}
 }
 for(auto& c:chunks)shade(c);
 return chunks;
}
inline Point deformedWave(const Vertex& v,float age,float wave,float secondWave,bool sway=true){
 float g=smooth((age-v.birth)/v.duration);if(v.birth==0&&age>=0)g=.08f+.92f*g;Point delta=sub(v.rest,v.root);Point p=add(v.root,mul(delta,g));
 float h=std::max(0.f,delta.z),weight=h*h/(3.8f*3.8f);
 if(sway){p.x+=.045f*weight*wave*g;p.y+=.022f*weight*secondWave*g;}
 return p;
}
inline Point deformed(const Vertex& v,float age,float water,bool sway=true){return deformedWave(v,age,std::sin(water*2*pi/7.f+v.root.x*.10f+v.root.y*.15f),std::sin(water*2*pi/9.f+.4f+v.root.x*.10f),sway);}
} // namespace plantgrowth
#endif
