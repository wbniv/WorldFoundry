-- qbert_l4r1_only.lua: capture L4R1 state-0 + state-1 by:
--   1. Boot, cheat ON.
--   2. Press Start; wait for ram 0x081 to change. Each change = +1 round visually.
--   3. Track our visual round counter; stop pressing Start when at L4R1 (15th change after L1R1 start).
--   4. The MOMENT cur_ram == 0x13 (L4R1 ram value), DISABLE cheat → Demo AI off.
--   5. Snap state-0 immediately, hop DR + UL, snap state-1.
--   6. Exit.
--
-- Per qbert_round_shots.txt: ram 0x04=L1R1, 0x13=L4R1 (15 increments).

local BASE = "/home/will/WorldFoundry.2026-new-level"
local LOG  = BASE .. "/scripts/research/mame/l4r1_only.txt"
local f = io.open(LOG, "w")
local function log(s) io.write(s); io.flush(); if f then f:write(s); f:flush() end end

local DIRS = {
    DR = "P1 Right (Down-Right)",
    UL = "P1 Left (Up-Left)",
}
local CHEAT = "Demo Mode (Unlim Lives, Start=Adv (Cheat)"
local POS   = 0x0081
local LIVES = 0x0D00
local TARGET_RAM = 0x12  -- L4 transition (catch BEFORE Demo AI plays L4R1)

local frame, fields, mem = 0, {}, nil
local STATE = "BOOT"
local last_ram = 0
local hop_dir, hop_start = nil, 0
local last_hop = 0
local snap_idx = 0
local start_release_at = 0  -- frame to release Start after a press
local advance_at      = 0   -- frame to next press Start

local function set(name, on) if fields[name] then fields[name]:set_value(on and 1 or 0) end end
local function set_cheat(on) if fields[CHEAT] then fields[CHEAT]:set_value(on and 1 or 0) end end
local function snap(label)
    snap_idx = snap_idx + 1
    manager.machine.video:snapshot()
    local rr = mem and mem:read_u8(POS) or 0
    log(string.format("[snap %s] idx=%04d frame=%d ram=0x%02X\n", label, snap_idx-1, frame, rr))
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
        set_cheat(true)
        log("[INFO] cheat enabled\n")
    end

    set("Coin 1", frame >= 500 and frame < 540)

    if mem and frame > 750 then mem:write_u8(LIVES, 9) end

    -- Release held hop
    if hop_dir and frame - hop_start >= 12 then
        set(DIRS[hop_dir], false)
        hop_dir = nil
    end

    if STATE == "BOOT" then
        if frame >= 1100 then
            STATE = "ADVANCE"
            advance_at = frame + 30  -- give game time to start
            log("[INFO] entering ADVANCE\n")
        end
        return
    end

    local cur_ram = mem and mem:read_u8(POS) or 0

    -- INSTANT cheat disable when we reach L4R1 ram value
    if STATE == "ADVANCE" and cur_ram == TARGET_RAM then
        set_cheat(false)
        set("1 Player Start", false)
        log(string.format("[INFO] L4R1 reached at frame=%d ram=0x%02X — cheat OFF\n", frame, cur_ram))
        STATE = "SETTLE"
        last_hop = frame + 180  -- wait for L4 transition animation to complete + Q*bert to land at apex
        return
    end

    -- Advance: press Start every 200 frames for 30 frames
    if STATE == "ADVANCE" then
        if frame == advance_at then
            set("1 Player Start", true)
            start_release_at = frame + 30
        elseif frame == start_release_at then
            set("1 Player Start", false)
            advance_at = frame + 170
        end
        return
    end

    -- Wait for cooldown
    if hop_dir or frame < last_hop + 30 then return end

    if STATE == "SETTLE" then
        snap("state0")
        STATE = "DO_DR"
        return
    end

    if STATE == "DO_DR" then
        start_hop("DR")
        STATE = "DO_UL"
        return
    end

    if STATE == "DO_UL" then
        start_hop("UL")
        STATE = "SNAP"
        return
    end

    if STATE == "SNAP" then
        snap("state1")
        log("[done]\n")
        if f then f:close() end
        manager.machine:exit()
        return
    end
end)
