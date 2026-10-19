#!/usr/bin/env python3
"""Generate mm_practice.lev — hand-crafted from snowgoons.lev as template."""

import sys

out = []


def emit(line=""):
    out.append(line)


# ── helpers ───────────────────────────────────────────────────────────────────

def fx(v):
    return f"{v:.16f}(1.15.16)"


def vec3(name, x, y, z):
    emit(f"\t\t{{ 'VEC3' ")
    emit(f"\t\t\t{{ 'NAME' \"{name}\" ")
    emit(f"\t\t\t}}")
    emit(f"\t\t\t{{ 'DATA' {fx(x)} {fx(y)} {fx(z)}  //x,y,z")
    emit(f"\t\t\t\t\t")
    emit(f"\t\t\t}}")
    emit(f"\t\t}}")


def eulr(name, a, b, c):
    emit(f"\t\t{{ 'EULR' ")
    emit(f"\t\t\t{{ 'NAME' \"{name}\" ")
    emit(f"\t\t\t}}")
    emit(f"\t\t\t{{ 'DATA' {fx(a)} {fx(b)} {fx(c)}  //a,b,c")
    emit(f"\t\t\t\t\t")
    emit(f"\t\t\t}}")
    emit(f"\t\t}}")


def box3(name, x0, y0, z0, x1, y1, z1):
    emit(f"\t\t{{ 'BOX3' ")
    emit(f"\t\t\t{{ 'NAME' \"{name}\" ")
    emit(f"\t\t\t}}")
    emit(f"\t\t\t{{ 'DATA' {fx(x0)} {fx(y0)} {fx(z0)} {fx(x1)} {fx(y1)} {fx(z1)}  //min(x,y,z)-max(x,y,z)")
    emit(f"\t\t\t\t\t")
    emit(f"\t\t\t}}")
    emit(f"\t\t}}")


def strfield(name, value):
    emit(f"\t\t{{ 'STR' ")
    emit(f"\t\t\t{{ 'NAME' \"{name}\" ")
    emit(f"\t\t\t}}")
    emit(f"\t\t\t{{ 'DATA' \"{value}\" ")
    emit(f"\t\t\t}}")
    emit(f"\t\t}}")


def classname(cn):
    strfield("Class Name", cn)


def filefield(name, value):
    emit(f"\t\t{{ 'FILE' ")
    emit(f"\t\t\t{{ 'NAME' \"{name}\" ")
    emit(f"\t\t\t}}")
    emit(f"\t\t\t{{ 'STR' \"{value}\" ")
    emit(f"\t\t\t}}")
    emit(f"\t\t}}")


def strref(name, value):
    emit(f"\t\t{{ 'STR' ")
    emit(f"\t\t\t{{ 'NAME' \"{name}\" ")
    emit(f"\t\t\t}}")
    emit(f"\t\t\t{{ 'STR' \"{value}\" ")
    emit(f"\t\t\t}}")
    emit(f"\t\t}}")


def i32(name, data, label, comment=""):
    emit(f"\t\t{{ 'I32' ")
    emit(f"\t\t\t{{ 'NAME' \"{name}\" ")
    emit(f"\t\t\t}}")
    if comment:
        emit(f"\t\t\t{{ 'DATA' {data}l  //{comment}")
    else:
        emit(f"\t\t\t{{ 'DATA' {data}l  //")
    emit(f"\t\t\t\t\t")
    emit(f"\t\t\t}}")
    emit(f"\t\t\t{{ 'STR' \"{label}\" ")
    emit(f"\t\t\t}}")
    emit(f"\t\t}}")


def i32enum(name, label):
    emit(f"\t\t{{ 'I32' ")
    emit(f"\t\t\t{{ 'NAME' \"{name}\" ")
    emit(f"\t\t\t}}")
    emit(f"\t\t\t{{ 'STR' \"{label}\" ")
    emit(f"\t\t\t}}")
    emit(f"\t\t}}")


