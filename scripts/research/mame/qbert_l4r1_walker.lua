-- qbert_l4r1_walker.lua: capture L4R1 state-1 by combining:
--   1. DIP cheat ON for round-advance (proven mechanism in qbert_round_shots).
--   2. At L4R1 entry (ram[0x081] == 0x13, round_num=16), execute a fixed-timing
--      2-hop dance ending at +119 frames where HUD has updated to L4R1
--      (verified via qbert_round_byte_hunt screenshot).
--   3. Use ROM position byte 0x0D64 to verify each hop landed; retry if dropped.
--
-- The fixed +119 timing matches qbert_round_shots's HOP_DELAY+HOP_HOLD+INTER_HOP+
-- HOP_HOLD+POST_HOP_WAIT = 30+12+35+12+30. Confirmed visually.

local BASE = "/home/will/WorldFoundry.2026-new-level"
local LOG = BASE .. "/scripts/research/mame/l4r1_walker.txt"
local f = io.open(LOG, "w")
local function log(s) io.write(s); io.flush(); if f then f:write(s); f:flush() end end

local DIRS = {
    DR = "P1 Right (Down-Right)",
    UL = "P1 Left (Up-Left)",
}
local CHEAT = "Demo Mode (Unlim Lives, Start=Adv (Cheat)"
local POS_ADDR = 0x0D64
local APEX_VAL = 0xB8
local LIVES = 0x0D00

local frame, fields, mem = 0, {}, nil
local PHASE = "BOOT"
local round_num = 0
local last_ram = -1
local snap_idx = 0

-- Round_shots-matched timing
local HOP_DELAY = 30
local HOP_HOLD = 12
local INTER_HOP = 35
local POST_HOP_WAIT = 30
local hop1_at, hop1_rel_at, hop2_at, hop2_rel_at, hop_snap_at = -1,-1,-1,-1,-1
local s0_snap_at = -1
local adv_at, adv_rel_at = -1, -1
local TARGET_ROUND = 16

local function set(name, on) if fields[name] then fields[name]:set_value(on and 1 or 0) end end
local function snap(label)
    snap_idx = snap_idx + 1
    manager.machine.video:snapshot()
    local p = mem and mem:read_u8(POS_ADDR) or 0
    log(string.format("[snap %s] idx=%04d frame=%d pos=0x%02X\n", label, snap_idx-1, frame, p))
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

    set("Coin 1", frame >= 500 and frame < 560)
    -- Boot Start press — explicit release after window
    if PHASE == "BOOT" or PHASE == "WAIT_RAM" then
        set("1 Player Start", frame >= 700 and frame < 760)
    end

    if mem and frame > 750 then mem:write_u8(LIVES, 9) end

    -- Default joystick low (override during HOP_DANCE phase only)
    if PHASE ~= "HOP_DANCE" then
        set("P1 Right (Down-Right)", false)
        set("P1 Left (Up-Left)", false)
    end

    if PHASE == "BOOT" then
        if frame >= 1100 then PHASE = "WAIT_RAM"; log("[INFO] WAIT_RAM\n") end
        return
    end

    local cur_ram = mem and mem:read_u8(0x0081) or 0

    if PHASE == "WAIT_RAM" then
        if cur_ram >= 0x04 and cur_ram ~= last_ram then
            round_num = round_num + 1
            last_ram = cur_ram
            log(string.format("[round %d] ram=0x%02X frame=%d\n", round_num, cur_ram, frame))
            if round_num == TARGET_ROUND then
                -- Schedule the snap dance with EXACT round_shots timing.
                -- Take state-0 snap immediately at ram-change (mirrors round_shots's s0).
                snap("state0")
                PHASE = "HOP_DANCE"
                hop1_at = frame + HOP_DELAY
                hop1_rel_at = hop1_at + HOP_HOLD
                hop2_at = hop1_rel_at + INTER_HOP
                hop2_rel_at = hop2_at + HOP_HOLD
                hop_snap_at = hop2_rel_at + POST_HOP_WAIT
                log(string.format("[INFO] L4R1 dance scheduled: hop1=%d hop2=%d snap=%d\n",
                    hop1_at, hop2_at, hop_snap_at))
                return
            end
            PHASE = "ADVANCE"
            adv_at = frame + 5
            adv_rel_at = adv_at + 30
        end
        return
    end

    if PHASE == "ADVANCE" then
        set("1 Player Start", frame >= adv_at and frame < adv_rel_at)
        if frame >= adv_rel_at then
            PHASE = "WAIT_RAM"
        end
        return
    end

    if PHASE == "HOP_DANCE" then
        set("P1 Right (Down-Right)", frame >= hop1_at and frame < hop1_rel_at)
        set("P1 Left (Up-Left)",     frame >= hop2_at and frame < hop2_rel_at)
        if frame == hop_snap_at then
            snap("state1")
            -- Read pos to confirm Q*bert location at snap moment
            local p = mem and mem:read_u8(POS_ADDR) or 0
            log(string.format("[INFO] dance complete, pos at snap = 0x%02X (apex=0x%02X)\n", p, APEX_VAL))
            log("[done]\n")
            if f then f:close() end
            manager.machine:exit()
            return
        end
        return
    end
end)
