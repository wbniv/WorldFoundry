#!/usr/bin/env python3
"""Compile the shared source helper with the real zForth VM and run regressions."""
import ast
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='forth-source-') as temp:
    tmp=Path(temp)
    src=(ROOT/'engine/stubs/scripting_zforth.cc').read_text()
    core=src[src.index('static const char* kCoreBootstrap ='):src.index('void Init(')]
    core=re.sub(r'//[^\n]*','',core)
    bootstrap=''.join(ast.literal_eval(x) for x in re.findall(r'"(?:\\.|[^"\\])*"',core))
    vendor=(ROOT/'engine/vendor/zforth-41db72d1/forth/core.zf').read_text()
    strings=vendor[vendor.index(': s"'):vendor.index('\n\n\n(',vendor.index(': ."'))]
    (tmp/'bootstrap.fth').write_text(bootstrap+'\n: emit 0 sys ; : tell 2 sys ;\n'+strings)
    (tmp/'test.cc').write_text(r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include "forth_source.hp"
#include "zforth.h"
static zf_ctx ctx;
static int count=0;
extern "C" zf_input_state zf_host_sys(zf_ctx*c,zf_syscall_id id,const char*) {
 if(id==ZF_SYSCALL_EMIT)zf_pop(c);
 else if(id==ZF_SYSCALL_TELL){zf_pop(c);zf_pop(c);}
 else std::abort();
 return ZF_INPUT_INTERPRET;
}
extern "C" void zf_host_trace(zf_ctx*,const char*,va_list){}
extern "C" zf_cell zf_host_parse_num(zf_ctx*c,const char*s){char*e;float n=strtof(s,&e);if(*e){fprintf(stderr,"Unknown: %s\n",s);zf_abort(c,ZF_ABORT_NOT_A_WORD);}return n;}
void check(bool ok,const char*what){if(!ok){fprintf(stderr,"FAIL %s\n",what);std::exit(1);}++count;}
void eval(const std::string&s){check(zf_eval(&ctx,s.c_str())==ZF_OK,s.c_str());}
void run(const char*source,float expected){
 auto p=forth_source::Split(source);
 if(!p.definitions.empty())eval(p.definitions);
 eval(forth_source::Wrap("test-entry",p.body));
 eval("test-entry");check(zf_pop(&ctx)==expected,source);
 zf_cell stack=1;zf_uservar_get(&ctx,ZF_USERVAR_DSP,&stack);check(stack==0,"balanced stack");
}
int main(int argc,char**argv){
 zf_init(&ctx,0);zf_bootstrap(&ctx);FILE*f=fopen(argv[1],"r");char buf[20000];int n=fread(buf,1,sizeof(buf)-1,f);buf[n]=0;fclose(f);eval(buf);
 run("41 1 +",42);
 run("\\ wf\n41 1 +",42);
 run(" \t\\ wf\r\n41 1 +",42);
 run("\\ ordinary comment ;\n42",42);
 run("\\ wf extra words ;\n42",42);
 run(": answer 42 ; answer \\ trailing ; : nonsense",42);
 run(": answer ( ; : ) 42 ; answer ( ; )",42);
 run(": a 20 ; \\ ;\n: b 22 ; a b +",42);
 run(": a 42 \\ ; nonsense\n; a",42);
 run("\\\n42",42);
 run("\\\r\n42",42);
 run("42 \\",42);
 run("42 \\",42);
 run("42 \\ words\r\n",42);
 run(": a 42 ; s\" ; \\ ( not syntax\" 2drop a",42);
 run(": a s\" ; \\ quoted\" 2drop 42 ; a",42);
 run(": a 42 ; .\" ; \\ printed\" a",42);
 auto p=forth_source::Split(": s\" compiling @ ; 42 \\ ;");
 check(p.body==" 42 \\ ;","string-word definition name isn't a string literal");
 p=forth_source::Split(": quoted ' ; drop ; quoted \\ ;");
 check(p.body==" quoted \\ ;","tick-quoted semicolon isn't a terminator");
 p=forth_source::Split(": quoted postpone ; ; quoted");
 check(p.body==" quoted","postponed word isn't a terminator");
 for(const char*body:{"", "\\", "\\ ;", "( ; )", ": only 1 ;"}) {
   auto parts=forth_source::Split(body);if(!parts.definitions.empty())eval(parts.definitions);
   eval(forth_source::Wrap("empty",parts.body));eval("empty");
   zf_cell d;zf_uservar_get(&ctx,ZF_USERVAR_DSP,&d);check(d==0,"empty script stack");
 }
 // Direct VM EOF comments must not contaminate a following eval.
 eval("\\ eof");eval("42");check(zf_pop(&ctx)==42,"EOF line comment resets parser");
 eval("\\");eval("42");check(zf_pop(&ctx)==42,"bare EOF line comment resets parser");
 eval("\\\n42");check(zf_pop(&ctx)==42,"bare empty line comment");
 eval(": stable 1 drop ;");zf_cell before,after,dsp,rsp;
 zf_uservar_get(&ctx,ZF_USERVAR_HERE,&before);
 for(int i=0;i<10000;i++)eval("stable");
 zf_uservar_get(&ctx,ZF_USERVAR_HERE,&after);zf_uservar_get(&ctx,ZF_USERVAR_DSP,&dsp);zf_uservar_get(&ctx,ZF_USERVAR_RSP,&rsp);
 check(before==after && dsp==0 && rsp==0,"execution doesn't grow dictionary or stacks");
 printf("PASS: %d checks, including 10000 repeated calls\n",count);
}
''')
    inc=['-I'+str(ROOT/'engine/stubs'),'-I'+str(ROOT/'engine/vendor/zforth-41db72d1/src/zforth')]
    subprocess.run(['cc',*inc,'-c',str(ROOT/'engine/vendor/zforth-41db72d1/src/zforth/zforth.c'),'-o',str(tmp/'vm.o')],check=True)
    subprocess.run(['c++','-std=c++17',*inc,str(tmp/'test.cc'),str(tmp/'vm.o'),'-o',str(tmp/'test')],check=True)
    subprocess.run([str(tmp/'test'),str(tmp/'bootstrap.fth')],check=True)
