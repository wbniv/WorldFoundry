#!/usr/bin/env python3
"""Two-button touch profile checked through the engine's existing input bridge."""
import os
import time
import verify_condo_camera_controls as c
h=c.h
h.PORT=7799
os.environ['CONDO_TEST_LEVEL']='condo_639_640_touch'
with h.game('touch') as (cli,player):
    for mb in (*range(110,138),140,141,142):cli.watch(1,mb)
    assert h.wait(lambda:h.value(cli,1,110)==1)
    read=lambda mb:h.value(cli,1,mb)
    h.check('touch starts in Walk',read(112)==0)
    grounded_z=h.value(cli,player,3011)
    c.hold(cli,c.A,.12)
    h.check('A tap selects Look and manual camera',read(112)==1 and read(113)==1)
    before=h.values(cli,player,h.POS);yaw=read(114)
    c.hold(cli,c.RIGHT,.4)
    h.check('Look directions orbit without walking',read(114)!=yaw and h.near(h.values(cli,player,h.POS),before,.05))
    h.check('Look mode visible',read(140)==0 and read(141)!=0 and read(142)==0)
    h.screenshot(cli,'runtime-touch-look.png')
    c.hold(cli,c.A,.12);r=read(116)
    c.hold(cli,c.UP,.3)
    h.check('Zoom mode moves closer',read(112)==2 and read(116)<r)
    r=read(116);c.hold(cli,c.DOWN,.3)
    h.check('Zoom mode moves farther',read(116)>r)
    r=read(116);p=h.values(cli,player,h.POS);c.hold(cli,c.LEFT,.2)
    h.check('Zoom ignores sideways input',abs(read(116)-r)<.001 and h.near(h.values(cli,player,h.POS),p,.05))
    h.screenshot(cli,'runtime-touch-zoom.png')
    mode=read(112);view=(read(114),read(115),read(116));door=h.value(cli,1,93)
    c.hold(cli,c.A|c.B,.8)
    h.check('held A+B teleports once',h.value(cli,1,81)==640)
    h.check('chord preserves mode and view',read(112)==mode and read(113)==1 and h.near((read(114),read(115),read(116)),view,.001))
    h.check('chord does not trigger door',h.value(cli,1,93)==door)
    # B-first chord and staggered releases cancel pending tap/hold actions.
    cli.inject_input('joystick1_raw',c.B,duration_frames=-1);time.sleep(.15)
    cli.inject_input('joystick1_raw',c.A|c.B,duration_frames=-1);time.sleep(.2)
    cli.inject_input('joystick1_raw',c.A,duration_frames=-1);time.sleep(.7)
    cli.inject_input('joystick1_raw',0,duration_frames=-1);time.sleep(.15)
    h.check('staggered chord restores 639 without mode/reset leak',h.value(cli,1,81)==639 and read(112)==mode and read(113)==1)
    c.hold(cli,c.B,.8)
    h.check('long B resets to automatic Walk',read(112)==0 and read(113)==0)
    h.check('long B does not operate door',h.value(cli,1,93)==door)
    p=h.values(cli,player,h.POS);c.hold(cli,c.UP,.4)
    h.check('Walk movement works',h.value(cli,player,3010)>p[1]+.1)
    h.check('A taps never jump',abs(h.value(cli,player,3011)-grounded_z)<.05)
    # Approach the existing wall-button zone, then tap B.
    h.place(cli,player,(7.3,-2.45,16.05))
    door=h.value(cli,1,93);c.hold(cli,c.B,.1)
    h.check('B tap operates nearby door',h.value(cli,1,93)!=door)
print('RESULT:', 'PASS' if not h.failures else h.failures)
raise SystemExit(bool(h.failures))
