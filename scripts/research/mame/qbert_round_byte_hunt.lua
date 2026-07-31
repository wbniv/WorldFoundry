-- qbert_round_byte_hunt.lua: find the byte(s) holding the visual round/level
-- displayed on the HUD.
--
-- Strategy: use DIP cheat to advance through all rounds. At each round's
-- "hop snap" moment (frame ram_change + 119, mirroring qbert_round_shots's
-- timing where the HUD reliably shows the current visual round), snapshot
-- RAM 0x0000-0x1FFF. Tag with the expected visual round.
--
-- Then post-analyze: for each byte, compute (snap[round_n][addr]) sequence
-- across rounds. A visual-round byte should increment by 1 per visual round
-- (or follow some level/round encoding pattern).

local BASE = "/home/will/WorldFoundry.2026-new-level"
local LOG  = BASE .. "/scripts/research/mame/round_byte_hunt.txt"
local f = io.open(LOG, "w")
local function log(s) io.write(s); io.flush(); if f then f:write(s); f:flush() end end

local frame, fields, mem = 0, {}, nil
local round_num = 0
local PHASE = "BOOT"
local last_ram = -1
local hop1_at, hop1_rel_at, hop2_at, hop2_rel_at, hop_snap_at = -1,-1,-1,-1,-1
local adv_at, adv_rel_at = -1, -1

-- Per round_shots's file_map (off-by-one due to transition screens):
--   round_num 1=L1R1, 2=L1R2, 3=L1R3, 4=L1R4, 5=L2-trans, 6=L2R1, 7=L2R2,
--   8=L2R3, 9=L2R4, 10=L3-trans, 11=L3R1, 12=L3R2, 13=L3R3, 14=L3R4,
--   15=L4-trans, 16=L4R1, 17=L4R2, 18=L4R3, 19=L4R4
local VISUAL_TAG = {
    [1]="L1R1",[2]="L1R2",[3]="L1R3",[4]="L1R4",
    [5]="L2-trans",[6]="L2R1",[7]="L2R2",[8]="L2R3",[9]="L2R4",
    [10]="L3-trans",[11]="L3R1",[12]="L3R2",[13]="L3R3",[14]="L3R4",
    [15]="L4-trans",[16]="L4R1",[17]="L4R2",[18]="L4R3",[19]="L4R4",
}

-- Minimal: snap RAM only at L1R1, L4R1 (sufficient to find level-counter byte
-- and round-counter byte). Plus L1R4 and L4R4 for extra resolution.
local SNAP_AT = {[1]=true, [4]=true, [6]=true, [9]=true, [11]=true, [14]=true,
                 [16]=true, [19]=true}
local snaps = {}  -- snaps[round_num] = byte array

local function read_range(base, len)
    local t = {}
    for i = 0, len-1 do
        local ok, v = pcall(function() return mem:read_u8(base+i) end)
        t[i] = ok and v or nil
    end
    return t
end

