-- Dump all palette RAM written during Q*bert startup (0x5000-0x57FF).
-- The game pre-loads ALL round palettes at boot. We capture every write,
-- then after frame 120 decode all 32-byte blocks and identify rounds.

local LOG_PATH = "/home/will/WorldFoundry.2026-new-level/scripts/research/mame/palette_startup_dump.txt"
local logfile = io.open(LOG_PATH, "w")
local function log(s)
    io.write(s); io.flush()
    if logfile then logfile:write(s); logfile:flush() end
end

local DAC = {0,16,33,49,70,86,102,118,136,152,169,185,206,222,238,255}
local function dac(v) return DAC[(v & 0xF) + 1] end

-- Full palette RAM: address -> last byte written
local ram = {}
local write_count = 0
local frame = 0

emu.register_frame_done(function()
    frame = frame + 1

    if frame == 1 then
        local cpu = manager.machine.devices[":maincpu"]
        local mem = cpu and cpu.spaces["program"]
        if mem then
            local ok = pcall(function()
                mem:install_write_tap(0x5000, 0x57FF, "full_pal_tap", function(off, data, mask)
                    ram[off] = data & 0xFF
                    write_count = write_count + 1
                end)
            end)
            log(string.format("[INFO] tap installed=%s frame=1\n", tostring(ok)))
        end
    end

    -- After frame 120 all startup writes are done; decode and exit
    if frame == 200 then
        log(string.format("\n[INFO] Total writes captured: %d across %d addresses\n",
            write_count, (function() local n=0 for _ in pairs(ram) do n=n+1 end return n end)()))

        -- Find address range that was written
        local min_addr, max_addr = 0x5800, 0x5000
        for addr in pairs(ram) do
            if addr < min_addr then min_addr = addr end
            if addr > max_addr then max_addr = addr end
        end
        log(string.format("[INFO] Written range: 0x%04X – 0x%04X\n\n", min_addr, max_addr))

        -- Decode every 32-byte block (16 colours each) in the written range
        local block_start = min_addr - (min_addr % 32)
        local block = 0
        for base = block_start, max_addr, 32 do
            -- Check if this block has any data
            local has_data = false
            for i = 0, 31 do
                if ram[base + i] then has_data = true; break end
            end
            if has_data then
                block = block + 1
                log(string.format("=== BLOCK %d (0x%04X-0x%04X) ===\n", block, base, base+31))
                for i = 0, 15 do
                    local b0 = ram[base + i*2]
                    local b1 = ram[base + i*2 + 1]
                    if b0 and b1 then
                        local r = dac(b1)
                        local g = dac(b0 >> 4)
                        local bv = dac(b0)
                        log(string.format("  pen%02d: #%02X%02X%02X  (raw: %02X %02X)\n",
                            i, r, g, bv, b0, b1))
                    else
                        log(string.format("  pen%02d: missing (b0=%s b1=%s)\n",
                            i, tostring(b0), tostring(b1)))
                    end
                end
            end
        end

        log("\n=== DONE ===\n")
        if logfile then logfile:close() end
        manager.machine:exit()
    end
end)
