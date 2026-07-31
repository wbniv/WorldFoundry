-- Q*bert per-round palette capture
-- Uses the MAME :palette device to read resolved ARGB colors each round.
-- DIP cheat: Demo Mode = unlimited lives + Start = advance round.

local frame = 0
local round = 0
local FIRST_ADVANCE = 600    -- frames before first advance (game boots + attract)
local ADVANCE_INTERVAL = 1800 -- frames between round advances (~30 sec at 60fps)
local last_advance = -1
local dip_set = false

-- Lazy lookup — emu.register_start fires before machine devices are ready
local function palette_dev()
    return manager.machine.devices[":palette"]
end

local function dump_palette(label)
    local dev = palette_dev()
    if not dev then
        print("[ERROR] :palette device not found at frame " .. frame)
        return
    end
    io.write("\n=== PALETTE " .. label .. " (frame=" .. frame .. ") ===\n")
    for i = 0, 15 do
        local c = dev:pen_color(i)
        -- MAME pen_color returns ARGB as integer: 0xAARRGGBB
        local r = (c >> 16) & 0xFF
        local g = (c >>  8) & 0xFF
        local b =  c        & 0xFF
        io.write(string.format("  pen%02d: #%02X%02X%02X  (R=%3d G=%3d B=%3d)\n",
            i, r, g, b, r, g, b))
    end
    io.flush()
end

local function set_input(name, val)
    for port_tag, port in pairs(manager.machine.ioport.ports) do
        for field_name, field in pairs(port.fields) do
            if field_name == name then
                field:set_value(val)
            end
        end
    end
end

emu.register_frame_done(function()
    frame = frame + 1

    -- Set DIP on first frame (machine is ready by then)
    if not dip_set and frame == 1 then
        set_input("Demo Mode (Unlim Lives, Start=Adv (Cheat)", 1)
        local dev = palette_dev()
        print("[INFO] DIP cheat set; :palette device = " .. tostring(dev and dev.shortname or "NOT FOUND"))
        dip_set = true
    end

    -- Advance round by pressing Start
    if frame >= FIRST_ADVANCE then
        local elapsed = frame - FIRST_ADVANCE
        local this_advance = math.floor(elapsed / ADVANCE_INTERVAL)
        local phase = elapsed % ADVANCE_INTERVAL

        -- Press Start for 20 frames at start of each interval
        set_input("1 Player Start", phase < 20 and 1 or 0)

        -- Dump palette shortly after the advance (game needs a few frames to load new palette)
        if this_advance > last_advance and phase == 60 then
            round = round + 1
            last_advance = this_advance
            dump_palette("R" .. round)
            manager.machine:save("/home/will/.mame/snap/qbert/palette_r" .. round .. ".png")
        end
    end

    -- Stop after 8 rounds (L1R1 through L2R4)
    if round >= 8 and frame > FIRST_ADVANCE + 8 * ADVANCE_INTERVAL then
        dump_palette("FINAL")
        manager.machine:exit()
    end
end)
