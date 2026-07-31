-- Force Q*bert to level 2+ by finding and writing the round/level counter.
-- Strategy:
--   1. Boot game normally, snapshot RAM at frame 600 (middle of L1R1).
--   2. Repeatedly increment candidate addresses and watch for palette writes.
-- Also watches for any palette write and dumps it immediately.

local LOG_PATH = "/home/will/WorldFoundry.2026-new-level/scripts/research/mame/force_level.txt"
local logfile = io.open(LOG_PATH, "w")
local function log(s) io.write(s); io.flush(); if logfile then logfile:write(s); logfile:flush() end end

local DAC = {0,16,33,49,70,86,102,118,136,152,169,185,206,222,238,255}
local function decode(b0,b1)
    return DAC[(b1&0xF)+1], DAC[((b0>>4)&0xF)+1], DAC[(b0&0xF)+1]
end

local frame = 0
local fields = {}
local mem = nil
local pal = {}; for i=0,31 do pal[i]=0 end
local pal_snap0 = nil
local write_count = 0
local last_dump_count = 0
local snap0 = nil   -- RAM snapshot at frame 600

local function dump_palette(label)
    log(string.format("\n=== PALETTE CHANGE: %s (frame=%d, writes=%d) ===\n", label, frame, write_count))
    for i=0,15 do
        local b0,b1 = pal[i*2] or 0, pal[i*2+1] or 0
        local r,g,bv = decode(b0,b1)
        log(string.format("  pen%02d: #%02X%02X%02X  (raw: %02X %02X)\n", i, r, g, bv, b0, b1))
    end
end

-- Track which candidate addr we're probing
local probe_addr = nil
local probe_start_frame = -1
local probe_idx = 0
-- Candidate addresses to probe (likely game state variables near known addresses)
-- Lives at 0x0D00; look for round/level near there and in the first 256 bytes
local CANDIDATES = {}
for i = 0, 0xFF do CANDIDATES[#CANDIDATES+1] = i end
for i = 0x0D00, 0x0D20 do CANDIDATES[#CANDIDATES+1] = i end
for i = 0x0E00, 0x0E20 do CANDIDATES[#CANDIDATES+1] = i end

emu.register_frame_done(function()
    frame = frame + 1

    if frame == 1 then
        for tag,port in pairs(manager.machine.ioport.ports) do
            for name,field in pairs(port.fields) do fields[name]=field end
        end
        local cpu = manager.machine.devices[":maincpu"]
        mem = cpu and cpu.spaces["program"]
        if mem then
            local ok = pcall(function()
                mem:install_write_tap(0x5000, 0x501F, "pal_watch", function(off, data, mask)
                    local rel = off - 0x5000
                    if (pal[rel] or 0) ~= (data & 0xFF) then
                        pal[rel] = data & 0xFF
                        write_count = write_count + 1
                    end
                end)
            end)
            log("[INFO] tap=" .. tostring(ok) .. "\n")
        end
    end

    -- Coin + Start
    if fields["Coin 1"] then fields["Coin 1"]:set_value(frame>=60 and frame<90 and 1 or 0) end
    if fields["1 Player Start"] then fields["1 Player Start"]:set_value(frame>=180 and frame<210 and 1 or 0) end

    -- After startup writes settle, record baseline
    if frame == 500 and not pal_snap0 then
        pal_snap0 = {}
        for i=0,31 do pal_snap0[i] = pal[i] end
        log(string.format("[frame %d] baseline palette locked (%d writes so far)\n", frame, write_count))
    end

    -- Snapshot RAM at frame 600 (game is running, L1R1)
    if frame == 600 and mem then
        snap0 = {}
        for i=0,0x1FF do
            local ok,v = pcall(function() return mem:read_u8(i) end)
            snap0[i] = ok and v or 0xFF
        end
        log(string.format("[frame %d] RAM snapshot taken\n", frame))
        -- Log the values of candidate addresses (pick ones that look like small game counters: 0-15)
        log("Candidates with value 0-15:\n")
        for _,addr in ipairs(CANDIDATES) do
            local v = snap0[addr] or 0xFF
            if v <= 15 then
                log(string.format("  0x%04X = %d\n", addr, v))
            end
        end
    end

    -- Starting at frame 700: probe candidates by writing value+1 and watching for palette write
    if frame >= 700 and snap0 and mem then
        local since_probe = (probe_start_frame > 0) and (frame - probe_start_frame) or 0

        -- If palette changed since last probe: winner!
        if write_count > last_dump_count + 31 then  -- > 31 new writes = new full palette
            dump_palette(string.format("after probing 0x%04X", probe_addr or -1))
            last_dump_count = write_count
            log("\n=== LEVEL COUNTER FOUND at 0x" .. string.format("%04X", probe_addr or 0) .. " ===\n")
            -- Done! Keep running to capture all level palettes
            -- Try incrementing further
            if probe_addr and mem then
                local cur = snap0[probe_addr] or 0
                for lvl = 2, 4 do
                    -- Write level value and wait
                    log(string.format("[forcing level %d]\n", lvl))
                end
            end
        end

        -- Move to next candidate every 30 frames
        if since_probe >= 30 then
            probe_idx = probe_idx + 1
            if probe_idx > #CANDIDATES then
                log("[done probing all candidates]\n")
                if logfile then logfile:close() end
                manager.machine:exit()
                return
            end
            probe_addr = CANDIDATES[probe_idx]
            probe_start_frame = frame
            -- Write the candidate address with its current value + 4 (try advancing 4 levels)
            local cur = snap0[probe_addr] or 0
            if cur <= 11 then  -- only probe if current value is sane for a round counter
                local ok = pcall(function() mem:write_u8(probe_addr, cur + 4) end)
            end
        end
    end

    if frame >= 12000 then
        log("[timeout]\n")
        if logfile then logfile:close() end
        manager.machine:exit()
    end
end)
