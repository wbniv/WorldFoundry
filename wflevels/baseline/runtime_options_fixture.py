"""Baseline developer controls, with stable identities independent of argv order."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# IDs are part of the runtime consumer contract. Append new IDs; never renumber.
OPTIONS = [
    (1000, 'show_fps', 'Show FPS', ['--no-fps'], 'bool', 'Live', 'fpscounter::enabled', 'overlay'),
    (1001, 'fixed_clock', 'Fixed simulation clock', ['-rateN', '-rate'], 'bool', 'Live', 'FakeFrameRate', 'clock'),
    (1002, 'clock_hz', 'Simulation rate (Hz)', ['-rateN'], 'int', 'Live', 'FakeFrameRate', 'clock'),
    (1003, 'frame_profile', 'Frame profiling', ['--frame-profile'], 'bool', 'Enable only', 'wf_profile::enabled()', 'frame_profile'),
    (1004, 'script_profile', 'Script profiling', ['--script-profile'], 'bool', 'Conditional enable only', 'WFScriptProfileEnabled()', 'script_profile'),
]
GHOSTS = [
    (1005, 'static_mesh', 'Static meshes', ['--static-mesh='], 'Renderer', 'Cached on first use; live rebuild is unavailable'),
    (1006, 'static_cull', 'Static mesh culling', ['--static-mesh-cull='], 'Renderer', 'Cached on first use; live culling change is unavailable'),
    (1007, 'shared_index', 'Shared static indices', ['--static-mesh-shared-index='], 'Renderer', 'Cached on first use; live ownership migration is unavailable'),
    (1008, 'bake_budget', 'Static bake budget', ['--static-mesh-bake-budget='], 'Renderer', 'Cached on first use; live change is unavailable'),
    (1010, 'width', 'Surface width', ['-width='], 'Surface', 'Surface creation only'),
    (1011, 'height', 'Surface height', ['-height='], 'Surface', 'Surface creation only'),
    (1012, 'xpos', 'Window X position', ['-xpos='], 'Surface', 'Desktop startup placement; unavailable on TV/mobile'),
    (1013, 'ypos', 'Window Y position', ['-ypos='], 'Surface', 'Desktop startup placement; unavailable on TV/mobile'),
    (1014, 'fullscreen', 'Fullscreen request', ['-fullscreen', '-window'], 'Surface', 'Startup request; no live window-mode adapter'),
    (1015, 'windowed', 'Windowed request', ['--windowed'], 'Surface', 'Separate parsed request; platform-dependent startup behavior'),
    (1020, 'vram_width', 'VRAM width', ['--vram-width='], 'Allocation', 'Resident texture layout cannot change here'),
    (1021, 'vram_height', 'VRAM height', ['--vram-height='], 'Allocation', 'Resident texture layout cannot change here'),
    (1022, 'slot_width', 'Transient texture width', ['--vram-slot-width='], 'Allocation', 'Resident texture layout cannot change here'),
    (1023, 'slot_height', 'Transient texture height', ['--vram-slot-height='], 'Allocation', 'Resident texture layout cannot change here'),
    (1024, 'perm_width', 'Permanent texture width', ['--vram-perm-width='], 'Allocation', 'Resident texture layout cannot change here'),
    (1025, 'perm_height', 'Permanent texture height', ['--vram-perm-height='], 'Allocation', 'Resident texture layout cannot change here'),
    (1026, 'halmem', 'HAL arena bytes', ['-halmem='], 'Allocation', 'DESIGNER_CHEATS; allocated before level load'),
    (1027, 'scratchmem', 'Scratch arena bytes', ['-scratchmem='], 'Allocation', 'DESIGNER_CHEATS; allocated before level load'),
    (1028, 'psxmem', 'PSX memory preset', ['-psxmem'], 'Allocation', 'Startup allocator preset; has no independent effective value'),
    (1030, 'debug_port', 'Debug listener port', ['--debug-port'], 'Connection', 'Requires bridge capability; no live listener rebind'),
    (1031, 'debug_bind', 'Debug listener address', ['--debug-bind'], 'Connection', 'Requires bridge capability; no live listener rebind'),
    (1040, 'level_path', 'Standalone level', ['-L'], 'Launch and diagnostics', 'Currently loaded level; no live reload adapter'),
    (1041, 'level_number', 'CD launch level', ['level#'], 'Launch and diagnostics', 'Launch selection; not a switch or live transition'),
    (1042, 'editor', 'Editor execution mode', ['--editor'], 'Launch and diagnostics', 'WF_ENABLE_EDITOR; startup execution path'),
    (1043, 'smoke_frames', 'Smoke-test frames', ['--frame-step-smoke='], 'Launch and diagnostics', 'Startup stepping harness'),
    (1044, 'cycles', 'Smoke-test cycles', ['--cycles='], 'Launch and diagnostics', 'Startup stepping harness'),
    (1045, 'no_swap', 'Smoke-test no swap', ['--frame-step-no-swap'], 'Launch and diagnostics', 'Startup stepping harness'),
    (1046, 'rate_checks', 'Frame-rate probes', ['--frame-rate-checks'], 'Launch and diagnostics', 'Stepping harness probes'),
    (1047, 'capture_frame', 'Scheduled frame capture', ['--capture-frame='], 'Launch and diagnostics', 'Conditional writer; no live capture scheduling adapter'),
    (1048, 'menu_input', 'Startup menu input', ['--menu-input='], 'Launch and diagnostics', 'Startup automation queue; live replacement is unavailable'),
    (1049, 'memory_test', 'Memory test', ['--memory-test'], 'Launch and diagnostics', 'Startup test exits before loading a level'),
    (1050, 'mutation_smoke', 'Mutation smoke test', ['--wfmut-smoke'], 'Launch and diagnostics', 'Startup test mode'),
    (1051, 'mutation_thread', 'Mutation thread death test', ['--wfmut-thread-test'], 'Launch and diagnostics', 'Startup death test; never run from Apply'),
    (1052, 'print_actors', 'Print actors at load', ['--debug-print-actors'], 'Launch and diagnostics', 'DO_TEST_CODE; startup actor dump'),
    (1053, 'record_video', 'Video recording', ['-record_video'], 'Launch and diagnostics', 'DESIGNER_CHEATS; startup writer lifecycle'),
    (1054, 'joy', 'Joystick playback', ['-joy'], 'Launch and diagnostics', 'JOYSTICK_RECORDER; startup reader lifecycle'),
    (1055, 'profile_load', 'Legacy load profiler', ['-profmemload'], 'Legacy / unavailable', 'DO_PROFILE; parsed flag has no effective reader'),
    (1056, 'profile_loop', 'Legacy loop profiler', ['-profmainloop'], 'Legacy / unavailable', 'DO_PROFILE; parsed flag has no effective reader'),
    (1057, 'breaktime', 'Debugger break time', ['-breaktime='], 'Launch and diagnostics', 'DO_DEBUGGING_INFO; intentional diagnostic action requires separate review'),
    (1058, 'linear_malloc', 'Legacy linear allocator', ['-lmalloc'], 'Legacy / unavailable', 'DEBUG; parsed flag has no effective reader'),
    (1059, 'zbuffer', 'Legacy Z buffer', ['-zb'], 'Legacy / unavailable', 'Parsed flag has no effective renderer reader'),
    (1060, 'zsort', 'Legacy Z sort', ['-zs'], 'Legacy / unavailable', 'Parsed flag has no effective renderer reader'),
    (1061, 'legacy_fps', 'Legacy frame-rate print', ['-f'], 'Legacy / unavailable', 'DESIGNER_CHEATS; parsed flag has no effective reader'),
    (1062, 'help', 'Help and exit', ['-h', '-help', '--help'], 'Launch and diagnostics', 'SW_DBSTREAM; launch operation exits'),
]
LEGACY = ['-l N', '-nologo', '-sound', '-cd', '-record_tga', '-paranoid']


def inventory():
    fields = [dict(id=i, key='runtime_'+key, label=label, cli=cli, value_type=kind,
                   policy=policy, group='Timing and profiling', accessor=accessor, adapter=adapter,
                   reason='') for i,key,label,cli,kind,policy,accessor,adapter in OPTIONS]
    fields += [dict(id=i, key='runtime_'+key, label=label, cli=cli, value_type='diagnostic',
                    policy='Ghost', group=group, accessor=key, adapter=None, reason=reason)
               for i,key,label,cli,group,reason in GHOSTS]
    fields += [dict(id=1080+i, key='runtime_legacy_'+str(i), label=cli, cli=[cli],
                    value_type='diagnostic', policy='Ghost', group='Legacy / unavailable',
                    accessor=None, adapter=None, reason='Documented legacy option; no active parser branch')
               for i,cli in enumerate(LEGACY)]
    # Standard includes are not an X-macro in the current engine. Include the
    # parser's actual user channel too; older help omitted it.
    streams = [('p', name, initial, help) for name,initial,help in
               [('cwarn','w','warnings'),('cerror','e','errors'),('cfatal','f','fatal'),
                ('cstats','s','statistics'),('cprogress','p','progress'),('cdebug','d','debugging'),('cuser','u','user')]]
    for family,path in [('s','wfsource/source/game/gamestrm.inc'),('l','wfsource/source/libstrm.inc')]:
        streams += [(family,*m) for m in re.findall(r'(?:EXTERN)?STREAMENTRY\(\s*(\w+)\s*,[^,]*,\s*\'(.)\'\s*,\s*"([^"]*)"', (ROOT/path).read_text())]
    for index,(family,name,initial,help) in enumerate(streams):
        fields.append(dict(id=1100+index, key='runtime_stream_'+family+'_'+initial,
                           label=family+initial+' '+help, cli=['-'+family+initial+'<output>'],
                           value_type='stream', policy='Conditional live', group='Debug streams',
                           accessor=name, adapter='stream', reason='SW_DBSTREAM; targets n, s, e, f<path>; monochrome unavailable',
                           family=family, channel=initial))
    assert len({f['id'] for f in fields}) == len(fields)
    assert all(1000 <= f['id'] < 1200 for f in fields)
    return fields


def sheet(fields):
    lines = ['PROPERTY_SHEET_HEADER(Runtime Options,0)']
    bindings = {}
    group = None
    for f in fields:
        if f['group'] != group:
            if group is not None: lines.append('GROUP_STOP()')
            group=f['group'];lines.append('GROUP_START('+group+')')
        kind=f['value_type']; numeric=kind in ('bool','int')
        lo,hi,default=(1,1000,20) if kind=='int' else (0,1,1 if f['id']==1000 else 0)
        help=' / '.join(f['cli'])+'. '+(f['reason'] or f['policy']+'; apply through runtime consumer')
        quote=lambda s: json.dumps(s,ensure_ascii=True)
        # Diagnostic rows use bounded text so absent capabilities can explicitly
        # display unavailable instead of a fictitious numeric value.
        lines.append('{'+','.join([str(4 if numeric else 5),quote(f['key']),str(lo if numeric else 0),str(hi if numeric else 255),str(default if numeric else 0),str(0 if numeric else 256),'""',str(8 if kind=='bool' else 2 if numeric else 0),'-1','-1',quote(help),'{0,0,'+quote(f['label'])+',"1"}'])+'},')
        bindings[f['key']]=dict(id=f['id'],readonly=True,initial=str(default) if numeric else 'unavailable',**({} if numeric else dict(max_length=255)))
    if group is not None:lines.append('GROUP_STOP()')
    lines.append('PROPERTY_SHEET_FOOTER')
    return lines,bindings


def write_manifest(here):
    fields=inventory()
    (here/'runtime-options.json').write_text(json.dumps(dict(version=1, id_range=[1000,1199],
        runtime_input='RPRP', fields=fields, exclusions={f'--plant-{key}=':'Plant CLI removal planned; retain value through authored plant settings, never a baseline CLI row' for key in ['seed','age','speed','texture','sway','water']}, status='Consumer snapshots effective values and activates supported fields at open'),indent=2)+'\n')
    return fields
