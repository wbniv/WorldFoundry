local frame = 0

emu.register_frame_done(function()
  frame = frame + 1
  if frame == 2 then
    print("=== ALL INPUT FIELDS ===")
    for tag, port in pairs(manager.machine.ioport.ports) do
      for name, field in pairs(port.fields) do
        print(string.format("PORT:%-20s FIELD:%s", tag, name))
      end
    end
    print("=== END FIELDS ===")
    manager.machine:exit()
  end
end)
