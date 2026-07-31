-- Full RAM diff: take snap before hop, make ONE clean hop, snap after.
-- Print ALL changed bytes with no filter. Also watch for palette changes.
local LOG_PATH = "/home/will/WorldFoundry.2026-new-level/scripts/research/mame/full_diff.txt"
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
local pal_written = 0
local last_pal_key = nil
local level_captured = 0

local function pal_key()
    local t = {}; for i=0,31 do t[i+1]=string.format("%02X",pal[i]) end
    return table.concat(t)
end

local function dump_palette(label)
    level_captured = level_captured + 1
    log(string.format("\n=== PALETTE %s (frame=%d) ===\n", label, frame))
    for i=0,15 do
        local b0,b1=pal[i*2] or 0,pal[i*2+1] or 0
        local r,g,bv=decode(b0,b1)
        log(string.format("  pen%02d: #%02X%02X%02X\n",i,r,g,bv))
    end
end

local function read_range(base, len)
    local t = {}
    for i=0,len-1 do
        local ok,v = pcall(function() return mem:read_u8(base+i) end)
        t[i] = ok and v or nil
    end
    return t
end

local function set_input(name, val)
    if fields[name] then fields[name]:set_value(val) end
end

local snap0 = nil
local snap1 = nil
local STATE = "BOOT"

emu.register_frame_done(function()
    frame = frame + 1

    if frame == 1 then
        for tag,port in pairs(manager.machine.ioport.ports) do
            for name,field in pairs(port.fields) do fields[name]=field end
        end
        local cpu = manager.machine.devices[":maincpu"]
        mem = cpu and cpu.spaces["program"]
        if mem then
            pcall(function()
                mem:install_write_tap(0x5000, 0x501F, "pal", function(off,data,mask)
                    pal[off-0x5000] = data & 0xFF; pal_written = pal_written + 1
                end)
            end)
        end
    end

    -- Lives
    if mem and frame > 300 then pcall(function() mem:write_u8(0x0D00, 3) end) end

    -- Coin + start
    set_input("Coin 1", frame>=60 and frame<90 and 1 or 0)
    set_input("1 Player Start", frame>=180 and frame<210 and 1 or 0)

    -- Wait for game fully active, then snap BEFORE any hop
    if STATE == "BOOT" and frame == 500 then
        snap0 = read_range(0, 0x2000)   -- 0x0000-0x1FFF
        log(string.format("[frame %d] snap0 taken\n", frame))
        last_pal_key = pal_key()
        STATE = "HOP"
    end

    -- Make exactly ONE hop at frame 540, wait until 650 for it to settle
    if STATE == "HOP" then
        -- Single hop Down-Right (toward row 2)
        set_input("P1 Right (Down-Right)", frame >= 540 and frame < 550 and 1 or 0)

        if frame == 640 then
            snap1 = read_range(0, 0x2000)
            log(string.format("[frame %d] snap1 taken (after 1 hop)\n", frame))

            -- Full diff
            local changed = {}
            for i=0,0x1FFF do
                local a, b = snap0[i], snap1[i]
                if a ~= nil and b ~= nil and a ~= b then
                    changed[#changed+1] = {addr=i, from=a, to=b}
                end
            end
            log(string.format("Total changed bytes: %d\n", #changed))
            for _, c in ipairs(changed) do
                local tag = ""
                if c.from == 0 and c.to >= 1 and c.to <= 4 then tag = " *** CUBE?" end
                if c.from == 0 and c.to > 0 and c.to < 32 then tag = tag .. " (was0->small)" end
                log(string.format("  0x%04X: %3d(0x%02X) -> %3d(0x%02X)%s\n",
                    c.addr, c.from, c.from, c.to, c.to, tag))
            end

            -- Now try to trigger level transitions by writing to round counter candidates
            -- Based on the diff, identify addresses that changed to 1 (after 1 hop)
            log("\n--- Addresses where value is now 1-4 and was 0 ---\n")
            for _, c in ipairs(changed) do
                if c.from == 0 and c.to >= 1 and c.to <= 4 then
                    log(string.format("  0x%04X: 0 -> %d\n", c.addr, c.to))
                end
            end

            STATE = "TRY_ADVANCE"
        end
    end

    -- Try advancing round by writing to various addresses
    if STATE == "TRY_ADVANCE" and frame == 660 then
        -- Strategy: write large values to locations that hold small non-zero values
        -- hoping one of them is the round counter (1=R1, advance to 5=L2R1)
        if mem then
            -- Try known candidate areas
            for addr = 0, 0xFF do
                local v = snap1[addr]
                if v and v >= 1 and v <= 4 then
                    pcall(function() mem:write_u8(addr, v + 4) end)
                end
            end
            log(string.format("[frame %d] wrote +4 to all 0x0000-0x00FF addrs with value 1-4\n", frame))
        end
        last_pal_key = pal_key()
        STATE = "WATCH"
    end

    if STATE == "WATCH" then
        local key = pal_key()
        if key ~= last_pal_key then
            dump_palette("transition")
            last_pal_key = key
        end
        if frame > 1200 then
            log("[done]\n")
            STATE = "DONE"
        end
    end

    if STATE == "DONE" or frame > 15000 then
        log(string.format("\n=== COMPLETE: %d palette changes seen ===\n", level_captured))
        if logfile then logfile:close() end
        manager.machine:exit()
    end
end)
