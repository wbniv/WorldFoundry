"""Exercise the actual Android menu Back branch, including repeats and a visible panel."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def test_back_returns_from_level_and_exits_from_selector(tmp_path):
    entry=(ROOT/'wfsource/source/hal/android/native_app_entry.cc').read_text()
    start=entry.index('        if (keyCode == AKEYCODE_BACK && levelmenu::MenuRunning())')
    end=entry.index('        // In standalone apps',start)
    branch=entry[start:end]
    source=tmp_path/'back.cc'
    source.write_text(r'''
#include <cassert>
#define AKEYCODE_BACK 4
#define AKEY_EVENT_ACTION_DOWN 0
#define AKEY_EVENT_ACTION_UP 1
#define WFLOG(...) ((void)0)
namespace levelmenu {
bool running=true,visible=false;int returns=0;
bool MenuRunning(){return running;} bool SelectorVisible(){return visible;}
void RequestReturn(){++returns;}
}
struct Overlay { int hidden=0; void OnBack(int){++hidden;} } gPhoneOverlay;
int NowMs(){return 0;}
struct App { void* activity; } app{},*gApp=&app;
int exits=0;void ANativeActivity_finish(void*){++exits;}
int handle(int keyCode,int action) {
'''+branch+r'''
return 0;
}
int main() {
  assert(handle(4,0)==1 && levelmenu::returns==0 && exits==0);
  for(int i=0;i<10;i++) handle(4,0);
  handle(4,1);assert(levelmenu::returns==1 && exits==0 && gPhoneOverlay.hidden==1);
  levelmenu::visible=true;
  handle(4,0);assert(exits==0);handle(4,1);assert(exits==1 && levelmenu::returns==1);
  levelmenu::running=false;assert(handle(4,1)==0 && exits==1);
  assert(handle(20,1)==0 && exits==1);
}
''')
    binary=tmp_path/'back'
    subprocess.run(['c++','-std=c++11',str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
