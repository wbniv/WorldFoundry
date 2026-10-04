#include "plant_ui.h"
#include <hal/remote_back_arrow.h>
#include "../../../engine/vendor/stb_easy_font.h"
namespace planted {
void uiInput(uint32_t buttons){
 static uint32_t previous=0;uint32_t edge=buttons&~previous;previous=buttons;auto& s=state();if(!s.modal||s.phone)return;
 const uint32_t up=1u<<11,down=1u<<12,right=1u<<13,left=1u<<14;
 if(s.focus==1&&s.adjustSpeed&&(edge&(left|right)))s.draftSpeed=std::max(0,std::min(6,s.draftSpeed+((edge&right)?1:-1)));
 else if(edge&(up|down|left|right)){
  s.adjustSpeed=false;
  struct Cell{int id;float x,y;};std::vector<Cell> cells={{0,1245,275},{1,1245,370},{14,1245,472},{15,1245,557},{17,1245,727}};
  for(int k=0;k<12;k++)cells.push_back({k+2,505.f+(k%3)*175,359.f+(k/3)*85});
  Cell from=cells[0];for(auto c:cells)if(c.id==s.focus)from=c;
  int best=s.focus;float bestScore=1e20f;
  for(auto c:cells){float primary,secondary;if(edge&(left|right)){primary=(c.x-from.x)*((edge&right)?1:-1);secondary=std::fabs(c.y-from.y);}else{primary=(c.y-from.y)*((edge&down)?1:-1);secondary=std::fabs(c.x-from.x);}if(primary<=1)continue;float score=primary+secondary*2.5f;if(score<bestScore){bestScore=score;best=c.id;}}
  s.focus=best;
 }
 if(!(edge&1))return;
 if(s.focus==0)s.draftSalt=!s.draftSalt;
 else if(s.focus==1)s.adjustSpeed=!s.adjustSpeed;
 else if(s.focus>=2&&s.focus<14){const char* keys[]={"1","2","3","4","5","6","7","8","9","<","0","Clear"};int k=s.focus-2;if(k==9){s.seedTyped=true;if(!s.draft.empty())s.draft.pop_back();}else if(k==11){s.draft.clear();s.seedTyped=true;}else {if(!s.seedTyped){s.draft.clear();s.seedTyped=true;}if(s.draft.size()<10)s.draft+=keys[k];}s.error.clear();}
 else if(s.focus==14)submit();else if(s.focus==15)submit(true);else cancel();
}
void buildUI(int w,int h,std::vector<PhonepadRect>& out){
 auto& s=state();out.clear();if(!s.active&&!s.modal)return;
 float sx=w/1920.f,sy=h/1080.f;
 auto rect=[&](float x,float y,float width,float height,uint32_t color){out.push_back({x*sx,y*sy,(x+width)*sx,(y+height)*sy,color});};
 auto text=[&](float x,float y,float scale,const std::string& str,uint32_t color=0xf1f2e4ffu){alignas(float) char buf[24000];int n=stb_easy_font_print(0,0,const_cast<char*>(str.c_str()),nullptr,buf,sizeof(buf));float* f=reinterpret_cast<float*>(buf);for(int i=0;i<n;i++){float* v=f+i*16;float x0=v[0],y0=v[1],x1=x0,y1=y0;for(int k=1;k<4;k++){x0=std::min(x0,v[k*4]);x1=std::max(x1,v[k*4]);y0=std::min(y0,v[k*4+1]);y1=std::max(y1,v[k*4+1]);}rect(x+x0*scale,y+y0*scale,(x1-x0)*scale,(y1-y0)*scale,color);}};
 if(s.active){rect(42,984,890,54,0x102621ddu);text(60,998,3,"Seed: "+std::to_string(s.seed)+" | "+(s.salt?"Saltwater":"Freshwater")+" | Hold A: settings");}
 if(!s.modal)return;
 rect(0,0,1920,1080,0x061014bbu);rect(375,145,1170,760,0x142d25ffu);text(420,180,5,"Plant settings");
 struct ArrowPainter {decltype(rect)& draw; void Rect(float x0,float y0,float x1,float y1,uint32_t c){draw(x0,y0,x1-x0,y1-y0,c);} } painter{rect};
 if(s.phone){text(425,350,4,"Edit settings on your connected phone");text(425,430,3,"Seed: "+std::to_string(s.seed));remoteui::BackArrow(painter,425,520,5,0xf1f2e4ffu);text(485,520,3,"Apply settings and close");return;}
 auto item=[&](int i,float x,float y,float width,float height,const std::string& label){rect(x,y,width,height,s.focus==i?0x497b51ffu:0x233e31ffu);text(x+18,y+18,3,label);};
 text(425,255,3,"Seed: "+(s.draft.empty()?"_":s.draft));item(0,1000,245,490,60,s.draftSalt?"Water: Saltwater":"Water: Freshwater");item(1,1000,320,490,100,std::string(s.adjustSpeed?"Adjust speed: ":"Growth speed: ")+speedLabel(s.draftSpeed));
 rect(1020,392,445,4,0x9aac9affu);for(int i=0;i<7;i++)rect(1017+i*74,385,6,18,0x9aac9affu);rect(1010+s.draftSpeed*74,379,20,30,0xe6df96ffu);
 const char* keys[]={"1","2","3","4","5","6","7","8","9","<","0","Clear"};for(int k=0;k<12;k++)item(2+k,425+(k%3)*175,325+(k/3)*85,160,68,keys[k]);
 item(14,1000,440,490,65,"Regenerate");item(15,1000,525,490,65,"New random seed");item(17,1000,695,490,65,"Cancel");
 if(!s.error.empty())text(425,810,2.8f,s.error,0xffbb88ffu);else text(425,810,2.8f,s.adjustSpeed?"Left / right: speed   A: finish adjusting":"Arrows: select   A: confirm / adjust speed");
 remoteui::BackArrow(painter,1280,810,4,0xf1f2e4ffu);text(1330,810,2.8f,"Apply / close");
}
}
