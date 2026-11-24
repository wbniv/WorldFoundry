"""Exercise Corolla's settings in a two-entry PC test bundle.

Run under Xvfb with libXtst available, WF_COROLLA_ENGINE naming the engine,
and build-docker/corolla-ui-test/cd.iff holding two copies of the standalone.
The second entry enables the PC menu's Backspace-to-apply route.
"""
import ctypes,json,os,subprocess,sys,time
from pathlib import Path
root=Path('/src');sys.path.insert(0,str(root/'tests'))
from debug_bridge_client import BridgeClient
out=root/'build-docker/corolla-gauge-captures/settings';out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,WF_WALL_CLOCK='10:45:00@0',WF_REST_PORT='0')
with (out/'engine.log').open('w') as log:
    engine=os.environ.get('WF_COROLLA_ENGINE',str(root/'build-docker/tourbillon/src/engine/wf_game'))
    p=subprocess.Popen([engine,'--menu-input=wait:20,a',
        '--debug-port','17795','--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps',
        '--vram-width=2048','--vram-height=2048','--vram-slot-width=2048','--vram-slot-height=1024'],
        cwd=root/'build-docker/corolla-ui-test',env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17795,timeout=60)
        def press(bits,seconds=.2):
            c.inject_input('joystick1_raw',bits,duration_frames=-1);time.sleep(seconds)
            c.inject_input('joystick1_raw',0,duration_frames=-1);time.sleep(.3)
        def shot(name):
            c.send({'op':'screenshot','filename':str(out/name)})
            assert c.wait_for(lambda m:m.get('op')=='screenshot_done',timeout=30)
        x11=ctypes.CDLL('libX11.so.6');xtst=ctypes.CDLL('libXtst.so.6')
        x11.XOpenDisplay.restype=ctypes.c_void_p;x11.XOpenDisplay.argtypes=[ctypes.c_char_p]
        x11.XKeysymToKeycode.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
        x11.XFlush.argtypes=[ctypes.c_void_p]
        xtst.XTestFakeKeyEvent.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_int,ctypes.c_ulong]
        display=x11.XOpenDisplay(None);assert display
        key=x11.XKeysymToKeycode(display,0xff08) # Backspace applies the settings form.
        def apply():
            xtst.XTestFakeKeyEvent(display,key,1,0);xtst.XTestFakeKeyEvent(display,key,0,0);x11.XFlush(display);time.sleep(1)
        time.sleep(4)
        for i in range(6):
            press(1,1.6);time.sleep(.4)
            press(1<<14);press(1<<12);press(1<<13) # Camera -> section rail -> Tulip.
            if i:press(1<<13) # advance from the preceding selection
            shot(f'palette-ui-{i}.png');apply();shot(f'palette-applied-{i}.png')
            if i:
                log.flush();assert f'COROLLA_PALETTE selection={i}' in (out/'engine.log').read_text(),i
        # Return from the last palette through Scarlet to the section rail,
        # enter Display, then apply Scarlet again.
        press(1,1.6);press(1<<14);press(1<<12);press(1<<13)
        for _ in range(6):press(1<<14)
        press(1<<12);press(1<<13);shot('display-after-palette.png');apply()
        log.flush();assert 'COROLLA_PALETTE selection=0' in (out/'engine.log').read_text()
        print('PASS all six palettes through controller settings',flush=True);c.close()
    finally:
        if p.poll() is None:p.terminate()
        p.wait(timeout=30)
