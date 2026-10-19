-- Diagnostic: coin+start, NO RAM writes, watch game state for 2500 frames
local BASE = "/home/will/WorldFoundry.2026-new-level"
local LOG = BASE .. "/scripts/research/mame/game_state.txt"
local f = io.open(LOG, "w")
local function log(s) io.write(s); io.flush(); if f then f:write(s); f:flush() end end

local frame = 0
local fields = {}
local mem = nil
local KEY_ADDRS = {0x0081, 0x008F, 0x0087, 0x0090, 0x0093, 0x00B6, 0x00B7, 0x00B8, 0x0D00, 0x0D03}

emu.register_frame_done(function()
    frame = frame + 1
    if frame == 1 then
        for tag,port in pairs(manager.machine.ioport.ports) do
            for name,field in pairs(port.fields) do fields[name]=field end
        end
        local cpu = manager.machine.devices[":maincpu"]
        mem = cpu and cpu.spaces["program"]
    end

    if fields["Coin 1"]         then fields["Coin 1"]:set_value(frame>=500 and frame<600 and 1 or 0) end
    if fields["1 Player Start"] then fields["1 Player Start"]:set_value(frame>=800 and frame<900 and 1 or 0) end

    -- NO RAM writes at all

    -- Log key addresses every 200 frames
    if mem and frame % 200 == 0 then
        local vals = {}
        for _, addr in ipairs(KEY_ADDRS) do
            local v=0; pcall(function() v=mem:read_u8(addr) end)
            vals[#vals+1] = string.format("0x%04X=%d", addr, v)
        end
        log(string.format("[f%05d] %s\n", frame, table.concat(vals, "  ")))
    end

    -- Also log joystick direction presses (frames where bot would hop)
    if frame >= 1100 and frame <= 1200 then
        -- Try 3 hops (Down-Right) to see if Q*bert moves
        if frame >= 1130 and frame < 1140 then
            if fields["P1 Right (Down-Right)"] then
                fields["P1 Right (Down-Right)"]:set_value(1)
            end
        else
            if fields["P1 Right (Down-Right)"] then
                fields["P1 Right (Down-Right)"]:set_value(0)
            end
        end
        if frame >= 1160 and frame < 1170 then
            if fields["P1 Right (Down-Right)"] then
                fields["P1 Right (Down-Right)"]:set_value(1)
            end
        else
            if frame >= 1140 then
                if fields["P1 Right (Down-Right)"] then
                    fields["P1 Right (Down-Right)"]:set_value(0)
                end
            end
        end
    end

    if frame >= 2500 then
        if f then f:close() end
        manager.machine:exit()
    end
end)
