-- Q*bert: advance through rounds using 44-hop covering sequence
-- Hold lives counter at 0x0D00 = 03 for infinite lives
-- Take screenshot every 300 frames; capture palette at each round clear

local frame = 0
local fields = {}
local mem = nil
local LIVES_ADDR = 0x0D00
local LIVES_VAL  = 3

-- 44-hop covering sequence (computed by greedy BFS)
-- Each entry: {start_frame_offset, end_frame_offset, button_name}
-- Relative to FIRST_HOP_FRAME
local HOP_SEQ = {
  {"P1 Left (Down-Left)"}, {"P1 Right (Down-Right)"}, {"P1 Left (Down-Left)"},
  {"P1 Right (Down-Right)"}, {"P1 Right (Down-Right)"}, {"P1 Up (Up-Right)"},
  {"P1 Right (Down-Right)"}, {"P1 Right (Down-Right)"}, {"P1 Up (Up-Right)"},
  {"P1 Down (Up-Left)"}, {"P1 Down (Up-Left)"}, {"P1 Down (Up-Left)"},
  {"P1 Left (Down-Left)"}, {"P1 Left (Down-Left)"}, {"P1 Left (Down-Left)"},
  {"P1 Left (Down-Left)"}, {"P1 Down (Up-Left)"}, {"P1 Down (Up-Left)"},
  {"P1 Up (Up-Right)"}, {"P1 Right (Down-Right)"}, {"P1 Left (Down-Left)"},
  {"P1 Left (Down-Left)"}, {"P1 Down (Up-Left)"}, {"P1 Left (Down-Left)"},
  {"P1 Up (Up-Right)"}, {"P1 Up (Up-Right)"}, {"P1 Up (Up-Right)"},
  {"P1 Up (Up-Right)"}, {"P1 Right (Down-Right)"}, {"P1 Up (Up-Right)"},
  {"P1 Up (Up-Right)"}, {"P1 Left (Down-Left)"}, {"P1 Left (Down-Left)"},
  {"P1 Right (Down-Right)"}, {"P1 Right (Down-Right)"}, {"P1 Right (Down-Right)"},
  {"P1 Down (Up-Left)"}, {"P1 Left (Down-Left)"}, {"P1 Up (Up-Right)"},
  {"P1 Right (Down-Right)"}, {"P1 Up (Up-Right)"}, {"P1 Right (Down-Right)"},
  {"P1 Up (Up-Right)"}, {"P1 Right (Down-Right)"},
}

local PRESS = 8   -- frames to hold button
local WAIT  = 52  -- frames to wait between hops (60 total)
local N_HOPS = #HOP_SEQ

local function press(name, on)
    if fields[name] then fields[name]:set_value(on and 1 or 0) end
end

local function hop_active(hop_idx, f_offset)
    -- Returns button to press, or nil
    local base = (hop_idx - 1) * (PRESS + WAIT)
    if f_offset >= base and f_offset < base + PRESS then
        return HOP_SEQ[hop_idx][1]
    end
    return nil
end

local GAME_START = 800   -- frame when game input begins
local SEQ_START  = 900   -- frame when first hop occurs
local SEQ_LEN    = N_HOPS * (PRESS + WAIT)

-- Track screenshots to detect level changes
local last_snap_colors = nil

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

    -- Coin + start
    press("Coin 1",         frame >= 500 and frame < 530)
    press("1 Player Start", frame >= 700 and frame < 730)

    if frame == 700 then print("Game starting") end

    -- Hold lives counter at 3 every frame after game starts
    if frame >= 800 and mem then
        pcall(function() mem:write_u8(LIVES_ADDR, LIVES_VAL) end)
    end

    -- Run covering sequence continuously (repeat when done)
    if frame >= SEQ_START then
        local f_offset = (frame - SEQ_START) % SEQ_LEN
        -- Release all buttons first
        for _, btn in ipairs({"P1 Left (Down-Left)","P1 Right (Down-Right)","P1 Up (Up-Right)","P1 Down (Up-Left)"}) do
            press(btn, false)
        end
        -- Check which hop is active
        for i = 1, N_HOPS do
            local btn = hop_active(i, f_offset)
            if btn then
                press(btn, true)
                break
            end
        end
    end

    -- Screenshot every 500 frames after game start
    if frame >= 900 and (frame % 500) == 0 then
        manager.machine.video:snapshot()
        print("snap@" .. frame)
        -- Also print some RAM
        if mem then
            local lives = mem:read_u8(LIVES_ADDR)
            io.write(string.format("  lives@0x0D00=%d  round_area:", lives))
            for i = 0x0D10, 0x0D20 do
                local ok, v = pcall(function() return mem:read_u8(i) end)
                io.write(string.format(" %02X", ok and v or 0xFF))
            end
            io.write("\n")
            io.flush()
        end
    end

    -- Run for 30000 frames (500 seconds of game time = ~8 minutes)
    if frame >= 30000 then
        print("Done at frame " .. frame)
        manager.machine:exit()
    end
end)