def fx32(name, value, label=None):
    if label is None:
        label = str(value)
    emit(f"\t\t{{ 'FX32' ")
    emit(f"\t\t\t{{ 'NAME' \"{name}\" ")
    emit(f"\t\t\t}}")
    emit(f"\t\t\t{{ 'DATA' {fx(value)} ")
    emit(f"\t\t\t}}")
    emit(f"\t\t\t{{ 'STR' \"{label}\" ")
    emit(f"\t\t\t}}")
    emit(f"\t\t}}")


# ── base actor fields (shared by almost all classes) ─────────────────────────

def base_actor(mobility="Anchored", moves_between_rooms=0, movement_mailbox=1,
               step_size=0.55, vert_elast=0.5, horiz_elast=0.5,
               mass=75.0, surface_friction=0.95,
               running_accel=1.0, running_decel=0.9,
               max_ground_speed=10.0, turn_rate=5.0,
               crawling_accel=0.5, jumping_accel=18.0,
               jumping_momentum=0.5, air_accel=1.0,
               horiz_air_drag=0.25, vert_air_drag=0.25,
               max_air_speed=10.0, falling_accel=9.81,
               fall_anim_threshold=2.0,
               stun_threshold=2.5, stun_duration=1.0):
    i32enum("Mobility", mobility)
    i32("Moves Between Rooms", moves_between_rooms, str(moves_between_rooms), "False|True")
    i32("Movement Mailbox", movement_mailbox, str(movement_mailbox))
    fx32("Step Size", step_size, str(step_size))
    fx32("Vertical Elasticity", vert_elast, str(vert_elast))
    fx32("Horizontal Elasticity", horiz_elast, str(horiz_elast))
    i32enum("At End Of Path", "Ping-Pong")
    strref("Object To Follow", "")
    strref("Follow Offset", "")
    fx32("Running Acceleration", running_accel, str(running_accel))
    fx32("Running Deceleration", running_decel, str(running_decel))
    fx32("Max Ground Speed", max_ground_speed, str(max_ground_speed))
    fx32("Turn Rate", turn_rate, str(turn_rate))
    fx32("Crawling Acceleration", crawling_accel, str(crawling_accel))
    fx32("Jumping Acceleration", jumping_accel, str(jumping_accel))
    fx32("Jumping Momentum Transfer", jumping_momentum, str(jumping_momentum))
    fx32("Air Acceleration", air_accel, str(air_accel))
    fx32("Horiz Air Drag", horiz_air_drag, str(horiz_air_drag))
    fx32("Vert Air Drag", vert_air_drag, str(vert_air_drag))
    fx32("Max Air Speed", max_air_speed, str(max_air_speed))
    fx32("Falling Acceleration", falling_accel, str(falling_accel))
    fx32("Fall Anim Threshold", fall_anim_threshold, str(fall_anim_threshold))
    fx32("Stun Threshold", stun_threshold, str(stun_threshold))
    fx32("Stun Duration", stun_duration, str(stun_duration))
    for t in ["A", "B", "C", "D", "E", "F"]:
        strref(f"Tool {t}", "")
    fx32("Mass", mass, str(mass))
    fx32("Surface Friction", surface_friction, str(surface_friction))


def tail_fields(mesh_name="", model_type="None",
                anim_mailbox=1, vis_mailbox=1,
                check_below=1, template_obj=0,
                num_local_mailboxes=0):
    fx32("hp", 32767.0, "32767.0")  # must be > 0 or engine treats actor as dead
    i32("Number Of Local Mailboxes", num_local_mailboxes, str(num_local_mailboxes))
    strref("Poof", "")
    i32("Is Needle Gun Target", 0, "0", "False|True")
    i32("Write To Mailbox On Death", 0, "0")


