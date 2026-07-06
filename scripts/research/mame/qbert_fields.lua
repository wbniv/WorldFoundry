local OUT = "/home/will/WorldFoundry.2026-new-level/scripts/research/mame/qbert_fields.txt"
local f = io.open(OUT, "w")
local frame = 0
emu.register_frame_done(function()
    frame = frame + 1
    if frame == 2 then
        f:write("=== ALL INPUT FIELDS ===\n")
        for tag, port in pairs(manager.machine.ioport.ports) do
            for name, field in pairs(port.fields) do
                f:write(string.format("PORT:%-30s  FIELD:%s\n", tag, name))
            end
        end
        f:write("=== END ===\n")
        f:close()
        manager.machine:exit()
    end
end)
