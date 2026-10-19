-- qbert_capture_v2.lua: capture state 0/1/2 cube colors per round.
--
-- Strategy: toggle DIP cheat dynamically.
--   • Cheat ON  → round advances via Start press; Demo AI moves Q*bert
--   • Cheat OFF → Demo AI suspended; we control Q*bert cleanly
--
-- Per-round flow:
--   1. Wait for ram_0x081 change (cheat fired → round advanced)
--   2. DISABLE cheat (suspend Demo AI)
--   3. Snap state-0 (Q*bert just respawned at apex, all cubes fresh)
--   4. Hop DR (visit (1,1) once) → snap hop1 (state 1 of (1,1))
--   5. Hop UL → DR (visit (1,1) twice) → snap hop2 (state 2 of (1,1))
--   6. Hop UL back to apex
--   7. ENABLE cheat
--   8. Press Start to advance to next round (cheat fires when Q*bert at apex)
--
-- Unlim lives via mem:write_u8(0x0D00, 9) every frame (still active without cheat).

local BASE = "/home/will/WorldFoundry.2026-new-level"
local LOG = BASE .. "/scripts/research/mame/capture_v2.txt"
local f = io.open(LOG, "w")
local function log(s) io.write(s); io.flush(); if f then f:write(s); f:flush() end end

local DIRS = {
    DR = "P1 Right (Down-Right)", DL = "P1 Down (Down-Left)",
    UR = "P1 Up (Up-Right)",      UL = "P1 Left (Up-Left)",
}

local frame, fields, mem = 0, {}, nil
local STATE = "BOOT"
local last_ram = 0
local round_num = 0
local MAX_ROUNDS = 22

local hop_dir = nil
local hop_start = 0
local last_hop = 0
local HOP_HOLD = 12
local HOP_COOLDOWN = 30

local CHEAT_FIELD = "Demo Mode (Unlim Lives, Start=Adv (Cheat)"
local LIVES = 0x0D00
local POS   = 0x0081

local function set(name, on) if fields[name] then fields[name]:set_value(on and 1 or 0) end end
local function set_cheat(on)
    if fields[CHEAT_FIELD] then fields[CHEAT_FIELD]:set_value(on and 1 or 0) end
end

local function snap(label)
    manager.machine.video:snapshot()
    local rr = mem and mem:read_u8(POS) or 0
    log(string.format("[snap %s] round=%d frame=%d 0x81=0x%02X\n",
        label, round_num, frame, rr))
end

local function start_hop(dir)
    hop_dir = dir
    hop_start = frame
    last_hop = frame
    set(DIRS[dir], true)
end

emu.register_frame_done(function()
    frame = frame + 1

    if frame == 1 then
        for _, port in pairs(manager.machine.ioport.ports) do
            for name, fld in pairs(port.fields) do fields[name] = fld end
        end
        local cpu = manager.machine.devices[":maincpu"]
        mem = cpu and cpu.spaces["program"]
        set_cheat(true)  -- start with cheat ON
        log("[INFO] cheat enabled at boot\n")
    end

    -- Boot inputs
    set("Coin 1", frame >= 500 and frame < 540)
    set("1 Player Start", frame >= 700 and frame < 740)

    -- Unlim lives (works whether cheat is on or off)
    if mem and frame > 750 then mem:write_u8(LIVES, 9) end

    -- Release joystick after HOP_HOLD frames
    if hop_dir and frame - hop_start >= HOP_HOLD then
        set(DIRS[hop_dir], false)
        hop_dir = nil
    end

    if STATE == "BOOT" then
        if frame >= 1100 then
            STATE = "WAIT_RAM"
            last_ram = mem and mem:read_u8(POS) or 0
            log(string.format("[init] frame=%d ram=0x%02X\n", frame, last_ram))
        end
        return
    end

    local cur_ram = mem and mem:read_u8(POS) or 0

    -- Detect cheat fire (round advance)
    if STATE == "WAIT_RAM" then
        if cur_ram ~= last_ram and cur_ram >= 0x04 then
            round_num = round_num + 1
            log(string.format("[round %d] ram=0x%02X (was 0x%02X) frame=%d\n",
                round_num, cur_ram, last_ram, frame))
            last_ram = cur_ram
            -- DISABLE cheat to suspend Demo AI
            set_cheat(false)
            STATE = "WAIT_SETTLE"
            last_hop = frame + 30  -- give Demo AI time to fully suspend + Q*bert settle
            return
        end
        return
    end

    -- Wait for cooldown before any state action
    if hop_dir or frame < last_hop + HOP_COOLDOWN then return end

    if STATE == "WAIT_SETTLE" then
        snap("s0")
        STATE = "DO_HOP1"
        return
    end

    if STATE == "DO_HOP1" then
        start_hop("DR")
        STATE = "SNAP_HOP1"
        return
    end

    if STATE == "SNAP_HOP1" then
        snap("hop1")
        STATE = "DO_BACK1"
        return
    end

    if STATE == "DO_BACK1" then
        start_hop("UL")
        STATE = "DO_HOP2"
        return
    end

    if STATE == "DO_HOP2" then
        start_hop("DR")
        STATE = "SNAP_HOP2"
        return
    end

    if STATE == "SNAP_HOP2" then
        snap("hop2")
        STATE = "DO_BACK2"
        return
    end

    if STATE == "DO_BACK2" then
        start_hop("UL")
        STATE = "RE_ENABLE_CHEAT"
        return
    end

    if STATE == "RE_ENABLE_CHEAT" then
        set_cheat(true)  -- re-enable so Demo AI resumes and completes the round
        STATE = "WAIT_RAM"
        last_hop = frame + 20
        if round_num >= MAX_ROUNDS then
            log("[done]\n")
            if f then f:close() end
            manager.machine:exit()
        end
        return
    end
end)
