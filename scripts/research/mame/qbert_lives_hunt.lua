-- Q*bert: find lives counter by watching RAM across a Q*bert death
-- Strategy: start game, sit still (Q*bert at apex), wait for enemy kill,
-- scan RAM before/after for addresses that decreased by 1

local frame = 0
local fields = {}
local mem = nil
local snap_pre = nil   -- RAM snapshot before death
local snap_post = nil  -- RAM snapshot after death
local state = "boot"
local death_detected = false

-- Track Q*bert's apex position via some indicator
-- We'll detect death by watching for position jump back to apex
-- Simplified: just take two snapshots at specific frames
-- Frame 1200: Q*bert is alive (before enemies typically reach)
-- Frame 3000: after likely death (30 seconds = 1800 frames after start)

local function press(name, on)
    if fields[name] then fields[name]:set_value(on and 1 or 0) end
end

local function snap_ram(start_addr, len)
    local s = {}
    for i = 0, len-1 do
        local ok, v = pcall(function() return mem:read_u8(start_addr + i) end)
        s[i] = ok and v or 0xFF
    end
    return s
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
    end

    -- Coin + start (no button presses after this - let Q*bert sit at apex)
    press("Coin 1",         frame >= 500 and frame < 530)
    press("1 Player Start", frame >= 700 and frame < 730)

    if frame == 800 then
        print("Game started, Q*bert sitting at apex waiting for enemies...")
    end

    -- Pre-death snapshot at frame 1200 (game running, probably alive)
    if frame == 1200 and mem and not snap_pre then
        snap_pre = snap_ram(0, 0x200)
        io.write("Pre-death RAM[00-3F]: ")
        for i = 0, 63 do io.write(string.format("%02X ", snap_pre[i] or 0xFF)) end
        io.write("\n")
        print("Pre-death snapshot at frame " .. frame)
        io.flush()
    end

    -- Screenshot every 600 frames
    if frame >= 800 and (frame % 600) == 0 then
        manager.machine.video:snapshot()
        print("snap@" .. frame)
    end

    -- Post-death snapshot at frame 3600 (60 seconds after boot)
    -- By this time Q*bert should have died at least once
    if frame == 3600 and mem and snap_pre and not snap_post then
        snap_post = snap_ram(0, 0x200)
        io.write("Post-death RAM[00-3F]: ")
        for i = 0, 63 do io.write(string.format("%02X ", snap_post[i] or 0xFF)) end
        io.write("\n")
        
        -- Compare snapshots
        print("\n=== RAM DIFF (pre-death vs post-death) ===")
        for i = 0, 0x1FF do
            local pre = snap_pre[i] or 0xFF
            local post = snap_post[i] or 0xFF
            if pre ~= post then
                local delta = (post - pre + 256) % 256
                local note = ""
                if delta == 255 then note = "  ← DECREASED BY 1 (lives candidate!)"
                elseif delta == 1 then note = "  ← increased by 1"
                elseif delta == 2 then note = "  ← increased by 2"
                end
                io.write(string.format("  0x%04X: %02X → %02X (delta=%d)%s\n", i, pre, post, delta <= 127 and delta or delta-256, note))
            end
        end
        io.flush()
        print("Post-death snapshot at frame " .. frame)
    end

    if frame >= 5000 then
        print("Done at frame " .. frame)
        manager.machine:exit()
    end
end)