def mesh_and_tail(mesh_name="", model_type="None",
                  anim_mailbox=1, vis_mailbox=1,
                  check_below=1, script_controls_input=0):
    i32("Script Controls Input", script_controls_input, str(script_controls_input), "False|True")
    filefield("Mesh Name", mesh_name)
    i32enum("Model Type", model_type)
    i32("Animation Mailbox", anim_mailbox, str(anim_mailbox))
    i32("Visibility Mailbox", vis_mailbox, str(vis_mailbox))
    strref("Shadow Object Template", "")
    i32("Check Below Only Once", check_below, str(check_below), "False|True")
    i32("Template Object", 0, "0", "False|True")


# ── object emitters ───────────────────────────────────────────────────────────

def begin_obj(name):
    emit(f"\t{{ 'OBJ' ")
    emit(f"\t\t{{ 'NAME' \"{name}\" ")
    emit(f"\t\t}}")


def end_obj():
    emit(f"\t}}")


# 1. Ramp — statplat, Mesh=ramp.iff
def emit_ramp():
    begin_obj("Ramp")
    vec3("Position", 0.0, 10.0, 2.0)
    eulr("Orientation", 0.0, 0.0, 0.0)
    box3("Global Bounding Box", -5.0, -10.0, -2.0, 5.0, 10.0, 2.0)
    classname("statplat")
    base_actor(mobility="Anchored", mass=0.0, surface_friction=0.5)
    tail_fields()
    mesh_and_tail(mesh_name="ramp.iff", model_type="Mesh")
    end_obj()


# 2. Actboxor01 — activates CamShot01 when player enters
def emit_actboxor():
    begin_obj("Actboxor01")
    vec3("Position", 0.0, 10.0, 3.0)
    eulr("Orientation", 0.0, 0.0, 0.0)
    box3("Global Bounding Box", -10.0, -12.0, -6.0, 10.0, 12.0, 4.0)
    classname("actboxor")
    base_actor(mobility="Anchored", mass=75.0, surface_friction=0.95)
    tail_fields()
    mesh_and_tail(mesh_name="", model_type="None", vis_mailbox=0)
    # actboxor-specific fields
    i32("MailBox", 100, "100")
    strref("Object", "CamShot01")
    i32("Activated By", 0, "All", "All|Actor|Class|List")
    strref("Activated By Actor", "Player")
    strref("Activated By Class", "")
    end_obj()


# 3. Room01 — the single room
def emit_room():
    begin_obj("Room01")
    vec3("Position", 0.0, 10.0, 3.0)
    eulr("Orientation", 0.0, 0.0, 0.0)
    box3("Global Bounding Box", -12.0, -14.0, -6.0, 12.0, 14.0, 5.0)
    classname("room")
    fx32("hp", 32767.0, "32767.0")
    i32("Number Of Local Mailboxes", 0, "0")
    strref("Poof", "")
    i32("Is Needle Gun Target", 0, "0", "False|True")
    i32("Write To Mailbox On Death", 0, "0")
    i32("Script Controls Input", 0, "0", "False|True")
    strref("Adjacent Room 1", "")
    strref("Adjacent Room 2", "")
    i32("Room Loaded Mailbox", 0, "0")
    end_obj()


# 4. Omni01 — ambient light (no BOX3)
def emit_light():
    begin_obj("Omni01")
    vec3("Position", 0.0, 10.0, 20.0)
    eulr("Orientation", 1.5707963, 0.0, 0.0)
    classname("light")
    base_actor(mobility="Anchored", mass=75.0, surface_friction=0.95)
    tail_fields()
    mesh_and_tail(mesh_name="", model_type="None", vis_mailbox=0)
    fx32("lightRed", 1.0, "1.000000")
    fx32("lightGreen", 1.0, "1.000000")
    fx32("lightBlue", 1.0, "1.000000")
    i32("lightType", 0, "Ambient", "Directional|Ambient")
    end_obj()


