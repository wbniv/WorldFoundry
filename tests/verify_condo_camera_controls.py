#!/usr/bin/env python3
"""Exercise Forth camera policy in the unmodified engine via debug bridge."""
import re
import time
from pathlib import Path
import verify_condo_unit_teleport as h
h.WORK=Path('/tmp/condo-camera-controls')
h.SHOTS=h.REPO/'docs/plans/2026-09-25-condo-camera-controls'
h.PORT=7798
A,B,C,D,E,F=1,2,4,8,16,32
UP,DOWN,RIGHT,LEFT=2048,4096,8192,16384

def actor(name):
    chunks=(h.REPO/'wflevels/condo_639_640/condo_639_640.lev').read_text().split("'OBJ'")[1:]
    for i,c in enumerate(chunks):
        if re.search(r"'NAME'\s*\""+re.escape(name)+r'"',c):return i+1
    raise AssertionError(name)

def hold(cli,bits,secs=.35):
    cli.inject_input('joystick1_raw',bits,duration_frames=-1);time.sleep(secs)
    cli.inject_input('joystick1_raw',0,duration_frames=-1);time.sleep(.12)

def run():
    with h.game('camera') as (cli,player):
        shot=actor('cs_dollhouse');camera=actor('Camera')
        for idx,mbs in ((1,range(110,138)),(shot,h.POS),(camera,h.POS),(1,[1921])):
            for mb in mbs:cli.watch(idx,mb)
        assert h.wait(lambda:h.value(cli,1,110)==1),'camera init failed'
        assert h.wait(lambda:h.value(cli,shot,3009) is not None),'shot watch failed'
        read=lambda mb:h.value(cli,1,mb)
        pos=lambda:h.values(cli,player,h.POS)
        shotpos=lambda:h.values(cli,shot,h.POS)
        default=shotpos();start=pos();az=read(114)
        hold(cli,D|RIGHT,.5)
        h.check('orbit changes shot',read(113)==1 and read(114)!=az and not h.near(shotpos(),default,.1),str(shotpos()))
        h.check('inspect leaves player stationary',h.near(pos()[:2],start[:2],.04))
        time.sleep(.5)
        expected=tuple(pos()[i]+read(130+i) for i in range(3))
        h.check('render camera follows shot',h.wait(lambda:h.near(h.values(cli,camera,h.POS),expected,.15),timeout=5),str(h.values(cli,camera,h.POS)))
        h.screenshot(cli,'runtime-orbit.png')
        az=read(114);hold(cli,D|LEFT,.25);h.check('reverse orbit',read(114)<az)
        el=read(115);hold(cli,D|DOWN,.4);h.check('tilt down',read(115)<el)
        el=read(115);hold(cli,D|UP,.2);h.check('tilt up',read(115)>el)
        r=read(116);hold(cli,E,.4);h.check('zoom closer',read(116)<r)
        r=read(116);hold(cli,F,.4);h.check('zoom farther',read(116)>r)
        door=h.value(cli,1,93);r=read(116);hold(cli,D|B|UP,.2)
        h.check('controller zoom fallback',read(116)<r and h.value(cli,1,93)==door)
        before=(read(114),read(115),read(116));hold(cli,D|LEFT|RIGHT|UP|DOWN|E|F,.25)
        h.check('opposing controls cancel',h.near((read(114),read(115),read(116)),before,.001))
        cli.set_mailbox(114,.99,idx=1);hold(cli,D|RIGHT,.2)
        h.check('azimuth wraps',0<=read(114)<.1)
        cli.set_mailbox(115,.222,idx=1);hold(cli,D|UP,.2)
        h.check('upper tilt clamp',read(115)<=.22224)
        cli.set_mailbox(115,.098,idx=1);cli.set_mailbox(116,4,idx=1);hold(cli,D|DOWN|E,.3)
        h.check('coupled floor clearance',read(115)>=.0972 and read(132)>=4.09)
        cli.set_mailbox(116,12,idx=1);hold(cli,F,.2)
        h.check('upper distance clamp',read(116)<=12.001)
        h.screenshot(cli,'runtime-inspect.png')
        view=(read(114),read(115),read(116));h.switch(cli,640)
        h.check('teleport preserves manual view',read(113)==1 and h.near((read(114),read(115),read(116)),view,.001))
        h.place(cli,player,(-5.6,-8.4,16.05))
        hold(cli,D|A,.1);hold(cli,D|LEFT|DOWN,.65);hold(cli,E,.4)
        time.sleep(.5)
        h.screenshot(cli,'runtime-640.png')
        h.place(cli,player,(4.0,-.8,16.05));time.sleep(.3)
        h.check('manual camera overrides window zone',h.value(cli,1,1921)==shot)
        ground_z=pos()[2]
        hold(cli,D|A,.4)
        h.check('reset restores automatic view',read(113)==0 and h.value(cli,1,1921)!=shot)
        h.check('reset does not jump',abs(pos()[2]-ground_z)<.05)
        h.place(cli,player,(4.65,-14.5,16.05));hold(cli,D|A,.1)
        h.check('reset restores authored shot',h.near(shotpos(),default,.002))
        h.screenshot(cli,'runtime-reset.png')
        before=pos();hold(cli,UP,.4)
        h.check('walk restored after inspect',pos()[1]>before[1]+.1)
        hold(cli,D|RIGHT,7.0)
        h.check('sustained orbit remains bounded',0<=read(114)<1 and 4<=read(116)<=12)
        for yaw in (0,.25,.5,.75):
            cli.set_mailbox(114,yaw,idx=1);time.sleep(.15)
            dx,dy=read(130),read(131)
            h.check(f'cardinal orbit {yaw}',
                    abs(dx)<.01 if yaw in (0,.5) else abs(dy)<.01)
        h.check('camera stays within room height',h.value(cli,camera,3011)<27.9)
    with h.game('camera-reload') as (cli,player):
        for mb in (110,113,112):cli.watch(1,mb)
        assert h.wait(lambda:h.value(cli,1,110)==1)
        h.check('reload restores automatic walk',h.value(cli,1,113)==0 and h.value(cli,1,112)==0)
    print('RESULT:', 'PASS' if not h.failures else h.failures)
    return bool(h.failures)
if __name__=='__main__':raise SystemExit(run())
