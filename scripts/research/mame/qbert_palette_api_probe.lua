-- Probe what methods/properties the :palette device actually exposes in this MAME build.
local frame = 0

emu.register_frame_done(function()
    frame = frame + 1
    if frame == 120 then
        local dev = manager.machine.devices[":palette"]
        if not dev then
            print("[ERROR] :palette device not found")
            manager.machine:exit()
            return
        end
        print("=== :palette device found, shortname=" .. tostring(dev.shortname) .. " ===")
        -- Direct method probes (pairs() doesn't work on MAME device objects)
        print("--- direct probes ---")
        local probes = {
            "pen_color", "pen", "color", "entries", "num_entries",
            "black_pen", "white_pen", "entry_color", "entry_contrast",
        }
        for _, name in ipairs(probes) do
            print(string.format("  %-20s = %s", name, tostring(dev[name])))
        end
        -- Try calling the ones that look callable
        print("--- call probes ---")
        for _, name in ipairs({"pen_color","pen","entry_color","color"}) do
            local ok, res = pcall(function() return dev[name](dev, 0) end)
            print(string.format("  %s(0) -> ok=%s res=%s", name, tostring(ok), tostring(res)))
        end
        -- Also try screen pixel at known L1R1 apex top-face coordinate (y=57,x=118)
        print("--- screen pixel sample ---")
        for tag, scr in pairs(manager.machine.screens) do
            local ok, px = pcall(function() return scr:pixel(118, 57) end)
            print(string.format("  screen[%s]:pixel(118,57) -> ok=%s px=%s (#%06X)", tag, tostring(ok), tostring(px), px or 0))
        end
        manager.machine:exit()
    end
end)
