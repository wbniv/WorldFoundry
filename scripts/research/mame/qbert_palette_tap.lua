-- Capture Q*bert palette writes using MAME memory write tap
-- The palette RAM at 0x5000 is write-only; tap catches the writes

local frame = 0
local fields = {}
local mem = nil
local LIVES_ADDR = 0x0D00
local palette_log = {}   -- list of {frame, addr, val} tuples
local tap_installed = false

local function press(name, on)
    if fields[name] then fields[name]:set_value(on and 1 or 0) end
end

-- Greedy 44-hop covering sequence
local HOP_SEQ = {
  "P1 Left (Down-Left)","P1 Right (Down-Right)","P1 Left (Down-Left)",
  "P1 Right (Down-Right)","P1 Right (Down-Right)","P1 Up (Up-Right)",
  "P1 Right (Down-Right)","P1 Right (Down-Right)","P1 Up (Up-Right)",
  "P1 Down (Up-Left)","P1 Down (Up-Left)","P1 Down (Up-Left)",
  "P1 Left (Down-Left)","P1 Left (Down-Left)","P1 Left (Down-Left)",
  "P1 Left (Down-Left)","P1 Down (Up-Left)","P1 Down (Up-Left)",
  "P1 Up (Up-Right)","P1 Right (Down-Right)","P1 Left (Down-Left)",
  "P1 Left (Down-Left)","P1 Down (Up-Left)","P1 Left (Down-Left)",
  "P1 Up (Up-Right)","P1 Up (Up-Right)","P1 Up (Up-Right)",
  "P1 Up (Up-Right)","P1 Right (Down-Right)","P1 Up (Up-Right)",
  "P1 Up (Up-Right)","P1 Left (Down-Left)","P1 Left (Down-Left)",
  "P1 Right (Down-Right)","P1 Right (Down-Right)","P1 Right (Down-Right)",
  "P1 Down (Up-Left)","P1 Left (Down-Left)","P1 Up (Up-Right)",
  "P1 Right (Down-Right)","P1 Up (Up-Right)","P1 Right (Down-Right)",
  "P1 Up (Up-Right)","P1 Right (Down-Right)",
}
local N_HOPS = #HOP_SEQ
local PRESS = 8
local WAIT  = 52
local SEQ_LEN = N_HOPS * (PRESS + WAIT)
local SEQ_START = 900

local function print_palette()
    if #palette_log == 0 then return end
    -- Group by frame batch (writes within 100 frames)
    local batches = {}
    local current = {frame=palette_log[1].frame, writes={}}
    for _, entry in ipairs(palette_log) do
        if entry.frame - current.frame > 200 then
            batches[#batches+1] = current
            current = {frame=entry.frame, writes={}}
        end
        current.writes[entry.off] = entry.val
        current.frame = entry.frame
    end
    batches[#batches+1] = current
    
    local DAC = {0,16,33,49,70,86,102,118,136,152,169,185,206,222,238,255}
    print(string.format("\n=== PALETTE BATCHES: %d total ===", #batches))
    for bi, batch in ipairs(batches) do
        print(string.format("  Batch %d @ frame %d (%d writes):", bi, batch.frame, 0))
        -- Decode 16 colors (32 bytes)
        local has_data = false
        for i = 0, 15 do
            local b0 = batch.writes[i*2] or batch.writes[i*2+1] and nil
            local b1 = batch.writes[i*2+1]
            if b0 and b1 then
                has_data = true
                local g = DAC[math.floor(b0 / 16) + 1]
                local b_val = DAC[(b0 % 16) + 1]
                local r = DAC[(b1 % 16) + 1]
                print(string.format("    [%2d] #%02X%02X%02X  (raw: %02X %02X)", i, r, g, b_val, b0, b1))
            end
        end
        if not has_data then
            -- Just print raw writes
            local offs = {}
            for off, _ in pairs(batch.writes) do offs[#offs+1] = off end
            table.sort(offs)
            for _, off in ipairs(offs) do
                io.write(string.format("    [%02X]=%02X ", off, batch.writes[off]))
            end
            io.write("\n")
        end
    end
    io.flush()
end

emu.register_frame_done(function()
    frame = frame + 1

    if frame == 1 then
        for tag, port in pairs(manager.machine.ioport.ports) do
            for name, field in pairs(port.fields) do fields[name] = field end
        end
        local cpu = manager.machine.devices[":maincpu"]
        if cpu then mem = cpu.spaces["program"] end
        print("Init: mem=" .. tostring(mem ~= nil))
        
        -- Install write tap on palette RAM 0x5000-0x501F
        if mem then
            local ok, err = pcall(function()
                mem:install_write_tap(0x5000, 0x501F, "pal_tap", function(off, data, mask)
                    palette_log[#palette_log+1] = {frame=frame, off=off, val=data}
                end)
                tap_installed = true
            end)
            if not ok then
                -- Try alternate API
                ok, err = pcall(function()
                    mem:tap_write(0x5000, 0x501F, "pal_tap", function(off, data)
                        palette_log[#palette_log+1] = {frame=frame, off=off, val=data}
                    end)
                    tap_installed = true
                end)
            end
            print("Tap installed: " .. tostring(tap_installed) .. " err=" .. tostring(err))
        end
    end

    -- Coin + start
    press("Coin 1",         frame >= 500 and frame < 530)
    press("1 Player Start", frame >= 700 and frame < 730)

    -- Hold lives at 3
    if frame >= 800 and mem then
        pcall(function() mem:write_u8(LIVES_ADDR, 3) end)
    end

    -- Covering sequence
    if frame >= SEQ_START then
        local f_offset = (frame - SEQ_START) % SEQ_LEN
        for _, btn in ipairs({"P1 Left (Down-Left)","P1 Right (Down-Right)","P1 Up (Up-Right)","P1 Down (Up-Left)"}) do
            press(btn, false)
        end
        local hop_i = math.floor(f_offset / (PRESS + WAIT)) + 1
        local hop_t = f_offset % (PRESS + WAIT)
        if hop_i >= 1 and hop_i <= N_HOPS and hop_t < PRESS then
            press(HOP_SEQ[hop_i], true)
        end
    end

    -- Print palette log summary every 5000 frames
    if frame % 5000 == 0 and #palette_log > 0 then
        print("=== frame " .. frame .. " palette writes so far: " .. #palette_log)
        print_palette()
        palette_log = {}  -- reset after printing
    end

    -- Screenshot every 2000 frames
    if frame >= 900 and (frame % 2000) == 0 then
        manager.machine.video:snapshot()
        print("snap@" .. frame)
    end

    if frame >= 30000 then
        print("=== FINAL palette writes: " .. #palette_log)
        print_palette()
        manager.machine:exit()
    end
end)
