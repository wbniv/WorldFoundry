/* Execute exported scripts with the real zForth VM; mock mailbox IO and physics only. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "zforth.h"
static zf_ctx pvm,dvm;
static float globals[7000], actors[1024][7000];
static int current_actor,player,director;
static float props[1024][16]; static char propset[1024][16];   /* instance properties for property@ ("prop actor field value") */
zf_input_state zf_host_sys(zf_ctx*c,zf_syscall_id id,const char*w) {
 int mb,a;
 if(id==128){mb=zf_pop(c);zf_push(c,mb<1900?globals[mb]:actors[current_actor][mb]);}
 else if(id==129){mb=zf_pop(c);float v=zf_pop(c);if(mb<1900)globals[mb]=v;else actors[current_actor][mb]=v;}
 else if(id==130){a=zf_pop(c);mb=zf_pop(c);float v=zf_pop(c);if(a<0||a>=1024||mb<0||mb>=7000)exit(2);actors[a][mb]=v;}
 else if(id==152){a=zf_pop(c);mb=zf_pop(c);zf_push(c,mb<1900?globals[mb]:actors[a][mb]);}
 else if(id==172||id==174){for(int i=0;i<5;i++)zf_pop(c);}
 else if(id==175||id==176){zf_pop(c);zf_pop(c);}
 else if(id==171){for(int i=0;i<3;i++)zf_pop(c);}
 else if(id==173){for(int i=0;i<8;i++)zf_pop(c);}                             /* swim-deform */
 else if(id==177){for(int i=0;i<7;i++)zf_pop(c);}
 else if(id==178){int f=zf_pop(c);a=zf_pop(c);int ok=a>=0&&a<1024&&f>=0&&f<16&&propset[a][f];zf_push(c,ok?props[a][f]:0);zf_push(c,ok);}  /* property@ */
 else if(id==179){zf_pop(c);zf_pop(c);for(int i=0;i<5;i++)zf_push(c,0);}
 else if(id==180){for(int i=0;i<3;i++)zf_pop(c);zf_push(c,0);zf_push(c,0);}
 else if(id==181){zf_pop(c);zf_pop(c);int n=zf_pop(c);for(int i=0;i<n;i++)zf_pop(c);zf_push(c,0);}  /* deform: status Ok */
 else if(id==182){for(int i=0;i<4;i++)zf_pop(c);zf_push(c,0);}                /* deform-block: status Ok */
 else if(id==169||id==170||id==0||id==1){zf_pop(c);}
 else {fprintf(stderr,"Unexpected syscall %d\n",id);exit(1);}
 return ZF_INPUT_INTERPRET;
}
void zf_host_trace(zf_ctx*c,const char*f,va_list v){}
zf_cell zf_host_parse_num(zf_ctx*c,const char*s){char*e;float n=strtof(s,&e);if(*e){fprintf(stderr,"Unknown %s\n",s);zf_abort(c,ZF_ABORT_NOT_A_WORD);}return n;}
static void eval(zf_ctx*c,const char*s){int r=zf_eval(c,s);if(r){fprintf(stderr,"Forth error %d: %.150s\n",r,s);exit(1);}zf_cell depth;zf_uservar_get(c,ZF_USERVAR_DSP,&depth);if(depth!=0){fprintf(stderr,"Unbalanced stack %g in %s\n",(double)depth,s);exit(1);}}
static void load(zf_ctx*c,const char*path){char buf[200000];FILE*f=fopen(path,"r");if(!f)exit(2);int n=fread(buf,1,sizeof(buf)-1,f);buf[n]=0;fclose(f);zf_init(c,0);zf_bootstrap(c);eval(c,buf);}
int main(int argc,char**argv){
 player=atoi(argv[3]);director=atoi(argv[4]);load(&pvm,argv[1]);load(&dvm,argv[2]);
 char line[200];int frame=0;
 while(fgets(line,sizeof(line),stdin)){
  if(strncmp(line,"reset",5)==0){float x,y,z;sscanf(line,"reset %f %f %f",&x,&y,&z);memset(globals,0,sizeof(globals));memset(actors,0,sizeof(actors));actors[player][3009]=x;actors[player][3010]=y;actors[player][3011]=z;frame=0;}
  else if(strncmp(line,"prop",4)==0){int pa,pf;float v;sscanf(line,"prop %d %d %f",&pa,&pf,&v);if(pa>=0&&pa<1024&&pf>=0&&pf<16){props[pa][pf]=v;propset[pa][pf]=1;}}
  else if(strncmp(line,"set",3)==0){int mb;float v;sscanf(line,"set %d %f",&mb,&v);globals[mb]=v;}
  else {
   int frames,bits;float dt;sscanf(line,"step %d %d %f",&frames,&bits,&dt);
   for(int i=0;i<frames;i++){
    current_actor=player;actors[player][1907]=dt;actors[player][1909]=bits;eval(&pvm,argv[5]);
    for(int j=0;j<3;j++)actors[player][3009+j]+=actors[player][3018+j]*dt;
    current_actor=director;actors[director][1907]=dt;actors[director][1909]=bits;eval(&dvm,argv[6]);
    printf("%d",frame++);
    for(int j=0;j<3;j++)printf(",%.9g",actors[player][3009+j]);
    for(int j=0;j<3;j++)printf(",%.9g",actors[player][3018+j]);
    for(int j=600;j<=750;j++)printf(",%.9g",globals[j]);
    for(int j=1100;j<=1111;j++)printf(",%.9g",globals[j]);
    for(int j=1200;j<=1280;j++)printf(",%.9g",globals[j]);
    int a=(int)globals[650];for(int j=3009;j<=3014;j++)printf(",%.9g",actors[a][j]);
    printf("\n");
   }
  }
 }
 return 0;
}
