-- Scan a WIDE RAM range to find lives counter
-- Take snapshot at game start (3 lives), and after first death
-- Also dump the full memory map to find actual RAM ranges

local frame = 0
local fields = {}
local mem = nil
local snap_t0 = nil
local snap_t1 = nil
local snap_t2 = nil
local RANGE_START = 0x0000
local RANGE_END   = 0x3FFF

local function press(name, on)
    if fields[name] then fields[name]:set_value(on and 1 or 0) end
end

local function snap_range(s, e)
    local snap = {}
    for i = s, e do
        local ok, v = pcall(function() return mem:read_u8(i) end)
        snap[i] = ok and v or 0xFF
    end
    return snap
end

local function diff_snaps(a, b, label)
    print(string.format("\n=== DIFF %s ===", label))
    for i = RANGE_START, RANGE_END do
        local va = a[i] or 0xFF
        local vb = b[i] or 0xFF
        if va ~= vb then
            local delta = (vb - va + 256) % 256
            local note = ""
            if delta == 255 then note = " ← DEC by 1 **LIVES?**"
            elseif delta == 1 then note = " ← INC by 1"
            elseif va == 3 and vb == 2 then note = " ← 3→2 **LIVES?**"
            elseif va == 2 and vb == 1 then note = " ← 2→1 **LIVES?**"
            end
            if string.len(note) > 0 or (delta >= 254 or delta <= 2) then
                io.write(string.format("  0x%04X: %02X→%02X%s\n", i, va, vb, note))
            end
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

        -- Dump memory space info
        if mem then
            print("Memory space: " .. tostring(mem))
        end
    end

    press("Coin 1",         frame >= 500 and frame < 530)
    press("1 Player Start", frame >= 700 and frame < 730)

    -- Snapshot at game start (3 lives)
    if frame == 900 and mem then
        snap_t0 = snap_range(RANGE_START, RANGE_END)
        print("Snapshot T0 (3 lives) at frame " .. frame)
        -- Print interesting ranges
        for _, se in ipairs({{0x80,0xFF},{0x100,0x1FF},{0x200,0x2FF}}) do
            local s, e = se[1], se[2]
            local non_ff = {}
            for i = s, e do
                if snap_t0[i] ~= 0xFF then
                    non_ff[#non_ff+1] = string.format("0x%04X=%02X", i, snap_t0[i])
                end
            end
            if #non_ff > 0 then
                print("  Non-0xFF at " .. string.format("0x%04X-0x%04X: ", s, e) .. table.concat(non_ff, " "))
            end
        end
    end

    -- Snapshot at frame 2100 (35 seconds — likely 2 lives after first death)
    if frame == 2100 and snap_t0 and not snap_t1 then
        snap_t1 = snap_range(RANGE_START, RANGE_END)
        print("Snapshot T1 at frame " .. frame)
        diff_snaps(snap_t0, snap_t1, "T0→T1 (3→2 lives?)")
    end

    -- Screenshot every 600 frames
    if frame >= 900 and (frame % 600) == 0 then
        manager.machine.video:snapshot()
        print("snap@" .. frame)
    end

    if frame >= 4000 then
        print("Done at frame " .. frame)
        manager.machine:exit()
    end
end)
