import json
s=[]
def key(t,k,hold=0.12):
    s.append({"at":round(t,3),"key":k,"action":"down"}); s.append({"at":round(t+hold,3),"key":k,"action":"up"})
def cap(t,l): s.append({"at":t,"capture":l})
t=0.5
for i in range(16): key(t,"DPAD_UP"); t+=0.24       # chooser top
key(6,"DPAD_DOWN",0.2)                                # Tide Harbour (2nd)
key(8,"DPAD_CENTER",0.2)                              # launch
cap(18,"scene-start")
def open_to_mode(t0):
    key(t0,"DPAD_CENTER",1.8)                         # long press: settings form
    key(t0+3,"DPAD_LEFT",0.2); key(t0+4,"DPAD_DOWN",0.2); key(t0+5,"DPAD_RIGHT",0.2)   # Tide Harbour group, item 1
    for i in range(5): key(t0+7+i,"DPAD_DOWN",0.2)    # -> River krathongs (6/7)
    return t0+12
t=open_to_mode(21)
cap(t+0.5,"mode-before")                             # 33.5
key(t+3,"DPAD_RIGHT",0.2)                             # Every night (36)
key(t+4,"DPAD_DOWN",0.2)                              # Krathong count (37)
cap(t+5,"count-before")                              # 38
t=t+7                                                 # 40
for i in range(75): key(t,"DPAD_RIGHT",0.1); t+=0.22   # 30 -> 100 (clamped if higher), ends ~51
cap(round(t+1,2),"count-set")                        # 56
key(60,"BACK",0.2)                                    # apply / close: launches start ~59 s
for c in (90,185,300): cap(c,f"river-{c}s")
# restore Festival nights / 30 at 390 s (after the steady window)
t=open_to_mode(390)
key(t+1,"DPAD_LEFT",0.2)                              # Festival nights
key(t+2,"DPAD_DOWN",0.2)
t=t+3
for i in range(70): key(t,"DPAD_LEFT",0.1); t+=0.22    # 100 -> 30
cap(round(t+1,2),"restored")
key(round(t+3,2),"BACK",0.2)
print("end",t+3, "events",len(s))
req={"workflow":"profile","app":"clocks","apk":"4ab6bddd8404430d28e2bf29568b10453c92919587f1ae8ab4264275ecd1511b.apk","duration":440,"warmup":3,"runs":1,"panel":"require-hidden","input_script":sorted(s,key=lambda e:e["at"])}
json.dump(req,open("profile-request.json","w"),indent=1)
