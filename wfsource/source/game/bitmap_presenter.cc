//==============================================================================
// game/bitmap_presenter.cc — cached native-pixel chapter text
// Copyright ( c ) 2026 World Foundry Group
// GNU General Public License Version 2; distributed WITHOUT ANY WARRANTY.
// Description: no runtime rasterizer, bitmap scaling or unchanged-frame layout.
// Original Author: Codex (gpt-6.1-sol, effort high), for Will Norris.
//==============================================================================
#include "bitmap_presenter.hp"
#include <mailbox/mailbox.hp>
#include <hal/phonepad/phonepad_overlay.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

namespace bitmaptext
{
static const char* const kControls="SELECT: continue   LEFT / C: close   UP / DOWN: text size";
void Presenter::Fatal(const char* error)const{fprintf(stderr,"BITMAP_TEXT: %s\n",error);abort();}
void Presenter::Validate()const{_catalog.Validate();_body.Validate();assert(_signCount>=0&&_signCount<=MAX_LABELS);}
bool Presenter::Load(const void* data,size_t bytes,const char*& error){Validate();if(!_catalog.Load(data,bytes,error))return false;if(_catalog.LabelCount()>MAX_LABELS){error="too many bitmap labels";return false;}if(!RendererBackendGet().BitmapTextSupported()){error="renderer does not support native-pixel bitmap text";return false;}Validate();return true;}
Presenter::~Presenter(){Validate();auto& rb=RendererBackendGet();if(_texture&&_generation==rb.TextureGeneration())rb.DestroyTexture(_texture);}
void Presenter::BeginLabels(){Validate();for(int i=0;i<_signCount;++i)_signs[i].visible=false;}
void Presenter::BuildSigns(int height){
    Validate();if(height==_signHeight)return;_signHeight=height;_signCount=_catalog.LabelCount();
    const int variant=_catalog.SelectVariant(1,height<900?18:24);int count=0;const char* error=NULL;Layout layout;
    for(int i=0;i<_signCount;++i){Label label=_catalog.GetLabel(i);if(!layout.Wrap(_catalog,variant,label.text,label.bytes,10000,error))Fatal(error);
        if(layout.LineCount()!=1)Fatal("world sign must fit one line");int first=count;
        if(count>=MAX_LABEL_GLYPHS)Fatal("too many world sign quads");
        const int backdrop=count++;
        const Variant v=_catalog.GetVariant(variant);int x=-int(floorf(layout.GetLine(0).width*0.5f+0.5f));
        if(!layout.Draw(_catalog,variant,label.text,label.bytes,0,1,x,0,v.lineStep,0,0xEFE4C9FFu,_signQuads,count,MAX_LABEL_GLYPHS,error))Fatal(error);
        float left=0,right=0,top=0,bottom=0;
        for(int q=backdrop+1;q<count;++q){const Quad& glyph=_signQuads[q];
            if(q==backdrop+1){left=glyph.x0;right=glyph.x1;top=glyph.y0;bottom=glyph.y1;}
            else{if(glyph.x0<left)left=glyph.x0;if(glyph.x1>right)right=glyph.x1;if(glyph.y0<top)top=glyph.y0;if(glyph.y1>bottom)bottom=glyph.y1;}
        }
        const float u=0.5f/_catalog.Width(),texV=0.5f/_catalog.Height();
        _signQuads[backdrop]={left-6,top-4,right+6,bottom+4,u,texV,u,texV,0,0x202B36FFu};
        _signs[i]={label.actor,first,count-first,0,0,0,false};
    }Validate();
}
bool Presenter::CaptureLabel(int actor,float x,float y,float z,int width,int height){
    Validate();BuildSigns(height);for(int i=0;i<_signCount;++i)if(_signs[i].actor==actor){Sign& sign=_signs[i];sign.visible=RendererBackendGet().ProjectTextAnchor(x,y,z,width,height,sign.x,sign.y,sign.depth);return true;}return false;
}
void Presenter::Draw(Mailboxes& mb,int width,int height){
    Validate();if(width<1||height<1)return;auto& rb=RendererBackendGet();
    if(!_texture||_generation!=rb.TextureGeneration()){
        _generation=rb.TextureGeneration();_texture=rb.CreateTexture(_catalog.Width(),_catalog.Height(),RB_TEX_COVERAGE8,_catalog.Pixels());
        if(!_texture)Fatal("glyph atlas upload failed");
    }
    const int beat=mb.ReadMailbox(_catalog.Binding(0)).WholePart();
    if(!beat){_beat=0;_page=-1;mb.WriteMailbox(_catalog.Binding(3),Scalar::zero);mb.WriteMailbox(_catalog.Binding(5),Scalar::zero);
        for(int i=0;i<_signCount;++i){const Sign& sign=_signs[i];if(sign.visible&&_catalog.GetLabel(i).realm==mb.ReadMailbox(_catalog.Binding(6)).WholePart())rb.DrawGlyphs(_signQuads+sign.first,sign.count,width,height,_texture,true,sign.x,sign.y,sign.depth);}return;
    }
    const char* error=NULL;int setting=mb.ReadMailbox(_catalog.Binding(4)).WholePart();if(setting<0||setting>2)Fatal("text-size step outside 0..2");
    int page=mb.ReadMailbox(_catalog.Binding(2)).WholePart();
    if(beat!=_beat||width!=_width||height!=_height||setting!=_size){
        int anchor=beat==_beat?_body.Anchor(page,_capacity):0;
        _beat=beat;_width=width;_height=height;_size=setting;
        if(!_catalog.GetText(beat,_text))Fatal("selected semantic beat absent from text catalog");
        const int factor[3]={2,3,4};int bodyPixels=(height<900?28:42)*factor[setting]/2;
        int headingPixels=(height<900?36:54)*factor[setting]/2,controlPixels=(height<900?24:36)*factor[setting]/2;
        _bodyVariant=_catalog.SelectVariant(0,bodyPixels);_headingVariant=_catalog.SelectVariant(1,headingPixels);_controlVariant=_catalog.SelectVariant(0,controlPixels);
        Variant body=_catalog.GetVariant(_bodyVariant),heading=_catalog.GetVariant(_headingVariant),control=_catalog.GetVariant(_controlVariant);
        _bodyX=int(width*0.04f+0.5f);int margin=int(height*0.04f+0.5f),usable=width-2*_bodyX;
        Layout progress;const char* maximum="256 / 256";
        if(!progress.Wrap(_catalog,_controlVariant,maximum,int(strlen(maximum)),usable,error))Fatal(error);
        const int progressWidth=int(ceilf(progress.GetLine(0).width))+control.pixels;
        if(!_heading.Wrap(_catalog,_headingVariant,_text.title,_text.titleBytes,usable-progressWidth,error)||!_controls.Wrap(_catalog,_controlVariant,kControls,int(strlen(kControls)),usable,error)||!_body.Wrap(_catalog,_bodyVariant,_text.body,_text.bodyBytes,usable,error))Fatal(error);
        _headingY=margin+heading.ascent;
        _bodyY=margin+_heading.LineCount()*heading.lineStep+body.pixels/2+body.ascent;
        _controlY=height-margin-_controls.LineCount()*control.lineStep+control.ascent;
        int bodyBottom=_controlY-control.ascent-body.pixels/2;
        _capacity=(bodyBottom-(_bodyY-body.ascent))/body.lineStep;
        if(_capacity<1)Fatal("output cannot fit heading, body and controls at native glyph size");
        page=_body.PageForAnchor(anchor,_capacity);_page=-1;
        fprintf(stderr,"BITMAP_TEXT beat=%d surface=%dx%d body_px=%d page_capacity=%d pages=%d atlas=%dx%d R8\n",beat,width,height,body.pixels,_capacity,_body.PageCount(_capacity),_catalog.Width(),_catalog.Height());
    }
    const int pages=_body.PageCount(_capacity);if(page<0||page>=pages)Fatal("display page outside current beat");
    mb.WriteMailbox(_catalog.Binding(2),Scalar(page));mb.WriteMailbox(_catalog.Binding(3),Scalar(pages));
    if(_page!=page){
        _page=page;_quadCount=0;Variant body=_catalog.GetVariant(_bodyVariant),heading=_catalog.GetVariant(_headingVariant),control=_catalog.GetVariant(_controlVariant);
        if(!_heading.Draw(_catalog,_headingVariant,_text.title,_text.titleBytes,0,_heading.LineCount(),_bodyX,_headingY,heading.lineStep,0,0xECD7A2FFu,_quads,_quadCount,Layout::MAX_QUADS,error)||!_body.Draw(_catalog,_bodyVariant,_text.body,_text.bodyBytes,page*_capacity,_capacity,_bodyX,_bodyY,body.lineStep,0,0xF3EEE3FFu,_quads,_quadCount,Layout::MAX_QUADS,error)||!_controls.Draw(_catalog,_controlVariant,kControls,int(strlen(kControls)),0,_controls.LineCount(),_bodyX,_controlY,control.lineStep,0,0xC8BEA6FFu,_quads,_quadCount,Layout::MAX_QUADS,error))Fatal(error);
        char progress[32];std::snprintf(progress,sizeof(progress),"%d / %d",page+1,pages);
        Layout progressLayout;if(!progressLayout.Wrap(_catalog,_controlVariant,progress,int(strlen(progress)),width,error))Fatal(error);
        int progressX=width-_bodyX-int(ceilf(progressLayout.GetLine(0).width));
        if(!progressLayout.Draw(_catalog,_controlVariant,progress,int(strlen(progress)),0,1,progressX,_headingY,control.lineStep,0,0xC8BEA6FFu,_quads,_quadCount,Layout::MAX_QUADS,error))Fatal(error);
    }
    const PhonepadRect background={0,0,float(width),float(height),0x202B36FFu};rb.DrawOverlay(&background,1,width,height);
    // Keep the opaque reading surface during the existing camera-ready delay.
    if(mb.ReadMailbox(_catalog.Binding(1)).WholePart()){
        rb.DrawGlyphs(_quads,_quadCount,width,height,_texture,false);
        mb.WriteMailbox(_catalog.Binding(5),Scalar(beat));
    }else mb.WriteMailbox(_catalog.Binding(5),Scalar::zero);
    Validate();
}
}
