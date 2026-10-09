//==============================================================================
// game/bitmap_text.cc — bounded layout over pre-rendered font assets
// Copyright ( c ) 2026 World Foundry Group
// This program is free software; you can redistribute it and/or modify it
// under the terms of the GNU General Public License Version 2.
// This program is distributed without ANY WARRANTY. See www.fsf.org.
//==============================================================================
// Description: strict bundle validation, UTF-8 wrapping, source anchors, quads.
// Original Author: Codex (gpt-6.1-sol, effort high), for Will Norris.
//==============================================================================
#include "bitmap_text.hp"
#include <assert.h>
#include <math.h>
#include <string.h>
#include <limits.h>

namespace bitmaptext
{
static int Read(const unsigned char* p) {
    unsigned value=unsigned(p[0])|(unsigned(p[1])<<8)|(unsigned(p[2])<<16)|(unsigned(p[3])<<24);
    int result; memcpy(&result,&value,4); return result;
}
bool Decode(const char* text,int bytes,int& offset,int& cp) {
    if(offset>=bytes)return false;
    unsigned a=(unsigned char)text[offset++];
    if(a<128){cp=int(a);return a!=0;}
    int n= a>=0xC2&&a<=0xDF ? 1 : a>=0xE0&&a<=0xEF ? 2 : a>=0xF0&&a<=0xF4 ? 3 : -1;
    if(n<0||offset+n>bytes)return false;
    unsigned value=a&((1u<<(6-n))-1);
    for(int i=0;i<n;++i){unsigned b=(unsigned char)text[offset++];if((b&0xC0)!=0x80)return false;value=(value<<6)|(b&63);}
    if(value<(n==1?128u:n==2?2048u:65536u)||value>0x10FFFF||(value>=0xD800&&value<=0xDFFF))return false;
    cp=int(value);return true;
}
void Catalog::Validate() const { assert(!_bytes||(_size>=64&&_width>0&&_height>0)); }
bool Catalog::Load(const void* bytes,size_t size,const char*& error) {
    _bytes=NULL; error=NULL;
    const unsigned char* p=(const unsigned char*)bytes;
    if(size<64||size>16*1024*1024||memcmp(p,"WFGA",4)||Read(p+4)!=1){error="invalid glyph bundle header/version";return false;}
    _width=Read(p+8);_height=Read(p+12);_variants=Read(p+16);_glyphs=Read(p+20);_kerns=Read(p+24);_texts=Read(p+28);_labels=Read(p+32);
    if(_width<1||_width>4096||_height<1||_height>4096||_variants<1||_variants>64||_glyphs<1||_glyphs>16384||_kerns<0||_kerns>131072||_texts<0||_texts>4096||_labels<0||_labels>1024){error="glyph bundle counts outside bounds";return false;}
    for(int i=0;i<7;++i)if(Read(p+36+i*4)<0||Read(p+36+i*4)>1900){error="invalid glyph mailbox binding";return false;}
    size_t cursor=64+size_t(_variants)*24;
    _glyphOffset=int(cursor);cursor+=size_t(_glyphs)*36;
    _kernOffset=int(cursor);cursor+=size_t(_kerns)*16;
    if(cursor>size){error="truncated glyph/metric tables";return false;}
    for(int i=0;i<_variants;++i){const unsigned char* v=p+64+i*24;if(Read(v)!=i||Read(v+4)<0||Read(v+4)>1||Read(v+8)<1||Read(v+8)>256||Read(v+12)<0||Read(v+16)<0||Read(v+20)<Read(v+12)+Read(v+16)){error="invalid font variant";return false;}}
    int previousVariant=-1,previousCode=-1;
    for(int i=0;i<_glyphs;++i){const unsigned char* g=p+_glyphOffset+i*36;int v=Read(g),cp=Read(g+4),x=Read(g+8),y=Read(g+12),w=Read(g+16),h=Read(g+20);
        if(v<0||v>=_variants||cp<0||cp>0x10FFFF||(cp>=0xD800&&cp<=0xDFFF)||v<previousVariant||(v==previousVariant&&cp<=previousCode)||x<0||y<0||w<0||h<0||w>_width-x||h>_height-y||Read(g+32)<0||Read(g+32)>256*64){error="invalid/unsorted glyph metrics";return false;} previousVariant=v;previousCode=cp;
    }
    int kv=-1,kl=-1,kr=-1;
    for(int i=0;i<_kerns;++i){const unsigned char* k=p+_kernOffset+i*16;int v=Read(k),l=Read(k+4),r=Read(k+8),a=Read(k+12);
        if(v<0||v>=_variants||l<0||r<0||a < -256*64||a>256*64||v<kv||(v==kv&&(l<kl||(l==kl&&r<=kr)))){error="invalid/unsorted kerning table";return false;}kv=v;kl=l;kr=r;
    }
    _textOffset=int(cursor);
    for(int table=0;table<2;++table){if(table)_labelOffset=int(cursor);int count=table?_labels:_texts;int previousID=0;
        for(int i=0;i<count;++i){const int header=table?16:12;if(cursor+header>size){error="truncated text record";return false;}
            int id=Read(p+cursor),a=Read(p+cursor+4),b=Read(p+cursor+(table?12:8));if(table&&(Read(p+cursor+8)<0||Read(p+cursor+8)>255)){error="invalid label realm";return false;}cursor+=header;
            int length=table?b:a+b;
            if(id<=previousID||a<0||b<0||a>65536||b>65536||length<0||size_t(length)>size-cursor||(table&&a>2047)){error="invalid text/label bounds";return false;}previousID=id;
            int offset=0,cp;while(offset<length)if(!Decode((const char*)p+cursor,length,offset,cp)){error="invalid UTF-8 text";return false;}
            cursor+=length;
        }
    }
    if(cursor+size_t(_width)*_height!=size){error="invalid glyph pixel payload length";return false;}
    _pixelOffset=int(cursor);_bytes=p;_size=size;Validate();return true;
}
Variant Catalog::GetVariant(int i) const {Validate();assert(_bytes&&i>=0&&i<_variants);const unsigned char* p=_bytes+64+i*24;return {Read(p),Read(p+4),Read(p+8),Read(p+12),Read(p+16),Read(p+20)};}
int Catalog::SelectVariant(int face,int pixels) const {Validate();int best=-1,distance=INT_MAX;for(int i=0;i<_variants;++i){Variant v=GetVariant(i);int d=v.pixels>pixels?v.pixels-pixels:pixels-v.pixels;if(v.face==face&&d<distance){best=i;distance=d;}}return best;}
int Catalog::Binding(int i)const{Validate();assert(_bytes&&i>=0&&i<7);return Read(_bytes+36+i*4);}
bool Catalog::FindGlyph(int variant,int cp,Glyph& g) const {
    Validate();if(!_bytes)return false;int lo=0,hi=_glyphs;
    while(lo<hi){int mid=(lo+hi)/2;const unsigned char* p=_bytes+_glyphOffset+mid*36;int v=Read(p),c=Read(p+4);if(v<variant||(v==variant&&c<cp))lo=mid+1;else hi=mid;}
    if(lo==_glyphs)return false;const unsigned char* p=_bytes+_glyphOffset+lo*36;if(Read(p)!=variant||Read(p+4)!=cp)return false;
    g={Read(p),Read(p+4),Read(p+8),Read(p+12),Read(p+16),Read(p+20),Read(p+24),Read(p+28),Read(p+32)};return true;
}
int Catalog::Kerning(int variant,int left,int right) const {
    Validate();int lo=0,hi=_kerns;while(lo<hi){int mid=(lo+hi)/2;const unsigned char* p=_bytes+_kernOffset+mid*16;int v=Read(p),l=Read(p+4),r=Read(p+8);if(v<variant||(v==variant&&(l<left||(l==left&&r<right))))lo=mid+1;else hi=mid;}
    if(lo==_kerns)return 0;const unsigned char* p=_bytes+_kernOffset+lo*16;return Read(p)==variant&&Read(p+4)==left&&Read(p+8)==right?Read(p+12):0;
}
bool Catalog::GetText(int id,Text& t) const {Validate();int off=_textOffset;for(int i=0;i<_texts;++i){int a=Read(_bytes+off),n=Read(_bytes+off+4),m=Read(_bytes+off+8);if(a==id){t={a,(const char*)_bytes+off+12,n,(const char*)_bytes+off+12+n,m};return true;}off+=12+n+m;}return false;}
Label Catalog::GetLabel(int index) const {Validate();assert(index>=0&&index<_labels);int off=_labelOffset;for(int i=0;i<index;++i)off+=16+Read(_bytes+off+12);return {Read(_bytes+off),Read(_bytes+off+4),Read(_bytes+off+8),(const char*)_bytes+off+16,Read(_bytes+off+12)};}
void Layout::Validate()const{assert(_count>=0&&_count<=MAX_LINES);}
bool Layout::Wrap(const Catalog& c,int variant,const char* text,int bytes,int width,const char*& error) {
    Validate();_count=0;error=NULL;if(width<1||bytes<0){error="invalid text layout bounds";return false;}
    int start=0,pos=0,lastBreak=-1,previous=0;float advance=0,breakWidth=0;
    while(pos<bytes){int before=pos,cp;if(!Decode(text,bytes,pos,cp)){error="invalid UTF-8 during layout";return false;}
        Glyph g; if(cp!='\n'&&!c.FindGlyph(variant,cp,g)){error="character absent from supplied atlas";return false;}
        float next=cp=='\n'?advance:advance+(g.advance+c.Kerning(variant,previous,cp))/64.0f;
        if(cp=='\n'||next>width){
            int end=before,resume=before;float lineWidth=advance;
            if(cp!='\n'&&lastBreak>=start){end=lastBreak;resume=lastBreak+1;lineWidth=breakWidth;}
            else if(cp=='\n')resume=pos;
            else if(before==start){error="single glyph exceeds layout width";return false;}
            if(_count==MAX_LINES){error="semantic beat exceeds bounded line capacity";return false;}
            _lines[_count++]={start,end,lineWidth};start=pos=resume;lastBreak=-1;previous=0;advance=0;
            while(pos<bytes&&text[pos]==' ')++pos;start=pos;continue;
        }
        if(cp==' '){lastBreak=before;breakWidth=advance;}
        advance=next;previous=cp;
    }
    if(start<bytes||_count==0){if(_count==MAX_LINES){error="semantic beat exceeds line capacity";return false;}_lines[_count++]={start,bytes,advance};}Validate();return true;
}
int Layout::PageCount(int capacity)const{Validate();assert(capacity>0);return (_count+capacity-1)/capacity;}
int Layout::Anchor(int page,int capacity)const{Validate();int i=page*capacity;return i<_count?_lines[i].begin:(_count?_lines[_count-1].end:0);}
int Layout::PageForAnchor(int offset,int capacity)const{Validate();assert(capacity>0);int i=0;while(i+1<_count&&_lines[i+1].begin<=offset)++i;return i/capacity;}
bool Layout::Draw(const Catalog& c,int variant,const char* text,int bytes,int first,int lines,int x,int baseline,int step,float depth,unsigned color,Quad* q,int& count,int limit,const char*& error)const{
    Validate();error=NULL;
    for(int line=first;line<_count&&line<first+lines;++line){int pos=_lines[line].begin,previous=0;float pen=float(x);
        while(pos<_lines[line].end){int cp;if(!Decode(text,bytes,pos,cp)){error="invalid UTF-8 during glyph drawing";return false;}Glyph g;if(!c.FindGlyph(variant,cp,g)){error="missing glyph during drawing";return false;}
            pen+=c.Kerning(variant,previous,cp)/64.0f;
            if(g.width&&g.height){if(count>=limit){error="visible glyph geometry capacity exceeded";return false;}float left=floorf(pen+0.5f)+g.bearingX,top=float(baseline+(line-first)*step+g.bearingY);
                q[count++]={left,top,left+g.width,top+g.height,float(g.x)/c.Width(),float(g.y)/c.Height(),float(g.x+g.width)/c.Width(),float(g.y+g.height)/c.Height(),depth,color};}
            pen+=g.advance/64.0f;previous=cp;
        }
    }return true;
}
}
