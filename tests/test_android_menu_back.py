"""Exercise the actual Android menu Back branch, including repeats and a visible panel."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def test_back_returns_from_level_and_exits_from_selector(tmp_path):
    entry=(ROOT/'wfsource/source/hal/android/native_app_entry.cc').read_text()
    start=entry.index('        if (keyCode == AKEYCODE_BACK && gPhoneOverlay.PanelVisible(NowMs()))')
    end=entry.index('        // Standalone apps keep',start)
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
struct Overlay { bool visible=false; int hidden=0; bool PanelVisible(int){return visible;} void OnBack(int){visible=false;++hidden;} } gPhoneOverlay;
int repeat=0;int AKeyEvent_getRepeatCount(void*){return repeat;}
int NowMs(){return 0;}
struct App { void* activity; } app{},*gApp=&app;
int exits=0;void ANativeActivity_finish(void*){++exits;}
int handle(int keyCode,int action) {
void* event=nullptr;
'''+branch+r'''
return 0;
}
int main() {
  // Startup: pairing panel above selector. First Back only dismisses it.
  levelmenu::visible=true;gPhoneOverlay.visible=true;
  assert(handle(4,0)==1 && gPhoneOverlay.visible && exits==0);
  repeat=1;for(int i=0;i<10;i++) handle(4,0);repeat=0;
  handle(4,1);assert(!gPhoneOverlay.visible && gPhoneOverlay.hidden==1 && exits==0 && levelmenu::returns==0);
  // A later Back with the unobstructed selector exits.
  handle(4,0);assert(exits==0);handle(4,1);assert(exits==1);
  // Panel shown during a selected level is dismissed without changing level.
  levelmenu::visible=false;gPhoneOverlay.visible=true;
  handle(4,0);handle(4,1);assert(gPhoneOverlay.hidden==2 && levelmenu::returns==0 && exits==1);
  handle(4,0);assert(levelmenu::returns==0);handle(4,1);assert(levelmenu::returns==1 && exits==1);
  // Standalone apps dismiss their panel, then fall through to Android Back.
  levelmenu::running=false;gPhoneOverlay.visible=true;
  handle(4,0);handle(4,1);assert(gPhoneOverlay.hidden==3 && levelmenu::returns==1);
  assert(handle(4,1)==0 && exits==1);
  assert(handle(20,1)==0 && exits==1);
}
''')
    binary=tmp_path/'back'
    subprocess.run(['c++','-std=c++11',str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