# 5. Camera
def emit_camera():
    begin_obj("Camera")
    vec3("Position", 20.0, -10.0, 15.0)
    eulr("Orientation", 0.0, 0.0, 0.0)
    box3("Global Bounding Box", -0.5, -0.5, 0.0, 0.5, 0.5, 1.0)
    classname("camera")
    base_actor(mobility="Camera", moves_between_rooms=1, mass=75.0, surface_friction=0.9499970)
    tail_fields()
    mesh_and_tail(mesh_name="", model_type="Box", vis_mailbox=1)
    i32("FoggingColor", 8947848, "8947848")
    fx32("FoggingStartDistance", 500.0, "500.0")
    fx32("FoggingCompleteDistance", 1000.0, "1000.0")
    end_obj()


# 6. Director
# Script strings in .lev must be single-line with \\=backslash \n=newline escapes
DIRECTOR_SCRIPT_LIT = (
    r"\\ wf"
    r"\n100 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then"
    r"\n 99 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then"
    r"\n 98 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then"
    "                                                                                                                                                                                                                                    "
    r"\n"
)


def emit_director():
    begin_obj("Director")
    vec3("Position", 0.0, 10.0, 5.0)
    eulr("Orientation", 0.0, 0.0, 0.0)
    box3("Global Bounding Box", -0.5, -0.5, 0.0, 0.5, 0.5, 1.0)
    classname("director")
    base_actor(mobility="Anchored", mass=75.0, surface_friction=0.95)
    tail_fields()
    emit(f"\t\t{{ 'STR' ")
    emit(f"\t\t\t{{ 'NAME' \"Script\" ")
    emit(f"\t\t\t}}")
    emit(f'\t\t\t{{ \'STR\' "{DIRECTOR_SCRIPT_LIT}"')
    emit(f"\t\t\t}}")
    emit(f"\t\t}}")
    mesh_and_tail(mesh_name="", model_type="None", vis_mailbox=1)
    end_obj()


# 7. Level (levelobj)
def emit_levelobj():
    begin_obj("Level")
    vec3("Position", 0.0, 10.0, 5.0)
    eulr("Orientation", 0.0, 0.0, 0.0)
    box3("Global Bounding Box", -0.5, -0.5, 0.0, 0.5, 0.5, 1.0)
    classname("levelobj")
    base_actor(mobility="Anchored", mass=75.0, surface_friction=0.9499970)
    tail_fields()
    mesh_and_tail(mesh_name="", model_type="Box", vis_mailbox=1)
    i32("Number Of Mailboxes", 101, "101")
    i32("Number Of Scratch Mailboxes", 10, "10")
    i32("Number Of Temporary Objects", 200, "200")
    fx32("Sound Yon", 20.0, "20.0")
    filefield("MusicVh", "")
    filefield("MusicVb", "")
    filefield("MusicSeq", "")
    end_obj()


# 8. Matte
def emit_matte():
    begin_obj("Matte")
    vec3("Position", 0.0, 10.0, 5.0)
    eulr("Orientation", 0.0, 0.0, 0.0)
    box3("Global Bounding Box", -0.5, -0.5, 0.0, 0.5, 0.5, 1.0)
    classname("matte")
    base_actor(mobility="Anchored", mass=75.0, surface_friction=0.9499970)
    tail_fields()
    mesh_and_tail(mesh_name="", model_type="Box", vis_mailbox=1)
    i32("Matte Type", 0, "Color", "None|Color|Image")
    i32("Background Color", 12176, "12176")
    i32("Debug Background Color", 0, "0")
    fx32("X Rotation Scale", 1.0, "1")
    fx32("Y Rotation Scale", 1.0, "1")
    end_obj()


