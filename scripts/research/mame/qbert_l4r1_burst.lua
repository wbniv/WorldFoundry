-- qbert_l4r1_burst.lua: capture a burst of L4R1 frames, then we post-pick the
-- one where cube (1,1) just transitioned to state-1.
--
-- Mechanism: same as qbert_round_shots.lua (DIP cheat advances rounds), but at
-- round_num=16 (L4R1) instead of doing 2 hops + 1 snap, snap every 4 frames
-- for 240 frames (4 seconds at 60fps). Demo AI will inevitably hop multiple
-- cubes during this burst; one of those snaps will show (1,1) in state-1 and
-- Q*bert clear of (137, 80).

local BASE = "/home/will/WorldFoundry.2026-new-level"
local LOG = BASE .. "/scripts/research/mame/l4r1_burst.txt"
local f = io.open(LOG, "w")
local function log(s) io.write(s); io.flush(); if f then f:write(s); f:flush() end end

local frame, fields, mem = 0, {}, nil
local round_num = 0
local PHASE = "BOOT"
local last_ram = -1
local burst_start = -1
local burst_count = 0
local snap_idx = 0
local adv_at = -1
local adv_rel_at = -1
local done = false

local CHEAT = "Demo Mode (Unlim Lives, Start=Adv (Cheat)"
local POS = 0x0081

local BURST_LEN = 1200  -- 20 seconds; Demo AI in L4R1 may be slow to start
local BURST_INTERVAL = 8

local function snap(label)
    snap_idx = snap_idx + 1
    manager.machine.video:snapshot()
    local rr = mem and mem:read_u8(POS) or 0
    log(string.format("[snap %s] idx=%04d frame=%d ram=0x%02X\n", label, snap_idx-1, frame, rr))
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

    if fields["Coin 1"] then
        fields["Coin 1"]:set_value(frame >= 500 and frame < 560 and 1 or 0)
    end
    if fields["1 Player Start"] then
        local boot_press = frame >= 700 and frame < 760
        fields["1 Player Start"]:set_value(boot_press and 1 or 0)
    end

    if done then return end

    if PHASE == "BOOT" then
        if frame >= 1100 then PHASE = "WAIT_RAM" end
        return
    end

    local cur_ram = mem and mem:read_u8(POS) or 0

    if PHASE == "WAIT_RAM" then
        if cur_ram >= 0x04 and cur_ram ~= last_ram then
            round_num = round_num + 1
            log(string.format("[round %d] ram=0x%02X frame=%d\n", round_num, cur_ram, frame))
            last_ram = cur_ram
            if round_num == 16 then
                -- L4R1 reached. Start burst capture.
                snap(string.format("L4R1_burst_start"))
                PHASE = "BURST"
                burst_start = frame
                burst_count = 1
                return
            end
            -- Otherwise advance to next round
            PHASE = "ADVANCE"
            adv_at = frame + 90
            adv_rel_at = adv_at + 30
        end
        return
    end

    if PHASE == "BURST" then
        if (frame - burst_start) % BURST_INTERVAL == 0 then
            snap(string.format("burst_%03d", burst_count))
            burst_count = burst_count + 1
        end
        if frame - burst_start >= BURST_LEN then
            log(string.format("[done] captured %d burst frames\n", burst_count))
            done = true
            if f then f:close() end
            manager.machine:exit()
        end
        return
    end

    if PHASE == "ADVANCE" then
        if fields["1 Player Start"] then
            fields["1 Player Start"]:set_value(frame >= adv_at and frame < adv_rel_at and 1 or 0)
        end
        if frame >= adv_rel_at then
            PHASE = "WAIT_RAM"
        end
        return
    end
end)
