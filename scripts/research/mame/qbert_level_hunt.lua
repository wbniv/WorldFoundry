-- Find the RAM address that holds the current level/round number.
-- Strategy: coin+start, let game boot to L1, snapshot RAM.
-- Then we'll look for addresses that change when round advances.
-- This run: just boot to gameplay and dump candidate addresses.

local LOG_PATH = "/home/will/WorldFoundry.2026-new-level/scripts/research/mame/level_hunt.txt"
local logfile = io.open(LOG_PATH, "w")
local function log(s) io.write(s); io.flush(); if logfile then logfile:write(s); logfile:flush() end end

local DAC = {0,16,33,49,70,86,102,118,136,152,169,185,206,222,238,255}
local function decode(b0, b1)
    return DAC[(b1&0xF)+1], DAC[((b0>>4)&0xF)+1], DAC[(b0&0xF)+1]
end

local frame = 0
local fields = {}
local mem = nil
local snap0 = nil  -- RAM snapshot at L1 start
local snap1 = nil  -- RAM snapshot after palette write (after hypothetical level advance)
local pal = {}
for i=0,31 do pal[i]=0 end
local pal_changed = false
local last_write_frame = -1
local write_count = 0

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
                        pal_changed = true
                        last_write_frame = frame
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

    -- Snapshot RAM at frame 400 (game running, L1R1 loaded)
    if frame == 400 and mem then
        snap0 = {}
        for i=0,0x1FF do
            local ok,v = pcall(function() return mem:read_u8(i) end)
            snap0[i] = ok and v or 0
        end
        log(string.format("[frame %d] RAM snapshot 0x0000-0x01FF taken\n", frame))
        -- Also dump current palette
        log("Current palette (L1R1 expected):\n")
        for i=0,15 do
            local b0,b1 = pal[i*2] or 0, pal[i*2+1] or 0
            local r,g,bv = decode(b0,b1)
            log(string.format("  pen%02d: #%02X%02X%02X\n", i, r, g, bv))
        end
        -- Dump small area around known addresses
        log("RAM 0x00-0x3F:\n")
        for i=0,0x3F do log(string.format(" %02X", snap0[i])) end
        log("\n")
    end

    -- Stop at frame 500
    if frame == 500 then
        log(string.format("\n[done] %d palette writes total\n", write_count))
        if logfile then logfile:close() end
        manager.machine:exit()
    end
end)