# 9. CamShot01
def emit_camshot():
    begin_obj("CamShot01")
    vec3("Position", 20.0, -10.0, 15.0)
    eulr("Orientation", 0.0, 0.0, 0.0)
    box3("Global Bounding Box", -0.5, -0.5, 0.0, 0.5, 0.5, 1.0)
    classname("camshot")
    base_actor(mobility="Anchored", mass=75.0, surface_friction=0.9499970)
    tail_fields()
    mesh_and_tail(mesh_name="", model_type="Box", vis_mailbox=1)
    strref("Target", "Target02")
    strref("Follow", "Target01")
    fx32("Climb Rate", 5.0, "5")
    fx32("Elasticity", 10.0, "10")
    i32("Track Object Mailbox", 0, "0")
    strref("Track Object", "Player")
    i32("Rotation", 0, "Track", "Fixed|Track")
    i32("Position X", 0, "Relative", "Absolute|Relative")
    i32("Position Y", 0, "Relative", "Absolute|Relative")
    i32("Position Z", 0, "Relative", "Absolute|Relative")
    fx32("FOV", 50.0, "50")
    fx32("Roll", 0.0, "0")
    fx32("Pan Time In Seconds", 1.0, "1")
    fx32("Hither", 0.1, "0.1")
    fx32("Yon", 1000.0, "1000")
    end_obj()


# 10. Target01 — camera-follows reference (near player spawn)
def emit_target(name, x, y, z):
    begin_obj(name)
    vec3("Position", x, y, z)
    eulr("Orientation", 0.0, 0.0, 0.0)
    box3("Global Bounding Box", -0.5, -0.5, 0.0, 0.5, 0.5, 1.0)
    classname("target")
    base_actor(mobility="Anchored", mass=75.0, surface_friction=0.9499970)
    tail_fields()
    mesh_and_tail(mesh_name="", model_type="Box", vis_mailbox=1)
    end_obj()


# 12. Player — the marble
PLAYER_SCRIPT_LIT = r"\n\\ wf\nINDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox\n"


def emit_player():
    begin_obj("Player")
    vec3("Position", 0.0, 0.0, 5.0)
    eulr("Orientation", 0.0, 0.0, 0.0)
    box3("Global Bounding Box",
         -0.33, -0.33, 0.0,
          0.33,  0.33, 0.66)
    classname("player")
    base_actor(
        mobility="Physics",
        moves_between_rooms=1,
        step_size=0.25,
        vert_elast=0.3,
        horiz_elast=0.7,
        mass=75.0,
        surface_friction=0.9499970,
        running_accel=15.0,
        running_decel=0.9,
        max_ground_speed=15.0,
        turn_rate=0.25,
        crawling_accel=0.5,
        jumping_accel=40.0,
        jumping_momentum=0.5,
        air_accel=10.0,
        horiz_air_drag=0.0,
        vert_air_drag=0.0,
        max_air_speed=12.0,
        falling_accel=9.8,
    )
    fx32("hp", 32767.0, "32767")
    i32("Number Of Local Mailboxes", 6, "6")
    strref("Poof", "")
    i32("Is Needle Gun Target", 0, "0", "False|True")
    i32("Write To Mailbox On Death", 0, "0")
    emit(f"\t\t{{ 'STR' ")
    emit(f"\t\t\t{{ 'NAME' \"Script\" ")
    emit(f"\t\t\t}}")
    emit(f'\t\t\t{{ \'STR\' "{PLAYER_SCRIPT_LIT}"')
    emit(f"\t\t\t}}")
    emit(f"\t\t}}")
    i32("Script Controls Input", 1, "1", "False|True")
    filefield("Mesh Name", "player.iff")
    i32enum("Model Type", "Mesh")
    i32("Animation Mailbox", 1, "1")
    i32("Visibility Mailbox", 2002, "2002")
    strref("Shadow Object Template", "")
    i32("Check Below Only Once", 1, "1", "False|True")
    i32("Template Object", 0, "0", "False|True")
    end_obj()


# ── Assemble the level ────────────────────────────────────────────────────────

emit()
emit("{ 'LVL' ")
emit_ramp()
emit_actboxor()
emit_room()
emit_light()
emit_camera()
emit_director()
emit_levelobj()
emit_matte()
emit_camshot()
emit_target("Target01", 5.0, 0.0, 4.5)
emit_target("Target02", 0.0, 10.0, 2.0)
emit_player()
emit("}")
emit()

dest = sys.argv[1] if len(sys.argv) > 1 else "mm_practice.lev"
with open(dest, "w") as f:
    f.write("\n".join(out))
print(f"Wrote {dest}")
