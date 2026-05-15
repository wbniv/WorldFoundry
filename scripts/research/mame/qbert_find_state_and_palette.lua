-- Q*bert: find cube state RAM address + dump palette at each level
-- Strategy:
--   1. Start game (coin@500, start@700)
--   2. At frame 900: snapshot all RAM 0x0000-0x01FF
--   3. At frames 920-950: hold DR to make one hop
--   4. At frame 1100: rescan RAM, print addresses that changed from 0 to 1-5
--      (those are cube state candidates)
--   5. If we find the cube state base, write all 28 to 2 to force level clear
--   6. Read 0x5000..0x501F for palette at each level
--   7. Repeat L1→L4

local frame = 0
local fields = {}
local mem = nil
local snap0 = nil          -- pre-hop RAM snapshot
local cube_base = nil      -- found cube state base address
local level_palettes = {}  -- indexed by level 1..4
local current_action = "boot"
local action_frame = 0     -- frame when current action started
local level = 1

local function press(name, on)
    if fields[name] then fields[name]:set_value(on and 1 or 0) end
end

local function read_pal()
    -- Read 32 bytes from CPU address 0x5000 (palette RAM)
    local bytes = {}
    for i = 0, 31 do
        local ok, v = pcall(function() return mem:read_u8(0x5000 + i) end)
        bytes[i+1] = ok and v or 0xFF
    end
    return bytes
end

local function dump_pal(label, bytes)
    io.write(string.format("PAL[%s]: ", label))
    for _, v in ipairs(bytes) do io.write(string.format("%02X", v)) end
    io.write("\n")
    io.flush()
end

local function snap_ram()
    local s = {}
    for i = 0, 0x1FF do
        local ok, v = pcall(function() return mem:read_u8(i) end)
        s[i] = ok and v or 0xFF
    end
    return s
end

emu.register_frame_done(function()
    frame = frame + 1

    -- Frame 1: init
    if frame == 1 then
        for tag, port in pairs(manager.machine.ioport.ports) do
            for name, field in pairs(port.fields) do fields[name] = field end
        end
        local cpu = manager.machine.devices[":maincpu"]
        if cpu then mem = cpu.spaces["program"] end
        print("Init: mem=" .. tostring(mem ~= nil))
    end

    -- Coin + start
    press("Coin 1",         frame >= 500 and frame < 530)
    press("1 Player Start", frame >= 700 and frame < 730)

    if frame == 700 then
        print("Game starting")
        current_action = "wait_game"
        action_frame = frame
    end

    -- After game boot (frame 900): read L1 palette and snapshot RAM
    if frame == 900 and mem then
        local p = read_pal()
        dump_pal("L1_initial", p)

        -- Print raw L1 palette
        io.write("RAM[0x5000..501F]: ")
        for i = 0, 31 do
            local ok, v = pcall(function() return mem:read_u8(0x5000 + i) end)
            io.write(string.format("%02X ", ok and v or 0xFF))
        end
        io.write("\n")

        snap0 = snap_ram()
        print("RAM snapshot at frame " .. frame)
        current_action = "pre_hop"
        action_frame = frame
    end

    -- At frame 950: make one DR hop
    press("P1 Right (Down-Right)", frame >= 950 and frame < 990)
    if frame == 950 then
        print("Pressing DR at frame " .. frame)
        current_action = "hopping"
        action_frame = frame
    end

    -- At frame 1100: diff RAM to find cube state
    if frame == 1100 and mem and snap0 and not cube_base then
        print("\n=== RAM DIFF (pre-hop vs +200 frames) ===")
        local candidates = {}
        for i = 0, 0x1FF do
            local ok, v = pcall(function() return mem:read_u8(i) end)
            if ok and snap0[i] ~= nil and snap0[i] ~= v then
                io.write(string.format("  0x%04X: %02X → %02X\n", i, snap0[i], v))
                if v >= 1 and v <= 4 and snap0[i] == 0 then
                    candidates[#candidates+1] = {addr=i, old=snap0[i], new=v}
                end
            end
        end

        -- Find runs of 28 consecutive 0-valued bytes near candidates
        print("\nCandidates (0→1..4):")
        for _, c in ipairs(candidates) do
            io.write(string.format("  0x%04X: %02X→%02X | ", c.addr, c.old, c.new))
            -- Print neighbors
            for j = -2, 30 do
                local ok, v = pcall(function() return mem:read_u8(c.addr - 1 + j) end)
                io.write(string.format("%02X", ok and v or 0xFF))
            end
            io.write("\n")
        end
        io.flush()

        -- Use the first candidate as cube_base guess
        if #candidates >= 1 then
            -- The cube that was hopped is at row=1, col=1 (DR from apex)
            -- That's cube linear index 2 (0-indexed: apex=0, (1,0)=1, (1,1)=2)
            local hopped_cube_idx = 2  -- DR from apex lands on cube #2
            cube_base = candidates[1].addr - hopped_cube_idx
            print(string.format("\nGuessed cube_base = 0x%04X (candidate - %d)", cube_base, hopped_cube_idx))
        end
    end

    -- At frame 1300: if we know cube_base, force level clear by writing state=2 to all 28 cubes
    if frame == 1300 and cube_base and mem then
        print("\nForcing level clear: writing state=2 to cubes 0..27 at 0x" .. string.format("%04X", cube_base))
        for i = 0, 27 do
            pcall(function() mem:write_u8(cube_base + i, 2) end)
        end
        manager.machine.video:snapshot()
        print("Snapshot taken (should show level clear)")
    end

    -- At frame 1500: read palette (should be L2 by now if level cleared)
    if frame == 1500 and mem then
        local p = read_pal()
        dump_pal("L2_attempt", p)
        manager.machine.video:snapshot()

        -- Dump low RAM to see level counter
        io.write("RAM[0x00..0x3F]@f1500: ")
        for i = 0, 63 do
            local ok, v = pcall(function() return mem:read_u8(i) end)
            io.write(string.format("%02X ", ok and v or 0xFF))
        end
        io.write("\n")
        io.flush()
    end

    -- Keep writing state=2 if cube_base known (sustain win condition)
    if cube_base and mem and frame >= 1300 and frame < 2000 and (frame % 30) == 0 then
        for i = 0, 27 do
            pcall(function() mem:write_u8(cube_base + i, 2) end)
        end
    end

    if frame >= 4000 then
        print("Done at frame " .. frame)
        manager.machine:exit()
    end
end)
