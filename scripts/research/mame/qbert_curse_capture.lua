-- qbert_curse_capture.lua: force a Q*bert death and snap every frame to
-- isolate the curse-bubble window.
--
-- Strategy: cheat ON for normal Demo AI play. After ~5 seconds of in-game,
-- write an off-pyramid value to player-position byte 0x0081 to trigger the
-- fall + curse-bubble + respawn animation. Snap every frame for 120 frames
-- starting immediately to capture the bubble.

local frame, fields, mem = 0, {}, nil
local forced_frame = nil
local CHEAT = "Demo Mode (Unlim Lives, Start=Adv (Cheat)"

local function log(s) io.write(s); io.flush() end
local function set(name, on)
    if fields[name] then fields[name]:set_value(on and 1 or 0) end
end

emu.register_frame_done(function()
    frame = frame + 1

    if frame == 1 then
        for _, port in pairs(manager.machine.ioport.ports) do
            for name, fld in pairs(port.fields) do fields[name] = fld end
        end
        local cpu = manager.machine.devices[":maincpu"]
        mem = cpu and cpu.spaces["program"]
        if fields[CHEAT] then fields[CHEAT]:set_value(1) end
        log("[boot] cheat on\n")
    end

    set("Coin 1",        frame >= 500 and frame < 540)
    set("1 Player Start", frame >= 700 and frame < 740)

    if frame < 1100 or not mem then return end

    -- ~5 s of gameplay (300 frames @ 60 Hz) after gameplay starts, then force.
    if not forced_frame and frame == 1400 then
        -- 0xFE = off-pyramid sentinel — triggers death animation in arcade.
        mem:write_u8(0x0081, 0xFE)
        forced_frame = frame
        log(string.format("[force-death] frame=%d wrote 0xFE to 0x81\n", frame))
    end

    if forced_frame then
        local d = frame - forced_frame
        if d >= 0 and d < 120 then
            manager.machine.video:snapshot()
            if d % 10 == 0 then
                log(string.format("[snap d+%03d] frame=%d 0x81=0x%02X 0xD00=%d\n",
                    d, frame, mem:read_u8(0x0081), mem:read_u8(0x0D00)))
            end
        end
        if d >= 130 then
            log("[done]\n")
            manager.machine:exit()
        end
    end
end)
