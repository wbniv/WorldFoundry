#!/usr/bin/env python3
"""Run the actual camera Forth in the existing vendor VM at controlled timesteps.

The temporary harness mocks mailbox I/O only; it does not replace camera policy
with a Python model or modify/rebuild the game engine.
"""
import ast
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='condo-camera-forth-') as temp:
    tmp=Path(temp)
    src=(ROOT/'engine/stubs/scripting_zforth.cc').read_text()
    core=src[src.index('static const char* kCoreBootstrap ='):src.index('void Init(')]
    core=re.sub(r'//[^\n]*','',core)
    bootstrap=''.join(ast.literal_eval(x) for x in re.findall(r'"(?:\\.|[^"\\])*"',core))
    mailbox=(ROOT/'wfsource/source/mailbox/mailbox.inc').read_text()
    constants={f'INDEXOF_{k}':int(v) for k,v in re.findall(r'MAILBOXENTRY\(\s*(\w+)\s*,\s*(\d+)',mailbox)}
    constants.update({f'JOYSTICK_BUTTON_{k}':1<<i for i,k in enumerate('ABCDEFGHIJK')})
    constants.update({f'JOYSTICK_BUTTON_{k}':1<<i for i,k in enumerate(('UP','DOWN','RIGHT','LEFT'),11)})
    controls=(ROOT/'wflevels/condo_639_640/camera_controls.fth').read_text()
    config={'shot':5,'camera':1,'touch':0,'default-yaw':0,'default-elevation':.1850858,
            'default-range':8.823831,'unit-z':15.75,'look-x':0,'look-y':0,'look-z':.9,
            'default-x':0,'default-y':-3.5,'default-z':9,'label-0':0,'label-1':0,'label-2':0}
    definitions=bootstrap+'\n'+''.join(f': {k} {v} ;\n' for k,v in constants.items())
    definitions+=': read-mailbox 128 sys ; : write-mailbox 129 sys ; : write-actor-mailbox 130 sys ;\n'
    definitions+=': r@ 0 pickr ;\n'
    definitions+=''.join(f': cc-{k} {v} ;\n' for k,v in config.items())+controls
    (tmp/'controls.fth').write_text(definitions)
    harness=r'''
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "zforth.h"
static float mb[7000]; static zf_ctx ctx;
zf_input_state zf_host_sys(zf_ctx*c,zf_syscall_id id,const char*w){
 int actor,idx;
 if(id==128){idx=zf_pop(c);zf_push(c,mb[idx]);}
 else if(id==129){idx=zf_pop(c);mb[idx]=zf_pop(c);}
 else if(id==130){actor=zf_pop(c);idx=zf_pop(c);zf_pop(c);}
 else {fprintf(stderr,"Unexpected syscall %d\n",id);exit(1);}
 return ZF_INPUT_INTERPRET;
}
void zf_host_trace(zf_ctx*c,const char*f,va_list v){}
zf_cell zf_host_parse_num(zf_ctx*c,const char*s){char*e;float n=strtof(s,&e);if(*e){fprintf(stderr,"Unknown %s\n",s);zf_abort(c,ZF_ABORT_NOT_A_WORD);}return n;}
void eval(const char*s){int r=zf_eval(&ctx,s);if(r){fprintf(stderr,"Forth error %d: %s\n",r,s);exit(1);}}
void check(int yes,const char*s){if(!yes){fprintf(stderr,"FAIL %s\n",s);exit(1);}printf("PASS %s\n",s);}
void tick(float dt,int keys){mb[1907]=dt;mb[1909]=keys;eval("cc-input");zf_cell d;zf_uservar_get(&ctx,ZF_USERVAR_DSP,&d);check(d==0,"balanced data stack");}
int main(int argc,char**argv){
 zf_init(&ctx,0);zf_bootstrap(&ctx);char buf[40000];FILE*f=fopen(argv[1],"r");int n=fread(buf,1,sizeof(buf)-1,f);buf[n]=0;fclose(f);eval(buf);
 mb[3011]=15.75;
 for(int rate=20;rate<=60;rate+=40){
   eval("cc-reset");for(int i=0;i<rate;i++)tick(1.0f/rate,8|8192);
   check(fabsf(mb[114]-1.0f/6)<.00002f,"equal one-second orbit at 20/60 Hz");
 }
 for(int i=0;i<4;i++){char s[64];snprintf(s,sizeof(s),"%f cc-sin",i*.25f);eval(s);float v=zf_pop(&ctx);check(fabsf(v-(float[]){0,1,0,-1}[i])<.00001f,"sine cardinal");}
 eval("cc-reset");tick(4,8|8192);check(mb[114]<.009f,"stall step bounded");
 mb[115]=0;tick(.02,16);check(mb[115]>.097f && isfinite(mb[132]),"low authored angle safely enters manual mode");
 for(int i=0;i<10000;i++)tick(.02,8|8192);
 check(mb[114]>=0 && mb[114]<1 && isfinite(mb[132]),"long orbit stays finite and wraps");
 return 0;
}
'''
    (tmp/'check.c').write_text(harness)
    subprocess.run(['cc','-I'+str(ROOT/'engine/stubs'),'-I'+str(ROOT/'engine/vendor/zforth-41db72d1/src/zforth'),str(tmp/'check.c'),str(ROOT/'engine/vendor/zforth-41db72d1/src/zforth/zforth.c'),'-lm','-o',str(tmp/'check')],check=True)
    result=subprocess.run([str(tmp/'check'),str(tmp/'controls.fth')],text=True,capture_output=True)
    for line in result.stdout.splitlines():
        if line!='PASS balanced data stack':print(line)
    print(f'Checked {result.stdout.count("PASS balanced data stack")} frames with balanced data stack.')
    if result.returncode:raise SystemExit(result.stderr or result.returncode)
