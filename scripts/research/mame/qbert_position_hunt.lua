-- qbert_position_hunt.lua: find Q*bert's true position byte(s) in RAM.
--
-- Strategy: drive Q*bert through a known position sequence, snapshot RAM at
-- each landing, then identify bytes that change deterministically with
-- position. A true position byte will have:
--   - a unique value when at apex (visited 3 times in our sequence)
--   - a unique value when at (1,1)
--   - a unique value when at (1,0)
-- ...and apex-value matches across all 3 apex visits.

local BASE = "/home/will/WorldFoundry.2026-new-level"
local LOG  = BASE .. "/scripts/research/mame/position_hunt.txt"
local f = io.open(LOG, "w")
local function log(s) io.write(s); io.flush(); if f then f:write(s); f:flush() end end

local frame, fields, mem = 0, {}, nil
local STATE = "BOOT"
local hop_dir, hop_start = nil, 0
local last_hop = 0

-- Sequence: apex → DR → UL → DL → UR → apex (5 known positions)
-- Tagged: apex_a, c11 ((1,1)), apex_b, c10 ((1,0)), apex_c
-- (0,0) → DR → (1,1) → DL → (2,1) → DR → (3,2) → UL → (2,1) → UL → (1,0) →
-- UR → (0,0) → DL → (1,0) → UR → (0,0)
local SEQ = {
    {tag="apex_a", dir=nil},
    {tag="c11",    dir="DR"},
    {tag="c21_a",  dir="DL"},
    {tag="c32",    dir="DR"},
    {tag="c21_b",  dir="UL"},
    {tag="c10_a",  dir="UL"},
    {tag="apex_b", dir="UR"},
    {tag="c10_b",  dir="DL"},
    {tag="apex_c", dir="UR"},
}
local seq_idx = 1
local snaps = {}  -- snaps[tag] = byte array

local DIR_FIELD = {
    DR = "P1 Right (Down-Right)",
    UR = "P1 Up (Up-Right)",
    DL = "P1 Down (Down-Left)",
    UL = "P1 Left (Up-Left)",
}

local function set(name, on) if fields[name] then fields[name]:set_value(on and 1 or 0) end end
local function start_hop(dir)
    hop_dir = dir; hop_start = frame; last_hop = frame
    set(DIR_FIELD[dir], true)
end
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
    end

    set("Coin 1", frame >= 500 and frame < 540)
    set("1 Player Start", frame >= 700 and frame < 740)
    if mem and frame > 750 then mem:write_u8(0x0D00, 9) end

    if hop_dir and frame - hop_start >= 12 then
        set(DIR_FIELD[hop_dir], false)
        hop_dir = nil
    end

    if STATE == "BOOT" then
        if frame >= 1200 then
            STATE = "PLAY"
            last_hop = frame + 90  -- spawn drop-in settle
            log("[INFO] PLAY\n")
        end
        return
    end

    if hop_dir or frame < last_hop + 60 then return end

    if STATE == "PLAY" then
        local step = SEQ[seq_idx]
        if step.dir == nil then
            -- Snap at this known position
            log(string.format("[snap %s] frame=%d\n", step.tag, frame))
            snaps[step.tag] = read_range(0, 0x2000)
            -- Take snapshot screenshot for visual confirmation
            manager.machine.video:snapshot()
        else
            -- Hop, then snap
            start_hop(step.dir)
            STATE = "WAIT_LAND"
            return
        end
        seq_idx = seq_idx + 1
        if seq_idx > #SEQ then
            STATE = "ANALYZE"
            return
        end
        return
    end

    if STATE == "WAIT_LAND" then
        local step = SEQ[seq_idx]
        log(string.format("[snap %s] frame=%d\n", step.tag, frame))
        snaps[step.tag] = read_range(0, 0x2000)
        manager.machine.video:snapshot()
        seq_idx = seq_idx + 1
        if seq_idx > #SEQ then
            STATE = "ANALYZE"
            return
        end
        STATE = "PLAY"
        return
    end

    if STATE == "ANALYZE" then
        log("\n=== STRICT POSITION-BYTE CANDIDATES ===\n")
        log("apex stable across 3 visits AND each cube has unique value\n")
        log("AND same-cube revisits match (c21_a==c21_b, c10_a==c10_b)\n\n")
        local strict = {}
        for addr = 0, 0x1FFF do
            local s = {
                apex_a=snaps.apex_a[addr], apex_b=snaps.apex_b[addr], apex_c=snaps.apex_c[addr],
                c11=snaps.c11[addr], c21_a=snaps.c21_a[addr], c21_b=snaps.c21_b[addr],
                c32=snaps.c32[addr], c10_a=snaps.c10_a[addr], c10_b=snaps.c10_b[addr],
            }
            local ok = true
            for k,v in pairs(s) do if v == nil then ok = false; break end end
            if ok and s.apex_a == s.apex_b and s.apex_b == s.apex_c
               and s.c21_a == s.c21_b and s.c10_a == s.c10_b
               and s.apex_a ~= s.c11 and s.apex_a ~= s.c21_a
               and s.apex_a ~= s.c32 and s.apex_a ~= s.c10_a
               and s.c11 ~= s.c21_a and s.c11 ~= s.c32 and s.c11 ~= s.c10_a
               and s.c21_a ~= s.c32 and s.c21_a ~= s.c10_a
               and s.c32 ~= s.c10_a then
                strict[#strict+1] = {addr=addr, s=s}
                log(string.format("  0x%04X: apex=0x%02X (1,1)=0x%02X (2,1)=0x%02X (3,2)=0x%02X (1,0)=0x%02X\n",
                    addr, s.apex_a, s.c11, s.c21_a, s.c32, s.c10_a))
            end
        end
        log(string.format("\n%d STRICT candidates\n", #strict))

        log("\n[done]\n")
        if f then f:close() end
        manager.machine:exit()
        return
    end
end)
