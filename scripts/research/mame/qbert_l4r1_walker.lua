-- qbert_l4r1_walker.lua: closes the L4R1 state-1 capture gap by combining:
--
--   1. DIP cheat ON for round-advance (proven mechanism in qbert_round_shots).
--   2. At L4R1 entry, detect apex via RAM 0x0D64 == 0xB8.
--   3. Run the walker's snap-dance: snap state-0, force DR hop, force UL hop
--      back to apex, snap state-1.
--
-- Demo AI in L4R1 takes ~hundreds of frames to start hopping (verified in
-- earlier burst captures). Our DR+UL injected hops happen in ~80 frames and
-- override Demo AI's slow ramp-up.

local BASE = "/home/will/WorldFoundry.2026-new-level"
local LOG = BASE .. "/scripts/research/mame/l4r1_walker.txt"
local f = io.open(LOG, "w")
local function log(s) io.write(s); io.flush(); if f then f:write(s); f:flush() end end

local DIRS = {
    DR = "P1 Right (Down-Right)",
    UL = "P1 Left (Up-Left)",
}
local CHEAT = "Demo Mode (Unlim Lives, Start=Adv (Cheat)"

-- Position byte from qbert_position_hunt
local POS_ADDR = 0x0D64
local APEX_VAL = 0xB8
local C11_VAL  = 0xF5  -- value at (1,1)
local LIVES = 0x0D00

local frame, fields, mem = 0, {}, nil
local STATE = "BOOT"
local round_num = 0
local last_round_ram = -1
local hop_dir, hop_start = nil, 0
local last_hop = 0
local snap_idx = 0
local pos_at_hop_start = 0
local apex_stable_count = 0
local TARGET_ROUND = 16  -- per qbert_round_shots file_map mapping

local function set(name, on) if fields[name] then fields[name]:set_value(on and 1 or 0) end end
local function snap(label)
    snap_idx = snap_idx + 1
    manager.machine.video:snapshot()
    local p = mem and mem:read_u8(POS_ADDR) or 0
    log(string.format("[snap %s] idx=%04d frame=%d pos=0x%02X\n", label, snap_idx-1, frame, p))
end
local function start_hop(dir)
    hop_dir = dir; hop_start = frame; last_hop = frame
    pos_at_hop_start = mem and mem:read_u8(POS_ADDR) or 0
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
        if fields[CHEAT] then fields[CHEAT]:set_value(1); log("[INFO] cheat ON\n") end
    end

    set("Coin 1", frame >= 500 and frame < 540)

    if mem and frame > 750 then mem:write_u8(LIVES, 9) end

    if hop_dir and frame - hop_start >= 12 then
        set(DIRS[hop_dir], false)
        hop_dir = nil
    end

    if STATE == "BOOT" then
        if frame >= 1100 then STATE = "WAIT_RAM"; log("[INFO] WAIT_RAM\n") end
        return
    end

    -- Use round counter at 0x0081 (per qbert_round_shots) for round-advance detection.
    -- Each round_num increment = ROM round transition fires.
    local cur_ram = mem and mem:read_u8(0x0081) or 0

    if STATE == "WAIT_RAM" then
        if cur_ram >= 0x04 and cur_ram ~= last_round_ram then
            round_num = round_num + 1
            last_round_ram = cur_ram
            log(string.format("[round %d] ram=0x%02X frame=%d\n", round_num, cur_ram, frame))
            if round_num == TARGET_ROUND then
                STATE = "TRANSITION_SETTLE"
                last_hop = frame + 0  -- no settle; rely on apex-detection to time the dance
                log("[INFO] L4R1 ram reached — waiting for first apex landing\n")
                return
            end
            STATE = "ADVANCE"
            last_hop = frame + 90  -- transition animation
        end
        return
    end

    if STATE == "ADVANCE" then
        -- Wait then press Start ONCE for 30 frames to advance via cheat
        if frame < last_hop + 90 then return end
        local elapsed = frame - (last_hop + 90)
        if elapsed < 30 then
            set("1 Player Start", true)
        else
            set("1 Player Start", false)
            STATE = "WAIT_RAM"  -- next ram change advances round_num
        end
        return
    end

    if STATE == "TRANSITION_SETTLE" then
        if frame < last_hop then return end
        STATE = "WAIT_APEX_STABLE"
        apex_stable_count = 0
        log(string.format("[INFO] transition settle done at frame=%d; waiting for stable apex\n", frame))
        return
    end

    -- Wait for pos = APEX_VAL stable for N consecutive frames (Q*bert landed in L4R1)
    if STATE == "WAIT_APEX_STABLE" then
        local p = mem and mem:read_u8(POS_ADDR) or 0
        if p == APEX_VAL then
            apex_stable_count = apex_stable_count + 1
            if apex_stable_count >= 30 then
                log(string.format("[INFO] apex stable for 30 frames at frame=%d — start dance\n", frame))
                STATE = "SNAP_S0"
                last_hop = frame + 5
            end
        else
            apex_stable_count = 0
        end
        return
    end

    if hop_dir or frame < last_hop + 30 then return end

    if STATE == "SNAP_S0" then
        snap("state0")
        STATE = "DO_DR"
        return
    end

    if STATE == "DO_DR" then
        start_hop("DR")
        STATE = "WAIT_C11"
        return
    end

    if STATE == "WAIT_C11" then
        local p = mem and mem:read_u8(POS_ADDR) or 0
        if p == pos_at_hop_start then
            -- Hop didn't register; retry
            log(string.format("[bot] DR didn't land (pos still 0x%02X), retry frame=%d\n", p, frame))
            STATE = "DO_DR"
            return
        end
        log(string.format("[INFO] DR landed at pos=0x%02X frame=%d\n", p, frame))
        STATE = "DO_UL"
        return
    end

    if STATE == "DO_UL" then
        start_hop("UL")
        STATE = "WAIT_APEX_BACK"
        return
    end

    if STATE == "WAIT_APEX_BACK" then
        local p = mem and mem:read_u8(POS_ADDR) or 0
        if p == APEX_VAL then
            log(string.format("[INFO] back at apex frame=%d\n", frame))
            snap("state1")
            log("[done]\n")
            if f then f:close() end
            manager.machine:exit()
            return
        end
        if frame - last_hop > 90 then
            -- Didn't make it back; abort snap state-1 anyway
            log(string.format("[WARN] not back at apex (pos=0x%02X) after 90 frames — aborting\n", p))
            snap("state1_offapex")
            log("[done]\n")
            if f then f:close() end
            manager.machine:exit()
            return
        end
        return
    end
end)
