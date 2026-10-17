// Real exported meshes: CPU evaluation, pose-only palette and late CPU fallback
// must agree on positions and mailbox outputs, including half-angle necks.
#include <renderassets/skin_pose.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <limits>
#include <stdexcept>
#include <vector>

using namespace wf_render;
static void need(bool ok,const char* message) { if(!ok)throw std::runtime_error(message); }
static unsigned u32(const char* p) { unsigned x;std::memcpy(&x,p,4);return x; }
static int i32(const char* p) { int x;std::memcpy(&x,p,4);return x; }
static short i16(const char* p) {short x;std::memcpy(&x,p,2);return x;}

int main(int argc,char** argv) {
    try {
        need(argc>=2,"need model paths");float maxError=0,minArea=1e30f,maxNormalError=0;
        for(int a=1;a<argc;++a) {
            std::ifstream input(argv[a],std::ios::binary);
            std::vector<char> bytes{std::istreambuf_iterator<char>(input),{}};
            need(bytes.size()>8 && std::memcmp(bytes.data(),"MODL",4)==0,"bad model");
            std::vector<float> rest,normals;std::vector<int> faces;std::vector<char> rig;
            for(size_t o=8;o+8<=bytes.size();) {
                unsigned size=u32(&bytes[o+4]);need(o+8+size<=bytes.size(),"truncated model");const char* p=&bytes[o+8];
                if(!std::memcmp(&bytes[o],"VRTX",4)) {
                    need(size%24==0,"bad vertices");for(unsigned j=0;j<size;j+=24)for(int k=0;k<3;++k)rest.push_back(i32(p+j+12+4*k)/65536.f);
                } else if(!std::memcmp(&bytes[o],"FACE",4)) {
                    need(size%8==0,"bad faces");for(unsigned j=0;j<size;j+=8)for(int k=0;k<3;++k)faces.push_back(i16(p+j+2*k));
                } else if(!std::memcmp(&bytes[o],"DFRM",4))rig.assign(p,p+size);
                o+=8+((size+3)&~3u);
            }
            for(size_t f=0;f<faces.size();f+=3) {
                float u[3],v[3],n[3];for(int k=0;k<3;++k){u[k]=rest[3*faces[f+1]+k]-rest[3*faces[f]+k];v[k]=rest[3*faces[f+2]+k]-rest[3*faces[f]+k];}
                n[0]=u[1]*v[2]-u[2]*v[1];n[1]=u[2]*v[0]-u[0]*v[2];n[2]=u[0]*v[1]-u[1]*v[0];
                float length=std::sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]);need(length>0,"degenerate face");
                for(float x:n)normals.push_back(x/length);
            }
            DfrmData data;const char* reason="";need(ParseDfrm(rig.data(),rig.size(),rest.size()/3,data,reason),reason);
            // A face that collapses at the end of an allowed transform range
            // cannot reproduce CPU's previous-normal rule in a derivative shader.
            if(a==1) {
                DfrmData unsafe=data;
                unsafe.transforms[0]={{0,0,0},{0,0,1},-90,90};
                unsafe.influences={{DfrmNone,0,0,0,0},{DfrmOnTransform,0,1,0,0},{DfrmNone,0,0,0,0}};
                const float triangle[]={0,0,0,1,0,0,0,1,0};const int face[]={0,1,2};DfrmSkin rejected;
                need(!rejected.Bind(unsafe,triangle,3,face,1),"collapsing face accepted");
                unsafe.transforms[0].lo=-20;unsafe.transforms[0].hi=20;
                need(rejected.Bind(unsafe,triangle,3,face,1),"safe angle interval rejected");
                unsafe.influences[0]={DfrmOnSample,0,0,0,0};
                need(!rejected.Bind(unsafe,triangle,3,face,1),"uncertified mixed sample face accepted");
            }
            DfrmEvaluator cpu,gpu;DfrmSkin skin;
            need(cpu.Bind(data,rest.data(),rest.size()/3,faces.data(),normals.data(),faces.size()/3),"cpu bind");
            need(gpu.Bind(data,rest.data(),rest.size()/3,faces.data(),normals.data(),faces.size()/3),"gpu bind");
            need(skin.Bind(data,rest.data(),rest.size()/3,faces.data(),faces.size()/3),"skin bind");need(skin.Palette().size()/12==40,"expected 40 entries");
            for(int pose=0;pose<320;++pose) {
                float block[40]={};double now=pose*.037;
                for(int k=0;k<21;++k)block[k]=std::sin(pose*.11+k)*3;
                block[21]=pose%3;block[22]=18;block[23]=.055f;block[24]=(pose%17)/16.f;
                block[25]=pose%9;block[26]=-.2;block[27]=(pose+2)%9;block[28]=pose%2 ? now-.4*(pose%13)/12 : .1;block[29]=.3;
                block[30]=std::sin(pose*.1)*20;block[31]=17;block[32]=-23;
                const float rot[9]={0,1,0,-1,0,0,0,0,1};
                int status=cpu.Evaluate(block,33,now,rot);need(status==0 || status==3,"cpu pose");
                need(gpu.Evaluate(block,33,now,rot,false)==status,"pose-only status");need(skin.Pose(data,gpu),"palette");
                for(size_t i=0;i<skin.Bindings().size();++i) {
                    float p[3];SkinPoint(skin.Bindings()[i],skin.Palette().data(),p);
                    for(int k=0;k<3;++k){float e=std::fabs(p[k]-cpu.Positions()[3*i+k]);maxError=std::max(maxError,e);need(e<1e-4,"palette position differs");}
                }
                const auto& positions=cpu.Positions();
                for(size_t f=0;f<faces.size();f+=3) {
                    float u[3],v[3],n[3];
                    for(int k=0;k<3;++k){u[k]=positions[3*faces[f+1]+k]-positions[3*faces[f]+k];v[k]=positions[3*faces[f+2]+k]-positions[3*faces[f]+k];}
                    n[0]=u[1]*v[2]-u[2]*v[1];n[1]=u[2]*v[0]-u[0]*v[2];n[2]=u[0]*v[1]-u[1]*v[0];
                    float area=std::sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]);minArea=std::min(minArea,area);need(area>1e-12,"degenerate posed face");
                    const float* expected=&cpu.FaceNormals()[f];
                    float length=std::sqrt(expected[0]*expected[0]+expected[1]*expected[1]+expected[2]*expected[2]);
                    for(int k=0;k<3;++k)maxNormalError=std::max(maxNormalError,std::fabs(n[k]/area-expected[k]/length));
                }
                for(int k=0;k<6;++k)need(cpu.Outputs()[k]==gpu.Outputs()[k],"mailbox differs");
                // A late draw rejection materializes the already sampled pose.
                need(gpu.Materialize(),"late materialize");need(gpu.Positions()==cpu.Positions(),"fallback positions differ");
                need(gpu.FaceNormals()==cpu.FaceNormals(),"fallback normals differ");
                const auto oldJoints=gpu.Joints();block[0]=std::numeric_limits<float>::quiet_NaN();
                need(gpu.Evaluate(block,33,now,rot,false)==DfrmNotFinite,"invalid input accepted");need(oldJoints==gpu.Joints(),"partial pose published");
            }
            std::printf("%s: 320 CPU/palette/fallback poses pass\n",argv[a]);
        }
        need(maxNormalError<1e-3,"geometric face normals differ from CPU normals");
        std::printf("maximum palette error %.9g model units; minimum posed double area %.9g; maximum normal error %.9g\n",maxError,minArea,maxNormalError);
    } catch(const std::exception& e){std::fprintf(stderr,"skin_pose_math: %s\n",e.what());return 1;}
}
