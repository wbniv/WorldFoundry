// Runtime layout tests against the actual chapter-generated atlas and text.
#include "../wfsource/source/game/bitmap_text.hp"
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>
#include <cmath>

static int checks=0;
static void Check(bool ok,const char* what){++checks;if(!ok){std::fprintf(stderr,"FAIL: %s\n",what);std::exit(1);}}
static std::string WithoutSpace(const char* text,int bytes){std::string out;for(int i=0;i<bytes;++i)if(text[i]!=' '&&text[i]!='\n')out+=text[i];return out;}
int main(int argc,char** argv){
    Check(argc==2,"supply real glyph bundle");std::ifstream input(argv[1],std::ios::binary);
    std::vector<unsigned char> bytes{std::istreambuf_iterator<char>(input),{}};
    bitmaptext::Catalog catalog;const char* error=nullptr;Check(catalog.Load(bytes.data(),bytes.size(),error),error?error:"valid real font catalog");
    Check(!catalog.Load(bytes.data(),63,error),"truncated header rejected");
    Check(catalog.Load(bytes.data(),bytes.size(),error),"reload valid font catalog");
    const int pixels[]={28,42,56,63,84};int texts=0;
    bitmaptext::Text text;
    for(int id=1;catalog.GetText(id,text);++id){++texts;
        for(int px:pixels)for(int width:{480,960,1766}){
            bitmaptext::Layout layout;int variant=catalog.SelectVariant(0,px);Check(catalog.GetVariant(variant).pixels==px,"exact baked size selected");
            Check(layout.Wrap(catalog,variant,text.body,text.bodyBytes,width,error),error?error:"real chapter text wraps");
            std::string recovered;int previousEnd=0;
            for(int i=0;i<layout.LineCount();++i){const auto& line=layout.GetLine(i);
                Check(line.begin>=previousEnd&&line.end>=line.begin&&line.end<=text.bodyBytes,"ordered bounded source ranges");
                Check(line.width<=width,"line fits measured region");
                for(int k=previousEnd;k<line.begin;++k)Check(text.body[k]==' '||text.body[k]=='\n',"only layout whitespace skipped");
                recovered+=WithoutSpace(text.body+line.begin,line.end-line.begin);previousEnd=line.end;
            }
            Check(recovered==WithoutSpace(text.body,text.bodyBytes),"exact text coverage without dropped/duplicated letters");
            bitmaptext::Layout reflow;
            Check(reflow.Wrap(catalog,variant,text.body,text.bodyBytes,width+173,error),"reflow succeeds");
            for(int capacity:{1,3,8})for(int page=0;page<layout.PageCount(capacity);++page){
                int anchor=layout.Anchor(page,capacity);Check(layout.PageForAnchor(anchor,capacity)==page,"page anchor round trip");
                int newPage=reflow.PageForAnchor(anchor,capacity),first=newPage*capacity;
                Check(reflow.GetLine(first).begin<=anchor,"reflow keeps prior passage visible");
            }
            for(int first=0;first<layout.LineCount();first+=16){
            bitmaptext::Quad quads[4096];int count=0;
            Check(layout.Draw(catalog,variant,text.body,text.bodyBytes,first,16,12,100,catalog.GetVariant(variant).lineStep,0,0xFFFFFFFFu,quads,count,4096,error),"real text emits glyph quads");
            for(int i=0;i<count;++i){const auto& q=quads[i];
                Check(std::fabs((q.u1-q.u0)*catalog.Width()-(q.x1-q.x0))<0.001f,"glyph width maps texels to pixels 1:1");
                Check(std::fabs((q.v1-q.v0)*catalog.Height()-(q.y1-q.y0))<0.001f,"glyph height maps texels to pixels 1:1");
                Check(q.x0==std::floor(q.x0)&&q.y0==std::floor(q.y0),"pixel aligned glyph origins");
            }
            }
        }
    }
    Check(texts>100,"complete chapter loaded");
    Check(!catalog.Load(nullptr,bytes.size(),error),"null bundle storage rejected");
    Check(catalog.Load(bytes.data(),bytes.size(),error),"valid catalog reload after rejected storage");
    bitmaptext::Layout split;std::string longToken(200,'W');int variant=catalog.SelectVariant(0,42);
    Check(split.Wrap(catalog,variant,longToken.data(),longToken.size(),80,error),"long token splits safely");Check(split.LineCount()>1,"long token actually wraps");
    Check(!split.Wrap(catalog,variant,"W",1,1,error),"unfittable glyph rejected instead of scaling");
    Check(!split.Wrap(catalog,variant,"\xF0\x80\x80\x80",4,200,error),"overlong UTF-8 rejected");
    Check(!split.Wrap(catalog,variant,"\xED\xA0\x80",3,200,error),"UTF-8 surrogate rejected");
    Check(!split.Wrap(catalog,variant,"\xF0\x9F\x99\x82",4,200,error),"unsupported glyph rejected");
    auto read32=[&](int offset){return unsigned(bytes[offset])|(unsigned(bytes[offset+1])<<8)|(unsigned(bytes[offset+2])<<16)|(unsigned(bytes[offset+3])<<24);};
    const int firstText=64+int(read32(16))*24+int(read32(20))*36+int(read32(24))*16;
    auto corrupt=bytes;
    for(int field:{4,8}){corrupt[firstText+field]=255;corrupt[firstText+field+1]=255;corrupt[firstText+field+2]=255;corrupt[firstText+field+3]=127;}
    Check(!catalog.Load(corrupt.data(),corrupt.size(),error),"oversized text lengths rejected without overflow");
    corrupt=bytes;const int titleBytes=int(read32(firstText+4));
    corrupt[firstText+12+titleBytes-1]=0xC3;corrupt[firstText+12+titleBytes]=0xA9;
    Check(!catalog.Load(corrupt.data(),corrupt.size(),error),"UTF-8 cannot straddle title/body boundary");
    corrupt=bytes;corrupt[8]=0;corrupt[9]=0;Check(!catalog.Load(corrupt.data(),corrupt.size(),error),"zero atlas width rejected");
    corrupt=bytes;corrupt.pop_back();Check(!catalog.Load(corrupt.data(),corrupt.size(),error),"truncated atlas pixels rejected");
    std::printf("PASS %d checks; %d catalog records; native-size geometry and source-anchor reflow\n",checks,texts);
}
