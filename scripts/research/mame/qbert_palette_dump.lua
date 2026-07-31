local frame = 0

emu.register_frame_done(function()
  frame = frame + 1
  if frame == 60 then
    -- Try different ways to find the palette
    print("=== DEVICE DUMP ===")
    for tag, dev in pairs(manager.machine.devices) do
      print("device: " .. tag .. " type=" .. tostring(dev.shortname))
    end
    print("=== END DEVICES ===")

    print("=== SCREEN PROPS ===")
    for tag, scr in pairs(manager.machine.screens) do
      print("screen: " .. tag)
      for k, v in pairs(scr) do
        print("  ." .. tostring(k) .. " = " .. tostring(v))
      end
    end
    print("=== END SCREENS ===")

    manager.machine:exit()
  end
end)
