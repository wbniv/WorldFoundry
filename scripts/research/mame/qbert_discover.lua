local done = false
emu.register_frame_done(function()
  if done then return end
  done = true
  local out = {}
  for tag, port in pairs(manager.machine.ioport.ports) do
    for name, field in pairs(port.fields) do
      table.insert(out, tag .. " | " .. name .. " | type=" .. field.type)
    end
  end
  table.sort(out)
  for _, s in ipairs(out) do print(s) end
  manager.machine:exit()
end)
