-- Q*bert palette capture using Demo Mode DIP cheat
-- "Demo Mode (Unlim Lives, Start=Adv (Cheat)" DIP = On gives:
--   - Unlimited lives (no death handling needed)
--   - 1P Start button advances to next round
-- Strategy: coin+start to begin, then press Start every ~1500 frames to skip rounds
-- Write tap on 0x5000-0x501F catches every palette write

local frame = 0
local fields = {}
local mem = nil
local palette_log = {}
local tap_installed = false
local level_snapshots = {}  -- {frame, batch_idx} for each Start press

local COIN_FRAME  = 500
local START_FRAME = 700
-- Press Start every N frames to advance rounds (after game is running)
local ADVANCE_INTERVAL = 1800   -- ~30 seconds per round
local FIRST_ADVANCE    = 2200   -- first advance after game settles

local function press(name, on)
    if fields[name] then fields[name]:set_value(on and 1 or 0) end
end

local DAC = {0,16,33,49,70,86,102,118,136,152,169,185,206,222,238,255}

local function decode_color(b0, b1)
    -- Gottlieb palette format: even byte = G[7:4]|B[3:0], odd byte = R[3:0]
    local g = DAC[math.floor(b0 / 16) + 1]
    local bv = DAC[(b0 % 16) + 1]
    local r = DAC[(b1 % 16) + 1]
    return r, g, bv
end

local function print_palette_batch(writes, label)
    print(string.format("\n=== PALETTE @ %s ===", label))
    for i = 0, 15 do
        local b0 = writes[i*2]
        local b1 = writes[i*2+1]
        if b0 ~= nil and b1 ~= nil then
            local r, g, bv = decode_color(b0, b1)
            print(string.format("  [%2d] #%02X%02X%02X  (raw %02X %02X)", i, r, g, bv, b0, b1))
        end
    end
    io.flush()
end

local function flush_palette(label)
    if #palette_log == 0 then return end
    local writes = {}
    for _, e in ipairs(palette_log) do
        writes[e.off] = e.val
    end
    print_palette_batch(writes, label)
    palette_log = {}
end

emu.register_frame_done(function()
    frame = frame + 1

    -- Frame 1: cache inputs, memory, install write tap, set Demo Mode DIP
    if frame == 1 then
        for tag, port in pairs(manager.machine.ioport.ports) do
            for name, field in pairs(port.fields) do
                fields[name] = field
                -- Enable Demo Mode DIP cheat
                if name == "Demo Mode (Unlim Lives, Start=Adv (Cheat)" then
                    field:set_value(1)
                    print("Demo Mode DIP enabled: " .. name)
                end
            end
        end
        local cpu = manager.machine.devices[":maincpu"]
        if cpu then mem = cpu.spaces["program"] end
        print("Init: mem=" .. tostring(mem ~= nil))

        if mem then
            local ok, err = pcall(function()
                mem:install_write_tap(0x5000, 0x501F, "pal_tap", function(off, data, mask)
                    palette_log[#palette_log+1] = {frame=frame, off=off, val=data}
                end)
                tap_installed = true
            end)
            if not ok then
                ok, err = pcall(function()
                    mem:tap_write(0x5000, 0x501F, "pal_tap", function(off, data)
                        palette_log[#palette_log+1] = {frame=frame, off=off, val=data}
                    end)
                    tap_installed = true
                end)
            end
            print("Tap installed: " .. tostring(tap_installed))
        end
    end

    -- Coin + Start to begin
    press("Coin 1",         frame >= COIN_FRAME and frame < COIN_FRAME + 30)
    press("1 Player Start", frame >= START_FRAME and frame < START_FRAME + 30)

    -- Advance rounds using Start button (Demo Mode: Start=Advance)
    if frame >= FIRST_ADVANCE then
        local elapsed = frame - FIRST_ADVANCE
        local advance_num = math.floor(elapsed / ADVANCE_INTERVAL)
        local phase = elapsed % ADVANCE_INTERVAL

        -- Flush palette log just before each advance (captures previous level's palette)
        if phase == 0 and advance_num >= 1 then
            flush_palette(string.format("before advance #%d @ frame %d", advance_num, frame))
        end

        -- Press Start for 20 frames to advance
        press("1 Player Start", phase < 20)
    end

    -- Screenshot every 1500 frames after game start
    if frame >= START_FRAME and (frame % 1500) == 0 then
        manager.machine.video:snapshot()
        print(string.format("snap @ frame %d  (tap_log=%d)", frame, #palette_log))
    end

    -- Periodic status
    if frame % 3000 == 0 then
        print(string.format("frame %d  palette_writes=%d", frame, #palette_log))
    end

    if frame >= 20000 then
        flush_palette("FINAL @ frame " .. frame)
        manager.machine:exit()
    end
end)