emu.register_frame_done(function()
    frame = frame + 1

    if frame == 1 then
        for _, port in pairs(manager.machine.ioport.ports) do
            for name, fld in pairs(port.fields) do fields[name] = fld end
        end
        local cpu = manager.machine.devices[":maincpu"]
        mem = cpu and cpu.spaces["program"]
        if fields["Demo Mode (Unlim Lives, Start=Adv (Cheat)"] then
            fields["Demo Mode (Unlim Lives, Start=Adv (Cheat)"]:set_value(1)
        end
    end

    if fields["Coin 1"] then fields["Coin 1"]:set_value(frame >= 500 and frame < 560 and 1 or 0) end
    if fields["1 Player Start"] then
        fields["1 Player Start"]:set_value(frame >= 700 and frame < 760 and 1 or 0)
    end

    if PHASE == "BOOT" then
        if frame >= 1100 then PHASE = "WAIT_RAM" end
        return
    end

    -- Default joystick
    if fields["P1 Right (Down-Right)"] then fields["P1 Right (Down-Right)"]:set_value(0) end
    if fields["P1 Left (Up-Left)"] then fields["P1 Left (Up-Left)"]:set_value(0) end

    local cur_ram = mem and mem:read_u8(0x081) or 0

    if PHASE == "WAIT_RAM" then
        if cur_ram >= 0x04 and cur_ram ~= last_ram then
            round_num = round_num + 1
            last_ram = cur_ram
            log(string.format("[round %d] %s ram=0x%02X frame=%d\n",
                round_num, VISUAL_TAG[round_num] or "?", cur_ram, frame))
            PHASE = "HOP"
            hop1_at = frame + 30
            hop1_rel_at = hop1_at + 12
            hop2_at = hop1_rel_at + 35
            hop2_rel_at = hop2_at + 12
            hop_snap_at = hop2_rel_at + 30
        end
        return
    end

    if PHASE == "HOP" then
        if fields["P1 Right (Down-Right)"] then
            fields["P1 Right (Down-Right)"]:set_value(
                (frame >= hop1_at and frame < hop1_rel_at) and 1 or 0)
        end
        if fields["P1 Left (Up-Left)"] then
            fields["P1 Left (Up-Left)"]:set_value(
                (frame >= hop2_at and frame < hop2_rel_at) and 1 or 0)
        end
        if frame == hop_snap_at then
            -- Snap RAM at this verified-visual-round moment
            if SNAP_AT[round_num] then
                snaps[round_num] = read_range(0, 0x2000)
                manager.machine.video:snapshot()  -- visual confirmation snap
                log(string.format("  [snap %s] ram saved + screenshot\n", VISUAL_TAG[round_num] or "?"))
            end
            -- Trigger ANALYZE only after final snap captured
            if round_num >= 19 then
                PHASE = "ANALYZE"
                return
            end
            PHASE = "ADVANCE"
            adv_at = frame + 5
            adv_rel_at = adv_at + 30
        end
        return
    end

    if PHASE == "ADVANCE" then
        if fields["1 Player Start"] then
            fields["1 Player Start"]:set_value(
                (frame >= adv_at and frame < adv_rel_at) and 1 or 0)
        end
        if frame >= adv_rel_at then
            PHASE = "WAIT_RAM"
        end
        return
    end

    if PHASE == "ANALYZE" then
        local keys = {1, 4, 6, 9, 11, 14, 16, 19}
        -- L1R1, L1R4, L2R1, L2R4, L3R1, L3R4, L4R1, L4R4
        local LEVEL_PATTERN = {1, 1, 2, 2, 3, 3, 4, 4}
        local RWL_PATTERN   = {1, 4, 1, 4, 1, 4, 1, 4}  -- round within level

        log("\n=== EXACT MATCH: level (1,1,2,2,3,3,4,4) ===\n")
        for addr = 0, 0x1FFF do
            local row = {}
            local valid = true
            for _, k in ipairs(keys) do
                local v = snaps[k] and snaps[k][addr]
                if v == nil then valid = false; break end
                row[#row+1] = v
            end
            if valid then
                local match = true
                for i = 1, #LEVEL_PATTERN do
                    if row[i] ~= LEVEL_PATTERN[i] then match = false; break end
                end
                if match then
                    log(string.format("  0x%04X: matches level pattern\n", addr))
                end
            end
        end

        log("\n=== EXACT MATCH: round-within-level (1,4,1,4,1,4,1,4) ===\n")
        for addr = 0, 0x1FFF do
            local row = {}
            local valid = true
            for _, k in ipairs(keys) do
                local v = snaps[k] and snaps[k][addr]
                if v == nil then valid = false; break end
                row[#row+1] = v
            end
            if valid then
                local match = true
                for i = 1, #RWL_PATTERN do
                    if row[i] ~= RWL_PATTERN[i] then match = false; break end
                end
                if match then
                    log(string.format("  0x%04X: matches round-within-level pattern\n", addr))
                end
            end
        end

        log("\n=== ZERO-INDEXED LEVEL (0,0,1,1,2,2,3,3) ===\n")
        local L0 = {0, 0, 1, 1, 2, 2, 3, 3}
        for addr = 0, 0x1FFF do
            local row = {}
            local valid = true
            for _, k in ipairs(keys) do
                local v = snaps[k] and snaps[k][addr]
                if v == nil then valid = false; break end
                row[#row+1] = v
            end
            if valid then
                local match = true
                for i = 1, #L0 do
                    if row[i] ~= L0[i] then match = false; break end
                end
                if match then
                    log(string.format("  0x%04X: matches zero-indexed level pattern\n", addr))
                end
            end
        end

        log("\n=== ZERO-INDEXED RWL (0,3,0,3,0,3,0,3) ===\n")
        local R0 = {0, 3, 0, 3, 0, 3, 0, 3}
        for addr = 0, 0x1FFF do
            local row = {}
            local valid = true
            for _, k in ipairs(keys) do
                local v = snaps[k] and snaps[k][addr]
                if v == nil then valid = false; break end
                row[#row+1] = v
            end
            if valid then
                local match = true
                for i = 1, #R0 do
                    if row[i] ~= R0[i] then match = false; break end
                end
                if match then
                    log(string.format("  0x%04X: matches zero-indexed RWL pattern\n", addr))
                end
            end
        end

        -- Also dump full table of bytes that have ≥3 distinct values (vs ≥4 before)
        log("\n=== BYTES WITH ≥3 DISTINCT VALUES (all snaps) ===\n")
        local hdr = "addr     "
        for _, k in ipairs(keys) do hdr = hdr .. string.format("%-9s", VISUAL_TAG[k]) end
        log(hdr .. "\n")
        for addr = 0, 0x1FFF do
            local row = {}
            local valid = true
            for _, k in ipairs(keys) do
                local v = snaps[k] and snaps[k][addr]
                if v == nil then valid = false; break end
                row[#row+1] = v
            end
            if valid then
                local distinct = {}
                for _, v in ipairs(row) do distinct[v] = true end
                local n = 0; for _ in pairs(distinct) do n = n + 1 end
                if n >= 3 and n <= 5 then  -- 3-5 distinct = level/round-style
                    local s = string.format("0x%04X   ", addr)
                    for _, v in ipairs(row) do s = s .. string.format("0x%02X     ", v) end
                    log(s .. "\n")
                end
            end
        end

        log("\n[done]\n")
        if f then f:close() end
        manager.machine:exit()
        return
    end
end)
