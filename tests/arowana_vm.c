/* Runs the actual generated Forth, mocking only mailbox IO and neutral physics. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "zforth.h"
static zf_ctx player_vm, director_vm;
static float global[7000], actors[64][7000];
static int current_actor, player, director;
static float deform[64][7];
zf_input_state zf_host_sys(zf_ctx*c,zf_syscall_id id,const char*w) {
 int index,a;
 if(id==128){index=zf_pop(c);zf_push(c,index<1900?global[index]:actors[current_actor][index]);}
 else if(id==129){index=zf_pop(c);float v=zf_pop(c);if(index<1900)global[index]=v;else actors[current_actor][index]=v;}
 else if(id==130){a=zf_pop(c);index=zf_pop(c);float value=zf_pop(c);if(a<0||a>=64||index<0||index>=7000){fprintf(stderr,"Invalid write actor=%d mb=%d value=%g\n",a,index,value);exit(1);}actors[a][index]=value;}
 else if(id==152){a=zf_pop(c);index=zf_pop(c);zf_push(c,index<1900?global[index]:actors[a][index]);}
 else if(id==173){a=zf_pop(c);for(int i=6;i>=0;i--)deform[a][i]=zf_pop(c);}
 else {fprintf(stderr,"Unexpected syscall %d\n",id);exit(1);}
 return ZF_INPUT_INTERPRET;
}
void zf_host_trace(zf_ctx*c,const char*f,va_list v){}
zf_cell zf_host_parse_num(zf_ctx*c,const char*s){char*e;float n=strtof(s,&e);if(*e){fprintf(stderr,"Unknown %s\n",s);zf_abort(c,ZF_ABORT_NOT_A_WORD);}return n;}
void eval(zf_ctx*c,const char*s){int r=zf_eval(c,s);if(r){fprintf(stderr,"Forth error %d: %.200s\n",r,s);exit(1);}zf_cell d;zf_uservar_get(c,ZF_USERVAR_DSP,&d);if(d!=0){fprintf(stderr,"Unbalanced stack %g\n",(double)d);exit(1);}}
void load(zf_ctx*c,const char*path){char buf[100000];FILE*f=fopen(path,"r");int n=fread(buf,1,sizeof(buf)-1,f);buf[n]=0;fclose(f);zf_init(c,0);zf_bootstrap(c);eval(c,buf);}
int main(int argc,char**argv){
 player=atoi(argv[3]);director=atoi(argv[4]);load(&player_vm,argv[1]);load(&director_vm,argv[2]);
 char line[200];int scenario=0,frame=0;
 while(fgets(line,sizeof(line),stdin)){
  if(strncmp(line,"reset",5)==0){
   float x,y,z,yaw;sscanf(line,"reset %d %f %f %f %f",&scenario,&x,&y,&z,&yaw);
   memset(global,0,sizeof(global));memset(actors,0,sizeof(actors));
   actors[player][3009]=x;actors[player][3010]=y;actors[player][3011]=z;global[740]=yaw;
   global[760]=1; /* Input init done; first trace command can hold a direction. */
   frame=0;
  }else if(strncmp(line,"set",3)==0){int mb;float v;sscanf(line,"set %d %f",&mb,&v);global[mb]=v;
  }else{
   int frames,bits;float dt;sscanf(line,"step %d %d %f",&frames,&bits,&dt);
   for(int i=0;i<frames;i++){
    current_actor=player;actors[player][1907]=dt;actors[player][1909]=bits;eval(&player_vm,"ar-player-tick");
    for(int j=0;j<3;j++)actors[player][3009+j]+=actors[player][3018+j]*dt;
    current_actor=director;actors[director][1907]=dt;actors[director][1909]=bits;eval(&director_vm,"ar-rig-tick ar-camera-tick");
    printf("%d,%d",scenario,frame++);
    for(int j=0;j<3;j++)printf(",%.9g",actors[player][3009+j]);
    for(int j=0;j<3;j++)printf(",%.9g",actors[player][3018+j]);
    for(int j=740;j<=747;j++)printf(",%.9g",global[j]);
    for(int j=762;j<=769;j++)printf(",%.9g",global[j]);
    printf(",%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g",global[702],global[701],global[761],global[753],global[635],global[608],global[706]);
    for(int a=1;a<64;a++)if(deform[a][6]!=0){
     printf(",%.9g,%.9g,%.9g,%.9g",deform[a][0],deform[a][1],deform[a][2],deform[a][4]);break;
    }
    printf(",%.9g\n",dt);
   }
  }
 }
 return 0;
}
