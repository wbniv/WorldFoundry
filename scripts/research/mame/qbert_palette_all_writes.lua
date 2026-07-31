-- Capture all unique palette states written to 0x5000-0x501F at startup.
local LOG_PATH = "/home/will/WorldFoundry.2026-new-level/scripts/research/mame/palette_all_writes.txt"
local logfile = io.open(LOG_PATH, "w")
local function log(s) io.write(s); io.flush(); if logfile then logfile:write(s); logfile:flush() end end

local DAC = {0,16,33,49,70,86,102,118,136,152,169,185,206,222,238,255}
local function decode(b0, b1)
    return DAC[(b1 & 0xF) + 1], DAC[((b0 >> 4) & 0xF) + 1], DAC[(b0 & 0xF) + 1]
end

local frame = 0
local write_count = 0
local last_write_frame = -1
-- Current working palette (32 bytes, updated by tap)
local pal = {}
for i = 0, 31 do pal[i] = 0 end
-- Unique palettes seen
local snapshots = {}

local function pal_key()
    local t = {}
    for i = 0, 31 do t[i+1] = string.format("%02X", pal[i]) end
    return table.concat(t)
end

local seen_keys = {}

local function maybe_snapshot()
    local key = pal_key()
    if not seen_keys[key] then
        seen_keys[key] = true
        local copy = {}
        for i = 0, 31 do copy[i] = pal[i] end
        snapshots[#snapshots+1] = {f=last_write_frame, pal=copy}
        local n = #snapshots
        log(string.format("\n=== PALETTE #%d (after frame %d, %d total writes) ===\n",
            n, last_write_frame, write_count))
        for i = 0, 15 do
            local b0, b1 = copy[i*2], copy[i*2+1]
            local r, g, bv = decode(b0, b1)
            log(string.format("  pen%02d: #%02X%02X%02X  (raw: %02X %02X)\n", i, r, g, bv, b0, b1))
        end
    end
end

local tap_ok = false

emu.register_frame_done(function()
    frame = frame + 1

    if frame == 1 then
        local cpu = manager.machine.devices[":maincpu"]
        local mem = cpu and cpu.spaces["program"]
        if mem then
            local ok = pcall(function()
                mem:install_write_tap(0x5000, 0x501F, "pal_snap", function(off, data, mask)
                    pal[off - 0x5000] = data & 0xFF
                    write_count = write_count + 1
                    last_write_frame = frame
                end)
            end)
            tap_ok = ok
            log("[INFO] tap=" .. tostring(ok) .. "\n")
        end
    end

    -- Snapshot when writes have settled (no write for 3 frames)
    if last_write_frame > 0 and frame - last_write_frame == 3 then
        maybe_snapshot()
    end

    if frame == 600 then
        log(string.format("\n=== DONE: %d writes, %d unique palettes ===\n",
            write_count, #snapshots))
        if logfile then logfile:close() end
        manager.machine:exit()
    end
end)
