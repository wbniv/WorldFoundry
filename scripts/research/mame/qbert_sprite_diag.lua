local BASE = "/home/will/WorldFoundry.2026-new-level"
local LOG = BASE .. "/scripts/research/mame/sprite_diag.txt"
local f = io.open(LOG, "w")
local function log(s) io.write(s); io.flush(); if f then f:write(s); f:flush() end end

local frame = 0
local fields = {}
local mem = nil

emu.register_frame_done(function()
    frame = frame + 1
    if frame == 1 then
        for tag,port in pairs(manager.machine.ioport.ports) do
            for name,field in pairs(port.fields) do fields[name]=field end
        end
        local cpu = manager.machine.devices[":maincpu"]
        mem = cpu and cpu.spaces["program"]
        log("[INFO] mem=" .. tostring(mem~=nil) .. "\n")
    end

    -- Coin+start (generous timing)
    if fields["Coin 1"]         then fields["Coin 1"]:set_value(frame>=500 and frame<600 and 1 or 0) end
    if fields["1 Player Start"] then fields["1 Player Start"]:set_value(frame>=800 and frame<900 and 1 or 0) end

    -- Keep lives
    if mem and frame > 800 then pcall(function() mem:write_u8(0x0D00, 9) end) end

    -- At frame 1500, dump RAM 0x3000-0x3080 and take snapshot
    if frame == 1500 and mem then
        log(string.format("\n=== SPRITE RAM dump @ frame %d ===\n", frame))
        for i=0,0x7F do
            local v=0; pcall(function() v=mem:read_u8(0x3000+i) end)
            if v ~= 0 then
                log(string.format("  0x%04X = %d (0x%02X)\n", 0x3000+i, v, v))
            end
        end
        log("=== END SPRITE DUMP ===\n")
        -- Also dump 0x0080-0x00A0 for position tracking
        log("=== RAM 0x0080-0x00A0 ===\n")
        for i=0,0x1F do
            local v=0; pcall(function() v=mem:read_u8(0x80+i) end)
            log(string.format("  0x%04X = %d\n", 0x80+i, v))
        end
        -- Try screenshot
        pcall(function() manager.machine.video:snapshot() end)
        log("=== snapshot attempted ===\n")
    end

    if frame >= 1600 then
        if f then f:close() end
        manager.machine:exit()
    end
end)
