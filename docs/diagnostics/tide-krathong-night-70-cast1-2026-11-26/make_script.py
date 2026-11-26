"""Coordinator profile request: Tide Harbour on cast1 at night, Every night + Krathong count 70, then restore
Festival nights / 30. Same navigation as tide-krathong-night-100-cast1-2026-11-26/make_script.py."""
import json, sys
s = []
def key(t, k, hold=0.12):
    s.append({"at": round(t, 2), "key": k, "action": "down"}); s.append({"at": round(t + hold, 2), "key": k, "action": "up"})
def cap(t, l): s.append({"at": round(t, 2), "capture": l})
t = 0.5
for i in range(16): key(t, "DPAD_UP"); t += 0.24     # chooser top
key(6, "DPAD_DOWN", 0.2)                              # Tide Harbour (2nd)
key(8, "DPAD_CENTER", 0.2)                            # launch
cap(18, "scene-start")
def open_to_mode(t0):
    key(t0, "DPAD_CENTER", 1.8)                       # long press: settings form
    key(t0 + 3, "DPAD_LEFT", 0.2); key(t0 + 4, "DPAD_DOWN", 0.2); key(t0 + 5, "DPAD_RIGHT", 0.2)
    for i in range(5): key(t0 + 7 + i, "DPAD_DOWN", 0.2)   # -> River krathongs (6/7)
    return t0 + 12
t = open_to_mode(21)
cap(t + 0.5, "mode-before")                           # 33.5
key(t + 3, "DPAD_RIGHT", 0.2)                         # Every night
key(t + 4, "DPAD_DOWN", 0.2)                          # Krathong count
cap(t + 5, "count-before")                            # 38
t = t + 7                                             # 40
for i in range(45): key(t, "DPAD_RIGHT", 0.1); t += 0.22   # 30 -> 70 (clamped)
cap(t + 1, "count-set")
APPLY = 53.5
key(APPLY, "BACK", 0.2)                               # launches start; 70 afloat by APPLY + 84 s
for c in (100, 140, 200, 260): cap(c, f"river-{c}s")
t = open_to_mode(275)
key(t + 1, "DPAD_LEFT", 0.2)                          # Festival nights
key(t + 2, "DPAD_DOWN", 0.2)
t = t + 3
for i in range(40): key(t, "DPAD_LEFT", 0.1); t += 0.22    # 70 -> 30
cap(t + 1, "restored")
key(t + 3, "BACK", 0.2)
end = t + 3
req = {"workflow": "profile", "app": "clocks", "apk": sys.argv[1], "duration": int(end + 12), "warmup": 3, "runs": 1,
       "panel": "require-hidden", "input_script": sorted(s, key=lambda e: e["at"])}
json.dump(req, open("profile-request.json", "w"), separators=(",", ":"))
print("end", round(end, 2), "duration", req["duration"], "events", len(s), "count-set at", [e["at"] for e in s if e.get("capture") == "count-set"])
