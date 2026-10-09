#include <pigsys/pigsys.hp>
#include "../../../engine/runtime_options.hpp"
#include <game/fps_overlay.hp>
#include <game/runtime_profile.hp>
#include <game/plant_settings.h>
#include <gfx/display.hp>
#include <gfx/vmem.hp>
#include <gfx/static_mesh.hp>
#include <hal/halbase.h>
#include <cpplib/stdstrm.hp>
#include <cpplib/libstrm.hp>
#include <game/gamestrm.hp>
#include <fstream>
#include <sstream>
#include <cmath>

extern Scalar FakeFrameRate;
extern int gDebugPort,gFrameStepSmokeCount,gFrameStepCycles,gCaptureFrame;
extern char gDebugBind[256];
extern const char* gLevelOverridePath;
extern const char* gCapturePath;
extern bool gWindowed,gEditorMode,gFrameStepNoSwap,gFrameRateChecks,gMemoryTest,gWfmutSmoke,gWfmutThreadTest;
extern "C" void WFScriptProfileEnable() __attribute__((weak));
extern "C" bool WFScriptProfileEnabled() __attribute__((weak));

namespace wfoptions {
namespace {
std::string number(double value){std::ostringstream out;out.precision(12);out<<value;return out.str();}
float selectedHz=20;
int surfaceWidth=0,surfaceHeight=0;
#if SW_DBSTREAM > 0
std::map<std::string,std::ostream*> streams(){
    std::map<std::string,std::ostream*> result={{"runtime_stream_p_w",&cwarn},{"runtime_stream_p_e",&cerror},{"runtime_stream_p_f",&cfatal},{"runtime_stream_p_s",&cstats},{"runtime_stream_p_p",&cprogress},{"runtime_stream_p_d",&cdebug},{"runtime_stream_p_u",&cuser}};
#define STREAMENTRY(stream,where,initial,helptext) result[std::string("runtime_stream_s_")+initial]=&stream;
#define EXTERNSTREAMENTRY STREAMENTRY
#include "gamestrm.inc"
#undef STREAMENTRY
#undef EXTERNSTREAMENTRY
#define STREAMENTRY(stream,where,initial,helptext) result[std::string("runtime_stream_l_")+initial]=&stream;
#include "../libstrm.inc"
#undef STREAMENTRY
    return result;
}
struct Sink {std::string target;std::unique_ptr<std::ofstream> file;std::streambuf* buffer=nullptr;};
std::map<std::string,Sink> activeSinks,preparedSinks;
std::string streamValue(std::ostream& stream,const std::string& key){
    auto it=activeSinks.find(key);if(it!=activeSinks.end()&&it->second.buffer==stream.rdbuf())return it->second.target;
    return DescribeStandardStream(stream);
}
#endif
Snapshot read(){
    Snapshot result;
    auto ghost=[&](const std::string& key,const std::string& value,const std::string& reason="Load-time option; no live application adapter"){result["runtime_"+key]={value,false,reason};};
    const double delta=FakeFrameRate.AsFloat();
    result["runtime_show_fps"]={fpscounter::enabled?"1":"0",true,"Changes the FPS overlay on Apply"};
    result["runtime_fixed_clock"]={delta>0?"1":"0",true,"Fixed simulation clock; presentation rate is independent"};
    result["runtime_clock_hz"]={number(delta>0?std::round(1/delta):selectedHz),true,"1 to 1000 Hz; disable Fixed simulation clock for real time"};
    result["runtime_frame_profile"]={wf_profile::enabled()?"1":"0",!wf_profile::enabled(),wf_profile::enabled()?"Active; stopping is unsupported":"Enable once; starts a fresh profiling window"};
    const bool scriptAvailable=WFScriptProfileEnable&&WFScriptProfileEnabled;
    const bool scriptOn=scriptAvailable&&WFScriptProfileEnabled();
    result["runtime_script_profile"]={scriptOn?"1":"0",scriptAvailable&&!scriptOn,!scriptAvailable?"Unavailable in the linked scripting backend":scriptOn?"Active; stopping is unsupported":"Enable once; starts a fresh profiling window"};
#if defined(RENDERER_PIPELINE_GL) || defined(RENDERER_PIPELINE_GLES)
    ghost("static_mesh",StaticMeshEnabled()?"On":"Off","Cached renderer setting; live rebuild unsupported");
    ghost("static_cull",StaticMeshFastCullEnabled()?"fast":"exact","Cached renderer setting; live change unsupported");
    ghost("shared_index",StaticMeshSharedIndex()?"On":"Off","Cached buffer ownership; live migration unsupported");
    ghost("bake_budget",std::to_string(StaticMeshBakeBudget()),"Cached renderer setting; live change unsupported");
#endif
    ghost("width",std::to_string(surfaceWidth),"Effective surface pixels; recreation required");ghost("height",std::to_string(surfaceHeight),"Effective surface pixels; recreation required");
    ghost("vram_width",std::to_string(Display::VRAMWidth));ghost("vram_height",std::to_string(Display::VRAMHeight));
    ghost("slot_width",std::to_string(VideoMemory::VRAMTransientWidth));ghost("slot_height",std::to_string(VideoMemory::VRAMTransientHeight));
    ghost("perm_width",std::to_string(VideoMemory::VRAMPermanentWidth));ghost("perm_height",std::to_string(VideoMemory::VRAMPermanentHeight));
    ghost("halmem",std::to_string(cbHalLmalloc),"Allocated arena; startup capability DESIGNER_CHEATS");
    ghost("scratchmem",std::to_string(cbHalScratchLmalloc),"Allocated arena; startup capability DESIGNER_CHEATS");
#ifdef WF_DEBUG_BRIDGE
    ghost("debug_port",std::to_string(gDebugPort));ghost("debug_bind",gDebugBind);
#else
    ghost("debug_port","unavailable","Debug bridge omitted");ghost("debug_bind","unavailable","Debug bridge omitted");
#endif
    ghost("level_path",gLevelOverridePath?gLevelOverridePath:"CD bundle","Loaded level source; requires level transition");
    ghost("windowed",gWindowed?"requested":"not requested","Parsed launch request; no live adapter");
    ghost("editor",gEditorMode?"On":"Off","Startup execution mode; requires WF_ENABLE_EDITOR");
    ghost("smoke_frames",std::to_string(gFrameStepSmokeCount));ghost("cycles",std::to_string(gFrameStepCycles));
    ghost("no_swap",gFrameStepNoSwap?"On":"Off");ghost("rate_checks",gFrameRateChecks?"On":"Off");
    ghost("capture_frame",gCaptureFrame?std::to_string(gCaptureFrame)+"="+(gCapturePath?gCapturePath:""):"not scheduled","Conditional frame writer; no live scheduling adapter");
    ghost("memory_test",gMemoryTest?"On":"Off");ghost("mutation_smoke",gWfmutSmoke?"On":"Off");ghost("mutation_thread",gWfmutThreadTest?"On":"Off");
#if SW_DBSTREAM > 0
    for(const auto& entry:streams())result[entry.first]={streamValue(*entry.second,entry.first),true,
#if DO_DEBUG_FILE_SYSTEM
        "Targets n (null), s (stdout), e (stderr), f<path>; monochrome unsupported"
#else
        "Targets n (null), s (stdout), e (stderr); file and monochrome unavailable in this build"
#endif
    };
#endif
    return result;
}
bool prepare(const Changes& changes,std::string& error){
#if SW_DBSTREAM > 0
    preparedSinks.clear();
#endif
    for(const auto& change:changes){
        if(change.first.compare(0,15,"runtime_stream_"))continue;
#if SW_DBSTREAM > 0
        if(!streams().count(change.first)){error="Unknown stream channel";return false;}
        const auto& target=change.second;Sink sink;sink.target=target;
        if(target=="n")sink.buffer=cnull.rdbuf();else if(target=="s")sink.buffer=std::cout.rdbuf();else if(target=="e")sink.buffer=std::cerr.rdbuf();
#if DO_DEBUG_FILE_SYSTEM
        else if(target.size()>1&&target[0]=='f'&&target.find_first_of("\r\n")==std::string::npos&&target.find('\0')==std::string::npos){
            sink.file.reset(new std::ofstream(target.substr(1),std::ios::app));
            if(!sink.file->good()){error="Cannot open stream output; previous sinks retained";preparedSinks.clear();return false;}sink.buffer=sink.file->rdbuf();
        }
#endif
        else{error="Unsupported stream destination";preparedSinks.clear();return false;}
        preparedSinks[change.first]=std::move(sink);
#else
        error="Debug streams unavailable";return false;
#endif
    }
    return true;
}
void apply(const Changes& changes){
    auto value=[&](const char* key)->const std::string*{auto it=changes.find(key);return it==changes.end()?nullptr:&it->second;};
    if(auto v=value("runtime_show_fps"))fpscounter::enabled=*v=="1";
    if(FakeFrameRate.AsFloat()>0)selectedHz=float(std::round(1/FakeFrameRate.AsFloat()));
    if(auto v=value("runtime_clock_hz"))selectedHz=float(std::stod(*v));
    bool fixed=FakeFrameRate.AsFloat()>0;if(auto v=value("runtime_fixed_clock"))fixed=*v=="1";
    if(value("runtime_fixed_clock")||value("runtime_clock_hz"))FakeFrameRate=fixed?Scalar::FromDouble(1/selectedHz):Scalar::zero;
    if(auto v=value("runtime_frame_profile"))if(*v=="1")wf_profile::enableFresh();
    if(auto v=value("runtime_script_profile"))if(*v=="1"&&WFScriptProfileEnable)WFScriptProfileEnable();
#if SW_DBSTREAM > 0
    for(auto& entry:preparedSinks){auto* stream=streams().at(entry.first);stream->flush();stream->rdbuf(entry.second.buffer);stream->clear();activeSinks[entry.first]=std::move(entry.second);}preparedSinks.clear();
#endif
    std::fprintf(stderr,"RUNTIME-OPTIONS applied=%zu fps=%d fixed_delta=%.9g frame_profile=%d script_profile=%d\n",changes.size(),int(fpscounter::enabled),FakeFrameRate.AsFloat(),int(wf_profile::enabled()),int(WFScriptProfileEnabled&&WFScriptProfileEnabled()));
}
}
void surfaceSize(int width,int height){surfaceWidth=width;surfaceHeight=height;}
void registerBaseline(wfprops::Registry& registry){if(registry.schema("BaselineSettings"))install(registry,Backend{read,prepare,apply});}
}
